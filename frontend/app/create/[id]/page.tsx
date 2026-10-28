"use client";

import { Suspense, use } from "react";
import Link from "next/link";
import { ArrowLeft, Layers3 } from "lucide-react";
import { PostEditor } from "@/components/post-editor";
import { Button } from "@/components/ui/button";
import { isHttpUrl, normalizeArticle, type Article } from "@/lib/news";
import { useWorkspace } from "@/lib/workspace";

function WritingStudio({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const article = useWorkspace<Article>(`verinews:story:${id}`);
  return <div className="min-h-screen">
    <header className="border-b bg-white"><div className="mx-auto flex h-20 max-w-5xl items-center justify-between px-5 sm:px-8"><Link href="/" className="flex items-center gap-2 text-lg font-bold"><Layers3 className="size-5 text-primary" />VeriNews<span className="text-primary">.</span></Link><span className="text-xs text-muted-foreground">Writing studio</span></div></header>
    <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8 sm:py-12">
      <Button asChild variant="ghost" className="mb-6 -ml-3"><Link href="/"><ArrowLeft />Back to newsroom</Link></Button>
      {article && isHttpUrl(article.url) ? <PostEditor key={article.id} article={normalizeArticle(article)} /> : <section className="rounded-2xl border bg-white p-10 text-center"><h1 className="text-xl font-semibold">Choose a story to start writing</h1><p className="mt-3 text-sm text-muted-foreground">Open a story from your newsroom. Selected stories are kept in this browser tab.</p><Button asChild className="mt-6"><Link href="/">Go to newsroom</Link></Button></section>}
    </main>
  </div>;
}

export default function CreatePost({ params }: { params: Promise<{ id: string }> }) {
  return <Suspense fallback={<main className="mx-auto max-w-4xl p-8" role="status">Opening your writing studio…</main>}><WritingStudio params={params} /></Suspense>;
}
