"""Event system for decoupled communication."""

from .event_bus import EventBus, Event
from .app_events import (
    PartSelectedEvent,
    PathDrawingStartedEvent,
    PathDrawingCompletedEvent,
    AnimationStateChangedEvent,
    MechanismGeneratedEvent,
    ProjectLoadedEvent,
    ProjectSavedEvent,
    ViewZoomChangedEvent,
)

# Global event bus instance
event_bus = EventBus()

__all__ = [
    'EventBus',
    'Event',
    'event_bus',
    'PartSelectedEvent',
    'PathDrawingStartedEvent',
    'PathDrawingCompletedEvent',
    'AnimationStateChangedEvent',
    'MechanismGeneratedEvent',
    'ProjectLoadedEvent',
    'ProjectSavedEvent',
    'ViewZoomChangedEvent'
]