"""
Type definitions for the event system.
"""

from collections.abc import Callable
from enum import Enum, IntEnum
from typing import Any, Protocol, runtime_checkable

from .base import Event


class EventPriority(IntEnum):
    """Event handler priorities."""

    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    CRITICAL = 200


@runtime_checkable
class EventFilter(Protocol):
    """Protocol for event filters."""

    def __call__(self, event: Event) -> bool:
        """Return True if event should be processed."""
        ...


class EventProcessingMode(Enum):
    """Event processing modes."""

    SYNC = "synchronous"
    ASYNC = "asynchronous"
    QUEUED = "queued"


# Common event filters
class EventTypeFilter:
    """Filter events by type."""

    def __init__(self, event_type: type):
        self.event_type = event_type

    def __call__(self, event: Event) -> bool:
        return isinstance(event, self.event_type)


class SourceFilter:
    """Filter events by source."""

    def __init__(self, source: str):
        self.source = source

    def __call__(self, event: Event) -> bool:
        return event.source == self.source


class CompositeFilter:
    """Combine multiple filters with AND/OR logic."""

    def __init__(self, *filters: EventFilter, logic: str = "AND"):
        self.filters = filters
        self.logic = logic.upper()

    def __call__(self, event: Event) -> bool:
        if self.logic == "AND":
            return all(f(event) for f in self.filters)
        elif self.logic == "OR":
            return any(f(event) for f in self.filters)
        else:
            raise ValueError(f"Unknown logic: {self.logic}")


# Type aliases
EventCallback = Callable[[Event], None]
AsyncEventCallback = Callable[[Event], Any]  # Can return awaitable
