"""Container widget for mechanism preview and selection UI."""

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from .constants import CONTAINER_MIN_WIDTH
from .styles import StyleSheets
from .preview_widget import MechanismPreviewWidget
from .path_analysis import score_to_match_percentage


class PreviewContainer(QWidget):
    """Container for a single preview and its title/select button."""

    selected = Signal(dict)  # Emits the mechanism data when selected
    clicked = Signal(dict)  # Emits the mechanism data when clicked for preview

    def __init__(
        self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self._is_selected = False
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title/Name
        name = self.mechanism_data.get("name", "Unnamed Mechanism")
        if ":" in name:
            mech_type = name.split(":")[0].strip()
        else:
            mech_type = name
        
        title_label = QLabel(mech_type)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(StyleSheets.TITLE_LABEL)
        layout.addWidget(title_label)

        # Preview Widget
        self.preview_widget = MechanismPreviewWidget(self.mechanism_data, self)
        self.preview_widget.setStyleSheet(StyleSheets.PREVIEW_WIDGET_NORMAL)
        layout.addWidget(self.preview_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Match percentage label
        score = self.mechanism_data.get("overall_score", 0)
        match_percentage = score_to_match_percentage(score)
        
        match_label = QLabel(f"Match: {match_percentage:.0f}%")
        match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        match_label.setStyleSheet(StyleSheets.MATCH_LABEL)
        layout.addWidget(match_label)

        # Select Button
        select_button = QPushButton("Select This")
        select_button.setFixedSize(120, 35)
        select_button.setStyleSheet(StyleSheets.SELECT_BUTTON)
        select_button.clicked.connect(self._emit_selected)
        layout.addWidget(select_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        self.setMinimumWidth(CONTAINER_MIN_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_data)
            self._set_selected_style(True)
        super().mousePressEvent(event)

    def _set_selected_style(self, selected: bool):
        """Update visual style to show selection."""
        self._is_selected = selected
        if selected:
            self.preview_widget.setStyleSheet(StyleSheets.PREVIEW_WIDGET_SELECTED)
            self.setStyleSheet(StyleSheets.CONTAINER_SELECTED)
        else:
            self.preview_widget.setStyleSheet(StyleSheets.PREVIEW_WIDGET_NORMAL)
            self.setStyleSheet("")

    def _emit_selected(self) -> None:
        """Emit the selected signal."""
        self.selected.emit(self.mechanism_data)

    def minimumSizeHint(self) -> QSize:
        """Return minimum size hint."""
        return QSize(CONTAINER_MIN_WIDTH, 400)

    def sizeHint(self) -> QSize:
        """Return size hint."""
        return self.minimumSizeHint()