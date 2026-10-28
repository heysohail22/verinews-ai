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
