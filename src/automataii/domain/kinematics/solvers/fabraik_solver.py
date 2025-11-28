"""
DEPRECATED: FABRIK solver has moved to presentation layer.

The Qt-coupled FABRIK solver has been relocated to:
    automataii.presentation.qt.kinematics.fabraik_solver

This stub exists for backwards compatibility during migration.

For pure domain IK algorithms without Qt dependencies, use:
    automataii.domain.kinematics.components.ik_solver_core
"""
import warnings

warnings.warn(
    "fabraik_solver has moved to automataii.presentation.qt.kinematics. "
    "Update your imports to use the new location.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backwards compatibility
from automataii.presentation.qt.kinematics.fabraik_solver import (
    solve_ik_fabrik_with_constraints,
    solve_ik_ccd,
    calculate_bend_hint,
    get_world_rotation,
    MAX_BONE_LENGTH_DEVIATION,
)

__all__ = [
    "solve_ik_fabrik_with_constraints",
    "solve_ik_ccd",
    "calculate_bend_hint",
    "get_world_rotation",
    "MAX_BONE_LENGTH_DEVIATION",
]
