from abc import ABC, abstractmethod
from typing import List
from devwrapped.model.events import Event


class Provider(ABC):
    """
    Base class for all git providers (GitHub, GitLab, Bitbucket, Gerrit).
    """

    @abstractmethod
    def name(self) -> str:
        """
        Returns provider name (e.g. 'github').
        """
        pass

    @abstractmethod
    def authenticate(self) -> None:
        """
        Handle authentication (tokens, env vars, etc).
        """
        pass

    @abstractmethod
    def fetch_events(self, year: int) -> List[Event]:
        """
        Fetch all relevant events for the given year.
        """
        pass


