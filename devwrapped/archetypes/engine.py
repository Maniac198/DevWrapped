"""Classify a developer's year into a single primary archetype.

Each archetype has a stable id, display name, emoji, description, and a
palette used by the HTML renderer to theme the final page.
"""

from __future__ import annotations

_ARCHETYPE_CATALOG: dict[str, dict] = {
    "night_owl": {
        "name": "Night Owl",
        "emoji": "🌙",
        "description": "Your best ideas arrived after dark.",
        "palette": {"primary": "#8b5cf6", "secondary": "#312e81", "accent": "#f0abfc"},
    },
    "early_bird": {
        "name": "Early Bird",
        "emoji": "🌅",
        "description": "You had the commits in before most devs had coffee.",
        "palette": {"primary": "#f59e0b", "secondary": "#7c2d12", "accent": "#fde68a"},
    },
    "sprint_coder": {
        "name": "Sprint Coder",
        "emoji": "🚀",
        "description": "You had intense bursts of coding energy.",
        "palette": {"primary": "#ef4444", "secondary": "#7f1d1d", "accent": "#fecaca"},
    },
    "deep_worker": {
        "name": "Deep Worker",
        "emoji": "🧠",
        "description": "When you code, you go deep and focus hard.",
        "palette": {"primary": "#14b8a6", "secondary": "#134e4a", "accent": "#99f6e4"},
    },
    "explorer": {
        "name": "Explorer",
        "emoji": "⚡",
        "description": "You worked across many different projects.",
        "palette": {"primary": "#06b6d4", "secondary": "#164e63", "accent": "#a5f3fc"},
    },
    "weekend_warrior": {
        "name": "Weekend Warrior",
        "emoji": "🛋️",
        "description": "The weekend is where your best code lives.",
        "palette": {"primary": "#ec4899", "secondary": "#831843", "accent": "#fbcfe8"},
    },
    "polyglot": {
        "name": "Polyglot",
        "emoji": "🗣️",
        "description": "You code in more languages than most people speak.",
        "palette": {"primary": "#a855f7", "secondary": "#4c1d95", "accent": "#e9d5ff"},
    },
    "collaborator": {
        "name": "Collaborator",
        "emoji": "🤝",
        "description": "Your year was defined by pull requests and teamwork.",
        "palette": {"primary": "#22c55e", "secondary": "#14532d", "accent": "#bbf7d0"},
    },
    "reviewer": {
        "name": "Reviewer",
        "emoji": "🔍",
        "description": "You spent your year reviewing code as much as writing it.",
        "palette": {"primary": "#f97316", "secondary": "#7c2d12", "accent": "#fed7aa"},
    },
    "marathoner": {
        "name": "Marathoner",
        "emoji": "🏃",
        "description": "Day after day, you just kept committing.",
        "palette": {"primary": "#0ea5e9", "secondary": "#0c4a6e", "accent": "#bae6fd"},
    },
    "steady_builder": {
        "name": "Steady Builder",
        "emoji": "🌱",
        "description": "You showed up consistently throughout the year.",
        "palette": {"primary": "#22c55e", "secondary": "#052e16", "accent": "#bbf7d0"},
    },
}


class ArchetypeEngine:
    """Pick a single archetype from computed metrics."""

    def __init__(self, metrics: dict):
        self.metrics = metrics

    def classify(self) -> dict:
        total = self.metrics.get("total_commits", 0)
        active_days = self.metrics.get("active_days", 0)
        hour = self.metrics.get("most_active_hour")
        repos = self.metrics.get("top_repos", {})
        per_month = self.metrics.get("commits_per_month", {})
        languages = self.metrics.get("languages", {})
        weekend_ratio = self.metrics.get("weekend_ratio", 0.0)
        longest_streak = self.metrics.get("longest_streak", 0)
        prs = self.metrics.get("total_pull_requests", 0)
        reviews = self.metrics.get("total_reviews", 0)

        # Priority order is intentional — more specific personas first.
        if reviews >= max(50, total) and reviews > 0:
            return self._archetype("reviewer")
        if weekend_ratio >= 0.5 and total >= 10:
            return self._archetype("weekend_warrior")
        if hour is not None and (hour >= 22 or hour <= 5) and total >= 10:
            return self._archetype("night_owl")
        if hour is not None and 5 <= hour <= 8 and total >= 10:
            return self._archetype("early_bird")
        if longest_streak >= 30:
            return self._archetype("marathoner")
        if prs >= max(25, total // 4) and prs > 0:
            return self._archetype("collaborator")
        if len(languages) >= 5:
            return self._archetype("polyglot")
        if per_month and max(per_month.values()) >= max(1, total) * 0.5 and total >= 20:
            return self._archetype("sprint_coder")
        if active_days > 0 and total / active_days >= 5:
            return self._archetype("deep_worker")
        if len(repos) >= 4:
            return self._archetype("explorer")
        return self._archetype("steady_builder")

    def _archetype(self, archetype_id: str) -> dict:
        data = _ARCHETYPE_CATALOG[archetype_id]
        return {
            "id": archetype_id,
            "name": data["name"],
            "emoji": data["emoji"],
            "description": data["description"],
            "palette": data["palette"],
        }


def available_archetypes() -> list[str]:
    """Introspection helper, useful for tests and docs."""
    return list(_ARCHETYPE_CATALOG.keys())
