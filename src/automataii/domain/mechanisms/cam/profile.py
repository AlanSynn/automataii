"""Pure cam profile builders shared by domain, infrastructure, and presentation.

Architecture note:
    This module is intentionally Qt-free.  It centralizes the numeric cam
    profile conventions that need to stay consistent across Design previews,
    manufacturing SVG export, and blueprint generation.
"""

from __future__ import annotations

import math
from typing import Any, SupportsFloat, SupportsIndex, cast

import numpy as np

_NumericPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_NumericPayload, value))
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


def _first_value(params: dict[str, Any], *names: str, default: object = None) -> object:
    for name in names:
        if name in params:
            return params[name]
    return default


def normalized_cam_timing(params: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return rise/high-dwell/return/low-dwell degrees for analytic pear cams."""
    rise_deg = _bounded_degrees(params.get("rise_deg"), 90.0)
    high_dwell_deg = _bounded_degrees(params.get("high_dwell_deg"), 60.0)
    return_deg = _bounded_degrees(params.get("return_deg"), 30.0)

    if "low_dwell_deg" in params or "dwell_low_deg" in params:
        low_dwell_deg = _bounded_degrees(
            _first_value(params, "low_dwell_deg", "dwell_low_deg"),
            180.0,
        )
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
    """Build an analytic pear-cam profile as finite ``(N, 2)`` points."""
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
    return np.stack([radius * np.cos(thetas), radius * np.sin(thetas)], axis=1).astype(float)


def build_pear_cam_profile_from_params(
    params: dict[str, Any],
    *,
    scale: float = 1.0,
    num_samples: int = 360,
) -> np.ndarray:
    """Build a scaled cam profile from Design/Foundry/manufacturing aliases."""
    scale = _positive_finite_float(scale, 1.0)
    if "cam_lobes" in params or "profile_harmonic" in params:
        return build_harmonic_cam_profile_from_params(params, scale=scale, num_samples=num_samples)
    rise_deg, high_dwell_deg, return_deg, low_dwell_deg = normalized_cam_timing(params)
    return build_pear_cam_profile(
        base_radius=_positive_finite_float(
            _first_value(params, "base_radius", "cam_radius", "base_radius_mm"),
            25.0,
        )
        * scale,
        eccentricity=_non_negative_finite_float(
            _first_value(params, "eccentricity", "cam_offset", "lift_mm", "eccentricity_mm"),
            10.0,
        )
        * scale,
        rise_deg=rise_deg,
        high_dwell_deg=high_dwell_deg,
        return_deg=return_deg,
        dwell_low_deg=low_dwell_deg,
        align_max_to_deg=_finite_float(
            _first_value(params, "align_max_deg", "align_max_to_deg"),
            90.0,
        ),
        num_samples=num_samples,
    )


def cam_profile_to_drawing_points(
    profile: np.ndarray,
    cx: float,
    cy: float,
) -> list[tuple[float, float]]:
    """Convert local cam profile points to the shared SVG/blueprint drawing plane.

    The Design tab keeps cam contact math in local coordinates where +Y is the
    follower support direction. Manufacturing SVG and blueprint drawings use
    the historical print orientation ``drawing_x = center_x + local_y`` and
    ``drawing_y = center_y - local_x``. Keeping that conversion here prevents
    the two export paths from drifting when cam profile generation changes.
    """
    rows = np.asarray(profile, dtype=float)
    if rows.ndim != 2 or rows.shape[0] < 3 or rows.shape[1] < 2:
        return []
    rows = rows[:, :2]
    if not np.isfinite(rows).all():
        return []
    center_x = _finite_float(cx, 0.0)
    center_y = _finite_float(cy, 0.0)
    return [(center_x + float(y), center_y - float(x)) for x, y in rows]


def build_harmonic_cam_profile_from_params(
    params: dict[str, Any],
    *,
    scale: float = 1.0,
    num_samples: int = 360,
) -> np.ndarray:
    """Build the Foundry/domain harmonic cam profile from shared aliases."""
    scale = _positive_finite_float(scale, 1.0)
    base_radius = (
        _positive_finite_float(
            _first_value(params, "base_radius", "cam_radius", "base_radius_mm"),
            60.0,
        )
        * scale
    )
    eccentricity = (
        _non_negative_finite_float(
            _first_value(params, "eccentricity", "cam_offset", "lift_mm", "eccentricity_mm"),
            20.0,
        )
        * scale
    )
    lobes_raw = _finite_float(params.get("cam_lobes"), 1.0)
    cam_lobes = int(lobes_raw) if lobes_raw >= 1.0 and float(lobes_raw).is_integer() else 1
    profile_harmonic = _finite_float(params.get("profile_harmonic"), 0.3)
    sample_count = max(3, int(_positive_finite_float(num_samples, 360.0)))

    thetas = np.linspace(0, 2 * np.pi, sample_count, endpoint=False)
    radii = (
        base_radius
        + eccentricity * np.cos(cam_lobes * thetas)
        + (eccentricity * profile_harmonic) * np.cos(2 * cam_lobes * thetas)
    )
    min_radius = max(1e-6, abs(base_radius) * 0.05)
    radii = np.maximum(radii, min_radius)
    return np.stack([radii * np.cos(thetas), radii * np.sin(thetas)], axis=1).astype(float)
