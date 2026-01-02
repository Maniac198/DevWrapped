import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from devwrapped.model.events import Event


class JSONRenderer:
    def __init__(self, output_path: str = "wrapped.json"):
        self.output_path = Path(output_path)

    def render(
        self,
        *,
        events: List[Event],
        metrics: dict | None = None,
        stories: list | None = None,
        archetype=None,
        year: int,
        provider: str,
        version: str = "0.1.0",
    ) -> None:
        payload = {
            "version": version,
            "year": year,
            "provider": provider,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics or {},
            "stories": stories or [],
             "archetype": archetype,
            "events": [self._serialize_event(e) for e in events],
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _serialize_event(self, event: Event) -> dict:
        return {
            "type": event.type.value,
            "actor": event.actor,
            "repo": event.repo,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata,
        }
