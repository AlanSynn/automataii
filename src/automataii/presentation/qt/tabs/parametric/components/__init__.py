"""
ParametricEditingManager extracted components.

This package contains modules extracted from ParametricEditingManager
using the LLM-native refactoring approach.

Extracted Modules:
- SimulationRegenerator: Mechanism simulation regeneration logic
- PhysicsSnapper: Physics constraint enforcement (Grashof, gear meshing)
"""
from automataii.presentation.qt.tabs.parametric.components.simulation_regenerator import SimulationRegenerator
from automataii.presentation.qt.tabs.parametric.components.physics_snapper import PhysicsSnapper

__all__ = [
    "SimulationRegenerator",
    "PhysicsSnapper",
]
