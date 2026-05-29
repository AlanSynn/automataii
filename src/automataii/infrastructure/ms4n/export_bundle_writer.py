"""Concrete filesystem export writer for Lab/MS4N bundles."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from automataii.application.ms4n.autopsy_sheet_service import AutopsySheetService
from automataii.domain.ms4n import BreakdownRepairEpisode
from automataii.infrastructure.ms4n.bundle_writer import BundleWriter
from automataii.infrastructure.ms4n.coding_csv_writer import write_coding_csv
from automataii.infrastructure.ms4n.jsonl_writer import write_episodes_jsonl


class FilesystemExportWriter:
    """Infrastructure adapter that writes all required P0 bundle files."""

    def write_bundle(
        self,
        episodes: Sequence[BreakdownRepairEpisode],
        output_dir: Path,
        autopsy_sheet_service: AutopsySheetService,
    ) -> tuple[Path, ...]:
        writer = BundleWriter(output_dir)
        research_dir = writer.ensure_subdir("research")
        autopsy_dir = writer.ensure_subdir("autopsy")
        traces_dir = writer.ensure_subdir("traces")

        files: list[Path] = []
        files.append(write_episodes_jsonl(episodes, research_dir / "episodes.jsonl"))
        files.append(write_coding_csv(episodes, research_dir / "coding_sheet.csv"))
        files.append(
            writer.write_facilitator_moves(episodes, research_dir / "facilitator_moves.csv")
        )
        for episode in episodes:
            files.append(
                writer.write_trace_snapshot_json(
                    episode,
                    "before",
                    traces_dir / f"{episode.episode_id}_before.json",
                )
            )
            files.append(
                writer.write_trace_snapshot_json(
                    episode,
                    "after",
                    traces_dir / f"{episode.episode_id}_after.json",
                )
            )
            sheet_path = autopsy_dir / f"{episode.episode_id}_sheet.md"
            sheet_path.write_text(
                autopsy_sheet_service.render_markdown(episode),
                encoding="utf-8",
            )
            files.append(sheet_path)
        files.append(writer.write_manifest(episodes, tuple(files)))
        return tuple(files)
