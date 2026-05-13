from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import SupportsFloat, SupportsIndex, cast

Point = tuple[float, float]
_FloatPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex


def _finite_float(value: object, default: float) -> float:
    try:
        result = float(cast(_FloatPayload, value))
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _finite_point(value: object) -> Point | None:
    if isinstance(value, str | bytes | bytearray) or not isinstance(value, Sequence):
        return None
    if len(value) < 2:
        return None
    x = _finite_float(value[0], math.nan)
    y = _finite_float(value[1], math.nan)
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x, y


@dataclass(frozen=True)
class EditorViewState:
    """Immutable view-model for EditorView."""

    mode: str = "select"
    selected_part: str | None = None
    drawing_path: bool = False
    path_points: tuple[Point, ...] = ()
    path_closed: bool = False
    zoom_level: float = 1.0
    pan_offset: Point = (0.0, 0.0)
    pinching: bool = False
    animation_time: float = 0.0
    animation_running: bool = False
    skeleton_visible: bool = True
    hovered_control: str | None = None
    raw_paths: Mapping[str, tuple[Point, ...]] | None = None
    corrected_paths: Mapping[str, tuple[Point, ...]] | None = None

    def with_mode(self, mode: str) -> EditorViewState:
        return replace(self, mode=mode)

    def with_selected_part(self, part: str | None) -> EditorViewState:
        return replace(self, selected_part=part)

    def start_path(self, start_points: Iterable[Point]) -> EditorViewState:
        points = tuple(
            point
            for raw_point in start_points
            if (point := _finite_point(raw_point)) is not None
        )
        return replace(self, drawing_path=True, path_points=points, path_closed=False)

    def append_point(self, point: Point) -> EditorViewState:
        if not self.drawing_path:
            raise RuntimeError("Cannot append point when drawing_path is False")
        normalized = _finite_point(point)
        if normalized is None:
            raise ValueError("Path point must contain two finite numbers")
        return replace(self, path_points=self.path_points + (normalized,))

    def finish_path(self, closed: bool) -> EditorViewState:
        if not self.drawing_path:
            return self
        return replace(self, drawing_path=False, path_closed=closed)

    def cancel_path(self) -> EditorViewState:
        return replace(self, drawing_path=False, path_points=(), path_closed=False)

    def with_zoom_level(self, zoom: float) -> EditorViewState:
        zoom_level = _finite_float(zoom, self.zoom_level)
        if zoom_level <= 0.0:
            zoom_level = self.zoom_level
        return replace(self, zoom_level=zoom_level)

    def with_pan_offset(self, offset: Point) -> EditorViewState:
        return replace(self, pan_offset=_finite_point(offset) or self.pan_offset)

    def with_pinching(self, pinching: bool) -> EditorViewState:
        return replace(self, pinching=pinching)

    def with_animation(self, running: bool, time: float | None = None) -> EditorViewState:
        if time is None:
            time = self.animation_time
        animation_time = _finite_float(time, self.animation_time)
        return replace(self, animation_running=running, animation_time=max(0.0, animation_time))

    def with_hovered_control(self, control_id: str | None) -> EditorViewState:
        return replace(self, hovered_control=control_id)

    def with_paths(
        self,
        raw: Mapping[str, Iterable[Point]] | None,
        corrected: Mapping[str, Iterable[Point]] | None,
    ) -> EditorViewState:
        def _convert(mapping: Mapping[str, Iterable[Point]] | None) -> Mapping[str, tuple[Point, ...]]:
            if not mapping:
                return {}
            converted: dict[str, tuple[Point, ...]] = {}
            for name, points in mapping.items():
                finite_points = tuple(
                    point
                    for raw_point in points
                    if (point := _finite_point(raw_point)) is not None
                )
                if finite_points:
                    converted[name] = finite_points
            return converted

        return replace(
            self,
            raw_paths=_convert(raw),
            corrected_paths=_convert(corrected),
        )


Listener = Callable[[EditorViewState], None]


class EditorViewStateStore:
    """State container with observer support for EditorView."""

    def __init__(self, initial_state: EditorViewState | None = None) -> None:
        self._state = initial_state or EditorViewState()
        self._listeners: list[Listener] = []

    @property
    def state(self) -> EditorViewState:
        return self._state

    def add_listener(self, listener: Listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _set_state(self, new_state: EditorViewState) -> None:
        if new_state is self._state:
            return
        self._state = new_state
        for listener in list(self._listeners):
            listener(self._state)

    # --- Mutators -----------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        self._set_state(self._state.with_mode(mode))

    def select_part(self, part: str | None) -> None:
        self._set_state(self._state.with_selected_part(part))

    def start_path(self, start_points: Iterable[Point]) -> None:
        self._set_state(self._state.start_path(start_points))

    def append_path_point(self, point: Point) -> None:
        self._set_state(self._state.append_point(point))

    def finish_path(self, closed: bool) -> None:
        self._set_state(self._state.finish_path(closed))

    def cancel_path(self) -> None:
        self._set_state(self._state.cancel_path())

    def set_zoom(self, zoom: float) -> None:
        self._set_state(self._state.with_zoom_level(zoom))

    def set_pan_offset(self, offset: Point) -> None:
        self._set_state(self._state.with_pan_offset(offset))

    def set_pinching(self, pinching: bool) -> None:
        self._set_state(self._state.with_pinching(pinching))

    def set_animation(self, running: bool, time: float | None = None) -> None:
        self._set_state(self._state.with_animation(running, time))

    def set_hovered_control(self, control_id: str | None) -> None:
        self._set_state(self._state.with_hovered_control(control_id))

    def update_paths(
        self,
        raw_paths: Mapping[str, Iterable[Point]] | None,
        corrected_paths: Mapping[str, Iterable[Point]] | None,
    ) -> None:
        self._set_state(self._state.with_paths(raw_paths, corrected_paths))
