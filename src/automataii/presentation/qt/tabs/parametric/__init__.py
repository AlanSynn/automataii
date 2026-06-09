"""
Parametric editing package.

This package contains the parametric editing system for mechanism design,
including the main manager and extracted components.

Main Classes:
- ParametricEditingManager: Main facade for parametric editing
- Components in .components/ subpackage
"""

from automataii.presentation.qt.tabs.parametric.components import (
    AnimationCoordinator,
    ParameterMapper,
    PhysicsSnapper,
    SimulationRegenerator,
    SnapResult,
    TransformConfig,
    VisualUpdater,
)

__all__ = [
    "AnimationCoordinator",
    "ParameterMapper",
    "PhysicsSnapper",
    "SimulationRegenerator",
    "SnapResult",
    "TransformConfig",
    "VisualUpdater",
]
