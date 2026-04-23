from datetime import datetime, timezone

from typer.testing import CliRunner

from devwrapped.cli import app
from devwrapped.model.events import Event, EventType


def _stub_backend(monkeypatch, provider_name, owner_value, events):
    """Replace backend.* callables for a given provider with in-memory fakes."""
    from devwrapped.providers import registry

    class FakeProvider:
        def __init__(self, *args, **kwargs):
            pass

        def name(self):
            return provider_name

        def fetch_events(self, year):
            return events

        def fetch_reviews(self, year):
            return []

        def repo_languages(self, repos):
            return {}

    class FakeClient:
        cache_hits = 0

    fake_backend = registry.ProviderBackend(
        name=provider_name,
        build_client=lambda **kw: FakeClient(),
        authenticated_user=lambda client: owner_value,
        discover_active_repos=lambda **kw: ["repo"],
        provider_factory=lambda **kw: FakeProvider(),
        owner_term="workspace" if provider_name == "bitbucket" else "owner",
        supports_reviews=provider_name == "github",
    )

    def _get(name: str):
        if name == provider_name:
            return fake_backend
        raise KeyError(name)

    # The CLI does `from devwrapped.providers.registry import get_backend`,
    # which creates a binding in the CLI namespace. Patch both so either
    # import path is stubbed.
    monkeypatch.setattr(registry, "get_backend", _get)
    monkeypatch.setattr("devwrapped.cli.get_backend", _get)


def test_generate_github_writes_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("GITHUB_TOKEN", "fake")

    _stub_backend(
        monkeypatch, "github", "tester",
        events=[Event(EventType.COMMIT, "tester", "tester/repo",
                      datetime(2024, 6, 1, tzinfo=timezone.utc), {})],
    )

    output = tmp_path / "wrapped.json"
    result = runner.invoke(app, [
        "generate", "--provider", "github",
        "--repo", "repo", "--year", "2024",
        "--output", str(output),
        "--no-languages", "--no-cache", "--no-reviews",
    ])
    assert result.exit_code == 0, result.stdout
    assert output.exists()


def test_generate_bitbucket_routes_through_registry(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("BITBUCKET_TOKEN", "fake")

    _stub_backend(
        monkeypatch, "bitbucket", "tester-bb",
        events=[Event(EventType.COMMIT, "tester-bb", "ws/app",
                      datetime(2024, 7, 1, tzinfo=timezone.utc), {})],
    )

    output = tmp_path / "wrapped.json"
    result = runner.invoke(app, [
        "generate", "--provider", "bitbucket",
        "--repo", "app", "--year", "2024",
        "--output", str(output),
        "--no-languages", "--no-cache",
    ])
    assert result.exit_code == 0, result.stdout
    assert output.exists()


def test_generate_rejects_unknown_provider():
    runner = CliRunner()
    result = runner.invoke(app, ["generate", "--provider", "gitlab", "--year", "2024"])
    assert result.exit_code == 1
    assert "not supported" in result.stdout.lower() or "gitlab" in result.stdout.lower()


def test_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert "DevWrapped" in result.stdout
