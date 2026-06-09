"""
Middleware system for state store.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.infrastructure.state.base import Action
    from automataii.infrastructure.state.store import StateStore


class Middleware(ABC):
    """
    Base class for state store middleware.

    Middleware can intercept and modify actions before they reach the reducer.
    """

    @abstractmethod
    def process(self, store: "StateStore", action: "Action") -> "Action":
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

    def process(self, store: "StateStore", action: "Action") -> "Action":
        """Log action details."""
        self._logger.log(
            self._log_level, f"Action dispatched: {action.type} with payload: {action.payload}"
        )
        return action


class PersistenceMiddleware(Middleware):
    """
    Middleware that persists certain actions to storage.
    """

    def __init__(self, persist_actions: set[str] = None):
        self._logger = logging.getLogger("StateStore.Persistence")
        self._persist_actions = persist_actions or set()
        self._storage_backend = None  # Could be file, database, etc.

    def process(self, store: "StateStore", action: "Action") -> "Action":
        """Persist action if needed."""
        if action.type in self._persist_actions:
            self._persist_action(action)

        return action

    def _persist_action(self, action: "Action") -> None:
        """Persist action to storage."""
        # Placeholder implementation
        self._logger.debug(f"Persisting action: {action.type}")
        # In real implementation, would save to file/database
