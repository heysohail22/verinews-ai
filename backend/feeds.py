import asyncio
import calendar
import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import feedparser
import httpx

from schemas import Article, NewsResponse, Source, Warning

FEEDS = (
    (Source(id="techcrunch-ai", name="TechCrunch AI"), "https://techcrunch.com/category/artificial-intelligence/feed/"),
    (Source(id="ars-technica", name="Ars Technica"), "https://feeds.arstechnica.com/arstechnica/index"),
    (Source(id="mit-ai", name="MIT News · AI"), "https://news.mit.edu/rss/topic/artificial-intelligence2"),
)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value):
    parser = PlainText()
    parser.feed(str(value or ""))
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def normalize_url(value):
    try:
        value = str(value or "").strip()
        if re.search(r"[\x00-\x20\x7f]", value):
            return None
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        port = parts.port
        host = parts.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port and not (parts.scheme.lower() == "https" and port == 443 or parts.scheme.lower() == "http" and port == 80):
            host += f":{port}"
        return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def parse_feed(content, source):
    parsed = feedparser.parse(content)
    if not parsed.entries and (parsed.bozo or not parsed.version):
        raise ValueError("Unreadable feed")
    articles = []
    for entry in parsed.entries:
        title = plain_text(entry.get("title"))
        url = normalize_url(entry.get("link"))
        if not title or not url:
            continue
        published = None
        date = entry.get("published_parsed") or entry.get("updated_parsed")
        if date:
            try:
                published = datetime.fromtimestamp(calendar.timegm(date), timezone.utc).isoformat().replace("+00:00", "Z")
            except (ValueError, OverflowError, OSError):
                pass
        articles.append(Article(id=hashlib.sha256(url.encode()).hexdigest(), title=title, url=url,
                                source_id=source.id, source=source.name, published_at=published,
                                description=plain_text(entry.get("summary") or entry.get("description"))))
    return articles, bool(parsed.bozo)


async def collect_news():
    semaphore = asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), follow_redirects=True,
                                 headers={"User-Agent": "VeriNews/1.0 RSS Reader"}) as client:
        async def fetch(source, url):
            async with semaphore:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    articles, malformed = parse_feed(response.content, source)
                    return articles, Warning(source_id=source.id, message="Feed formatting issues; some entries may be missing.") if malformed else None, True
                except (httpx.HTTPError, ValueError):
                    return [], Warning(source_id=source.id, message="Source is currently unavailable. Try collecting again later."), False
        results = await asyncio.gather(*(fetch(*feed) for feed in FEEDS))
    if not any(result[2] for result in results):
        raise AllFeedsFailed()
    unique = {}
    for articles, _, _ in results:
        for article in articles:
            unique.setdefault(article.url, article)
    articles = sorted(unique.values(), key=lambda a: (a.url, a.source_id))
    articles.sort(key=lambda a: a.published_at or "", reverse=True)
    return NewsResponse(articles=articles[:100], sources=[source for source, _ in FEEDS],
                        collected_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        warnings=[warning for _, warning, _ in results if warning])


class AllFeedsFailed(Exception):
    pass
