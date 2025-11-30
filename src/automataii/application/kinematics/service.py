from __future__ import annotations

from collections.abc import Mapping

from automataii.infrastructure.telemetry import telemetry_span

from .state import IKState, IKStateStore


class IKService:
    """Application-layer façade for IK workflows."""

    def __init__(self, store: IKStateStore | None = None) -> None:
        self._store = store or IKStateStore()

    @property
    def state(self) -> IKState:
        return self._store.state

    def add_listener(self, listener) -> None:
        self._store.add_listener(listener)

    def remove_listener(self, listener) -> None:
        self._store.remove_listener(listener)

    # Skeleton / project data ------------------------------------------------
    def update_skeleton(self, skeleton: Mapping[str, object] | None) -> None:
        with telemetry_span("application.ik.update_skeleton"):
            self._store.update_skeleton(skeleton)

    def update_project_parts(self, parts: Mapping[str, object]) -> None:
        with telemetry_span("application.ik.update_project_parts", part_count=len(parts)):
            self._store.update_project_parts(parts)

    # Animation --------------------------------------------------------------
    def set_animation_duration(self, duration_ms: int) -> None:
        with telemetry_span("application.ik.set_animation_duration", duration_ms=duration_ms):
            self._store.set_animation_duration(duration_ms)

    def set_timing_profile(self, profile: str) -> None:
        with telemetry_span("application.ik.set_timing_profile", profile=profile):
            self._store.set_timing_profile(profile)

    def start_animation(self) -> None:
        with telemetry_span("application.ik.start_animation"):
            self._store.start_animation()

    def stop_animation(self) -> None:
        with telemetry_span("application.ik.stop_animation"):
            self._store.stop_animation()

    def reset_animation(self) -> None:
        with telemetry_span("application.ik.reset_animation"):
            self._store.stop_animation()
            self._store.set_animation_time(0.0)

    def tick_animation(self, delta_seconds: float) -> None:
        """Advance animation clock if running."""
        if not self.state.animation_running:
            return
        new_time = self.state.animation_time + float(delta_seconds)
        self._store.set_animation_time(new_time)

    # Mechanism targets ------------------------------------------------------
    def set_mechanism_target(self, part_name: str, position: tuple[float, float]) -> None:
        with telemetry_span("application.ik.set_mechanism_target", part=part_name):
            self._store.set_mechanism_target(part_name, position)

    def clear_mechanism_target(self, part_name: str | None = None) -> None:
        with telemetry_span("application.ik.clear_mechanism_target", part=part_name):
            self._store.clear_mechanism_targets(part_name)
