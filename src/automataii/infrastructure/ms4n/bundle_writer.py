"""Low-level bundle writers for Lab/MS4N P0 exports."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path

from automataii.domain.ms4n import BreakdownRepairEpisode


class BundleWriter:
    """Small deterministic filesystem helper for export artifacts."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def ensure_subdir(self, name: str) -> Path:
        path = self.output_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_manifest(
        self, episodes: Sequence[BreakdownRepairEpisode], files: Sequence[Path]
    ) -> Path:
        manifest_path = self.output_dir / "manifest.json"
        payload = {
            "schema_version": "ms4n.export.v1",
            "episode_count": len(episodes),
            "files": [str(path.relative_to(self.output_dir)) for path in files if path.exists()],
        }
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def write_facilitator_moves(
        self,
        episodes: Sequence[BreakdownRepairEpisode],
        path: Path,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("episode_id", "move_type", "note", "timestamp"),
            )
            writer.writeheader()
            for episode in episodes:
                for move in episode.facilitator_moves:
                    writer.writerow(
                        {
                            "episode_id": episode.episode_id,
                            "move_type": move.move_type,
                            "note": move.note,
                            "timestamp": move.timestamp,
                        }
                    )
        return path

    def write_trace_snapshot_json(
        self,
        episode: BreakdownRepairEpisode,
        snapshot_role: str,
        path: Path,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot_role not in {"before", "after"}:
            raise ValueError("snapshot_role must be 'before' or 'after'")
        snapshot = episode.before_snapshot if snapshot_role == "before" else episode.after_snapshot
        payload = {
            "schema_version": "ms4n.trace_snapshot.v1",
            "episode_id": episode.episode_id,
            "snapshot_role": snapshot_role,
            "snapshot_id": snapshot.snapshot_id if snapshot is not None else "",
            "mechanism_id": episode.mechanism_id,
            "mechanism_type": episode.mechanism_type,
            "part_name": episode.part_name,
            "coordinate_space": snapshot.coordinate_space if snapshot is not None else "",
            "snapshot_present": snapshot is not None,
            "trace_points": [list(point) for point in snapshot.trace_points]
            if snapshot is not None
            else [],
            "trace_summary": snapshot.trace_summary.to_dict()
            if snapshot is not None and snapshot.trace_summary is not None
            else None,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2),
            encoding="utf-8",
        )
        return path
