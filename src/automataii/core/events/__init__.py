"""
Event System Module

Provides a decoupled communication system based on publish-subscribe pattern.
Supports typed events, async handling, and event replay for debugging.
"""

from .base import (
    ApplicationShutdown,
    ApplicationStarted,
    AutoSaveTriggered,
    ComponentActivated,
    ComponentDeactivated,
    DomainEvent,
    Event,
    EventHandler,
    ImageSelectedEvent,
    ProjectClosed,
    ProjectCreated,
    ProjectLoaded,
    ProjectLoadedEvent,
    ProjectModified,
    ProjectSaved,
    SystemEvent,
    UIEvent,
)
from .decorators import async_event_handler, event_handler
from .event_bus import EventBus, get_global_event_bus
from .types import EventFilter, EventPriority

__all__ = [
    'EventBus', 'get_global_event_bus',
    'Event', 'EventHandler', 'DomainEvent', 'SystemEvent', 'UIEvent',
    'ApplicationStarted', 'ApplicationShutdown',
    'ProjectLoaded', 'ProjectSaved', 'ProjectCreated', 'ProjectClosed', 'ProjectModified',
    'AutoSaveTriggered', 'ComponentActivated', 'ComponentDeactivated',
    'ImageSelectedEvent', 'ProjectLoadedEvent',
    'event_handler', 'async_event_handler',
    'EventFilter', 'EventPriority'
]
