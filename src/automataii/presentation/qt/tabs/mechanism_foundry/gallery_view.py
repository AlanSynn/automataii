from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from automataii.application.mechanism_foundry import ContentLoader, MechanismFoundryController
from automataii.presentation.qt.tabs.mechanism_foundry.gallery_thumbnail import GalleryThumbnail
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitProfile,
)


class GalleryView(QWidget):
    mechanism_selected = pyqtSignal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        controller: MechanismFoundryController | None = None,
        physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
        grid_cell_cm: float = DEFAULT_GRID_CELL_CM,
    ):
        super().__init__(parent)
        self.controller = controller or MechanismFoundryController(
            physical_profile=physical_profile,
            grid_cell_cm=grid_cell_cm,
        )
        self.content_loader = ContentLoader()
        self._grid_layout: QGridLayout | None = None
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
        self._grid_layout = grid_layout
        self._populate_gallery(grid_layout)

        scroll_layout.addLayout(grid_layout)
        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

    def _on_thumbnail_clicked(self, mechanism_type: str) -> None:
        self.mechanism_selected.emit(mechanism_type)

    def set_controller(self, controller: MechanismFoundryController) -> None:
        """Refresh gallery content from the active Foundry controller instance."""
        self.controller = controller
        if self._grid_layout is not None:
            self._clear_layout(self._grid_layout)
            self._populate_gallery(self._grid_layout)

    def _populate_gallery(self, grid_layout: QGridLayout) -> None:
        mechanisms = self.controller.list_mechanisms()
        columns = 3
        row = 0
        col = 0

        for item in mechanisms:
            content = self.content_loader.load_content(item.mechanism_type)
            description = self._build_gallery_description(content.goal, content.gallery_summary)
            motion_summary = " / ".join(content.motions) if content.motions else ""

            thumbnail = GalleryThumbnail(
                item.mechanism_type,
                item.display_name,
                description,
                self,
                motion_summary=motion_summary,
            )
            thumbnail.clicked.connect(self._on_thumbnail_clicked)

            grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= columns:
                col = 0
                row += 1

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                GalleryView._clear_layout(child_layout)
            if isinstance(item, QSpacerItem):
                del item

    @staticmethod
    def _build_gallery_description(goal: str, gallery_summary: str | None) -> str:
        if gallery_summary:
            return str(gallery_summary).strip()

        clean = str(goal).strip()
        if not clean:
            return ""

        first_sentence = clean.split(".")[0].strip()
        if first_sentence and len(first_sentence) <= 120:
            return first_sentence + "."
        return clean[:117].rstrip() + "..."
