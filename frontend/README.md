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

Click **Collect latest news** to fetch RSS news.
The dashboard shows the 10 most-covered AI story groups from the last 24 hours,
ranked by distinct publisher count then freshness. Expand publisher coverage to
read other reporting. Counts describe collected coverage, not verification or
independent confirmation. Collection replaces the previous results; failed recollections retain
previous stories and their original timestamp. Refreshing clears all articles.
No API keys or article persistence are required. News collection does not fact-check stories.

```bash
pnpm lint
pnpm build
pnpm start
```

Each story has **Generate X post**, powered by local Ollama through FastAPI.
The default model is `qwen3:4b-instruct` (see backend setup). Generated drafts are
editable, with X-compatible weighted character counts, regeneration, and Copy.
Copy is disabled when text is empty, invalid, or above 280 characters. If clipboard
access is unavailable, copy the text manually. Failed regeneration preserves the
previous draft; successful news recollection resets drafts. Refreshing clears them.
Review every draft: it is generated from RSS text and is not fact-checked.
