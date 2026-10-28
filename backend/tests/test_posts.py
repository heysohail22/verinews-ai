import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

import posts
from main import app
from schemas import PostRequest

STORY = PostRequest(title="Acme announces Atlas", description="Acme says Atlas is a developer preview.", source="Example", url="https://example.com/story")


def mock_ollama(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(posts.httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    return real_client


def test_generation_and_prompt(monkeypatch):
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["model"] == "test-local-model"
        assert "untrusted" in payload["messages"][0]["content"]
        assert json.loads(payload["messages"][1]["content"])["title"] == STORY.title
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({"body": "Acme says Atlas is in developer preview."})}})
    monkeypatch.setenv("OLLAMA_MODEL", "test-local-model")
    mock_ollama(monkeypatch, handler)
    result = asyncio.run(posts.generate_post(STORY))
    assert result.draft == "Acme says Atlas is in developer preview.\n\nSource: Example\nhttps://example.com/story"


@pytest.mark.parametrize("status,expected", [(404, 503), (500, 502)])
def test_ollama_http_failures(monkeypatch, status, expected):
    mock_ollama(monkeypatch, lambda request: httpx.Response(status, json={"error": "internal details"}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(posts.generate_post(STORY))
    assert error.value.status_code == expected
    assert "internal details" not in error.value.detail


@pytest.mark.parametrize("error_type,expected", [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)])
def test_ollama_network_failures(monkeypatch, error_type, expected):
    def handler(request):
        raise error_type("private diagnostics", request=request)
    mock_ollama(monkeypatch, handler)
    with pytest.raises(HTTPException) as error:
        asyncio.run(posts.generate_post(STORY))
    assert error.value.status_code == expected


@pytest.mark.parametrize("message", ["not JSON", '{"body":""}', '{"body":null}', '{"body":"<think>analysis</think>draft"}', '{"body":"Visit https://made-up.example"}'])
def test_invalid_model_output(monkeypatch, message):
    mock_ollama(monkeypatch, lambda request: httpx.Response(200, json={"done": True, "message": {"content": message}}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(posts.generate_post(STORY))
    assert error.value.status_code == 502


def test_endpoint_and_cors(monkeypatch):
    real_client = mock_ollama(monkeypatch, lambda request: httpx.Response(200, json={"done": True, "message": {"content": '{"body":"Acme announced Atlas."}'}}))
    async def check():
        async with real_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.options('/api/posts/x', headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
            result = await client.post('/api/posts/x', json=STORY.model_dump())
            assert result.status_code == 200
            assert result.json()["draft"].endswith(STORY.url)
            invalid = await client.post('/api/posts/x', json={**STORY.model_dump(), "url": "javascript:alert(1)"})
            assert invalid.status_code == 422
    asyncio.run(check())


def test_duplicate_generation_rejected():
    async def check():
        async with posts._generation_lock:
            with pytest.raises(HTTPException) as error:
                await posts.generate_post(STORY)
            assert error.value.status_code == 429
    asyncio.run(check())
