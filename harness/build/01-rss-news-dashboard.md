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
