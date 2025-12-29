from datetime import datetime

from devwrapped.metrics.engine import MetricsEngine
from devwrapped.model.events import Event, EventType


def test_metrics_engine_basic():
    events = [
        Event(
            type=EventType.COMMIT,
            actor="a",
            repo="repo1",
            timestamp=datetime(2024, 6, 1, 10),
            metadata={},
        ),
        Event(
            type=EventType.COMMIT,
            actor="a",
            repo="repo1",
            timestamp=datetime(2024, 6, 1, 11),
            metadata={},
        ),
        Event(
            type=EventType.COMMIT,
            actor="a",
            repo="repo2",
            timestamp=datetime(2024, 6, 2, 23),
            metadata={},
        ),
    ]

    engine = MetricsEngine(events)
    metrics = engine.compute()

    assert metrics["total_commits"] == 3
    assert metrics["active_days"] == 2
    assert metrics["busiest_day"] == "2024-06-01"
    assert metrics["most_active_hour"] in (10, 11)
    assert metrics["top_repos"]["repo1"] == 2
