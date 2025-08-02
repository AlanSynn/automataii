# src/automataii/ui/tabs/image_processing/tab.py

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene, QHBoxLayout

from automataii.ui.tabs.base.tab import BaseTab
from automataii.ui.views.image_processing.view import ImageProcessingView

from .action_handler import ImageProcessingActionHandler
from .scene_manager import ImageProcessingSceneManager
from .state_manager import ImageProcessingStateManager
from .ui_panel import ImageProcessingControlPanel

logger = logging.getLogger(__name__)


class ImageProcessingTab(BaseTab):
    """
    The main widget for the Image Processing Tab, orchestrating all components.
    """

    # Signals expected by main_window.py
    parts_generated = pyqtSignal(dict, str)
    skeleton_updated = pyqtSignal(dict)
    request_editor_tab_switch = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)
        self._init_architecture()
        logger.info("ImageProcessingTab initialized with new architecture.")

    def _init_architecture(self):
        """Initialize all managers and UI components."""
        # Create scene and view
        self.scene = QGraphicsScene(self)
        self.view = ImageProcessingView(self.scene, self)

        # Create managers
        self.state = ImageProcessingStateManager(self)
        self.scene_manager = ImageProcessingSceneManager(self.scene, self.view, self.state, self)
        self.action_handler = ImageProcessingActionHandler(
            self.state, self.scene_manager, self.main_window, self
        )

        # Create UI panel
        self.ui_panel = ImageProcessingControlPanel(self)

        # Create horizontal layout for image processing
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(self._design_system.spacing.md)
        main_layout.addWidget(self.ui_panel)
        main_layout.addWidget(self.view, 1)  # View takes most space

        # Connect components
        self._connect_components()

    def _connect_components(self):
        """Connect signals between all components."""

        # UI Panel -> Action Handler
        self.ui_panel.load_image_clicked.connect(self.action_handler.handle_load_image)
        self.ui_panel.capture_image_clicked.connect(self.action_handler.handle_capture_image)

        # Processing steps group -> Action Handler
        processing_group = self.ui_panel.get_processing_steps_group()
        processing_group.processImageClicked.connect(self.action_handler.handle_process_image)
        processing_group.editSkeletonClicked.connect(self.action_handler.handle_edit_skeleton)
        processing_group.saveSkeletonClicked.connect(self.action_handler.handle_save_skeleton)
        processing_group.generatePartsClicked.connect(self.action_handler.handle_generate_parts)
        processing_group.extendSkeletonClicked.connect(self.action_handler.handle_extend_skeleton)
        processing_group.lockJointsClicked.connect(self.action_handler.handle_lock_joints)

        # View controls -> Scene Manager
        self.ui_panel.zoom_in_clicked.connect(self.scene_manager.zoom_in)
        self.ui_panel.zoom_out_clicked.connect(self.scene_manager.zoom_out)
        self.ui_panel.zoom_fit_clicked.connect(self.scene_manager.zoom_to_fit)
        self.ui_panel.zoom_reset_clicked.connect(self.scene_manager.reset_view)
        self.ui_panel.image_zoom_changed.connect(self._handle_image_zoom_change)
        self.ui_panel.image_fit_clicked.connect(self._handle_image_zoom_change_fit)

        # State Manager -> UI Panel
        self.state.state_changed.connect(lambda: self.ui_panel.update_ui_from_state(self.state))

        # Action Handler -> Tab signals (for main window)
        self.action_handler.parts_generated.connect(self.parts_generated.emit)
        self.action_handler.skeleton_updated.connect(self.skeleton_updated.emit)
        self.action_handler.request_editor_tab_switch.connect(self.request_editor_tab_switch.emit)

    def _handle_image_zoom_change(self, zoom_text: str):
        """Handle zoom combo box changes."""
        try:
            # Extract percentage and convert to scale factor
            zoom_str = zoom_text.strip().replace("%", "")
            zoom_percent = float(zoom_str)
            scale_factor = zoom_percent / 100.0

            # Apply zoom to view
            if hasattr(self.view, "set_zoom_scale"):
                self.view.set_zoom_scale(scale_factor)
            elif hasattr(self.view, "setTransform"):
                # Fallback if specific method doesn't exist
                from PyQt6.QtGui import QTransform

                transform = QTransform()
                transform.scale(scale_factor, scale_factor)
                self.view.setTransform(transform)

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to set zoom level: {e}")

    def _handle_image_zoom_change_fit(self):
        """Handle fit button click."""
        self.scene_manager.zoom_to_fit()

    # Public API methods for main window integration

    def load_input_image(self, image_path: str):
        """Load an image from the specified path."""
        self.action_handler.load_image_from_path(image_path)

    def _load_image_from_path(self, image_path: str) -> bool:
        """Load an image from the specified path. Returns True if successful."""
        try:
            self.action_handler.load_image_from_path(image_path)
            
            # Auto-process the image after loading
            logger.info(f"Auto-processing image after loading: {image_path}")
            from PyQt6.QtCore import QTimer
            # Delay processing slightly to ensure UI is ready
            QTimer.singleShot(500, self.action_handler.handle_process_image)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load image from {image_path}: {e}")
            return False

    def on_parts_loaded_in_editor(self, loaded: bool):
        """React to parts being loaded in editor tab."""
        self.state.on_parts_loaded_in_editor(loaded)

    def on_skeleton_updated_externally(self, skeleton_data: dict):
        """Update when skeleton changes externally."""
        self.scene_manager.update_skeleton_from_external(skeleton_data)
        # Sync with state
        self.state.set_skeleton_data(skeleton_data)

    def _toggle_detailed_processing_visibility(self, visible: bool):
        """Toggle processing steps visibility."""
        processing_group = self.ui_panel.get_processing_steps_group()
        processing_group.setVisible(visible)

    def clear_all_data(self):
        """Clear all data from the tab."""
        self.state.clear_all()
        self.scene_manager.clear_scene()
        logger.info("ImageProcessingTab: All data cleared")

    # Architecture component getters for external access
    def get_state_manager(self):
        """Get the state manager for external access."""
        return self.state

    def get_action_handler(self):
        """Get the action handler for external access."""
        return self.action_handler

    def get_ui_panel(self):
        """Get the UI panel for external access."""
        return self.ui_panel

    def get_scene_manager(self):
        """Get the scene manager for external access."""
        return self.scene_manager

    def activate_tab(self) -> None:
        """Called when the tab becomes active."""
        super().activate_tab()  # Call parent to apply theme styles
        logger.debug("ImageProcessingTab activated")
        # Resume any background processing
        if self.action_handler:
            self.action_handler.resume_processing()

        # Refresh view state
        if self.view and self.state:
            self.state.refresh_display()

    def deactivate_tab(self) -> None:
        """Called when the tab becomes inactive."""
        logger.debug("ImageProcessingTab deactivated")
        # Pause any background processing to save resources
        if self.action_handler:
            self.action_handler.pause_processing()

        # Clear any temporary graphics items
        if self.scene:
            # Remove temporary overlays and guides
            temp_items = [
                item
                for item in self.scene.items()
                if hasattr(item, "is_temporary") and item.is_temporary
            ]
            for item in temp_items:
                self.scene.removeItem(item)
                if hasattr(item, "deleteLater"):
                    item.deleteLater()

        # Force garbage collection for this tab's resources
        import gc

        gc.collect()
