"""User-facing Lab tab for mechanism-first research scaffolding."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QGridLayout, QLabel, QWidget

from automataii.application.ms4n import (
    EpisodeSummaryViewModel,
    ExportResult,
    ExportService,
    KitAssetViewModel,
    KitCatalogService,
)
from automataii.infrastructure.ms4n import FilesystemExportWriter, load_kit_manifest
from automataii.presentation.qt.tabs.lab.presenter import LabPresenter
from automataii.presentation.qt.tabs.lab.widgets import (
    EpisodeBuilderPanel,
    FacilitatorLogPanel,
    KitCatalogPanel,
    MotionAutopsyPanel,
    TraceDuelPanel,
)


class LabTab(QWidget):
    """Lab-facing P0 workflow shell; backend artifacts remain under MS4N packages."""

    kit_asset_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tab_lab")
        self.presenter = LabPresenter(
            self,
            kit_catalog_service=KitCatalogService(loader=load_kit_manifest),
            export_service=ExportService(writer=FilesystemExportWriter()),
        )
        self._init_ui()
        self._connect_signals()
        self._try_load_default_manifest()

    def _init_ui(self) -> None:
        layout = QGridLayout(self)
        self.title_label = QLabel("Lab", self)
        self.title_label.setObjectName("lab_title_label")
        layout.addWidget(self.title_label, 0, 0, 1, 2)

        self.kit_catalog_panel = KitCatalogPanel(self)
        self.episode_builder_panel = EpisodeBuilderPanel(self)
        self.trace_duel_panel = TraceDuelPanel(self)
        self.motion_autopsy_panel = MotionAutopsyPanel(self)
        self.facilitator_log_panel = FacilitatorLogPanel(self)

        layout.addWidget(self.kit_catalog_panel, 1, 0)
        layout.addWidget(self.episode_builder_panel, 1, 1)
        layout.addWidget(self.trace_duel_panel, 2, 0)
        layout.addWidget(self.motion_autopsy_panel, 2, 1)
        layout.addWidget(self.facilitator_log_panel, 3, 0, 1, 2)

    def _connect_signals(self) -> None:
        self.kit_catalog_panel.asset_selected.connect(self.kit_asset_selected.emit)
        self.episode_builder_panel.explanation_submitted.connect(self.presenter.save_explanation)
        self.facilitator_log_panel.export_requested.connect(self._choose_export_directory)

    def _try_load_default_manifest(self) -> None:
        manifest_path = Path(__file__).resolve().parents[6] / "kit" / "ms4n-kit-manifest.json"
        if not manifest_path.exists():
            self.show_lab_message("Lab kit manifest not found")
            return
        try:
            self.presenter.load_manifest(manifest_path)
        except Exception as exc:
            self.show_lab_message(f"Could not load Lab kit manifest: {exc}")

    def set_kit_assets(self, assets: Sequence[KitAssetViewModel]) -> None:
        self.kit_catalog_panel.set_assets(assets)

    def set_episode_summary(self, summary: EpisodeSummaryViewModel) -> None:
        self.episode_builder_panel.set_summary(summary)

    def set_trace_duel_summary(self, summary: Mapping[str, object]) -> None:
        self.trace_duel_panel.set_summary(summary)

    def set_motion_autopsy_rows(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.motion_autopsy_panel.set_rows(rows)

    def show_export_result(self, result: ExportResult) -> None:
        files_text = ", ".join(path.name for path in result.files)
        self.facilitator_log_panel.set_status(f"Exported Lab bundle: {files_text}")

    def show_lab_message(self, message: str) -> None:
        self.facilitator_log_panel.set_status(message)

    def _choose_export_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Export Lab research bundle")
        if directory:
            self.presenter.export_bundle(Path(directory))
