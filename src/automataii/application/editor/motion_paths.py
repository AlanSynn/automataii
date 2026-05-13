from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import SupportsFloat, SupportsIndex, cast

Point = tuple[float, float]
MotionPath = tuple[Point, ...]
Listener = Callable[[Mapping[str, MotionPath]], None]
_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object) -> float | None:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _normalize_points(points: Iterable[Sequence[float]] | None) -> MotionPath:
    if not points:
        return ()
    normalized: list[Point] = []
    for pair in points:
        try:
            if isinstance(pair, str | bytes | bytearray) or len(pair) != 2:
                continue
            x = _finite_float(pair[0])
            y = _finite_float(pair[1])
        except (TypeError, IndexError):
            continue
        if x is None or y is None:
            continue
        normalized.append((x, y))
    return tuple(normalized)


class MotionPathRepository:
    """In-memory repository for editor motion paths with observer support."""

    def __init__(self) -> None:
        self._paths: dict[str, MotionPath] = {}
        self._listeners: list[Listener] = []

    # -- Subscription -----------------------------------------------------
    def subscribe(self, listener: Listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify(self) -> None:
        snapshot = self.snapshot()
        for listener in list(self._listeners):
            listener(snapshot)

    # -- Mutation ---------------------------------------------------------
    def replace(self, mapping: Mapping[str, Iterable[Sequence[float]]]) -> None:
        normalized: dict[str, MotionPath] = {}
        for name, points in mapping.items():
            if not isinstance(name, str) or not name:
                continue
            tuples = _normalize_points(points)
            if tuples:
                normalized[name] = tuples
        if normalized == self._paths:
            return
        self._paths = normalized
        self._notify()

    def upsert(self, part_name: str, points: Iterable[Sequence[float]] | None) -> None:
        if not isinstance(part_name, str) or not part_name:
            return
        tuples = _normalize_points(points)
        if not tuples:
            self.remove(part_name)
            return
        if self._paths.get(part_name) == tuples:
            return
        self._paths[part_name] = tuples
        self._notify()

    def remove(self, part_name: str) -> None:
        if part_name in self._paths:
            del self._paths[part_name]
            self._notify()

    def clear(self) -> None:
        if not self._paths:
            return
        self._paths.clear()
        self._notify()

    # -- Query ------------------------------------------------------------
    def snapshot(self) -> dict[str, MotionPath]:
        return {name: tuple(points) for name, points in self._paths.items()}
