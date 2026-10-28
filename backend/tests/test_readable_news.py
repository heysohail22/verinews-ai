import asyncio

from fastapi import HTTPException

import readable_news
from schemas import Article, Coverage, ExtractedArticle, NewsResponse


def story(i):
    return Article(id=str(i), title=f"Story {i}", url=f"https://example.com/{i}", source="Example", source_id="example", published_at="2026-10-28T12:00:00Z", description="Search snippet", coverage=[Coverage(title=f"Story {i}", url=f"https://example.com/{i}", source="Example", source_id="example", published_at="2026-10-28T12:00:00Z")])


def response(count):
    return NewsResponse(articles=[story(i) for i in range(count)], sources=[], warnings=[], collected_at="2026-10-28T12:00:00Z")


def context(request, **changes):
    return ExtractedArticle(url=request.url, source=request.source, text="This is readable publisher article text. " * 20, word_count=120, truncated=False, **changes)


def test_removes_unreadable_and_backfills_top_ten(monkeypatch):
    async def extract(request):
        if request.url.endswith(("/0", "/1")):
            raise HTTPException(status_code=422, detail="Unavailable")
        return context(request)
    monkeypatch.setattr(readable_news, "extract_story", extract)
    result = asyncio.run(readable_news.retain_readable_stories(response(15)))
    assert len(result.articles) == 10
    assert result.articles[0].title == "Story 2"
    assert result.articles[-1].title == "Story 11"
    assert all(item.content and item.content_word_count >= 60 for item in result.articles)
    assert result.articles[0].description != "Search snippet"


def test_all_unreadable_is_empty_collection(monkeypatch):
    async def unavailable(request):
        raise HTTPException(status_code=422, detail="Unavailable")
    monkeypatch.setattr(readable_news, "extract_story", unavailable)
    result = asyncio.run(readable_news.retain_readable_stories(response(3)))
    assert result.articles == []
    assert result.sources == []


def test_public_excerpt_and_selected_publisher_are_preserved(monkeypatch):
    async def extract(request):
        return ExtractedArticle(url="https://other.example/story", source="Other", text="Publicly readable text. " * 30, word_count=90, truncated=True, access_note="May be incomplete")
    monkeypatch.setattr(readable_news, "extract_story", extract)
    candidate = response(1)
    candidate.articles[0].coverage.append(Coverage(title="Story 0", source="Other", source_id="other", url="https://other.example/story", published_at=None))
    result = asyncio.run(readable_news.retain_readable_stories(candidate))
    item = result.articles[0]
    assert item.content_is_excerpt
    assert item.content_note == "May be incomplete"
    assert item.url == "https://other.example/story"
    assert item.source_id == "other"
    assert item.published_at is None


def test_slow_article_is_skipped(monkeypatch):
    async def timeout(request):
        raise TimeoutError()
    monkeypatch.setattr(readable_news, "extract_story", timeout)
    assert asyncio.run(readable_news.retain_readable_stories(response(1))).articles == []


def test_continues_beyond_first_thirty_candidates(monkeypatch):
    async def extract(request):
        index = int(request.url.rsplit("/", 1)[1])
        if index < 31:
            raise HTTPException(status_code=422, detail="Unavailable")
        return context(request)
    monkeypatch.setattr(readable_news, "extract_story", extract)
    result = asyncio.run(readable_news.retain_readable_stories(response(45)))
    assert len(result.articles) == 10
    assert result.articles[0].title == "Story 31"
    assert result.stories_checked > 30
