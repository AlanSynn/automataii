"""
Image Processing Tab Coordinator

Main coordinator that brings together all components of the image processing tab.
"""
import logging
from typing import Optional, Dict

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QMessageBox
from PyQt6.QtCore import QTimer

from ....core.models.mechanism import PartInfo
from PyQt6.QtCore import pyqtSignal

from .state_manager import ImageProcessingState
from .control_panels import ImageProcessingControlPanel
from .view_manager import ViewManager
from .services import ImageService, ProcessingService, SkeletonService, PartsService
from automataii.gui.views.image.skeleton_visualizer import SkeletonVisualizer


class ImageProcessingTab(QWidget):
    """Main image processing tab widget that coordinates all components."""

    # Signals
    parts_generated = pyqtSignal(dict, str)
    skeleton_updated = pyqtSignal(dict)
    request_editor_tab_switch = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.validated_parts_info: Optional[Dict[str, PartInfo]] = None
        logging.info("ImageProcessingTab: Initializing...")

        # Initialize state manager
        self.state = ImageProcessingState()
        logging.info("ImageProcessingTab: State manager initialized")

        # Initialize services
        self.image_service = ImageService(self)
        self.processing_service = ProcessingService(self)
        self.skeleton_service = SkeletonService(self)
        self.parts_service = PartsService(self)
        logging.info("ImageProcessingTab: Services initialized")

        # Initialize UI components
        self.control_panel = ImageProcessingControlPanel(self)
        logging.info("ImageProcessingTab: Control panel initialized")

        self.view_manager = ViewManager(self)
        logging.info("ImageProcessingTab: View manager initialized")

        # Pass the scene to the visualizer
        self.skeleton_visualizer = SkeletonVisualizer(self.view_manager.scene)

        # For backwards compatibility
        self.image_proc_view = self.view_manager.view
        self.image_proc_scene = self.view_manager.scene

        self._init_ui()
        logging.info("ImageProcessingTab: UI initialized")

        self._connect_signals()
        logging.info("ImageProcessingTab: Signals connected")
        logging.info("ImageProcessingTab: Initialization complete")

    def _init_ui(self):
        """Initialize the tab UI layout."""
        layout = QHBoxLayout(self)
        layout.addWidget(self.control_panel)
        layout.addWidget(self.view_manager, 1)
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect all signals between components."""
        # Control panel signals
        self.control_panel.load_image_btn.clicked.connect(self.load_input_image)
        self.control_panel.capture_image_btn.clicked.connect(self.capture_image)
        self.control_panel.next_stage_btn.clicked.connect(self.next_stage)

        # Processing steps signals
        steps = self.control_panel.processing_steps_group
        steps.processImageClicked.connect(self.process_image)
        steps.editSkeletonClicked.connect(self.edit_skeleton)
        steps.saveSkeletonClicked.connect(self.save_skeleton)
        steps.generatePartsClicked.connect(self.create_parts_from_skeleton)
        steps.extendSkeletonClicked.connect(self.extend_skeleton)
        steps.lockJointsClicked.connect(self.show_lock_joints_dialog)

        # View options signals
        self.control_panel.show_skeleton_checkbox.toggled.connect(
            self.skeleton_visualizer.set_visibility
        )
        self.control_panel.show_parts_checkbox.toggled.connect(
            self._toggle_parts_visibility
        )

    # --- Image Loading Methods ---

    def load_input_image(self):
        """Load an image from file."""
        filepath, _ = self.image_service.load_image_from_file(self.state.character_dir)
        if filepath:
            self._handle_image_loaded(filepath)

    def capture_image(self):
        """Capture an image from camera."""
        filepath = self.image_service.capture_from_camera(self.state.active_camera_dialogs)
        if filepath:
            self._handle_image_loaded(filepath)

    def _load_image_from_path(self, image_path: str) -> bool:
        """Load an image from a given path (used by landing tab)."""
        logging.info(f"ImageProcessingTab: _load_image_from_path called with: {image_path}")

        result = self.view_manager.load_image(image_path)
        logging.info(f"ImageProcessingTab: view_manager.load_image returned: {result}")

        if result:
            self.state.update_from_image_load(image_path)
            # Don't show processing steps - keep them hidden
            self._update_button_states()
            self._update_status(f"Loaded input image: {image_path}")

            # Check if image is actually visible in the scene
            if hasattr(self.view_manager, 'view') and self.view_manager.view.scene():
                scene_items = self.view_manager.view.scene().items()
                logging.info(f"ImageProcessingTab: Scene has {len(scene_items)} items after image load")

                # Try to fit the view to the loaded image
                self.view_manager.view.zoom_to_fit()
                logging.info("ImageProcessingTab: Called zoom_to_fit on view")

            # Auto-process if enabled
            if self.state.has_image() and self.state.character_dir:
                self.process_image()
                if self.state.has_skeleton():
                    self.create_parts_from_skeleton()

            return True
        else:
            logging.error(f"ImageProcessingTab: Failed to load image: {image_path}")
            QMessageBox.warning(self, "Load Error", f"Could not load image: {image_path}")
            return False

    def _auto_process_after_delay(self):
        """Auto-process image after delay to let user see original first."""
        if self.state.has_image() and self.state.character_dir:
            self.process_image()
            if self.state.has_skeleton():
                self.create_parts_from_skeleton()

    def _handle_image_loaded(self, filepath: str):
        """Handle successful image loading."""
        if self.view_manager.load_image(filepath):
            self.state.update_from_image_load(filepath)
            self._update_status(f"Loaded input image: {filepath}")

            # Auto-process if configured
            if self.state.has_image() and self.state.character_dir:
                self.process_image()
                if self.state.has_skeleton():
                    self.create_parts_from_skeleton()
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {filepath}")

    # --- Processing Methods ---

    def process_image(self):
        """Process the loaded image."""
        if not self.state.has_image():
            QMessageBox.warning(self, "Warning", "No input image loaded.")
            self._update_button_states()
            return

        self._update_status("Processing image...")

        # Process image
        annotation_results = self.processing_service.process_image(
            self.state.input_image_path
        )

        if annotation_results:
            self.state.current_annotation_results = annotation_results
            self.state.current_temp_char_dir = annotation_results["output_dir"]

            # Load processed texture first
            self.view_manager.load_image(annotation_results["texture_path"])

            # Load skeleton from generated config
            char_cfg_path = annotation_results["char_cfg_path"]
            # Load skeleton data directly for the image view
            raw_skeleton_data = self.skeleton_service.load_skeleton_from_file(char_cfg_path)
            if raw_skeleton_data:
                # Load skeleton into view using the raw YAML data
                load_result = self.view_manager.load_skeleton(raw_skeleton_data)
                logging.info(f"view_manager.load_skeleton returned: {load_result}")

                if load_result:
                    # Store for other uses
                    self.state.skeleton_data = raw_skeleton_data
                    self.skeleton_updated.emit(raw_skeleton_data)
                    self._update_button_states()

                    # Ensure skeleton is visible if checkbox is checked
                    if self.control_panel.show_skeleton_checkbox.isChecked():
                        self.skeleton_visualizer.load_skeleton(raw_skeleton_data)
                        self.skeleton_visualizer.set_visibility(True)

                    # Auto-generate parts after skeleton is loaded
                    logging.info("Auto-generating parts after skeleton load")
                    self.create_parts_from_skeleton()

            self._update_status("Image processed successfully", 5000)
        else:
            self.state.current_annotation_results = None
            self.state.current_temp_char_dir = None
            self._update_status("Image processing failed", 5000)

        self._update_button_states()

    # --- Skeleton Methods ---

    def _load_skeleton_from_config(self, char_cfg_filepath: str) -> bool:
        """Load skeleton data from config file."""
        skeleton_data = self.skeleton_service.load_skeleton_from_file(char_cfg_filepath)

        if skeleton_data:
            logging.info(f"Skeleton data loaded from service: {bool(skeleton_data)}")
            load_result = self.view_manager.load_skeleton(skeleton_data)
            logging.info(f"view_manager.load_skeleton returned: {load_result}")
            if load_result:
                self.state.skeleton_data = skeleton_data
                self.skeleton_updated.emit(skeleton_data)
                self._update_button_states()
                return True
            else:
                logging.warning("view_manager.load_skeleton returned False")
        else:
            logging.warning("skeleton_service.load_skeleton_from_file returned None")

        return False

    def edit_skeleton(self):
        """Enable skeleton editing mode."""
        if not self.view_manager.view.joints:
            QMessageBox.information(
                self,
                "Edit Skeleton",
                "No skeleton loaded to edit. Please process an image first."
            )
            return

        self.view_manager.set_edit_mode(True)
        self._update_status("Skeleton editing enabled. Drag joints to modify.")

    def save_skeleton(self):
        """Save the current skeleton."""
        skeleton_data = self.view_manager.get_skeleton_data()
        if not skeleton_data:
            QMessageBox.warning(self, "Save Error", "No skeleton data to save.")
            return

        save_path = self.skeleton_service.save_skeleton(
            skeleton_data,
            self.state.character_dir
        )

        if save_path:
            self.state.skeleton_data = skeleton_data
            self.skeleton_updated.emit(skeleton_data)
            self._update_status(f"Skeleton saved to {save_path}")

    def extend_skeleton(self):
        """Extend skeleton bone lengths."""
        if not self.main_window or not self.main_window.skeleton_manager:
            return

        if self.skeleton_service.extend_skeleton(self.main_window.skeleton_manager):
            # Update view with modified skeleton
            if self.main_window.skeleton_manager.standardized_model:
                updated_skeleton = self.main_window.skeleton_manager.standardized_model.model_dump()
                self.state.skeleton_data = updated_skeleton
                self.view_manager.load_skeleton(updated_skeleton)
                self._update_status("Skeleton extended by 10%", 3000)

    def show_lock_joints_dialog(self):
        """Show joint locking dialog."""
        if not self.main_window or not self.main_window.skeleton_manager:
            return

        if self.skeleton_service.show_lock_joints_dialog(self.main_window.skeleton_manager):
            # Update view with modified skeleton
            if self.main_window.skeleton_manager.standardized_model:
                updated_skeleton = self.main_window.skeleton_manager.standardized_model.model_dump()
                self.state.skeleton_data = updated_skeleton
                self.view_manager.load_skeleton(updated_skeleton)

    # --- Parts Generation Methods ---

    def create_parts_from_skeleton(self):
        """Generate body parts from skeleton."""
        logging.info(f"create_parts_from_skeleton called. has_skeleton={self.state.has_skeleton()}, has_annotation_results={self.state.has_annotation_results()}")
        if not self.state.can_generate_parts():
            logging.warning(f"Cannot generate parts: skeleton_data={bool(self.state.skeleton_data)}, annotation_results={bool(self.state.current_annotation_results)}")
            QMessageBox.warning(
                self,
                "Missing Data",
                "Cannot create parts. Please process image first."
            )
            return

        parts_info_path, output_dir = self.parts_service.generate_parts(
            self.state.current_annotation_results,
            self.state.current_temp_char_dir
        )

        if parts_info_path:
            self.state.current_parts_info_path = parts_info_path
            self.parts_generated.emit(
                self.state.current_annotation_results,
                output_dir
            )
            self._update_button_states()

            # Trigger parts visibility update after a small delay to ensure they're loaded
            QTimer.singleShot(500, self._ensure_parts_visible)

            # Show parts immediately if checkbox is checked
            if self.control_panel.show_parts_checkbox.isChecked():
                # Wait for parts to be loaded by the signal handler
                QTimer.singleShot(100, lambda: self._toggle_parts_visibility(True))

    # --- Navigation Methods ---

    def next_stage(self):
        """Proceed to the editor tab."""
        if (
            not self.main_window
            or not self.main_window.project_data_manager
            or not self.main_window.project_data_manager.parts
        ):
            QMessageBox.information(
                self,
                "Next Stage",
                "Please process image and generate parts first."
            )
            return

        self.request_editor_tab_switch.emit()
        logging.info("Requested switch to Editor Tab.")

    # --- View Management Methods ---

    def _ensure_parts_visible(self):
        """Ensure parts are visible if checkbox is checked."""
        if self.control_panel.show_parts_checkbox.isChecked():
            self._toggle_parts_visibility(True)

    def _toggle_parts_visibility(self, checked: bool):
        """Toggle visibility of body parts."""
        if not self.view_manager:
            return

        if checked:
            parts_info = self.validated_parts_info
            if not parts_info:
                # Fallback for older logic or race conditions
                if (
                    self.main_window
                    and self.main_window.project_data_manager
                    and self.main_window.project_data_manager.parts
                ):
                    parts_info = self.main_window.project_data_manager.parts

            if parts_info:
                effective_offset = (
                    self.main_window.project_data_manager.effective_bounding_box_offset
                )
                self.view_manager.load_character_parts(parts_info, {}, effective_offset)
                self.view_manager.show_part_visuals(True)
            else:
                logging.warning("Cannot show parts, no parts loaded.")
                self.control_panel.show_parts_checkbox.setChecked(False)
                QMessageBox.information(
                    self,
                    "View Parts",
                    "No part data has been loaded. Please process an image first.",
                )
        else:
            self.view_manager.show_part_visuals(False)

    # --- External Update Methods ---

    def on_project_data_loaded(self, parts_info: Dict[str, PartInfo]):
        """Receives validated parts data from the ProjectCoordinator."""
        logging.info(
            f"ImageProcessingTab: Received validated parts data for {len(parts_info)} parts."
        )
        self.validated_parts_info = parts_info
        self._update_button_states()

    def on_parts_loaded_in_editor(self, loaded: bool):
        """Handle parts loaded notification from editor."""
        logging.info(f"Parts loaded in editor: {loaded}")
        self._update_button_states()

    def on_skeleton_updated_externally(self, skeleton_data_dict: Optional[dict]):
        """
        Slot to be called when skeleton data is updated from another source,
        like the ProjectDataManager after a project load.
        """
        # logging.info("Received external skeleton update")
        if skeleton_data_dict:
            # The new visualizer now takes the standardized dict directly
            self.skeleton_visualizer.load_skeleton(skeleton_data_dict)
            self.skeleton_visualizer.set_visibility(
                self.control_panel.show_skeleton_checkbox.isChecked()
            )
        else:
            self.skeleton_visualizer.clear()

    # --- Helper Methods ---

    def _update_button_states(self):
        """Update button states based on current state."""
        parts_loaded = (
            self.main_window.project_data_manager.parts is not None
            and len(self.main_window.project_data_manager.parts) > 0
        )

        self.control_panel.update_button_states(
            has_image=self.state.has_image(),
            has_skeleton=self.state.has_skeleton(),
            has_parts=self.state.has_parts_info(),
            can_proceed=parts_loaded
        )

    def _update_status(self, message: str, timeout: int = 0):
        """Update the status bar message."""
        if self.main_window:
            self.main_window.statusBar().showMessage(message, timeout)

    def update_button_states(self):
        """Public method for backwards compatibility."""
        self._update_button_states()
