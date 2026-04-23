"""On-disk HTTP response cache keyed by URL+params with ETag revalidation.

The cache is intentionally tiny and has one job: let DevWrapped replay GitHub
API responses across runs without re-fetching the world. When present, cached
entries are sent to GitHub with ``If-None-Match`` so the server can respond
with ``304 Not Modified`` (which doesn't count against the rate limit budget
for conditional requests).

Security notes:
  * Cache lives under ``$XDG_CACHE_HOME/devwrapped`` (or ``~/.cache/devwrapped``)
    by default, with parent directories created with ``mode=0o700`` and each
    file written with ``mode=0o600``.
  * We never cache response headers other than ``ETag`` and ``Last-Modified``
    — and we never cache anything that looks like an auth header.
  * Keys are SHA-256 hashes of ``(method, url, sorted(params))`` so file names
    don't leak repo or user identifiers on shared systems.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from devwrapped.logging_utils import log_event

log = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    status: int
    body: Any
    etag: str | None = None
    last_modified: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


def default_cache_dir() -> Path:
    """Resolve the cache dir honoring ``XDG_CACHE_HOME``."""
    xdg = os.getenv("XDG_CACHE_HOME")
    root = Path(xdg) if xdg else Path.home() / ".cache"
    return root / "devwrapped"


class ResponseCache:
    """Simple JSON-on-disk cache. Safe to use from a single-process CLI run."""

    def __init__(self, path: str | Path | None = None, *, enabled: bool = True):
        self.enabled = enabled
        self.path = Path(path) if path else default_cache_dir()
        if self.enabled:
            try:
                self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError as exc:
                log_event(
                    log,
                    logging.WARNING,
                    "cache.disabled",
                    path=str(self.path),
                    error=str(exc),
                )
                self.enabled = False

    # ------------------------------------------------------------------

    @staticmethod
    def make_key(method: str, url: str, params: dict | None) -> str:
        norm_params = json.dumps(
            sorted((params or {}).items()), ensure_ascii=False, default=str
        )
        payload = f"{method.upper()}\n{url}\n{norm_params}".encode()
        return hashlib.sha256(payload).hexdigest()

    def _file_for(self, key: str) -> Path:
        # Fan out into 2-char subdir to keep directory sizes sane.
        return self.path / key[:2] / key

    def get(self, key: str) -> CachedResponse | None:
        if not self.enabled:
            return None
        f = self._file_for(key)
        if not f.is_file():
            return None
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        try:
            return CachedResponse(**raw)
        except TypeError:
            return None

    def set(self, key: str, response: CachedResponse) -> None:
        if not self.enabled:
            return
        f = self._file_for(key)
        try:
            f.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Atomic write with restrictive perms.
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(f.parent),
                prefix=f.name + ".",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(asdict(response), tmp, ensure_ascii=False, default=str)
                tmp.flush()
                os.fchmod(tmp.fileno(), 0o600)
                tmp_name = tmp.name
            os.replace(tmp_name, f)
        except OSError as exc:
            log_event(
                log,
                logging.DEBUG,
                "cache.write_failed",
                key=key[:8],
                error=str(exc),
            )

    def purge(self) -> int:
        """Delete all cached entries. Returns number of files removed."""
        if not self.enabled or not self.path.exists():
            return 0
        removed = 0
        for child in self.path.rglob("*"):
            if child.is_file():
                try:
                    child.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed


__all__ = ["ResponseCache", "CachedResponse", "default_cache_dir"]
