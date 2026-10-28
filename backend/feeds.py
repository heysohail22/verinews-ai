import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit


from schemas import Article, NewsResponse, Source, Warning
from stories import rank_stories
from ddgs import DDGS
from ddgs.exceptions import DDGSException

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


def make_news_response(results, limit=10, group=True):
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
    articles = rank_stories(list(unique.values()), limit=limit) if group else sorted(unique.values(), key=lambda item: (item.published_at, item.url), reverse=True)
    publishers = {item.source_id: Source(id=item.source_id, name=item.source)
                  for article in articles for item in (article.coverage or [article])}
    return NewsResponse(articles=articles, sources=sorted(publishers.values(), key=lambda source: source.name.casefold()),
                        collected_at=collected_at.isoformat().replace("+00:00", "Z"),
                        candidates_found=sum(len(items) for items, _, _ in results),
                        warnings=[warning for _, warning, _ in results if warning])


SEARCH_REGIONS = (("in-en", "India"), ("us-en", "US"))


def parse_search_result(entry):
    if not isinstance(entry, dict):
        return None
    title = plain_text(entry.get("title"))
    url = normalize_url(entry.get("url"))
    if not title or not url:
        return None
    published = None
    raw_date = entry.get("date")
    try:
        if isinstance(raw_date, (int, float)) and not isinstance(raw_date, bool):
            date = datetime.fromtimestamp(raw_date, timezone.utc)
        else:
            date = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        if date.tzinfo is not None:
            published = date.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    publisher = plain_text(entry.get("source")) or urlsplit(url).hostname.removeprefix("www.")
    identity = re.sub(r"\s+on\s+msn\.com$", "", publisher.casefold()).strip()
    return Article(id=hashlib.sha256(url.encode()).hexdigest(), title=title, url=url,
                   source_id="publisher-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                   source=publisher, published_at=published, description=plain_text(entry.get("body")))


SEARCH_PAGES = 3
RESULTS_PER_PAGE = 20


async def collect_search_news():
    semaphore = asyncio.Semaphore(2)
    async def search(region, name):
        rows_seen = []
        urls_seen = set()
        warning = None
        succeeded = False
        async with semaphore:
            try:
                async with asyncio.timeout(30):
                    client = DDGS(timeout=8)
                    for page in range(1, SEARCH_PAGES + 1):
                        rows = await asyncio.to_thread(
                            client.news, "latest ai news", region=region, page=page,
                            safesearch="moderate", timelimit="d", max_results=RESULTS_PER_PAGE, backend="bing,yahoo",
                        )
                        succeeded = True
                        new_rows = [entry for entry in rows if isinstance(entry, dict) and entry.get("url") not in urls_seen]
                        if not new_rows:
                            break
                        rows_seen.extend(new_rows)
                        urls_seen.update(entry.get("url") for entry in new_rows)
            except (DDGSException, TimeoutError, OSError, ValueError) as exc:
                # DDGS signals the end of available pages with this exception.
                if not (succeeded and isinstance(exc, DDGSException) and "No results found" in str(exc)):
                    warning = Warning(source_id=f"ddgs-{region}", message=f"Bing/Yahoo News · {name}: Some search results are unavailable.")
        articles = [article for row in rows_seen if (article := parse_search_result(row))]
        return articles, warning, succeeded
    results = await asyncio.gather(*(search(*region) for region in SEARCH_REGIONS))
    if not any(result[2] for result in results):
        raise NewsSearchFailed()
    # Date filtering, deduplication and grouping see the whole retrieved pool.
    return make_news_response(results, limit=SEARCH_PAGES * RESULTS_PER_PAGE * len(SEARCH_REGIONS), group=False)


async def collect_news(progress=None):
    from ai_ranking import rank_ai_news
    from readable_news import retain_readable_stories
    if progress:
        await progress({"stage": "search", "message": "Collecting AI news candidates from Bing/Yahoo"})
    candidates = await collect_search_news()
    reviewed = await rank_ai_news(candidates, progress=progress)
    if progress:
        await progress({"stage": "reading", "message": "Reading AI-selected articles and preparing your top stories"})
    return await retain_readable_stories(reviewed, progress=progress)


class NewsSearchFailed(Exception):
    pass
