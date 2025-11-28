"""
Pure Domain Kinematics module for Automataii.

This module contains framework-agnostic IK algorithms and data structures.

For Qt-coupled IK components (IKManager, FABRIK solver with Qt types),
use: automataii.presentation.qt.kinematics

Pure Domain Components:
- IKSolverCore: Core IK solving algorithms (no Qt dependency)
- IKAnimationController: Animation timing/easing (no Qt dependency)
- Point2D, IKSolution: Pure domain data types
"""
from .components.ik_solver_core import IKSolverCore, IKSolution, Point2D
from .components.ik_animation_controller import (
    IKAnimationController,
    TimingProfile,
    AnimationConfig,
)

__all__ = [
    # Pure domain IK solver
    "IKSolverCore",
    "IKSolution",
    "Point2D",
    # Animation controller
    "IKAnimationController",
    "TimingProfile",
    "AnimationConfig",
]
