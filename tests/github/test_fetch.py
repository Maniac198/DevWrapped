from datetime import datetime
from devwrapped.providers.github.fetch import GitHubCommitFetcher
from devwrapped.model.events import EventType


class FakeClient:
    def get(self, path, params=None):
        return [
            {
                "sha": "abc123",
                "commit": {
                    "author": {
                        "name": "Test User",
                        "date": "2024-06-01T10:00:00Z"
                    },
                    "message": "Initial commit\n\nDetails"
                }
            }
        ]


def test_fetch_commits_creates_events():
    client = FakeClient()
    fetcher = GitHubCommitFetcher(
        client=client,
        owner="test",
        repo="repo"
    )

    events = fetcher.fetch_commits(2024)

    assert len(events) == 1

    event = events[0]
    assert event.type == EventType.COMMIT
    assert event.actor == "Test User"
    assert event.repo == "test/repo"
    assert event.metadata["sha"] == "abc123"
    assert event.metadata["message"] == "Initial commit"
    assert isinstance(event.timestamp, datetime)
