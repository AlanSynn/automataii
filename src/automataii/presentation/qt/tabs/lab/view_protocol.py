"""View protocol for the user-facing Lab tab."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from automataii.application.ms4n import EpisodeSummaryViewModel, ExportResult, KitAssetViewModel


class LabViewProtocol(Protocol):
    def set_kit_assets(self, assets: Sequence[KitAssetViewModel]) -> None: ...

    def set_episode_summary(self, summary: EpisodeSummaryViewModel) -> None: ...

    def set_trace_duel_summary(self, summary: Mapping[str, object]) -> None: ...

    def set_motion_autopsy_rows(self, rows: Sequence[Mapping[str, object]]) -> None: ...

    def show_export_result(self, result: ExportResult) -> None: ...

    def show_lab_message(self, message: str) -> None: ...
