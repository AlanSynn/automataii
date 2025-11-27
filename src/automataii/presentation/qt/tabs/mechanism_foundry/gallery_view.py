from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import ContentLoader, MechanismFoundryController
from automataii.presentation.qt.tabs.mechanism_foundry.gallery_thumbnail import GalleryThumbnail


class GalleryView(QWidget):
    mechanism_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = MechanismFoundryController()
        self.content_loader = ContentLoader()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Mechanism Gallery")
        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 8px;
            """
        )
        layout.addWidget(title)

        subtitle = QLabel("Explore and interact with fundamental mechanisms")
        subtitle.setStyleSheet(
            """
            font-size: 14px;
            color: #7f8c8d;
            margin-bottom: 16px;
            """
        )
        layout.addWidget(subtitle)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        mechanisms = self.controller.list_mechanisms()
        columns = 3
        row = 0
        col = 0

        for item in mechanisms:
            content = self.content_loader.load_content(item.mechanism_type)
            description = content.goal[:120] + "..." if len(content.goal) > 120 else content.goal

            thumbnail = GalleryThumbnail(item.mechanism_type, item.display_name, description, self)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)

            grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= columns:
                col = 0
                row += 1

        scroll_layout.addLayout(grid_layout)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

    def _on_thumbnail_clicked(self, mechanism_type: str) -> None:
        self.mechanism_selected.emit(mechanism_type)
