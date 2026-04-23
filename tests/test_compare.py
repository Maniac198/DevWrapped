import json

from devwrapped.compare import compute_yoy, load_payload


def _payload(year, commits, days, streak, archetype_id="explorer", archetype_name="Explorer", langs=None):
    return {
        "year": year,
        "metrics": {
            "total_commits": commits,
            "active_days": days,
            "longest_streak": streak,
            "repo_count": 3,
            "total_pull_requests": 10,
            "total_reviews": 5,
            "languages": langs or {"Python": 1000},
        },
        "archetype": {"id": archetype_id, "name": archetype_name, "emoji": "⚡"},
    }


def test_compute_yoy_returns_deltas_and_pct():
    prev = _payload(2023, 100, 50, 5)
    curr = _payload(2024, 150, 60, 7)
    yoy = compute_yoy(prev, curr)

    assert yoy["previous_year"] == 2023
    assert yoy["current_year"] == 2024
    assert yoy["total_commits"]["diff"] == 50
    assert yoy["total_commits"]["pct"] == 50.0
    assert yoy["active_days"]["diff"] == 10
    assert yoy["longest_streak"]["diff"] == 2


def test_compute_yoy_handles_zero_previous_without_crashing():
    prev = _payload(2023, 0, 0, 0)
    curr = _payload(2024, 10, 5, 2)
    yoy = compute_yoy(prev, curr)
    # pct is undefined when previous is zero — we return None for that case.
    assert yoy["total_commits"]["pct"] is None
    assert yoy["total_commits"]["diff"] == 10


def test_compute_yoy_archetype_change_detected():
    prev = _payload(2023, 10, 5, 3, archetype_id="explorer", archetype_name="Explorer")
    curr = _payload(2024, 50, 20, 5, archetype_id="night_owl", archetype_name="Night Owl")
    yoy = compute_yoy(prev, curr)
    assert yoy["archetype_changed"]["changed"] is True
    assert yoy["archetype_changed"]["to_name"] == "Night Owl"


def test_compute_yoy_new_languages():
    prev = _payload(2023, 10, 5, 3, langs={"Python": 1000})
    curr = _payload(2024, 20, 10, 5, langs={"Python": 800, "Go": 500, "Rust": 100})
    yoy = compute_yoy(prev, curr)
    assert set(yoy["new_languages"]) == {"Go", "Rust"}


def test_compute_yoy_returns_none_when_inputs_missing():
    assert compute_yoy(None, None) is None
    assert compute_yoy({}, {"metrics": {"total_commits": 1}}) is None


def test_load_payload_handles_missing_and_invalid(tmp_path):
    assert load_payload(tmp_path / "nope.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert load_payload(bad) is None


def test_load_payload_roundtrip(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"year": 2024, "metrics": {"total_commits": 1}}))
    assert load_payload(f)["year"] == 2024
