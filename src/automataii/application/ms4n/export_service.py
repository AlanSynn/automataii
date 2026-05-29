"""Export orchestration for P0 Lab/MS4N research bundles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from automataii.application.ms4n.autopsy_sheet_service import AutopsySheetService
from automataii.domain.ms4n import BreakdownRepairEpisode


@dataclass(frozen=True)
class ExportResult:
    output_dir: Path
    files: tuple[Path, ...]


class ExportWriterProtocol(Protocol):
    """Infrastructure port for writing a concrete research bundle."""

    def write_bundle(
        self,
        episodes: Sequence[BreakdownRepairEpisode],
        output_dir: Path,
        autopsy_sheet_service: AutopsySheetService,
    ) -> tuple[Path, ...]: ...


class ExportService:
    """Application-level export orchestration behind an infrastructure writer port."""

    def __init__(
        self,
        writer: ExportWriterProtocol | None = None,
        autopsy_sheet_service: AutopsySheetService | None = None,
    ) -> None:
        self._writer = writer
        self._autopsy_sheet_service = autopsy_sheet_service or AutopsySheetService()

    def export_bundle(
        self,
        episodes: Sequence[BreakdownRepairEpisode],
        output_dir: Path,
    ) -> ExportResult:
        if self._writer is None:
            raise RuntimeError("ExportService requires an infrastructure ExportWriterProtocol")
        for episode in episodes:
            episode.assert_valid_for_p0()
        files = self._writer.write_bundle(episodes, output_dir, self._autopsy_sheet_service)
        return ExportResult(output_dir=output_dir, files=tuple(files))
