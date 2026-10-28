"""Local development launcher; reuse Ollama or own its temporary server."""
import os
import shutil
import subprocess
import time
from urllib.parse import urlsplit

import httpx


def stop_owned_server(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def ensure_ollama():
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    process = None
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            try:
                response = client.get(f"{base}/api/tags")
                response.raise_for_status()
            except httpx.RequestError:
                parsed = urlsplit(base)
                if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                    raise RuntimeError(f"Cannot reach configured Ollama server: {base}") from None
                executable = shutil.which("ollama")
                if not executable:
                    raise RuntimeError("Ollama is not installed or is missing from PATH.")
                env = {**os.environ, "OLLAMA_HOST": base, "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1"}
                print("Starting local Ollama server…", flush=True)
                process = subprocess.Popen([executable, "serve"], env=env)
                deadline = time.monotonic() + 20
                while True:
                    try:
                        response = client.get(f"{base}/api/tags")
                        response.raise_for_status()
                        break
                    except httpx.RequestError:
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("Ollama did not start. Check the server output above.") from None
                        time.sleep(0.25)
            installed = {model["name"] for model in response.json()["models"]}
            default = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
            required = {default, os.getenv("OLLAMA_RANKING_MODEL", default)}
            missing = [model for model in sorted(required) if model not in installed and f"{model}:latest" not in installed]
            if missing:
                commands = "; ".join(f"ollama pull {model}" for model in missing)
                raise RuntimeError(f"Required model not installed. Run: {commands}")
            print(f"Ollama ready ({', '.join(sorted(required))}). Models load on demand.", flush=True)
        return process
    except BaseException:
        stop_owned_server(process)
        raise


def run_backend():
    import uvicorn
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv(Path(__file__).with_name(".env"))
    process = None
    try:
        process = ensure_ollama()
        uvicorn.run("main:app", host="127.0.0.1", port=8000)
    except (RuntimeError, httpx.HTTPError, ValueError, KeyError) as exc:
        raise SystemExit(f"Backend startup failed: {exc}") from None
    finally:
        stop_owned_server(process)
