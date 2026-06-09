"""
Central event bus implementation.
"""

import asyncio
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from weakref import WeakSet

from automataii.infrastructure.events.base import Event, EventHandler
from automataii.infrastructure.events.types import EventFilter, EventPriority, EventProcessingMode


class EventBus:
    """
    Central event bus for decoupled communication.

    Features:
    - Type-safe event publishing and subscription
    - Priority-based handler ordering
    - Async event processing
    - Event filtering and routing
    - Event replay for debugging
    - Weak references to prevent memory leaks
    """

    def __init__(self, max_history: int = 1000, thread_pool_size: int = 4):
        self._handlers: defaultdict[type[Event], list[EventHandler]] = defaultdict(list)
        self._filters: dict[str, EventFilter] = {}
        self._event_history: deque[Event] = deque(maxlen=max_history)
        self._subscribers: defaultdict[type[Event], WeakSet] = defaultdict(WeakSet)
        self._processing_mode = EventProcessingMode.SYNC
        self._thread_pool = ThreadPoolExecutor(max_workers=thread_pool_size)
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)
        self._enabled = True

        # Statistics
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "handlers_called": 0,
            "errors": 0,
        }

    def subscribe(
        self,
        event_type: type[Event],
        handler: EventHandler | Callable[[Event], None],
        priority: EventPriority = EventPriority.NORMAL,
        filter_func: EventFilter | None = None,
    ) -> str:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The event class to subscribe to
            handler: Handler function or EventHandler instance
            priority: Handler priority (higher = called first)
            filter_func: Optional filter to apply before calling handler

        Returns:
            Subscription ID for later unsubscription
        """
        with self._lock:
            if not callable(handler):
                raise ValueError("Handler must be callable")

            # Wrap function handlers in EventHandler
            if not isinstance(handler, EventHandler):
                handler = FunctionEventHandler(handler, event_type, priority, filter_func)

            # Insert handler in priority order
            handlers = self._handlers[event_type]
            insert_index = 0
            for i, existing_handler in enumerate(handlers):
                if existing_handler.priority < handler.priority:
                    insert_index = i
                    break
                insert_index = i + 1

            handlers.insert(insert_index, handler)
            subscription_id = f"{event_type.__name__}_{id(handler)}"

            self._logger.debug(f"Subscribed {handler} to {event_type.__name__}")
            return subscription_id

    def unsubscribe(self, event_type: type[Event], handler: EventHandler | str) -> bool:
        """
        Unsubscribe from events.

        Args:
            event_type: The event type to unsubscribe from
            handler: Handler instance or subscription ID

        Returns:
            True if handler was found and removed
        """
        with self._lock:
            handlers = self._handlers[event_type]

            if isinstance(handler, str):
                # Find by subscription ID
                for i, h in enumerate(handlers):
                    if f"{event_type.__name__}_{id(h)}" == handler:
                        del handlers[i]
                        self._logger.debug(f"Unsubscribed {handler} from {event_type.__name__}")
                        return True
            else:
                # Find by handler instance or wrapped function
                for i, h in enumerate(list(handlers)):
                    if h is handler:
                        del handlers[i]
                        self._logger.debug(f"Unsubscribed {handler} from {event_type.__name__}")
                        return True
                    if isinstance(h, FunctionEventHandler) and getattr(h, "func", None) is handler:
                        del handlers[i]
                        self._logger.debug(f"Unsubscribed {handler} from {event_type.__name__}")
                        return True

            return False

    def publish(self, event: Event, mode: EventProcessingMode | None = None) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event instance to publish
            mode: Processing mode override
        """
        if not self._enabled:
            return

        mode = mode or self._processing_mode

        with self._lock:
            self._event_history.append(event)
            self._stats["events_published"] += 1

        # Find handlers for this event type and its base classes
        handlers = self._get_handlers_for_event(event)

        if not handlers:
            return

        if mode == EventProcessingMode.SYNC:
            self._process_sync(event, handlers)
        elif mode == EventProcessingMode.ASYNC:
            self._process_async(event, handlers)
        elif mode == EventProcessingMode.QUEUED:
            self._process_queued(event, handlers)

    def _get_handlers_for_event(self, event: Event) -> list[EventHandler]:
        """Get all handlers that should process this event."""
        handlers = []
        event_type = type(event)

        # Get handlers for exact type and base classes
        for cls in event_type.__mro__:
            if cls in self._handlers:
                handlers.extend(self._handlers[cls])

        # Apply filters
        filtered_handlers = []
        for handler in handlers:
            if hasattr(handler, "filter_func") and handler.filter_func:
                if handler.filter_func(event):
                    filtered_handlers.append(handler)
            else:
                filtered_handlers.append(handler)

        return filtered_handlers

    def _process_sync(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event synchronously."""
        for handler in handlers:
            try:
                handler.handle(event)
                self._stats["handlers_called"] += 1
            except Exception as e:
                self._stats["errors"] += 1
                self._logger.error(f"Error in handler {handler}: {e}", exc_info=True)

        self._stats["events_processed"] += 1

    def _process_async(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event asynchronously."""

        async def process_handlers():
            for handler in handlers:
                try:
                    if handler.is_async:
                        await handler.handle(event)
                    else:
                        handler.handle(event)
                    self._stats["handlers_called"] += 1
                except Exception as e:
                    self._stats["errors"] += 1
                    self._logger.error(f"Error in async handler {handler}: {e}", exc_info=True)

        # Schedule async processing
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(process_handlers())
        except RuntimeError:
            # No event loop, use thread pool
            self._thread_pool.submit(lambda: self._process_sync(event, handlers))

        self._stats["events_processed"] += 1

    def _process_queued(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event in background thread."""
        self._thread_pool.submit(self._process_sync, event, handlers)
        self._stats["events_processed"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            return self._stats.copy()

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the event bus and clean up resources.

        Args:
            wait: If True, wait for pending tasks to complete
        """
        self._enabled = False
        try:
            self._thread_pool.shutdown(wait=wait)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
        self._logger.info("EventBus shutdown complete")

    def __del__(self) -> None:
        """Ensure thread pool is cleaned up on garbage collection."""
        try:
            if hasattr(self, "_thread_pool"):
                self._thread_pool.shutdown(wait=False)
        except Exception:
            pass  # Suppress errors during garbage collection


class FunctionEventHandler(EventHandler):
    """Wrapper for function-based event handlers."""

    def __init__(
        self,
        func: Callable[[Event], None],
        event_type: type[Event],
        priority: EventPriority = EventPriority.NORMAL,
        filter_func: EventFilter | None = None,
    ):
        self.func = func
        self._event_type = event_type
        self._priority = priority
        self.filter_func = filter_func

    def handle(self, event: Event) -> None:
        self.func(event)

    @property
    def event_type(self) -> type[Event]:
        return self._event_type

    @property
    def priority(self) -> int:
        return self._priority

    def __repr__(self) -> str:
        return f"FunctionEventHandler({self.func.__name__})"


# Global event bus instance
_global_event_bus: EventBus | None = None


def get_global_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus
