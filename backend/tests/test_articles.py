import asyncio
import json
import socket
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import HTTPException

import articles
from main import app
from schemas import ArticleCandidate, ArticleRequest, ExtractedArticle

TEXT = " ".join(f"The Atlas research team reports finding number {i}, with detailed observations from independent laboratory experiments." for i in range(16))
HTML = f'<html><head><title>Atlas research report</title></head><body><nav>Subscribe Home</nav><article><h1>Atlas research report</h1><p>{TEXT}</p></article></body></html>'.encode()


@pytest.fixture(autouse=True)
def clear_cache():
    articles._cache.clear()


def client_mock(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(articles.httpx, "AsyncClient", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    async def safe(url):
        if url.startswith("http://127."):
            raise ValueError("Private")
        return url
    monkeypatch.setattr(articles, "public_url", safe)
    return real


def test_extraction_and_cache(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
    client_mock(monkeypatch, handler)
    first = asyncio.run(articles.extract_article("https://publisher.example/story"))
    second = asyncio.run(articles.extract_article("https://publisher.example/story"))
    assert first == second
    assert first.word_count >= 100
    assert "finding number 15" in first.text
    assert "Subscribe Home" not in first.text
    assert len(calls) == 1


@pytest.mark.parametrize("region", ["US", "IN"])
def test_google_resolution_preserves_edition(monkeypatch, region):
    def handler(request):
        if request.url.path == "/rss/articles/abc":
            assert request.url.params["gl"] == region
            assert request.url.params["hl"] == f"en-{region}"
            return httpx.Response(200, text='<div data-n-a-sg="signature" data-n-a-ts="123"></div>')
        if request.url.path.endswith("batchexecute"):
            envelope = json.loads(parse_qs(request.content.decode())["f.req"][0])
            assert json.loads(envelope[0][0][1])[1][0][7] == f"{region}:en"
            return httpx.Response(200, text=")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", "https://publisher.example/story"]), None]]))
        assert request.url.host == "publisher.example"
        return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
    client_mock(monkeypatch, handler)
    result = asyncio.run(articles.extract_article(f"https://news.google.com/rss/articles/abc?gl={region}"))
    assert result.url == "https://publisher.example/story"
    assert result.word_count >= 100


@pytest.mark.parametrize("status,content,kind", [
    (403, b"blocked", "text/html"),
    (200, b"<article>Only a headline</article>", "text/html"),
    (200, HTML, "application/pdf"),
    (200, b'<script type="application/ld+json">{"isAccessibleForFree":false}</script>' + HTML, "text/html"),
])
def test_unavailable_content(monkeypatch, status, content, kind):
    client_mock(monkeypatch, lambda request: httpx.Response(status, content=content, headers={"content-type": kind}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(articles.extract_article("https://publisher.example/story"))
    assert error.value.status_code == 422
    assert "Full article unavailable" in error.value.detail
    assert not articles._cache


def test_redirect_private_address_blocked(monkeypatch):
    client_mock(monkeypatch, lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/private"}))
    with pytest.raises(HTTPException):
        asyncio.run(articles.extract_article("https://publisher.example/story"))


def test_size_limit(monkeypatch):
    monkeypatch.setattr(articles, "MAX_BYTES", 20)
    client_mock(monkeypatch, lambda request: httpx.Response(200, content=HTML, headers={"content-type": "text/html"}))
    with pytest.raises(HTTPException):
        asyncio.run(articles.extract_article("https://publisher.example/story"))


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
def test_public_address_validation(monkeypatch, ip):
    async def addresses(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 80))]
    async def check():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", addresses)
        with pytest.raises(ValueError):
            await articles.public_url("https://publisher.example/story")
    asyncio.run(check())


def test_extract_endpoint(monkeypatch):
    real = client_mock(monkeypatch, lambda request: httpx.Response(200, content=HTML, headers={"content-type": "text/html"}))
    async def check():
        async with real(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/articles/extract", json={"url": "https://publisher.example/story"})
            assert response.status_code == 200
            assert response.json()["word_count"] >= 100
            invalid = await client.post("/api/articles/extract", json={"url": "file:///etc/passwd"})
            assert invalid.status_code == 422
    asyncio.run(check())


def test_readable_short_article_is_accepted():
    text = " ".join(f"observation{i}" for i in range(90))
    page = f"<html><body><article><h1>Short research report</h1><p>{text}</p></article></body></html>".encode()
    assert 60 <= articles.readable_article(page, "https://publisher.example/short").word_count < 100


def test_obvious_topic_mismatch_rejected():
    unrelated = ExtractedArticle(url="https://publisher.example/sebi", text="India's markets regulator SEBI is working on artificial intelligence oversight for securities trading.", word_count=15, truncated=False)
    with pytest.raises(HTTPException):
        articles.validate_article_match(unrelated, "Trump says he will ban term artificial intelligence")
    related = unrelated.model_copy(update={"text": "Trump said he will ban the term artificial intelligence in documents."})
    articles.validate_article_match(related, "Trump says he will ban term artificial intelligence")


def test_automatic_coverage_fallback_and_attribution(monkeypatch):
    def handler(request):
        if request.url.host == "blocked.example":
            return httpx.Response(403)
        return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
    client_mock(monkeypatch, handler)
    request = ArticleRequest(url="https://blocked.example/story", source="Blocked Publisher", expected_title="Atlas research report", alternatives=[ArticleCandidate(url="https://publisher.example/story", source="Readable Publisher")])
    result = asyncio.run(articles.extract_story(request))
    assert result.url == "https://publisher.example/story"
    assert result.source == "Readable Publisher"


def test_fallback_rejects_unrelated_text_then_tries_next(monkeypatch):
    calls = []
    async def extracted(url):
        calls.append(url)
        text = "Unrelated securities regulation" if "wrong" in url else "Atlas research report describes laboratory observations"
        return ExtractedArticle(url=url, text=text, word_count=100, truncated=False)
    monkeypatch.setattr(articles, "extract_article", extracted)
    request = ArticleRequest(url="https://wrong.example/story", expected_title="Atlas research report", alternatives=[ArticleCandidate(url="https://right.example/story", source="Right")])
    result = asyncio.run(articles.extract_story(request))
    assert result.url == "https://right.example/story"
    assert len(calls) == 2


def test_javascript_challenge_is_not_article_context(monkeypatch):
    challenge = b"<html><head><title>Client Challenge</title></head><body><p>JavaScript is disabled in your browser. Please enable JavaScript to proceed.</p></body></html>"
    client_mock(monkeypatch, lambda request: httpx.Response(200, content=challenge, headers={"content-type": "text/html"}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(articles.extract_article("https://publisher.example/story"))
    assert "JavaScript challenge" in error.value.detail
