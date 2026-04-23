"""Formal CLI exit codes.

The DevWrapped CLI is used both interactively and in CI, so we give callers a
stable, documented contract. Keep this in sync with the README.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    USAGE_ERROR = 1
    AUTH_FAILURE = 2
    NO_DATA = 3
    RATE_LIMITED = 4
    INTERNAL = 10


__all__ = ["ExitCode"]
