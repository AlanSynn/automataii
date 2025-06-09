"""Event bus implementation for decoupled communication."""

import logging
import weakref
from typing import Dict, List, Callable, Any, Type, Optional
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod
import threading


class Event(ABC):
    """Base class for all events.
    
    All events should inherit from this class and be dataclasses.
    """
    
    @property
    @abstractmethod
    def event_type(self) -> str:
        """Get the event type identifier."""
        pass
    
    @property
    def timestamp(self) -> datetime:
        """Get event timestamp."""
        if not hasattr(self, '_timestamp'):
            self._timestamp = datetime.now()
        return self._timestamp


class EventBus:
    """Central event bus for application-wide communication.
    
    This implementation uses weak references to prevent memory leaks
    and supports both synchronous and asynchronous event handling.
    """
    
    def __init__(self):
        # Use weak references to handlers to prevent memory leaks
        self._handlers: Dict[Type[Event], List[weakref.ref]] = {}
        self._lock = threading.RLock()
        self._event_history: List[Event] = []
        self._history_limit = 1000
        
        logging.info("EventBus initialized")
    
    def subscribe(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Function to call when event is published
        """
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            
            # Create weak reference to handler
            handler_ref = weakref.ref(handler)
            
            # Check if already subscribed
            for existing_ref in self._handlers[event_type]:
                if existing_ref() is handler:
                    logging.debug(f"EventBus: Handler already subscribed to {event_type.__name__}")
                    return
            
            self._handlers[event_type].append(handler_ref)
            logging.debug(f"EventBus: Subscribed handler to {event_type.__name__}")
    
    def unsubscribe(self, event_type: Type[Event], handler: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        with self._lock:
            if event_type not in self._handlers:
                return
            
            # Remove handler reference
            self._handlers[event_type] = [
                ref for ref in self._handlers[event_type]
                if ref() is not handler
            ]
            
            # Clean up empty handler lists
            if not self._handlers[event_type]:
                del self._handlers[event_type]
            
            logging.debug(f"EventBus: Unsubscribed handler from {event_type.__name__}")
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers.
        
        Args:
            event: Event instance to publish
        """
        event_type = type(event)
        
        with self._lock:
            # Add to history
            self._add_to_history(event)
            
            # Get handlers for this event type
            if event_type not in self._handlers:
                logging.debug(f"EventBus: No handlers for {event_type.__name__}")
                return
            
            # Clean up dead references and get live handlers
            live_handlers = []
            dead_refs = []
            
            for handler_ref in self._handlers[event_type]:
                handler = handler_ref()
                if handler is not None:
                    live_handlers.append(handler)
                else:
                    dead_refs.append(handler_ref)
            
            # Remove dead references
            for dead_ref in dead_refs:
                self._handlers[event_type].remove(dead_ref)
            
            # Clean up empty handler lists
            if not self._handlers[event_type]:
                del self._handlers[event_type]
        
        # Call handlers outside of lock to prevent deadlocks
        for handler in live_handlers:
            try:
                handler(event)
            except Exception as e:
                logging.error(
                    f"EventBus: Error in handler for {event_type.__name__}: {e}",
                    exc_info=True
                )
        
        logging.debug(
            f"EventBus: Published {event_type.__name__} to {len(live_handlers)} handlers"
        )
    
    def publish_async(self, event: Event) -> None:
        """Publish an event asynchronously.
        
        Args:
            event: Event instance to publish
        """
        # Create a thread to handle the event
        thread = threading.Thread(
            target=self.publish,
            args=(event,),
            daemon=True
        )
        thread.start()
    
    def clear_handlers(self, event_type: Optional[Type[Event]] = None) -> None:
        """Clear handlers for a specific event type or all handlers.
        
        Args:
            event_type: Event type to clear handlers for, or None for all
        """
        with self._lock:
            if event_type is None:
                self._handlers.clear()
                logging.info("EventBus: Cleared all handlers")
            elif event_type in self._handlers:
                del self._handlers[event_type]
                logging.info(f"EventBus: Cleared handlers for {event_type.__name__}")
    
    def get_handler_count(self, event_type: Type[Event]) -> int:
        """Get the number of handlers for an event type.
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of active handlers
        """
        with self._lock:
            if event_type not in self._handlers:
                return 0
            
            # Count live handlers
            count = 0
            for handler_ref in self._handlers[event_type]:
                if handler_ref() is not None:
                    count += 1
            
            return count
    
    def get_event_history(self, event_type: Optional[Type[Event]] = None, 
                         limit: int = 100) -> List[Event]:
        """Get event history.
        
        Args:
            event_type: Filter by event type, or None for all
            limit: Maximum number of events to return
            
        Returns:
            List of events in chronological order
        """
        with self._lock:
            if event_type is None:
                # Return all events
                return list(self._event_history[-limit:])
            else:
                # Filter by type
                filtered = [
                    e for e in self._event_history
                    if isinstance(e, event_type)
                ]
                return filtered[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._event_history.clear()
            logging.info("EventBus: Cleared event history")
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining size limit.
        
        Args:
            event: Event to add
        """
        self._event_history.append(event)
        
        # Trim history if needed
        if len(self._event_history) > self._history_limit:
            self._event_history = self._event_history[-self._history_limit:]
    
    def create_scoped_bus(self) -> 'ScopedEventBus':
        """Create a scoped event bus that forwards to this bus.
        
        Returns:
            New scoped event bus instance
        """
        return ScopedEventBus(self)


class ScopedEventBus(EventBus):
    """Scoped event bus that can be disposed of easily.
    
    Useful for components that need their own event handling
    but should also forward events to the main bus.
    """
    
    def __init__(self, parent_bus: Optional[EventBus] = None):
        super().__init__()
        self._parent_bus = parent_bus
        self._is_disposed = False
    
    def publish(self, event: Event) -> None:
        """Publish event to local and parent bus."""
        if self._is_disposed:
            return
        
        # Publish locally
        super().publish(event)
        
        # Forward to parent if exists
        if self._parent_bus:
            self._parent_bus.publish(event)
    
    def dispose(self) -> None:
        """Dispose of this scoped bus."""
        self._is_disposed = True
        self.clear_handlers()
        self._parent_bus = None
        logging.debug("ScopedEventBus: Disposed")