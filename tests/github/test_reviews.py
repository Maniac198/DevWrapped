from devwrapped.model.events import EventType
from devwrapped.providers.github.fetch import GitHubReviewFetcher


class FakeClient:
    def __init__(self, search_results, reviews_by_pr):
        self._search = search_results
        self._reviews = reviews_by_pr

    def get_paginated(self, path, params=None):
        assert path == "/search/issues"
        yield from self._search

    def get(self, path, params=None):
        # e.g. /repos/alice/app/pulls/5/reviews
        parts = path.strip("/").split("/")
        owner_repo = f"{parts[1]}/{parts[2]}"
        number = int(parts[4])
        return self._reviews.get((owner_repo, number), [])


def test_review_fetcher_emits_events_for_target_year():
    search = [
        {
            "number": 5,
            "updated_at": "2024-12-01T00:00:00Z",
            "repository_url": "https://api.github.com/repos/alice/app",
        },
        {
            # Older PR — our loop should stop once we fall out of the year.
            "number": 1,
            "updated_at": "2022-01-01T00:00:00Z",
            "repository_url": "https://api.github.com/repos/alice/app",
        },
    ]
    reviews = {
        ("alice/app", 5): [
            {
                "user": {"login": "alice"},
                "state": "APPROVED",
                "submitted_at": "2024-11-30T12:00:00Z",
            },
            {
                "user": {"login": "alice"},
                "state": "COMMENTED",
                "submitted_at": "2023-01-02T00:00:00Z",  # different year — skipped
            },
            {
                "user": {"login": "bob"},
                "state": "APPROVED",
                "submitted_at": "2024-06-01T00:00:00Z",  # not the author
            },
        ],
    }

    events = GitHubReviewFetcher(
        FakeClient(search, reviews), author="alice"
    ).fetch_reviews(2024)
    assert len(events) == 1
    assert events[0].type == EventType.REVIEW
    assert events[0].metadata["state"] == "APPROVED"
    assert events[0].metadata["pr_number"] == 5
    assert events[0].repo == "alice/app"
