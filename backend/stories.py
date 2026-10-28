"""Deterministic title grouping; a coverage estimate, not fact verification."""
import re
import unicodedata

from schemas import Article, Coverage

STOPWORDS = frozenset("a an the and or of for to in on at by with from its is are as new ai artificial intelligence".split())
# Opposite outcomes should not be merged just because the entities match.
OUTCOMES = frozenset("not denies denied cancels cancelled delays delayed launches launched releases released".split())


def title_tokens(title: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", title).casefold())) - STOPWORDS


def same_story(left: str, right: str) -> bool:
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    if {t for t in a if any(c.isdigit() for c in t)} != {t for t in b if any(c.isdigit() for c in t)}:
        return False
    if (a & OUTCOMES) != (b & OUTCOMES):
        return False
    return len(a & b) / len(a | b) >= 0.65


def rank_stories(articles: list[Article], limit: int = 10) -> list[Article]:
    # Stable newest-first input chooses a representative and breaks ranking ties.
    ordered = sorted(articles, key=lambda article: article.url)
    ordered.sort(key=lambda article: article.published_at or "", reverse=True)
    groups: list[list[Article]] = []
    for article in ordered:
        for group in groups:
            # Compare with the representative, not a transitive chain of headlines.
            if same_story(article.title, group[0].title):
                group.append(article)
                break
        else:
            groups.append([article])
    stories = []
    for group in groups:
        publishers = {}
        for article in group:
            publishers.setdefault(article.source_id, article)
        coverage = [Coverage(title=a.title, url=a.url, source_id=a.source_id,
                             source=a.source, published_at=a.published_at)
                    for a in publishers.values()]
        stories.append(group[0].model_copy(update={"publisher_count": sum(item.source_id != "google-news-unattributed" for item in coverage), "coverage": coverage}))
    # Python's stable sort preserves freshness and deterministic URL ties.
    stories.sort(key=lambda article: article.publisher_count, reverse=True)
    return stories[:limit]
