from typing import List

from devwrapped.providers.base import Provider
from devwrapped.model.events import Event
from devwrapped.providers.github.client import GitHubClient
from devwrapped.providers.github.fetch import GitHubCommitFetcher


class GitHubProvider(Provider):
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.client = GitHubClient()

    def name(self) -> str:
        return "github"

    def authenticate(self) -> None:
        pass

    def fetch_events(self, year: int) -> List[Event]:
        fetcher = GitHubCommitFetcher(
            client=self.client,
            owner=self.owner,
            repo=self.repo
        )
        return fetcher.fetch_commits(year)
