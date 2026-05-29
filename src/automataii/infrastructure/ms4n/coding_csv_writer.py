"""Coding CSV writer for Lab/MS4N P0 analysis."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path

from automataii.domain.ms4n import BreakdownRepairEpisode

CODING_CSV_HEADER: tuple[str, ...] = (
    "episode_id",
    "session_id",
    "mechanism_id",
    "mechanism_type",
    "part_name",
    "status",
    "symptom",
    "suspected_causes",
    "repair_action",
    "change_count",
    "repair_count",
    "trace_point_count",
    "before_bbox",
    "after_bbox",
    "motion_delta_summary",
    "learner_explanation_present",
    "facilitator_moves",
    "artifact_ref_count",
)


def write_coding_csv(episodes: Sequence[BreakdownRepairEpisode], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CODING_CSV_HEADER)
        writer.writeheader()
        for episode in episodes:
            writer.writerow(episode_to_coding_row(episode))
    return path


def episode_to_coding_row(episode: BreakdownRepairEpisode) -> dict[str, object]:
    breakdown = episode.breakdown_events[0] if episode.breakdown_events else None
    repair = episode.repair_actions[0] if episode.repair_actions else None
    before_summary = episode.before_snapshot.trace_summary if episode.before_snapshot else None
    after_summary = episode.after_snapshot.trace_summary if episode.after_snapshot else None
    point_count = 0
    if after_summary is not None:
        point_count = after_summary.point_count
    elif before_summary is not None:
        point_count = before_summary.point_count
    return {
        "episode_id": episode.episode_id,
        "session_id": episode.session_id,
        "mechanism_id": episode.mechanism_id,
        "mechanism_type": episode.mechanism_type,
        "part_name": episode.part_name,
        "status": episode.status,
        "symptom": breakdown.symptom if breakdown is not None else "",
        "suspected_causes": "|".join(breakdown.suspected_causes) if breakdown is not None else "",
        "repair_action": repair.action_type if repair is not None else "",
        "change_count": episode.change_count,
        "repair_count": episode.repair_count,
        "trace_point_count": point_count,
        "before_bbox": _bbox_text(before_summary.bbox if before_summary is not None else None),
        "after_bbox": _bbox_text(after_summary.bbox if after_summary is not None else None),
        "motion_delta_summary": json.dumps(
            episode.trace_delta_summary,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        ),
        "learner_explanation_present": episode.learner_explanation.is_present,
        "facilitator_moves": "; ".join(
            f"{move.move_type}: {move.note}" for move in episode.facilitator_moves
        ),
        "artifact_ref_count": len(episode.artifact_refs),
    }


def _bbox_text(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return ""
    return ",".join(f"{value:.6g}" for value in bbox)
