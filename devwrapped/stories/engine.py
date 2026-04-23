"""Narrative "cards" derived from metrics — the heart of the Wrapped experience."""

from __future__ import annotations

import calendar
from collections.abc import Callable

Story = dict[str, str]


class StoryEngine:
    """Turn a metrics dict into a list of narrative cards."""

    def __init__(self, metrics: dict):
        self.metrics = metrics

    def generate(self) -> list[Story]:
        generators: list[Callable[[], list[Story]]] = [
            self._commit_volume_story,
            self._time_of_day_story,
            self._peak_month_story,
            self._repo_focus_story,
            self._streak_story,
            self._weekday_story,
            self._pull_request_story,
            self._review_story,
            self._language_story,
        ]

        stories: list[Story] = []
        for gen in generators:
            stories.extend(gen())
        return stories

    # 1. Commit volume
    def _commit_volume_story(self) -> list[Story]:
        total = self.metrics.get("total_commits", 0)
        if total == 0:
            return []
        if total >= 500:
            emoji, qualifier = "🔥", "legendary"
        elif total >= 100:
            emoji, qualifier = "🔥", "serious"
        elif total >= 25:
            emoji, qualifier = "✨", "solid"
        else:
            emoji, qualifier = "🌱", "a fresh start"
        return [
            {
                "id": "commit_volume",
                "title": "Your Coding Year",
                "text": f"You shipped {total} commits — {qualifier} output.",
                "emoji": emoji,
            }
        ]

    # 2. Time of day
    def _time_of_day_story(self) -> list[Story]:
        hour = self.metrics.get("most_active_hour")
        if hour is None:
            return []
        if hour >= 22 or hour <= 5:
            label, emoji = "late at night", "🌙"
        elif 6 <= hour <= 11:
            label, emoji = "in the mornings", "☀️"
        elif 12 <= hour <= 17:
            label, emoji = "in the afternoons", "🌤️"
        else:
            label, emoji = "in the evenings", "🌆"
        return [
            {
                "id": "time_of_day",
                "title": "Your Coding Rhythm",
                "text": f"You coded most often {label} (peak hour: {hour:02d}:00).",
                "emoji": emoji,
            }
        ]

    # 3. Peak month
    def _peak_month_story(self) -> list[Story]:
        per_month = self.metrics.get("commits_per_month", {})
        if not per_month or not any(per_month.values()):
            return []
        peak_month, count = max(per_month.items(), key=lambda kv: kv[1])
        try:
            label = calendar.month_name[int(peak_month)]
        except (ValueError, IndexError):
            label = peak_month
        return [
            {
                "id": "peak_month",
                "title": "Your Peak Month",
                "text": f"{label} was your busiest month with {count} commits.",
                "emoji": "🚀",
            }
        ]

    # 4. Main project
    def _repo_focus_story(self) -> list[Story]:
        repos = self.metrics.get("top_repos", {})
        if not repos:
            return []
        repo, count = next(iter(repos.items()))
        return [
            {
                "id": "repo_focus",
                "title": "Your Main Project",
                "text": f"{repo} saw the most love — {count} commits.",
                "emoji": "🧠",
            }
        ]

    # 5. Streak
    def _streak_story(self) -> list[Story]:
        longest = self.metrics.get("longest_streak", 0)
        if longest < 3:
            return []
        if longest >= 30:
            emoji = "🏆"
            qualifier = "a marathon run"
        elif longest >= 14:
            emoji = "⚡"
            qualifier = "an impressive stretch"
        else:
            emoji = "🔥"
            qualifier = "a strong streak"
        return [
            {
                "id": "longest_streak",
                "title": "Your Longest Streak",
                "text": f"You committed {longest} days in a row — {qualifier}.",
                "emoji": emoji,
            }
        ]

    # 6. Weekday vs weekend
    def _weekday_story(self) -> list[Story]:
        dominant = self.metrics.get("dominant_weekday")
        weekend_ratio = self.metrics.get("weekend_ratio", 0)
        if dominant is None:
            return []
        if weekend_ratio >= 0.4:
            return [
                {
                    "id": "weekend_warrior",
                    "title": "Weekend Warrior",
                    "text": f"{int(weekend_ratio * 100)}% of your commits happened on weekends.",
                    "emoji": "🛋️",
                }
            ]
        return [
            {
                "id": "dominant_weekday",
                "title": "Your Power Day",
                "text": f"{dominant} was your most productive day of the week.",
                "emoji": "📅",
            }
        ]

    # 7. Pull requests
    def _pull_request_story(self) -> list[Story]:
        total = self.metrics.get("total_pull_requests", 0)
        if total == 0:
            return []
        merged = self.metrics.get("merged_pull_requests", 0)
        if total == 0:
            return []
        merge_rate = int((merged / total) * 100) if total else 0
        return [
            {
                "id": "pull_requests",
                "title": "Shipping Together",
                "text": f"{total} pull requests opened · {merged} merged ({merge_rate}% merge rate).",
                "emoji": "🤝",
            }
        ]

    # 8. Reviews
    def _review_story(self) -> list[Story]:
        reviews = self.metrics.get("total_reviews", 0)
        if reviews == 0:
            return []
        approvals = self.metrics.get("approvals_given", 0)
        repos = self.metrics.get("reviewed_repo_count", 0)
        approval_rate = int(approvals / reviews * 100) if reviews else 0
        return [
            {
                "id": "reviews",
                "title": "Reviewing with Care",
                "text": (
                    f"You submitted {reviews} reviews across {repos} "
                    f"repositor{'y' if repos == 1 else 'ies'} ({approval_rate}% approvals)."
                ),
                "emoji": "🔍",
            }
        ]

    # 9. Languages
    def _language_story(self) -> list[Story]:
        languages = self.metrics.get("languages", {})
        if not languages:
            return []
        top_langs = list(languages.keys())[:3]
        if not top_langs:
            return []
        if len(top_langs) == 1:
            text = f"Your year was written in {top_langs[0]}."
        else:
            text = "Your year was written in " + ", ".join(top_langs[:-1]) + f" and {top_langs[-1]}."
        return [
            {
                "id": "languages",
                "title": "Your Tech Stack",
                "text": text,
                "emoji": "🧑‍💻",
            }
        ]
