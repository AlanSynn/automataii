# src/automataii/domain/kinematics/core/base_component.py

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
import logging


class KinematicsComponent(ABC):
    """
    Base class for all kinematics components.

    Provides common functionality for error handling, logging, and state management.
    Domain layer version without UI dependencies.
    """

    def __init__(self, name: str = "KinematicsComponent"):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._is_initialized = False
        self._last_error: Optional[str] = None
        
        # Event callbacks (for UI integration)
        self._error_callback: Optional[Callable[[str], None]] = None
        self._state_change_callback: Optional[Callable[[dict], None]] = None

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the component.

        Returns:
            True if initialization was successful
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources used by the component."""
        pass

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """
        Get the current state of the component.

        Returns:
            Dictionary containing component state
        """
        pass

    @abstractmethod
    def set_state(self, state: dict[str, Any]) -> bool:
        """
        Set the component state.

        Args:
            state: Dictionary containing new state

        Returns:
            True if state was set successfully
        """
        pass

    def is_initialized(self) -> bool:
        """Check if the component is initialized."""
        return self._is_initialized

    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for error events."""
        self._error_callback = callback

    def set_state_change_callback(self, callback: Callable[[dict], None]) -> None:
        """Set callback for state change events."""
        self._state_change_callback = callback

    def _emit_error(self, message: str) -> None:
        """Emit an error event with the given message."""
        self._last_error = message
        self.logger.error(message)
        if self._error_callback:
            self._error_callback(message)

    def _emit_state_changed(self) -> None:
        """Emit a state changed event with current state."""
        state = self.get_state()
        self.logger.debug(f"State changed: {state}")
        if self._state_change_callback:
            self._state_change_callback(state)
