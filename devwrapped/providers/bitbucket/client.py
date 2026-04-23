"""Thin Bitbucket Cloud REST v2 client.

Security posture mirrors :mod:`devwrapped.providers.github.client`:
  * TLS-only (``https://api.bitbucket.org/2.0``).
  * Tokens are never logged — errors surface HTTP status and response body
    only after going through :func:`devwrapped.logging_utils.redact`.
  * Credentials come from environment variables. Callers must NEVER pass a
    token through a file path or command-line argument.

Authentication
--------------
Two supported modes, tried in this priority order:

  1. Workspace / repository access token: ``BITBUCKET_TOKEN`` → ``Authorization: Bearer <token>``.
  2. App password: ``BITBUCKET_USERNAME`` + ``BITBUCKET_APP_PASSWORD`` → HTTP Basic auth.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Iterator
from typing import Any

import requests

from devwrapped.cache import CachedResponse, ResponseCache
from devwrapped.logging_utils import log_event, redact

log = logging.getLogger(__name__)


class BitbucketAPIError(RuntimeError):
    """Raised for non-retriable Bitbucket API failures."""

    def __init__(self, status: int, path: str, body: Any):
        self.status = status
        self.path = path
        self.body = body
        super().__init__(f"Bitbucket API error {status} for {path}")


class BitbucketClient:
    BASE_URL = "https://api.bitbucket.org/2.0"
    DEFAULT_TIMEOUT = 20
    MAX_RETRIES = 4
    DEFAULT_PAGELEN = 100

    def __init__(
        self,
        *,
        token: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
        session: requests.Session | None = None,
        timeout: float | None = None,
        cache: ResponseCache | None = None,
    ):
        self.token = token or os.getenv("BITBUCKET_TOKEN") or os.getenv("BITBUCKET_ACCESS_TOKEN")
        self.username = username or os.getenv("BITBUCKET_USERNAME")
        self.app_password = app_password or os.getenv("BITBUCKET_APP_PASSWORD")

        if not self.token and not (self.username and self.app_password):
            raise RuntimeError(
                "Bitbucket credentials missing. Set BITBUCKET_TOKEN (access "
                "token) or BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD."
            )

        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.cache = cache
        self.cache_hits = 0
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "devwrapped/0.2 (+https://github.com/Maniac198/devwrapped)",
            }
        )

        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        else:
            # requests will set the Authorization header per-request from .auth.
            self.session.auth = (self.username or "", self.app_password or "")

    # ---- low-level request -----------------------------------------------

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if not url.startswith("http"):
            url = f"{self.BASE_URL}{url}"

        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self.MAX_RETRIES:
            attempt += 1
            try:
                response = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
            except requests.RequestException as exc:
                last_exc = exc
                log_event(
                    log,
                    logging.WARNING,
                    "bitbucket.request.network_error",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )
                self._sleep_with_backoff(attempt)
                continue

            if response.status_code == 429:
                delay = self._rate_limit_delay(response)
                log_event(
                    log,
                    logging.WARNING,
                    "bitbucket.request.rate_limited",
                    url=url,
                    attempt=attempt,
                    sleep_seconds=delay,
                )
                if attempt > self.MAX_RETRIES:
                    break
                time.sleep(delay)
                continue

            if 500 <= response.status_code < 600:
                log_event(
                    log,
                    logging.WARNING,
                    "bitbucket.request.server_error",
                    url=url,
                    attempt=attempt,
                    status=response.status_code,
                )
                if attempt > self.MAX_RETRIES:
                    break
                self._sleep_with_backoff(attempt)
                continue

            return response

        if last_exc is not None:
            raise BitbucketAPIError(0, url, str(last_exc)) from last_exc
        raise BitbucketAPIError(599, url, "exhausted retries")

    @staticmethod
    def _rate_limit_delay(response: requests.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass
        return 30.0

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        base = min(30, 2 ** max(0, attempt - 1))
        time.sleep(base + random.uniform(0, 1))

    # ---- public helpers --------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Any:
        """Issue a GET with ETag-aware caching."""
        full_url = path if path.startswith("http") else f"{self.BASE_URL}{path}"
        cache_key = None
        cached: CachedResponse | None = None
        extra_headers: dict[str, str] = {}

        if self.cache is not None:
            cache_key = ResponseCache.make_key("GET", full_url, params)
            cached = self.cache.get(cache_key)
            if cached:
                if cached.etag:
                    extra_headers["If-None-Match"] = cached.etag
                if cached.last_modified:
                    extra_headers["If-Modified-Since"] = cached.last_modified

        response = self._request(
            "GET", full_url, params=params, headers=extra_headers or None
        )

        if response.status_code == 304 and cached is not None:
            self.cache_hits += 1
            log_event(log, logging.DEBUG, "bitbucket.cache.hit", url=full_url)
            return cached.body

        if response.status_code >= 400:
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text
            log_event(
                log,
                logging.ERROR,
                "bitbucket.api_error",
                url=full_url,
                status=response.status_code,
                body=redact(body),
            )
            raise BitbucketAPIError(response.status_code, full_url, body)

        if not response.content:
            return None
        try:
            body = response.json()
        except ValueError:
            body = response.text

        if self.cache is not None and cache_key is not None and response.status_code == 200:
            self.cache.set(
                cache_key,
                CachedResponse(
                    status=200,
                    body=body,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                ),
            )
        return body

    def get_paginated(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every ``values`` entry across pages, following ``next`` URLs."""
        # First call carries explicit params; subsequent calls follow the
        # server-provided ``next`` URL which already encodes them.
        first_params: dict = dict(params or {})
        first_params.setdefault("pagelen", self.DEFAULT_PAGELEN)
        current_params: dict | None = first_params
        url: str = path

        while True:
            data = self.get(url, params=current_params)
            if not isinstance(data, dict):
                return
            values = data.get("values") or []
            if not isinstance(values, list):
                return
            yield from values
            next_url = data.get("next")
            if not next_url:
                return
            url = next_url
            current_params = None  # params are baked into the ``next`` URL

    # ---- domain helpers --------------------------------------------------

    def get_authenticated_user(self) -> str:
        """Return the username (``username`` or ``nickname``) of the caller."""
        data = self.get("/user")
        if not isinstance(data, dict):
            raise BitbucketAPIError(500, "/user", "unexpected response shape")
        # 'username' is deprecated but still often present; fall back through
        # the chain of identifier fields Bitbucket exposes.
        for key in ("username", "nickname", "display_name", "account_id"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        raise BitbucketAPIError(500, "/user", "no usable identifier on /user response")

    def list_repos(self, workspace: str) -> Iterator[dict]:
        """Yield repositories in *workspace* with a shape similar to GitHub's."""
        for repo in self.get_paginated(f"/repositories/{workspace}"):
            yield {
                "name": repo.get("name"),
                "slug": repo.get("slug") or (repo.get("full_name", "").rsplit("/", 1)[-1]),
                "full_name": repo.get("full_name"),
                "private": bool(repo.get("is_private")),
                "fork": bool(repo.get("parent")),
                "language": repo.get("language") or None,
                "updated_on": repo.get("updated_on"),
            }

    def has_commit_in_year(self, workspace: str, slug: str, year: int) -> bool:
        """Return True if *workspace/slug* has at least one commit in *year*.

        Bitbucket returns commits newest-first with no arbitrary date filter
        that works universally, so we walk forward until we hit the year or
        fall past it. Usually the first page (<=100 commits) is enough.
        """
        try:
            for commit in self.get_paginated(
                f"/repositories/{workspace}/{slug}/commits", params={"pagelen": 100}
            ):
                date_str = commit.get("date")
                if not isinstance(date_str, str):
                    continue
                # ISO8601 in "YYYY-MM-DD..." shape — cheap prefix check is enough.
                commit_year_str = date_str[:4]
                if not commit_year_str.isdigit():
                    continue
                commit_year = int(commit_year_str)
                if commit_year > year:
                    continue
                # commit_year < year → remaining commits are older; stop.
                return commit_year == year
        except BitbucketAPIError as exc:
            log_event(
                log,
                logging.WARNING,
                "bitbucket.activity_check_failed",
                workspace=workspace,
                slug=slug,
                status=exc.status,
            )
            return False
        return False

    def repo_language(self, workspace: str, slug: str) -> str | None:
        """Return the repo's primary language, if any."""
        try:
            data = self.get(f"/repositories/{workspace}/{slug}")
            if isinstance(data, dict):
                lang = data.get("language")
                if isinstance(lang, str) and lang.strip():
                    return lang.strip()
        except BitbucketAPIError as exc:
            log_event(
                log,
                logging.DEBUG,
                "bitbucket.language_fetch_failed",
                workspace=workspace,
                slug=slug,
                status=exc.status,
            )
        return None


__all__ = ["BitbucketAPIError", "BitbucketClient"]
