"""Discover active repositories in a Bitbucket workspace."""

from __future__ import annotations

import logging

from devwrapped.logging_utils import log_event
from devwrapped.providers.bitbucket.client import BitbucketClient

log = logging.getLogger(__name__)


def discover_active_repos(
    *,
    client: BitbucketClient,
    workspace: str,
    year: int,
    include_forks: bool = False,
    include_private: bool = False,
) -> list[str]:
    """Return the slugs of repos in *workspace* that have commits in *year*.

    Bitbucket doesn't expose an "archived" flag the way GitHub does, so that
    filter is deliberately absent here.
    """
    active: list[str] = []
    for repo in client.list_repos(workspace):
        if not include_private and repo.get("private"):
            continue
        if not include_forks and repo.get("fork"):
            continue

        slug = repo.get("slug")
        if not slug:
            continue

        if client.has_commit_in_year(workspace, slug, year):
            active.append(slug)
            log_event(
                log, logging.INFO, "bitbucket.repo.active",
                workspace=workspace, slug=slug, year=year,
            )
    return active


__all__ = ["discover_active_repos"]
