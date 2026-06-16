"""Shared helpers for reading mechanism parameters with alias support.

Factory-created and imported mechanisms can carry both current internal names
(``coupler_point_x``/``coupler_point_y``) and legacy dataset aliases
(``p_x``/``p_y``).  These helpers intentionally treat explicit zero as a valid
value instead of falling through to an alias.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import SupportsFloat, SupportsIndex, cast

from automataii.shared.physical_kit import physical_profile_from_params

FloatLike = str | bytes | bytearray | memoryview | SupportsFloat | SupportsIndex


def finite_float(value: object, default: float) -> float:
    """Return ``value`` as a finite float, or ``default`` when invalid."""
    try:
        result = float(cast(FloatLike, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def positive_finite_float(value: object, default: float) -> float:
    """Return ``value`` as a positive finite float, or ``default`` when invalid."""
    result = finite_float(value, default)
    return result if result > 0.0 else default


def param_value(params: Mapping[str, object], *names: str, default: object = None) -> object:
    """Return the first present, non-``None`` parameter value among ``names``."""
    for name in names:
        if name in params and params[name] is not None:
            return params[name]
    return default


def finite_param(params: Mapping[str, object], *names: str, default: float) -> float:
    """Return the first present parameter alias as a finite float."""
    return finite_float(param_value(params, *names, default=default), default)


def positive_finite_param(params: Mapping[str, object], *names: str, default: float) -> float:
    """Return the first present parameter alias as a positive finite float."""
    return positive_finite_float(param_value(params, *names, default=default), default)


def truthy_param(value: object) -> bool:
    """Return a robust boolean interpretation for numeric/string mechanism flags."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off"}
    return not math.isclose(finite_float(value, 0.0), 0.0, abs_tol=1e-9)


def gear_linkage_pin_radius(params: Mapping[str, object], driven_radius: float) -> float:
    """Clamp a gear+linkage crank pin to stay inside the driven gear's usable body."""
    safe_radius = positive_finite_float(driven_radius, 1.0)
    profile = physical_profile_from_params(params)
    default_radius = min(safe_radius * 0.72, safe_radius)
    requested = positive_finite_param(params, "linkage_pin_radius", default=default_radius)
    hole_radius = float(profile.hole_diameter_mm) / 2.0
    max_radius = float(max(1.0, safe_radius - hole_radius))
    return float(min(requested, max_radius))


def gear_linkage_arm_length(params: Mapping[str, object]) -> float:
    """Return the gear+linkage output arm length with the physical-grid default."""
    default_length = positive_finite_param(params, "grid_cell_cm", default=2.0) * 20.0
    return float(positive_finite_param(params, "linkage_arm_length", default=default_length))
