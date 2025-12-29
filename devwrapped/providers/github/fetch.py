from datetime import datetime
from typing import List

from devwrapped.model.events import Event, EventType
from devwrapped.providers.github.client import GitHubClient


class GitHubCommitFetcher:
    def __init__(self, client: GitHubClient, owner: str, repo: str):
        self.client = client
        self.owner = owner
        self.repo = repo

    def fetch_commits(self, year: int) -> List[Event]:
        since = f"{year}-01-01T00:00:00Z"
        until = f"{year}-12-31T23:59:59Z"

        events: List[Event] = []

        for commit in self.client.get_paginated(
            f"/repos/{self.owner}/{self.repo}/commits",
            params={
                "since": since,
                "until": until,
            },
        ):
            commit_data = commit["commit"]
            author = commit_data.get("author")

            if not author:
                continue

            events.append(
                Event(
                    type=EventType.COMMIT,
                    actor=author["name"],
                    repo=f"{self.owner}/{self.repo}",
                    timestamp=datetime.fromisoformat(
                        author["date"].replace("Z", "+00:00")
                    ),
                    metadata={
                        "sha": commit["sha"],
                        "message": commit_data["message"].split("\n")[0],
                    },
                )
            )

        return events

