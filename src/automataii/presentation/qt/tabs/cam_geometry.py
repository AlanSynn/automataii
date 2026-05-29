"""Shared cam profile/contact geometry for presentation-layer mechanisms.

This module intentionally defines the UI convention used by the Mechanism
Design Tab rather than a physical cam-normal contact solver: after any cam
rotation, contact is the scene-vertical support height ``[0, max_y]`` of the
profile, and the follower head/base is placed scene-vertically above that
contact by the rod length.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, cast

import numpy as np
from PyQt6.QtCore import QPointF


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(Any, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result > 0.0 else default


def _non_negative_finite_float(value: object, default: float) -> float:
    result = _finite_float(value, default)
    return result if result >= 0.0 else default


def _bounded_degrees(value: object, default: float) -> float:
    return max(0.0, min(360.0, _finite_float(value, default)))


def normalized_cam_timing(params: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return rise/high-dwell/return/low-dwell degrees matching visual factory rules."""
    rise_deg = _bounded_degrees(params.get("rise_deg"), 90.0)
    high_dwell_deg = _bounded_degrees(params.get("high_dwell_deg"), 60.0)
    return_deg = _bounded_degrees(params.get("return_deg"), 30.0)

    if "low_dwell_deg" in params:
        low_dwell_deg = _bounded_degrees(params.get("low_dwell_deg"), 180.0)
    else:
        low_dwell_deg = max(0.0, 360.0 - (rise_deg + high_dwell_deg + return_deg))

    total = rise_deg + high_dwell_deg + return_deg + low_dwell_deg
    if total > 360.0:
        scale = 360.0 / max(1e-6, total)
        rise_deg *= scale
        high_dwell_deg *= scale
        return_deg *= scale
        low_dwell_deg *= scale

    return rise_deg, high_dwell_deg, return_deg, low_dwell_deg


def build_pear_cam_profile(
    *,
    base_radius: float,
    eccentricity: float,
    rise_deg: float = 90.0,
    high_dwell_deg: float = 60.0,
    return_deg: float | None = None,
    dwell_low_deg: float = 180.0,
    align_max_to_deg: float = 90.0,
    num_samples: int = 360,
) -> np.ndarray:
    """Build the analytic pear-cam profile used by the Qt visual factory."""
    base_radius = _positive_finite_float(base_radius, 25.0)
    eccentricity = _non_negative_finite_float(eccentricity, 10.0)
    rise_deg = _bounded_degrees(rise_deg, 90.0)
    high_dwell_deg = _bounded_degrees(high_dwell_deg, 60.0)
    dwell_low_deg = _bounded_degrees(dwell_low_deg, 180.0)
    if return_deg is None:
        return_deg = 360.0 - (rise_deg + high_dwell_deg + dwell_low_deg)
    return_deg = _bounded_degrees(return_deg, 30.0)

    total = rise_deg + high_dwell_deg + return_deg + dwell_low_deg
    if total > 360.0:
        scale = 360.0 / max(1e-6, total)
        rise_deg *= scale
        high_dwell_deg *= scale
        return_deg *= scale
        dwell_low_deg *= scale

    sample_count = max(3, int(_positive_finite_float(num_samples, 360.0)))
    rise = np.deg2rad(rise_deg)
    dwell_high = np.deg2rad(high_dwell_deg)
    fall = np.deg2rad(return_deg)

    theta0 = np.deg2rad(_finite_float(align_max_to_deg, 90.0))
    seg1_end = theta0 + rise
    seg2_end = seg1_end + dwell_high
    seg3_end = seg2_end + fall

    thetas = np.linspace(0, 2 * np.pi, sample_count, endpoint=False)
    s = np.zeros_like(thetas)
    for index, theta in enumerate(thetas):
        rel = (theta - theta0) % (2 * np.pi) + theta0
        if rel < seg1_end:
            u = (rel - theta0) / rise if rise > 0 else 1.0
            s[index] = 0.5 * (1 - np.cos(np.pi * u))
        elif rel < seg2_end:
            s[index] = 1.0
        elif rel < seg3_end:
            u = (rel - seg2_end) / fall if fall > 0 else 1.0
            s[index] = 0.5 * (1 + np.cos(np.pi * u))
        else:
            s[index] = 0.0

    radius = base_radius + eccentricity * s
    points = np.stack([radius * np.cos(thetas), radius * np.sin(thetas)], axis=1)
    return points.astype(float)


def build_pear_cam_profile_from_params(
    params: dict[str, Any],
    *,
    scale: float = 1.0,
    num_samples: int = 360,
) -> np.ndarray:
    """Build a scaled pear-cam profile from mechanism parameter aliases."""
    scale = _positive_finite_float(scale, 1.0)
    rise_deg, high_dwell_deg, return_deg, low_dwell_deg = normalized_cam_timing(params)
    return build_pear_cam_profile(
        base_radius=_positive_finite_float(params.get("base_radius"), 25.0) * scale,
        eccentricity=_non_negative_finite_float(params.get("eccentricity"), 10.0) * scale,
        rise_deg=rise_deg,
        high_dwell_deg=high_dwell_deg,
        return_deg=return_deg,
        dwell_low_deg=low_dwell_deg,
        align_max_to_deg=_finite_float(params.get("align_max_deg"), 90.0),
        num_samples=num_samples,
    )


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
