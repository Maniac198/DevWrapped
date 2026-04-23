import json

from devwrapped.render.index import build_index


def _write_year(root, year, archetype_name="Explorer", archetype_id="explorer",
                emoji="⚡", commits=100):
    d = root / str(year)
    d.mkdir()
    (d / "wrapped.json").write_text(
        json.dumps(
            {
                "year": year,
                "metrics": {"total_commits": commits},
                "archetype": {"id": archetype_id, "name": archetype_name, "emoji": emoji},
            }
        )
    )


def test_build_index_lists_years_desc(tmp_path):
    _write_year(tmp_path, 2022, "Night Owl", "night_owl", "🌙")
    _write_year(tmp_path, 2023, "Explorer", "explorer", "⚡")
    _write_year(tmp_path, 2024, "Marathoner", "marathoner", "🏃")

    (tmp_path / "ignored").mkdir()
    (tmp_path / "images").mkdir()

    out = build_index(tmp_path)
    html = out.read_text()

    # Check ordering in the year list section specifically (the landing
    # page also embeds min/max year attributes up top which would otherwise
    # confuse a naive search-based assertion).
    list_section = html.split('<ul class="years">', 1)[1]
    assert list_section.index("2024") < list_section.index("2023") < list_section.index("2022")
    assert "Marathoner" in html
    assert "Explorer" in html
    assert "Night Owl" in html
    assert "ignored" not in html


def test_build_index_emits_years_manifest(tmp_path):
    _write_year(tmp_path, 2023, "Explorer", "explorer", "⚡", commits=110)
    _write_year(tmp_path, 2024, "Marathoner", "marathoner", "🏃", commits=220)

    build_index(tmp_path)
    manifest_path = tmp_path / "years.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())

    assert "generated_at" in manifest
    years = manifest["years"]
    assert [entry["year"] for entry in years] == [2024, 2023]
    assert years[0]["archetype_id"] == "marathoner"
    assert years[0]["archetype_emoji"] == "🏃"
    assert years[0]["total_commits"] == 220


def test_build_index_landing_has_year_jump_form(tmp_path):
    _write_year(tmp_path, 2024)
    out = build_index(tmp_path)
    html = out.read_text()
    assert 'id="jump-form"' in html
    assert 'id="jump-year"' in html
    # datalist populated with known years.
    assert '<option value="2024"></option>' in html
    # JS redirect for ?year= shortcut.
    assert 'params.get("year")' in html


def test_build_index_handles_empty_directory(tmp_path):
    out = build_index(tmp_path)
    assert out.exists()
    html = out.read_text()
    assert "No years yet" in html
    manifest = json.loads((tmp_path / "years.json").read_text())
    assert manifest["years"] == []


def test_build_index_handles_missing_wrapped_json(tmp_path):
    (tmp_path / "2024").mkdir()
    (tmp_path / "2024" / "index.html").write_text("<html></html>")

    out = build_index(tmp_path)
    html = out.read_text()
    assert "2024" in html
    manifest = json.loads((tmp_path / "years.json").read_text())
    assert manifest["years"] == [
        {
            "year": 2024,
            "archetype_id": None,
            "archetype_name": None,
            "archetype_emoji": None,
            "total_commits": None,
        }
    ]
