from datetime import datetime, timezone

from devwrapped.model.events import Event, EventType
from devwrapped.providers.github import GitHubProvider


class FakeClient:
    def list_languages(self, owner, repo):
        return {"Python": 1000}


def test_provider_fetch_events(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def fake_commits(self, year):
        return [
            Event(
                type=EventType.COMMIT,
                actor="fake",
                repo="fake/repo",
                timestamp=datetime(year, 6, 1, tzinfo=timezone.utc),
                metadata={},
            )
        ]

    def fake_prs(self, year):
        return [
            Event(
                type=EventType.PULL_REQUEST,
                actor="fake",
                repo="fake/repo",
                timestamp=datetime(year, 7, 1, tzinfo=timezone.utc),
                metadata={"merged": True},
            )
        ]

    monkeypatch.setattr(
        "devwrapped.providers.github.fetch.GitHubCommitFetcher.fetch_commits",
        fake_commits,
    )
    monkeypatch.setattr(
        "devwrapped.providers.github.fetch.GitHubPullRequestFetcher.fetch_pull_requests",
        fake_prs,
    )

    provider = GitHubProvider(owner="fake", repo="repo")
    events = provider.fetch_events(2024)
    assert len(events) == 2
    assert provider.name() == "github"


def test_provider_skip_pull_requests(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    monkeypatch.setattr(
        "devwrapped.providers.github.fetch.GitHubCommitFetcher.fetch_commits",
        lambda self, year: [],
    )

    provider = GitHubProvider(owner="fake", repo="repo", include_pull_requests=False)
    assert provider.fetch_events(2024) == []
