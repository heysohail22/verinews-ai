import logging
import asyncio
import json
from contextlib import suppress
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from feeds import NewsSearchFailed, collect_news
from schemas import NewsResponse, PostRequest, PostResponse, EvidenceResponse
from posts import generate_post
from ai_ranking import AIRankingError
from articles import extract_story
from schemas import ArticleRequest, ExtractedArticle

app = FastAPI(title="VeriNews")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger(__name__).error("Unexpected collection error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "The service could not complete the request. Please try again."})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/news", response_model=NewsResponse)
async def news():
    try:
        return await collect_news()
    except NewsSearchFailed:
        raise HTTPException(status_code=502, detail="Bing/Yahoo news search is currently unavailable. Search providers may be refusing automated access. Please try again later. RSS is disabled.") from None

    except AIRankingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@app.post("/api/posts/x", response_model=PostResponse)
async def x_post(story: PostRequest):
    return await generate_post(story)


@app.post("/api/posts/linkedin", response_model=PostResponse)
async def linkedin_post(story: PostRequest):
    return await generate_post(story, platform="linkedin")


@app.post("/api/articles/extract", response_model=ExtractedArticle)
async def article_text(request: ArticleRequest):
    return await extract_story(request)


@app.get("/api/news/stream")
async def stream_news():
    async def events():
        queue = asyncio.Queue()
        async def progress(event):
            await queue.put({"type": "progress", **event})
        async def run():
            try:
                result = await collect_news(progress=progress)
                await queue.put({"type": "result", "data": result.model_dump()})
            except NewsSearchFailed:
                await queue.put({"type": "error", "message": "Bing/Yahoo news search is unavailable. Please try again later."})
            except AIRankingError as exc:
                await queue.put({"type": "error", "message": str(exc)})
            except Exception:
                logging.getLogger(__name__).exception("Collection stream failed")
                await queue.put({"type": "error", "message": "News collection failed. Please try again."})
        task = asyncio.create_task(run())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    event = {"type": "heartbeat"}
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] in {"result", "error"}:
                    break
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/evidence", response_model=EvidenceResponse)
async def evidence_check(story: PostRequest):
    from evidence import check_evidence
    return await check_evidence(story)


if __name__ == "__main__":
    from startup import run_backend
    run_backend()
