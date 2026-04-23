from devwrapped.model.events import EventType
from devwrapped.providers.bitbucket.fetch import (
    BitbucketCommitFetcher,
    BitbucketPullRequestFetcher,
)


class FakeClient:
    def __init__(self, pages):
        self._pages = pages
        self.last_params = None

    def get_paginated(self, path, params=None):
        self.last_params = params
        yield from self._pages


def _commit(sha, date, username=None, raw=None, message="x"):
    user_obj = {}
    if username:
        user_obj = {"username": username, "display_name": username.title()}
    return {
        "hash": sha,
        "date": date,
        "message": message,
        "author": {"user": user_obj, "raw": raw or f"{username} <{username}@ex>"},
    }


def test_commit_fetcher_normalizes_shape():
    client = FakeClient([_commit("abc", "2024-06-01T10:00:00+00:00", username="alice",
                                  message="Initial\n\nbody")])
    events = BitbucketCommitFetcher(client, "ws", "app").fetch_commits(2024)
    assert len(events) == 1
    e = events[0]
    assert e.type == EventType.COMMIT
    assert e.actor == "alice"
    assert e.repo == "ws/app"
    assert e.metadata["sha"] == "abc"
    assert e.metadata["message"] == "Initial"  # first line only


def test_commit_fetcher_breaks_when_past_target_year():
    # Bitbucket returns commits newest-first. Once we've seen a commit in an
    # earlier year we must stop — otherwise we waste rate-limit budget.
    client = FakeClient([
        _commit("1", "2025-02-01T10:00:00+00:00", username="alice"),
        _commit("2", "2024-11-10T10:00:00+00:00", username="alice"),
        _commit("3", "2024-01-05T10:00:00+00:00", username="alice"),
        _commit("4", "2023-12-31T23:00:00+00:00", username="alice"),
        # If we didn't break, we'd also include this one.
        _commit("5", "2020-01-01T00:00:00+00:00", username="alice"),
    ])
    events = BitbucketCommitFetcher(client, "ws", "app").fetch_commits(2024)
    assert [e.metadata["sha"] for e in events] == ["2", "3"]


def test_commit_fetcher_filters_author_case_insensitively():
    client = FakeClient([
        _commit("1", "2024-06-01T10:00:00+00:00", username="alice"),
        _commit("2", "2024-07-01T10:00:00+00:00", username="bob"),
    ])
    events = BitbucketCommitFetcher(client, "ws", "app", author="ALICE").fetch_commits(2024)
    assert [e.actor for e in events] == ["alice"]


def test_commit_fetcher_falls_back_to_raw_when_no_user():
    client = FakeClient([
        {
            "hash": "abc",
            "date": "2024-06-01T10:00:00+00:00",
            "message": "hi",
            "author": {"raw": "Charlie Brown <charlie@ex>"},
        }
    ])
    events = BitbucketCommitFetcher(client, "ws", "app").fetch_commits(2024)
    assert events[0].actor == "Charlie Brown"


def test_pr_fetcher_filters_year_and_state(monkeypatch):
    client = FakeClient([
        {"id": 1, "title": "feat a", "state": "MERGED",
         "author": {"username": "alice"}, "created_on": "2024-06-01T00:00:00+00:00"},
        {"id": 2, "title": "old", "state": "MERGED",
         "author": {"username": "alice"}, "created_on": "2023-01-01T00:00:00+00:00"},
        {"id": 3, "title": "other user", "state": "OPEN",
         "author": {"username": "bob"}, "created_on": "2024-07-01T00:00:00+00:00"},
    ])
    events = BitbucketPullRequestFetcher(client, "ws", "app", author="alice").fetch_pull_requests(2024)
    assert len(events) == 1
    e = events[0]
    assert e.type == EventType.PULL_REQUEST
    assert e.metadata["number"] == 1
    assert e.metadata["merged"] is True

    # Ensures the fetcher asked Bitbucket for all four PR states.
    assert client.last_params["state"] == list(BitbucketPullRequestFetcher.DEFAULT_STATES)
