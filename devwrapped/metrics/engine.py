from collections import Counter, defaultdict
from typing import Dict, List

from devwrapped.model.events import Event, EventType


class MetricsEngine:
    def __init__(self, events: List[Event]):
        self.events = [e for e in events if e.type == EventType.COMMIT]

    def compute(self) -> Dict:
        return {
            "total_commits": self._total_commits(),
            "active_days": self._active_days(),
            "busiest_day": self._busiest_day(),
            "most_active_hour": self._most_active_hour(),
            "commits_per_month": self._commits_per_month(),
            "top_repos": self._top_repos(),
        }

    def _total_commits(self) -> int:
        return len(self.events)

    def _active_days(self) -> int:
        return len({e.timestamp.date() for e in self.events})

    def _busiest_day(self):
        if not self.events:
            return None

        counter = Counter(e.timestamp.date() for e in self.events)
        return counter.most_common(1)[0][0].isoformat()

    def _most_active_hour(self):
        if not self.events:
            return None

        counter = Counter(e.timestamp.hour for e in self.events)
        return counter.most_common(1)[0][0]

    def _commits_per_month(self):
        counter = Counter(f"{e.timestamp.month:02d}" for e in self.events)
        return dict(sorted(counter.items()))

    def _top_repos(self, limit: int = 5):
        counter = Counter(e.repo for e in self.events)
        return dict(counter.most_common(limit))
