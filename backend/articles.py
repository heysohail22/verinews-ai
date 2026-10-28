"""Bounded, on-demand article extraction. No persistent article storage."""
import asyncio
import ipaddress
import json
import re
import socket
import time
from collections import OrderedDict
from html import unescape
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx
import trafilatura
from fastapi import HTTPException

from feeds import normalize_url
from schemas import ArticleCandidate, ExtractedArticle

MAX_BYTES = 3_000_000
MAX_TEXT = 24_000
MIN_WORDS = 60
_cache: OrderedDict[str, tuple[float, ExtractedArticle]] = OrderedDict()


class InsufficientArticleText(ValueError):
    def __init__(self, url: str, word_count: int):
        self.url = url
        self.word_count = word_count
        super().__init__("Not enough article context")


async def public_url(url: str) -> str:
    normalized = normalize_url(url)
    if not normalized:
        raise ValueError("Invalid URL")
    parts = urlsplit(normalized)
    if parts.port not in (None, 80, 443) or parts.hostname.endswith((".localhost", ".local")):
        raise ValueError("Non-public URL")
    addresses = await asyncio.get_running_loop().getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global or ipaddress.ip_address(item[4][0]).is_multicast for item in addresses):
        raise ValueError("Non-public address")
    return normalized


async def read_page(client, url, *, method="GET", data=None):
    for _ in range(6):
        url = await public_url(url)
        async with client.stream(method, url, data=data) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Missing redirect")
                url = urljoin(url, location)
                if response.status_code == 303 or response.status_code in {301, 302} and method == "POST":
                    method, data = "GET", None
                continue
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError("Page too large")
            return url, bytes(content), response.headers.get("content-type", "").lower()
    raise ValueError("Too many redirects")


def google_host(url):
    return urlsplit(url).hostname == "news.google.com"


async def resolve_google(client, url):
    path = urlsplit(url).path
    match = re.fullmatch(r"/(?:rss/)?(?:articles|read)/([A-Za-z0-9_-]+)", path)
    if not match:
        raise ValueError("Unsupported Google News link")
    article_id = match[1]
    locale = parse_qs(urlsplit(url).query)
    region = "IN" if locale.get("gl", [""])[0] == "IN" or locale.get("ceid", [""])[0] == "IN:en" else "US"
    language = "en-IN" if region == "IN" else "en-US"
    edition = f"{region}:en"
    page_url = f"https://news.google.com/rss/articles/{article_id}?" + urlencode({"hl": language, "gl": region, "ceid": edition})
    resolved, content, _ = await read_page(client, page_url)
    if not google_host(resolved):
        return resolved
    page = content.decode("utf-8", errors="replace")
    signature = re.search(r'data-n-a-sg=["\']([^"\']+)', page)
    timestamp = re.search(r'data-n-a-ts=["\'](\d+)', page)
    if not signature or not timestamp:
        raise ValueError("Google News resolution unavailable")
    # Google's undocumented URL-resolution RPC; may change or be rate-limited.
    context = [["X", "X", ["X", "X"], None, None, 1, 1, edition, None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0]
    request = ["garturlreq", context, article_id, int(timestamp[1]), unescape(signature[1])]
    envelope = [[["Fbv4je", json.dumps(request), None, "generic"]]]
    _, raw, _ = await read_page(client, "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je", method="POST", data={"f.req": json.dumps(envelope)})
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("["):
            continue
        try:
            rows = json.loads(line)
            for row in rows:
                if isinstance(row, list) and len(row) > 2 and row[0] == "wrb.fr" and row[1] == "Fbv4je":
                    result = json.loads(row[2])
                    if result[0] == "garturlres" and isinstance(result[1], str) and not google_host(result[1]):
                        return await public_url(result[1])
        except (ValueError, TypeError, IndexError):
            continue
    raise ValueError("No publisher URL returned")


def readable_article(content: bytes, url: str) -> ExtractedArticle:
    if re.search(rb'"isAccessibleForFree"\s*:\s*(?:false|"false")', content, re.IGNORECASE):
        raise ValueError("Subscription article")
    text = trafilatura.extract(content, url=url, include_comments=False, include_tables=False, favor_precision=True)
    if re.search(rb"<title[^>]*>\s*(?:Client Challenge|Just a moment)[^<]*</title>", content, re.IGNORECASE) or re.search(r"^(?:access denied|just a moment|verify you are human|enable javascript|javascript is disabled)", (text or "").strip(), re.IGNORECASE):
        raise ValueError("Blocked page")
    if not text or len(text.split()) < MIN_WORDS:
        raise InsufficientArticleText(url, len((text or "").split()))
    truncated = len(text) > MAX_TEXT
    if truncated:
        text = text[:MAX_TEXT].rsplit(" ", 1)[0]
    return ExtractedArticle(url=url, text=text, word_count=len(text.split()), truncated=truncated)


async def extract_article(url: str) -> ExtractedArticle:
    key = normalize_url(url)
    if not key:
        raise HTTPException(status_code=422, detail="A valid HTTP(S) article URL is required.")
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        _cache.move_to_end(key)
        return cached[1]
    try:
        async with asyncio.timeout(45):
            async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), follow_redirects=False,
                                         headers={"User-Agent": "VeriNews/1.0 Article Reader"}) as client:
                url = await public_url(key)
                if google_host(url):
                    url = await resolve_google(client, url)
                final_url, content, content_type = await read_page(client, url)
                if google_host(final_url) or not any(kind in content_type for kind in ("text/html", "application/xhtml+xml")):
                    raise ValueError("Not a publisher article")
                article = await asyncio.to_thread(readable_article, content, final_url)
    except (httpx.HTTPError, ValueError, OSError, TimeoutError) as exc:
        if isinstance(exc, InsufficientArticleText):
            domain = urlsplit(exc.url).hostname
            detail = f"Full article unavailable: only {exc.word_count} readable words were extracted from {domain}; at least {MIN_WORDS} are needed. Other collected coverage will be tried when available. No post was generated."
        elif isinstance(exc, ValueError) and str(exc) == "Blocked page":
            detail = "The publisher returned a browser/JavaScript challenge instead of article text. Other collected coverage will be tried when available."
        elif isinstance(exc, ValueError) and str(exc) == "Subscription article":
            detail = "Full article unavailable: the publisher marks this as subscription content."
        elif isinstance(exc, httpx.HTTPStatusError):
            detail = f"Full article unavailable: the publisher or Google News returned HTTP {exc.response.status_code}. Other collected coverage will be tried when available."
        elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
            detail = "Full article unavailable: the request timed out. Try again later."
        else:
            detail = "Full article unavailable: the link could not be resolved or read. Other collected coverage will be tried when available."
        raise HTTPException(status_code=422, detail=detail) from None
    entry = (time.monotonic() + 600, article)
    _cache[key] = entry
    _cache[article.url] = entry
    _cache.move_to_end(key)
    while len(_cache) > 20:
        _cache.popitem(last=False)
    return article


def validate_article_match(article: ExtractedArticle, expected_title: str) -> None:
    # Reject obvious topic mismatches; this is not semantic verification.
    common = set("a an the and or of for to in on at by with from its is are as new ai artificial intelligence news says said say will he she it his her term latest announces announced announce launches launched launch releases released release unveils unveiled unveil".split())
    words = set(re.findall(r"[^\W_]+", expected_title.casefold())) - common
    text_words = set(re.findall(r"[^\W_]+", article.text.casefold()))
    if words and len(words & text_words) < min(2, len(words)):
        raise HTTPException(status_code=422, detail="The resolved article does not appear to match this headline. Other collected coverage will be tried when available; no post was generated from the unrelated page.")


async def extract_story(request) -> ExtractedArticle:
    """Try at most four collected URLs within a shared one-minute budget."""
    candidates = [ArticleCandidate(url=request.url, source=request.source), *request.alternatives]
    seen = set()
    failures = []
    try:
        async with asyncio.timeout(60):
            for candidate in candidates:
                key = normalize_url(candidate.url)
                if not key:
                    continue
                # Locale variations of the same Google article aren't new coverage.
                identity = urlsplit(key).path if google_host(key) else key
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    article = await extract_article(key)
                    validate_article_match(article, request.expected_title)
                    return article.model_copy(update={"source": candidate.source})
                except HTTPException as exc:
                    failures.append(exc.detail)
                if len(seen) >= 4:
                    break
    except TimeoutError:
        failures.append("Article reading timed out.")
    if len(seen) == 1 and failures:
        detail = f"{failures[0]} No other collected coverage is available for this story."
    else:
        detail = f"Could not read matching article text from {len(seen)} collected sources. They may be blocked, unavailable or too short. Try another story or collect news again."
    raise HTTPException(status_code=422, detail=detail)
