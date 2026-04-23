from devwrapped.archetypes.engine import ArchetypeEngine, available_archetypes


def _classify(**overrides):
    metrics = {
        "total_commits": 50,
        "active_days": 15,
        "most_active_hour": 14,
        "top_repos": {"repo1": 50},
        "commits_per_month": {"06": 20, "07": 15, "08": 15},
        "weekend_ratio": 0.1,
        "longest_streak": 5,
        "languages": {"Python": 1000},
        "total_pull_requests": 0,
    }
    metrics.update(overrides)
    return ArchetypeEngine(metrics).classify()


def test_night_owl():
    arc = _classify(most_active_hour=23)
    assert arc["id"] == "night_owl"
    assert "palette" in arc


def test_early_bird():
    arc = _classify(most_active_hour=6)
    assert arc["id"] == "early_bird"


def test_weekend_warrior_takes_priority():
    arc = _classify(weekend_ratio=0.6, most_active_hour=23)
    assert arc["id"] == "weekend_warrior"


def test_marathoner():
    arc = _classify(longest_streak=45)
    assert arc["id"] == "marathoner"


def test_polyglot():
    arc = _classify(languages={"A": 1, "B": 1, "C": 1, "D": 1, "E": 1})
    assert arc["id"] == "polyglot"


def test_collaborator():
    arc = _classify(total_pull_requests=30, total_commits=80)
    assert arc["id"] == "collaborator"


def test_sprint_coder():
    arc = _classify(
        total_commits=50,
        commits_per_month={"06": 30, "07": 10, "08": 10},
    )
    assert arc["id"] == "sprint_coder"


def test_deep_worker():
    arc = _classify(total_commits=80, active_days=10, top_repos={"r": 80})
    assert arc["id"] == "deep_worker"


def test_explorer():
    arc = _classify(
        top_repos={"a": 5, "b": 5, "c": 5, "d": 5},
        total_commits=20,
        active_days=20,
        commits_per_month={f"{m:02d}": 2 for m in range(1, 11)},
    )
    assert arc["id"] == "explorer"


def test_steady_builder_default():
    arc = _classify(
        total_commits=12,
        active_days=12,
        commits_per_month={"01": 4, "02": 4, "03": 4},
        top_repos={"r": 12},
    )
    assert arc["id"] == "steady_builder"


def test_all_catalog_entries_reachable():
    ids = available_archetypes()
    assert "steady_builder" in ids
    assert len(ids) >= 8
