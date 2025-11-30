"""
Decorators for event handling.
"""

import functools
from collections.abc import Callable
from typing import Any

from automataii.infrastructure.events.base import Event
from automataii.infrastructure.events.types import EventFilter, EventPriority


def event_handler(
    event_type: type[Event],
    priority: EventPriority = EventPriority.NORMAL,
    filter_func: EventFilter | None = None,
    auto_subscribe: bool = True
):
    """
    Decorator to mark a method as an event handler.

    Usage:
        @event_handler(ProjectLoaded)
        def on_project_loaded(self, event: ProjectLoaded):
            # Handle project loaded event
            pass
    """
    def decorator(func: Callable[[Any, Event], None]):
        func._event_type = event_type
        func._priority = priority
        func._filter_func = filter_func
        func._auto_subscribe = auto_subscribe

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def async_event_handler(
    event_type: type[Event],
    priority: EventPriority = EventPriority.NORMAL,
    filter_func: EventFilter | None = None,
    auto_subscribe: bool = True
):
    """
    Decorator to mark an async method as an event handler.

    Usage:
        @async_event_handler(ProjectLoaded)
        async def on_project_loaded(self, event: ProjectLoaded):
            # Handle project loaded event asynchronously
            await some_async_operation()
    """
    def decorator(func: Callable[[Any, Event], Any]):
        func._event_type = event_type
        func._priority = priority
        func._filter_func = filter_func
        func._auto_subscribe = auto_subscribe
        func._is_async = True

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator
