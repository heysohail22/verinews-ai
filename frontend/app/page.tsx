"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { XPostDraft } from "@/components/x-post-draft";
import { collectNews, normalizeArticle, type NewsResponse } from "@/lib/news";

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function Home() {
  const [data, setData] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);

  async function collect() {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError("");
    try {
      const result = await collectNews();
      setData(result);
    } catch (err) {
      setError(err instanceof Error && err.name !== "TimeoutError" && err.name !== "TypeError"
        ? err.message : "Could not reach the news service. Check that the backend is running and try again.");
    } finally {
      pending.current = false;
      setLoading(false);
    }
  }

  const articles = (data?.articles ?? []).map(normalizeArticle);

  return (
    <main className="dashboard">
      <header className="masthead">
        <Link className="brand" href="/" aria-label="VeriNews home"><span className="brand-mark" aria-hidden="true">V</span>VeriNews<span className="edition">RSS EDITION</span></Link>
        <span className="header-note">A little signal. Less noise.</span>
      </header>
      <section className="intro" aria-labelledby="page-title">
        <div><p className="eyebrow">YOUR DAILY READING ROOM</p><h1 id="page-title">Most covered<br className="desktop-break" /> AI stories<span className="accent">.</span></h1><p className="intro-copy">Top 10 story groups from the last 24 hours.<br />Ranked by publisher count, then freshness within collected feeds.</p></div>
        <div className="collection"><button className="primary" disabled={loading} onClick={collect}><span aria-hidden="true" className={loading ? "spinning" : ""}>↻</span> {loading ? "Collecting…" : "Collect latest news"}</button><p>{data ? <>Last collected <time dateTime={data.collected_at}>{formatDate(data.collected_at)}</time></> : "Ready when you are. No automatic refreshes."}</p></div>
      </section>
      <div role="status" className="sr-only">{loading ? "Collecting news from RSS sources." : data ? `Collection complete. ${articles.length} stories shown.` : "Ready to collect news."}</div>
      {error && <div role="alert" className="notice error"><div><strong>Unable to collect news</strong><p>{error} {data && "Your previous collection is still shown below."}</p></div><button disabled={loading} onClick={collect}>Try again</button></div>}
      {!!data?.warnings.length && <aside className="notice" aria-label="Source warnings"><div><strong>Some sources need another moment</strong>{data.warnings.map(w => <p key={w.source_id}>{w.message}</p>)}</div></aside>}
      <section aria-label="News collection" aria-busy={loading}>
        <div className="results-heading"><h2>Most covered in the last 24 hours</h2><span>{articles.length} {articles.length === 1 ? "story" : "stories"}</span></div>
        {!data ? <div className="empty"><span className="empty-icon" aria-hidden="true">≋</span><p className="eyebrow">A FRESH START</p><h3>Your next read is waiting.</h3><p>Click “Collect latest news” to bring the latest AI and<br className="desktop-break" /> technology reporting into one place.</p><span className="empty-footnote">Coverage estimates from RSS feeds. Always linked to the source.</span></div>
          : !data.articles.length ? <div className="empty"><h3>No stories just yet.</h3><p>No articles with publication dates in the last 24 hours were found. Try collecting again.</p><button onClick={collect} disabled={loading}>Try again</button></div>
          : <div className="article-grid">{articles.map(article => <article className="article-card" key={article.id}><div className="article-meta"><span className="publisher">{article.source}</span>{article.published_at ? <time dateTime={article.published_at}>{formatDate(article.published_at)}</time> : <span>Date unavailable</span>}</div><h3>{article.title}</h3><p className="coverage-count">{article.publisher_count ? `Covered by ${article.publisher_count} ${article.publisher_count === 1 ? "publisher" : "publishers"}` : "Publisher not identified"} · Latest coverage shown</p><p className="description">{article.description || "No description available."}</p>{/^https?:\/\//i.test(article.url) && <a className="read-link" href={article.url} target="_blank" rel="noopener noreferrer">Read original <span aria-hidden="true">↗</span></a>}{article.coverage.length > 1 && <details className="coverage-details"><summary>View publisher coverage ({article.coverage.length})</summary><ul>{article.coverage.map(item => <li key={item.source_id}><a href={item.url} target="_blank" rel="noopener noreferrer">{item.source}: {item.title}</a>{item.published_at && <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>}</li>)}</ul></details>}<XPostDraft key={`${article.id}:${data.collected_at}`} article={article} /></article>)}</div>}
      </section>
      <footer><span>VeriNews <span className="footer-dot">/</span> Curiosity, collected.</span><p>Descriptions come from RSS feeds. Stories have not been fact-checked.</p></footer>
    </main>
  );
}
