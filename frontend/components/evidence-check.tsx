"use client";

import { useRef, useState } from "react";
import { ArrowUpRight, Loader2, ShieldQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import { checkEvidence, type Article, type EvidenceResult } from "@/lib/news";

const labels = { supported: "Supported by retrieved evidence", conflicting_evidence: "Conflicting evidence", insufficient_evidence: "Insufficient evidence" };
export function EvidenceCheck({ article }: { article: Article }) {
  const [result, setResult] = useState<EvidenceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  async function check() {
    if (pending.current) return;
    pending.current = true; setLoading(true); setError("");
    try { setResult(await checkEvidence(article)); }
    catch (err) { setError(err instanceof Error && !["TypeError", "TimeoutError"].includes(err.name) ? err.message : "Evidence check could not finish. Check the backend and Ollama, then retry."); }
    finally { pending.current = false; setLoading(false); }
  }
  return <div className="border-t px-6 py-4 sm:px-7">
    <Button variant="outline" size="sm" onClick={check} disabled={loading} className="text-xs">{loading ? <Loader2 className="animate-spin" /> : <ShieldQuestion />}{loading ? "Checking evidence…" : result ? "Check evidence again" : "Check evidence"}</Button>
    {loading && <p role="status" className="mt-3 text-xs leading-5 text-muted-foreground">Searching sources, reading articles and comparing the headline claim. This may take a few minutes.</p>}
    {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
    {result && <div className="mt-4 space-y-3 text-xs" aria-live="polite"><p className={`font-semibold ${result.status === "supported" ? "text-emerald-700" : result.status === "conflicting_evidence" ? "text-amber-700" : "text-muted-foreground"}`}>{labels[result.status]}</p><p className="leading-5"><strong>Checked claim:</strong> {result.claim}</p><p className="text-[10px] text-muted-foreground">Checked {new Date(result.checked_at).toLocaleString()}</p><details><summary className="cursor-pointer font-medium">Review sources and evidence ({result.sources.length})</summary><div className="mt-3 space-y-4">{result.sources.map(source => <div key={source.url} className="rounded-lg border bg-background p-3"><p className="mb-2 font-semibold capitalize">{source.relationship}</p><a href={source.url} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 break-all text-primary">{source.title}<ArrowUpRight className="size-3 shrink-0" /></a><p className="mt-1 break-all text-[10px] text-muted-foreground">{source.url}</p>{source.passage && <blockquote className="my-3 border-l-2 border-primary/30 pl-3 leading-6">“{source.passage}”</blockquote>}<p className="leading-5 text-muted-foreground">{source.explanation}</p></div>)}{result.notes.map((note, i) => <p key={i} className="leading-5 text-muted-foreground">{note}</p>)}</div></details></div>}
  </div>;
}
