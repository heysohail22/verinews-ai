import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from feeds import NewsSearchFailed, collect_news
from schemas import NewsResponse, PostRequest, PostResponse
from posts import generate_post
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


@app.post("/api/posts/x", response_model=PostResponse)
async def x_post(story: PostRequest):
    return await generate_post(story)


@app.post("/api/posts/linkedin", response_model=PostResponse)
async def linkedin_post(story: PostRequest):
    return await generate_post(story, platform="linkedin")


@app.post("/api/articles/extract", response_model=ExtractedArticle)
async def article_text(request: ArticleRequest):
    return await extract_story(request)
