"""Episode builder panel for Lab."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from automataii.application.ms4n import EpisodeSummaryViewModel


class EpisodeBuilderPanel(QWidget):
    explanation_submitted = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lab_episode_builder_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Breakdown → repair episode"))
        self.summary_label = QLabel("No active episode", self)
        layout.addWidget(self.summary_label)
        self.explanation_edit = QTextEdit(self)
        self.explanation_edit.setPlaceholderText(
            "Learner explanation: what changed, what moved, why?"
        )
        layout.addWidget(self.explanation_edit)
        self.save_explanation_button = QPushButton("Save explanation", self)
        self.save_explanation_button.clicked.connect(self._submit_explanation)
        layout.addWidget(self.save_explanation_button)

    def set_summary(self, summary: EpisodeSummaryViewModel) -> None:
        self.summary_label.setText(
            f"{summary.episode_id} · {summary.mechanism_type} · "
            f"{summary.status} · changes {summary.change_count} / repairs {summary.repair_count}"
        )

    def _submit_explanation(self) -> None:
        self.explanation_submitted.emit(self.explanation_edit.toPlainText())
