"""Motion Autopsy table panel for Lab."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class MotionAutopsyPanel(QWidget):
    HEADERS = ("episode_id", "mechanism", "status", "changes", "repairs", "explanation")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lab_motion_autopsy_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Motion Autopsy"))
        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        layout.addWidget(self.table)

    def set_rows(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, header in enumerate(self.HEADERS):
                self.table.setItem(
                    row_index, column_index, QTableWidgetItem(str(row.get(header, "")))
                )
