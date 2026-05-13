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
