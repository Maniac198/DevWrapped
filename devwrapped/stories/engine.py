from typing import List, Dict


class StoryEngine:
    def __init__(self, metrics: Dict):
        self.metrics = metrics

    def generate(self) -> List[Dict]:
        stories = []

        stories.extend(self._commit_volume_story())
        stories.extend(self._time_of_day_story())
        stories.extend(self._peak_month_story())
        stories.extend(self._repo_focus_story())

        return stories

    # 1️⃣ Commit volume
    def _commit_volume_story(self):
        total = self.metrics.get("total_commits", 0)

        if total == 0:
            return []

        return [{
            "id": "commit_volume",
            "title": "Your Coding Year",
            "text": f"You made {total} commits this year.",
            "emoji": "🔥" if total > 100 else "✨"
        }]

    # 2️⃣ Time of day
    def _time_of_day_story(self):
        hour = self.metrics.get("most_active_hour")

        if hour is None:
            return []

        if hour >= 22 or hour <= 5:
            label = "late at night"
            emoji = "🌙"
        elif 6 <= hour <= 11:
            label = "in the mornings"
            emoji = "☀️"
        elif 12 <= hour <= 17:
            label = "in the afternoons"
            emoji = "🌤️"
        else:
            label = "in the evenings"
            emoji = "🌆"

        return [{
            "id": "time_of_day",
            "title": "Your Coding Rhythm",
            "text": f"You coded most often {label}.",
            "emoji": emoji
        }]

    # 3️⃣ Peak month
    def _peak_month_story(self):
        per_month = self.metrics.get("commits_per_month", {})

        if not per_month:
            return []

        peak_month = max(per_month, key=per_month.get)
        count = per_month[peak_month]

        return [{
            "id": "peak_month",
            "title": "Your Peak Month",
            "text": f"{peak_month} was your most active month with {count} commits.",
            "emoji": "🚀"
        }]

    # 4️⃣ Repo focus
    def _repo_focus_story(self):
        repos = self.metrics.get("top_repos", {})

        if not repos:
            return []

        repo, count = next(iter(repos.items()))

        return [{
            "id": "repo_focus",
            "title": "Your Main Project",
            "text": f"You focused most on {repo}, with {count} commits.",
            "emoji": "🧠"
        }]
