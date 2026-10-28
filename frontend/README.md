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

Click **Collect latest news** to fetch RSS news. Search and publisher filters run
locally; publisher filtering matches any publisher in a story's coverage.
The dashboard shows the 10 most-covered AI story groups from the last 24 hours,
ranked by distinct publisher count then freshness. Expand publisher coverage to
read other reporting. Counts describe collected coverage, not verification or
independent confirmation. Collection replaces the previous results; failed recollections retain
previous stories and their original timestamp. Refreshing clears all articles.
No API keys, persistence, generated summaries, or fact-checking are involved.

```bash
pnpm lint
pnpm build
pnpm start
```
