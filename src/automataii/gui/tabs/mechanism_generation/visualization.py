"""Visualization components for mechanism generation."""

import logging
from typing import Optional, Dict, List, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QGraphicsScene, QGraphicsEllipseItem, QGraphicsItem, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath

from automataii.gui.views.editor.editor_view import EditorView
from automataii.gui.graphics_items.part_item import CharacterPartItem
from automataii.processing.animation.parts_extraction.models import PartInfo
from .mechanism_graphics import (
    AnimatedFourBarLinkage, AnimatedCamFollower, AnimatedGearTrain,
    MechanismColors
)
from automataii.gui.dialogs.recommendation.constants import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
)


class MechanismVisualizationWidget(QWidget):
    """Widget for mechanism visualization with zoom controls."""

    # Signals for point selection
    cam_center_selected = pyqtSignal(QPointF)
    pivot_a_selected = pyqtSignal(QPointF)
    pivot_d_selected = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)

        # Scene and view
        self.scene = QGraphicsScene(self)
        self.view = EditorView(self.scene, self)

        # Visual markers
        self._markers: Dict[str, QGraphicsEllipseItem] = {}
        self._mechanism_items: List[QGraphicsItem] = []
        self._animated_mechanisms: List[QGraphicsItem] = []

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Main view
        layout.addWidget(self.view, 1)

        # Create zoom toolbar
        self._create_zoom_toolbar()

    def _create_zoom_toolbar(self):
        """Create floating zoom toolbar."""
        self.zoom_toolbar = QWidget(self)
        zoom_layout = QHBoxLayout(self.zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        # Zoom combo
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedSize(70, 28)
        self.zoom_combo.setStyleSheet(self._get_zoom_combo_style())
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.zoom_combo.addItems(zoom_levels)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom level for mechanism view")

        # Fit button
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setFixedSize(45, 28)
        self.fit_btn.setStyleSheet(self._get_fit_button_style())
        self.fit_btn.setToolTip("Zoom to fit all items in mechanism view")

        zoom_layout.addWidget(self.zoom_combo)
        zoom_layout.addWidget(self.fit_btn)

        # Style toolbar
        self.zoom_toolbar.setStyleSheet(
            """
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
            """
        )

    def _get_zoom_combo_style(self) -> str:
        return """
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """

    def _get_fit_button_style(self) -> str:
        return """
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 4px;
                background-color: white;
                font-size: 13px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """

    def _connect_signals(self):
        """Connect internal signals."""
        # View signals
        self.view.cam_center_selected.connect(self.cam_center_selected.emit)
        self.view.pivot_a_selected.connect(self.pivot_a_selected.emit)
        self.view.pivot_d_selected.connect(self.pivot_d_selected.emit)

        # Zoom controls
        self.zoom_combo.currentTextChanged.connect(self._handle_zoom_changed)
        self.fit_btn.clicked.connect(self.view.zoom_to_fit)

    def _handle_zoom_changed(self, zoom_text: str):
        """Handle zoom combo box value change."""
        if not zoom_text:
            return

        try:
            zoom_value = float(zoom_text.strip('%'))
            self.view.set_zoom(zoom_value / 100.0)
        except ValueError:
            pass

    def showEvent(self, event):
        """Handle show event to position toolbar."""
        super().showEvent(event)
        QApplication.instance().processEvents()
        self._position_zoom_toolbar()

    def resizeEvent(self, event):
        """Handle resize event to reposition toolbar."""
        super().resizeEvent(event)
        self._position_zoom_toolbar()

    def _position_zoom_toolbar(self):
        """Position the zoom toolbar in bottom-right corner."""
        if not self.isVisible() or not self.zoom_toolbar.isVisible():
            return

        toolbar_width = self.zoom_toolbar.sizeHint().width()
        toolbar_height = self.zoom_toolbar.sizeHint().height()
        x = self.width() - toolbar_width - 10
        y = self.height() - toolbar_height - 10
        self.zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

    def set_selection_mode(self, mode: str):
        """Set the view's selection mode."""
        self.view.set_mode(mode)

    def add_character_parts(self, parts: Dict[str, CharacterPartItem]):
        """Add character parts to the scene."""
        # Clear existing parts
        for item in list(self.scene.items()):
            if isinstance(item, CharacterPartItem):
                self.scene.removeItem(item)

        # Add new parts
        for part_name, part_item in parts.items():
            # Create a copy of the part item
            pixmap = part_item.pixmap()
            new_item = CharacterPartItem(pixmap, part_name, part_item.part_info)
            new_item.setPos(part_item.scenePos())
            new_item.setRotation(part_item.rotation())
            new_item.setZValue(part_item.zValue())
            self.scene.addItem(new_item)

    def highlight_part(self, part_name: str):
        """Highlight a specific part."""
        for item in self.scene.items():
            if isinstance(item, CharacterPartItem):
                item.setSelected(item.part_name == part_name)

    def add_point_marker(self, marker_id: str, point: QPointF, color: QColor):
        """Add or update a point marker."""
        # Remove existing marker if present
        if marker_id in self._markers:
            self.scene.removeItem(self._markers[marker_id])

        # Create new marker
        marker = QGraphicsEllipseItem(-5, -5, 10, 10)
        marker.setPos(point)
        marker.setPen(QPen(color, 2))
        marker.setBrush(QBrush(color))
        marker.setZValue(1000)  # High z-value to be on top
        self.scene.addItem(marker)

        self._markers[marker_id] = marker
        self._logger.info(f"Added marker '{marker_id}' at {point}")

    def remove_point_marker(self, marker_id: str):
        """Remove a point marker."""
        if marker_id in self._markers:
            self.scene.removeItem(self._markers[marker_id])
            del self._markers[marker_id]

    def clear_markers(self):
        """Clear all point markers."""
        for marker in self._markers.values():
            self.scene.removeItem(marker)
        self._markers.clear()

    def add_mechanism_visual(self, item: QGraphicsItem):
        """Add a mechanism visual item."""
        self.scene.addItem(item)
        self._mechanism_items.append(item)

    def visualize_mechanism(self, mechanism_data: Dict):
        """Visualize a complete mechanism with animation."""
        # Clear previous animated mechanisms
        for item in self._animated_mechanisms:
            if item.scene():
                self.scene.removeItem(item)
        self._animated_mechanisms.clear()

        mechanism_type = mechanism_data.get("type", "")

        # Create appropriate animated mechanism
        if mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            mechanism = AnimatedFourBarLinkage(mechanism_data)
            self.scene.addItem(mechanism)
            self._animated_mechanisms.append(mechanism)

        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            mechanism = AnimatedCamFollower(mechanism_data)
            self.scene.addItem(mechanism)
            self._animated_mechanisms.append(mechanism)

        elif mechanism_type == "gear_train":
            mechanism = AnimatedGearTrain(mechanism_data)
            self.scene.addItem(mechanism)
            self._animated_mechanisms.append(mechanism)

        self._logger.info(f"Visualized {mechanism_type} mechanism")

    def start_mechanism_animation(self):
        """Start animation for all mechanisms."""
        for mechanism in self._animated_mechanisms:
            if hasattr(mechanism, 'start_animation'):
                mechanism.start_animation()

    def stop_mechanism_animation(self):
        """Stop animation for all mechanisms."""
        for mechanism in self._animated_mechanisms:
            if hasattr(mechanism, 'stop_animation'):
                mechanism.stop_animation()

    def reset_mechanism_animation(self):
        """Reset animation for all mechanisms."""
        for mechanism in self._animated_mechanisms:
            if hasattr(mechanism, 'reset_animation'):
                mechanism.reset_animation()

    def clear_mechanism_visuals(self):
        """Clear all mechanism visual items."""
        for item in self._mechanism_items:
            if item.scene():
                self.scene.removeItem(item)
        self._mechanism_items.clear()

    def visualize_skeleton(self, skeleton_data: Dict):
        """Visualize skeleton joints and connections."""
        # This would implement skeleton visualization
        # Similar to editor_tab's skeleton visualization
        pass

    def visualize_motion_path(self, path: QPainterPath, color: QColor = QColor(100, 200, 100)):
        """Visualize a motion path."""
        from PyQt6.QtWidgets import QGraphicsPathItem

        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
        path_item.setZValue(500)  # Above parts but below markers
        self.scene.addItem(path_item)
        self._mechanism_items.append(path_item)

    def clear_all(self):
        """Clear all visualization elements."""
        self.scene.clear()
        self._markers.clear()
        self._mechanism_items.clear()
        self._animated_mechanisms.clear()
        self._logger.info("Visualization cleared")