"""Aggregate normalized Events into summary metrics for stories and rendering."""

from __future__ import annotations

import calendar
from collections import Counter
from collections.abc import Iterable
from datetime import date, timedelta

from devwrapped.model.events import Event, EventType

_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class MetricsEngine:
    """Compute Wrapped metrics from a list of :class:`Event` objects."""

    def __init__(self, events: Iterable[Event], *, languages: dict[str, int] | None = None):
        events = list(events)
        self.all_events = events
        self.commits = [e for e in events if e.type == EventType.COMMIT]
        self.pull_requests = [e for e in events if e.type == EventType.PULL_REQUEST]
        self.reviews = [e for e in events if e.type == EventType.REVIEW]
        self.languages = languages or {}

    # ---- public API -------------------------------------------------------

    def compute(self) -> dict:
        streaks = self._streaks()
        weekday = self._weekday_distribution()
        return {
            "total_commits": len(self.commits),
            "active_days": self._active_days(),
            "busiest_day": self._busiest_day(),
            "busiest_day_count": self._busiest_day_count(),
            "most_active_hour": self._most_active_hour(),
            "commits_per_month": self._commits_per_month(),
            "commits_per_day": self._commits_per_day(),
            "top_repos": self._top_repos(),
            "repo_count": len({e.repo for e in self.commits}),
            "weekday_distribution": weekday,
            "dominant_weekday": self._dominant_weekday(weekday),
            "weekend_ratio": self._weekend_ratio(weekday),
            "longest_streak": streaks["longest"],
            "current_streak": streaks["current"],
            "total_pull_requests": len(self.pull_requests),
            "merged_pull_requests": sum(
                1 for e in self.pull_requests if e.metadata.get("merged")
            ),
            "total_reviews": len(self.reviews),
            "approvals_given": sum(
                1 for e in self.reviews if (e.metadata.get("state") or "").upper() == "APPROVED"
            ),
            "changes_requested": sum(
                1 for e in self.reviews if (e.metadata.get("state") or "").upper() == "CHANGES_REQUESTED"
            ),
            "reviewed_repo_count": len({e.repo for e in self.reviews}),
            "languages": self._top_languages(),
            "commits_per_active_day": self._commits_per_active_day(),
        }

    # ---- individual metrics ----------------------------------------------

    def _active_days(self) -> int:
        return len({e.timestamp.date() for e in self.commits})

    def _busiest_day(self) -> str | None:
        if not self.commits:
            return None
        counter = Counter(e.timestamp.date() for e in self.commits)
        return counter.most_common(1)[0][0].isoformat()

    def _busiest_day_count(self) -> int:
        if not self.commits:
            return 0
        counter = Counter(e.timestamp.date() for e in self.commits)
        return counter.most_common(1)[0][1]

    def _most_active_hour(self) -> int | None:
        if not self.commits:
            return None
        counter = Counter(e.timestamp.hour for e in self.commits)
        return counter.most_common(1)[0][0]

    def _commits_per_month(self) -> dict[str, int]:
        counter = Counter(f"{e.timestamp.month:02d}" for e in self.commits)
        # Include zero-filled months so visualizations don't have gaps.
        return {f"{m:02d}": counter.get(f"{m:02d}", 0) for m in range(1, 13)}

    def _commits_per_day(self) -> dict[str, int]:
        counter: Counter[str] = Counter(
            e.timestamp.date().isoformat() for e in self.commits
        )
        return dict(sorted(counter.items()))

    def _top_repos(self, limit: int = 5) -> dict[str, int]:
        counter = Counter(e.repo for e in self.commits)
        return dict(counter.most_common(limit))

    def _weekday_distribution(self) -> dict[str, int]:
        counter = Counter(_WEEKDAY_NAMES[e.timestamp.weekday()] for e in self.commits)
        return {name: counter.get(name, 0) for name in _WEEKDAY_NAMES}

    def _dominant_weekday(self, distribution: dict[str, int]) -> str | None:
        if not any(distribution.values()):
            return None
        return max(distribution.items(), key=lambda kv: kv[1])[0]

    @staticmethod
    def _weekend_ratio(distribution: dict[str, int]) -> float:
        total = sum(distribution.values())
        if total == 0:
            return 0.0
        weekend = distribution.get("Sat", 0) + distribution.get("Sun", 0)
        return round(weekend / total, 3)

    def _streaks(self) -> dict[str, int]:
        if not self.commits:
            return {"longest": 0, "current": 0}

        days = sorted({e.timestamp.date() for e in self.commits})
        longest = current = 1
        for prev, curr in zip(days, days[1:], strict=False):
            if (curr - prev).days == 1:
                current += 1
                longest = max(longest, current)
            else:
                current = 1

        # "Current" streak = run ending on the last day we saw activity.
        current_run = 1
        for prev, curr in zip(
            reversed(days[:-1]), reversed(days[1:]), strict=False
        ):
            if (curr - prev).days == 1:
                current_run += 1
            else:
                break

        return {"longest": longest, "current": current_run}

    def _top_languages(self, limit: int = 5) -> dict[str, int]:
        if not self.languages:
            return {}
        ordered = sorted(self.languages.items(), key=lambda kv: kv[1], reverse=True)
        return dict(ordered[:limit])

    def _commits_per_active_day(self) -> float:
        active = self._active_days()
        if active == 0:
            return 0.0
        return round(len(self.commits) / active, 2)

    # ---- helpers (exposed for tests) -------------------------------------

    @staticmethod
    def month_label(month_number: str) -> str:
        try:
            return calendar.month_abbr[int(month_number)] or month_number
        except (ValueError, IndexError):
            return month_number

    @staticmethod
    def date_range(start: date, end: date) -> list[date]:
        days = []
        cur = start
        while cur <= end:
            days.append(cur)
            cur += timedelta(days=1)
        return days


__all__ = ["MetricsEngine"]
