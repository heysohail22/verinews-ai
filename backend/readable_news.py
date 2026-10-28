"""Show only ranked stories with readable publisher text, within a bounded budget."""
import asyncio
import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException

from articles import extract_story, remember_article
from schemas import ArticleCandidate, ArticleRequest, NewsResponse, Source

CHECK_TIMEOUT = 15
COLLECTION_TIMEOUT = 60


async def retain_readable_stories(response: NewsResponse, progress=None) -> NewsResponse:
    if not response.articles:
        return response
    readable = []
    contexts = []
    checked = 0

    async def check(story):
        try:
            async with asyncio.timeout(CHECK_TIMEOUT):
                context = await extract_story(ArticleRequest(
                    url=story.url, expected_title=story.title, source=story.source,
                    alternatives=[ArticleCandidate(url=item.url, source=item.source)
                                  for item in story.coverage if item.url != story.url][:9],
                ))
            if not context.text.strip() or context.word_count < 60:
                return None
            publisher = next((item for item in story.coverage if item.source == context.source), None)
            compact = " ".join(context.text.split())
            description = compact if len(compact) <= 420 else compact[:420].rsplit(" ", 1)[0] + "…"
            article = story.model_copy(update={
                "id": hashlib.sha256(context.url.encode()).hexdigest(),
                "url": context.url, "source": context.source or story.source,
                "source_id": publisher.source_id if publisher else story.source_id,
                "published_at": publisher.published_at if publisher else story.published_at,
                "description": description, "content": context.text,
                "content_word_count": context.word_count,
                "content_is_excerpt": context.truncated, "content_note": context.access_note,
            })
            return article, context
        except (HTTPException, TimeoutError):
            return None

    try:
        async with asyncio.timeout(COLLECTION_TIMEOUT):
            # Check three at a time and keep original ranking regardless of speed.
            for offset in range(0, len(response.articles), 3):
                batch = response.articles[offset:offset + 3]
                checked += len(batch)
                results = await asyncio.gather(*(check(story) for story in batch))
                for result in results:
                    if result is not None:
                        article, context = result
                        if article.url not in {item.url for item in readable}:
                            readable.append(article)
                            contexts.append(context)
                    if len(readable) == 10:
                        break
                if progress:
                    await progress({"stage": "reading", "completed": checked, "total": len(response.articles), "message": f"Checked {checked} story groups · {len(readable)} readable stories ready"})
                if len(readable) == 10:
                    break
    except TimeoutError:
        pass
    # Keep selected contexts warm after checking lower-ranked candidates.
    for context in contexts:
        remember_article(context.url, context)
    publishers = {item.source_id: Source(id=item.source_id, name=item.source)
                  for story in readable for item in story.coverage}
    return response.model_copy(update={
        "articles": readable,
        "stories_checked": checked,
        "sources": sorted(publishers.values(), key=lambda source: source.name.casefold()),
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
