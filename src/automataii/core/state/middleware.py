"""
Middleware system for state store.
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
import logging
import time

if TYPE_CHECKING:
    from .store import StateStore
    from .base import Action


class Middleware(ABC):
    """
    Base class for state store middleware.
    
    Middleware can intercept and modify actions before they reach the reducer.
    """
    
    @abstractmethod
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """
        Process action through middleware.
        
        Args:
            store: State store instance
            action: Action to process
            
        Returns:
            Processed action (may be modified)
        """
        pass


class LoggingMiddleware(Middleware):
    """
    Middleware that logs all actions.
    """
    
    def __init__(self, log_level: int = logging.DEBUG):
        self._logger = logging.getLogger("StateStore")
        self._log_level = log_level
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Log action details."""
        self._logger.log(
            self._log_level,
            f"Action dispatched: {action.type} with payload: {action.payload}"
        )
        return action


class PerformanceMiddleware(Middleware):
    """
    Middleware that measures action processing time.
    """
    
    def __init__(self, warn_threshold_ms: float = 100.0):
        self._logger = logging.getLogger("StateStore.Performance")
        self._warn_threshold = warn_threshold_ms / 1000.0  # Convert to seconds
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Measure action processing time."""
        start_time = time.perf_counter()
        
        # Process action (this is where the actual processing happens in the store)
        # For middleware, we just pass through, but we could modify the action here
        result_action = action
        
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        if duration > self._warn_threshold:
            self._logger.warning(
                f"Slow action detected: {action.type} took {duration*1000:.2f}ms"
            )
        else:
            self._logger.debug(
                f"Action {action.type} processed in {duration*1000:.2f}ms"
            )
        
        return result_action


class ValidationMiddleware(Middleware):
    """
    Middleware that validates actions before processing.
    """
    
    def __init__(self, strict_mode: bool = False):
        self._logger = logging.getLogger("StateStore.Validation")
        self._strict_mode = strict_mode
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Validate action."""
        errors = self._validate_action(action)
        
        if errors:
            error_msg = f"Invalid action {action.type}: {', '.join(errors)}"
            
            if self._strict_mode:
                raise ValueError(error_msg)
            else:
                self._logger.warning(error_msg)
        
        return action
    
    def _validate_action(self, action: 'Action') -> list[str]:
        """Validate action and return list of errors."""
        errors = []
        
        # Check action type
        if not action.type:
            errors.append("Action type is required")
        
        if not isinstance(action.type, str):
            errors.append("Action type must be string")
        
        # Additional validation can be added here
        
        return errors


class PersistenceMiddleware(Middleware):
    """
    Middleware that persists certain actions to storage.
    """
    
    def __init__(self, persist_actions: set[str] = None):
        self._logger = logging.getLogger("StateStore.Persistence")
        self._persist_actions = persist_actions or set()
        self._storage_backend = None  # Could be file, database, etc.
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Persist action if needed."""
        if action.type in self._persist_actions:
            self._persist_action(action)
        
        return action
    
    def _persist_action(self, action: 'Action') -> None:
        """Persist action to storage."""
        # Placeholder implementation
        self._logger.debug(f"Persisting action: {action.type}")
        # In real implementation, would save to file/database


class ThrottleMiddleware(Middleware):
    """
    Middleware that throttles rapid actions of the same type.
    """
    
    def __init__(self, throttle_ms: float = 100.0):
        self._logger = logging.getLogger("StateStore.Throttle")
        self._throttle_interval = throttle_ms / 1000.0
        self._last_action_times = {}
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Throttle rapid actions."""
        current_time = time.perf_counter()
        action_type = action.type
        
        last_time = self._last_action_times.get(action_type, 0)
        
        if current_time - last_time < self._throttle_interval:
            self._logger.debug(f"Throttling action: {action_type}")
            # Could return None to indicate action should be dropped
            # or modify the action to indicate it was throttled
            pass
        
        self._last_action_times[action_type] = current_time
        return action


class DebugMiddleware(Middleware):
    """
    Middleware that provides detailed debugging information.
    """
    
    def __init__(self):
        self._logger = logging.getLogger("StateStore.Debug")
        self._action_count = 0
    
    def process(self, store: 'StateStore', action: 'Action') -> 'Action':
        """Log detailed debug information."""
        self._action_count += 1
        
        # Log action details
        self._logger.debug(f"[{self._action_count}] Processing action: {action}")
        
        # Log current state (be careful with large states)
        current_state = store.state
        if hasattr(current_state, 'data') and len(str(current_state.data)) < 1000:
            self._logger.debug(f"Current state: {current_state.data}")
        
        # Log store statistics
        stats = store.get_stats()
        self._logger.debug(f"Store stats: {stats}")
        
        return action