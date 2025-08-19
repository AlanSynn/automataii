"""
Central state store implementation.
"""

import logging
import threading
from collections import deque
from collections.abc import Callable
from typing import Any, Generic, TypeVar
from weakref import WeakSet

from .base import Action, ActionTypes, Reducer, State
from .middleware import Middleware

StateType = TypeVar('StateType')
Subscriber = Callable[[State[StateType]], None]


class StateStore(Generic[StateType]):
    """
    Central state store with Redux-like pattern.
    
    Features:
    - Immutable state updates
    - Middleware support
    - Time-travel debugging
    - Subscription management
    - Thread-safe operations
    """

    def __init__(
        self,
        initial_state: StateType,
        reducer: Reducer[StateType],
        middleware: list[Middleware] = None,
        max_history: int = 100
    ):
        self._current_state = State(initial_state).freeze()
        self._reducer = reducer
        self._middleware = middleware or []
        self._subscribers: WeakSet[Subscriber] = WeakSet()
        self._lock = threading.RLock()
        self._logger = logging.getLogger(__name__)

        # History for time-travel debugging
        self._history: deque[tuple[State[StateType], Action]] = deque(maxlen=max_history)
        self._future: deque[tuple[State[StateType], Action]] = deque()
        self._history_enabled = True

        # Dispatch tracking
        self._dispatching = False
        self._dispatch_count = 0

        # Initialize with init action
        self.dispatch(Action(type=ActionTypes.INIT))

    @property
    def state(self) -> State[StateType]:
        """Get current state (immutable)."""
        with self._lock:
            return self._current_state

    def dispatch(self, action: Action) -> Action:
        """
        Dispatch an action to update state.
        
        Args:
            action: Action to dispatch
            
        Returns:
            The dispatched action (possibly modified by middleware)
        """
        if self._dispatching:
            raise RuntimeError("Cannot dispatch while already dispatching")

        with self._lock:
            self._dispatching = True
            self._dispatch_count += 1

            try:
                # Apply middleware chain
                final_action = self._apply_middleware(action)

                # Store previous state for history
                previous_state = self._current_state

                # Apply reducer
                new_state = self._reducer.reduce(self._current_state, final_action)

                # Update current state
                self._current_state = new_state.freeze()

                # Update history
                if self._history_enabled and previous_state != new_state:
                    self._history.append((previous_state, final_action))
                    self._future.clear()  # Clear future when new action is dispatched

                # Notify subscribers
                self._notify_subscribers()

                self._logger.debug(f"Dispatched action: {final_action.type}")
                return final_action

            finally:
                self._dispatching = False

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        """
        Subscribe to state changes.
        
        Args:
            subscriber: Function to call when state changes
            
        Returns:
            Unsubscribe function
        """
        with self._lock:
            self._subscribers.add(subscriber)

            def unsubscribe():
                try:
                    self._subscribers.discard(subscriber)
                except:
                    pass  # Already removed or weakref expired

            return unsubscribe

    def _apply_middleware(self, action: Action) -> Action:
        """Apply middleware chain to action."""
        current_action = action

        for middleware in self._middleware:
            current_action = middleware.process(self, current_action)

        return current_action

    def _notify_subscribers(self) -> None:
        """Notify all subscribers of state change."""
        # Copy subscribers to avoid modification during iteration
        subscribers = list(self._subscribers)

        for subscriber in subscribers:
            try:
                subscriber(self._current_state)
            except Exception as e:
                self._logger.error(f"Error in subscriber: {e}", exc_info=True)

    # Time travel debugging methods

    def can_undo(self) -> bool:
        """Check if undo is possible."""
        with self._lock:
            return len(self._history) > 1  # Keep initial state

    def can_redo(self) -> bool:
        """Check if redo is possible."""
        with self._lock:
            return len(self._future) > 0

    def undo(self) -> bool:
        """
        Undo the last action.
        
        Returns:
            True if undo was performed
        """
        if not self.can_undo():
            return False

        with self._lock:
            # Move current state to future
            current_action = self._history[-1][1] if self._history else None
            if current_action:
                self._future.appendleft((self._current_state, current_action))

            # Restore previous state
            self._history.pop()
            if self._history:
                self._current_state = self._history[-1][0]

            # Notify subscribers
            self._notify_subscribers()
            self._logger.debug("Undid last action")
            return True

    def redo(self) -> bool:
        """
        Redo the next action.
        
        Returns:
            True if redo was performed
        """
        if not self.can_redo():
            return False

        with self._lock:
            # Get next state from future
            next_state, next_action = self._future.popleft()

            # Move current state to history
            self._history.append((self._current_state, next_action))

            # Set next state as current
            self._current_state = next_state

            # Notify subscribers
            self._notify_subscribers()
            self._logger.debug("Redid action")
            return True

    def get_history(self) -> list[tuple[State[StateType], Action]]:
        """Get action history."""
        with self._lock:
            return list(self._history)

    def replay_from_history(self, index: int = 0) -> None:
        """
        Replay actions from a specific point in history.
        
        Args:
            index: History index to replay from
        """
        if not (0 <= index < len(self._history)):
            raise IndexError("Invalid history index")

        with self._lock:
            self._history_enabled = False

            try:
                # Reset to initial state
                if self._history:
                    initial_state = self._history[0][0]
                    self._current_state = initial_state

                    # Replay actions from index
                    for i in range(index, len(self._history)):
                        state, action = self._history[i]
                        new_state = self._reducer.reduce(self._current_state, action)
                        self._current_state = new_state.freeze()

                # Notify subscribers
                self._notify_subscribers()

            finally:
                self._history_enabled = True

    def set_history_enabled(self, enabled: bool) -> None:
        """Enable or disable history tracking."""
        with self._lock:
            self._history_enabled = enabled
            if not enabled:
                self._history.clear()
                self._future.clear()

    def clear_history(self) -> None:
        """Clear action history."""
        with self._lock:
            self._history.clear()
            self._future.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        with self._lock:
            return {
                'dispatch_count': self._dispatch_count,
                'subscriber_count': len(self._subscribers),
                'history_size': len(self._history),
                'future_size': len(self._future),
                'history_enabled': self._history_enabled,
                'current_action_type': self._history[-1][1].type if self._history else None
            }


# Global store instance
_global_store: StateStore | None = None


def get_global_store() -> StateStore | None:
    """Get the global state store."""
    return _global_store


def set_global_store(store: StateStore) -> None:
    """Set the global state store."""
    global _global_store
    _global_store = store
