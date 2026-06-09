"""
Character Selection Dialog.

Dialog for selecting a character preset to assign to mechanisms.
Displays available presets with thumbnails and allows user selection.

Architecture: Presentation Layer - Qt-specific UI component.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from automataii.application.character import CharacterPresetService
    from automataii.domain.character import CharacterPreset


class CharacterSelectionDialog(QDialog):
    """Dialog for selecting a character preset.

    Displays available character presets with thumbnails and descriptions.
    Returns the selected preset on accept.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Character")
        self.setMinimumSize(400, 300)
        self.resize(450, 350)

        self._selected_preset: CharacterPreset | None = None
        self._preset_service: CharacterPresetService | None = None

        self._setup_ui()
        self._load_presets()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("Select a character preset to assign to the mechanism:")
        header.setStyleSheet("font-size: 13px; color: #333;")
        layout.addWidget(header)

        # Content area with list and preview
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Preset list
        self._preset_list = QListWidget()
        self._preset_list.setMinimumWidth(200)
        self._preset_list.setStyleSheet("""
            QListWidget {
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: #1976D2;
            }
            QListWidget::item:hover {
                background-color: #F5F5F5;
            }
        """)
        self._preset_list.itemSelectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self._preset_list, stretch=1)

        # Preview panel
        preview_panel = QVBoxLayout()
        preview_panel.setSpacing(8)

        self._thumbnail_label = QLabel()
        self._thumbnail_label.setFixedSize(120, 150)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        preview_panel.addWidget(self._thumbnail_label)

        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        self._description_label.setStyleSheet("font-size: 12px; color: #666;")
        self._description_label.setMaximumWidth(140)
        preview_panel.addWidget(self._description_label)

        preview_panel.addStretch()
        content_layout.addLayout(preview_panel)

        layout.addLayout(content_layout)

        # Button box
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        # Disable OK until selection is made
        ok_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(False)
            ok_button.setText("Assign")

        layout.addWidget(self._button_box)

    def _load_presets(self) -> None:
        """Load available presets into the list."""
        from automataii.application.character import CharacterPresetService

        self._preset_service = CharacterPresetService()
        available = self._preset_service.get_available_presets()

        for preset_id in available:
            info = self._preset_service.get_preset_info(preset_id)
            if info:
                item = QListWidgetItem(info.get("name", preset_id))
                item.setData(Qt.ItemDataRole.UserRole, preset_id)
                self._preset_list.addItem(item)

        # Select first item by default
        if self._preset_list.count() > 0:
            self._preset_list.setCurrentRow(0)

    def _on_selection_changed(self) -> None:
        """Handle preset selection change."""
        current = self._preset_list.currentItem()
        if not current:
            return

        preset_id = current.data(Qt.ItemDataRole.UserRole)
        if not preset_id or not self._preset_service:
            return

        # Update preview
        info = self._preset_service.get_preset_info(preset_id)
        if info:
            self._description_label.setText(info.get("description", ""))
            self._load_thumbnail(info.get("thumbnail_path"))

        # Enable OK button
        ok_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setEnabled(True)

    def _load_thumbnail(self, path: str | None) -> None:
        """Load and display thumbnail image."""
        if not path:
            self._thumbnail_label.setText("No preview")
            return

        path_obj = Path(path)

        # Handle SVG files
        if path_obj.suffix.lower() == ".svg":
            if path_obj.exists():
                renderer = QSvgRenderer(str(path_obj))
                pixmap = QPixmap(100, 130)
                pixmap.fill(Qt.GlobalColor.transparent)
                from PyQt6.QtGui import QPainter

                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                self._thumbnail_label.setPixmap(
                    pixmap.scaled(
                        100,
                        130,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        # Handle PNG/JPG files
        if path_obj.exists():
            pixmap = QPixmap(str(path_obj))
            if not pixmap.isNull():
                self._thumbnail_label.setPixmap(
                    pixmap.scaled(
                        100,
                        130,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        # Fallback: check for .svg version
        svg_path = path_obj.with_suffix(".svg")
        if svg_path.exists():
            self._load_thumbnail(str(svg_path))
            return

        self._thumbnail_label.setText("Preview\nnot available")

    def _on_accept(self) -> None:
        """Handle dialog acceptance."""
        current = self._preset_list.currentItem()
        if not current or not self._preset_service:
            self.reject()
            return

        preset_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_preset = self._preset_service.get_preset(preset_id)

        if self._selected_preset:
            logging.info(f"Selected character preset: {self._selected_preset.name}")
            self.accept()
        else:
            logging.warning(f"Failed to load preset: {preset_id}")
            self.reject()

    def selected_preset(self) -> CharacterPreset | None:
        """Get the selected preset.

        Returns:
            The selected CharacterPreset, or None if cancelled.
        """
        return self._selected_preset
