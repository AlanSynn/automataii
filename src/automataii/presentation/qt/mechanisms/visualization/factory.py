"""
Factory for creating mechanism visualizers.

This module provides a factory pattern implementation for creating
the appropriate visualizer based on mechanism type.
"""

import logging

from .base import MechanismVisualizer, VisualizationConfig


class VisualizerFactory:
    """Factory for creating mechanism visualizers."""

    _visualizers: dict[str, type[MechanismVisualizer]] = {}

    @classmethod
    def register(cls, mechanism_type: str, visualizer_class: type[MechanismVisualizer]) -> None:
        """
        Register a visualizer class for a mechanism type.

        Args:
            mechanism_type: Type identifier for the mechanism
            visualizer_class: Visualizer class to use for this type
        """
        cls._visualizers[mechanism_type] = visualizer_class
        logging.debug(f"Registered visualizer for mechanism type: {mechanism_type}")

    @classmethod
    def create(cls, mechanism_type: str,
               config: VisualizationConfig | None = None) -> MechanismVisualizer | None:
        """
        Create a visualizer for the specified mechanism type.

        Args:
            mechanism_type: Type of mechanism to visualize
            config: Optional visualization configuration

        Returns:
            Visualizer instance, or None if type not supported
        """
        visualizer_class = cls._visualizers.get(mechanism_type)

        if not visualizer_class:
            logging.warning(f"No visualizer registered for mechanism type: {mechanism_type}")
            return None

        return visualizer_class(config)

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """
        Get list of supported mechanism types.

        Returns:
            List of mechanism type identifiers
        """
        return list(cls._visualizers.keys())

    @classmethod
    def is_supported(cls, mechanism_type: str) -> bool:
        """
        Check if a mechanism type is supported.

        Args:
            mechanism_type: Type to check

        Returns:
            True if supported, False otherwise
        """
        return mechanism_type in cls._visualizers


# Auto-registration of built-in visualizers
def _register_builtin_visualizers():
    """Register built-in visualizers when module is imported."""
    try:
        from .visualizers import (
            CamVisualizer,
            FiveBarVisualizer,
            FourBarVisualizer,
            GearVisualizer,
            PlanetaryGearVisualizer,
            SixBarVisualizer,
        )

        VisualizerFactory.register("4_bar_linkage", FourBarVisualizer)
        VisualizerFactory.register("5_bar_linkage", FiveBarVisualizer)
        VisualizerFactory.register("6_bar_linkage", SixBarVisualizer)
        VisualizerFactory.register("cam", CamVisualizer)
        VisualizerFactory.register("gear", GearVisualizer)
        VisualizerFactory.register("planetary_gear", PlanetaryGearVisualizer)

        logging.info(f"Registered {len(VisualizerFactory._visualizers)} mechanism visualizers")

    except ImportError as e:
        logging.warning(f"Failed to register built-in visualizers: {e}")


# Register on module import
_register_builtin_visualizers()
