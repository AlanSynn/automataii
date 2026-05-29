"""Qt-free conversion helpers for Lab trace snapshots."""

from __future__ import annotations

import math
from collections.abc import Sequence

from automataii.domain.ms4n.trace import TracePoint, TraceValidationError, validate_trace_points


def points_to_trace_points(
    points: Sequence[object], start_frame: int = 0
) -> tuple[TracePoint, ...]:
    """Convert JSON-safe x/y point sequences into `(frame, x, y)` tuples."""
    raw_points: list[tuple[int, float, float]] = []
    for offset, point in enumerate(points):
        x, y = _extract_xy(point)
        raw_points.append((start_frame + offset, x, y))
    trace_points: tuple[TracePoint, ...] = validate_trace_points(raw_points)
    return trace_points


def _extract_xy(point: object) -> tuple[float, float]:
    if isinstance(point, Sequence) and not isinstance(point, str | bytes | bytearray):
        if len(point) != 2:
            raise TraceValidationError("point sequence must contain exactly x and y")
        return (_finite(point[0], "x"), _finite(point[1], "y"))
    raise TraceValidationError(f"Unsupported trace point object: {type(point).__name__}")


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TraceValidationError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise TraceValidationError(f"{label} must be finite")
    return result
