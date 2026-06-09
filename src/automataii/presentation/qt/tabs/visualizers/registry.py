"""
Mechanism Visualizer Registry - Central registry for mechanism visualizers.

Provides a single point of access for mechanism-specific visualizers,
eliminating the need for type-switch statements throughout the codebase.

Design Pattern: Registry + Singleton
SOLID Principle: Dependency Inversion - depend on abstractions (Protocol), not concretions
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .protocol import MechanismVisualizerProtocol

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

logger = logging.getLogger(__name__)


class MechanismVisualizerNotFoundError(Exception):
    """Raised when a visualizer for the requested mechanism type is not found."""

    pass


class MechanismVisualizerRegistry:
    """Registry for mechanism visualizers.

    Provides centralized access to mechanism-specific visualizers,
    replacing scattered type-switch statements with polymorphic dispatch.

    Usage:
        registry = MechanismVisualizerRegistry(scene)
        registry.register("4_bar_linkage", FourBarVisualizer)

        visualizer = registry.get("4_bar_linkage")
        items = visualizer.create_visuals(data)

    Thread Safety: Not thread-safe. Use one registry per thread/scene.
    """

    def __init__(self, scene: QGraphicsScene) -> None:
        """Initialize registry with a graphics scene.

        Args:
            scene: The QGraphicsScene to pass to visualizers
        """
        self._scene = scene
        self._visualizers: dict[str, MechanismVisualizerProtocol] = {}
        self._visualizer_classes: dict[str, type] = {}

    @property
    def scene(self) -> QGraphicsScene:
        """Get the graphics scene."""
        return self._scene

    def register(
        self,
        mechanism_type: str,
        visualizer_class: type,
    ) -> None:
        """Register a visualizer class for a mechanism type.

        Args:
            mechanism_type: The mechanism type identifier (e.g., '4_bar_linkage')
            visualizer_class: The visualizer class to instantiate for this type

        Note:
            Visualizers are lazily instantiated on first access.
        """
        if mechanism_type in self._visualizer_classes:
            logger.warning(f"Visualizer for '{mechanism_type}' already registered, overwriting")
        self._visualizer_classes[mechanism_type] = visualizer_class
        # Clear cached instance if re-registering
        self._visualizers.pop(mechanism_type, None)
        logger.debug(f"Registered visualizer for mechanism type: {mechanism_type}")

    def get(self, mechanism_type: str) -> MechanismVisualizerProtocol:
        """Get visualizer for a mechanism type.

        Args:
            mechanism_type: The mechanism type identifier

        Returns:
            Visualizer instance for the mechanism type

        Raises:
            MechanismVisualizerNotFoundError: If no visualizer is registered
        """
        # Return cached instance if available
        if mechanism_type in self._visualizers:
            return self._visualizers[mechanism_type]

        # Lazy instantiation
        if mechanism_type not in self._visualizer_classes:
            raise MechanismVisualizerNotFoundError(
                f"No visualizer registered for mechanism type '{mechanism_type}'. "
                f"Available types: {list(self._visualizer_classes.keys())}"
            )

        visualizer_class = self._visualizer_classes[mechanism_type]
        visualizer = visualizer_class(self._scene)
        self._visualizers[mechanism_type] = visualizer
        return visualizer

    def has(self, mechanism_type: str) -> bool:
        """Check if a visualizer is registered for the mechanism type.

        Args:
            mechanism_type: The mechanism type identifier

        Returns:
            True if a visualizer is registered
        """
        return mechanism_type in self._visualizer_classes

    def list_types(self) -> list[str]:
        """List all registered mechanism types.

        Returns:
            List of registered mechanism type identifiers
        """
        return list(self._visualizer_classes.keys())

    def create_visuals(
        self,
        mechanism_type: str,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        """Convenience method to create visuals for a mechanism type.

        Args:
            mechanism_type: The mechanism type identifier
            mechanism_data: Mechanism data dictionary
            transform_function: Optional coordinate transform
            **kwargs: Additional arguments passed to visualizer

        Returns:
            List of visual items
        """
        visualizer = self.get(mechanism_type)
        return visualizer.create_visuals(
            mechanism_data,
            transform_function=transform_function,
            **kwargs,
        )

    def update_visuals(
        self,
        mechanism_type: str,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[Any],
        **kwargs: Any,
    ) -> None:
        """Convenience method to update visuals for a mechanism type.

        Args:
            mechanism_type: The mechanism type identifier
            time: Animation time
            layer_data: Layer data
            visual_items: Visual items to update
            **kwargs: Additional arguments passed to visualizer
        """
        visualizer = self.get(mechanism_type)
        visualizer.update_visuals(time, layer_data, visual_items, **kwargs)

    def clear(self) -> None:
        """Clear all cached visualizer instances."""
        self._visualizers.clear()
