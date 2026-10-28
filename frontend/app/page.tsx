"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowRight, ArrowUpRight, BrainCircuit, Check, Clock3, FilePenLine, Globe2, Layers3, Link2, Loader2, Newspaper, RefreshCw, Rss, TriangleAlert } from "lucide-react";
import { EvidenceCheck } from "@/components/evidence-check";
import { saveWorkspace, useWorkspace } from "@/lib/workspace";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { collectNews, isHttpUrl, normalizeArticle, type CollectionProgress, type NewsResponse } from "@/lib/news";

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function Home() {
  const cached = useWorkspace<NewsResponse>("verinews:collection");
  const [fresh, setData] = useState<NewsResponse | null>(null);
  const data = fresh ?? cached;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<CollectionProgress>({ stage: "search", message: "Starting news collection…" });
  const pending = useRef(false);

  async function collect() {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError("");
    setProgress({ stage: "search", message: "Searching Bing/Yahoo for recent AI headlines…" });
    try { const result = await collectNews(setProgress); setData(result); saveWorkspace("verinews:collection", result); }
    catch (err) {
      setError(err instanceof Error && !["TimeoutError", "TypeError"].includes(err.name)
        ? err.message : "Could not reach the news service. Check that the backend is running and try again.");
    } finally { pending.current = false; setLoading(false); }
  }

  const articles = (data?.articles ?? []).filter(article => isHttpUrl(article.url) && !!article.content?.trim()).map(normalizeArticle);

  return <div className="min-h-screen font-sans">
    <div>
      <header className="border-b bg-white/90">
        <div className="mx-auto flex h-20 max-w-[1280px] items-center justify-between gap-4 px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="VeriNews home"><span className="flex size-10 items-center justify-center rounded-2xl bg-primary text-white"><Layers3 className="size-5" /></span><span className="text-xl font-bold tracking-tight">VeriNews<span className="text-primary">.</span></span></Link>
          <div className="flex items-center gap-5"><span className="hidden text-xs text-muted-foreground sm:block">Discover. Read. Create.</span><Badge variant="outline" className="gap-2 rounded-full px-3 py-2 text-[11px]"><Globe2 className="size-3.5" />US + India</Badge></div>
        </div>
      </header>

      <main id="newsroom" className="mx-auto max-w-[1280px] px-5 pb-8 pt-10 sm:px-9 sm:pt-12 xl:px-8">
        <section className="flex flex-col justify-between gap-6 pb-9 md:flex-row md:items-end" aria-labelledby="page-title">
          <div><div className="mb-4 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary"><span className="size-1.5 rounded-full bg-primary" />THE DAILY AI BRIEF</div><h1 id="page-title" className="text-3xl font-semibold tracking-[-1.4px] max-w-3xl sm:text-[48px] sm:leading-[1.12]">Stay curious. Share what matters<span className="text-primary">.</span></h1><p className="mt-3 max-w-xl text-[13px] leading-6 text-muted-foreground">AI-selected stories from the last 24 hours.<br className="hidden sm:block" /> Find your next read. Create something worth sharing.</p></div>
          <div className="shrink-0 md:text-right"><Button onClick={collect} disabled={loading} className="h-11 rounded-lg px-5 text-xs shadow-sm">{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />} {loading ? progress.stage === "ranking" ? "AI reviewing…" : progress.stage === "reading" ? "Reading articles…" : "Collecting…" : "Collect latest news"}</Button><p className="mt-3 text-[10px] text-muted-foreground">{data ? <>Last collected <time dateTime={data.collected_at}>{formatDate(data.collected_at)}</time></> : "Local AI review may take a few minutes."}</p></div>
        </section>

        <div className="mb-9 grid grid-cols-3 overflow-hidden rounded-xl border bg-white">
          {[{icon: Newspaper, value: String(articles.length).padStart(2, "0"), label: "Stories collected"}, {icon: Clock3, value: "24h", label: "News window"}, {icon: Globe2, value: "US + IN", label: "Regional coverage"}].map(({icon: Icon, value, label}) => <div key={label} className="flex items-center gap-3 border-r p-4 last:border-0 sm:px-6 sm:py-5"><span className="hidden size-9 items-center justify-center rounded-lg bg-background text-muted-foreground sm:flex"><Icon className="size-4" /></span><div><p className="text-base font-semibold tracking-tight sm:text-lg">{value}</p><p className="mt-1 text-[9px] text-muted-foreground sm:text-[11px]">{label}</p></div></div>)}
        </div>

        <div role="status" className="sr-only">{loading ? "Searching for recent AI news and checking article text." : data ? `${articles.length} stories collected.` : "Ready to collect news."}</div>
        {loading && <Card className="mb-7 overflow-hidden border-primary/20 bg-white shadow-none" role="status" aria-live="polite">
          <div className="flex items-start gap-4 p-5 sm:p-6"><span className="relative flex size-11 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary"><span className="absolute inset-0 rounded-xl border border-primary/30 motion-safe:animate-ping" /><BrainCircuit className="size-5 motion-safe:animate-pulse" /></span><div className="min-w-0 flex-1"><h2 className="text-sm font-semibold">{progress.stage === "ranking" ? "AI is finding the stories that matter" : progress.stage === "reading" ? "Preparing readable stories" : "Gathering the latest headlines"}</h2><p className="mt-2 text-xs leading-6 text-muted-foreground">{progress.message}</p><div className="mt-4 grid grid-cols-3 gap-2">{(["search", "ranking", "reading"] as const).map((stage, index) => { const current = ["search", "ranking", "reading"].indexOf(progress.stage); return <div key={stage} className="space-y-2"><div className={`h-1 rounded-full ${index <= current ? "bg-primary" : "bg-muted"} ${index === current ? "motion-safe:animate-pulse" : ""}`} /><p className={`text-[10px] ${index === current ? "font-medium text-primary" : "text-muted-foreground"}`}>{["Collect", "AI review", "Read articles"][index]}</p></div>; })}</div><p className="mt-3 text-[10px] text-muted-foreground">Relevance review, not fact-checking. Previous results stay visible until the new collection is ready.</p></div><Loader2 className="size-4 shrink-0 animate-spin text-primary" /></div>
        </Card>}
        {error && <Alert variant="destructive" className="mb-6 bg-white"><TriangleAlert className="size-4" /><AlertTitle>Couldn’t collect news</AlertTitle><AlertDescription>{error} {data && "Your previous collection is still here."}<Button onClick={collect} disabled={loading} size="sm" variant="outline" className="ml-3 mt-2">Try again</Button></AlertDescription></Alert>}
        {!!data?.warnings.length && <Alert className="mb-6 border-amber-200 bg-amber-50"><TriangleAlert className="size-4" /><AlertTitle>Some sources are unavailable</AlertTitle><AlertDescription>{data.warnings.map(w => <p key={w.source_id}>{w.message}</p>)}</AlertDescription></Alert>}

        <section aria-label="News stories" aria-busy={loading}>
          {data && <p className="mb-4 text-[11px] text-muted-foreground">{data.candidates_found ?? 0} search candidates collected · {data.ai_reviewed ?? 0} headlines reviewed by AI · {data.stories_checked ?? 0} stories checked · {articles.length} readable stories kept</p>}
          <div className="mb-5 flex items-center justify-between"><div className="flex items-center gap-2.5"><h2 className="text-sm font-semibold">Your next story</h2><Badge variant="secondary" className="rounded-md text-[10px]">{articles.length} stories</Badge></div><span className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><ArrowDown className="size-3" />AI importance first</span></div>
          {loading && !data ? <div className="grid gap-5 md:grid-cols-2">{[0,1,2,3].map(i => <Card key={i} className="p-7 shadow-none"><Skeleton className="mb-6 h-8 w-36" /><Skeleton className="mb-3 h-5 w-full" /><Skeleton className="mb-6 h-5 w-4/5" /><Skeleton className="mb-2 h-3 w-full" /><Skeleton className="mb-8 h-3 w-3/4" /><Skeleton className="h-9 w-full" /></Card>)}</div>
            : !articles.length ? <Card className="flex min-h-[340px] flex-col items-center justify-center border-dashed bg-white/60 px-6 py-14 text-center shadow-none"><div className="mb-5 flex size-14 items-center justify-center rounded-2xl border border-primary/10 bg-secondary"><Rss className="size-6 text-primary" /></div><h3 className="text-xl font-semibold tracking-tight">{data ? "A quiet moment in the newsroom." : "Good stories start here."}</h3><p className="mt-3 max-w-sm text-xs leading-6 text-muted-foreground">{data ? "No AI-relevant stories with readable article text qualified. Try collecting again later." : "Bring the latest AI reporting into one place. Pick a story, then turn it into a post for X or LinkedIn."}</p><Button className="mt-6 gap-2 text-xs" variant="outline" onClick={collect} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}{loading ? "Collecting…" : data ? "Try collecting again" : "Collect your first stories"}</Button><p className="mt-5 flex items-center gap-1.5 text-[10px] text-muted-foreground"><Check className="size-3" />No API keys needed</p></Card>
            : <div className="grid items-stretch gap-5 md:grid-cols-2">{articles.map((article, index) => <Card key={article.id} role="article" aria-labelledby={`story-${article.id}`} className="news-card flex flex-col rounded-xl bg-white shadow-none">
              <CardContent className="flex flex-1 flex-col p-6 pb-5 sm:p-7 sm:pb-5">
                <div className="mb-5 flex items-center justify-between gap-3"><div className="flex min-w-0 items-center gap-2.5"><span className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-background text-[10px] font-bold text-primary">{article.source.slice(0, 2).toUpperCase()}</span><span className="truncate text-[11px] font-semibold text-foreground/75">{article.source}</span></div><span className="font-mono text-[10px] text-muted-foreground/65">{String(index + 1).padStart(2, "0")}</span></div>
                <h3 id={`story-${article.id}`} className="text-[23px] font-semibold leading-[1.45] tracking-[-0.55px] [overflow-wrap:anywhere]">{article.title}</h3>
                <p className="mb-5 mt-3 line-clamp-3 text-xs leading-[1.9] text-muted-foreground [overflow-wrap:anywhere]">{article.description || "No description available. Read the original for the full story."}</p>
                <a href={article.url} target="_blank" rel="noopener noreferrer" className="mb-5 flex items-start gap-2 rounded-lg border bg-background px-3 py-2.5 text-[11px] leading-5 text-muted-foreground hover:text-primary"><Link2 className="mt-1 size-3 shrink-0" /><span className="min-w-0 break-all">{article.url}</span><ArrowUpRight className="mt-1 size-3 shrink-0" /></a>
                <p className="mb-3 text-[10px] text-muted-foreground">{article.content_word_count ?? 0} words loaded{article.content_is_excerpt ? " · Public excerpt; may be incomplete" : " · Article text available"}</p>
                <div className="mt-auto flex items-center gap-1.5 text-[10px] text-muted-foreground"><Clock3 className="size-3" />{article.published_at ? <time dateTime={article.published_at}>{formatDate(article.published_at)}</time> : "Date unavailable"}</div>
              </CardContent>
              <EvidenceCheck key={`${article.id}:${data?.collected_at}`} article={article} />
              <CardFooter className="justify-between gap-2 border-t bg-[#fdfdfe] px-6 py-4 sm:px-7">{isHttpUrl(article.url) && <Button asChild variant="ghost" size="sm" className="-ml-3 text-[11px] text-muted-foreground"><a href={article.url} target="_blank" rel="noopener noreferrer">Read original<ArrowUpRight /></a></Button>}<Button asChild className="h-10 rounded-xl px-4 text-xs shadow-sm"><Link href={`/create/${encodeURIComponent(article.id)}`} onClick={() => saveWorkspace(`verinews:story:${article.id}`, article)}><FilePenLine className="size-4" />Create post<ArrowRight className="size-4" /></Link></Button></CardFooter>
            </Card>)}</div>}
        </section>
        <Separator className="mt-10" />
        <footer className="flex flex-col justify-between gap-3 py-6 text-[10px] text-muted-foreground sm:flex-row"><span>VeriNews <span className="mx-2 opacity-40">/</span> Curiosity, collected.</span><p>News discovery · AI drafts · Always review before sharing.</p></footer>
      </main>
    </div>
  </div>;
}
