from devwrapped.providers.github import GitHubProvider
from devwrapped.model.events import Event


class FakeFetcher:
    def fetch_commits(self, year):
        return [
            Event(
                type="commit",
                actor="fake",
                repo="fake/repo",
                timestamp=None,
                metadata={}
            )
        ]


def test_provider_fetch_events(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def fake_fetcher_init(self, client, owner, repo):
        self.fetch_commits = lambda year: FakeFetcher().fetch_commits(year)

    monkeypatch.setattr(
        "devwrapped.providers.github.fetch.GitHubCommitFetcher.__init__",
        fake_fetcher_init
    )

    provider = GitHubProvider(owner="fake", repo="repo")
    events = provider.fetch_events(2024)

    assert len(events) == 1
