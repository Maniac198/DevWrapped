from datetime import datetime, timezone

from devwrapped.model.events import Event, EventType
from devwrapped.providers.bitbucket import BitbucketProvider


def test_provider_fetch_events_combines_commits_and_prs(monkeypatch):
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")

    def fake_commits(self, year):
        return [Event(EventType.COMMIT, "alice", "ws/app",
                      datetime(year, 6, 1, tzinfo=timezone.utc), {})]

    def fake_prs(self, year):
        return [Event(EventType.PULL_REQUEST, "alice", "ws/app",
                      datetime(year, 7, 1, tzinfo=timezone.utc), {"merged": True})]

    monkeypatch.setattr(
        "devwrapped.providers.bitbucket.fetch.BitbucketCommitFetcher.fetch_commits",
        fake_commits,
    )
    monkeypatch.setattr(
        "devwrapped.providers.bitbucket.fetch.BitbucketPullRequestFetcher.fetch_pull_requests",
        fake_prs,
    )

    provider = BitbucketProvider(workspace="ws", repo="app")
    events = provider.fetch_events(2024)
    assert len(events) == 2
    assert provider.name() == "bitbucket"


def test_provider_returns_empty_reviews(monkeypatch):
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")
    provider = BitbucketProvider(workspace="ws", repo="app")
    assert provider.fetch_reviews(2024) == []


def test_provider_aggregates_languages_as_counts(monkeypatch):
    monkeypatch.setenv("BITBUCKET_TOKEN", "t")

    class FakeClient:
        def repo_language(self, workspace, slug):
            return {"a": "python", "b": "python", "c": "go"}[slug]

    provider = BitbucketProvider(workspace="ws", repo="a", client=FakeClient())
    result = provider.repo_languages(["a", "b", "c"])
    assert result == {"python": 2, "go": 1}
