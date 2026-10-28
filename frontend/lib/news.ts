export type Coverage = {
  title: string; url: string; source_id: string; source: string;
  published_at: string | null;
};
export type Article = {
  id: string; title: string; url: string; source_id: string; source: string;
  published_at: string | null; description: string;
  publisher_count: number; coverage: Coverage[];
};
export type NewsResponse = {
  articles: Article[];
  sources: { id: string; name: string }[];
  collected_at: string;
  warnings: { source_id: string; message: string }[];
};

type IncomingArticle = Omit<Article, "coverage" | "publisher_count"> & {
  coverage?: Coverage[] | null;
  publisher_count?: number | null;
};

// Older backend responses and Fast Refresh state may predate story grouping.
export function normalizeArticle(article: IncomingArticle): Article {
  const coverage = Array.isArray(article.coverage) && article.coverage.length
    ? article.coverage
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
  const response = await fetch(`${base}/api/news`, { cache: "no-store", signal: AbortSignal.timeout(60000) });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "News collection failed. Please try again.");
  }
  const data: Omit<NewsResponse, "articles"> & { articles: IncomingArticle[] } = await response.json();
  return { ...data, articles: data.articles.map(normalizeArticle) };
}

export async function generateXPost(article: Article): Promise<{ draft: string; model: string }> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  try {
    const response = await fetch(`${base}/api/posts/x`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(190000),
      body: JSON.stringify({ title: article.title, description: article.description, source: article.source, url: article.url }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Could not generate a draft. Please try again.");
    if (typeof body?.draft !== "string" || !body.draft.trim()) throw new Error("The service returned an empty draft. Please try again.");
    return body;
  } catch (err) {
    if (err instanceof Error && err.name === "TimeoutError") throw new Error("Draft generation timed out. Try again or use a smaller local model.");
    if (err instanceof TypeError) throw new Error("Could not reach the backend. Check that FastAPI is running.");
    throw err;
  }
}
