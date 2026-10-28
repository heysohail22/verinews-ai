import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

import posts
from main import app
from schemas import PostRequest, ExtractedArticle

STORY = PostRequest(title="Acme announces Atlas", description="Acme says Atlas is a developer preview.", source="Example", url="https://example.com/story")


@pytest.fixture(autouse=True)
def article_context(monkeypatch):
    async def extracted(url):
        return ExtractedArticle(url=url, text="Acme says Atlas is a developer preview. " * 20, word_count=160, truncated=False)
    monkeypatch.setattr(posts, "extract_article", extracted)


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
    assert result.draft == "Acme says Atlas is in developer preview.\n\nhttps://example.com/story"


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


def test_linkedin_style_and_publisher_cleanup(monkeypatch):
    story = PostRequest(title="Atlas released - Example (News)", description="Atlas released - Example (News)", source="Example (News)", url=STORY.url)
    def handler(request):
        payload = json.loads(request.content)
        prompt = payload["messages"][0]["content"]
        assert "LinkedIn" in prompt
        assert "80–140 words" in prompt
        assert "160 characters" not in prompt
        assert json.loads(payload["messages"][1]["content"])["title"] == "Atlas released"
        assert "article_text" in json.loads(payload["messages"][1]["content"])
        assert "description" not in json.loads(payload["messages"][1]["content"])
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({"body": "Atlas is released - Example (News)\n\nIt is a developer preview."})}})
    mock_ollama(monkeypatch, handler)
    result = asyncio.run(posts.generate_post(story, platform="linkedin"))
    assert result.body == "Atlas is released\n\nIt is a developer preview."
    assert result.source_url == STORY.url
    assert "Example (News)" not in result.draft


def test_linkedin_endpoint(monkeypatch):
    real_client = mock_ollama(monkeypatch, lambda request: httpx.Response(200, json={"done": True, "message": {"content": '{"body":"Atlas is available.\\n\\nA developer preview is open."}'}}))
    async def check():
        async with real_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            result = await client.post('/api/posts/linkedin', json=STORY.model_dump())
            assert result.status_code == 200
            assert result.json()["body"]
            assert result.json()["source_url"] == STORY.url
    asyncio.run(check())


def test_no_post_without_full_article(monkeypatch):
    async def unavailable(url):
        raise HTTPException(status_code=422, detail="Full article unavailable")
    monkeypatch.setattr(posts, "extract_article", unavailable)
    def never_generate(request):
        pytest.fail("Ollama must not run without readable article text")
    mock_ollama(monkeypatch, never_generate)
    with pytest.raises(HTTPException) as error:
        asyncio.run(posts.generate_post(STORY))
    assert error.value.status_code == 422


def test_prompt_uses_full_article_and_publisher_url(monkeypatch):
    async def extracted(url):
        return ExtractedArticle(url="https://publisher.example/full", text="Acme says the Atlas remark was a joke, not an announced ban.", word_count=11, truncated=False)
    monkeypatch.setattr(posts, "extract_article", extracted)
    def handler(request):
        payload = json.loads(request.content)
        supplied = json.loads(payload["messages"][1]["content"])
        assert "joke" in supplied["article_text"]
        assert "description" not in supplied
        assert "Do not claim verification" in payload["messages"][0]["content"]
        return httpx.Response(200, json={"done": True, "message": {"content": '{"body":"The remark was a joke."}'}})
    mock_ollama(monkeypatch, handler)
    result = asyncio.run(posts.generate_post(STORY))
    assert result.source_url == "https://publisher.example/full"


def test_altered_numeric_range_rejected(monkeypatch):
    async def extracted(url):
        return ExtractedArticle(url=url, text="Acme says Atlas workload could fall by 30–50 percent, the report says.", word_count=11, truncated=False)
    monkeypatch.setattr(posts, "extract_article", extracted)
    mock_ollama(monkeypatch, lambda request: httpx.Response(200, json={"done": True, "message": {"content": '{"body":"Workload could fall by 30-5 percent."}'}}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(posts.generate_post(STORY))
    assert error.value.status_code == 502
