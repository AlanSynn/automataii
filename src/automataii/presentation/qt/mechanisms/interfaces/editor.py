"""
Base interface for mechanism editors.
Defines the contract for interactive editing capabilities.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsScene


@dataclass
class HandleConfig:
    """Configuration for an interactive handle."""

    handle_id: str
    position: QPointF
    param_name: str
    tooltip: str
    size: float = 12.0
    color: QColor = field(default_factory=lambda: QColor(255, 100, 0))
    hover_color: QColor = field(default_factory=lambda: QColor(255, 150, 50))
    constraints: dict[str, Any] | None = None
    callback: Callable | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.handle_id,
            "position": (self.position.x(), self.position.y()),
            "param_name": self.param_name,
            "tooltip": self.tooltip,
            "size": self.size,
            "constraints": self.constraints,
        }


class EditorInterface(ABC):
    """
    Abstract base class for mechanism editors.

    Provides interactive editing capabilities for mechanisms
    through drag handles and real-time updates.
    """

    @abstractmethod
    def __init__(self, mechanism_id: str, scene: QGraphicsScene):
        """
        Initialize editor.

        Args:
            mechanism_id: Unique mechanism identifier
            scene: Graphics scene for handles
        """
        pass

    @abstractmethod
    def create_handles(self, mechanism_data: dict[str, Any]) -> list[HandleConfig]:
        """
        Create interactive handles for the mechanism.

        Args:
            mechanism_data: Mechanism configuration

        Returns:
            List of handle configurations
        """
        pass

    @abstractmethod
    def on_handle_moved(self, handle_id: str, new_position: QPointF) -> dict[str, Any]:
        """
        Handle movement callback.

        Args:
            handle_id: Identifier of moved handle
            new_position: New handle position

        Returns:
            Updated parameters
        """
        pass

    @abstractmethod
    def update_handle_positions(self, simulation_data: dict[str, Any]) -> None:
        """
        Update handle positions based on simulation.

        Args:
            simulation_data: Current simulation state
        """
        pass

    @abstractmethod
    def validate_handle_position(self, handle_id: str, position: QPointF) -> bool:
        """
        Validate if handle position is valid.

        Args:
            handle_id: Handle identifier
            position: Proposed position

        Returns:
            True if position is valid
        """
        pass

    @abstractmethod
    def get_handle_constraints(self, handle_id: str) -> dict[str, Any]:
        """
        Get constraints for a specific handle.

        Args:
            handle_id: Handle identifier

        Returns:
            Constraint definitions
        """
        pass

    @abstractmethod
    def show_handles(self) -> None:
        """Show all handles."""
        pass

    @abstractmethod
    def hide_handles(self) -> None:
        """Hide all handles."""
        pass

    @abstractmethod
    def remove_handles(self) -> None:
        """Remove all handles from scene."""
        pass

    @property
    @abstractmethod
    def is_editing(self) -> bool:
        """Check if currently in edit mode."""
        pass
