"""Structured JSON logging with credential redaction.

DevWrapped never logs raw tokens, API responses, or commit messages by default.
The redaction layer protects against accidental leakage of:
  * Bearer / token / key / secret / password headers and fields
  * Common credential formats (AWS, GitHub, Stripe, Google, JWT, private keys)
  * Query-string secrets (?token=..., ?access_token=..., ?api_key=...)

Inspired by the workspace logging-security rule: structured JSON, correlation IDs,
UTC RFC3339 timestamps, no free-form text for critical signals.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

_REDACTED = "[REDACTED]"

# Patterns for well-known secret formats, scrubbed wherever they appear in
# structured log fields or free-form messages.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"ghu_[A-Za-z0-9]{20,}"),
    re.compile(r"ghs_[A-Za-z0-9]{20,}"),
    re.compile(r"ghr_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"sk_live_[0-9A-Za-z]{16,}"),
    re.compile(r"sk_test_[0-9A-Za-z]{16,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"(?i)(?:bearer|token)\s+[A-Za-z0-9._\-]{12,}"),
]

# Field name fragments that should be redacted no matter what the value looks
# like. These are used for both structured payloads and HTTP headers.
_SENSITIVE_KEYS = (
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "access_key",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "refresh_token",
    "session",
    "cookie",
    "x-api-key",
)

_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:access_token|token|api_key|apikey|client_secret|password)=)[^&#\s]+"
)


def _sanitize_log_field(value: str) -> str:
    """Strip control characters used for log injection and apply regex redactions."""
    # Prevent log injection: strip CR/LF and other ASCII control chars.
    cleaned = "".join(ch for ch in value if ch == "\t" or (ord(ch) >= 0x20 and ch != "\x7f"))
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(_REDACTED, cleaned)
    cleaned = _QUERY_SECRET_RE.sub(r"\1" + _REDACTED, cleaned)
    return cleaned


def redact(value: Any) -> Any:
    """Recursively redact credentials from arbitrary JSON-like structures."""
    if isinstance(value, str):
        return _sanitize_log_field(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if any(sensitive in key_str.lower() for sensitive in _SENSITIVE_KEYS):
                out[key_str] = _REDACTED
            else:
                out[key_str] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects with UTC RFC3339 timestamps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": _sanitize_log_field(record.getMessage()),
        }

        correlation_id = getattr(record, "correlation_id", None) or _current_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Merge explicit structured fields passed via extra={"fields": {...}}.
        extra_fields = getattr(record, "fields", None)
        if isinstance(extra_fields, dict):
            payload.update({k: redact(v) for k, v in extra_fields.items()})

        if record.exc_info:
            payload["exc_info"] = _sanitize_log_field(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)


_CORRELATION_ID: str | None = None


def _current_correlation_id() -> str | None:
    return _CORRELATION_ID


def new_correlation_id() -> str:
    """Generate and register a correlation ID for this run."""
    global _CORRELATION_ID
    _CORRELATION_ID = uuid.uuid4().hex[:12]
    return _CORRELATION_ID


def configure_logging(level: str | int | None = None, *, json_output: bool | None = None) -> None:
    """Configure root logger.

    By default we use human-readable logs to stderr. Set DEVWRAPPED_LOG_JSON=1
    (or pass ``json_output=True``) to switch to structured JSON — this is the
    recommended mode for CI runs and any environment where logs are aggregated.
    """
    if level is None:
        level = os.getenv("DEVWRAPPED_LOG_LEVEL", "INFO").upper()
    if json_output is None:
        json_output = os.getenv("DEVWRAPPED_LOG_JSON", "0") == "1"

    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")
        )

    root = logging.getLogger()
    # Remove any previously attached handlers so we don't double-log on re-init.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    """Convenience helper to emit a structured event.

    Example:
        log_event(log, logging.INFO, "repo.discovered", owner=owner, repo=repo_name)
    """
    logger.log(level, message, extra={"fields": fields})
