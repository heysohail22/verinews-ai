from schemas import Article
from stories import rank_stories, same_story


def article(title, publisher, hour, suffix=""):
    return Article(id=publisher + suffix, title=title,
                   url=f"https://{publisher}.example/{suffix}", source_id=publisher,
                   source=publisher, published_at=f"2026-10-28T{hour:02}:00:00Z", description="")


def test_coverage_beats_freshness_and_counts_distinct_publishers():
    stories = rank_stories([
        article("Acme launches Atlas model for coding tasks", "one", 8),
        article("Acme launches Atlas model for coding tasks today", "two", 9),
        article("Acme launches Atlas model for coding tasks", "one", 10, "duplicate-report"),
        article("Robotics company unveils warehouse robot", "three", 11),
    ])
    assert len(stories) == 2
    assert stories[0].publisher_count == 2
    assert {item.source_id for item in stories[0].coverage} == {"one", "two"}
    assert stories[0].source == "one"
    assert stories[1].publisher_count == 1


def test_ties_use_freshness_and_are_deterministic():
    entries = [article("Robot warehouse", "a", 8), article("New chip", "b", 9)]
    assert rank_stories(entries) == rank_stories(list(reversed(entries)))
    assert rank_stories(entries)[0].source == "b"


def test_different_models_and_outcomes_stay_separate():
    assert not same_story("Acme launches Atlas 2 model for coding", "Acme launches Atlas 3 model for coding")
    assert not same_story("Acme launches Atlas model for coding", "Acme delays Atlas model for coding")
    assert not same_story("Acme funding", "Acme model")
    assert not same_story("AI", "AI")


def test_unknown_publishers_do_not_count_as_identified_publishers():
    story = rank_stories([article("Acme releases Atlas", "google-news-unattributed", 8)])[0]
    assert story.publisher_count == 0


def test_similar_articles_do_not_form_transitive_chains():
    entries = [
        article("alpha beta gamma delta epsilon", "a", 10),
        article("alpha beta gamma delta epsilon zeta eta", "b", 9),
        article("gamma delta epsilon zeta eta", "c", 8),
    ]
    stories = rank_stories(entries)
    assert sorted(story.publisher_count for story in stories) == [1, 2]
