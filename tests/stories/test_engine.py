from devwrapped.stories.engine import StoryEngine


def test_story_generation():
    metrics = {
        "total_commits": 42,
        "most_active_hour": 23,
        "commits_per_month": {"10": 20, "09": 10},
        "top_repos": {"repo1": 30},
    }

    stories = StoryEngine(metrics).generate()

    assert len(stories) >= 3
    assert any("late at night" in s["text"] for s in stories)
    assert any("repo1" in s["text"] for s in stories)
