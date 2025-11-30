"""
Core mechanism domain types and protocols.

This module provides the foundational types for mechanism computation.
"""

from automataii.domain.mechanisms.core.cache import (
    clear_all_caches,
    compute_cam_contact_radius,
    compute_cam_profile_points,
    compute_fourbar_geometry,
    compute_grashof_condition,
    compute_transmission_angle,
    get_cache_stats,
)
from automataii.domain.mechanisms.core.protocols import Mechanism
from automataii.domain.mechanisms.core.state import (
    ForceType,
    ForceVector,
    MechanismState,
    RenderConfig,
    SafetyLevel,
    SafetyStatus,
)

__all__ = [
    # Protocols
    "Mechanism",
    # State types
    "MechanismState",
    "RenderConfig",
    "SafetyLevel",
    "SafetyStatus",
    "ForceType",
    "ForceVector",
    # Cached computation functions
    "compute_fourbar_geometry",
    "compute_grashof_condition",
    "compute_cam_profile_points",
    "compute_cam_contact_radius",
    "compute_transmission_angle",
    "get_cache_stats",
    "clear_all_caches",
]
