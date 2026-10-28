"use client";

import { useRef, useState } from "react";
import twitterText from "twitter-text";
import { generateXPost, type Article } from "@/lib/news";

export function XPostDraft({ article }: { article: Article }) {
  const [draft, setDraft] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const pending = useRef(false);
  const parsed = draft === null ? null : twitterText.parseTweet(draft);

  async function generate() {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError("");
    setCopyMessage("");
    try {
      const result = await generateXPost(article);
      setDraft(result.draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a draft. Try again.");
    } finally {
      pending.current = false;
      setLoading(false);
    }
  }

  async function copy() {
    if (!draft || !parsed?.valid) return;
    try {
      await navigator.clipboard.writeText(draft);
      setCopyMessage("Copied.");
    } catch {
      setCopyMessage("Could not access clipboard. Select the draft and copy it manually.");
    }
  }

  return <section className="post-draft" aria-label={`X post draft for ${article.title}`}>
    <button className="generate-post" disabled={loading} onClick={generate}>
      {loading ? "Generating X post…" : draft === null ? "Generate X post" : "Regenerate X post"}
    </button>
    <p className="draft-status" role="status">{loading ? "Writing with local Ollama. This may take a few minutes." : copyMessage}</p>
    {error && <p className="draft-error" role="alert">{error} {draft !== null && "Your previous draft is preserved."}</p>}
    {draft !== null && <div className="draft-editor">
      <label htmlFor={`draft-${article.id}`}>Edit your X draft</label>
      <textarea id={`draft-${article.id}`} value={draft} rows={7} disabled={loading}
        onChange={event => { setDraft(event.target.value); setCopyMessage(""); }}
        aria-describedby={`draft-help-${article.id} draft-count-${article.id}`} />
      <p id={`draft-count-${article.id}`} className={parsed?.valid ? "draft-count" : "draft-error"} aria-live="polite">
        {parsed?.weightedLength ?? 0}/280 characters{parsed && !parsed.valid ? " · Edit before copying" : ""}
      </p>
      <p id={`draft-help-${article.id}`} className="draft-help">AI draft based on RSS text, not the full article. Check claims and source attribution before posting. Links use X’s character-counting rules.</p>
      <button disabled={loading || !parsed?.valid} onClick={copy}>Copy post</button>
    </div>}
  </section>;
}
