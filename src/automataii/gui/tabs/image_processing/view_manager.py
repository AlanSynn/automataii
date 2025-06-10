"""
View Manager for Image Processing Tab

Manages the image processing view and zoom controls.
"""
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QGraphicsScene, QApplication
)
from PyQt6.QtCore import pyqtSignal

from automataii.gui.views.image_view import ImageProcessingView


class ViewManager(QWidget):
    """Manages the image processing view and associated controls."""

    # Signals
    zoom_changed = pyqtSignal(str)  # Emitted when zoom level changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab = parent  # Keep a reference to the parent tab

        # Create scene and view
        self.scene = QGraphicsScene(self)
        self.view = ImageProcessingView(
            self.scene,
            project_data_manager=self.tab.main_window.project_data_manager,
            parent=self,
        )

        # Zoom controls
        self.zoom_combo = QComboBox()
        self.fit_btn = QPushButton("Fit")

        self._init_ui()
        self._setup_zoom_controls()

    def _init_ui(self):
        """Initialize the view manager UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Add the view
        layout.addWidget(self.view, 1)

        # Create zoom toolbar (will be positioned as overlay)
        self.zoom_toolbar = self._create_zoom_toolbar()

    def _create_zoom_toolbar(self) -> QWidget:
        """Create the zoom toolbar widget."""
        toolbar = QWidget(self)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addStretch()

        # Configure zoom combo
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedSize(80, 28)
        self.zoom_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 4px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """)

        # Configure fit button
        self.fit_btn.setFixedSize(45, 28)
        self.fit_btn.setStyleSheet("""
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
        """)

        # Add controls
        layout.addWidget(self.zoom_combo)
        layout.addWidget(self.fit_btn)

        # Style the toolbar
        toolbar.setStyleSheet("""
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """)

        return toolbar

    def _setup_zoom_controls(self):
        """Setup zoom control options and connections."""
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.zoom_combo.addItems(zoom_levels)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom level")
        self.fit_btn.setToolTip("Zoom to fit all items")

        # Connect signals
        self.zoom_combo.currentTextChanged.connect(self._handle_zoom_change)
        self.fit_btn.clicked.connect(self._handle_fit_click)

    def _handle_zoom_change(self, zoom_text: str):
        """Handle zoom combo box changes."""
        try:
            if zoom_text.lower() == "fit":
                self.view.zoom_to_fit()
                return

            if zoom_text.endswith("%"):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text)

            # Clamp zoom value
            zoom_value = max(0.1, min(zoom_value, 10.0))

            self.view.set_zoom_level(zoom_value)

            # Update combo box
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.zoom_combo.blockSignals(False)

            self.zoom_changed.emit(f"{int(zoom_value * 100)}%")

        except ValueError:
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText("100%")
            self.zoom_combo.blockSignals(False)
            self.view.set_zoom_level(1.0)
        except Exception as e:
            logging.error(f"Error in zoom change: {e}")

    def _handle_fit_click(self):
        """Handle fit button click."""
        self.view.zoom_to_fit()
        current_scale = self.view.transform().m11()
        zoom_percent = int(current_scale * 100)
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.zoom_combo.blockSignals(False)
        self.zoom_changed.emit(f"{zoom_percent}%")

    def showEvent(self, event):
        """Handle show event to position zoom toolbar."""
        super().showEvent(event)
        self._position_zoom_toolbar()

    def resizeEvent(self, event):
        """Handle resize event to reposition zoom toolbar."""
        super().resizeEvent(event)
        self._position_zoom_toolbar()

    def _position_zoom_toolbar(self):
        """Position the zoom toolbar as an overlay."""
        if not self.isVisible() or not self.zoom_toolbar.isVisible():
            return

        toolbar_width = self.zoom_toolbar.sizeHint().width()
        toolbar_height = self.zoom_toolbar.sizeHint().height()
        x = self.width() - toolbar_width - 10
        y = self.height() - toolbar_height - 10
        self.zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

    def load_image(self, image_path: str) -> bool:
        """Load an image into the view."""
        logging.info(f"ViewManager: load_image called with {image_path}")
        result = self.view.load_image(image_path)
        logging.info(f"ViewManager: view.load_image returned {result}")

        # Check if view and scene are properly set up
        if hasattr(self, 'view') and self.view:
            logging.info(f"ViewManager: view exists")
            if self.view.scene():
                logging.info(f"ViewManager: scene exists with {len(self.view.scene().items())} items")
            else:
                logging.error("ViewManager: view has no scene!")
        else:
            logging.error("ViewManager: view does not exist!")

        return result

    def load_skeleton(self, skeleton_data: Optional[dict]) -> bool:
        """Load skeleton data into the view."""
        result = self.view.load_skeleton(skeleton_data)
        return result if result is not None else True

    def get_skeleton_data(self) -> Optional[dict]:
        """Get current skeleton data from the view."""
        return self.view.get_skeleton_data()

    def set_edit_mode(self, enabled: bool):
        """Enable or disable skeleton edit mode."""
        self.view.set_edit_mode(enabled)

    def show_skeleton_visuals(self, visible: bool):
        """Show or hide skeleton visuals."""
        self.view.show_skeleton_visuals(visible)

    def show_part_visuals(self, visible: bool):
        """Show or hide part visuals."""
        self.view.show_part_visuals(visible)

    def load_parts(self, parts_info: dict):
        """Load character parts into the view."""
        logging.info(f"ViewManager: Passing part loading to view for {len(parts_info)} parts.")
        if hasattr(self.view, "load_parts"):
            self.view.load_parts(parts_info)
        else:
            logging.error("ViewManager: view object does not have a load_parts method.")

    def load_character_parts(self, parts_info: dict, skeleton_to_part_map: dict, effective_offset: tuple):
        """Load character parts into the view."""
        self.view.load_character_parts(parts_info, skeleton_to_part_map, effective_offset)

    def get_part_manager(self):
        return self._part_manager

    def set_skeleton_visibility(self, visible: bool):
        """Sets the visibility of the skeleton."""
        if self._skeleton_manager:
            self._skeleton_manager.set_skeleton_visualization_visibility(visible)

    def clear_scene(self, clear_image=False):
        """Clears the scene of all items, optionally keeping the image."""
        if self.view:
            self.view.clear_scene(clear_image)