export type Coverage = {
  title: string; url: string; source_id: string; source: string;
  published_at: string | null;
};
export type Article = {
  id: string; title: string; url: string; source_id: string; source: string;
  published_at: string | null; description: string;
  publisher_count: number; coverage: Coverage[];
  content?: string; content_word_count?: number; content_is_excerpt?: boolean; content_note?: string;
};
export type NewsResponse = {
  candidates_found?: number; stories_checked?: number;
  articles: Article[];
  sources: { id: string; name: string }[];
  collected_at: string;
  warnings: { source_id: string; message: string }[];
};

export function isHttpUrl(value: unknown): value is string {
  if (typeof value !== "string" || /[\x00-\x20\x7f]/.test(value)) return false;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}

type IncomingArticle = Omit<Article, "coverage" | "publisher_count"> & {
  coverage?: Coverage[] | null;
  publisher_count?: number | null;
};

// Older backend responses and Fast Refresh state may predate story grouping.
export function normalizeArticle(article: IncomingArticle): Article {
  const coverage = Array.isArray(article.coverage) && article.coverage.length
    ? article.coverage.filter(item => isHttpUrl(item.url))
    : [{
      title: article.title, url: article.url, source_id: article.source_id,
      source: article.source, published_at: article.published_at,
    }];
  return {
    ...article,
    coverage,
    publisher_count: article.publisher_count ?? new Set(
      coverage.filter(item => item.source_id !== "google-news-unattributed")
        .map(item => item.source_id),
    ).size,
  };
}

export async function collectNews(): Promise<NewsResponse> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/api/news`, { cache: "no-store", signal: AbortSignal.timeout(105000) });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "News collection failed. Please try again.");
  }
  const data: Omit<NewsResponse, "articles"> & { articles: IncomingArticle[] } = await response.json();
  return { ...data, articles: data.articles.filter(article => isHttpUrl(article.url)).map(normalizeArticle) };
}

export type PostPlatform = "x" | "linkedin";

export async function generatePost(article: Article, platform: PostPlatform): Promise<{ draft: string; body: string; source_url: string; model: string }> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/posts/${platform}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(240000),
      body: JSON.stringify({ title: article.title, description: article.description, source: article.source, url: article.url }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Could not generate a draft. Please try again.");
    if (typeof body?.draft !== "string" || !body.draft.trim()) throw new Error("The service returned an empty draft. Please try again.");
    if (typeof body.body !== "string" || !body.body.trim() || typeof body.source_url !== "string" || !isHttpUrl(body.source_url)) {
      throw new Error("The backend is using an older draft format. Restart FastAPI and try again.");
    }
    return body;
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") throw new Error("Draft generation timed out. Try again or use a smaller local model.");
    if (err instanceof TypeError) throw new Error("Could not reach the backend. Check that FastAPI is running.");
    throw err;
  }
}

export type ExtractedArticle = { access_note?: string; source: string; url: string; text: string; word_count: number; truncated: boolean };

export async function extractArticle(article: Article): Promise<ExtractedArticle> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/articles/extract`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(65000), body: JSON.stringify({ url: article.url, expected_title: article.title, source: article.source, alternatives: article.coverage.filter(item => item.url !== article.url).slice(0, 9).map(item => ({ url: item.url, source: item.source })) }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Could not read the full article. Try again.");
    if (typeof body?.text !== "string" || typeof body?.url !== "string" || !isHttpUrl(body.url) || !body.text.trim()) throw new Error("Article extraction returned no usable text. Restart the backend and try again.");
    return body;
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") throw new Error("Reading the article timed out. Try again.");
    if (err instanceof TypeError) throw new Error("Cannot reach the article service. Check that FastAPI is running.");
    throw err;
  }
}
