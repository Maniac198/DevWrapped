import json

from typer.testing import CliRunner

from devwrapped.cli import app


def test_render_command_rebuilds_html(tmp_path):
    payload = {
        "version": "0.2.0",
        "year": 2024,
        "provider": "github",
        "metrics": {
            "total_commits": 50,
            "active_days": 20,
            "longest_streak": 3,
            "most_active_hour": 14,
            "commits_per_month": {f"{m:02d}": m for m in range(1, 13)},
            "top_repos": {"alpha": 10},
            "weekday_distribution": {
                "Mon": 5, "Tue": 3, "Wed": 2, "Thu": 4, "Fri": 1, "Sat": 0, "Sun": 0
            },
            "commits_per_day": {"2024-06-15": 3},
        },
        "stories": [{"id": "x", "title": "Hi", "text": "World", "emoji": "✨"}],
        "archetype": {
            "id": "explorer",
            "name": "Explorer",
            "emoji": "⚡",
            "description": "desc",
            "palette": {"primary": "#06b6d4", "secondary": "#164e63", "accent": "#a5f3fc"},
        },
    }
    in_path = tmp_path / "wrapped.json"
    in_path.write_text(json.dumps(payload))
    out_path = tmp_path / "wrapped.html"

    result = CliRunner().invoke(app, ["render", str(in_path), "--output", str(out_path)])
    assert result.exit_code == 0, result.stdout
    assert out_path.exists()
    html = out_path.read_text()
    assert "Explorer" in html
    assert "DevWrapped" in html
    # Heatmap should be regenerated from commits_per_day.
    assert "<svg" in html


def test_render_command_rejects_missing_file(tmp_path):
    result = CliRunner().invoke(app, ["render", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_render_command_rejects_bad_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    result = CliRunner().invoke(app, ["render", str(bad)])
    assert result.exit_code == 1
