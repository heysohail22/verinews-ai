import asyncio
import json

import httpx
import pytest

import ai_ranking
import main
from schemas import Article, NewsResponse


def news(count):
    return NewsResponse(articles=[Article(id=f"original-{i}", title=f"AI event {i}", url=f"https://example.com/{i}", source=f"Publisher {i}", source_id=str(i), published_at="2026-10-28T12:00:00Z", description="A useful search description") for i in range(count)], sources=[], warnings=[], collected_at="2026-10-28T12:00:00Z")


def assessment(record, **changes):
    return {"id": record["id"], "relevance": 90, "importance": int(record["id"][1:]), "decision": "keep", "reason": "Concrete AI development", **changes}


def mock_model(monkeypatch, handler):
    real = httpx.AsyncClient
    def handle(request):
        body = json.loads(request.content)
        assert body["think"] is False
        assert body["stream"] is False
        assert body["keep_alive"] == 0
        assert body["options"]["num_ctx"] == 4096
        assert "untrusted" in body["messages"][0]["content"]
        records = json.loads(body["messages"][1]["content"])
        assert len(records) <= 5
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({"articles": handler(records)})}})
    monkeypatch.setattr(ai_ranking.httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handle), **kwargs))
    return real


def test_every_headline_is_reviewed_before_selection(monkeypatch):
    seen = []
    def handler(records):
        seen.extend(record["id"] for record in records)
        return [assessment(record, decision="exclude" if record["id"] == "a0" else "keep") for record in records]
    mock_model(monkeypatch, handler)
    events = []
    async def progress(event):
        events.append(event)
    result = asyncio.run(ai_ranking.rank_ai_news(news(41), progress))
    assert seen == [f"a{i}" for i in range(41)]
    assert result.ai_reviewed == 41
    assert result.ai_selected == 40
    assert len(result.articles) == 40
    assert result.articles[0].id == "original-40"
    assert events[-1]["completed"] == 41


def test_uncertain_headline_gets_description_second_pass(monkeypatch):
    calls = []
    def handler(records):
        calls.append(records)
        return [assessment(record, decision="keep" if "description" in record else "uncertain") for record in records]
    mock_model(monkeypatch, handler)
    result = asyncio.run(ai_ranking.rank_ai_news(news(1)))
    assert len(calls) == 2
    assert "description" not in calls[0][0]
    assert calls[1][0]["description"]
    assert len(result.articles) == 1


@pytest.mark.parametrize("failure", ["missing", "duplicate", "invented", "score"])
def test_invalid_assessments_fail_closed(monkeypatch, failure):
    def handler(records):
        result = [assessment(record) for record in records]
        if failure == "missing": return result[:-1]
        if failure == "duplicate": return result + [result[0]]
        if failure == "invented": result[0]["id"] = "unknown"
        if failure == "score": result[0]["relevance"] = 101
        return result
    mock_model(monkeypatch, handler)
    with pytest.raises(ai_ranking.AIRankingError):
        asyncio.run(ai_ranking.rank_ai_news(news(2)))


def test_ai_keep_decision_is_not_overridden_by_score_cutoff(monkeypatch):
    def handler(records):
        return [assessment(record, relevance=20 if record["id"] == "a0" else 90, decision="keep" if record["id"] == "a0" else "uncertain") for record in records]
    mock_model(monkeypatch, handler)
    result = asyncio.run(ai_ranking.rank_ai_news(news(2)))
    assert [article.id for article in result.articles] == ["original-0"]
    assert result.articles[0].ai_relevance == 20
    assert result.ai_reviewed == 2


def test_stream_emits_real_progress_and_result(monkeypatch):
    async def collect(progress=None):
        await progress({"stage": "ranking", "completed": 1, "total": 1, "message": "Reviewed 1 headline"})
        return news(1)
    monkeypatch.setattr(main, "collect_news", collect)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            response = await client.get("/api/news/stream")
            events = [json.loads(line) for line in response.text.splitlines()]
            assert events[0]["stage"] == "ranking"
            assert events[-1]["type"] == "result"
            assert events[-1]["data"]["articles"]
    asyncio.run(check())


def test_stream_reports_review_error_without_results(monkeypatch):
    async def collect(progress=None):
        raise ai_ranking.AIRankingError("Cannot reach Ollama")
    monkeypatch.setattr(main, "collect_news", collect)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            response = await client.get("/api/news/stream")
            events = [json.loads(line) for line in response.text.splitlines()]
            assert events == [{"type": "error", "message": "Cannot reach Ollama"}]
    asyncio.run(check())


def test_invalid_batch_recovers_by_splitting(monkeypatch):
    sizes = []
    def handler(records):
        sizes.append(len(records))
        return [] if len(records) > 1 else [assessment(records[0])]
    mock_model(monkeypatch, handler)
    result = asyncio.run(ai_ranking.rank_ai_news(news(5)))
    assert result.ai_reviewed == 5
    assert result.ai_selected == 5
    assert sizes[0] == 5
    assert sizes.count(1) == 5


def test_transient_single_headline_failure_is_retried(monkeypatch):
    calls = []
    def handler(records):
        calls.append(records)
        return [] if len(calls) == 1 else [assessment(records[0])]
    mock_model(monkeypatch, handler)
    result = asyncio.run(ai_ranking.rank_ai_news(news(1)))
    assert result.ai_reviewed == 1
    assert len(calls) == 2
