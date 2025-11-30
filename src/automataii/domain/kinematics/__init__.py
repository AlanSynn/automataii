"""
Pure Domain Kinematics module for Automataii.

This module contains framework-agnostic IK algorithms and data structures.

For Qt-coupled IK components (IKManager, FABRIK solver with Qt types),
use: automataii.presentation.qt.kinematics

Pure Domain Components:
- IKSolverCore: Core IK solving algorithms (no Qt dependency)
- IKAnimationController: Animation timing/easing (no Qt dependency)
- Point2D, IKSolution: Pure domain data types
- Joint configuration: Mappings and limb definitions
"""
from .components.ik_animation_controller import (
    AnimationConfig,
    IKAnimationController,
    TimingProfile,
)
from .components.ik_solver_core import IKSolution, IKSolverCore, Point2D
from .joint_config import (
    EFFECTOR_JOINTS,
    IK_JOINT_TO_SOURCE_NAME,
    IK_PART_TO_ACTUAL_PART,
    LIMB_CHAINS,
    LIMB_CONFIGS,
    SOURCE_NAME_TO_IK_JOINT,
    LimbConfig,
    get_actual_part_name,
    get_limb_for_effector,
    get_source_joint_name,
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
    # Joint configuration
    "IK_PART_TO_ACTUAL_PART",
    "IK_JOINT_TO_SOURCE_NAME",
    "SOURCE_NAME_TO_IK_JOINT",
    "LIMB_CHAINS",
    "LIMB_CONFIGS",
    "EFFECTOR_JOINTS",
    "LimbConfig",
    "get_limb_for_effector",
    "get_actual_part_name",
    "get_source_joint_name",
]
