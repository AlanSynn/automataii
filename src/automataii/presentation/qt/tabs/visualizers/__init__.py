"""
Mechanism Visualizers Package - Polymorphic mechanism visualization system.

This package provides a registry-based approach to mechanism visualization,
replacing scattered type-switch statements with polymorphic dispatch.

Architecture:
    - MechanismVisualizerProtocol: Interface all visualizers must implement
    - MechanismVisualizerRegistry: Central registry for visualizer lookup
    - *Visualizer classes: Mechanism-specific implementations

Usage:
    from automataii.presentation.qt.tabs.visualizers import (
        MechanismVisualizerRegistry,
        FourBarVisualizer,
        CamVisualizer,
        GearVisualizer,
    )

    # Create registry and register visualizers
    registry = MechanismVisualizerRegistry(scene)
    registry.register("4_bar_linkage", FourBarVisualizer)
    registry.register("cam", CamVisualizer)

    # Use registry for polymorphic dispatch
    visuals = registry.create_visuals("4_bar_linkage", mechanism_data)

Design Patterns:
    - Strategy: Each visualizer implements the Protocol
    - Registry: Central lookup eliminates type-switches
    - Factory: Registry lazily instantiates visualizers
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .cam_visualizer import CamVisualizer
from .gear_visualizer import GearVisualizer, PlanetaryGearVisualizer
from .linkage_visualizer import FiveBarVisualizer, FourBarVisualizer, SixBarVisualizer
from .protocol import BaseMechanismVisualizer, MechanismVisualizerProtocol
from .registry import MechanismVisualizerNotFoundError, MechanismVisualizerRegistry

__all__ = [
    # Protocol and Base
    "MechanismVisualizerProtocol",
    "BaseMechanismVisualizer",
    # Registry
    "MechanismVisualizerRegistry",
    "MechanismVisualizerNotFoundError",
    # Linkage Visualizers
    "FourBarVisualizer",
    "FiveBarVisualizer",
    "SixBarVisualizer",
    # Cam Visualizer
    "CamVisualizer",
    # Gear Visualizers
    "GearVisualizer",
    "PlanetaryGearVisualizer",
]


def create_default_registry(scene: QGraphicsScene) -> MechanismVisualizerRegistry:
    """Create a registry with all default visualizers registered.

    Args:
        scene: The QGraphicsScene for visual items

    Returns:
        Configured MechanismVisualizerRegistry

    Usage:
        registry = create_default_registry(self.scene)
        visuals = registry.create_visuals(mechanism_type, data)
    """
    from PyQt6.QtWidgets import QGraphicsScene

    registry = MechanismVisualizerRegistry(scene)

    # Register all visualizers
    registry.register("4_bar_linkage", FourBarVisualizer)
    registry.register("5_bar_linkage", FiveBarVisualizer)
    registry.register("6_bar_linkage", SixBarVisualizer)
    registry.register("cam", CamVisualizer)
    registry.register("gear", GearVisualizer)
    registry.register("planetary_gear", PlanetaryGearVisualizer)

    return registry


if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene
