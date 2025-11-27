"""
IKManager extracted components.

This package contains modules extracted from IKManager
using the LLM-native refactoring approach.

Extracted Modules:
- IKSolverCore: Single-bone and two-bone IK solving algorithms
- IKAnimationController: Animation timing and easing functions
"""
from automataii.domain.kinematics.components.ik_solver_core import IKSolverCore
from automataii.domain.kinematics.components.ik_animation_controller import IKAnimationController

__all__ = [
    "IKSolverCore",
    "IKAnimationController",
]
