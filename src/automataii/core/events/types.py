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






# Type aliases
EventCallback = Callable[[Event], None]
AsyncEventCallback = Callable[[Event], Any]  # Can return awaitable
