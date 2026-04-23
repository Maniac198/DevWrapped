from datetime import datetime, timezone

from devwrapped.metrics.engine import MetricsEngine
from devwrapped.model.events import Event, EventType


def _commit(year, month, day, hour=10, repo="repo1"):
    return Event(
        type=EventType.COMMIT,
        actor="a",
        repo=repo,
        timestamp=datetime(year, month, day, hour, tzinfo=timezone.utc),
        metadata={},
    )


def test_metrics_engine_basic():
    events = [
        _commit(2024, 6, 1, 10),
        _commit(2024, 6, 1, 11),
        _commit(2024, 6, 2, 23, repo="repo2"),
    ]
    metrics = MetricsEngine(events).compute()

    assert metrics["total_commits"] == 3
    assert metrics["active_days"] == 2
    assert metrics["busiest_day"] == "2024-06-01"
    assert metrics["busiest_day_count"] == 2
    assert metrics["most_active_hour"] in (10, 11)
    assert metrics["top_repos"]["repo1"] == 2
    assert metrics["repo_count"] == 2
    assert metrics["commits_per_active_day"] == 1.5
    assert metrics["commits_per_month"]["06"] == 3
    # Ensure months are zero-padded and include all 12.
    assert set(metrics["commits_per_month"].keys()) == {f"{m:02d}" for m in range(1, 13)}


def test_streaks():
    events = [
        _commit(2024, 1, 1),
        _commit(2024, 1, 2),
        _commit(2024, 1, 3),
        _commit(2024, 1, 10),
        _commit(2024, 1, 11),
    ]
    metrics = MetricsEngine(events).compute()
    assert metrics["longest_streak"] == 3
    assert metrics["current_streak"] == 2


def test_weekday_distribution_and_weekend_ratio():
    # 2024-06-01 is Saturday, 2024-06-02 is Sunday, 2024-06-03 Monday.
    events = [_commit(2024, 6, 1), _commit(2024, 6, 2), _commit(2024, 6, 3)]
    metrics = MetricsEngine(events).compute()
    assert metrics["weekday_distribution"]["Sat"] == 1
    assert metrics["weekday_distribution"]["Sun"] == 1
    assert metrics["weekday_distribution"]["Mon"] == 1
    assert metrics["weekend_ratio"] == round(2 / 3, 3)


def test_languages_are_sorted_and_limited():
    events = [_commit(2024, 6, 1)]
    languages = {"Python": 1000, "Go": 500, "Rust": 100, "C": 10, "Zig": 1, "Lua": 2}
    metrics = MetricsEngine(events, languages=languages).compute()
    assert list(metrics["languages"].keys())[:2] == ["Python", "Go"]
    assert len(metrics["languages"]) == 5


def test_empty_events():
    metrics = MetricsEngine([]).compute()
    assert metrics["total_commits"] == 0
    assert metrics["longest_streak"] == 0
    assert metrics["busiest_day"] is None


def test_pull_request_metrics():
    events = [
        _commit(2024, 1, 1),
        Event(
            type=EventType.PULL_REQUEST,
            actor="a",
            repo="repo1",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            metadata={"merged": True},
        ),
        Event(
            type=EventType.PULL_REQUEST,
            actor="a",
            repo="repo1",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
            metadata={"merged": False},
        ),
    ]
    metrics = MetricsEngine(events).compute()
    assert metrics["total_pull_requests"] == 2
    assert metrics["merged_pull_requests"] == 1
