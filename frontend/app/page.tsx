"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUpRight, Check, ChevronRight, Clock3, Globe2, Layers3, Loader2, Newspaper, RefreshCw, Rss, Sparkles, TriangleAlert } from "lucide-react";
import { PostComposer } from "@/components/post-composer";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
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
    try { setData(await collectNews()); }
    catch (err) {
      setError(err instanceof Error && !["TimeoutError", "TypeError"].includes(err.name)
        ? err.message : "Could not reach the news service. Check that the backend is running and try again.");
    } finally { pending.current = false; setLoading(false); }
  }

  const articles = (data?.articles ?? []).map(normalizeArticle);

  return <div className="min-h-screen font-sans">
    <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r bg-white lg:flex">
      <Link href="/" className="flex h-24 items-center gap-2.5 px-7" aria-label="VeriNews home">
        <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-white"><Layers3 className="size-5" /></span>
        <span className="text-xl font-bold tracking-tight">VeriNews<span className="text-primary">.</span></span>
      </Link>
      <div className="px-4 pt-6">
        <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.16em] text-muted-foreground">WORKSPACE</p>
        <a href="#newsroom" aria-current="page" className="flex items-center gap-3 rounded-lg bg-secondary px-3 py-3 text-[13px] font-semibold text-primary"><Newspaper className="size-4" />Newsroom<span className="ml-auto flex size-5 items-center justify-center rounded bg-white/75 text-[10px]">{articles.length}</span></a>
      </div>
      <div className="mt-10 px-7">
        <p className="text-[10px] font-semibold tracking-[0.16em] text-muted-foreground">FROM SIGNAL TO STORY</p>
        <ol className="mt-5 space-y-5 text-xs text-muted-foreground">
          {["Collect the latest news", "Find a story worth sharing", "Make the draft your own"].map((step, i) => <li className="flex items-center gap-3" key={step}><span className="flex size-5 shrink-0 items-center justify-center rounded-full border text-[9px]">{i + 1}</span>{step}</li>)}
        </ol>
      </div>
      <div className="mt-auto p-5">
        <div className="rounded-xl border bg-background p-4"><Sparkles className="mb-3 size-4 text-primary" /><p className="text-xs font-semibold">Your perspective matters.</p><p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">Start with the news. Finish with a post that sounds like you.</p></div>
        <div className="mt-5 flex items-center gap-2 px-2 text-[10px] text-muted-foreground"><span className="size-1.5 rounded-full bg-primary/60" />Your local workspace</div>
      </div>
    </aside>

    <div className="lg:pl-60">
      <header className="flex h-[76px] items-center justify-between border-b bg-white px-5 sm:px-9 xl:px-12">
        <div className="flex items-center gap-2 text-xs"><Link href="/" className="font-bold lg:hidden">VeriNews<span className="text-primary">.</span></Link><span className="hidden text-muted-foreground sm:inline">Workspace</span><ChevronRight className="size-3 text-muted-foreground" /><span className="font-medium">Newsroom</span></div>
        <Badge variant="outline" className="gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-normal text-muted-foreground"><Globe2 className="size-3" />US &amp; India <span className="mx-1 text-border">|</span> English</Badge>
      </header>

      <main id="newsroom" className="mx-auto max-w-[1360px] px-5 pb-8 pt-10 sm:px-9 sm:pt-12 xl:px-12">
        <section className="flex flex-col justify-between gap-6 pb-9 md:flex-row md:items-end" aria-labelledby="page-title">
          <div><div className="mb-4 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary"><span className="size-1.5 rounded-full bg-primary" />A little signal. Less noise.</div><h1 id="page-title" className="text-3xl font-semibold tracking-[-1.4px] sm:text-[38px]">Your AI news, curated<span className="text-primary">.</span></h1><p className="mt-3 max-w-xl text-[13px] leading-6 text-muted-foreground">The most covered stories of the last 24 hours.<br className="hidden sm:block" /> Find your next read. Create something worth sharing.</p></div>
          <div className="shrink-0 md:text-right"><Button onClick={collect} disabled={loading} className="h-11 rounded-lg px-5 text-xs shadow-sm">{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />} {loading ? "Collecting…" : "Collect latest news"}</Button><p className="mt-3 text-[10px] text-muted-foreground">{data ? <>Last collected <time dateTime={data.collected_at}>{formatDate(data.collected_at)}</time></> : "Fresh news, whenever you’re ready."}</p></div>
        </section>

        <div className="mb-9 grid grid-cols-3 overflow-hidden rounded-xl border bg-white">
          {[{icon: Newspaper, value: String(articles.length).padStart(2, "0"), label: "Stories collected"}, {icon: Clock3, value: "24h", label: "News window"}, {icon: Globe2, value: "US + IN", label: "Regional coverage"}].map(({icon: Icon, value, label}) => <div key={label} className="flex items-center gap-3 border-r p-4 last:border-0 sm:px-6 sm:py-5"><span className="hidden size-9 items-center justify-center rounded-lg bg-background text-muted-foreground sm:flex"><Icon className="size-4" /></span><div><p className="text-base font-semibold tracking-tight sm:text-lg">{value}</p><p className="mt-1 text-[9px] text-muted-foreground sm:text-[11px]">{label}</p></div></div>)}
        </div>

        <div role="status" className="sr-only">{loading ? "Collecting RSS news." : data ? `${articles.length} stories collected.` : "Ready to collect news."}</div>
        {error && <Alert variant="destructive" className="mb-6 bg-white"><TriangleAlert className="size-4" /><AlertTitle>Couldn’t collect news</AlertTitle><AlertDescription>{error} {data && "Your previous collection is still here."}<Button onClick={collect} disabled={loading} size="sm" variant="outline" className="ml-3 mt-2">Try again</Button></AlertDescription></Alert>}
        {!!data?.warnings.length && <Alert className="mb-6 border-amber-200 bg-amber-50"><TriangleAlert className="size-4" /><AlertTitle>Some sources are unavailable</AlertTitle><AlertDescription>{data.warnings.map(w => <p key={w.source_id}>{w.message}</p>)}</AlertDescription></Alert>}

        <section aria-label="News stories" aria-busy={loading}>
          <div className="mb-5 flex items-center justify-between"><div className="flex items-center gap-2.5"><h2 className="text-sm font-semibold">The reading room</h2><Badge variant="secondary" className="rounded-md text-[10px]">{articles.length} stories</Badge></div><span className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><ArrowDown className="size-3" />Most covered first</span></div>
          {loading && !data ? <div className="grid gap-5 xl:grid-cols-2">{[0,1,2,3].map(i => <Card key={i} className="p-7 shadow-none"><Skeleton className="mb-6 h-8 w-36" /><Skeleton className="mb-3 h-5 w-full" /><Skeleton className="mb-6 h-5 w-4/5" /><Skeleton className="mb-2 h-3 w-full" /><Skeleton className="mb-8 h-3 w-3/4" /><Skeleton className="h-9 w-full" /></Card>)}</div>
            : !articles.length ? <Card className="flex min-h-[340px] flex-col items-center justify-center border-dashed bg-white/60 px-6 py-14 text-center shadow-none"><div className="mb-5 flex size-14 items-center justify-center rounded-2xl border border-primary/10 bg-secondary"><Rss className="size-6 text-primary" /></div><h3 className="text-xl font-semibold tracking-tight">{data ? "A quiet moment in the newsroom." : "Good stories start here."}</h3><p className="mt-3 max-w-sm text-xs leading-6 text-muted-foreground">{data ? "No dated stories from the last 24 hours were found. Collect again in a little while." : "Bring the latest AI reporting into one place. Pick a story, then turn it into a post for X or LinkedIn."}</p><Button className="mt-6 gap-2 text-xs" variant="outline" onClick={collect} disabled={loading}>{loading ? <Loader2 className="animate-spin" /> : <RefreshCw />}{loading ? "Collecting…" : data ? "Try collecting again" : "Collect your first stories"}</Button><p className="mt-5 flex items-center gap-1.5 text-[10px] text-muted-foreground"><Check className="size-3" />No API keys needed</p></Card>
            : <div className="grid items-stretch gap-5 xl:grid-cols-2">{articles.map((article, index) => <Card key={article.id} role="article" aria-labelledby={`story-${article.id}`} className="news-card flex flex-col rounded-xl bg-white shadow-none">
              <CardContent className="flex flex-1 flex-col p-6 pb-5 sm:p-7 sm:pb-5">
                <div className="mb-5 flex items-center justify-between gap-3"><div className="flex min-w-0 items-center gap-2.5"><span className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-background text-[10px] font-bold text-primary">{article.source.slice(0, 2).toUpperCase()}</span><span className="truncate text-[11px] font-semibold text-foreground/75">{article.source}</span></div><span className="font-mono text-[10px] text-muted-foreground/65">{String(index + 1).padStart(2, "0")}</span></div>
                <h3 id={`story-${article.id}`} className="text-[20px] font-semibold leading-[1.45] tracking-[-0.55px] [overflow-wrap:anywhere]">{article.title}</h3>
                <p className="mb-5 mt-3 line-clamp-3 text-xs leading-[1.9] text-muted-foreground [overflow-wrap:anywhere]">{article.description || "No description available. Read the original for the full story."}</p>
                <div className="mt-auto flex items-center gap-1.5 text-[10px] text-muted-foreground"><Clock3 className="size-3" />{article.published_at ? <time dateTime={article.published_at}>{formatDate(article.published_at)}</time> : "Date unavailable"}</div>
              </CardContent>
              <CardFooter className="justify-between gap-2 border-t bg-[#fdfdfe] px-6 py-4 sm:px-7">{/^https?:\/\//i.test(article.url) && <Button asChild variant="ghost" size="sm" className="-ml-3 text-[11px] text-muted-foreground"><a href={article.url} target="_blank" rel="noopener noreferrer">Read original<ArrowUpRight /></a></Button>}<PostComposer key={`${article.id}:${data?.collected_at}`} article={article} /></CardFooter>
            </Card>)}</div>}
        </section>
        <Separator className="mt-10" />
        <footer className="flex flex-col justify-between gap-3 py-6 text-[10px] text-muted-foreground sm:flex-row"><span>VeriNews <span className="mx-2 opacity-40">/</span> Curiosity, collected.</span><p>RSS reporting · AI drafts · Always review before sharing.</p></footer>
      </main>
    </div>
  </div>;
}
