"""Normalized activity events across all git providers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    REVIEW = "review"
    COMMENT = "comment"


@dataclass
class Event:
    """A normalized activity event across all git providers.

    ``actor`` is intentionally a stable identifier (login) rather than an email;
    use :meth:`pseudonymize_actor` when emitting to untrusted sinks.
    """

    type: EventType
    actor: str
    repo: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def pseudonymize_actor(self, salt: str = "devwrapped") -> str:
        """Return a stable, non-reversible hash of the actor.

        Useful when exporting telemetry to logs or aggregated reports where we
        want to count unique contributors without leaking identities.
        """
        h = hashlib.sha256()
        h.update(salt.encode("utf-8"))
        h.update(b":")
        h.update(self.actor.encode("utf-8"))
        return h.hexdigest()[:16]
