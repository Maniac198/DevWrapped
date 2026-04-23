from devwrapped.stories.engine import StoryEngine


def test_yoy_story_renders_all_parts():
    metrics = {
        "total_commits": 150,
        "yoy": {
            "previous_year": 2023,
            "current_year": 2024,
            "total_commits": {"previous": 100, "current": 150, "diff": 50, "pct": 50.0},
            "active_days": {"previous": 50, "current": 60, "diff": 10, "pct": 20.0},
            "archetype_changed": {"changed": True, "to_name": "Night Owl"},
            "new_languages": ["Go", "Rust"],
        },
    }
    stories = StoryEngine(metrics).generate()
    yoy = [s for s in stories if s["id"] == "yoy"]
    assert len(yoy) == 1
    assert "Since 2023" in yoy[0]["text"]
    assert "▲" in yoy[0]["text"]
    assert "50%" in yoy[0]["text"]
    assert "Night Owl" in yoy[0]["text"]
    assert "Go" in yoy[0]["text"]


def test_yoy_story_absent_when_no_data():
    stories = StoryEngine({"total_commits": 10}).generate()
    assert not any(s["id"] == "yoy" for s in stories)


def test_yoy_story_negative_delta_uses_down_arrow():
    metrics = {
        "total_commits": 50,
        "yoy": {
            "previous_year": 2023,
            "current_year": 2024,
            "total_commits": {"previous": 100, "current": 50, "diff": -50, "pct": -50.0},
        },
    }
    stories = StoryEngine(metrics).generate()
    yoy = [s for s in stories if s["id"] == "yoy"]
    assert yoy and "▼" in yoy[0]["text"]
