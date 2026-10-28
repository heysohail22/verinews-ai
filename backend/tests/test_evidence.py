import asyncio
import json

import httpx
import pytest

import evidence
from schemas import ExtractedArticle, PostRequest

STORY = PostRequest(title="Acme released Atlas today", url="https://original.example/story", source="Original")
TEXT = "Acme released Atlas today for all developers. " * 20


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(evidence, "search_sources", lambda claim: [{"title": "Atlas report", "href": f"https://source{i}.example/story"} for i in range(3)])
    async def extract(url):
        # Different source texts; avoid duplicate-copy detection.
        return ExtractedArticle(url=url, text=TEXT + (url + " different evidence ") * 100, word_count=500, truncated=False)
    monkeypatch.setattr(evidence, "extract_article", extract)


def test_support_requires_two_sources(setup, monkeypatch):
    async def compare(client, claim, text):
        return evidence.Comparison(relationship="supports", passage="Acme released Atlas today for all developers.", explanation="Reports release")
    monkeypatch.setattr(evidence, "compare_source", compare)
    result = asyncio.run(evidence.check_evidence(STORY))
    assert result.status == "supported"
    assert len(result.sources) == 3


def test_contradiction_is_visible(setup, monkeypatch):
    async def compare(client, claim, text):
        return evidence.Comparison(relationship="contradicts", passage="Acme released Atlas today for all developers.", explanation="Disagreement")
    monkeypatch.setattr(evidence, "compare_source", compare)
    assert asyncio.run(evidence.check_evidence(STORY)).status == "conflicting_evidence"


def test_no_search_evidence_is_insufficient(monkeypatch):
    monkeypatch.setattr(evidence, "search_sources", lambda claim: [])
    assert asyncio.run(evidence.check_evidence(STORY)).status == "insufficient_evidence"


def test_fabricated_passage_is_rejected():
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({"relationship": "supports", "passage": "An invented claim not present in any source text.", "explanation": "Invented"})}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            assert await evidence.compare_source(client, STORY.title, TEXT) is None
    asyncio.run(run())
    assert len(calls) == 2


def test_original_domain_and_duplicate_copies_not_counted(monkeypatch):
    monkeypatch.setattr(evidence, "search_sources", lambda claim: [{"href": "https://original.example/other"}, {"href": "https://one.example/a"}, {"href": "https://two.example/a"}])
    async def extract(url):
        assert "original.example" not in url
        return ExtractedArticle(url=url, text=TEXT, word_count=160, truncated=False)
    async def compare(client, claim, text):
        return evidence.Comparison(relationship="supports", passage="Acme released Atlas today for all developers.", explanation="Reports release")
    monkeypatch.setattr(evidence, "extract_article", extract)
    monkeypatch.setattr(evidence, "compare_source", compare)
    result = asyncio.run(evidence.check_evidence(STORY))
    assert len(result.sources) == 1
    assert result.status == "insufficient_evidence"


def test_exact_passage_is_accepted():
    def handle(request):
        payload = json.loads(request.content)
        assert payload["think"] is False
        assert payload["options"]["num_ctx"] == 4096
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({"relationship": "supports", "passage": "Acme released Atlas today for all developers.", "explanation": "Reports release"})}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            result = await evidence.compare_source(client, STORY.title, TEXT)
            assert result.relationship == "supports"
    asyncio.run(run())


def test_unreadable_pages_are_not_evidence(setup, monkeypatch):
    from fastapi import HTTPException
    async def blocked(url):
        raise HTTPException(422, "Blocked")
    monkeypatch.setattr(evidence, "extract_article", blocked)
    result = asyncio.run(evidence.check_evidence(STORY))
    assert result.status == "insufficient_evidence"
    assert result.sources == []


def test_endpoint_returns_evidence_contract(monkeypatch):
    from main import app
    async def check(story):
        return evidence.EvidenceResponse(claim=story.title, status="insufficient_evidence", checked_at="2026-10-28T12:00:00Z")
    monkeypatch.setattr(evidence, "check_evidence", check)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/evidence", json=STORY.model_dump())
            assert response.status_code == 200
            assert response.json()["status"] == "insufficient_evidence"
            assert response.json()["claim"] == STORY.title
    asyncio.run(run())
