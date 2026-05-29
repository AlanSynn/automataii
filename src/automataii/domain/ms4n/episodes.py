"""Domain models for Lab/MS4N breakdown-repair research episodes."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from automataii.domain.ms4n.repair_taxonomy import (
    validate_change,
    validate_facilitator_move,
    validate_repair_action,
    validate_status,
    validate_suspected_cause,
    validate_symptom,
)
from automataii.domain.ms4n.trace import (
    TracePoint,
    TraceSummary,
    compare_trace_summaries,
    validate_trace_points,
)

EPISODE_SCHEMA_VERSION = "ms4n.episode.v1"

JsonDict = dict[str, object]
Point2 = tuple[float, float]


class EpisodeValidationError(ValueError):
    """Raised when an episode cannot support P0 evidence claims."""


@dataclass(frozen=True)
class ValidationResult:
    """Non-throwing validation result for UI feedback."""

    is_valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise EpisodeValidationError("; ".join(self.errors))


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    artifact_type: str
    uri: str
    note: str = ""

    def to_dict(self) -> JsonDict:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "uri": self.uri,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ArtifactRef:
        return cls(
            artifact_id=str(data.get("artifact_id", "")),
            artifact_type=str(data.get("artifact_type", "")),
            uri=str(data.get("uri", "")),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class LearnerExplanation:
    text: str = ""
    absence_note: str = ""

    @property
    def is_present(self) -> bool:
        return bool(self.text.strip())

    @property
    def has_evidence(self) -> bool:
        return self.is_present or bool(self.absence_note.strip())

    def to_dict(self) -> JsonDict:
        return {
            "text": self.text,
            "absence_note": self.absence_note,
            "is_present": self.is_present,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> LearnerExplanation:
        return cls(text=str(data.get("text", "")), absence_note=str(data.get("absence_note", "")))


@dataclass(frozen=True)
class MechanicalChange:
    change_type: str
    target: str
    before_value: object = ""
    after_value: object = ""
    rationale_text: str = ""

    def __post_init__(self) -> None:
        validate_change(self.change_type)
        ensure_json_safe(self.before_value, "change.before_value")
        ensure_json_safe(self.after_value, "change.after_value")

    def to_dict(self) -> JsonDict:
        return {
            "change_type": self.change_type,
            "target": self.target,
            "before_value": json_safe_copy(self.before_value),
            "after_value": json_safe_copy(self.after_value),
            "rationale_text": self.rationale_text,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MechanicalChange:
        return cls(
            change_type=str(data.get("change_type", "")),
            target=str(data.get("target", "")),
            before_value=data.get("before_value", ""),
            after_value=data.get("after_value", ""),
            rationale_text=str(data.get("rationale_text", "")),
        )


@dataclass(frozen=True)
class BreakdownEvent:
    symptom: str
    suspected_causes: tuple[str, ...] = field(default_factory=tuple)
    evidence_ref: ArtifactRef | None = None
    note: str = ""

    def __post_init__(self) -> None:
        validate_symptom(self.symptom)
        for cause in self.suspected_causes:
            validate_suspected_cause(cause)

    def to_dict(self) -> JsonDict:
        return {
            "symptom": self.symptom,
            "suspected_causes": list(self.suspected_causes),
            "evidence_ref": self.evidence_ref.to_dict() if self.evidence_ref is not None else None,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> BreakdownEvent:
        raw_causes = data.get("suspected_causes", ())
        causes = _string_tuple(raw_causes)
        raw_ref = data.get("evidence_ref")
        ref = ArtifactRef.from_dict(raw_ref) if isinstance(raw_ref, Mapping) else None
        return cls(
            symptom=str(data.get("symptom", "")),
            suspected_causes=causes,
            evidence_ref=ref,
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class RepairAction:
    action_type: str
    target: str
    before_value: object = ""
    after_value: object = ""
    note: str = ""

    def __post_init__(self) -> None:
        validate_repair_action(self.action_type)
        ensure_json_safe(self.before_value, "repair.before_value")
        ensure_json_safe(self.after_value, "repair.after_value")

    def to_dict(self) -> JsonDict:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "before_value": json_safe_copy(self.before_value),
            "after_value": json_safe_copy(self.after_value),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> RepairAction:
        return cls(
            action_type=str(data.get("action_type", "")),
            target=str(data.get("target", "")),
            before_value=data.get("before_value", ""),
            after_value=data.get("after_value", ""),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class FacilitatorMove:
    move_type: str
    note: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        validate_facilitator_move(self.move_type)

    def to_dict(self) -> JsonDict:
        return {
            "move_type": self.move_type,
            "note": self.note,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> FacilitatorMove:
        return cls(
            move_type=str(data.get("move_type", "")),
            note=str(data.get("note", "")),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass(frozen=True)
class MechanismStateSnapshot:
    snapshot_id: str
    mechanism_id: str
    mechanism_type: str
    part_name: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    key_points: Mapping[str, Point2] = field(default_factory=dict)
    trace_points: tuple[TracePoint, ...] = field(default_factory=tuple)
    trace_summary: TraceSummary | None = None
    coordinate_space: str = "scene"
    physical_observation_note: str = ""

    def __post_init__(self) -> None:
        ensure_json_safe(self.parameters, "snapshot.parameters")
        for name, point in self.key_points.items():
            if len(point) != 2:
                raise EpisodeValidationError(f"key point {name!r} must have x/y coordinates")
            ensure_finite_float(point[0], f"key_points.{name}.x")
            ensure_finite_float(point[1], f"key_points.{name}.y")
        validate_trace_points(self.trace_points)

    def to_dict(self) -> JsonDict:
        return {
            "snapshot_id": self.snapshot_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_type": self.mechanism_type,
            "part_name": self.part_name,
            "parameters": json_safe_copy(dict(self.parameters)),
            "key_points": {key: list(value) for key, value in self.key_points.items()},
            "trace_points": [list(point) for point in self.trace_points],
            "trace_summary": self.trace_summary.to_dict()
            if self.trace_summary is not None
            else None,
            "coordinate_space": self.coordinate_space,
            "physical_observation_note": self.physical_observation_note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MechanismStateSnapshot:
        raw_key_points = data.get("key_points", {})
        key_points: dict[str, Point2] = {}
        if isinstance(raw_key_points, Mapping):
            for name, value in raw_key_points.items():
                if (
                    isinstance(value, Sequence)
                    and not isinstance(value, str | bytes)
                    and len(value) == 2
                ):
                    key_points[str(name)] = (float(value[0]), float(value[1]))
        raw_trace_points = data.get("trace_points", ())
        trace_points: tuple[TracePoint, ...] = ()
        if raw_trace_points is None:
            trace_points = ()
        elif isinstance(raw_trace_points, Sequence) and not isinstance(
            raw_trace_points, str | bytes
        ):
            trace_points = validate_trace_points(raw_trace_points)
        else:
            raise EpisodeValidationError("trace_points must be a list of frame/x/y triples")
        raw_trace_summary = data.get("trace_summary")
        trace_summary = (
            TraceSummary.from_dict(raw_trace_summary)
            if isinstance(raw_trace_summary, dict)
            else None
        )
        raw_parameters = data.get("parameters", {})
        parameters: Mapping[str, object] = (
            raw_parameters if isinstance(raw_parameters, Mapping) else {}
        )
        return cls(
            snapshot_id=str(data.get("snapshot_id", "")),
            mechanism_id=str(data.get("mechanism_id", "")),
            mechanism_type=str(data.get("mechanism_type", "")),
            part_name=str(data.get("part_name", "")),
            parameters=parameters,
            key_points=key_points,
            trace_points=trace_points,
            trace_summary=trace_summary,
            coordinate_space=str(data.get("coordinate_space", "scene")),
            physical_observation_note=str(data.get("physical_observation_note", "")),
        )


@dataclass(frozen=True)
class BreakdownRepairEpisode:
    episode_id: str
    session_id: str
    participant_hash: str
    mechanism_id: str
    mechanism_type: str
    part_name: str
    kit_asset_ids: tuple[str, ...] = field(default_factory=tuple)
    status: str = "open"
    before_snapshot: MechanismStateSnapshot | None = None
    breakdown_events: tuple[BreakdownEvent, ...] = field(default_factory=tuple)
    primary_changes: tuple[MechanicalChange, ...] = field(default_factory=tuple)
    repair_actions: tuple[RepairAction, ...] = field(default_factory=tuple)
    after_snapshot: MechanismStateSnapshot | None = None
    learner_explanation: LearnerExplanation = field(default_factory=LearnerExplanation)
    facilitator_moves: tuple[FacilitatorMove, ...] = field(default_factory=tuple)
    artifact_refs: tuple[ArtifactRef, ...] = field(default_factory=tuple)
    constraint_violation_note: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        validate_status(self.status)

    @property
    def change_count(self) -> int:
        return len(self.primary_changes)

    @property
    def repair_count(self) -> int:
        return len(self.repair_actions)

    @property
    def trace_delta_summary(self) -> dict[str, object]:
        before_summary = self.before_snapshot.trace_summary if self.before_snapshot else None
        after_summary = self.after_snapshot.trace_summary if self.after_snapshot else None
        summary: dict[str, object] = compare_trace_summaries(before_summary, after_summary)
        return summary

    def validate_for_p0(self) -> ValidationResult:
        errors: list[str] = []
        if not self.episode_id:
            errors.append("episode_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if not self.participant_hash:
            errors.append("participant_hash is required")
        if not self.mechanism_id:
            errors.append("mechanism_id is required")
        if not self.mechanism_type:
            errors.append("mechanism_type is required")
        if not self.part_name:
            errors.append("part_name is required")
        if not self.kit_asset_ids:
            errors.append("kit_asset_ids requires at least one kit asset id")
        if any(not asset_id.strip() for asset_id in self.kit_asset_ids):
            errors.append("kit_asset_ids cannot contain blank ids")
        if self.status == "repaired":
            if self.before_snapshot is None:
                errors.append("repaired episode requires before_snapshot")
            if not self.breakdown_events:
                errors.append("repaired episode requires at least one breakdown_event")
            if not self.primary_changes:
                errors.append("repaired episode requires one primary change")
            if not self.repair_actions:
                errors.append("repaired episode requires one repair_action")
            if self.after_snapshot is None:
                errors.append("repaired episode requires after_snapshot")
            if not self.learner_explanation.has_evidence:
                errors.append("repaired episode requires learner explanation or absence note")
        if (self.change_count > 1 or self.repair_count > 1) and self.status == "repaired":
            errors.append(
                "repaired status requires exactly one primary change and one repair action"
            )
        if self.change_count > 1 or self.repair_count > 1:
            if not self.constraint_violation_note.strip():
                errors.append("multi-change episodes require constraint_violation_note")
            if self.status not in {"open", "unresolved", "abandoned"}:
                errors.append("multi-change episodes must remain open, unresolved, or abandoned")
        return ValidationResult(is_valid=not errors, errors=tuple(errors))

    def assert_valid_for_p0(self) -> None:
        self.validate_for_p0().raise_if_invalid()

    def to_dict(self) -> JsonDict:
        payload: JsonDict = {
            "schema_version": EPISODE_SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "participant_hash": self.participant_hash,
            "mechanism_id": self.mechanism_id,
            "mechanism_type": self.mechanism_type,
            "part_name": self.part_name,
            "kit_asset_ids": list(self.kit_asset_ids),
            "status": self.status,
            "before_snapshot": (
                self.before_snapshot.to_dict() if self.before_snapshot is not None else None
            ),
            "breakdown_events": [event.to_dict() for event in self.breakdown_events],
            "primary_changes": [change.to_dict() for change in self.primary_changes],
            "repair_actions": [action.to_dict() for action in self.repair_actions],
            "after_snapshot": self.after_snapshot.to_dict()
            if self.after_snapshot is not None
            else None,
            "learner_explanation": self.learner_explanation.to_dict(),
            "facilitator_moves": [move.to_dict() for move in self.facilitator_moves],
            "artifact_refs": [artifact.to_dict() for artifact in self.artifact_refs],
            "constraint_violation_note": self.constraint_violation_note,
            "change_count": self.change_count,
            "repair_count": self.repair_count,
            "trace_delta_summary": self.trace_delta_summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return cast(JsonDict, json_safe_copy(payload))

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> BreakdownRepairEpisode:
        before = _snapshot_or_none(data.get("before_snapshot"))
        after = _snapshot_or_none(data.get("after_snapshot"))
        raw_explanation = data.get("learner_explanation", {})
        explanation = (
            LearnerExplanation.from_dict(raw_explanation)
            if isinstance(raw_explanation, Mapping)
            else LearnerExplanation()
        )
        return cls(
            episode_id=str(data.get("episode_id", "")),
            session_id=str(data.get("session_id", "")),
            participant_hash=str(data.get("participant_hash", "")),
            mechanism_id=str(data.get("mechanism_id", "")),
            mechanism_type=str(data.get("mechanism_type", "")),
            part_name=str(data.get("part_name", "")),
            kit_asset_ids=_string_tuple(data.get("kit_asset_ids", ())),
            status=str(data.get("status", "open")),
            before_snapshot=before,
            breakdown_events=tuple(
                BreakdownEvent.from_dict(item)
                for item in _mapping_items(data.get("breakdown_events", ()))
            ),
            primary_changes=tuple(
                MechanicalChange.from_dict(item)
                for item in _mapping_items(data.get("primary_changes", ()))
            ),
            repair_actions=tuple(
                RepairAction.from_dict(item)
                for item in _mapping_items(data.get("repair_actions", ()))
            ),
            after_snapshot=after,
            learner_explanation=explanation,
            facilitator_moves=tuple(
                FacilitatorMove.from_dict(item)
                for item in _mapping_items(data.get("facilitator_moves", ()))
            ),
            artifact_refs=tuple(
                ArtifactRef.from_dict(item)
                for item in _mapping_items(data.get("artifact_refs", ()))
            ),
            constraint_violation_note=str(data.get("constraint_violation_note", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
        )


def ensure_finite_float(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise EpisodeValidationError(f"{path} must be a finite number; got {value!r}")
    finite_value = float(value)
    if not math.isfinite(finite_value):
        raise EpisodeValidationError(f"{path} must be finite; got {value!r}")
    return finite_value


def ensure_json_safe(value: object, path: str = "$", allow_none: bool = True) -> None:
    if value is None:
        if allow_none:
            return
        raise EpisodeValidationError(f"{path} cannot be null")
    if isinstance(value, bool | str):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        ensure_finite_float(value, path)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EpisodeValidationError(f"{path} has non-string key {key!r}")
            ensure_json_safe(item, f"{path}.{key}", allow_none=allow_none)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, item in enumerate(value):
            ensure_json_safe(item, f"{path}[{index}]", allow_none=allow_none)
        return
    raise EpisodeValidationError(f"{path} contains non-JSON-safe value {type(value).__name__}")


def json_safe_copy(value: object) -> object:
    ensure_json_safe(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe_copy(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [json_safe_copy(item) for item in value]
    return value


def _snapshot_or_none(value: object) -> MechanismStateSnapshot | None:
    return MechanismStateSnapshot.from_dict(value) if isinstance(value, Mapping) else None


def _mapping_items(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, bytes | bytearray):
        return ()
    return tuple(str(item) for item in value)
