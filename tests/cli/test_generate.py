from typer.testing import CliRunner

from devwrapped.cli import app
from devwrapped.model.events import Event, EventType
from datetime import datetime


def test_generate_command(monkeypatch, tmp_path):
    runner = CliRunner()

    class FakeProvider:
        def name(self):
            return "github"

        def fetch_events(self, year):
            return [
                Event(
                    type=EventType.COMMIT,
                    actor="test",
                    repo="test/repo",
                    timestamp=datetime.utcnow(),
                    metadata={},
                )
            ]

    monkeypatch.setattr(
        "devwrapped.cli.GitHubProvider",
        lambda owner, repo: FakeProvider()
    )

    output_file = tmp_path / "wrapped.json"

    result = runner.invoke(
        app,
        [
            "generate",
            "--provider", "github",
            "--owner", "test",
            "--repo", "repo",
            "--year", "2024",
            "--output", str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()
