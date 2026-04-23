"""Thin GitHub REST client with retries, rate-limit handling, and safe errors.

Security notes:
  * The authentication token is never logged. Errors surface HTTP status and
    response body only after redaction.
  * We use TLS (``https://api.github.com``) exclusively.
  * All requests go through a single :class:`requests.Session` so that the
    token header is applied consistently and not exposed through per-call
    argument plumbing.
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Iterator
from typing import Any

import requests

from devwrapped.logging_utils import log_event, redact

log = logging.getLogger(__name__)


class GitHubAPIError(RuntimeError):
    """Raised for non-retriable GitHub API failures."""

    def __init__(self, status: int, path: str, body: Any):
        self.status = status
        self.path = path
        self.body = body
        super().__init__(f"GitHub API error {status} for {path}")


class GitHubClient:
    BASE_URL = "https://api.github.com"
    DEFAULT_TIMEOUT = 20  # seconds
    MAX_RETRIES = 4

    def __init__(
        self,
        token: str | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float | None = None,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise RuntimeError(
                "GitHub token not found. Set the GITHUB_TOKEN environment variable."
            )

        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "devwrapped/0.2 (+https://github.com/Maniac198/devwrapped)",
            }
        )

    # ---- low-level request ------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.BASE_URL}{path}"
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
                    "github.request.network_error",
                    path=path,
                    attempt=attempt,
                    error=str(exc),
                )
                self._sleep_with_backoff(attempt)
                continue

            # Rate limit handling. GitHub uses 403 + X-RateLimit-Remaining=0 or
            # 429. Respect retry-after and reset headers when present.
            if response.status_code in (429, 403) and self._is_rate_limited(response):
                delay = self._rate_limit_delay(response)
                log_event(
                    log,
                    logging.WARNING,
                    "github.request.rate_limited",
                    path=path,
                    attempt=attempt,
                    sleep_seconds=delay,
                )
                if attempt > self.MAX_RETRIES:
                    break
                time.sleep(delay)
                continue

            # Transient 5xx — retry with exponential backoff.
            if 500 <= response.status_code < 600:
                log_event(
                    log,
                    logging.WARNING,
                    "github.request.server_error",
                    path=path,
                    attempt=attempt,
                    status=response.status_code,
                )
                if attempt > self.MAX_RETRIES:
                    break
                self._sleep_with_backoff(attempt)
                continue

            return response

        if last_exc is not None:
            raise GitHubAPIError(0, path, str(last_exc)) from last_exc
        raise GitHubAPIError(599, path, "exhausted retries")

    @staticmethod
    def _is_rate_limited(response: requests.Response) -> bool:
        if response.status_code == 429:
            return True
        remaining = response.headers.get("X-RateLimit-Remaining")
        return remaining == "0"

    @staticmethod
    def _rate_limit_delay(response: requests.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass
        reset = response.headers.get("X-RateLimit-Reset")
        if reset:
            try:
                return max(1.0, float(reset) - time.time())
            except ValueError:
                pass
        return 30.0

    @staticmethod
    def _sleep_with_backoff(attempt: int) -> None:
        base = min(30, 2 ** max(0, attempt - 1))
        # Full jitter to avoid thundering herd.
        time.sleep(base + random.uniform(0, 1))

    # ---- public helpers ---------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Any:
        response = self._request("GET", path, params=params)
        if response.status_code >= 400:
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text
            log_event(
                log,
                logging.ERROR,
                "github.api_error",
                path=path,
                status=response.status_code,
                body=redact(body),
            )
            raise GitHubAPIError(response.status_code, path, body)

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def get_paginated(self, path: str, params: dict | None = None) -> Iterator[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)

        page = 1
        while True:
            params["page"] = page
            data = self.get(path, params=params)

            if not data:
                return

            if not isinstance(data, list):
                raise GitHubAPIError(
                    500, path, "expected a list response for pagination"
                )

            yield from data

            if len(data) < params["per_page"]:
                return
            page += 1

    # ---- domain helpers ---------------------------------------------------

    def list_repos(self, owner: str, *, is_org: bool = False) -> Iterator[dict]:
        path = f"/orgs/{owner}/repos" if is_org else f"/users/{owner}/repos"
        for repo in self.get_paginated(path):
            yield {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "archived": repo.get("archived", False),
                "fork": repo.get("fork", False),
                "private": repo.get("private", False),
                "language": repo.get("language"),
            }

    def has_commit_in_year(self, owner: str, repo: str, year: int) -> bool:
        """Return True if *repo* has any authored commit in *year*.

        Empty repos respond with 409 — treat that as a hard "no". Other
        non-transient errors (403, 404, 422) also mean "no" but are logged so
        that auth issues surface in aggregated logs without halting the run.
        """
        since = f"{year}-01-01T00:00:00Z"
        until = f"{year}-12-31T23:59:59Z"
        try:
            commits = self.get(
                f"/repos/{owner}/{repo}/commits",
                params={"since": since, "until": until, "per_page": 1},
            )
            return bool(commits)
        except GitHubAPIError as exc:
            if exc.status == 409:
                return False
            log_event(
                log,
                logging.WARNING,
                "github.activity_check_failed",
                owner=owner,
                repo=repo,
                year=year,
                status=exc.status,
            )
            return False

    def list_languages(self, owner: str, repo: str) -> dict[str, int]:
        try:
            data = self.get(f"/repos/{owner}/{repo}/languages") or {}
            return {str(k): int(v) for k, v in data.items()}
        except GitHubAPIError as exc:
            log_event(
                log,
                logging.DEBUG,
                "github.language_fetch_failed",
                owner=owner,
                repo=repo,
                status=exc.status,
            )
            return {}

    def get_authenticated_user(self) -> str:
        data = self.get("/user")
        if not isinstance(data, dict) or "login" not in data:
            raise GitHubAPIError(500, "/user", "unexpected response shape")
        return str(data["login"])
