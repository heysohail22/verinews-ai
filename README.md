# VeriNews AI

A local AI news workspace that collects recent AI reporting, checks headline
claims against retrieved evidence, and prepares editable posts for X and LinkedIn.
It uses Ollama with `qwen3:0.6b` and requires no paid API keys.

## Features

- Search Bing/Yahoo News through DDGS for US and India coverage from the last 24 hours.
- Review every unique recent headline with local AI, in batches of five, before grouping related stories and selecting up to 10 readable articles.
- Display article excerpts, publishers, publication times and clickable source URLs.
- Check evidence on demand, with supporting or conflicting passages and source links.
- Open a dedicated writing page to generate, edit and copy X or LinkedIn drafts.
- Show collection and AI-review progress while retaining the previous collection if a request fails.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- Node.js 20.9+ and pnpm (the frontend declares its version in `package.json`).
- [Ollama](https://ollama.com/) installed and available on your PATH.
- Internet access for search, article retrieval and the initial model download.

The model runs locally. Search queries and article requests still go to external
websites. Local inference needs RAM; the small default model, bounded context and
one AI request at a time reduce memory use but cannot guarantee against exhaustion.

## Setup and run

Clone the repository:

```bash
git clone https://github.com/heysohail22/verinews-ai.git
cd verinews-ai
```

Download the model once:

```bash
ollama pull qwen3:0.6b
```

Start the backend in one terminal:

```bash
cd backend
uv sync
cp .env.example .env
uv run main.py
```

The launcher checks the configured models, starts a local Ollama server if needed,
and starts FastAPI at http://localhost:8000. Models load on demand. Ctrl+C stops
FastAPI and an Ollama server started by the launcher; an existing Ollama service
is left running. Restart the launcher after backend code changes.

Start the frontend in another terminal, from the repository root:

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

Open http://localhost:3000. Backend API documentation is at
http://localhost:8000/docs.

### Configuration

Backend settings can be supplied through environment variables or `backend/.env`.
Existing environment variables take precedence.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen3:0.6b` | Default local model |
| `OLLAMA_RANKING_MODEL` | Value of `OLLAMA_MODEL` | Optional headline-review model |
| `OLLAMA_EVIDENCE_MODEL` | Value of `OLLAMA_MODEL` | Optional evidence-comparison model |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | Allowed frontend origin |

`frontend/.env.local` can set `NEXT_PUBLIC_API_BASE_URL`, which defaults to
`http://localhost:8000`. Restart Next.js after changing it; production builds
embed this public setting.

## Using the application

1. Click **Collect latest news**. Search, AI review and article-reading progress appear as collection runs.
2. Read a story card and follow its source URL to inspect the original reporting.
3. Click **Check evidence** to retrieve other sources and compare the headline claim. Expand the result to review passages, links and the check time.
4. Click **Create post** to open the writing studio. Choose X or LinkedIn, generate a draft, edit it and copy it.

X uses weighted 280-character counting; LinkedIn allows up to 3,000 characters.
The optional source link is included when copying. Drafts are never automatically
published. Review them before sharing.

The collection and selected stories are kept in this browser tab's sessionStorage,
with an in-memory fallback. There is no article database. Drafts are held in the
editor's state and can be lost when leaving or refreshing the writing page.

## How it works

### Discovery and selection

DDGS requests up to three pages of 20 news candidates for each region, using
`backend="bing,yahoo"`. This is a bounded search pool, not all news on the internet.
There is no RSS fallback and DuckDuckGo is not queried.

The backend validates URLs, applies the 24-hour publication window and removes
repeated URLs. Ollama reviews all eligible headlines in batches of five; ambiguous
headlines may be reviewed again with search descriptions. Invalid structured
responses trigger smaller retries. Topic selection follows the model's `keep`
decision without an extra keyword filter or relevance-score cutoff.

Related stories are grouped by conservative title similarity, then ordered by AI
importance and relevance. Publisher coverage and freshness break ties. HTTPX and
Trafilatura extract article text before stories are shown. Blocked, mismatching
or insufficiently readable stories are skipped; fewer than 10 may qualify.

### Evidence checks

Checks search for the headline claim, try up to six candidate pages, and compare
up to three readable sources. The original domain and substantially copied texts
are excluded. Every cited passage must exist in the supplied source text after
whitespace normalization. Search snippets alone do not count as evidence.

- **Supported by retrieved evidence:** at least two retrieved sources support the claim.
- **Conflicting evidence:** a retrieved source contradicts the claim.
- **Insufficient evidence:** support is inadequate, sources are unavailable, comparisons fail validation, or the time limit is reached.

Different domains do not establish editorial independence, and AI can misinterpret
real passages. These labels assist human review; they are not guaranteed fact
verification and do not check every claim within an article.

### Article reading and drafting

The extractor requires at least 60 readable words, validates public HTTP(S)
addresses, bounds redirects and downloads, and keeps a short-lived in-memory
cache. Public excerpts may be used when sufficient text is returned, with an
incomplete-content label. Paywalls and browser challenges are not bypassed;
Playwright extraction is not implemented.

Drafts use retrieved article text, limited to 6,000 characters for model input,
with truncation disclosed to the model. Thinking is disabled, the context is
bounded, and models unload after inference. A shared lock prevents simultaneous
headline, evidence and drafting model requests within one backend process.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend health; does not check upstream services |
| GET | `/api/news` | Collect reviewed, readable stories |
| GET | `/api/news/stream` | Collection with NDJSON progress events |
| POST | `/api/articles/extract` | Extract article text with collected coverage fallbacks |
| POST | `/api/evidence` | Check a headline claim against retrieved sources |
| POST | `/api/posts/x` | Generate an X draft |
| POST | `/api/posts/linkedin` | Generate a LinkedIn draft |

See `/docs` for request and response schemas.

## Development checks

From `backend`:

```bash
uv run pytest
```

From `frontend`:

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

Backend tests mock external search and model services. Passing them does not
establish live provider availability or model accuracy. For a submission demo,
test collection, an evidence check and both draft formats with local Ollama.

To serve a production frontend build, run `pnpm start` after `pnpm build`.
For backend auto-reload, run `uv run uvicorn main:app --reload --env-file .env`
from `backend`, with Ollama already running.

## Project structure

```text
backend/                 FastAPI, search, extraction, evidence checks and Ollama
  tests/                 Backend regression tests
frontend/                Next.js, React, Tailwind and shadcn/ui
  app/create/[id]/        Dedicated writing route
  components/            Newsroom controls and post editor
harness/                 Project implementation notes
README.md                Setup, usage and project documentation
```

## Limitations

Search providers may refuse automated access or return different results from
browser searches. Article extraction can fail on subscriptions, JavaScript-only
pages or publisher blocks. Collection may take several minutes. Title grouping
and the small local model can make mistakes; neither rankings nor publisher
counts establish truth. Always inspect evidence and review generated posts.
