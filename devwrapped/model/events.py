from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict


class EventType(str, Enum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    REVIEW = "review"
    COMMENT = "comment"


@dataclass
class Event:
    """
    A normalized activity event across all git providers.
    """
    type: EventType
    actor: str               # username / email hash later
    repo: str                # repo identifier
    timestamp: datetime
    metadata: Dict[str, str] # provider-specific extras
