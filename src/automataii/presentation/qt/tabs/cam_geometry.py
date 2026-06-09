"""Shared cam profile/contact geometry for presentation-layer mechanisms.

This module intentionally defines the UI convention used by the Mechanism
Design Tab rather than a physical cam-normal contact solver: after any cam
rotation, contact is the scene-vertical support height ``[0, max_y]`` of the
profile, and the follower head/base is placed scene-vertically above that
contact by the rod length.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF

from automataii.domain.mechanisms.cam.profile import (
    build_harmonic_cam_profile_from_params,
    build_pear_cam_profile,
    build_pear_cam_profile_from_params,
    normalized_cam_timing,
)

__all__ = [
    "build_harmonic_cam_profile_from_params",
    "build_pear_cam_profile",
    "build_pear_cam_profile_from_params",
    "cam_contact_local_from_profile",
    "cam_contact_local_from_rotated_profile",
    "cam_contact_y_from_params",
    "cam_follower_base_scene",
    "cam_motion_angle",
    "cam_scene_unit_scale",
    "normalized_cam_timing",
    "rotate_cam_profile",
]


def cam_motion_angle(time: float, reverse_direction: object = False) -> float:
    """Return the CAM rotation phase with the shared reverse-direction contract."""
    try:
        angle = float(time)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(angle):
        return 0.0
    return -angle if bool(reverse_direction) else angle


def rotate_cam_profile(profile: np.ndarray, angle: float) -> np.ndarray:
    """Rotate a local cam profile by angle radians."""
    profile = np.asarray(profile, dtype=float)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated_x = profile[:, 0] * cos_a - profile[:, 1] * sin_a
    rotated_y = profile[:, 0] * sin_a + profile[:, 1] * cos_a
    return np.column_stack([rotated_x, rotated_y])


def cam_contact_local_from_rotated_profile(rotated_profile: np.ndarray) -> np.ndarray:
    """Return local contact point for the scene-vertical follower convention."""
    rows = np.asarray(rotated_profile, dtype=float)
    if rows.ndim != 2 or rows.shape[0] == 0 or rows.shape[1] < 2:
        return np.array([0.0, 0.0], dtype=float)
    return np.array([0.0, float(np.max(rows[:, 1]))], dtype=float)


def cam_contact_local_from_profile(profile: np.ndarray, angle: float = 0.0) -> np.ndarray:
    """Return local contact point after rotating the profile by angle."""
    return cam_contact_local_from_rotated_profile(rotate_cam_profile(profile, angle))


def cam_contact_y_from_params(
    params: dict[str, Any],
    *,
    scale: float = 1.0,
    angle: float = 0.0,
) -> float:
    """Return local contact Y for params using the same profile as visuals."""
    profile = build_pear_cam_profile_from_params(params, scale=scale)
    return float(cam_contact_local_from_profile(profile, angle)[1])


def cam_scene_unit_scale(to_scene: Callable[[np.ndarray], QPointF | None]) -> float:
    """Return scene pixels per local cam unit along +Y."""
    try:
        origin = to_scene(np.array([0.0, 0.0], dtype=float))
        y_unit = to_scene(np.array([0.0, 1.0], dtype=float))
        if origin is None or y_unit is None:
            return 1.0
        unit_scale = math.hypot(y_unit.x() - origin.x(), y_unit.y() - origin.y())
        return unit_scale if math.isfinite(unit_scale) and unit_scale > 0.0 else 1.0
    except Exception:
        logging.debug("Failed to measure cam scene unit scale; using neutral scale", exc_info=True)
        return 1.0


def cam_follower_base_scene(
    contact_scene: QPointF,
    scaled_rod_length: float,
    unit_scale: float,
    *,
    fixed_x: float | None = None,
) -> QPointF:
    """Return follower head/base in scene-vertical coordinates above contact."""
    follower_x = contact_scene.x() if fixed_x is None else fixed_x
    return QPointF(float(follower_x), float(contact_scene.y() - scaled_rod_length * unit_scale))
