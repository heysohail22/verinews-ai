# VeriNews RSS backend

Requires Python 3.12+ and uv. No API keys or database are needed.

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

`GET /api/health` checks service health. `GET /api/news` returns up to 10
story groups from the last 24 hours, publisher sources, UTC completion time,
and feed warnings. All upstream failures return 502; an empty valid feed is a success.

## Coverage collection and ranking

`feeds.py` generates five Google News RSS searches per region (10 feeds total): artificial intelligence,
AI models/LLMs, AI agents, AI regulation, and OpenAI/Anthropic/DeepMind. Each
query includes `when:1d`; the backend additionally enforces the 24-hour window.
Feeds cover both US English (`en-US`, `US`, `US:en`) and India English
(`en-IN`, `IN`, `IN:en`), with no API key and at most three concurrent requests.
Results are combined before URL deduplication and story grouping, so a publisher
appearing in both regions still counts once per story.

1. Parse the actual publisher from each RSS entry's `source` metadata. Normalize
   its domain (or name when no domain exists) so repeated feeds don't count twice.
2. Exclude unknown/future publication dates and entries older than 24 hours.
3. Deduplicate normalized article URLs across all topic feeds.
4. Group similar titles using normalized word sets and a conservative 0.65 Jaccard
   overlap threshold. Publisher suffixes and common words are removed; numeric
   model identifiers and selected outcome words must agree. Compare to the newest
   representative to avoid transitive grouping chains.
5. Rank by distinct identified publisher count, then newest publication time,
   with deterministic URL ties. Return at most 10 groups; fewer are allowed.

Each `articles` item remains a representative article and adds `publisher_count`
and `coverage` (one latest article link per publisher). `sources` now lists the
publishers in the returned groups; it no longer lists configured query feeds.
Warnings retain the query feed ID and include its display name in the message.

This measures **most covered stories within the collected feeds**, not global
trending activity. Missing publisher metadata does not inflate publisher counts.
Title grouping may miss differently worded reports or merge similar events.
Distinct publishers may reuse syndicated reporting: counts do not establish
independent confirmation, credibility, or truth. No AI, Ollama, API keys, stored
history, or momentum scoring is used. Google RSS links may open Google News
before the publisher, and the public RSS endpoint has no availability guarantee.

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

Verification (28 October 2026): 22 fixture tests passed, covering ranking,
publisher counting, overlapping feeds, grouping boundaries, freshness, result
limits, unsafe links, and failures. Live collection across all five feeds returned
10 story groups with no source warnings. Frontend lint passed.

TypeScript checking and the production Next.js build also passed.

## Local X post drafts

Install Ollama and download the model once:

```bash
ollama pull qwen3:4b-instruct
ollama serve  # only if the Ollama service is not already running
```

The backend defaults to `OLLAMA_BASE_URL=http://localhost:11434` and
`OLLAMA_MODEL=qwen3:4b-instruct`. Change these with environment variables or copy
`.env.example` to `.env` and start with `uv run uvicorn main:app --reload --env-file .env`.
No Python Ollama SDK or API key is required; httpx calls the local `/api/chat` API.

`POST /api/posts/x` accepts `title`, `description`, `source`, and an HTTP(S) `url`.
It returns `{ "draft": "...", "model": "..." }`. The model receives bounded RSS
text as untrusted reference data, with thinking disabled and JSON output. The
backend appends attribution and the supplied source URL itself. Only one draft
is generated per backend process at a time (429 if busy); the Ollama request has
an explicit timeout. Missing model/server, timeouts, and unusable output return
helpful errors. Generation does not fetch full articles or verify claims.

The frontend uses `twitter-text` weighted counting and disables Copy for invalid
or over-280-character drafts. A model may exceed the requested length; edit the
result before copying. Model instructions reduce but cannot eliminate invented
claims. Review the draft and source evidence before manually posting to X.
Nothing is published automatically, and drafts are not stored persistently.
