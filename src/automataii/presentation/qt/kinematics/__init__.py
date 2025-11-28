"""
Qt-coupled Kinematics module.

This module contains the Qt-dependent IK components that work directly
with Qt graphics items and scene coordinate systems.

For pure domain IK algorithms, see automataii.domain.kinematics.components.
"""
from .ik_manager import IKManager
from .fabraik_solver import solve_ik_fabrik_with_constraints, solve_ik_ccd

__all__ = [
    "IKManager",
    "solve_ik_fabrik_with_constraints",
    "solve_ik_ccd",
]
