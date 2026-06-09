"""
Event System Module.

Provides a decoupled communication system based on publish-subscribe pattern.
Supports typed events, async handling, and event replay for debugging.
"""

from automataii.infrastructure.events.base import (
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
from automataii.infrastructure.events.decorators import async_event_handler, event_handler
from automataii.infrastructure.events.event_bus import (
    EventBus,
    FunctionEventHandler,
    get_global_event_bus,
)
from automataii.infrastructure.events.types import (
    AsyncEventCallback,
    EventCallback,
    EventFilter,
    EventPriority,
    EventProcessingMode,
)

__all__ = [
    # Core
    "EventBus",
    "get_global_event_bus",
    "FunctionEventHandler",
    # Base types
    "Event",
    "EventHandler",
    "DomainEvent",
    "SystemEvent",
    "UIEvent",
    # Common events
    "ApplicationStarted",
    "ApplicationShutdown",
    "ProjectLoaded",
    "ProjectSaved",
    "ProjectCreated",
    "ProjectClosed",
    "ProjectModified",
    "AutoSaveTriggered",
    "ComponentActivated",
    "ComponentDeactivated",
    "ImageSelectedEvent",
    "ProjectLoadedEvent",
    # Decorators
    "event_handler",
    "async_event_handler",
    # Types
    "EventFilter",
    "EventPriority",
    "EventProcessingMode",
    "EventCallback",
    "AsyncEventCallback",
]
