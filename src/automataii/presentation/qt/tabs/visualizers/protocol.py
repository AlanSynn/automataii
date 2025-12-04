"""
Mechanism Visualizer Protocol - Interface for polymorphic mechanism visualization.

This module defines the Protocol that all mechanism visualizers must implement,
enabling the replacement of 68+ type-switch statements with registry-based dispatch.

Design Pattern: Strategy (via Protocol)
SOLID Principle: Open/Closed - new mechanisms can be added without modifying existing code
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene


@runtime_checkable
class MechanismVisualizerProtocol(Protocol):
    """Protocol defining the interface for mechanism visualizers.

    All mechanism-specific visualizers must implement this interface to be
    usable with the MechanismVisualizerRegistry.

    Responsibilities:
    - Create visual items for a mechanism
    - Update visuals during animation
    - Regenerate simulation data from parameters

    Time Complexity: Implementation-dependent, typically O(n) where n = number of joints
    """

    @property
    def mechanism_type(self) -> str:
        """Return the mechanism type identifier (e.g., '4_bar_linkage', 'cam')."""
        ...

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation of the mechanism.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state
            transform_function: Optional coordinate transform function
            **kwargs: Additional visualizer-specific arguments

        Returns:
            List of QGraphicsItem objects representing the mechanism
        """
        ...

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update visual items for animation frame.

        Args:
            time: Animation time in radians (0 to 2π for one cycle)
            layer_data: Layer data containing mechanism state
            visual_items: List of visual items to update
            **kwargs: Additional visualizer-specific arguments
        """
        ...

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data from mechanism parameters.

        Args:
            params: Mechanism parameters
            **kwargs: Additional simulation options

        Returns:
            Dictionary containing simulation results (joint_positions, etc.)
        """
        ...


class BaseMechanismVisualizer:
    """Base class providing common functionality for mechanism visualizers.

    Subclasses should override mechanism_type property and implement
    the required methods from MechanismVisualizerProtocol.
    """

    def __init__(self, scene: QGraphicsScene) -> None:
        """Initialize the visualizer with a graphics scene.

        Args:
            scene: The QGraphicsScene where visual items will be added
        """
        self._scene = scene

    @property
    def scene(self) -> QGraphicsScene:
        """Get the graphics scene."""
        return self._scene

    @property
    def mechanism_type(self) -> str:
        """Return the mechanism type identifier. Override in subclasses."""
        raise NotImplementedError("Subclasses must override mechanism_type")

    def _get_transform_function(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
    ) -> Any | None:
        """Get the coordinate transform function from data or parameter.

        Args:
            mechanism_data: Mechanism data that may contain transform_function
            transform_function: Explicitly provided transform function

        Returns:
            Transform function or None
        """
        if transform_function is not None:
            return transform_function
        return mechanism_data.get("transform_function")
