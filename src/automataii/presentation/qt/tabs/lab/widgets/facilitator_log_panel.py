"""Facilitator log and export panel for Lab."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


class FacilitatorLogPanel(QWidget):
    export_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lab_facilitator_log_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Facilitator log / export"))
        self.log_edit = QTextEdit(self)
        self.log_edit.setPlaceholderText(
            "Facilitator moves, fabrication checks, and recovery notes"
        )
        layout.addWidget(self.log_edit)
        self.export_button = QPushButton("Export research bundle", self)
        self.export_button.clicked.connect(self.export_requested.emit)
        layout.addWidget(self.export_button)
        self.status_label = QLabel("", self)
        layout.addWidget(self.status_label)

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)
