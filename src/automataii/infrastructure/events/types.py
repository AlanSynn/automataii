"""
Type definitions for the event system.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from automataii.infrastructure.events.base import Event


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


# Type aliases
EventCallback = Callable[["Event"], None]
AsyncEventCallback = Callable[["Event"], Any]  # Can return awaitable
