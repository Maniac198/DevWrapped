"""GitHub event fetchers (commits, pull requests).

Both fetchers return normalized :class:`Event` instances so downstream metrics
and stories don't need provider-specific knowledge.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from devwrapped.logging_utils import log_event
from devwrapped.model.events import Event, EventType
from devwrapped.providers.github.client import GitHubAPIError, GitHubClient

log = logging.getLogger(__name__)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # Normalize Zulu suffix and ensure tz-aware.
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _year_bounds(year: int) -> tuple[str, str]:
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59Z"


class GitHubCommitFetcher:
    """Yield normalized COMMIT events for a single repo/year."""

    def __init__(self, client: GitHubClient, owner: str, repo: str, *, author: str | None = None):
        self.client = client
        self.owner = owner
        self.repo = repo
        self.author = author

    def fetch_commits(self, year: int) -> list[Event]:
        since, until = _year_bounds(year)
        params: dict[str, object] = {"since": since, "until": until}
        if self.author:
            params["author"] = self.author

        events: list[Event] = []
        try:
            page_source: Iterable[dict] = self.client.get_paginated(
                f"/repos/{self.owner}/{self.repo}/commits", params=params
            )
        except GitHubAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "github.commits.fetch_failed",
                owner=self.owner,
                repo=self.repo,
                status=exc.status,
            )
            return events

        for commit in page_source:
            commit_data = commit.get("commit") or {}
            author = commit_data.get("author") or {}
            ts = _parse_iso(author.get("date"))
            if ts is None:
                continue

            events.append(
                Event(
                    type=EventType.COMMIT,
                    actor=author.get("name") or (commit.get("author") or {}).get("login") or "unknown",
                    repo=f"{self.owner}/{self.repo}",
                    timestamp=ts,
                    metadata={
                        "sha": commit.get("sha", ""),
                        "message": (commit_data.get("message") or "").split("\n", 1)[0],
                    },
                )
            )
        return events


class GitHubPullRequestFetcher:
    """Yield normalized PULL_REQUEST events for a repo/year, filtered by actor."""

    def __init__(self, client: GitHubClient, owner: str, repo: str, *, author: str | None = None):
        self.client = client
        self.owner = owner
        self.repo = repo
        self.author = author

    def fetch_pull_requests(self, year: int) -> list[Event]:
        events: list[Event] = []
        try:
            page_source: Iterable[dict] = self.client.get_paginated(
                f"/repos/{self.owner}/{self.repo}/pulls",
                params={"state": "all", "sort": "created", "direction": "desc"},
            )
        except GitHubAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "github.pulls.fetch_failed",
                owner=self.owner,
                repo=self.repo,
                status=exc.status,
            )
            return events

        for pr in page_source:
            created = _parse_iso(pr.get("created_at"))
            if created is None:
                continue
            if created.year < year:
                # Results are sorted desc, so we can stop walking older PRs.
                break
            if created.year != year:
                continue
            user = (pr.get("user") or {}).get("login") or "unknown"
            if self.author and user.lower() != self.author.lower():
                continue

            events.append(
                Event(
                    type=EventType.PULL_REQUEST,
                    actor=user,
                    repo=f"{self.owner}/{self.repo}",
                    timestamp=created.astimezone(timezone.utc),
                    metadata={
                        "number": pr.get("number"),
                        "title": (pr.get("title") or "").split("\n", 1)[0],
                        "state": pr.get("state"),
                        "merged": bool(pr.get("merged_at")),
                    },
                )
            )
        return events
