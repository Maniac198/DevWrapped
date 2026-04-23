from datetime import datetime, timezone

from devwrapped.model.events import EventType
from devwrapped.providers.github.fetch import (
    GitHubCommitFetcher,
    GitHubPullRequestFetcher,
)


class FakeClient:
    def __init__(self, pages):
        self._pages = pages

    def get_paginated(self, path, params=None):
        yield from self._pages


def test_fetch_commits_creates_events():
    client = FakeClient(
        [
            {
                "sha": "abc123",
                "commit": {
                    "author": {"name": "Test User", "date": "2024-06-01T10:00:00Z"},
                    "message": "Initial commit\n\nDetails",
                },
            }
        ]
    )
    fetcher = GitHubCommitFetcher(client=client, owner="test", repo="repo")
    events = fetcher.fetch_commits(2024)
    assert len(events) == 1
    event = events[0]
    assert event.type == EventType.COMMIT
    assert event.actor == "Test User"
    assert event.repo == "test/repo"
    assert event.metadata["sha"] == "abc123"
    assert event.metadata["message"] == "Initial commit"
    assert event.timestamp == datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)


def test_fetch_commits_skips_commits_with_missing_author():
    client = FakeClient([{"sha": "abc", "commit": {"author": None, "message": "x"}}])
    events = GitHubCommitFetcher(client, "o", "r").fetch_commits(2024)
    assert events == []


def test_pull_request_fetcher_filters_by_year_and_author():
    client = FakeClient(
        [
            {
                "number": 5,
                "title": "New",
                "state": "open",
                "user": {"login": "alice"},
                "created_at": "2024-11-02T12:00:00Z",
                "merged_at": None,
            },
            {
                "number": 4,
                "title": "Old",
                "state": "closed",
                "user": {"login": "alice"},
                "created_at": "2023-10-01T12:00:00Z",
                "merged_at": "2023-10-02T12:00:00Z",
            },
        ]
    )
    events = GitHubPullRequestFetcher(client, "o", "r", author="alice").fetch_pull_requests(2024)
    assert len(events) == 1
    assert events[0].type == EventType.PULL_REQUEST
    assert events[0].metadata["number"] == 5


def test_pull_request_fetcher_filters_out_other_users():
    client = FakeClient(
        [
            {
                "number": 1,
                "title": "Theirs",
                "state": "open",
                "user": {"login": "bob"},
                "created_at": "2024-06-01T00:00:00Z",
            }
        ]
    )
    events = GitHubPullRequestFetcher(client, "o", "r", author="alice").fetch_pull_requests(2024)
    assert events == []
