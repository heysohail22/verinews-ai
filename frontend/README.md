# VeriNews dashboard

Requires Node.js 20.9+ and the pnpm version specified in `package.json`.

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

Open http://localhost:3000 and run the FastAPI backend separately (see
`../backend/README.md`). `NEXT_PUBLIC_API_BASE_URL` defaults to
`http://localhost:8000`; set it in `.env.local` to change the backend URL, then
restart Next.js. This public variable is embedded during production builds.

Click **Collect latest news** to search Bing/Yahoo News via DDGS (India and US).
Bing/Yahoo is always used directly. DuckDuckGo is not queried. Unavailable search shows an error. There is no RSS collection or fallback.
The dashboard shows the 10 most-covered AI story groups from the last 24 hours,
ranked by distinct publisher count then freshness. Ranking describes collected
coverage, not verification or independent confirmation. Collection replaces the previous results; failed recollections retain
previous stories and their original timestamp. Refreshing clears all articles.
No API keys or article persistence are required. News collection does not fact-check stories.

```bash
pnpm lint
pnpm build
pnpm start
```

Each story has a **Create a post** composer with X and LinkedIn options, powered by local Ollama through FastAPI.
The default model is `qwen3:4b-instruct` (see backend setup). Generated drafts are
editable, with X-compatible weighted counts, a 3,000-character LinkedIn limit, regeneration, and Copy.
Copy is disabled when text is empty, invalid, or above the selected platform limit. If clipboard
access is unavailable, copy the text manually. Failed regeneration preserves the
previous draft; successful news recollection resets drafts. Refreshing clears them.
Review every draft: it is generated from extracted article text and is not fact-checked.

X and LinkedIn drafts are kept separately while switching formats. LinkedIn
requests a longer, paragraph-based update. The editor shows only the post body,
with an optional source link; copying includes the link only when selected.
Publisher suffixes and the separate source label are omitted from generated text.
Publisher coverage counts and expandable links have been removed from story cards.

## UI components

The dashboard uses shadcn/ui's New York components (Radix primitives) with a
shared Tailwind v4 theme, Lucide icons, and `clsx`/`tailwind-merge` utilities.
`components.json` configures aliases and theme settings. Component sources and
their MIT license are in `components/ui/`; no external theme service is needed.

Click **Create post** on a story to open the writing panel. It contains keyboard
navigable X/LinkedIn tabs, an editable draft and a source-link switch. Closing and
reopening preserves the draft until a successful recollection or page refresh.
The desktop rail collapses away on mobile; the writing panel fills narrow screens.

Redesign checks: ESLint, TypeScript and production build passed. Browser visual
and interaction checks were unavailable in the implementation session.

### Article reading

Opening Create post resolves and reads the publisher article before enabling
Generate. The panel displays the extracted word count, an expandable text preview,
and the resolved publisher link. Both formats reuse a short-lived backend memory
cache. Unavailable articles show a retry action and do not generate posts from the
headline. Text marked as an excerpt was shortened to the configured context cap.
Source text can still be incomplete; extraction does not fact-check it.


Article reading is automatic: Google links are resolved and up to four collected
sources are tried for a matching, readable article. The selected publisher and
source URL are shown in the studio and used in the generated draft. No manual
URL entry is required. If every candidate is blocked, too short or unrelated,
the panel offers **Retry available sources** and does not generate a headline-only
post. Some publisher sites return JavaScript challenges and remain unavailable.

If a subscription-marked page returns enough public text, the studio labels it
as a potentially incomplete excerpt rather than rejecting the page solely on
metadata. Review the extracted text and access note before drafting. Subscriber-only
content is not unlocked; insufficient public context still blocks generation.

Collection now checks publisher article text before displaying a story. Unreadable
stories are left out and lower-ranked candidates can fill the list, up to 10.
Cards show an article-text excerpt and loaded word count, with incomplete public
excerpts labelled. Create post reuses the loaded text. Search plus reading may
take about a minute. An empty collection means no readable recent stories qualified.

A larger pool is fetched before selecting the ten: up to three search pages per
region (120 candidate results). Collection counts show candidates, attempted
story checks and readable stories kept. There is no pre-reading 30-story cutoff.
Reading stops after ten successes or the time budget, so fewer may be returned.
Results are still in-memory and disappear on refresh.

## Newsroom and writing studio

The newsroom has a full-width layout without a sidebar. Each article card shows
the publisher URL and links to `/create/[id]` using Next.js navigation. Selected
article text and the collected news are stored in sessionStorage for this tab,
with an in-memory fallback if browser storage is unavailable. The writing route
provides X/LinkedIn drafts, character counts, editing, source-link controls and
copying. Direct visits without a selected article show a link back to the newsroom.
