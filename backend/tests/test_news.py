import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

import feeds
from main import app

RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title>
<item><title>New AI</title><link>https://EXAMPLE.com:443/story?q=1#top</link><pubDate>Wed, 28 Oct 2026 10:00:00 +0200</pubDate><description>&lt;p&gt;Hello &amp;amp; world&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description></item>
<item><title>Duplicate</title><link>https://example.com/story?q=1</link></item>
<item><title>Undated</title><link>https://example.com/other?q=2</link></item>
<item><title>Unsafe</title><link>javascript:alert(1)</link></item>
<item><title></title><link>https://example.com/empty</link></item>
</channel></rss>'''
EMPTY = b'<rss version="2.0"><channel><title>Empty</title></channel></rss>'


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 28, 12, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(feeds, "datetime", FixedDatetime)


def mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(feeds.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_normalization():
    articles, warning = feeds.parse_feed(RSS, feeds.FEEDS[0][0])
    assert not warning
    assert len(articles) == 3
    assert articles[0].url == "https://example.com/story?q=1"
    assert articles[0].published_at == "2026-10-28T08:00:00Z"
    assert articles[0].description == "Hello & world"
    assert articles[2].published_at is None
    assert articles[2].description == ""
    assert articles[0].id == articles[1].id


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/a", "https://", "https://a:bad/x", "https://user:pass@example.com/x", "https://example.com/\nx"])
def test_unsafe_links(url):
    assert feeds.normalize_url(url) is None


def test_collection_dedup_sort_partial_failure(monkeypatch):
    monkeypatch.setattr(feeds, "FEEDS", (
        (feeds.Source(id="test", name="Test"), "https://example.com/feed"),
        (feeds.Source(id="mit-ai", name="MIT AI"), "https://news.mit.edu/rss"),
    ))
    def handler(request):
        return httpx.Response(503 if request.url.host == "news.mit.edu" else 200, content=RSS)
    mock_client(monkeypatch, handler)
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 1
    assert result.articles[0].title == "New AI"
    assert [source.id for source in result.sources] == ["test"]
    assert result.warnings[0].source_id == "mit-ai"
    assert result.collected_at.endswith("Z")


def test_health_and_all_failure(monkeypatch):
    real_client = httpx.AsyncClient
    mock_client(monkeypatch, lambda request: httpx.Response(500))
    async def check():
        async with real_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/health")).json() == {"status": "ok"}
            response = await client.get("/api/news")
            assert response.status_code == 502
            assert "detail" in response.json()
    asyncio.run(check())


def test_empty_feed_is_success(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=EMPTY))
    result = asyncio.run(feeds.collect_news())
    assert result.articles == []
    assert result.warnings == []


def test_malformed_feed_with_entries():
    articles, warning = feeds.parse_feed(RSS[:-15], feeds.FEEDS[0][0])
    assert articles
    assert warning


def test_unreadable_feed():
    with pytest.raises(ValueError):
        feeds.parse_feed(b'<html>Not a feed</html>', feeds.FEEDS[0][0])


def rss_items(entries):
    items = "".join(
        f"<item><title>{title}</title><link>{url}</link>"
        + (f"<pubDate>{format_datetime(date)}</pubDate>" if date else "")
        + "</item>" for title, url, date in entries
    )
    return f'<rss version="2.0"><channel><title>Test</title>{items}</channel></rss>'.encode()


def test_limit(monkeypatch):
    now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
    content = rss_items([(f"Story {i}", f"https://example.com/{i}", now - timedelta(minutes=i)) for i in reversed(range(15))])
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=content))
    result = asyncio.run(feeds.collect_news())
    assert [a.title for a in result.articles] == [f"Story {i}" for i in range(10)]
    assert result.articles == asyncio.run(feeds.collect_news()).articles


def test_freshness_boundaries_and_duplicates(monkeypatch):
    now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
    content = rss_items([
        ("Unknown", "https://example.com/unknown", None),
        ("Old", "https://example.com/old", now - timedelta(hours=24, seconds=1)),
        ("Future", "https://example.com/future", now + timedelta(seconds=1)),
        ("Boundary", "https://example.com/boundary", now - timedelta(hours=24)),
        ("Earlier duplicate", "https://example.com/new#first", now - timedelta(hours=1)),
        ("Newest duplicate", "https://example.com/new", now),
    ])
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=content))
    result = asyncio.run(feeds.collect_news())
    assert [a.title for a in result.articles] == ["Newest duplicate", "Boundary"]


def test_no_recent_articles_is_success(monkeypatch):
    content = rss_items([("Old", "https://example.com/old", datetime(2020, 1, 1, tzinfo=timezone.utc))])
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=content))
    result = asyncio.run(feeds.collect_news())
    assert result.articles == []
    assert result.warnings == []


def test_google_publisher_metadata():
    content = b'''<rss version="2.0"><channel><title>Google</title><item>
    <title>Acme launches Atlas model - Example News</title>
    <link>https://news.google.com/rss/articles/test</link>
    <source url="https://www.example.com">Example News</source>
    </item></channel></rss>'''
    article = feeds.parse_feed(content, feeds.FEEDS[0][0])[0][0]
    assert article.source == "Example News"
    assert article.source_id.startswith("publisher-")
    assert article.title == "Acme launches Atlas model"
    assert article.source_id == feeds.parse_feed(content, feeds.FEEDS[1][0])[0][0].source_id


def test_topic_overlap_does_not_inflate_publishers(monkeypatch):
    content = RSS.replace(b"<title>New AI</title>", b'<source url="https://example.com">Example</source><title>New AI - Example</title>')
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=content))
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 1
    assert result.articles[0].publisher_count == 1
    assert len(result.articles[0].coverage) == 1
    assert result.sources[0].name == "Example"
