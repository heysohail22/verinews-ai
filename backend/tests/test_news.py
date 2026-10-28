import asyncio

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
    def handler(request):
        return httpx.Response(503 if request.url.host == "news.mit.edu" else 200, content=RSS)
    mock_client(monkeypatch, handler)
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 2
    assert result.articles[0].title == "New AI"
    assert result.articles[1].published_at is None
    assert len(result.sources) == 3
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


def test_limit(monkeypatch):
    content = ('<rss version="2.0"><channel><title>Many</title>' + ''.join(f'<item><title>Story {i}</title><link>https://example.com/{i}</link></item>' for i in range(110)) + '</channel></rss>').encode()
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=content))
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 100
    assert result.articles == asyncio.run(feeds.collect_news()).articles
