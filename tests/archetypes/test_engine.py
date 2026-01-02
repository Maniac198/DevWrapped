from devwrapped.archetypes.engine import ArchetypeEngine


def test_night_owl():
    metrics = {
        "total_commits": 50,
        "active_days": 10,
        "most_active_hour": 23,
        "top_repos": {"repo1": 50},
        "commits_per_month": {"10": 20},
    }

    archetype = ArchetypeEngine(metrics).classify()

    assert archetype["id"] == "night_owl"


def test_steady_builder_default():
    metrics = {
        "total_commits": 20,
        "active_days": 15,
        "most_active_hour": 14,
        "top_repos": {"repo1": 10},
        "commits_per_month": {"01": 3, "02": 3, "03": 4},
    }

    archetype = ArchetypeEngine(metrics).classify()

    assert archetype["id"] == "steady_builder"
