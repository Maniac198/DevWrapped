"""Year-over-year comparisons between two DevWrapped payloads.

``compute_yoy`` returns a structured delta that :mod:`devwrapped.stories.engine`
consumes to render a "How you changed" story. Standalone so the same function
powers both the rendered story and the ``devwrapped diff`` CLI command.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from devwrapped.logging_utils import log_event

log = logging.getLogger(__name__)


def load_payload(path: str | Path) -> dict | None:
    """Load a ``wrapped.json`` payload from disk. Returns ``None`` on any error."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log_event(log, logging.WARNING, "compare.load_failed", path=str(p), error=str(exc))
        return None


def compute_yoy(previous: dict | None, current: dict | None) -> dict | None:
    """Return a compact delta dict, or ``None`` if we can't compare meaningfully."""
    if not previous or not current:
        return None

    prev_metrics = previous.get("metrics") or {}
    curr_metrics = current.get("metrics") or {}
    if not prev_metrics or not curr_metrics:
        return None

    prev_year = previous.get("year")
    curr_year = current.get("year")

    delta = {
        "previous_year": prev_year,
        "current_year": curr_year,
        "total_commits": _delta(curr_metrics.get("total_commits"), prev_metrics.get("total_commits")),
        "active_days": _delta(curr_metrics.get("active_days"), prev_metrics.get("active_days")),
        "longest_streak": _delta(curr_metrics.get("longest_streak"), prev_metrics.get("longest_streak")),
        "repo_count": _delta(curr_metrics.get("repo_count"), prev_metrics.get("repo_count")),
        "total_pull_requests": _delta(
            curr_metrics.get("total_pull_requests"), prev_metrics.get("total_pull_requests")
        ),
        "total_reviews": _delta(
            curr_metrics.get("total_reviews"), prev_metrics.get("total_reviews")
        ),
        "archetype_changed": _archetype_change(previous.get("archetype"), current.get("archetype")),
        "new_languages": _new_languages(prev_metrics.get("languages"), curr_metrics.get("languages")),
    }
    return delta


# ---------------------------------------------------------------------------


def _delta(current: Any, previous: Any) -> dict | None:
    try:
        c = float(current or 0)
        p = float(previous or 0)
    except (TypeError, ValueError):
        return None
    diff = c - p
    pct: float | None = None
    if p > 0:
        pct = round((diff / p) * 100, 1)
    return {
        "previous": _number(p),
        "current": _number(c),
        "diff": _number(diff),
        "pct": pct,
    }


def _archetype_change(
    previous: dict | None, current: dict | None
) -> dict | None:
    if not previous and not current:
        return None
    prev_id = (previous or {}).get("id")
    curr_id = (current or {}).get("id")
    if prev_id == curr_id:
        return {"changed": False, "from": prev_id, "to": curr_id, "name": (current or {}).get("name")}
    return {
        "changed": True,
        "from": prev_id,
        "to": curr_id,
        "from_name": (previous or {}).get("name"),
        "to_name": (current or {}).get("name"),
        "emoji": (current or {}).get("emoji"),
    }


def _new_languages(
    previous: dict | None, current: dict | None
) -> list[str]:
    prev = set((previous or {}).keys())
    curr_sorted = sorted((current or {}).items(), key=lambda kv: kv[1], reverse=True)
    return [lang for lang, _ in curr_sorted if lang not in prev][:3]


def _number(value: float) -> int | float:
    if abs(value - int(value)) < 1e-9:
        return int(value)
    return round(value, 2)


__all__ = ["compute_yoy", "load_payload"]
