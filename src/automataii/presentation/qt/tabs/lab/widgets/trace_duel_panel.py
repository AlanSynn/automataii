"""Trace Duel summary panel for Lab."""

from __future__ import annotations

import json
from collections.abc import Mapping

from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget


class TraceDuelPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lab_trace_duel_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Trace Duel"))
        self.summary_view = QTextEdit(self)
        self.summary_view.setReadOnly(True)
        layout.addWidget(self.summary_view)

    def set_summary(self, summary: Mapping[str, object]) -> None:
        self.summary_view.setPlainText(json.dumps(dict(summary), ensure_ascii=False, indent=2))
