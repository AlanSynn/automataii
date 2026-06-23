"""
Path Cache - LRU cache for computed mechanism motion paths
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from automataii.domain.mechanisms.core.protocols import Mechanism


@dataclass(frozen=True)
class PathCacheKey:
    mechanism_type: str
    parameters: tuple[tuple[str, float], ...]
    point_name: str
    angle_samples: int = 360

    @classmethod
    def from_dict(
        cls,
        mechanism_type: str,
        params: dict[str, float],
        point_name: str,
        angle_samples: int = 360,
    ) -> PathCacheKey:
        sorted_params = tuple(sorted(params.items()))
        return cls(
            mechanism_type=mechanism_type,
            parameters=sorted_params,
            point_name=point_name,
            angle_samples=angle_samples,
        )


@dataclass(frozen=True)
class CachedPath:
    points: tuple[tuple[float, float], ...]
    angles: tuple[float, ...]
    timestamp: float
    valid_angle_ranges: tuple[tuple[float, float], ...] = ()
    is_closed_cycle: bool = True


def select_angle_bounds(
    valid_angle_ranges: tuple[tuple[float, float], ...],
    preferred_angle: float,
    *,
    is_closed_cycle: bool = False,
) -> tuple[float, float] | None:
    """Pick the usable non-wrapping angle interval nearest the current UI angle."""
    if is_closed_cycle:
        return (0.0, 360.0)

    ranges = tuple(
        (float(start), float(end))
        for start, end in valid_angle_ranges
        if np.isfinite(start) and np.isfinite(end) and end >= start
    )
    if not ranges:
        return None

    angle = float(preferred_angle) % 360.0
    angle_variants = (angle, angle - 360.0, angle + 360.0)
    for start, end in ranges:
        if any(start <= variant <= end for variant in angle_variants):
            return (start, end)

    return min(
        ranges, key=lambda item: (_circular_distance_to_range(angle, item), -(item[1] - item[0]))
    )


def _circular_distance_to_range(angle: float, bounds: tuple[float, float]) -> float:
    start, end = bounds
    distances: list[float] = []
    for variant in (angle, angle - 360.0, angle + 360.0):
        if start <= variant <= end:
            return 0.0
        distances.extend((abs(variant - start), abs(variant - end)))
    return min(distances)


class PathCache:
    def __init__(self, max_size_bytes: int = 10 * 1024 * 1024):
        self._cache: OrderedDict[PathCacheKey, CachedPath] = OrderedDict()
        self._max_size_bytes = max_size_bytes
        self._current_size_bytes = 0
        self._hits = 0
        self._misses = 0

    def get(self, key: PathCacheKey) -> CachedPath | None:
        if key in self._cache:
            self._hits += 1
            self._cache.move_to_end(key)
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: PathCacheKey, path: CachedPath) -> None:
        estimated_size = self._estimate_size(path)
        existing = self._cache.pop(key, None)
        if existing is not None:
            self._current_size_bytes -= self._estimate_size(existing)

        if estimated_size > self._max_size_bytes:
            return

        while self._current_size_bytes + estimated_size > self._max_size_bytes and self._cache:
            oldest_key, oldest_path = self._cache.popitem(last=False)
            self._current_size_bytes -= self._estimate_size(oldest_path)

        self._cache[key] = path
        self._current_size_bytes += estimated_size

    def compute_and_cache(
        self,
        mechanism: Mechanism,
        params: dict[str, float],
        point_name: str,
        angle_samples: int = 360,
    ) -> CachedPath:
        if isinstance(angle_samples, bool) or not isinstance(angle_samples, int):
            raise ValueError(f"angle_samples must be an integer, got {type(angle_samples)}")
        if angle_samples <= 0:
            raise ValueError(f"angle_samples must be positive, got {angle_samples}")

        key = PathCacheKey.from_dict(
            mechanism.mechanism_type,
            params,
            point_name,
            angle_samples,
        )

        cached = self.get(key)
        if cached:
            return cached

        sample_angles = tuple(
            float(angle) for angle in np.linspace(0, 360, angle_samples, endpoint=False)
        )
        points: list[tuple[float, float]] = []
        valid_angles: list[float] = []
        valid_mask: list[bool] = []

        for angle in sample_angles:
            point: tuple[float, float] | None = None
            try:
                state = mechanism.compute_state(params, angle)
                position = state.positions.get(point_name)
                if position is not None and len(position) >= 2 and self._is_usable_state(state):
                    x = float(position[0])
                    y = float(position[1])
                    if np.isfinite(x) and np.isfinite(y):
                        point = (x, y)
            except Exception:
                point = None

            valid_mask.append(point is not None)
            if point is not None:
                points.append(point)
                valid_angles.append(angle)

        valid_angle_ranges = self._valid_angle_ranges(sample_angles, valid_mask)
        is_closed_cycle = len(valid_angles) == len(sample_angles)
        if is_closed_cycle:
            valid_angle_ranges = ((0.0, 360.0),)

        cached_path = CachedPath(
            points=tuple(points),
            angles=tuple(valid_angles),
            timestamp=time.time(),
            valid_angle_ranges=valid_angle_ranges,
            is_closed_cycle=is_closed_cycle,
        )

        self.put(key, cached_path)
        return cached_path

    def invalidate(self, mechanism_type: str) -> None:
        keys_to_remove = [key for key in self._cache if key.mechanism_type == mechanism_type]
        for key in keys_to_remove:
            path = self._cache.pop(key)
            self._current_size_bytes -= self._estimate_size(path)

    def clear(self) -> None:
        self._cache.clear()
        self._current_size_bytes = 0

    @staticmethod
    def _estimate_size(path: CachedPath) -> int:
        return (
            len(path.points) * 2 * 8
            + len(path.angles) * 8
            + len(path.valid_angle_ranges) * 2 * 8
            + 8
        )

    @staticmethod
    def _is_usable_state(state: object) -> bool:
        safety = getattr(state, "safety_status", None)
        level = getattr(safety, "level", None)
        level_name = str(getattr(level, "name", level)).upper()
        return level_name != "DANGER"

    @staticmethod
    def _valid_angle_ranges(
        angles: tuple[float, ...],
        valid_mask: list[bool],
    ) -> tuple[tuple[float, float], ...]:
        ranges: list[tuple[float, float]] = []
        start: float | None = None
        last: float | None = None

        for angle, valid in zip(angles, valid_mask, strict=True):
            if valid:
                if start is None:
                    start = angle
                last = angle
            elif start is not None and last is not None:
                ranges.append((start, last))
                start = None
                last = None

        if start is not None and last is not None:
            ranges.append((start, last))

        if len(ranges) > 1 and valid_mask[0] and valid_mask[-1]:
            _first_start, first_end = ranges[0]
            last_start, _last_end = ranges[-1]
            ranges = [(last_start - 360.0, first_end), *ranges[1:-1]]

        return tuple(ranges)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size_bytes(self) -> int:
        return self._current_size_bytes

    @property
    def entry_count(self) -> int:
        return len(self._cache)
