"""Backend registry — lookup table for provider-specific wiring.

Each backend exposes a uniform interface the CLI can call without caring
whether we're on GitHub, Bitbucket, or a provider added later. The interface
is minimal and defined via :class:`ProviderBackend`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol


class _Client(Protocol):
    cache_hits: int


class _Provider(Protocol):
    def name(self) -> str: ...
    def fetch_events(self, year: int) -> list: ...
    def fetch_reviews(self, year: int) -> list: ...
    def repo_languages(self, repos: Iterable[str]) -> dict: ...


@dataclass(frozen=True)
class ProviderBackend:
    """Glue that wires a provider name to its concrete components."""

    name: str
    build_client: Callable[..., _Client]
    authenticated_user: Callable[[_Client], str]
    discover_active_repos: Callable[..., list[str]]
    provider_factory: Callable[..., _Provider]
    owner_term: str = "owner"  # display label for logs/docs
    supports_reviews: bool = True


def _github_backend() -> ProviderBackend:
    # Imports are local so that ``devwrapped --help`` doesn't pay the cost
    # of wiring every backend up-front.
    from devwrapped.providers.github.client import GitHubClient
    from devwrapped.providers.github.discovery import (
        discover_active_repos as gh_discover,
    )
    from devwrapped.providers.github.provider import GitHubProvider

    def _client(**kw):
        return GitHubClient(**{k: v for k, v in kw.items() if k in {"cache"}})

    def _user(client):
        return client.get_authenticated_user()

    def _discover(*, client, owner, year, is_org=False, include_forks=False,
                  include_archived=False, include_private=False):
        return gh_discover(
            client=client,
            owner=owner,
            year=year,
            is_org=is_org,
            include_forks=include_forks,
            include_archived=include_archived,
            include_private=include_private,
        )

    def _provider(*, owner, repo, client, author=None, include_pull_requests=True):
        return GitHubProvider(
            owner=owner, repo=repo, client=client, author=author,
            include_pull_requests=include_pull_requests,
        )

    return ProviderBackend(
        name="github",
        build_client=_client,
        authenticated_user=_user,
        discover_active_repos=_discover,
        provider_factory=_provider,
        owner_term="owner",
        supports_reviews=True,
    )


def _bitbucket_backend() -> ProviderBackend:
    from devwrapped.providers.bitbucket.client import BitbucketClient
    from devwrapped.providers.bitbucket.discovery import (
        discover_active_repos as bb_discover,
    )
    from devwrapped.providers.bitbucket.provider import BitbucketProvider

    def _client(**kw):
        return BitbucketClient(**{k: v for k, v in kw.items() if k in {"cache"}})

    def _user(client):
        return client.get_authenticated_user()

    def _discover(*, client, owner, year, is_org=False, include_forks=False,
                  include_archived=False, include_private=False):
        # Bitbucket has no "archived" flag and no workspace/org distinction
        # beyond the workspace slug — we ignore those toggles here.
        return bb_discover(
            client=client,
            workspace=owner,
            year=year,
            include_forks=include_forks,
            include_private=include_private,
        )

    def _provider(*, owner, repo, client, author=None, include_pull_requests=True):
        return BitbucketProvider(
            workspace=owner, repo=repo, client=client, author=author,
            include_pull_requests=include_pull_requests,
        )

    return ProviderBackend(
        name="bitbucket",
        build_client=_client,
        authenticated_user=_user,
        discover_active_repos=_discover,
        provider_factory=_provider,
        owner_term="workspace",
        supports_reviews=False,
    )


_BACKENDS: dict[str, Callable[[], ProviderBackend]] = {
    "github": _github_backend,
    "bitbucket": _bitbucket_backend,
}


def get_backend(name: str) -> ProviderBackend:
    factory = _BACKENDS.get(name)
    if factory is None:
        raise KeyError(f"Unknown provider: {name!r}")
    return factory()


def available_backends() -> list[str]:
    return list(_BACKENDS.keys())


__all__ = ["ProviderBackend", "get_backend", "available_backends"]
