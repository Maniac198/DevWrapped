"""GitHub implementation of the Provider interface."""

from __future__ import annotations

from collections.abc import Iterable

from devwrapped.model.events import Event
from devwrapped.providers.base import Provider
from devwrapped.providers.github.client import GitHubClient
from devwrapped.providers.github.fetch import (
    GitHubCommitFetcher,
    GitHubPullRequestFetcher,
)


class GitHubProvider(Provider):
    """Fetch commit + pull-request events from GitHub."""

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        client: GitHubClient | None = None,
        author: str | None = None,
        include_pull_requests: bool = True,
    ):
        self.owner = owner
        self.repo = repo
        self.author = author
        self.include_pull_requests = include_pull_requests
        self.client = client or GitHubClient()

    def name(self) -> str:
        return "github"

    def authenticate(self) -> None:
        # Authentication is handled lazily by :class:`GitHubClient`.
        return None

    def fetch_events(self, year: int) -> list[Event]:
        commit_events = GitHubCommitFetcher(
            client=self.client, owner=self.owner, repo=self.repo, author=self.author
        ).fetch_commits(year)

        if not self.include_pull_requests:
            return commit_events

        pr_events = GitHubPullRequestFetcher(
            client=self.client, owner=self.owner, repo=self.repo, author=self.author
        ).fetch_pull_requests(year)

        return [*commit_events, *pr_events]

    # Handy when the caller wants to enumerate languages for richer stories.
    def repo_languages(self, repos: Iterable[str]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for r in repos:
            for lang, size in self.client.list_languages(self.owner, r).items():
                totals[lang] = totals.get(lang, 0) + size
        return totals
