import asyncio
import calendar
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, urlunsplit

import feedparser
import httpx

from schemas import Article, NewsResponse, Source, Warning
from stories import rank_stories

TOPICS = (
    ("ai", "artificial intelligence"),
    ("models", '"AI model" OR LLM'),
    ("agents", '"AI agents"'),
    ("regulation", '"AI regulation"'),
    ("companies", 'OpenAI OR Anthropic OR DeepMind'),
)
FEEDS = tuple(
    (Source(id=f"google-news-{topic}", name=f"Google News · {query}"),
     "https://news.google.com/rss/search?" + urlencode({
         "q": f"({query}) when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en",
     }))
    for topic, query in TOPICS
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
        publisher = source
        entry_source = entry.get("source") or {}
        publisher_name = plain_text(entry_source.get("title"))
        if source.id.startswith("google-news-") and publisher_name:
            publisher_url = normalize_url(entry_source.get("href"))
            identity = urlsplit(publisher_url).hostname.removeprefix("www.") if publisher_url else publisher_name.casefold()
            publisher = Source(id="publisher-" + hashlib.sha256(identity.encode()).hexdigest()[:16], name=publisher_name)
            # Google appends the publisher to the headline; omit it for grouping.
            suffix = f" - {publisher_name}"
            if title.endswith(suffix):
                title = title[:-len(suffix)].strip()
            if not title:
                continue
        elif source.id.startswith("google-news-"):
            # Missing attribution must not count separate topic feeds as publishers.
            publisher = Source(id="google-news-unattributed", name="Google News (publisher unavailable)")
        articles.append(Article(id=hashlib.sha256(url.encode()).hexdigest(), title=title, url=url,
                                source_id=publisher.id, source=publisher.name, published_at=published,
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
                    return articles, Warning(source_id=source.id, message=f"{source.name}: Feed formatting issues; some entries may be missing.") if malformed else None, True
                except (httpx.HTTPError, ValueError):
                    return [], Warning(source_id=source.id, message=f"{source.name}: Source is currently unavailable. Try collecting again later."), False
        results = await asyncio.gather(*(fetch(*feed) for feed in FEEDS))
    if not any(result[2] for result in results):
        raise AllFeedsFailed()
    collected_at = datetime.now(timezone.utc)
    cutoff = collected_at - timedelta(hours=24)
    unique = {}
    for articles, _, _ in results:
        for article in articles:
            if not article.published_at:
                continue
            published_at = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
            if cutoff <= published_at <= collected_at:
                previous = unique.get(article.url)
                if previous is None or article.published_at > previous.published_at:
                    unique[article.url] = article
    articles = rank_stories(list(unique.values()))
    publishers = {item.source_id: Source(id=item.source_id, name=item.source)
                  for article in articles for item in article.coverage}
    return NewsResponse(articles=articles, sources=sorted(publishers.values(), key=lambda source: source.name.casefold()),
                        collected_at=collected_at.isoformat().replace("+00:00", "Z"),
                        warnings=[warning for _, warning, _ in results if warning])


class AllFeedsFailed(Exception):
    pass
