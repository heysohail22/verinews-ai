import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from feeds import AllFeedsFailed, collect_news
from schemas import NewsResponse

app = FastAPI(title="VeriNews")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")], allow_methods=["GET"])


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger(__name__).error("Unexpected collection error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Unable to collect news. Please try again."})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/news", response_model=NewsResponse)
async def news():
    try:
        return await collect_news()
    except AllFeedsFailed:
        raise HTTPException(status_code=502, detail="All news sources are currently unavailable. Please try again later.") from None
