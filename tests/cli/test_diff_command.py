import json

from typer.testing import CliRunner

from devwrapped.cli import app


def _write(path, payload):
    path.write_text(json.dumps(payload))


def test_diff_command_prints_table(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write(a, {
        "year": 2023,
        "metrics": {"total_commits": 100, "active_days": 50, "longest_streak": 4,
                    "repo_count": 2, "total_pull_requests": 5, "total_reviews": 3,
                    "languages": {"Python": 1}},
        "archetype": {"id": "explorer", "name": "Explorer"},
    })
    _write(b, {
        "year": 2024,
        "metrics": {"total_commits": 150, "active_days": 70, "longest_streak": 8,
                    "repo_count": 4, "total_pull_requests": 12, "total_reviews": 9,
                    "languages": {"Python": 2, "Go": 1}},
        "archetype": {"id": "night_owl", "name": "Night Owl"},
    })

    result = CliRunner().invoke(app, ["diff", str(a), str(b)])
    assert result.exit_code == 0, result.stdout
    assert "2023" in result.stdout and "2024" in result.stdout
    assert "Commits" in result.stdout
    assert "+50" in result.stdout
    assert "Archetype" in result.stdout


def test_diff_command_rejects_missing(tmp_path):
    result = CliRunner().invoke(app, ["diff", str(tmp_path / "no.json"), str(tmp_path / "also.json")])
    assert result.exit_code == 1
