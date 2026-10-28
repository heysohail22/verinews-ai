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
  candidates_found?: number; stories_checked?: number; ai_reviewed?: number; ai_selected?: number;
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

export type CollectionProgress = { stage: "search" | "ranking" | "reading"; message: string; completed?: number; total?: number };

export async function collectNews(onProgress?: (progress: CollectionProgress) => void): Promise<NewsResponse> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/api/news/stream`, { cache: "no-store", signal: AbortSignal.timeout(900000) });
  if (!response.ok || !response.body) {
    throw new Error(response.status === 404 ? "Restart FastAPI to enable the AI review progress endpoint." : "Could not start news collection. Please try again.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: NewsResponse | null = null;
  function event(line: string) {
    if (!line.trim()) return;
    const item = JSON.parse(line);
    if (item.type === "error") throw new Error(item.message || "Collection failed.");
    if (item.type === "progress") onProgress?.(item as CollectionProgress);
    if (item.type === "result") {
      const data = item.data as NewsResponse;
      if (!Array.isArray(data?.articles)) throw new Error("The news service returned invalid results.");
      result = { ...data, articles: data.articles.filter(article => isHttpUrl(article.url)).map(normalizeArticle) };
    }
  }
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) event(line);
      if (chunk.done) { event(buffer); break; }
    }
    if (!result) throw new Error("Collection ended before results were ready. Please try again.");
    return result;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
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

export type EvidenceResult = {
  claim: string; status: "supported" | "conflicting_evidence" | "insufficient_evidence";
  checked_at: string; notes: string[];
  sources: { title: string; url: string; publisher: string; relationship: "supports" | "contradicts" | "inconclusive"; passage: string; explanation: string }[];
};
export async function checkEvidence(article: Article): Promise<EvidenceResult> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/api/evidence`, {
    method: "POST", headers: { "Content-Type": "application/json" }, signal: AbortSignal.timeout(260000),
    body: JSON.stringify({ title: article.title, source: article.source, url: article.url }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || "Evidence check failed. Please try again.");
  if (!["supported", "conflicting_evidence", "insufficient_evidence"].includes(body?.status) || !Array.isArray(body?.sources) || !Array.isArray(body?.notes)) throw new Error("The evidence service returned invalid results.");
  return { ...body, sources: body.sources.filter((source: { url: unknown }) => isHttpUrl(source.url)) };
}
