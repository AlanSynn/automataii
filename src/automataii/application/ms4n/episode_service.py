"""Application-level lifecycle helpers for Lab/MS4N episodes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime

from automataii.application.ms4n.view_models import EpisodeSummaryViewModel
from automataii.domain.ms4n import (
    ArtifactRef,
    BreakdownEvent,
    BreakdownRepairEpisode,
    FacilitatorMove,
    LearnerExplanation,
    MechanicalChange,
    MechanismStateSnapshot,
    RepairAction,
)
from automataii.domain.ms4n.trace import TracePoint, normalize_trace_points, summarize_trace


class EpisodeService:
    """Owns P0 episode state transitions; UI remains a thin client."""

    def start_episode(
        self,
        *,
        episode_id: str,
        session_id: str,
        participant_hash: str,
        mechanism_id: str,
        mechanism_type: str,
        part_name: str,
        kit_asset_ids: Sequence[str] = (),
    ) -> BreakdownRepairEpisode:
        now = _now_iso()
        return BreakdownRepairEpisode(
            episode_id=episode_id,
            session_id=session_id,
            participant_hash=participant_hash,
            mechanism_id=mechanism_id,
            mechanism_type=mechanism_type,
            part_name=part_name,
            kit_asset_ids=tuple(kit_asset_ids),
            status="open",
            created_at=now,
            updated_at=now,
        )

    def make_snapshot(
        self,
        *,
        snapshot_id: str,
        mechanism_id: str,
        mechanism_type: str,
        part_name: str,
        parameters: Mapping[str, object] | None = None,
        key_points: Mapping[str, tuple[float, float]] | None = None,
        trace_points: Sequence[object] | None = None,
        coordinate_space: str = "scene",
        physical_observation_note: str = "",
    ) -> MechanismStateSnapshot:
        bounded_trace: tuple[TracePoint, ...] = ()
        trace_summary = None
        if trace_points is not None:
            bounded = normalize_trace_points(trace_points)
            bounded_trace = bounded.points
            trace_summary = summarize_trace(trace_points)
        return MechanismStateSnapshot(
            snapshot_id=snapshot_id,
            mechanism_id=mechanism_id,
            mechanism_type=mechanism_type,
            part_name=part_name,
            parameters=dict(parameters or {}),
            key_points=dict(key_points or {}),
            trace_points=bounded_trace,
            trace_summary=trace_summary,
            coordinate_space=coordinate_space,
            physical_observation_note=physical_observation_note,
        )

    def attach_before(
        self,
        episode: BreakdownRepairEpisode,
        snapshot: MechanismStateSnapshot,
    ) -> BreakdownRepairEpisode:
        return replace(episode, before_snapshot=snapshot, updated_at=_now_iso())

    def attach_after(
        self,
        episode: BreakdownRepairEpisode,
        snapshot: MechanismStateSnapshot,
    ) -> BreakdownRepairEpisode:
        return replace(episode, after_snapshot=snapshot, updated_at=_now_iso())

    def record_breakdown(
        self,
        episode: BreakdownRepairEpisode,
        breakdown: BreakdownEvent,
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            breakdown_events=(*episode.breakdown_events, breakdown),
            updated_at=_now_iso(),
        )

    def record_primary_change(
        self,
        episode: BreakdownRepairEpisode,
        change: MechanicalChange,
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            primary_changes=(*episode.primary_changes, change),
            updated_at=_now_iso(),
        )

    def record_repair(
        self,
        episode: BreakdownRepairEpisode,
        repair: RepairAction,
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            repair_actions=(*episode.repair_actions, repair),
            updated_at=_now_iso(),
        )

    def save_explanation(
        self,
        episode: BreakdownRepairEpisode,
        *,
        text: str = "",
        absence_note: str = "",
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            learner_explanation=LearnerExplanation(text=text, absence_note=absence_note),
            updated_at=_now_iso(),
        )

    def add_facilitator_move(
        self,
        episode: BreakdownRepairEpisode,
        move: FacilitatorMove,
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            facilitator_moves=(*episode.facilitator_moves, move),
            updated_at=_now_iso(),
        )

    def add_artifact_ref(
        self,
        episode: BreakdownRepairEpisode,
        artifact: ArtifactRef,
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            artifact_refs=(*episode.artifact_refs, artifact),
            updated_at=_now_iso(),
        )

    def mark_repaired(self, episode: BreakdownRepairEpisode) -> BreakdownRepairEpisode:
        candidate = replace(episode, status="repaired", updated_at=_now_iso())
        candidate.assert_valid_for_p0()
        return candidate

    def mark_unresolved(
        self,
        episode: BreakdownRepairEpisode,
        *,
        constraint_violation_note: str = "",
    ) -> BreakdownRepairEpisode:
        return replace(
            episode,
            status="unresolved",
            constraint_violation_note=constraint_violation_note,
            updated_at=_now_iso(),
        )

    def to_summary_view_model(self, episode: BreakdownRepairEpisode) -> EpisodeSummaryViewModel:
        return EpisodeSummaryViewModel(
            episode_id=episode.episode_id,
            mechanism_id=episode.mechanism_id,
            mechanism_type=episode.mechanism_type,
            part_name=episode.part_name,
            status=episode.status,
            change_count=episode.change_count,
            repair_count=episode.repair_count,
            learner_explanation_present=episode.learner_explanation.is_present,
        )


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
