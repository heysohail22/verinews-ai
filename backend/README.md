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
It returns `draft`, the editable `body`, `source_url`, and `model`. The model receives bounded extracted publisher
article text as untrusted reference data, with thinking disabled and JSON output. The
backend appends attribution and the supplied source URL itself. Only one draft
is generated per backend process at a time (429 if busy); the Ollama request has
an explicit timeout. Missing model/server, timeouts, and unusable output return
helpful errors. Generation requires readable publisher article text and does not verify claims.

The frontend uses `twitter-text` weighted counting and disables Copy for invalid
or over-280-character drafts. A model may exceed the requested length; edit the
result before copying. Model instructions reduce but cannot eliminate invented
claims. Review the draft and source evidence before manually posting.
Nothing is published automatically, and drafts are not stored persistently.

### LinkedIn drafts and composer

`POST /api/posts/linkedin` accepts the same story fields as the X endpoint. It
requests 2–3 paragraphs (around 80–140 words when the extracted article text supports
that length), without inventing context to fill space. Paragraph breaks are
preserved. Both formats remove trailing ` - Publisher` suffixes from inputs and
output and omit the separate publisher/source label. Meaningful attribution in
the prose remains allowed. The frontend stores each format separately, lets the
user include or omit the source URL when copying, and enforces a 3,000-character
LinkedIn limit or X weighted 280-character limit. Publisher coverage is no longer
shown on cards; backend grouping and ranking remain unchanged.

## Full article context before generation

`POST /api/articles/extract` accepts `{ "url": "https://..." }` and returns the
resolved publisher `url`, readable `text`, `word_count`, and `truncated` flag.
Opening Create post loads this context; generation is disabled until it succeeds.
Both post endpoints independently require extraction, so bypassing the frontend
cannot silently fall back to a headline/RSS-only draft. RSS descriptions remain
on dashboard cards but are not sent as generation evidence.

Google News RSS links are resolved with a signature and its undocumented
`batchexecute` RPC before fetching the publisher. That mechanism may change or be
rate-limited. HTTP redirects are bounded and each destination is checked for
public addresses. Downloads allow only HTTP(S), standard ports and HTML, cap
responses at 3 MB, and use a 45-second overall timeout with explicit per-request
timeouts. Trafilatura removes navigation/comments; at least 60 readable words
are required. Recognized paywalls and unreadable/blocked pages fail with a useful
422 response; there is no paywall bypass or RSS fallback. Extraction heuristics
cannot guarantee that every page's complete article is available.

Extracted text is capped at 24,000 characters (marked as an excerpt when capped)
and reused for up to 10 minutes in a bounded, 20-entry in-memory cache. Nothing is
written to article files or a database. The prompt prohibits invented statements
about verification or missing official confirmation. Full article context improves
grounding but does not establish truth or eliminate model errors.

Verification: 52 fixture tests passed, including Google URL decoding, content
extraction, caching, redirects, non-public destinations, short/blocked/paywalled
pages, and generation refusal without full context. Live Google News resolution
and publisher extraction returned 333 words; an unavailable story was rejected.
Frontend lint, TypeScript and production build passed. Browser checks unavailable.

The live full-article-to-Ollama path completed. Its draft contained an altered
numeric range, so a regression-tested guard now rejects output ranges absent
from the source text. This is a narrow check, not comprehensive fact verification;
model drafts still require review.

### Short articles and publisher-link fallback

Readable articles between 60 and 99 words are now accepted. The supplied Gulf
Daily News article extracted successfully at 97 words; the former 100-word
minimum rejected it. Errors now distinguish insufficient text, HTTP failures,
timeouts and resolution failures. The extraction request may include
`expected_title`; a word-overlap check rejects obvious topic mismatches, including
on cache hits and before generation. This is only a conservative mismatch check,
not semantic matching or fact verification.

The writing panel now tries collected publisher alternatives automatically.
Generation uses the matching publisher URL and attribution from the loaded context.

Verification: 54 backend tests, frontend lint, TypeScript and production build
passed. Live extraction of the supplied GDN URL returned 97 words and passed the
headline check. The supplied Google URL resolved to a different story during the
diagnostic run, so use the direct URL fallback for this story.

## Automatic publisher fallback

Google News is retained for discovery. Resolving a Google RSS link is expected;
it is not itself an extraction error. The supplied India-edition example resolved
to Newstimes, whose HTTP response was a JavaScript Client Challenge page, not the
article. That response is now classified as a challenge rather than merely short
text. No challenge or paywall bypass was added.

The extraction request accepts up to nine `alternatives` (URL and publisher name).
The reader tries at most four distinct collected URLs in a shared 60-second
budget, skipping duplicate Google article IDs across locale query variations and
rejecting mismatching article text. Google resolution preserves US/India edition
settings. Successful text is also cached under the resolved publisher URL, so
post generation can reuse it without repeating Google resolution. The response
includes the selected `source`, and the composer uses that publisher and URL.
The manual URL-entry form is removed. If all candidates fail, no draft is created.

Verification: 58 backend tests passed, covering automatic fallback, publisher
attribution, locale retention, and challenge-page rejection. Frontend lint,
TypeScript and production build passed. Live testing found that all four sources
for one current story were unavailable; the reader correctly refused generation.
This does not guarantee that every story will have an accessible source.
