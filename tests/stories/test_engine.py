from devwrapped.stories.engine import StoryEngine


def test_story_generation_basic():
    metrics = {
        "total_commits": 120,
        "most_active_hour": 23,
        "commits_per_month": {"10": 20, "09": 10},
        "top_repos": {"repo1": 30},
        "longest_streak": 14,
        "dominant_weekday": "Tue",
        "weekend_ratio": 0.2,
        "total_pull_requests": 4,
        "merged_pull_requests": 3,
        "languages": {"Python": 1000, "Go": 500},
    }
    stories = StoryEngine(metrics).generate()
    assert any(s["id"] == "commit_volume" for s in stories)
    assert any(s["id"] == "time_of_day" and "late at night" in s["text"] for s in stories)
    assert any(s["id"] == "peak_month" for s in stories)
    assert any(s["id"] == "repo_focus" and "repo1" in s["text"] for s in stories)
    assert any(s["id"] == "longest_streak" for s in stories)
    assert any(s["id"] == "dominant_weekday" for s in stories)
    assert any(s["id"] == "pull_requests" and "75%" in s["text"] for s in stories)
    assert any(s["id"] == "languages" for s in stories)


def test_weekend_warrior_wins_over_dominant_weekday():
    metrics = {
        "total_commits": 50,
        "most_active_hour": 14,
        "commits_per_month": {"06": 50},
        "top_repos": {"repo": 50},
        "dominant_weekday": "Sat",
        "weekend_ratio": 0.6,
    }
    ids = {s["id"] for s in StoryEngine(metrics).generate()}
    assert "weekend_warrior" in ids
    assert "dominant_weekday" not in ids


def test_no_stories_for_empty_metrics():
    assert StoryEngine({"total_commits": 0}).generate() == []
