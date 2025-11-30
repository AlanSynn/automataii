"""
Zoom Controls Widget - Inline zoom controls for canvas views.

Extracted as shared component from EditorTab and ImageProcessingTab.
Provides consistent zoom UI across all tabs with canvas views.

Design Pattern: Composite Widget (reusable UI component)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

if TYPE_CHECKING:
    from automataii.presentation.qt.views.editor_view import EditorView
    from automataii.presentation.qt.image_view import ImageProcessingView


class ZoomControlsWidget(QWidget):
    """
    Inline zoom controls widget for canvas views.

    Provides a consistent set of zoom controls that can be embedded
    in any tab's control panel or toolbar.

    Signals:
        zoom_in_clicked: Emitted when zoom in button is clicked
        zoom_out_clicked: Emitted when zoom out button is clicked
        zoom_fit_clicked: Emitted when zoom fit button is clicked
        zoom_reset_clicked: Emitted when zoom reset button is clicked

    Responsibilities:
    - Create styled zoom buttons (+ - ⌖ 1:1)
    - Wire signals for external view control
    - Maintain consistent styling across tabs

    Time Complexity: O(1) for all operations
    """

    # Signals for external handling
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    zoom_fit_clicked = pyqtSignal()
    zoom_reset_clicked = pyqtSignal()

    # Default button style
    DEFAULT_STYLE = """
        QPushButton {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 4px 8px;
            font-weight: bold;
            color: #495057;
            min-height: 22px;
            min-width: 30px;
            font-size: 10pt;
        }
        QPushButton:hover {
            background-color: #e9ecef;
            border-color: #adb5bd;
        }
        QPushButton:pressed {
            background-color: #dee2e6;
            border-color: #6c757d;
        }
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        include_reset: bool = True,
        include_center: bool = False,
        custom_style: str | None = None,
    ):
        """
        Initialize zoom controls widget.

        Args:
            parent: Parent widget
            include_reset: Whether to include the 1:1 reset button
            include_center: Whether to include a center on character button
            custom_style: Optional custom stylesheet override
        """
        super().__init__(parent)

        self._include_reset = include_reset
        self._include_center = include_center
        self._style = custom_style or self.DEFAULT_STYLE

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the zoom controls UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Zoom In button
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setStyleSheet(self._style)
        self.zoom_in_btn.clicked.connect(self.zoom_in_clicked.emit)
        layout.addWidget(self.zoom_in_btn)

        # Zoom Out button
        self.zoom_out_btn = QPushButton("−")  # Using proper minus sign
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setStyleSheet(self._style)
        self.zoom_out_btn.clicked.connect(self.zoom_out_clicked.emit)
        layout.addWidget(self.zoom_out_btn)

        # Zoom Fit button
        self.zoom_fit_btn = QPushButton("⌖")
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.setStyleSheet(self._style)
        self.zoom_fit_btn.clicked.connect(self.zoom_fit_clicked.emit)
        layout.addWidget(self.zoom_fit_btn)

        # Zoom Reset button (optional)
        if self._include_reset:
            self.zoom_reset_btn = QPushButton("1:1")
            self.zoom_reset_btn.setToolTip("Reset Zoom (100%)")
            self.zoom_reset_btn.setStyleSheet(self._style)
            self.zoom_reset_btn.setMinimumWidth(35)
            self.zoom_reset_btn.clicked.connect(self.zoom_reset_clicked.emit)
            layout.addWidget(self.zoom_reset_btn)
        else:
            self.zoom_reset_btn = None

        # Center on Character button (optional)
        if self._include_center:
            self.center_btn = QPushButton("⎈")
            self.center_btn.setToolTip("Center on Character")
            self.center_btn.setStyleSheet(self._style)
            layout.addWidget(self.center_btn)
        else:
            self.center_btn = None

    def connect_to_view(
        self,
        view: EditorView | ImageProcessingView,
        center_callback: callable | None = None,
    ) -> None:
        """
        Connect zoom controls to a canvas view.

        Convenience method to wire signals to a view's zoom methods.

        Args:
            view: The view to control (EditorView or ImageProcessingView)
            center_callback: Optional callback for center button
        """
        # Connect signals to view methods
        self.zoom_in_clicked.connect(lambda: view.zoom(1))
        self.zoom_out_clicked.connect(lambda: view.zoom(-1))
        self.zoom_fit_clicked.connect(view.zoom_to_fit)

        if self.zoom_reset_btn and hasattr(view, "reset_view"):
            self.zoom_reset_clicked.connect(view.reset_view)

        if self.center_btn and center_callback:
            self.center_btn.clicked.connect(center_callback)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all zoom controls."""
        self.zoom_in_btn.setEnabled(enabled)
        self.zoom_out_btn.setEnabled(enabled)
        self.zoom_fit_btn.setEnabled(enabled)
        if self.zoom_reset_btn:
            self.zoom_reset_btn.setEnabled(enabled)
        if self.center_btn:
            self.center_btn.setEnabled(enabled)

    def set_style(self, style: str) -> None:
        """Update the button style."""
        self._style = style
        self.zoom_in_btn.setStyleSheet(style)
        self.zoom_out_btn.setStyleSheet(style)
        self.zoom_fit_btn.setStyleSheet(style)
        if self.zoom_reset_btn:
            self.zoom_reset_btn.setStyleSheet(style)
        if self.center_btn:
            self.center_btn.setStyleSheet(style)
