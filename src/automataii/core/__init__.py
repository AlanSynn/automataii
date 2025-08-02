"""
Core module exports.
"""

from .base import Event, EventHandler, ApplicationStarted, ComponentActivated
from .event_bus import EventBus, get_global_event_bus, set_global_event_bus
from .decorators import EventHandlerMixin, event_handler
from .store import StateStore
from .project_manager import ProjectManager

# Check if Container exists in services
try:
    from ..services.di import Container
    _has_container = True
except ImportError:
    _has_container = False

__all__ = [
    "Event",
    "EventHandler", 
    "ApplicationStarted",
    "ComponentActivated",
    "EventBus",
    "get_global_event_bus",
    "set_global_event_bus",
    "EventHandlerMixin",
    "event_handler",
    "StateStore",
    "ProjectManager",
]

if _has_container:
    __all__.append("Container")