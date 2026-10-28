import asyncio

import httpx
import pytest

import feeds
from main import app


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/a", "https://", "https://a:bad/x", "https://user:pass@example.com/x", "https://example.com/\nx"])
def test_unsafe_links(url):
    assert feeds.normalize_url(url) is None


def test_plain_text_and_url_normalization():
    assert feeds.plain_text("<p>Hello &amp; world</p><script>bad()</script>") == "Hello & world"
    assert feeds.normalize_url("https://EXAMPLE.com:443/story?q=1#top") == "https://example.com/story?q=1"


def test_health_and_search_failure(monkeypatch):
    async def unavailable(**kwargs):
        raise feeds.NewsSearchFailed()
    monkeypatch.setattr(feeds, "collect_search_news", unavailable)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/health")).json() == {"status": "ok"}
            result = await client.get("/api/news")
            assert result.status_code == 502
            assert "Bing/Yahoo" in result.json()["detail"]
            assert "RSS is disabled" in result.json()["detail"]
    asyncio.run(check())
