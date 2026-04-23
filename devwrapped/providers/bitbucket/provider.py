"""Bitbucket Cloud implementation of the Provider interface."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from devwrapped.model.events import Event
from devwrapped.providers.base import Provider
from devwrapped.providers.bitbucket.client import BitbucketClient
from devwrapped.providers.bitbucket.fetch import (
    BitbucketCommitFetcher,
    BitbucketPullRequestFetcher,
)


class BitbucketProvider(Provider):
    """Fetch commit + pull-request events from Bitbucket Cloud."""

    def __init__(
        self,
        workspace: str,
        repo: str,
        *,
        client: BitbucketClient | None = None,
        author: str | None = None,
        include_pull_requests: bool = True,
    ):
        self.workspace = workspace
        self.repo = repo
        self.author = author
        self.include_pull_requests = include_pull_requests
        self.client = client or BitbucketClient()

    def name(self) -> str:
        return "bitbucket"

    def authenticate(self) -> None:
        return None

    def fetch_events(self, year: int) -> list[Event]:
        commits = BitbucketCommitFetcher(
            client=self.client, workspace=self.workspace, slug=self.repo, author=self.author
        ).fetch_commits(year)

        if not self.include_pull_requests:
            return commits

        prs = BitbucketPullRequestFetcher(
            client=self.client, workspace=self.workspace, slug=self.repo, author=self.author
        ).fetch_pull_requests(year)

        return [*commits, *prs]

    def fetch_reviews(self, year: int) -> list[Event]:
        """Bitbucket's participants/approvals model differs from GitHub's.

        A PR has per-user "approved" booleans rather than discrete review
        submissions with timestamps, so there is no faithful mapping to our
        REVIEW event type. Returning an empty list keeps the CLI contract
        stable while we (eventually) model this correctly.
        """
        return []

    def repo_languages(self, repos: Iterable[str]) -> dict[str, int]:
        """Aggregate primary languages across *repos*.

        Bitbucket exposes a single primary language per repo (no byte
        counts), so we return a count-per-language mapping. Downstream
        consumers only compare magnitudes, so counts work fine.
        """
        counter: Counter[str] = Counter()
        for slug in repos:
            lang = self.client.repo_language(self.workspace, slug)
            if lang:
                counter[lang] += 1
        return dict(counter)
