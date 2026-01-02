import os
import requests


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError(
                "GitHub token not found. Set GITHUB_TOKEN env variable."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        })

    def get(self, path: str, params: dict | None = None):
        url = f"{self.BASE_URL}{path}"
        response = self.session.get(url, params=params)

        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub API error {response.status_code}: {response.text}"
            )

        return response.json()

    def get_paginated(self, path: str, params: dict | None = None):
        params = params or {}
        params["per_page"] = 100

        page = 1
        while True:
            params["page"] = page
            data = self.get(path, params=params)

            if not data:
                break

            for item in data:
                yield item

            page += 1

    def list_repos(self, owner: str, is_org: bool = False):
        """
        List repositories for a user or org.
        """
        path = f"/orgs/{owner}/repos" if is_org else f"/users/{owner}/repos"

        for repo in self.get_paginated(path):
            yield {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "archived": repo["archived"],
                "fork": repo["fork"],
                "private": repo["private"],
            }

    def has_commit_in_year(self, owner: str, repo: str, year: int) -> bool:
        since = f"{year}-01-01T00:00:00Z"
        until = f"{year}-12-31T23:59:59Z"

        try:
            commits = self.get(
                f"/repos/{owner}/{repo}/commits",
                params={
                    "since": since,
                    "until": until,
                    "per_page": 1,
                },
            )
            return bool(commits)

        except RuntimeError as e:
            # GitHub returns 409 for empty repositories
            if "409" in str(e):
                return False

            # Other errors: treat as inactive but do not crash
            return False

    def get_authenticated_user(self) -> str:
        data = self.get("/user")
        return data["login"]
