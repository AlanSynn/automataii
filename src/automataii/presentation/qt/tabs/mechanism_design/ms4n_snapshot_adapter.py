"""Presentation boundary adapter from Mechanism Design state to MS4N snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import uuid4

from automataii.application.ms4n import EpisodeService, points_to_trace_points
from automataii.domain.ms4n import MechanismStateSnapshot


class MS4NSnapshotAdapter:
    """Consumes the public snapshot-source contract without reading private tab fields."""

    def __init__(self, episode_service: EpisodeService | None = None) -> None:
        self._episode_service = episode_service or EpisodeService()

    def capture(
        self,
        snapshot_source_provider: object,
        *,
        mechanism_id: str | None = None,
        snapshot_id: str | None = None,
        physical_observation_note: str = "",
    ) -> MechanismStateSnapshot:
        source_method = getattr(snapshot_source_provider, "get_ms4n_snapshot_source", None)
        if not callable(source_method):
            raise TypeError("snapshot source provider must implement get_ms4n_snapshot_source")
        source = source_method(mechanism_id)
        if not isinstance(source, Mapping):
            raise TypeError("MS4N snapshot source must be a mapping")
        return build_snapshot_from_source(
            source,
            episode_service=self._episode_service,
            snapshot_id=snapshot_id,
            physical_observation_note=physical_observation_note,
        )


def build_snapshot_from_source(
    source: Mapping[str, object],
    *,
    episode_service: EpisodeService | None = None,
    snapshot_id: str | None = None,
    physical_observation_note: str = "",
) -> MechanismStateSnapshot:
    service = episode_service or EpisodeService()
    raw_trace_points = source.get("trace_points", ())
    trace_points: Sequence[object] = ()
    if isinstance(raw_trace_points, Sequence) and not isinstance(raw_trace_points, str | bytes):
        trace_points = raw_trace_points
    elif "trace_points" in source:
        raise TypeError("MS4N trace_points must be a sequence of plain x/y points")
    normalized_trace = points_to_trace_points(trace_points)
    return service.make_snapshot(
        snapshot_id=snapshot_id or f"snapshot_{uuid4().hex[:12]}",
        mechanism_id=str(source.get("mechanism_id", "")),
        mechanism_type=str(source.get("mechanism_type", "")),
        part_name=str(source.get("part_name", "")),
        parameters=_mapping_or_empty(source.get("parameters")),
        key_points=_key_points(source.get("key_points")),
        trace_points=normalized_trace,
        coordinate_space=str(source.get("coordinate_space", "scene")),
        physical_observation_note=physical_observation_note,
    )


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _key_points(value: object) -> dict[str, tuple[float, float]]:
    if not isinstance(value, Mapping):
        return {}
    points: dict[str, tuple[float, float]] = {}
    for name, point in value.items():
        if isinstance(point, Sequence) and not isinstance(point, str | bytes) and len(point) == 2:
            points[str(name)] = (float(point[0]), float(point[1]))
            continue
        x_attr = getattr(point, "x", None)
        y_attr = getattr(point, "y", None)
        if callable(x_attr) and callable(y_attr):
            points[str(name)] = (float(x_attr()), float(y_attr()))
    return points
