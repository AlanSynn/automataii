"""
Decorators for event handling.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from automataii.infrastructure.events.base import Event
from automataii.infrastructure.events.types import EventFilter, EventPriority

F = TypeVar("F", bound=Callable[..., Any])


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
    def decorator(func: F) -> F:
        # Use setattr to dynamically add attributes without type errors
        func._event_type = event_type
        func._priority = priority
        func._filter_func = filter_func
        func._auto_subscribe = auto_subscribe

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Copy attributes to wrapper
        wrapper._event_type = event_type
        wrapper._priority = priority
        wrapper._filter_func = filter_func
        wrapper._auto_subscribe = auto_subscribe

        return cast(F, wrapper)

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
    def decorator(func: F) -> F:
        # Use setattr to dynamically add attributes without type errors
        func._event_type = event_type
        func._priority = priority
        func._filter_func = filter_func
        func._auto_subscribe = auto_subscribe
        func._is_async = True

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        # Copy attributes to wrapper
        wrapper._event_type = event_type
        wrapper._priority = priority
        wrapper._filter_func = filter_func
        wrapper._auto_subscribe = auto_subscribe
        wrapper._is_async = True

        return cast(F, wrapper)

    return decorator
