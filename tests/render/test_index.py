import json

from devwrapped.render.index import build_index


def test_build_index_lists_years_desc(tmp_path):
    for year, archetype in [("2022", "Night Owl"), ("2023", "Explorer"), ("2024", "Marathoner")]:
        (tmp_path / year).mkdir()
        (tmp_path / year / "wrapped.json").write_text(
            json.dumps(
                {
                    "year": int(year),
                    "metrics": {"total_commits": 100 + int(year[-1])},
                    "archetype": {"name": archetype, "emoji": "🧠"},
                }
            )
        )

    (tmp_path / "ignored").mkdir()
    (tmp_path / "images").mkdir()

    out = build_index(tmp_path)
    html = out.read_text()

    assert html.index("2024") < html.index("2023") < html.index("2022")
    assert "Marathoner" in html
    assert "Explorer" in html
    assert "Night Owl" in html
    assert "ignored" not in html


def test_build_index_handles_empty_directory(tmp_path):
    out = build_index(tmp_path)
    assert out.exists()
    html = out.read_text()
    assert "No years yet" in html


def test_build_index_handles_missing_wrapped_json(tmp_path):
    (tmp_path / "2024").mkdir()
    (tmp_path / "2024" / "index.html").write_text("<html></html>")

    out = build_index(tmp_path)
    html = out.read_text()
    assert "2024" in html
