"""
Shared event definitions for cross-component communication.

Contains event types and constants used across presentation components.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class EventType(Enum):
    """Standard event types for cross-component communication."""

    # Animation events
    ANIMATION_STARTED = auto()
    ANIMATION_STOPPED = auto()
    ANIMATION_FRAME = auto()
    ANIMATION_RESET = auto()

    # Mechanism events
    MECHANISM_SELECTED = auto()
    MECHANISM_CHANGED = auto()
    MECHANISM_UPDATED = auto()

    # Skeleton events
    SKELETON_LOADED = auto()
    SKELETON_UPDATED = auto()
    SKELETON_CLEARED = auto()

    # UI events
    VIEW_CHANGED = auto()
    PARAMETER_CHANGED = auto()
    SELECTION_CHANGED = auto()


@dataclass(frozen=True)
class Event:
    """
    Immutable event for cross-component communication.

    Attributes:
        event_type: Type of the event
        source: Component that emitted the event
        data: Optional event payload
    """

    event_type: EventType
    source: str
    data: dict[str, Any] | None = None

    def with_data(self, **kwargs: Any) -> Event:
        """Create new event with additional data."""
        existing = self.data or {}
        return Event(
            event_type=self.event_type,
            source=self.source,
            data={**existing, **kwargs},
        )


__all__ = [
    "EventType",
    "Event",
]
