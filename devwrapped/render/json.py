"""Render the Wrapped payload as JSON."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from devwrapped.model.events import Event


class JSONRenderer:
    """Serialize events + metrics + stories + archetype to JSON."""

    def __init__(self, output_path: str | Path = "wrapped.json"):
        self.output_path = Path(output_path)

    def render(
        self,
        *,
        events: Iterable[Event] = (),
        metrics: dict | None = None,
        stories: list | None = None,
        archetype: dict | None = None,
        year: int,
        provider: str,
        version: str = "0.2.0",
        include_events: bool = True,
        pseudonymize_actors: bool = False,
    ) -> None:
        events_list = list(events)

        payload = {
            "version": version,
            "year": year,
            "provider": provider,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "metrics": metrics or {},
            "stories": stories or [],
            "archetype": archetype,
        }

        if include_events:
            payload["events"] = [
                self._serialize_event(e, pseudonymize=pseudonymize_actors)
                for e in events_list
            ]

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    @staticmethod
    def _serialize_event(event: Event, *, pseudonymize: bool) -> dict:
        return {
            "type": event.type.value if hasattr(event.type, "value") else str(event.type),
            "actor": event.pseudonymize_actor() if pseudonymize else event.actor,
            "repo": event.repo,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "metadata": event.metadata,
        }
