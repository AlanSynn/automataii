from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, Mapping, Tuple


@dataclass(frozen=True)
class IKState:
    """Immutable snapshot of IK-related state."""

    skeleton_data: Mapping[str, object] | None = None
    project_parts: Mapping[str, object] | None = None
    animation_running: bool = False
    animation_time: float = 0.0
    animation_duration_ms: int = 3000
    timing_profile: str = "linear"
    mechanism_targets: Mapping[str, Tuple[float, float]] = None

    def with_skeleton(self, skeleton: Mapping[str, object] | None) -> "IKState":
        return replace(self, skeleton_data=skeleton)

    def with_project_parts(self, parts: Mapping[str, object]) -> "IKState":
        return replace(self, project_parts=dict(parts))

    def start_animation(self) -> "IKState":
        return replace(self, animation_running=True, animation_time=0.0)

    def stop_animation(self) -> "IKState":
        return replace(self, animation_running=False)

    def set_animation_time(self, time: float) -> "IKState":
        return replace(self, animation_time=float(time))

    def set_animation_duration(self, duration_ms: int) -> "IKState":
        return replace(self, animation_duration_ms=int(duration_ms))

    def set_timing_profile(self, profile: str) -> "IKState":
        return replace(self, timing_profile=profile)

    def with_mechanism_target(self, part: str, pos: Tuple[float, float]) -> "IKState":
        targets = dict(self.mechanism_targets or {})
        targets[part] = (float(pos[0]), float(pos[1]))
        return replace(self, mechanism_targets=targets)

    def without_mechanism_target(self, part: str | None = None) -> "IKState":
        if part is None:
            return replace(self, mechanism_targets={})
        targets = dict(self.mechanism_targets or {})
        targets.pop(part, None)
        return replace(self, mechanism_targets=targets)


Listener = Callable[[IKState], None]


class IKStateStore:
    """Observable state container for IK workflows."""

    def __init__(self, initial: IKState | None = None) -> None:
        self._state = initial or IKState()
        self._listeners: list[Listener] = []

    @property
    def state(self) -> IKState:
        return self._state

    def add_listener(self, listener: Listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _set_state(self, new_state: IKState) -> None:
        if new_state is self._state:
            return
        self._state = new_state
        for listener in list(self._listeners):
            listener(self._state)

    # Mutators ---------------------------------------------------------------
    def update_skeleton(self, skeleton: Mapping[str, object] | None) -> None:
        self._set_state(self._state.with_skeleton(skeleton))

    def update_project_parts(self, parts: Mapping[str, object]) -> None:
        self._set_state(self._state.with_project_parts(parts))

    def start_animation(self) -> None:
        self._set_state(self._state.start_animation())

    def stop_animation(self) -> None:
        self._set_state(self._state.stop_animation())

    def set_animation_time(self, time: float) -> None:
        self._set_state(self._state.set_animation_time(time))

    def set_animation_duration(self, duration_ms: int) -> None:
        self._set_state(self._state.set_animation_duration(duration_ms))

    def set_timing_profile(self, profile: str) -> None:
        self._set_state(self._state.set_timing_profile(profile))

    def set_mechanism_target(self, part: str, position: Tuple[float, float]) -> None:
        self._set_state(self._state.with_mechanism_target(part, position))

    def clear_mechanism_targets(self, part: str | None = None) -> None:
        self._set_state(self._state.without_mechanism_target(part))
