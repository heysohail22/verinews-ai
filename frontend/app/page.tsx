"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { collectNews, type NewsResponse } from "@/lib/news";

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function Home() {
  const [data, setData] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const pending = useRef(false);

  async function collect() {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError("");
    try {
      const result = await collectNews();
      setData(result);
      setSource(current => result.sources.some(s => s.id === current) ? current : "");
    } catch (err) {
      setError(err instanceof Error && err.name !== "TimeoutError" && err.name !== "TypeError"
        ? err.message : "Could not reach the news service. Check that the backend is running and try again.");
    } finally {
      pending.current = false;
      setLoading(false);
    }
  }

  const query = search.trim().toLocaleLowerCase();
  const articles = (data?.articles ?? []).filter(article =>
    (!source || article.source_id === source) &&
    (!query || `${article.title} ${article.description}`.toLocaleLowerCase().includes(query)));

  function clearFilters() { setSearch(""); setSource(""); }

  return (
    <main className="dashboard">
      <header className="masthead">
        <Link className="brand" href="/" aria-label="VeriNews home"><span className="brand-mark" aria-hidden="true">V</span>VeriNews<span className="edition">RSS EDITION</span></Link>
        <span className="header-note">A little signal. Less noise.</span>
      </header>
      <section className="intro" aria-labelledby="page-title">
        <div><p className="eyebrow">YOUR DAILY READING ROOM</p><h1 id="page-title">Latest AI &amp;<br className="desktop-break" /> Technology News<span className="accent">.</span></h1><p className="intro-copy">Fresh perspectives from across the tech world.<br />Collect the latest stories, find your focus, and read the originals.</p></div>
        <div className="collection"><button className="primary" disabled={loading} onClick={collect}><span aria-hidden="true" className={loading ? "spinning" : ""}>↻</span> {loading ? "Collecting…" : "Collect latest news"}</button><p>{data ? <>Last collected <time dateTime={data.collected_at}>{formatDate(data.collected_at)}</time></> : "Ready when you are. No automatic refreshes."}</p></div>
      </section>
      <div role="status" className="sr-only">{loading ? "Collecting news from RSS sources." : data ? `Collection complete. ${articles.length} articles shown.` : "Ready to collect news."}</div>
      {error && <div role="alert" className="notice error"><div><strong>Unable to collect news</strong><p>{error} {data && "Your previous collection is still shown below."}</p></div><button disabled={loading} onClick={collect}>Try again</button></div>}
      {!!data?.warnings.length && <aside className="notice" aria-label="Source warnings"><div><strong>Some sources need another moment</strong>{data.warnings.map(w => <p key={w.source_id}>{data.sources.find(s => s.id === w.source_id)?.name ?? w.source_id}: {w.message}</p>)}</div></aside>}
      <section aria-label="News collection" aria-busy={loading}>
        <div className="filters"><div className="search-control"><label htmlFor="search">Search stories</label><input id="search" type="search" placeholder="Search titles and descriptions…" value={search} onChange={e => setSearch(e.target.value)} /></div><div className="source-control"><label htmlFor="source">Publisher</label><select id="source" value={source} onChange={e => setSource(e.target.value)}><option value="">All sources</option>{data?.sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div></div>
        <div className="results-heading"><h2>The latest stories</h2><span>{articles.length} {articles.length === 1 ? "article" : "articles"}{data && (search || source) ? ` of ${data.articles.length}` : ""}</span></div>
        {!data ? <div className="empty"><span className="empty-icon" aria-hidden="true">≋</span><p className="eyebrow">A FRESH START</p><h3>Your next read is waiting.</h3><p>Click “Collect latest news” to bring the latest AI and<br className="desktop-break" /> technology reporting into one place.</p><span className="empty-footnote">Direct from publishers. Always linked to the source.</span></div>
          : !data.articles.length ? <div className="empty"><h3>No stories just yet.</h3><p>The feeds returned no usable articles. Try collecting again.</p><button onClick={collect} disabled={loading}>Try again</button></div>
          : !articles.length ? <div className="empty"><h3>No matching stories.</h3><p>Try a different search or publisher.</p><button onClick={clearFilters}>Clear filters</button></div>
          : <div className="article-grid">{articles.map(article => <article className="article-card" key={article.id}><div className="article-meta"><span className="publisher">{article.source}</span>{article.published_at ? <time dateTime={article.published_at}>{formatDate(article.published_at)}</time> : <span>Date unavailable</span>}</div><h3>{article.title}</h3><p className="description">{article.description || "No description available."}</p>{/^https?:\/\//i.test(article.url) && <a className="read-link" href={article.url} target="_blank" rel="noopener noreferrer">Read original <span aria-hidden="true">↗</span></a>}</article>)}</div>}
      </section>
      <footer><span>VeriNews <span className="footer-dot">/</span> Curiosity, collected.</span><p>Descriptions come from RSS feeds. Stories have not been fact-checked.</p></footer>
    </main>
  );
}
