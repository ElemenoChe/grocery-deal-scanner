"""Adapter interface. Add a store by subclassing AdSource."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Deal, ListItem


class AdSource(ABC):
    #: short id used in config and reports, e.g. "kroger"
    name: str = "base"
    #: how often this store publishes a new ad, for the scheduler and README
    cadence: str = "weekly"

    @abstractmethod
    def fetch(self, items: list[ListItem]) -> list[Deal]:
        """Return every deal relevant to the given list items."""
