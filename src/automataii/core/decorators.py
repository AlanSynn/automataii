"""
Decorators for event handling.
"""

import functools
from collections.abc import Callable
from typing import Any

from .base import Event
from .event_bus import get_global_event_bus
from .types import EventFilter, EventPriority


def event_handler(
    event_type: type[Event],
    priority: EventPriority = EventPriority.NORMAL,
    filter_func: EventFilter | None = None,
    auto_subscribe: bool = True,
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
    auto_subscribe: bool = True,
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


class EventHandlerMixin:
    """
    Mixin class that automatically subscribes decorated methods to events.

    Usage:
        class MyComponent(EventHandlerMixin):
            @event_handler(ProjectLoaded)
            def on_project_loaded(self, event: ProjectLoaded):
                # This will be automatically subscribed
                pass
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_subscriptions = []
        self._auto_subscribe_handlers()

    def _auto_subscribe_handlers(self):
        """Automatically subscribe methods decorated with @event_handler."""
        event_bus = get_global_event_bus()

        for attr_name in dir(self):
            attr = getattr(self, attr_name)

            if (
                callable(attr)
                and hasattr(attr, "_event_type")
                and hasattr(attr, "_auto_subscribe")
                and attr._auto_subscribe
            ):
                # Use the bound method directly as the handler
                subscription_id = event_bus.subscribe(
                    attr._event_type,
                    attr,  # Use the bound method directly
                    getattr(attr, "_priority", EventPriority.NORMAL),
                    getattr(attr, "_filter_func", None),
                )

                self._event_subscriptions.append((attr._event_type, subscription_id))

    def unsubscribe_all_events(self):
        """Unsubscribe all automatically subscribed event handlers."""
        event_bus = get_global_event_bus()

        for event_type, subscription_id in self._event_subscriptions:
            event_bus.unsubscribe(event_type, subscription_id)

        self._event_subscriptions.clear()

    def __del__(self):
        """Cleanup subscriptions on object destruction."""
        try:
            self.unsubscribe_all_events()
        except Exception:
            pass  # Ignore errors during cleanup


def subscribes_to(*event_types: type[Event]):
    """
    Class decorator to mark which events a class subscribes to.
    Useful for documentation and introspection.
    """

    def decorator(cls):
        cls._subscribed_events = event_types
        return cls

    return decorator
