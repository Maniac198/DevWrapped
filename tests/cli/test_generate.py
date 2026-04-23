from datetime import datetime, timezone

from typer.testing import CliRunner

from devwrapped.cli import app
from devwrapped.model.events import Event, EventType


def test_generate_command_writes_json(monkeypatch, tmp_path):
    runner = CliRunner()

    monkeypatch.setenv("GITHUB_TOKEN", "fake")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_authenticated_user(self):
            return "tester"

        def list_languages(self, owner, repo):
            return {}

    monkeypatch.setattr("devwrapped.cli.GitHubClient", FakeClient)

    class FakeProvider:
        def __init__(self, *args, **kwargs):
            pass

        def name(self):
            return "github"

        def fetch_events(self, year):
            return [
                Event(
                    type=EventType.COMMIT,
                    actor="tester",
                    repo="tester/repo",
                    timestamp=datetime(year, 6, 1, 10, tzinfo=timezone.utc),
                    metadata={},
                )
            ]

        def fetch_reviews(self, year):
            return []

    monkeypatch.setattr("devwrapped.cli.GitHubProvider", FakeProvider)

    output_file = tmp_path / "wrapped.json"
    result = runner.invoke(
        app,
        [
            "generate",
            "--provider", "github",
            "--repo", "repo",
            "--year", "2024",
            "--output", str(output_file),
            "--no-languages",
            "--no-cache",
            "--no-reviews",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert output_file.exists()


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "DevWrapped" in result.stdout
