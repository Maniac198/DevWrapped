from typing import Dict


class ArchetypeEngine:
    def __init__(self, metrics: Dict):
        self.metrics = metrics

    def classify(self) -> Dict:
        """
        Returns a single primary archetype.
        """
        total = self.metrics.get("total_commits", 0)
        active_days = self.metrics.get("active_days", 0)
        hour = self.metrics.get("most_active_hour")
        repos = self.metrics.get("top_repos", {})
        per_month = self.metrics.get("commits_per_month", {})

        # 🌙 Night Owl
        if hour is not None and (hour >= 22 or hour <= 5):
            return self._archetype(
                "night_owl",
                "Night Owl",
                "🌙",
                "You did your best coding late at night."
            )

        # 🚀 Sprint Coder
        if per_month and max(per_month.values()) >= total * 0.5:
            return self._archetype(
                "sprint_coder",
                "Sprint Coder",
                "🚀",
                "You had intense bursts of coding activity."
            )

        # 🧠 Deep Worker
        if active_days > 0 and total / active_days >= 5:
            return self._archetype(
                "deep_worker",
                "Deep Worker",
                "🧠",
                "When you code, you go deep and focus hard."
            )

        # ⚡ Explorer
        if len(repos) >= 4:
            return self._archetype(
                "explorer",
                "Explorer",
                "⚡",
                "You worked across many different projects."
            )

        # 🌱 Steady Builder (default)
        return self._archetype(
            "steady_builder",
            "Steady Builder",
            "🌱",
            "You showed up consistently throughout the year."
        )

    def _archetype(self, id: str, name: str, emoji: str, description: str) -> Dict:
        return {
            "id": id,
            "name": name,
            "emoji": emoji,
            "description": description,
        }
