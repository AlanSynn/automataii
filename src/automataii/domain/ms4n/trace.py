"""Trace normalization and summary metrics for Lab/MS4N research episodes."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

TracePoint = tuple[int, float, float]
BoundingBox = tuple[float, float, float, float]
MotionDelta = tuple[float, float]
DOWNSAMPLE_RULE = "uniform_downsample_to_500"


class TraceValidationError(ValueError):
    """Raised when trace data cannot be represented safely in research exports."""


@dataclass(frozen=True)
class NormalizedTrace:
    """A deterministic bounded trace plus provenance metadata."""

    points: tuple[TracePoint, ...]
    original_point_count: int
    was_downsampled: bool
    sampling_rule: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "points": [list(point) for point in self.points],
            "original_point_count": self.original_point_count,
            "was_downsampled": self.was_downsampled,
            "sampling_rule": self.sampling_rule,
        }


@dataclass(frozen=True)
class TraceSummary:
    """Compact motion evidence that is safe for JSONL/CSV coding."""

    point_count: int
    original_point_count: int
    was_downsampled: bool
    sampling_rule: str | None
    path_length: float
    bbox: BoundingBox | None
    motion_delta: MotionDelta | None

    @property
    def bbox_width(self) -> float:
        if self.bbox is None:
            return 0.0
        return self.bbox[2] - self.bbox[0]

    @property
    def bbox_height(self) -> float:
        if self.bbox is None:
            return 0.0
        return self.bbox[3] - self.bbox[1]

    @property
    def bbox_area(self) -> float:
        return self.bbox_width * self.bbox_height

    def to_dict(self) -> dict[str, object]:
        return {
            "point_count": self.point_count,
            "original_point_count": self.original_point_count,
            "was_downsampled": self.was_downsampled,
            "sampling_rule": self.sampling_rule,
            "path_length": self.path_length,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "bbox_width": self.bbox_width,
            "bbox_height": self.bbox_height,
            "bbox_area": self.bbox_area,
            "motion_delta": list(self.motion_delta) if self.motion_delta is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TraceSummary:
        raw_bbox = data.get("bbox")
        bbox: BoundingBox | None = None
        if isinstance(raw_bbox, Sequence) and not isinstance(raw_bbox, str | bytes):
            if len(raw_bbox) == 4:
                bbox = (
                    _object_to_float(raw_bbox[0], "bbox[0]"),
                    _object_to_float(raw_bbox[1], "bbox[1]"),
                    _object_to_float(raw_bbox[2], "bbox[2]"),
                    _object_to_float(raw_bbox[3], "bbox[3]"),
                )
        raw_delta = data.get("motion_delta")
        motion_delta = None
        if isinstance(raw_delta, Sequence) and not isinstance(raw_delta, str | bytes):
            if len(raw_delta) == 2:
                motion_delta = (float(raw_delta[0]), float(raw_delta[1]))
        return cls(
            point_count=_object_to_int(data.get("point_count", 0), "point_count"),
            original_point_count=_object_to_int(
                data.get("original_point_count", data.get("point_count", 0)),
                "original_point_count",
            ),
            was_downsampled=bool(data.get("was_downsampled", False)),
            sampling_rule=(
                str(data["sampling_rule"]) if data.get("sampling_rule") is not None else None
            ),
            path_length=_object_to_float(data.get("path_length", 0.0), "path_length"),
            bbox=bbox,
            motion_delta=motion_delta,
        )


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TraceValidationError(f"{label} must be a finite number; got {value!r}")
    finite_value = float(value)
    if not math.isfinite(finite_value):
        raise TraceValidationError(f"{label} must be finite; got {value!r}")
    return finite_value


def _object_to_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TraceValidationError(f"{label} must be numeric; got {value!r}")
    try:
        result = float(value)
    except ValueError as exc:
        raise TraceValidationError(f"{label} must be numeric; got {value!r}") from exc
    if not math.isfinite(result):
        raise TraceValidationError(f"{label} must be finite; got {value!r}")
    return result


def _object_to_int(value: object, label: str) -> int:
    result = _object_to_float(value, label)
    if not result.is_integer():
        raise TraceValidationError(f"{label} must be an integer; got {value!r}")
    return int(result)


def _trace_point(point: object, index: int) -> TracePoint:
    if isinstance(point, str | bytes | bytearray):
        raise TraceValidationError(f"trace point {index} must be a 3-item sequence")
    if not isinstance(point, Sequence) or len(point) != 3:
        raise TraceValidationError(f"trace point {index} must be a 3-item sequence")
    frame_raw = point[0]
    if isinstance(frame_raw, bool) or not isinstance(frame_raw, int | float):
        raise TraceValidationError(f"trace point {index} frame must be numeric")
    frame_float = _finite_number(frame_raw, f"trace point {index} frame")
    if not frame_float.is_integer():
        raise TraceValidationError(f"trace point {index} frame must be an integer")
    x = _finite_number(point[1], f"trace point {index} x")
    y = _finite_number(point[2], f"trace point {index} y")
    return (int(frame_float), x, y)


def validate_trace_points(points: Sequence[object]) -> tuple[TracePoint, ...]:
    return cast(
        tuple[TracePoint, ...],
        tuple(_trace_point(point, index) for index, point in enumerate(points)),
    )


def normalize_trace_points(points: Sequence[object], max_points: int = 500) -> NormalizedTrace:
    """Validate and deterministically bound traces while preserving first/last points."""
    if max_points < 2:
        raise TraceValidationError("max_points must be at least 2")
    validated = validate_trace_points(points)
    original_count = len(validated)
    if original_count <= max_points:
        return NormalizedTrace(
            points=validated,
            original_point_count=original_count,
            was_downsampled=False,
            sampling_rule=None,
        )

    step = (original_count - 1) / (max_points - 1)
    indices = [min(original_count - 1, int(math.floor(i * step))) for i in range(max_points)]
    indices[-1] = original_count - 1
    bounded = tuple(validated[index] for index in indices)
    return NormalizedTrace(
        points=bounded,
        original_point_count=original_count,
        was_downsampled=True,
        sampling_rule=DOWNSAMPLE_RULE,
    )


def summarize_trace(points: Sequence[object], max_points: int = 500) -> TraceSummary:
    normalized = normalize_trace_points(points, max_points=max_points)
    bounded = normalized.points
    if not bounded:
        return TraceSummary(
            point_count=0,
            original_point_count=normalized.original_point_count,
            was_downsampled=normalized.was_downsampled,
            sampling_rule=normalized.sampling_rule,
            path_length=0.0,
            bbox=None,
            motion_delta=None,
        )

    xs = [point[1] for point in bounded]
    ys = [point[2] for point in bounded]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    path_length = 0.0
    for previous, current in zip(bounded, bounded[1:], strict=False):
        path_length += math.hypot(current[1] - previous[1], current[2] - previous[2])
    first = bounded[0]
    last = bounded[-1]
    motion_delta = (last[1] - first[1], last[2] - first[2])
    return TraceSummary(
        point_count=len(bounded),
        original_point_count=normalized.original_point_count,
        was_downsampled=normalized.was_downsampled,
        sampling_rule=normalized.sampling_rule,
        path_length=path_length,
        bbox=bbox,
        motion_delta=motion_delta,
    )


def compare_trace_summaries(
    before: TraceSummary | None,
    after: TraceSummary | None,
) -> dict[str, object]:
    """Return a small deterministic delta summary for the Trace Duel view/export."""
    if before is None and after is None:
        return {"available": False}
    if before is None:
        assert after is not None
        return {"available": True, "change": "after_only", "after_point_count": after.point_count}
    if after is None:
        return {
            "available": True,
            "change": "before_only",
            "before_point_count": before.point_count,
        }
    return {
        "available": True,
        "change": "before_after",
        "point_count_delta": after.point_count - before.point_count,
        "path_length_delta": after.path_length - before.path_length,
        "bbox_area_delta": after.bbox_area - before.bbox_area,
        "motion_delta_before": list(before.motion_delta)
        if before.motion_delta is not None
        else None,
        "motion_delta_after": list(after.motion_delta) if after.motion_delta is not None else None,
    }
