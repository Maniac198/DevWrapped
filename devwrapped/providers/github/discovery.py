"""Discover repositories with activity for a given user/org in a given year."""

from __future__ import annotations

import logging

from devwrapped.logging_utils import log_event
from devwrapped.providers.github.client import GitHubClient

log = logging.getLogger(__name__)


def discover_active_repos(
    *,
    client: GitHubClient,
    owner: str,
    year: int,
    is_org: bool = False,
    include_forks: bool = False,
    include_archived: bool = False,
    include_private: bool = False,
) -> list[str]:
    """Return the set of repo names owned by *owner* that had commits in *year*."""
    active_repos: list[str] = []

    for repo in client.list_repos(owner, is_org=is_org):
        if not include_archived and repo.get("archived"):
            continue
        if not include_forks and repo.get("fork"):
            continue
        if not include_private and repo.get("private"):
            continue

        repo_name = repo["name"]
        if client.has_commit_in_year(owner, repo_name, year):
            active_repos.append(repo_name)
            log_event(
                log, logging.INFO, "repo.active", owner=owner, repo=repo_name, year=year
            )

    return active_repos
