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


class GitHubReviewFetcher:
    """Yield normalized REVIEW events for PRs the user has reviewed.

    Uses GitHub's search API to scope the query to a single year, which is
    dramatically cheaper than walking every repo's PR list.
    """

    def __init__(self, client: GitHubClient, *, author: str):
        self.client = client
        self.author = author

    def fetch_reviews(self, year: int) -> list[Event]:
        # ``is:pr reviewed-by:<user> created:YYYY-01-01..YYYY-12-31`` would
        # filter by the PR's creation year; we want reviews *submitted* in the
        # target year so we iterate PRs reviewed-by-user and then walk their
        # reviews endpoint to confirm submission date.
        query = f"is:pr reviewed-by:{self.author}"
        events: list[Event] = []

        try:
            page_source: Iterable[dict] = self.client.get_paginated(
                "/search/issues", params={"q": query, "sort": "updated", "order": "desc"}
            )
        except GitHubAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "github.reviews.search_failed",
                author=self.author,
                status=exc.status,
            )
            return events

        seen: set[tuple[str, int]] = set()
        for issue in page_source:
            updated = _parse_iso(issue.get("updated_at"))
            # Cheap break: once we're well past the target year, stop walking.
            if updated and updated.year < year:
                break

            repo_url = issue.get("repository_url", "")
            # Shape: https://api.github.com/repos/<owner>/<repo>
            owner_repo = repo_url.rsplit("/repos/", 1)[-1]
            if not owner_repo or "/" not in owner_repo:
                continue
            number = issue.get("number")
            if not isinstance(number, int):
                continue
            key = (owner_repo, number)
            if key in seen:
                continue
            seen.add(key)

            try:
                reviews = self.client.get(
                    f"/repos/{owner_repo}/pulls/{number}/reviews"
                ) or []
            except GitHubAPIError as exc:
                log_event(
                    log,
                    logging.DEBUG,
                    "github.reviews.fetch_failed",
                    owner_repo=owner_repo,
                    number=number,
                    status=exc.status,
                )
                continue

            for review in reviews:
                user = (review.get("user") or {}).get("login") or ""
                if user.lower() != self.author.lower():
                    continue
                submitted = _parse_iso(review.get("submitted_at"))
                if submitted is None or submitted.year != year:
                    continue
                events.append(
                    Event(
                        type=EventType.REVIEW,
                        actor=user,
                        repo=owner_repo,
                        timestamp=submitted.astimezone(timezone.utc),
                        metadata={
                            "pr_number": number,
                            "state": review.get("state"),
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
