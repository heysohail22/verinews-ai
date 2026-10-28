# VeriNews RSS backend

Requires Python 3.12+ and uv. No API keys or database are needed.

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

`GET /api/health` checks service health. `GET /api/news` collects fresh RSS entries,
returning up to 10 deduplicated articles from the last 24 hours, configured sources, UTC completion time,
and source warnings. All upstream failures return 502; an empty valid feed is a success.

Server-controlled feeds in `feeds.py`:

- Google News AI topic search: https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en
- Disabled fallback — TechCrunch AI: https://techcrunch.com/category/artificial-intelligence/feed/
- Disabled fallback — Ars Technica (general technology): https://feeds.arstechnica.com/arstechnica/index
- Disabled fallback — MIT News AI: https://news.mit.edu/rss/topic/artificial-intelligence2

Google News broadens discovery across publishers without an API key. It uses
English/US search settings and Google News article links, which may open a Google
News page before the publisher. This public RSS endpoint has no availability
guarantee. After fetching, the backend keeps articles published within the last
24 hours, removes duplicate normalized URLs, and returns the newest 10. The window
includes the exact 24-hour boundary and excludes future timestamps and unknown
dates. Fewer than 10 qualifying entries means fewer results, including an empty
successful collection. Different URLs covering the same event are not grouped;
relevance, source quality, and significance scoring are not implemented.

Requests use three concurrent slots, an 8-second connect timeout and a 20-second
network operation timeout. Descriptions are plain RSS text, not full articles or
AI summaries. No stories are stored. Links retain meaningful query parameters;
fragments, default ports and hostname case are normalized for deduplication.

CORS permits `http://localhost:3000` by default. Set `FRONTEND_ORIGIN` to the exact
frontend origin if using another host or port (including `127.0.0.1`).

```bash
uv run pytest
```

Tests use deterministic RSS fixtures and mocked HTTP; live feeds can change or fail.

Verification (28 October 2026): 13 fixture tests passed. Live `/api/news` returned
HTTP 200 with 90 articles, all three sources available, and no warnings.

Updated filtering verification: fixture tests cover the 10-article limit, newest-first
ordering, exact 24-hour cutoff, unknown/future dates, duplicate URLs, and no recent results.
