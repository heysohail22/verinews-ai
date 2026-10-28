export type Article = {
  id: string; title: string; url: string; source_id: string; source: string;
  published_at: string | null; description: string;
};
export type NewsResponse = {
  articles: Article[];
  sources: { id: string; name: string }[];
  collected_at: string;
  warnings: { source_id: string; message: string }[];
};

export async function collectNews(): Promise<NewsResponse> {
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
  const response = await fetch(`${base}/api/news`, { cache: "no-store", signal: AbortSignal.timeout(60000) });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "News collection failed. Please try again.");
  }
  return response.json();
}
