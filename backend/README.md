# VeriNews backend

Requires Python 3.12+, uv, and local Ollama for post generation. No API keys.

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## News search without RSS

`GET /api/news` searches Bing/Yahoo News using DDGS directly (no LangChain).
The query is `latest ai news`, regions are `in-en` and `us-en`, Safe Search is
moderate, the search time filter is the past day, and each region requests up to three pages of 20 candidates (up to 120 across both regions). Search runs in worker threads with explicit timeouts and bounded
concurrency. The backend additionally enforces a UTC 24-hour publication window,
rejects unsafe links, cleans descriptions, and deduplicates normalized URLs.

Related headlines are grouped using conservative word similarity. Groups are
ranked by distinct identified publisher count, then freshness. The full retrieved pool
is considered for article-reading checks; at most 10 readable groups are returned. This measures coverage in collected results, not global trends,
independent confirmation, or truth. Different wording can prevent grouping and
similar events can be grouped incorrectly.

There is **no RSS collection or fallback** and DuckDuckGo is not queried.
Every collection uses `backend="bing,yahoo"`. Search failure returns HTTP 502. A successful search with no qualifying articles
returns HTTP 200 and an empty list. Partial regional failures keep successful
results with warnings. Search availability and results are not guaranteed;
Browser search pages may show different results or ordering.

`GET /api/health` returns `{"status":"ok"}` without checking upstream services.
`GET /api/news` returns `articles`, publisher `sources`, `collected_at`, and
`warnings`. Each story includes a representative article, `publisher_count`, and
one `coverage` link per publisher for automatic article-reading fallback.

## Reading articles

`POST /api/articles/extract` accepts `url`, optional `expected_title`, `source`,
and up to nine `alternatives` (URL/source objects). It automatically tries at most
four distinct collected links within 60 seconds. Google-wrapped links from older
results can still be resolved, but no RSS discovery requests are made.

Trafilatura extracts publisher text. Downloads allow public HTTP(S) addresses,
standard ports, bounded redirects, HTML content, and a 3 MB response limit.
At least 60 words are required; JavaScript challenges, unreadable pages, and
obvious headline mismatches are rejected. Subscription metadata is checked only
for the current article. If sufficient text is publicly returned, it can be used
as a labelled potentially incomplete excerpt; subscriber-only content is not
fetched or unlocked. The
response contains `url`, `source`, `text`, `word_count`, and `truncated`.

Text is capped at 24,000 characters and marked as an excerpt when shortened. A
bounded in-memory cache reuses it for 10 minutes; no article files or database
are created. Reading does not guarantee a complete article or fact-check it.
Browser-based loading with Playwright is not yet implemented.

## Local X and LinkedIn drafts

```bash
ollama pull qwen3:0.6b
ollama serve  # only if the Ollama service is not already running
```

Defaults: `OLLAMA_BASE_URL=http://localhost:11434`,
`OLLAMA_MODEL=qwen3:0.6b`, `FRONTEND_ORIGIN=http://localhost:3000`.
Set environment variables, or copy `.env.example` to `.env` and run:

```bash
uv run uvicorn main:app --reload --env-file .env
```

`POST /api/posts/x` and `/api/posts/linkedin` accept `title`, `description`,
`source`, and `url`. They require readable, matching publisher text before calling
Ollama. The RSS/search description is not used as article evidence. Thinking is
disabled and JSON output is requested. No automatic publishing is implemented.
Responses contain `draft`, editable `body`, `source_url`, and `model`.

X requests a concise body; LinkedIn requests 2–3 paragraphs and around 80–140
words when supported by the source. Trailing publisher suffixes and separate
source labels are omitted. The frontend supports editing, optional source-link
inclusion, X weighted 280-character counting, a LinkedIn 3,000-character limit,
and Copy. Model output can still contain errors: review drafts before posting.

One generation runs per backend process at a time (429 when busy). Missing
Ollama/model, timeout, invalid output and unavailable article errors are handled.
Extraction and draft generation do not bypass publisher challenges or paywalls.

## Verification

```bash
uv run pytest
```

Fixture tests mock external services and cover search normalization, filters,
regional failures, no-RSS behavior, grouping, extraction and generation. Live
DDGS checks returned news initially and later no results, so availability remains
an upstream dependency. See the harness document for implementation observations.

### Bing/Yahoo is the default

The user requested always using Bing/Yahoo. DuckDuckGo requests and the
provider-switch warning have been removed. Partial regional failures can still
produce genuine availability warnings. Live collection returned 10 story groups
with no warnings; all 56 backend tests passed. RSS remains disabled.

### Public excerpts on subscription-marked pages

The supplied Verge page marks its NewsArticle as `isAccessibleForFree: false`,
but publicly returns a readable short update. The old global regex rejected the
page before reading it. Detection now parses current-article JSON-LD rather than
matching unrelated embedded records. Sufficient publicly returned text is loaded
with `truncated=true` and an `access_note` that it may be incomplete. That note
is displayed in the studio and passed to Ollama. Insufficient public text still
fails; no hidden subscriber content is accessed.

Verification: the supplied Verge URL loaded 100 words as a labelled excerpt.
All 58 backend tests, frontend lint, TypeScript and production build passed.

## Readable-content collection

Collection now reads article text before showing stories. It checks candidates in
ranking order across the retrieved pool, three at a time, with 15 seconds per story and a 60-second shared
reading budget after search. Unreadable, blocked, too-short, mismatching or timed-out
stories are omitted. Lower-ranked groups can backfill the list up to 10; fewer
are returned when fewer qualify. If no articles qualify, collection succeeds with
an empty list, while upstream search failures remain errors.

Returned articles include `content`, `content_word_count`, `content_is_excerpt`,
and `content_note`. Their descriptions are plain excerpts of the extracted text,
not AI summaries or search snippets. When alternate publisher coverage is used,
its URL, publisher and available date are retained. Public excerpts remain labelled
as potentially incomplete. Selected text is kept warm in the bounded memory cache
and preloaded in the writing panel, so choosing a format does not re-download it.
Server-side post generation still checks/reuses its cached publisher context.

Verification: 62 tests passed, frontend lint, TypeScript and production build
passed. A live collection returned 9 stories, all with article text (275–1,386
words), including a labelled Verge excerpt, and no collection warnings. Browser
interaction checks remain unavailable. RSS and DuckDuckGo remain disabled.

## Larger pool before the final ten

Search now requests three pages per region and stops early when a page adds no
new URLs or there are no further results. Previously fetched pages survive a
later-page failure. The complete retrieved candidate pool is used for freshness
filtering, deduplication and story grouping, without the former 30-group cutoff.
Readability checking can continue past candidate 30 to fill the top ten, subject
to the shared time budget. This requests up to 120 results, not every article on
the internet, and fewer may be available. The final list remains at most ten.

`candidates_found` and `stories_checked` are included in the response and shown
alongside the kept count. Search has a 30-second regional budget, reading has a
60-second budget, and the client waits up to 105 seconds. No article database or
persistent storage was added. All 64 tests, lint, TypeScript and production build
passed, including pagination and backfill beyond the first 30 candidates.

### Local AI headline review

The default model is `qwen3:0.6b` for headline review and post drafts.
`OLLAMA_RANKING_MODEL` can override the headline model separately. Every unique
recent candidate is reviewed in sequential batches of five before grouping and
selecting up to ten readable stories. Ambiguous headlines may be reviewed again
with their search descriptions. Structured output must account for every input ID.
The streaming news endpoint reports collection, review counts and article reading
to the animated frontend status display. AI relevance scores are not fact checks.
Ollama uses a 4096-token context and unloads the model after each request to reduce
idle memory use. Draft input is limited to 6000 characters and marked as truncated
when necessary. These limits reduce memory use but do not guarantee against OOM.

Topic selection follows the AI `keep` decision directly; there is no additional
keyword filter or relevance-score cutoff. Scores determine ordering. The 24-hour
window, URL validation, duplicate grouping and readable-content checks still apply.

### Start backend and Ollama together

From `backend`, run `uv run main.py`. This loads `backend/.env`, checks the
configured Ollama server, starts `ollama serve` if the local server is unavailable,
and verifies the configured models are installed before starting FastAPI at
`http://127.0.0.1:8000`. Missing models produce an `ollama pull` instruction.
Models load on the first AI request rather than occupying RAM at startup.
Ctrl+C stops FastAPI and any Ollama server this launcher started. An existing
Ollama service is reused and left running. This launcher does not enable reload;
restart it after code changes.
