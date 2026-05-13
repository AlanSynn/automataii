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
        estimated_size = len(path.points) * 2 * 8 + len(path.angles) * 8 + 8
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

        angles = tuple(float(angle) for angle in np.linspace(0, 360, angle_samples, endpoint=False))
        points = []

        for angle in angles:
            try:
                state = mechanism.compute_state(params, angle)
                position = state.positions.get(point_name)
                if position is None or len(position) < 2:
                    points.append((0.0, 0.0))
                else:
                    points.append((float(position[0]), float(position[1])))
            except Exception:
                points.append((0.0, 0.0))

        cached_path = CachedPath(
            points=tuple(points),
            angles=angles,
            timestamp=time.time(),
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
        return len(path.points) * 2 * 8 + len(path.angles) * 8 + 8

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
