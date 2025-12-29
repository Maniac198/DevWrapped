from typing import List

from devwrapped.providers.github.client import GitHubClient
from devwrapped.providers.github.fetch import GitHubCommitFetcher

def discover_active_repos(
    *,
    client: GitHubClient,
    owner: str,
    year: int,
    is_org: bool = False,
) -> list[str]:
    active_repos: list[str] = []

    for repo in client.list_repos(owner, is_org=is_org):
        if repo["archived"] or repo["fork"]:
            continue

        repo_name = repo["name"]

        # 🔥 FAST CHECK
        if client.has_commit_in_year(owner, repo_name, year):
            active_repos.append(repo_name)

    return active_repos
