"""Bitbucket event fetchers (commits, pull requests).

Both fetchers normalize the Bitbucket-specific payload shape into the
:class:`devwrapped.model.events.Event` dataclass so downstream metrics,
stories and rendering stay provider-agnostic.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from devwrapped.logging_utils import log_event
from devwrapped.model.events import Event, EventType
from devwrapped.providers.bitbucket.client import BitbucketAPIError, BitbucketClient

log = logging.getLogger(__name__)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _commit_actor(commit: dict) -> str:
    """Extract the stablest actor identifier available on a commit payload."""
    author = commit.get("author") or {}
    user = author.get("user") or {}
    for key in ("username", "nickname", "display_name", "account_id"):
        value = user.get(key)
        if isinstance(value, str) and value:
            return value
    # Fall back to the raw "Name <email>" header field if there's no linked account.
    raw = author.get("raw")
    if isinstance(raw, str) and raw:
        return raw.split("<", 1)[0].strip() or raw
    return "unknown"


class BitbucketCommitFetcher:
    """Yield normalized COMMIT events for a single workspace/repo/year."""

    def __init__(
        self,
        client: BitbucketClient,
        workspace: str,
        slug: str,
        *,
        author: str | None = None,
    ):
        self.client = client
        self.workspace = workspace
        self.slug = slug
        self.author = author.lower() if author else None

    def fetch_commits(self, year: int) -> list[Event]:
        events: list[Event] = []
        try:
            page_source: Iterable[dict] = self.client.get_paginated(
                f"/repositories/{self.workspace}/{self.slug}/commits",
                params={"pagelen": 100},
            )
        except BitbucketAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "bitbucket.commits.fetch_failed",
                workspace=self.workspace,
                slug=self.slug,
                status=exc.status,
            )
            return events

        for commit in page_source:
            ts = _parse_iso(commit.get("date"))
            if ts is None:
                continue

            # Bitbucket returns commits newest-first. Once we're past the
            # target year, we can stop paging.
            if ts.year > year:
                continue
            if ts.year < year:
                break

            actor = _commit_actor(commit)
            if self.author and actor.lower() != self.author:
                # The caller asked for commits authored by a specific user.
                continue

            events.append(
                Event(
                    type=EventType.COMMIT,
                    actor=actor,
                    repo=f"{self.workspace}/{self.slug}",
                    timestamp=ts.astimezone(timezone.utc),
                    metadata={
                        "sha": commit.get("hash", ""),
                        "message": (commit.get("message") or "").split("\n", 1)[0],
                    },
                )
            )
        return events


class BitbucketPullRequestFetcher:
    """Yield normalized PULL_REQUEST events for a workspace/repo/year.

    Bitbucket scopes PR state filters; by default the API returns only OPEN +
    MERGED. We explicitly request OPEN / MERGED / DECLINED / SUPERSEDED in a
    single call using repeated ``state`` params, which Bitbucket concatenates.
    """

    DEFAULT_STATES = ("OPEN", "MERGED", "DECLINED", "SUPERSEDED")

    def __init__(
        self,
        client: BitbucketClient,
        workspace: str,
        slug: str,
        *,
        author: str | None = None,
        states: Iterable[str] | None = None,
    ):
        self.client = client
        self.workspace = workspace
        self.slug = slug
        self.author = author.lower() if author else None
        self.states = list(states) if states else list(self.DEFAULT_STATES)

    def fetch_pull_requests(self, year: int) -> list[Event]:
        events: list[Event] = []
        try:
            page_source: Iterable[dict] = self.client.get_paginated(
                f"/repositories/{self.workspace}/{self.slug}/pullrequests",
                params={"state": self.states, "pagelen": 50},
            )
        except BitbucketAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "bitbucket.pulls.fetch_failed",
                workspace=self.workspace,
                slug=self.slug,
                status=exc.status,
            )
            return events

        for pr in page_source:
            created = _parse_iso(pr.get("created_on"))
            if created is None:
                continue

            # PRs aren't reliably date-sorted by the API, so don't "break"
            # based on year — just filter.
            if created.year != year:
                continue

            author_field = pr.get("author") or {}
            user = (
                author_field.get("username")
                or author_field.get("nickname")
                or author_field.get("display_name")
                or "unknown"
            )
            if self.author and str(user).lower() != self.author:
                continue

            state = (pr.get("state") or "").upper()
            events.append(
                Event(
                    type=EventType.PULL_REQUEST,
                    actor=user,
                    repo=f"{self.workspace}/{self.slug}",
                    timestamp=created.astimezone(timezone.utc),
                    metadata={
                        "number": pr.get("id"),
                        "title": (pr.get("title") or "").split("\n", 1)[0],
                        "state": state,
                        "merged": state == "MERGED",
                    },
                )
            )
        return events


__all__ = ["BitbucketCommitFetcher", "BitbucketPullRequestFetcher"]
