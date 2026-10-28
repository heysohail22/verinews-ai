# Version 1: RSS News Dashboard

Status: Implemented; backend tests and live API verified. Browser verification remains unavailable in this session.
Created: 28 October 2026.

## Purpose

Build the first working version of VeriNews: a local dashboard that collects AI and technology news from configured RSS feeds and displays the results. A user clicks one button, sees real news entries, and follows links to the original reporting.

This document records the scope agreed in the project conversation. It is the implementation specification for this phase. Update it when agreed requirements change; do not describe planned behavior as completed work.

## Repository baseline

- `frontend/` contains an existing Next.js App Router, React, TypeScript, and Tailwind scaffold. Its home page is still the starter page.
- `backend/` contains a Python project requiring Python 3.12 or newer. Its `main.py` is a placeholder and its dependency list is empty.
- Preserve the existing package managers and project structure. Inspect the installed tooling before selecting exact run commands or dependency versions.

## Scope

Implement a Next.js news dashboard backed by a Python FastAPI service. The backend downloads configured RSS feeds with `httpx`, parses their content with `feedparser`, normalizes entries, and returns JSON. The frontend keeps results in React memory.

No database, file-based article storage, or browser persistence is required. Reloading the page clears collected results. A fresh collection replaces the previous result set rather than appending duplicates.

### Explicit non-goals

- Full article scraping or `trafilatura` integration.
- LLM integration, Ollama, LangChain, or LangGraph.
- Claim extraction, cross-validation, or claims of factual verification.
- Social media post generation or publishing.
- Email delivery, authentication, scheduling, or deployment.
- Tavily, paid services, or API-key requirements.
- User-supplied feed URLs or a source-management interface.

The displayed description is RSS-provided text, not a generated summary or guaranteed full article.

## User experience

### Dashboard

Replace the starter page with a responsive dashboard branded “VeriNews” and the subtitle “Latest AI & Technology News.” Use a light background, white cards, a restrained accent color, readable typography, and visible focus states.

Include:

1. A primary **Collect latest news** button.
2. A source dropdown with an **All sources** option.
3. A text search field that filters titles and descriptions locally.
4. A visible article count reflecting the current filters.
5. The last successful collection time, formatted in the user's browser timezone.
6. Article cards with title, source, publication date when available, RSS description, and a **Read original** link.

Use a single-column layout on narrow screens and a comfortable card layout on wider screens. External links open safely in a new tab. Do not rely on article images, because feeds may not supply them.

### Interaction states

- **Initial:** Explain that the user can collect news to get started. Do not fetch automatically on page load.
- **Loading:** Disable the collection button, change its label to “Collecting…”, and announce loading accessibly. Prevent duplicate requests.
- **Success:** Show the returned articles, source options, and collection time.
- **Empty collection:** Explain that the feeds returned no usable articles and allow retrying.
- **No filter matches:** Explain that the active filters have no matches and offer to clear them.
- **Partial failure:** Show successful results and a non-blocking warning naming unavailable sources.
- **Complete failure:** Show a useful error with a retry action. If earlier results exist, retain them and keep their original collection timestamp so they are not presented as freshly collected.

Source and search filters work together. Reset a selected source to “All sources” if it is no longer present in a new response.

## Backend behavior

Keep a small server-controlled source list, initially around three AI-focused or technology RSS feeds. Confirm the actual feed URLs work during implementation and record the selected sources in the backend README. Prefer AI-specific feeds where available; this phase does not promise automatic AI topic classification.

For each collection:

1. Download the configured feeds with bounded concurrency and explicit network timeouts.
2. Parse downloaded bytes using `feedparser`; keep network handling in `httpx`.
3. Normalize entries into the shared article response shape.
4. Require a non-empty title and a valid HTTP(S) article URL; skip unusable entries.
5. Convert available publication dates to UTC ISO 8601. Use `null` when dates cannot be determined; never invent dates.
6. Convert descriptions into plain text, removing HTML markup and collapsing unnecessary whitespace. Render them as text in React, never as raw HTML.
7. Deduplicate by normalized article URL within the collection. Keep URL normalization conservative so meaningful query parameters are preserved.
8. Sort dated entries newest first; put undated entries last with deterministic ordering.
9. Bound the returned result set to 100 articles for this first version.
10. Return successful entries even if another source fails. A malformed feed with usable entries may contribute results with a warning.

Do not call an LLM or fetch full article pages. No API key should be needed. Validate article links before exposing them as clickable URLs.

## API contract: two endpoints

The FastAPI backend owns both endpoints. No separate Next.js API routes are needed for this phase.

### `GET /api/health`

Return HTTP 200 with:

```json
{"status": "ok"}
```

This checks that the service is running; it does not test all upstream feeds.

### `GET /api/news`

Collect the configured feeds on request and return HTTP 200 when at least one feed was read successfully, including when that feed contains no usable articles. No request body or query parameters are required in version 1.

```json
{
  "articles": [
    {
      "id": "stable-url-derived-id",
      "title": "Example AI announcement",
      "url": "https://example.com/news/announcement",
      "source_id": "example-publisher",
      "source": "Example Publisher",
      "published_at": "2026-10-28T08:00:00Z",
      "description": "Plain-text description supplied by the RSS feed."
    }
  ],
  "sources": [
    {"id": "example-publisher", "name": "Example Publisher"}
  ],
  "collected_at": "2026-10-28T09:00:00Z",
  "warnings": []
}
```

Example values above are illustrative, not selected production sources.

- `id`: deterministic identifier derived from the normalized URL, stable between requests.
- `source_id`: matches a source's `id` for reliable filtering.
- `published_at`: UTC date string or `null`.
- `description`: plain text; use an empty string if absent and a frontend fallback such as “No description available.”
- `sources`: configured source identifiers and display names, including sources that failed so warnings remain understandable.
- `collected_at`: UTC timestamp for completion of this collection.
- `warnings`: objects containing `source_id` and a short user-facing `message`.

If all feeds fail, return HTTP 502 with a concise error in FastAPI's `detail` field. Do not expose stack traces or internal exception dumps. Unexpected backend errors use HTTP 500 with a generic user-facing message and server-side diagnostics.

## Local integration

- Run Next.js and FastAPI as separate local processes.
- Configure the frontend backend URL through `NEXT_PUBLIC_API_BASE_URL`, with a documented local example.
- Allow the local frontend origin through FastAPI CORS; avoid unnecessarily broad configuration.
- Keep feed configuration on the server; the browser only requests the backend endpoint.
- Add installation and run instructions to the existing frontend and backend READMEs during implementation.

## Suggested implementation structure

Adapt filenames to existing project conventions if needed; avoid unnecessary layers.

```text
backend/
  main.py                 FastAPI app and route wiring
  feeds.py                Configured sources and collection logic
  schemas.py              Response models
  tests/                  Focused RSS behavior tests
  pyproject.toml
  README.md
frontend/
  app/page.tsx            Dashboard and interaction state
  app/globals.css        Shared visual styles
  components/             Reusable UI only where useful
  lib/news.ts             API client and response types
  README.md
harness/build/
  01-rss-news-dashboard.md
```

## Implementation sequence

1. **RSS backend:** Add required dependencies, source configuration, response models, collection handling, and both endpoints.
2. **Backend verification:** Use representative feed fixtures to verify normalization, deduplication, absent dates, unsafe links, and partial/all-source failures. Check selected real feeds separately.
3. **Dashboard:** Build the layout, controls, cards, and interaction states using the API contract.
4. **Integration:** Connect the button, configure local CORS and API URL, and verify collection through the browser.
5. **Handoff:** Document run commands, chosen sources, limitations, and observed checks. Record actual verification results when implementation occurs.

## Acceptance criteria

- [ ] Both apps run locally with documented commands and no paid keys.
- [x] The health endpoint returns the specified response.
- [ ] Clicking Collect latest news requests real RSS data from the backend and displays it.
- [ ] Every displayed article has a title, publisher, valid original link, and description or clear fallback.
- [x] Missing dates are represented honestly and dated articles appear newest first.
- [x] Duplicate article URLs are shown once per collection.
- [ ] Search and source filtering update the displayed results and count without another backend request.
- [ ] Loading, initial, empty, no-match, partial-failure, and complete-failure states behave as specified.
- [ ] Previous results survive a failed recollection without receiving a misleading fresh timestamp.
- [x] RSS markup is not injected into the page and unsafe article URL schemes are rejected.
- [ ] The dashboard is usable by keyboard and on mobile and desktop widths.
- [x] Refreshing clears results; neither app stores articles persistently.
- [x] The UI does not imply that collected stories have been fact-checked.

## Planned verification

Run focused backend tests against fixture data so checks do not depend on changing live feeds. Perform a live collection smoke check, frontend lint, and production build with the repository's configured package manager. Verify the complete button-to-results flow in a browser, including simulated upstream and backend failures where practical.

Verification on 28 October 2026:

- `UV_CACHE_DIR=/tmp/verinews-uv uv run --directory backend pytest`: 13 passed. Covers normalization, unsafe URLs, missing dates/descriptions, deduplication, sorting, result limits, empty feeds, malformed feeds, partial failures, health, and all-source 502 responses.
- Live FastAPI ASGI smoke check: health returned `{"status":"ok"}`; `/api/news` returned HTTP 200 with 90 articles and no source warnings. All three configured feeds worked. Local CORS returned `http://localhost:3000`.
- `pnpm --pm-on-fail=ignore --dir frontend lint`: passed. The installed pnpm is 11.1.3 while the repository requests 12.15.0; the override was used only for verification, leaving the package-manager declaration unchanged.
- Initial build attempts hit sandbox process/port restrictions. Final verification outside the sandbox with `node node_modules/typescript/bin/tsc --noEmit && node node_modules/next/dist/bin/next build` (from `frontend/`) passed TypeScript checking and the production Turbopack build.
- Browser verification could not run: the browser tool reported no available browsers. Mobile/desktop visual checks and simulated frontend interactions remain unverified.

Implementation includes all specified UI states, in-memory filtering, recollection replacement, and preservation of previous data/timestamps on failure. These frontend behaviors have been reviewed in code but require browser interaction checks.

## Later phases

After this phase works, separately specify full article extraction using `trafilatura`, local LLM claim extraction, supporting-source retrieval and comparison, and social post drafting. These are future possibilities, not acceptance requirements for version 1.

## Agreed scope update: recent ten stories

The user requested a first filtering pass: collect feeds, keep entries published
within the preceding 24 hours, deduplicate normalized URLs, and return the newest
10. Unknown dates and future timestamps are excluded; fewer eligible entries
produce fewer results. This supersedes the original 100-article limit and inclusion
of undated articles. Google News AI is currently the active feed; the three direct
publisher feeds were disabled by the user. No relevance/significance scoring or
cross-publisher event clustering is included in this pass.

## Agreed scope update: most-covered story groups

The user authorized broader RSS discovery and a first ranking pass without AI.
Five English/US Google News topic searches replace the single query. Entries from
the last 24 hours are deduplicated by normalized URL and grouped conservatively
by headline similarity. The API returns the top 10 groups, ranked by distinct
identified publisher count and then freshness, with per-publisher coverage links.
The dashboard labels these as most-covered stories within collected feeds.
Publisher filtering matches any coverage member. `sources` now contains returned
publishers; warnings name unavailable query feeds directly. This supersedes the
previous newest-only ordering. It adds no AI, fact-checking, persistence, or
momentum tracking. Syndicated coverage can inflate publisher counts; differently
worded headlines can remain separate.

Verification: 22 backend fixture tests and frontend lint passed. Live collection
returned 10 story groups from five searches with no warnings. Browser interaction
checks remain unavailable in this session.

TypeScript checking and the production Next.js build also passed.

## Region coverage update

The user requested India in addition to US coverage. Each of the five topic
queries now runs in both US-English and India-English editions (10 feeds).
Results share the existing 24-hour window, deduplication, grouping, and top-10
ranking. Publisher counts remain unique across regions.

## Dashboard controls update

At the user's request, removed the search field and publisher dropdown, along
with local filter state and the no-match state. The story count now reflects all
returned story groups. Backend collection and ranking are unchanged.

## Agreed scope update: local X draft generation

The user authorized a Generate X post action using installed local Ollama. Each
story now offers generation, an editable draft, weighted X character counting
(280 maximum), and Copy. A new `POST /api/posts/x` FastAPI endpoint calls local
Ollama (`qwen3:4b-instruct` by default), with thinking disabled. The server appends
publisher attribution and the original supplied URL. Errors preserve prior drafts;
successful recollection resets them. This supersedes the original prohibition on
LLM integration and post generation only for this requested draft feature. It adds
no publishing, full article scraping, or fact-checking. Models may exceed length
instructions; the UI requires editing invalid/overlong drafts before copying.

X draft verification: all 34 backend tests pass, including mock generation,
prompt/input bounds, malformed output, missing model/server, timeout, busy
handling, POST endpoint and CORS. A real call to the user's local
`qwen3:4b-instruct` generated a fictional sample draft with attribution and the
supplied URL; twitter-text counted it as 171/280, valid. URL, emoji, CJK and
280/281 boundary checks passed. Frontend lint, TypeScript and production build
passed after correcting a CSS edit and the twitter-text ESM import. Browser
interaction and clipboard checks remain unverified (no browser available).

## Composer UI and LinkedIn update

At the user's request, the composer offers X and LinkedIn with separate editable
drafts, platform counts, optional source-link inclusion, regenerate and copy.
LinkedIn requests 2–3 paragraphs and 80–140 words when supported by the RSS text.
Trailing publisher suffixes (for example ` - Gulf Daily News (Bahrain)`) and the
separate source-label line are omitted. Publisher coverage counts and expandable
links were removed from cards; backend ranking remains unchanged.

Verification: 36 backend tests passed. A live local LinkedIn generation produced
a 66-word fictional sample draft without a publisher suffix or source-label line.
Lint, TypeScript and production build passed.

## shadcn/ui redesign

The user requested a more polished interface using shadcn/ui. Official New York
registry components were installed manually under `frontend/components/ui/`,
with the upstream MIT license. `components.json` configures future component
additions. The dashboard now uses a desktop workspace rail, responsive story
cards, a region badge, collection statistics, empty/loading states, and a violet
accent with shared Tailwind theme tokens. A Create post action opens a spacious
Radix-backed Sheet with accessible platform Tabs, editor, source-link Switch,
character counts, regenerate and copy actions. Drafts survive closing the panel;
successful recollection still resets them. Removed search/publisher controls and
publisher coverage details remain absent.

Verification: frontend ESLint, TypeScript and production build passed. Backend
behavior was unchanged by this visual redesign. The browser tool returned no
available browsers, so desktop/mobile appearance, focus behavior and clipboard
interactions remain unverified in a browser.

## Full publisher article extraction

The user installed Trafilatura and authorized full-article context before post
generation. Create post now loads readable article text on demand, resolves Google
News links, previews extracted text and enables generation only after success.
Both post endpoints also require extraction server-side; RSS descriptions are not
used as evidence. A bounded memory cache reuses article text across formats for
10 minutes. This supersedes the original no-article-scraping non-goal for this
explicitly requested feature, without adding persistent storage or fact-checking.

Downloads, redirects, sizes and context lengths are bounded. Private-address and
non-HTML URLs are rejected. Unavailable, blocked, recognized paywalled or too-short
pages produce a useful error with no headline-only fallback. The model is told
not to invent claims about verification or missing official confirmation.

Verification: 52 fixture tests passed outside the sandbox (the sandboxed worker
thread test stalled). Frontend lint, TypeScript and production build passed.
Live Google resolution and publisher extraction yielded 333 words, while another
story was unavailable and correctly rejected. Browser interactions unavailable.

The live full-article-to-Ollama path completed. Its draft contained an altered
numeric range, so a regression-tested guard now rejects output ranges absent
from the source text. This is a narrow check, not comprehensive fact verification;
model drafts still require review.

## Short-article extraction fix

The user supplied a GDN article that extracted to 97 words and was rejected by
the old 100-word floor. Lowered the floor to 60 words while retaining HTML,
paywall, blocked-page, size and address checks. Added clearer extraction errors
and a direct publisher-link fallback. Headline/content word overlap now blocks
obvious mismatches at both extraction and generation; the supplied Google link
resolved to an unrelated story during diagnostics. Generation uses the loaded,
validated publisher URL. This check is not semantic matching or verification.

Verification: 54 tests passed; lint, TypeScript and production build passed. The
supplied GDN URL extracted 97 words live and passed the headline check. Browser
interaction checks remain unavailable.

## Extraction retry clarity

After another reported short-text failure, the supplied direct GDN URL was tested
through the running backend and returned HTTP 200 with 97 words. Precision and
default Trafilatura extraction both found the same text. The failing URL could
not be established from the reported message. Made the publisher URL form always
visible while context is unavailable and renamed the RSS retry action explicitly.
Short-text failures now include the actual extracted word count and publisher
domain, rather than a generic threshold message. The 60-word floor is unchanged.
Extraction tests passed; frontend lint, TypeScript and production build passed.
Browser interactions remain unverified.

## Automatic source resolution and fallback

The user requested automatic reading without pasting publisher URLs. The supplied
Google RSS link resolved successfully to Newstimes, but the publisher returned a
JavaScript Client Challenge instead of the article. Added explicit challenge
classification, preserved US/India locale during Google decoding, and removed
manual URL entry. The extraction API now tries up to four distinct collected
coverage links within a 60-second budget, checking the headline match each time.
Successful context is cached under the resolved URL and carries its publisher
name into the studio and post generation. All unavailable sources means no draft.

Verification: 58 backend tests passed; frontend lint, TypeScript and production
build passed. Live attempts across four publishers for a current story remained
unavailable and correctly blocked generation. Browser interactions unverified.

## DDGS discovery update

The user authorized DDGS without LangChain. Collection now searches DuckDuckGo
News for `latest ai news` in India and US English, moderate Safe Search, past-day
filter, up to 20 results per region. Existing date filtering, deduplication,
grouping, coverage ranking and top-10 selection apply. Google RSS remains an
explicitly announced fallback when DDGS fails or yields no eligible articles.
This replaces RSS as the primary discovery method without changing article
extraction or claiming Playwright was implemented.

A live India query returned current news. Later calls returned no results; the
integrated collector correctly returned 10 RSS fallback stories with a warning.
Results need not match DuckDuckGo's browser News tab or its order. Screenshot
settings used Any time, while the app filters to 24 hours and reranks groups.

DDGS verification: all 65 backend tests pass. Frontend ESLint and TypeScript
checks pass. Live collection and fallback outcomes are recorded above. No
browser interaction verification was available in this session.

## DuckDuckGo-only discovery

The user explicitly rejected RSS fallback. Removed RSS feed configuration,
collection/parsing code and the feedparser dependency. `GET /api/news` now uses
only DDGS's DuckDuckGo news backend. Failure returns a DuckDuckGo-specific 502;
valid empty search results remain empty. Partial regional success is preserved.
No automatic switch to another discovery provider occurs. Existing Google URL
resolution remains only for older article links, not RSS discovery. Refreshing
clears any old in-memory RSS results shown by the frontend.

DuckDuckGo-only verification: all 56 backend tests passed, including successful
empty results, unavailable search returning 502, partial regional success and
retained top-10 selection. Removed legacy RSS tests with the deleted RSS code.

## Authorized Bing/Yahoo fallback after DuckDuckGo 403

The reported collection failure was reproduced: DuckDuckGo news returned HTTP
403, which DDGS surfaced as no results. The user explicitly selected Bing/Yahoo
fallback with a visible notice, keeping RSS disabled. Added that search fallback
for failed or empty primary discovery. Live collection returned 10 stories with
the provider-switch warning. The query, regions, date filters and ranking are
unchanged. No RSS code or dependency was restored.

The separate file:/// browser warning was not reproduced. App source and served
HTML contained no file URLs. Added client-side HTTP(S) validation for incoming
results, coverage links and extracted publisher URLs, including older state.
Verification: 57 backend tests, URL guard checks, frontend lint, TypeScript and
production build passed. The browser warning's original initiator remains unknown.

## Bing/Yahoo-only search

The user requested always using Bing/Yahoo instead of first trying DuckDuckGo.
Removed the DuckDuckGo attempt and provider-switch notice. Every regional query
now uses DDGS with `backend="bing,yahoo"`; RSS remains absent. Genuine regional
failures retain warnings, and total failure returns a Bing/Yahoo-specific error.
Live collection returned 10 stories with no warnings. All 56 backend tests passed.

## Publicly available text on subscription-marked pages

The user's Verge URL declares the current NewsArticle subscription-only but also
returns readable public text. Replaced the blanket metadata regex with scoped
JSON-LD inspection. Sufficient public text may be used as a clearly labelled,
potentially incomplete excerpt (`truncated` and `access_note`), with that limitation
passed to Ollama. This adds no access to hidden subscriber content. Short or
blocked responses still fail. Related-article subscription flags no longer cause
false positives on a free current article.

Verification: the supplied Verge page loaded 100 words and passed the headline
check. All 58 backend tests, lint, TypeScript and production build passed. Browser
visual checks were unavailable.

## Show only stories with readable content

The user requested content/description beyond the headline and removal of stories
without usable news text. Collection now considers up to 30 ranked candidate
groups, checks three at a time (15 seconds per story, 60-second shared reading
budget), and returns at most 10 readable stories. Unreadable groups are omitted;
lower-ranked candidates backfill when possible. Selected publisher URLs and dates
are preserved. Cards use actual extracted-text excerpts, loaded word counts and
public-excerpt labels. The writing studio is preloaded with that context. Content
remains in browser/server memory, without persistent article storage.

Verification: 62 backend tests passed, including removal, backfill, excerpt/source
metadata and timeouts. Frontend lint, TypeScript and production build passed.
Live collection returned 9 readable stories (275–1,386 words) without warnings.
No browser interaction checks were available. RSS and DuckDuckGo remain disabled.

## Larger candidate pool before filtering to ten

The user requested fetching news before selecting/storing the final ten. Search
now requests up to three pages of 20 results in both regions (120 requested),
stopping when no new URLs appear. It preserves earlier pages if later retrieval
fails. Removed the 30-group cutoff before article reading. Date filtering,
deduplication and grouping see the whole retrieved pool; readability checks can
continue beyond candidate 30 until ten succeed or the time budget expires.
Added candidate/check counts to the API and dashboard. No persistent storage is
introduced: the selected ten remain in collection memory.

Verification: 64 backend tests passed, including pagination and backfill beyond
30 candidates. Frontend lint, TypeScript and production build passed.

Live smoke check: 70 search candidates collected, 15 story groups checked, 10
readable stories kept, and no warnings.
