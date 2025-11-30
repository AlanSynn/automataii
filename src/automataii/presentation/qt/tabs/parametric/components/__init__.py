"""
ParametricEditingManager extracted components.

This package contains modules extracted from ParametricEditingManager
using the LLM-native refactoring approach.

Extracted Modules:
- SimulationRegenerator: Mechanism simulation regeneration logic
- PhysicsSnapper: Physics constraint enforcement (Grashof, gear meshing)
- ParameterMapper: Parameter setup and coordinate transformation
- VisualUpdater: Real-time mechanism visual updates
- AnimationCoordinator: Animation control coordination
"""
from automataii.presentation.qt.tabs.parametric.components.animation_coordinator import (
    AnimationCoordinator,
)
from automataii.presentation.qt.tabs.parametric.components.parameter_mapper import (
    ParameterMapper,
    TransformConfig,
)
from automataii.presentation.qt.tabs.parametric.components.physics_snapper import (
    PhysicsSnapper,
    SnapResult,
)
from automataii.presentation.qt.tabs.parametric.components.simulation_regenerator import (
    SimulationRegenerator,
)
from automataii.presentation.qt.tabs.parametric.components.visual_updater import (
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
