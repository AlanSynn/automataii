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

from .base import Event, EventHandler
from .types import EventFilter, EventPriority, EventProcessingMode


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
        self._shutdown = False

        # Memory management
        self._cleanup_threshold = 100  # Cleanup after this many operations
        self._operation_count = 0
        self._weak_handlers = {}  # Track weak references to handlers
        self._handler_stats = defaultdict(int)  # Track handler usage
        self._max_handlers_per_type = 50  # Prevent unbounded growth

        # Statistics
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "handlers_called": 0,
            "errors": 0,
            "memory_cleanups": 0,
            "handlers_cleaned": 0,
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
            if self._shutdown:
                raise RuntimeError("EventBus has been shut down")
                
            if not callable(handler):
                raise ValueError("Handler must be callable")

            # Prevent unbounded growth of handlers
            if len(self._handlers[event_type]) >= self._max_handlers_per_type:
                self._logger.warning(
                    f"Too many handlers for {event_type.__name__} ({len(self._handlers[event_type])}). "
                    f"Cleaning up unused handlers."
                )
                self._cleanup_unused_handlers(event_type)

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
            # Handle both string event types and class event types
            if hasattr(event_type, '__name__'):
                event_name = event_type.__name__
            else:
                event_name = str(event_type)
            subscription_id = f"{event_name}_{id(handler)}"

            # Track handler for memory management
            self._handler_stats[subscription_id] = 0
            
            # Increment operation count and check for cleanup
            self._operation_count += 1
            if self._operation_count % self._cleanup_threshold == 0:
                self._perform_memory_cleanup()

            self._logger.debug(f"Subscribed {handler} to {event_name}")
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
                # Find by handler instance or function
                for i, h in enumerate(handlers):
                    if h == handler:
                        # Direct handler match
                        del handlers[i]
                        self._logger.debug(f"Unsubscribed {handler} from {event_type.__name__}")
                        return True
                    elif isinstance(h, FunctionEventHandler) and h.func == handler:
                        # Function handler match
                        del handlers[i]
                        self._logger.debug(f"Unsubscribed function {handler} from {event_type.__name__}")
                        return True

            return False

    def publish(self, event: Event, mode: EventProcessingMode | None = None) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event instance to publish
            mode: Processing mode override
        """
        if not self._enabled or self._shutdown:
            return

        mode = mode or self._processing_mode

        # Thread-safe event history and stats update
        with self._lock:
            try:
                self._event_history.append(event)
                self._stats["events_published"] += 1
                
                # Find handlers for this event type and its base classes
                handlers = self._get_handlers_for_event(event)
                
                if not handlers:
                    return
                    
                # Create a copy of handlers to avoid modification during iteration
                handlers_copy = handlers.copy()
                
            except Exception as e:
                self._logger.error(f"Error preparing event publication: {e}")
                return

        # Process outside the lock to avoid deadlocks
        if mode == EventProcessingMode.SYNC:
            self._process_sync(event, handlers_copy)
        elif mode == EventProcessingMode.ASYNC:
            self._process_async(event, handlers_copy)
        elif mode == EventProcessingMode.QUEUED:
            self._process_queued(event, handlers_copy)

    def _get_handlers_for_event(self, event: Event) -> list[EventHandler]:
        """Get all handlers that should process this event. Must be called within lock."""
        handlers = []
        event_type = type(event)

        try:
            # Get handlers for exact type and base classes
            for cls in event_type.__mro__:
                if cls in self._handlers:
                    # Create a copy to avoid concurrent modification
                    handlers.extend(self._handlers[cls].copy())

            # Apply filters safely
            filtered_handlers = []
            for handler in handlers:
                try:
                    if hasattr(handler, "filter_func") and handler.filter_func:
                        if handler.filter_func(event):
                            filtered_handlers.append(handler)
                    else:
                        filtered_handlers.append(handler)
                except Exception as e:
                    self._logger.error(f"Error applying filter for handler {handler}: {e}")
                    # Include handler anyway to avoid breaking the event system
                    filtered_handlers.append(handler)

            return filtered_handlers
            
        except Exception as e:
            self._logger.error(f"Error getting handlers for event {event_type.__name__}: {e}")
            return []

    def _process_sync(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event synchronously with thread safety."""
        if self._shutdown:
            return
            
        for handler in handlers:
            # Check if shutdown occurred during processing
            if self._shutdown:
                break
                
            try:
                handler.handle(event)
                
                # Thread-safe stats update
                with self._lock:
                    self._stats["handlers_called"] += 1
                    
                    # Track handler usage for memory management
                    handler_id = f"{type(event).__name__}_{id(handler)}"
                    if handler_id in self._handler_stats:
                        self._handler_stats[handler_id] += 1
                    
            except Exception as e:
                with self._lock:
                    self._stats["errors"] += 1
                self._logger.error(f"Error in handler {handler}: {e}", exc_info=True)

        # Thread-safe final stats update
        with self._lock:
            self._stats["events_processed"] += 1

    def _process_async(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event asynchronously with thread safety."""
        if self._shutdown:
            return

        async def process_handlers():
            for handler in handlers:
                # Check if shutdown occurred during processing
                if self._shutdown:
                    break
                    
                try:
                    if handler.is_async:
                        await handler.handle(event)
                    else:
                        handler.handle(event)
                    
                    # Thread-safe stats update
                    with self._lock:
                        self._stats["handlers_called"] += 1
                        
                        # Track handler usage for memory management
                        handler_id = f"{type(event).__name__}_{id(handler)}"
                        if handler_id in self._handler_stats:
                            self._handler_stats[handler_id] += 1
                        
                except Exception as e:
                    with self._lock:
                        self._stats["errors"] += 1
                    self._logger.error(f"Error in async handler {handler}: {e}", exc_info=True)

        # Schedule async processing safely
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.create_task(process_handlers())
            else:
                # Fallback to thread pool if loop is closed
                self._thread_pool.submit(lambda: self._process_sync(event, handlers))
        except RuntimeError:
            # No event loop, use thread pool
            if not self._shutdown:
                self._thread_pool.submit(lambda: self._process_sync(event, handlers))

        # Thread-safe final stats update
        with self._lock:
            self._stats["events_processed"] += 1

    def _process_queued(self, event: Event, handlers: list[EventHandler]) -> None:
        """Process event in background thread with thread safety."""
        if self._shutdown:
            return
            
        try:
            self._thread_pool.submit(self._process_sync, event, handlers)
            with self._lock:
                self._stats["events_processed"] += 1
        except RuntimeError:
            # Thread pool might be shut down
            if not self._shutdown:
                self._logger.warning("Thread pool unavailable, falling back to sync processing")
                self._process_sync(event, handlers)

    def replay_events(self, filter_func: EventFilter | None = None, start_index: int = 0) -> None:
        """
        Replay events from history.

        Args:
            filter_func: Optional filter for events to replay
            start_index: Index to start replay from
        """
        with self._lock:
            events_to_replay = list(self._event_history)[start_index:]

        for event in events_to_replay:
            if not filter_func or filter_func(event):
                self.publish(event)

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._event_history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            return self._stats.copy()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable event processing."""
        self._enabled = enabled

    def set_processing_mode(self, mode: EventProcessingMode) -> None:
        """Set default event processing mode."""
        self._processing_mode = mode

    def shutdown(self) -> None:
        """Shutdown the event bus and cleanup resources."""
        self._enabled = False
        self._shutdown = True
        self._thread_pool.shutdown(wait=True)
        with self._lock:
            self._handlers.clear()
            self._subscribers.clear()
            self._handler_stats.clear()
            self._weak_handlers.clear()
            self._event_history.clear()

    def _perform_memory_cleanup(self) -> None:
        """Perform comprehensive memory cleanup."""
        try:
            cleaned_count = 0
            
            # Clean up unused handlers
            for event_type in list(self._handlers.keys()):
                cleaned_count += self._cleanup_unused_handlers(event_type)
            
            # Clean up unused filter functions
            self._cleanup_unused_filters()
            
            # Clean up old event history if needed
            if len(self._event_history) > self._event_history.maxlen * 0.8:
                # Remove oldest 20% of events
                remove_count = int(len(self._event_history) * 0.2)
                for _ in range(remove_count):
                    if self._event_history:
                        self._event_history.popleft()
            
            # Force garbage collection
            import gc
            gc.collect()
            
            self._stats["memory_cleanups"] += 1
            self._stats["handlers_cleaned"] += cleaned_count
            
            if cleaned_count > 0:
                self._logger.debug(f"Memory cleanup completed. Cleaned {cleaned_count} handlers.")
                
        except Exception as e:
            self._logger.error(f"Error during memory cleanup: {e}")

    def _cleanup_unused_handlers(self, event_type: type[Event]) -> int:
        """Clean up unused handlers for a specific event type."""
        handlers = self._handlers[event_type]
        cleaned_count = 0
        
        # Remove handlers that haven't been used recently
        handlers_to_remove = []
        for i, handler in enumerate(handlers):
            handler_id = f"{event_type.__name__}_{id(handler)}"
            
            # Check if handler is still referenced elsewhere
            import weakref
            try:
                # Create weak reference to test if handler is still alive
                weak_ref = weakref.ref(handler)
                if weak_ref() is None:
                    handlers_to_remove.append(i)
                    continue
                    
                # Check usage statistics
                usage_count = self._handler_stats.get(handler_id, 0)
                if usage_count == 0 and hasattr(handler, '_created_time'):
                    # Handler created but never used - remove if old enough
                    import time
                    if time.time() - handler._created_time > 300:  # 5 minutes
                        handlers_to_remove.append(i)
                        
            except Exception:
                # If we can't check the handler, it's probably dead
                handlers_to_remove.append(i)
        
        # Remove handlers in reverse order to maintain indices
        for i in reversed(handlers_to_remove):
            removed_handler = handlers.pop(i)
            handler_id = f"{event_type.__name__}_{id(removed_handler)}"
            if handler_id in self._handler_stats:
                del self._handler_stats[handler_id]
            cleaned_count += 1
        
        return cleaned_count

    def _cleanup_unused_filters(self) -> None:
        """Clean up unused filter functions."""
        # Remove filters that are no longer referenced by any handler
        active_filters = set()
        for handlers in self._handlers.values():
            for handler in handlers:
                if hasattr(handler, 'filter_func') and handler.filter_func:
                    filter_id = id(handler.filter_func)
                    active_filters.add(filter_id)
        
        # Remove unused filters
        unused_filters = []
        for filter_id in list(self._filters.keys()):
            if filter_id not in active_filters:
                unused_filters.append(filter_id)
        
        for filter_id in unused_filters:
            del self._filters[filter_id]

    def get_memory_stats(self) -> dict[str, Any]:
        """Get detailed memory usage statistics."""
        with self._lock:
            total_handlers = sum(len(handlers) for handlers in self._handlers.values())
            stats = {
                "total_event_types": len(self._handlers),
                "total_handlers": total_handlers,
                "total_filters": len(self._filters),
                "event_history_size": len(self._event_history),
                "handler_stats_size": len(self._handler_stats),
                "average_handlers_per_type": total_handlers / max(1, len(self._handlers)),
                "memory_cleanups_performed": self._stats["memory_cleanups"],
                "handlers_cleaned_total": self._stats["handlers_cleaned"],
            }
            return stats


class FunctionEventHandler(EventHandler):
    """Wrapper for function-based event handlers."""

    def __init__(
        self,
        func: Callable[[Event], None],
        event_type: type[Event],
        priority: EventPriority = EventPriority.NORMAL,
        filter_func: EventFilter | None = None,
    ):
        import time
        self.func = func
        self._event_type = event_type
        self._priority = priority
        self.filter_func = filter_func
        self._created_time = time.time()  # Track creation time for memory management

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


def set_global_event_bus(event_bus: EventBus) -> None:
    """Set the global event bus instance."""
    global _global_event_bus
    _global_event_bus = event_bus
