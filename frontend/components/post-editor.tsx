"use client";

import { useId, useRef, useState } from "react";
import { ArrowUpRight, Check, Copy, Link2, Loader2, RefreshCw, Sparkles } from "lucide-react";
import twitterText from "twitter-text";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { extractArticle, generatePost, isHttpUrl, type Article, type ExtractedArticle, type PostPlatform } from "@/lib/news";
import { cn } from "@/lib/utils";

type Draft = { body: string; sourceUrl: string; includeLink: boolean };

export function PostEditor({ article }: { article: Article }) {
  const [platform, setPlatform] = useState<PostPlatform>("x");
  const [drafts, setDrafts] = useState<Partial<Record<PostPlatform, Draft>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [context, setContext] = useState<ExtractedArticle | null>(() => article.content ? { url: article.url, source: article.source, text: article.content, word_count: article.content_word_count ?? article.content.split(/\s+/).length, truncated: article.content_is_excerpt ?? false, access_note: article.content_note ?? "" } : null);
  const [reading, setReading] = useState(false);
  const [readError, setReadError] = useState("");
  const readingRef = useRef(false);
  const pending = useRef(false);
  const editorId = useId();
  const draft = drafts[platform];
  const label = platform === "x" ? "X" : "LinkedIn";
  const text = draft ? draft.body + (draft.includeLink ? `\n\n${draft.sourceUrl}` : "") : "";
  const count = platform === "x" ? twitterText.parseTweet(text).weightedLength : text.length;
  const limit = platform === "x" ? 280 : 3000;
  const valid = !!draft?.body.trim() && (platform === "x" ? twitterText.parseTweet(text).valid : count <= limit);

  function updateDraft(update: Partial<Draft>) {
    setDrafts(current => ({ ...current, [platform]: { body: "", sourceUrl: context?.url ?? article.url, includeLink: true, ...current[platform], ...update } }));
    setMessage("");
  }

  async function readArticle() {
    if (readingRef.current) return;
    readingRef.current = true;
    setReading(true); setReadError("");
    try { setContext(await extractArticle(article)); }
    catch (err) { setReadError(err instanceof Error ? err.message : "Could not read the full article."); }
    finally { setReading(false); readingRef.current = false; }
  }

  async function generate() {
    if (pending.current || !context) return;
    pending.current = true;
    setLoading(true); setError(""); setMessage("");
    try {
      const result = await generatePost({ ...article, url: context.url, source: context.source || article.source }, platform);
      setDrafts(current => ({ ...current, [platform]: { body: result.body, sourceUrl: result.source_url, includeLink: current[platform]?.includeLink ?? true } }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a draft. Try again.");
    } finally { pending.current = false; setLoading(false); }
  }

  async function copy() {
    if (!valid) return;
    try { await navigator.clipboard.writeText(text); setMessage("Post copied to clipboard."); }
    catch { setMessage("Clipboard unavailable. Copy the text manually; include the source link if selected."); }
  }

  return <section aria-label="Post editor" className="overflow-hidden rounded-2xl border bg-white shadow-sm">
      <div className="border-b px-6 py-6 text-left sm:px-8">
        <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-primary"><Sparkles className="size-3.5" />Your writing studio</div>
        <h1 className="text-3xl font-semibold tracking-tight">Make this story your own.</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">Choose a platform, generate a draft, then add your perspective.</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6 sm:px-8">
        <div className="mb-7 rounded-xl border bg-background p-4">
          <p className="mb-2 flex items-center gap-2 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground"><span className="size-1 rounded-full bg-primary" />The source story</p>
          <p className="text-sm font-semibold leading-relaxed tracking-tight">{article.title}</p>
          <a href={isHttpUrl(context?.url ?? article.url) ? context?.url ?? article.url : undefined} target="_blank" rel="noopener noreferrer" className="mt-3 flex items-start gap-2 text-xs leading-5 text-primary"><span className="break-all">{context?.url || article.url}</span><ArrowUpRight className="mt-1 size-3 shrink-0" /></a>
        </div>

        <div className="mb-6">
          {!context && !reading && !readError && <Button variant="outline" onClick={() => void readArticle()}>Load article text</Button>}
          {reading && <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" />Resolving publisher links and trying available coverage…</p>}
          {readError && <Alert variant="destructive"><AlertDescription>{readError}<Button onClick={() => void readArticle()} size="sm" variant="outline" className="mt-3">Retry available sources</Button></AlertDescription></Alert>}
          {context && <div className="rounded-lg border bg-background/60 p-3"><p className="flex items-center gap-2 text-xs text-primary"><Check className="size-3.5" />Article text loaded · {context.word_count.toLocaleString()} words{context.truncated ? " (excerpt)" : ""}</p>{context.access_note && <p className="mt-2 text-xs leading-5 text-amber-700">{context.access_note}</p>}<details className="mt-2 text-xs"><summary className="cursor-pointer text-muted-foreground">Review extracted article text</summary><p className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{context.text}</p></details></div>}
        </div>

        <Tabs value={platform} onValueChange={value => { setPlatform(value as PostPlatform); setError(""); setMessage(""); }}>
          <div className="mb-3 flex items-center justify-between"><p className="text-xs font-semibold">Choose your platform</p><Badge variant="outline" className="text-[9px] font-normal">AI assisted</Badge></div>
          <TabsList className="grid h-12 w-full grid-cols-2 rounded-lg p-1" aria-label="Post platform">
            <TabsTrigger value="x" disabled={loading} className="h-10 gap-2 text-xs"><span className="text-base">𝕏</span> X <span className="ml-1 hidden text-[10px] font-normal text-muted-foreground min-[400px]:inline">Short &amp; sharp</span></TabsTrigger>
            <TabsTrigger value="linkedin" disabled={loading} className="h-10 gap-2 text-xs"><span aria-hidden="true" className="flex size-4 items-center justify-center rounded-sm bg-current text-[9px]"><span className="text-white">in</span></span>LinkedIn<span className="ml-1 hidden text-[10px] font-normal text-muted-foreground min-[400px]:inline">More room</span></TabsTrigger>
          </TabsList>
          <TabsContent value={platform} className="mt-6">
            <div className="mb-6">        <div className="flex gap-3"><Button disabled={loading || reading || !context} onClick={generate} variant={draft ? "outline" : "default"} className="h-11 flex-1 rounded-lg text-xs">{loading ? <Loader2 className="animate-spin" /> : draft ? <RefreshCw /> : <Sparkles />}{loading ? "Writing your draft…" : draft ? "Regenerate" : `Generate ${label} post`}</Button>{draft && <Button disabled={loading || !valid} onClick={copy} className="h-11 flex-1 rounded-lg text-xs"><Copy />Copy post</Button>}</div></div>
            <div className="mb-3 flex items-center justify-between"><label htmlFor={editorId} className="text-xs font-semibold">{label} draft</label><span className={cn("font-mono text-[10px] text-muted-foreground", draft && !valid && "text-destructive")} aria-live="polite">{count.toLocaleString()}/{limit.toLocaleString()}</span></div>
            <Textarea id={editorId} value={draft?.body ?? ""} disabled={loading} onChange={event => updateDraft({ body: event.target.value })} rows={platform === "x" ? 10 : 16} placeholder={`Generate a ${label} post from this article, or write your own draft here…`} aria-describedby={`${editorId}-help`} className="editor-textarea min-h-72 resize-y rounded-xl border-border bg-white p-5 text-sm leading-7 shadow-none focus-visible:ring-primary/30" />
            {draft && !valid && <p className="mt-3 text-xs text-destructive">Edit the draft to fit {label} before copying.</p>}
            {draft && <div className="mt-4 flex items-center justify-between rounded-xl border px-4 py-3"><div className="flex items-center gap-3"><span className="flex size-8 items-center justify-center rounded-lg bg-background text-muted-foreground"><Link2 className="size-4" /></span><div><label htmlFor={`${editorId}-link`} className="block text-xs font-medium">Include source link</label><p className="mt-1 text-[10px] text-muted-foreground">Added when you copy the post</p></div></div><Switch id={`${editorId}-link`} checked={draft.includeLink} disabled={loading} onCheckedChange={checked => updateDraft({ includeLink: checked })} /></div>}
          </TabsContent>
        </Tabs>
        {error && <Alert variant="destructive" className="mt-5 text-xs"><AlertDescription>{error} {draft && "Your previous draft is preserved."}</AlertDescription></Alert>}
        <p className="mt-4 text-xs leading-6 text-muted-foreground" role="status">{loading ? <span className="flex items-center gap-2"><Loader2 className="size-3.5 animate-spin" />Writing with local Ollama. This may take a few minutes.</span> : message && <span className="flex items-start gap-2"><Check className="mt-1 size-3.5 shrink-0 text-primary" />{message}</span>}</p>
        <p id={`${editorId}-help`} className="mt-5 text-[10px] leading-5 text-muted-foreground">Generated only after article text is available. Extraction is not fact-checking. Review the source and draft before sharing.</p>
      </div>

      <div className="border-t bg-background/40 px-6 py-5 sm:px-8">

        <p className="mt-3 text-center text-[9px] text-muted-foreground">Only a draft. Nothing is posted automatically.</p>
      </div>
    </section>;
}
