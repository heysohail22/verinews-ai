import httpx
import pytest

import startup


def test_existing_server_is_reused_without_starting_process(monkeypatch):
    real = httpx.Client
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:0.6b")
    monkeypatch.setenv("OLLAMA_RANKING_MODEL", "qwen3:0.6b")
    monkeypatch.setattr(startup.httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": [{"name": "qwen3:0.6b"}]})), **kwargs))
    monkeypatch.setattr(startup.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("must reuse existing server"))
    assert startup.ensure_ollama() is None


def test_missing_model_gives_install_command(monkeypatch):
    real = httpx.Client
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:0.6b")
    monkeypatch.setenv("OLLAMA_RANKING_MODEL", "qwen3:0.6b")
    monkeypatch.setattr(startup.httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"models": []})), **kwargs))
    with pytest.raises(RuntimeError, match="ollama pull qwen3:0.6b"):
        startup.ensure_ollama()
