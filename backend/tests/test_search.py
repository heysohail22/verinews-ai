import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from ddgs.exceptions import DDGSException

import feeds
import readable_news
import ai_ranking
from schemas import ExtractedArticle
from schemas import NewsResponse


@pytest.fixture(autouse=True)
def readable_context(monkeypatch):
    async def extracted(request):
        return ExtractedArticle(url=request.url, source=request.source, text="Acme Atlas article context. " * 40, word_count=160, truncated=False)
    monkeypatch.setattr(readable_news, "extract_story", extracted)
    async def reviewed(response, progress=None):
        return response
    monkeypatch.setattr(ai_ranking, "rank_ai_news", reviewed)


def row(**changes):
    return {"title": "Acme launches Atlas model", "url": "https://publisher.example/story", "source": "Example", "body": "<p>Developer preview.</p>", "date": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), **changes}


def test_normalize_search_results():
    result = feeds.parse_search_result(row())
    assert result.description == "Developer preview."
    assert result.published_at.endswith("Z")
    assert result.source == "Example"
    assert feeds.parse_search_result(row(url="javascript:alert(1)")) is None
    assert feeds.parse_search_result(row(title=" ")) is None
    assert feeds.parse_search_result(row(date="unknown")).published_at is None
    assert feeds.parse_search_result(row(date="2026-10-28T10:00:00")).published_at is None
    assert feeds.parse_search_result(row(date=1793188800)).published_at.endswith("Z")


def test_search_parameters_regions_and_dedup(monkeypatch):
    calls = []
    class Client:
        def __init__(self, timeout):
            assert timeout == 8
        def news(self, query, **kwargs):
            calls.append((query, kwargs))
            return [row()]
    monkeypatch.setattr(feeds, "DDGS", Client)
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 1
    assert result.warnings == []
    assert len(calls) == 4
    assert result.articles[0].publisher_count == 1
    assert {kwargs["region"] for _, kwargs in calls} == {"in-en", "us-en"}
    assert all(query == "latest ai news" and kwargs["timelimit"] == "d" and kwargs["backend"] == "bing,yahoo" and kwargs["max_results"] == 20 for query, kwargs in calls)


def test_partial_search_failure_keeps_results(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        def news(self, query, **kwargs):
            if kwargs["region"] == "us-en":
                raise DDGSException("upstream failure")
            return [row()]
    monkeypatch.setattr(feeds, "DDGS", Client)
    result = asyncio.run(feeds.collect_news())
    assert len(result.articles) == 1
    assert result.warnings[0].source_id == "ddgs-us-en"


def test_unavailable_search_fails_without_fallback(monkeypatch):
    async def unavailable(**kwargs):
        raise feeds.NewsSearchFailed()
    monkeypatch.setattr(feeds, "collect_search_news", unavailable)
    with pytest.raises(feeds.NewsSearchFailed):
        asyncio.run(feeds.collect_news())


def test_empty_search_has_no_provider_switch_warning(monkeypatch):
    response = NewsResponse(articles=[], sources=[], warnings=[], collected_at="2026-10-28T12:00:00Z")
    async def empty():
        return response
    monkeypatch.setattr(feeds, "collect_search_news", empty)
    assert asyncio.run(feeds.collect_news()) == response


def test_search_date_window(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        def news(self, *args, **kwargs):
            return [row(url="https://example.com/old", date=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat()), row(url="https://example.com/future", date=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()), row()]
    monkeypatch.setattr(feeds, "DDGS", Client)
    result = asyncio.run(feeds.collect_search_news())
    assert [article.url for article in result.articles] == ["https://publisher.example/story"]



def test_top_ten_limit(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        def news(self, *args, **kwargs):
            return [row(title=f"Distinct story {i}", url=f"https://example.com/{i}") for i in range(15)]
    monkeypatch.setattr(feeds, "DDGS", Client)
    assert len(asyncio.run(feeds.collect_news()).articles) == 10



def test_pagination_preserves_large_pool_before_final_selection(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        def news(self, query, **kwargs):
            calls.append((kwargs["region"], kwargs["page"]))
            return [row(title=f"Event {kwargs['page'] * 20 + i}", url=f"https://example.com/{kwargs['region']}/{kwargs['page']}/{i}") for i in range(20)]
    monkeypatch.setattr(feeds, "DDGS", Client)
    result = asyncio.run(feeds.collect_search_news())
    assert len(calls) == 6
    assert result.candidates_found == 120
    assert len(result.articles) > 30
