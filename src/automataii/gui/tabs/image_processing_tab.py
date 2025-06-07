import os
import logging
import tempfile
import time
import yaml
import cv2  # Assuming cv2 is used by capture_image or process_image
import json
from typing import Optional, Dict, Any
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
    QSizePolicy,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QDialog,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..dialogs.camera_dialog import CameraDialog
from ..views.image_view import ImageProcessingView
from PyQt6.QtWidgets import QGraphicsScene
from ..widgets.processing_steps_group import ProcessingStepsGroup

# Automataii specific imports
from ...animate.image_to_annotations import image_to_annotations, AnnotationResults
from ...animate.body_parts_extractor import BodyPartsExtractor


class ImageProcessingTab(QWidget):
    # Signal to indicate parts have been generated and parts_info.json is ready
    parts_generated = pyqtSignal(dict, str)
    # Signal to indicate skeleton has been loaded/updated
    skeleton_updated = pyqtSignal(dict)
    # Signal to request a switch to the editor tab
    request_editor_tab_switch = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = (
            main_window  # Reference to MainWindow for shared resources/status bar
        )

        # Tab-specific data
        self.input_image_path: Optional[str] = None
        self.character_dir: Optional[str] = None
        self.current_temp_char_dir: Optional[str] = None
        self.current_annotation_results: Optional[AnnotationResults] = None
        self.skeleton_data: Optional[dict] = None
        self.active_camera_dialogs: list = []

        # Instantiate scene and view here
        self.image_proc_scene = QGraphicsScene(self)
        self.image_proc_view = ImageProcessingView(self.image_proc_scene, self)

        # Add the new ProcessingStepsGroup, initially hidden
        self.processing_steps_group = ProcessingStepsGroup()
        self.processing_steps_group.setVisible(False)  # Hidden by default

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left Control Panel
        control_panel = QWidget()
        control_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(5, 10, 5, 10)
        panel_layout.setSpacing(10)

        # Input Group
        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        self.load_image_btn = QPushButton("Load Image File")
        self.capture_image_btn = QPushButton("Capture Camera")
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        panel_layout.addWidget(input_group)

        # Output Group
        output_group = QGroupBox("Next")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(10)
        self.next_stage_btn = QPushButton("Proceed to Editor")
        output_layout.addWidget(self.next_stage_btn)
        panel_layout.addWidget(output_group)

        # Processing Group
        panel_layout.addWidget(self.processing_steps_group)

        # View Options Group
        view_options_group = QGroupBox("View Options")
        view_options_layout = QVBoxLayout(view_options_group)
        view_options_layout.setSpacing(10)
        self.show_skeleton_checkbox = QCheckBox("Show Skeleton")
        self.show_parts_checkbox = QCheckBox("Show Body Parts")
        view_options_layout.addWidget(self.show_skeleton_checkbox)
        view_options_layout.addWidget(self.show_parts_checkbox)
        panel_layout.addWidget(view_options_group)

        panel_layout.addStretch()

        # Right View Area (ImageProcessingView is owned by MainWindow but displayed here)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.image_zoom_combo = QComboBox()
        self.image_zoom_combo.setEditable(True)
        self.image_zoom_combo.setFixedSize(80, 28)
        self.image_zoom_combo.setStyleSheet(
            """
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
        """
        )
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.image_zoom_combo.addItems(zoom_levels)
        self.image_zoom_combo.setCurrentText("100%")
        self.image_zoom_combo.setToolTip("Zoom level")

        self.image_fit_btn = QPushButton("Fit")
        self.image_fit_btn.setFixedSize(45, 28)
        self.image_fit_btn.setStyleSheet(
            """
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
        )
        self.image_fit_btn.setToolTip("Zoom to fit all items")

        zoom_layout.addWidget(self.image_zoom_combo)
        zoom_layout.addWidget(self.image_fit_btn)

        # ImageProcessingView is managed by MainWindow, passed in __init__
        right_layout.addWidget(self.image_proc_view, 1)

        zoom_toolbar.setParent(right_panel)
        zoom_toolbar.setStyleSheet(
            """
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """
        )
        zoom_toolbar.show()

        def position_image_zoom_toolbar():
            if not right_panel.isVisible() or not zoom_toolbar.isVisible():
                return
            toolbar_width = zoom_toolbar.sizeHint().width()
            toolbar_height = zoom_toolbar.sizeHint().height()
            x = right_panel.width() - toolbar_width - 10  # Adjusted padding
            y = right_panel.height() - toolbar_height - 10  # Adjusted padding
            zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

        original_show_event = right_panel.showEvent

        def new_show_event(event):
            original_show_event(event)
            position_image_zoom_toolbar()

        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent

        def new_resize_event(event):
            original_resize_event(event)
            position_image_zoom_toolbar()

        right_panel.resizeEvent = new_resize_event

        # Ensure toolbar is repositioned initially if already visible
        if right_panel.isVisible():
            QApplication.instance().processEvents()  # Allow layout to settle
            position_image_zoom_toolbar()

        layout.addWidget(control_panel)
        layout.addWidget(right_panel, 1)
        self.setLayout(layout)

        # Connect signals
        self.load_image_btn.clicked.connect(self.load_input_image)
        self.capture_image_btn.clicked.connect(self.capture_image)
        # Connect signals from ProcessingStepsGroup
        self.processing_steps_group.processImageClicked.connect(self.process_image)
        self.processing_steps_group.editSkeletonClicked.connect(self.edit_skeleton)
        self.processing_steps_group.saveSkeletonClicked.connect(self.save_skeleton)
        self.processing_steps_group.generatePartsClicked.connect(
            self.create_parts_from_skeleton
        )
        self.processing_steps_group.extendSkeletonClicked.connect(self.extend_skeleton)
        self.processing_steps_group.lockJointsClicked.connect(self.show_lock_joints_dialog)

        self.next_stage_btn.clicked.connect(self.next_stage)

        self.image_zoom_combo.currentTextChanged.connect(self._handle_image_zoom_change)
        self.image_fit_btn.clicked.connect(self._handle_image_zoom_change_fit)

        self.show_skeleton_checkbox.toggled.connect(
            self._toggle_skeleton_visibility_in_view
        )
        self.show_parts_checkbox.toggled.connect(self._toggle_parts_visibility_in_view)

    def _toggle_skeleton_visibility_in_view(self, checked: bool):
        if self.image_proc_view:
            self.image_proc_view.show_skeleton_visuals(checked)

    def _toggle_parts_visibility_in_view(self, checked: bool):
        if not self.image_proc_view:
            return

        if checked:
            if (
                self.main_window
                and self.main_window.project_data_manager
                and self.main_window.project_data_manager.parts
            ):
                parts_info = self.main_window.project_data_manager.parts
                effective_offset = (
                    self.main_window.project_data_manager.effective_bounding_box_offset
                )
                # skeleton_to_part_map can be an empty dict if not immediately relevant for ImageProcessingView display
                self.image_proc_view.load_character_parts(
                    parts_info, {}, effective_offset
                )
                self.image_proc_view.show_part_visuals(True)
            else:
                logging.warning(
                    "ImageProcessingTab: Cannot show parts, ProjectDataManager has no parts loaded."
                )
                self.show_parts_checkbox.setChecked(
                    False
                )  # Uncheck if data is not available
                QMessageBox.information(
                    self,
                    "View Parts",
                    "No part data has been loaded into the project yet. Please process an image first.",
                )
        else:
            self.image_proc_view.show_part_visuals(False)
            # Optionally, clear them if they are re-added every time show is true.
            # Since load_character_parts now clears, this might not be strictly necessary here,
            # but explicit show/hide is cleaner if parts persist.
            # For now, just hiding is fine as load_character_parts handles clearing.

    # --- Image Processing Actions ---
    def load_input_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Input Image",
            self.character_dir or "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if not filepath:
            return
        if self.image_proc_view.load_image(filepath):
            self.input_image_path = filepath
            # Try to infer character_dir if not set, or if new image is in a different place
            potential_char_dir = os.path.dirname(filepath)
            # A simple heuristic: if a 'character_data' or 'output' subdir exists, or parts_info.json, assume it's a root
            if (
                os.path.exists(os.path.join(potential_char_dir, "character_data"))
                or os.path.exists(os.path.join(potential_char_dir, "output"))
                or os.path.exists(os.path.join(potential_char_dir, "parts_info.json"))
            ):
                self.character_dir = potential_char_dir
            elif os.path.basename(potential_char_dir) in [
                "source_images",
                "input_images",
                "images",
            ]:
                self.character_dir = os.path.dirname(
                    potential_char_dir
                )  # Go one level up
            else:  # Default to image's directory if no better guess
                self.character_dir = potential_char_dir

            self.main_window.statusBar().showMessage(
                f"Loaded input image: {os.path.basename(filepath)}"
            )
            logging.info(
                f"Input image loaded: {filepath}. Character dir set to: {self.character_dir}"
            )
            # Automatically try to process if an image is loaded
            # self.process_image() # Or user clicks process button
            if self.input_image_path and self.character_dir:
                logging.info(
                    "Automatically proceeding with image processing and part generation."
                )
                self.process_image()  # This will internally call load_skeleton
                # Check if skeleton was loaded successfully before creating parts
                if self.skeleton_data:  # Check if skeleton_data was set by process_image (via load_skeleton)
                    self.create_parts_from_skeleton()
                else:
                    logging.warning(
                        "Skeleton data not available after process_image, skipping part generation."
                    )
                    QMessageBox.warning(
                        self,
                        "Processing Step Skipped",
                        "Skeleton not found after image processing. Body part generation was skipped.",
                    )
            else:
                logging.warning(
                    "Cannot auto-process: input_image_path or character_dir not set."
                )
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {filepath}")

    def _load_image_from_path(self, image_path: str):
        """Load an image directly from a given path (used by landing tab)."""
        if not os.path.exists(image_path):
            logging.error(f"Image path does not exist: {image_path}")
            return False

        if self.image_proc_view.load_image(image_path):
            self.input_image_path = image_path
            # Try to infer character_dir if not set
            potential_char_dir = os.path.dirname(image_path)
            # A simple heuristic: if a 'character_data' or 'output' subdir exists, or parts_info.json, assume it's a root
            if (
                os.path.exists(os.path.join(potential_char_dir, "character_data"))
                or os.path.exists(os.path.join(potential_char_dir, "output"))
                or os.path.exists(os.path.join(potential_char_dir, "parts_info.json"))
            ):
                self.character_dir = potential_char_dir
            elif os.path.basename(potential_char_dir) in [
                "source_images",
                "input_images",
                "images",
            ]:
                self.character_dir = os.path.dirname(
                    potential_char_dir
                )  # Go one level up
            else:  # Default to image's directory if no better guess
                self.character_dir = potential_char_dir

            self.main_window.statusBar().showMessage(
                f"Loaded input image: {os.path.basename(image_path)}"
            )
            logging.info(
                f"Input image loaded: {image_path}. Character dir set to: {self.character_dir}"
            )

            # Show the processing steps group when an image is loaded
            self.processing_steps_group.setVisible(True)
            self.update_button_states()  # Ensure buttons are in correct state after loading image

            # Automatically try to process if an image is loaded
            if self.input_image_path and self.character_dir:
                self.process_image()
                if self.skeleton_data:
                    self.create_parts_from_skeleton()
                else:
                    QMessageBox.warning(
                        self,
                        "Processing Step Skipped",
                        "Skeleton not found after image processing. Body part generation was skipped.",
                    )

            # Automatic processing removed as per user request.
            # User will now need to click buttons in "Processing Steps" to proceed.
            logging.info(
                "Image loaded. Automatic processing steps are disabled. User must initiate processing manually."
            )
            return True
        else:
            QMessageBox.warning(
                self, "Load Error", f"Could not load image: {image_path}"
            )
            return False

    def capture_image(self):
        try:
            dialog = CameraDialog(self)
            self.active_camera_dialogs.append(dialog)
            dialog.finished.connect(
                lambda: (
                    self.active_camera_dialogs.remove(dialog)
                    if dialog in self.active_camera_dialogs
                    else None
                )
            )

            if (
                dialog.exec() == QDialog.DialogCode.Accepted
                and dialog.captured_image is not None
            ):
                temp_dir = tempfile.gettempdir()
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                temp_path = os.path.join(temp_dir, f"automata_capture_{timestamp}.png")
                try:
                    cv2.imwrite(temp_path, dialog.captured_image)
                    logging.info(f"Captured image saved to {temp_path}")
                    if self.image_proc_view.load_image(temp_path):
                        self.input_image_path = temp_path
                        self.character_dir = temp_dir  # Use temp dir for captured image output by default
                        self.main_window.statusBar().showMessage(
                            f"Loaded captured image: {os.path.basename(temp_path)}"
                        )
                        # self.process_image() # Or user clicks process button
                    else:
                        QMessageBox.warning(
                            self,
                            "Load Error",
                            "Failed to load captured image into view.",
                        )
                except Exception as e:
                    logging.error(f"Failed to save captured image: {e}")
                    QMessageBox.critical(
                        self, "Save Error", f"Could not save captured image: {e}"
                    )
        except Exception as e:
            logging.error(f"Error opening camera dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Camera Error", f"Could not open camera: {e}")

    def process_image(self):
        """
        Processes the loaded input image using image_to_annotations.
        This will generate char_cfg.yaml, texture.png, mask.png etc. in a temp dir.
        Then, it loads the skeleton data from the generated char_cfg.yaml.
        """
        if not self.input_image_path:
            QMessageBox.warning(self, "Warning", "No input image loaded.")
            self.update_button_states()
            return

        self.main_window.statusBar().showMessage("Processing image...")
        QApplication.processEvents()  # Ensure UI updates

        progress_dialog = QProgressDialog(
            "Processing image, please wait...", None, 0, 0, self
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setCancelButton(None)  # No cancel button for now
        progress_dialog.show()
        QApplication.processEvents()

        try:
            # Call the refactored image_to_annotations
            annotation_results = image_to_annotations(self.input_image_path)

            if annotation_results and annotation_results.get("char_cfg_path"):
                self.current_annotation_results = annotation_results
                self.current_temp_char_dir = annotation_results["output_dir"]
                char_cfg_file_path = annotation_results["char_cfg_path"]

                logging.info(
                    f"Image processing successful. Annotation results: {annotation_results}"
                )
                self.main_window.statusBar().showMessage(
                    f"Image processed. Temp files at {self.current_temp_char_dir}", 5000
                )

                # Load skeleton data from the generated char_cfg.yaml
                if self.load_skeleton_data_from_config(char_cfg_file_path):
                    # Skeleton data is loaded into self.skeleton_data and skeleton_updated emitted
                    logging.info(f"Skeleton loaded from {char_cfg_file_path}")
                    # Update view with the new texture from temp dir
                    if self.image_proc_view.load_image(
                        annotation_results["texture_path"]
                    ):  # Load the cropped texture
                        # And the skeleton for visualization
                        self.image_proc_view.load_skeleton(self.skeleton_data)
                        self.show_skeleton_checkbox.setChecked(True)
                else:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to load skeleton from {char_cfg_file_path}",
                    )
            else:
                self.current_annotation_results = None
                self.current_temp_char_dir = None
                QMessageBox.critical(
                    self, "Error", "Image processing (image_to_annotations) failed."
                )
                self.main_window.statusBar().showMessage(
                    "Image processing failed.", 5000
                )

        except Exception as e:
            self.current_annotation_results = None
            self.current_temp_char_dir = None
            logging.error(f"Error during image processing: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Processing Error", f"An unexpected error occurred: {e}"
            )
            self.main_window.statusBar().showMessage(f"Processing error: {e}", 5000)
        finally:
            progress_dialog.close()
            self.update_button_states()

    def load_skeleton_data_from_config(self, char_cfg_filepath: str) -> bool:
        if not char_cfg_filepath or not os.path.exists(char_cfg_filepath):
            if char_cfg_filepath:  # Only show error if a path was given but invalid
                logging.warning(f"Skeleton file not found: {char_cfg_filepath}")
                QMessageBox.warning(
                    self,
                    "Load Error",
                    f"Skeleton file not found: {os.path.basename(char_cfg_filepath)}",
                )
            return False

        try:
            with open(char_cfg_filepath, "r") as f:
                loaded_skeleton_data = yaml.safe_load(f)
            if (
                not loaded_skeleton_data or "skeleton" not in loaded_skeleton_data
            ):  # Basic validation
                raise ValueError("Invalid or empty skeleton file format.")

            if self.image_proc_view.load_skeleton(loaded_skeleton_data):
                self.skeleton_data = loaded_skeleton_data
                # Update character_dir if loading skeleton from a different location and it seems valid
                potential_char_dir = os.path.dirname(char_cfg_filepath)
                if os.path.exists(
                    os.path.join(potential_char_dir, "image.png")
                ):  # Heuristic
                    self.character_dir = potential_char_dir

                self.main_window.statusBar().showMessage(
                    f"Loaded skeleton: {os.path.basename(char_cfg_filepath)}"
                )
                logging.info(
                    f"Skeleton loaded from {char_cfg_filepath}. Character_dir is now {self.character_dir}"
                )
                self.skeleton_updated.emit(self.skeleton_data)  # Emit signal
                self.update_button_states()  # Update states, which will include the new group
                return True
            else:
                raise RuntimeError("ImageProcessingView failed to load skeleton data.")

        except Exception as e:
            logging.error(
                f"Failed to load skeleton from {char_cfg_filepath}: {e}", exc_info=True
            )
            QMessageBox.critical(
                self, "Load Skeleton Error", f"Failed to load skeleton: {e}"
            )
            return False

    def edit_skeleton(self):
        if not self.image_proc_view.joints:  # Check if joints are loaded in the view
            QMessageBox.information(
                self,
                "Edit Skeleton",
                "No skeleton loaded to edit. Please process an image or load a skeleton first.",
            )
            return
        # The view itself should handle the editability of joints. This button might just serve as a toggle or focus.
        self.image_proc_view.set_edit_mode(True)  # Assuming view has such a method
        self.main_window.statusBar().showMessage(
            "Skeleton editing enabled. Drag joints to modify."
        )
        logging.info("Skeleton editing mode enabled.")

    def save_skeleton(self):
        if not self.image_proc_view.joints:
            QMessageBox.warning(self, "Save Error", "No skeleton data loaded to save.")
            return

        default_path = (
            os.path.join(self.character_dir, "char_cfg.yaml")
            if self.character_dir
            else "char_cfg.yaml"
        )
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Skeleton As", default_path, "YAML Files (*.yaml *.yml)"
        )

        if not save_path:
            return

        try:
            current_skeleton_data = self.image_proc_view.get_skeleton_data()
            if not current_skeleton_data:
                raise ValueError("Could not retrieve skeleton data from view.")

            with open(save_path, "w") as f:
                yaml.dump(
                    current_skeleton_data, f, default_flow_style=None, sort_keys=False
                )

            self.skeleton_data = current_skeleton_data  # Update internal state
            self.main_window.statusBar().showMessage(
                f"Skeleton saved to {os.path.basename(save_path)}"
            )
            logging.info(f"Skeleton saved to {save_path}")
            self.skeleton_updated.emit(self.skeleton_data)  # Emit signal

        except Exception as e:
            logging.error(f"Failed to save skeleton: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Save Skeleton Error", f"Could not save skeleton: {e}"
            )

    def create_parts_from_skeleton(self):
        """Initiates part creation using BodyPartsExtractor based on current skeleton and image."""
        if (
            not self.current_annotation_results
            or not self.current_annotation_results.get("texture_path")
            or not self.current_annotation_results.get("char_cfg_path")
            or not self.current_temp_char_dir
        ):
            QMessageBox.warning(
                self,
                "Missing Data",
                "Cannot create parts. Texture, char_cfg, or temp directory not available. Please process image first.",
            )
            return

        # texture_path_str = self.current_annotation_results['texture_path'] # Used by BodyPartsExtractor internally via char_dir
        # char_cfg_path_str = self.current_annotation_results['char_cfg_path'] # Used by BodyPartsExtractor internally via char_dir
        # mask_path_str = self.current_annotation_results.get('mask_path') # Used by BodyPartsExtractor internally via char_dir

        logging.info(
            f"Creating parts using custom BodyPartsExtractor. Input char_dir: {self.current_temp_char_dir}"
        )
        self.main_window.statusBar().showMessage("Generating character parts...", 5000)

        progress_dialog = QProgressDialog(
            "Generating body parts...", "Cancel", 0, 0, self
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()
        QApplication.processEvents()  # Ensure dialog shows

        try:
            # Define the intended output directory for this custom BodyPartsExtractor
            # It will create this directory if it doesn't exist.
            # Ensure bpe_output_dir is INSIDE the current_temp_char_dir for proper session isolation.
            bpe_output_dir = Path(self.current_temp_char_dir) / "bpe_output"
            bpe_output_dir.mkdir(parents=True, exist_ok=True)  # Ensure it exists

            self.body_parts_extractor = BodyPartsExtractor(
                char_dir=str(
                    self.current_temp_char_dir
                ),  # This is the input dir containing char_cfg, texture, mask
                output_dir=str(
                    bpe_output_dir
                ),  # This is where parts_info.json and part SVGs should go
            )

            # Call process() method of the custom extractor
            self.body_parts_extractor.process()  # This method saves parts_info.json inside its self.output_dir

            # The body_parts_extractor.output_dir should now be bpe_output_dir
            actual_bpe_output_dir_from_extractor = Path(
                self.body_parts_extractor.output_dir
            )

            # Verify the extractor used the intended output directory
            if actual_bpe_output_dir_from_extractor != bpe_output_dir:
                logging.warning(
                    f"BodyPartsExtractor output dir {actual_bpe_output_dir_from_extractor} differs from intended {bpe_output_dir}. Using intended dir for consistency."
                )
                # Force using the intended directory for subsequent operations
                # This assumes parts_info.json was indeed written to actual_bpe_output_dir_from_extractor,
                # and we might need to reconcile if it truly went elsewhere.
                # However, BPE's __init__ sets self.output_dir to the passed output_dir, so they should match unless process() changes it.
                # For now, trust that BPE will write to the directory it was told to, or that its self.output_dir is correct.
                # The critical path is finding parts_info.json.

            expected_parts_info_path = (
                actual_bpe_output_dir_from_extractor / "parts_info.json"
            )

            if not expected_parts_info_path.exists():
                logging.error(
                    f"CRITICAL: parts_info.json was NOT found at {expected_parts_info_path} immediately after custom BodyPartsExtractor finished processing."
                )
                QMessageBox.critical(
                    self,
                    "Parts Generation Error",
                    f"parts_info.json was not created by BodyPartsExtractor at the expected location:\\n{expected_parts_info_path}\\n\\nPlease check the application logs for errors from BodyPartsExtractor.",
                )
                progress_dialog.close()
                return
            else:
                logging.info(
                    f"SUCCESS: parts_info.json found at {expected_parts_info_path} after custom BodyPartsExtractor processing."
                )

            self.current_parts_info_path = str(expected_parts_info_path)

            progress_dialog.close()
            msg_parts_generated = "Character parts generated successfully"
            if self.main_window.debug_mode:
                msg_parts_generated += f"in: {actual_bpe_output_dir_from_extractor}"
            QMessageBox.information(self, "Parts Generated", msg_parts_generated)

            if self.current_annotation_results:
                # Pass the actual_bpe_output_dir_from_extractor where parts_info.json resides
                self.parts_generated.emit(
                    self.current_annotation_results,
                    str(actual_bpe_output_dir_from_extractor),
                )
            else:
                logging.error(
                    "Cannot emit parts_generated: self.current_annotation_results is None."
                )

            self.update_button_states()

        except Exception as e:
            progress_dialog.close()
            logging.error(
                f"Error during part creation with custom BodyPartsExtractor: {e}",
                exc_info=True,
            )
            QMessageBox.critical(self, "Part Creation Error", f"An error occurred: {e}")
        finally:
            if progress_dialog.isVisible():
                progress_dialog.close()

    def next_stage(self):
        # Before switching, ensure parts have been processed and loaded by ProjectDataManager
        # The source of truth for parts being ready for the editor is the ProjectDataManager
        if (
            not self.main_window
            or not self.main_window.project_data_manager
            or not self.main_window.project_data_manager.parts
        ):
            QMessageBox.information(
                self,
                "Next Stage",
                "Please process image and generate parts, then ensure they are loaded into the project first.",
            )
            return

        # If skeleton data is also ready, it's good, but parts are essential for the editor tab's primary content.
        # Ensure parts_generated signal was emitted with the correct data (including parts_info_path)
        # The actual data loading into ProjectDataManager will be handled by MainWindow
        # when it receives the parts_generated signal.

        # We just need to request the tab switch.
        # The parts_generated signal (emitted from create_parts_from_skeleton)
        # should have already provided MainWindow with the necessary paths.
        self.request_editor_tab_switch.emit()
        logging.info("Requested switch to Editor Tab.")

    def _handle_image_zoom_change(self, zoom_text: str):
        try:
            if zoom_text.lower() == "fit":
                self.image_proc_view.zoom_to_fit()
                return

            if zoom_text.endswith("%"):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:  # Assume it's a direct scale factor if not percentage
                zoom_value = float(zoom_text)

            # Clamp zoom value to reasonable limits
            zoom_value = max(0.1, min(zoom_value, 10.0))

            self.image_proc_view.set_zoom_level(zoom_value)

            # Update combo box to show exact percentage after potential clamping
            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.image_zoom_combo.blockSignals(False)

        except ValueError:
            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText("100%")  # Reset to default
            self.image_zoom_combo.blockSignals(False)
            self.image_proc_view.set_zoom_level(1.0)
        except Exception as e:
            logging.error(f"Error in _handle_image_zoom_change: {e}")

    def _handle_image_zoom_change_fit(self):
        self.image_proc_view.zoom_to_fit()
        current_scale = self.image_proc_view.transform().m11()
        zoom_percent = int(current_scale * 100)
        self.image_zoom_combo.blockSignals(True)
        self.image_zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.image_zoom_combo.blockSignals(False)

    # --- Helper/Internal Methods ---
    def update_button_states(self):
        """Updates the enabled/disabled state of buttons based on current tab state."""
        has_image = bool(self.input_image_path)
        has_skeleton = bool(self.skeleton_data)

        # Update enabled state of buttons within ProcessingStepsGroup
        self.processing_steps_group.set_buttons_enabled_state(
            process_enabled=has_image,
            edit_enabled=has_skeleton,
            save_enabled=has_skeleton,
            generate_enabled=(has_skeleton and has_image),
            skeleton_tools_enabled=has_skeleton,  # Enable skeleton tools when skeleton is loaded
        )

        # next_stage_btn enabled if parts_info.json has been generated (or parts loaded in main_window)
        parts_are_actually_loaded = (
            self.main_window.project_data_manager.parts is not None
            and len(self.main_window.project_data_manager.parts) > 0
        )
        self.next_stage_btn.setEnabled(parts_are_actually_loaded)

    def on_parts_loaded_in_editor(self, loaded: bool):
        """
        Slot to be called when parts are loaded/cleared in the editor.
        Updates the state of UI elements in this tab.
        """
        logging.info(f"ImageProcessingTab notified: parts loaded in editor = {loaded}")
        # This method is more about reacting to external changes (EditorTab loading parts)
        # rather than this tab initiating the load *into* EditorTab.
        # If `loaded` is True, it means a project is active.
        # If `loaded` is False, project might have been cleared.

        # If parts are loaded elsewhere, this tab might want to reflect that state,
        # e.g., by enabling/disabling certain buttons.
        # However, the primary flow is:
        # 1. This tab generates data (image_to_annotations -> char_cfg, BPE -> parts_info)
        # 2. This tab emits `parts_generated` with paths.
        # 3. MainWindow receives this, tells ProjectDataManager to load from these paths.
        # 4. ProjectDataManager emits `project_data_loaded`.
        # 5. MainWindow tells EditorTab to populate from ProjectDataManager.
        # So, this slot might be less critical if the above flow is robust.

        self.update_button_states()  # General state update

    def on_skeleton_updated_externally(self, skeleton_data: Optional[dict]):
        """
        Slot for when skeleton data is updated from an external source
        (e.g., loaded directly into SkeletonManager by MainWindow).
        Updates the view in this tab if a texture is loaded.
        """
        logging.info(f"ImageProcessingTab: Received external skeleton update.")
        self.skeleton_data = skeleton_data
        # MODIFIED: Check image_item and its pixmap directly
        texture_loaded = False
        if (
            self.image_proc_view
            and self.image_proc_view.image_item
            and not self.image_proc_view.image_item.pixmap().isNull()
        ):
            texture_loaded = True

        if texture_loaded and self.skeleton_data:
            self.image_proc_view.load_skeleton(self.skeleton_data)
            self.show_skeleton_checkbox.setChecked(True)
        elif not self.skeleton_data:
            # self.image_proc_view.clear_skeleton_visuals() # load_skeleton with None/empty should handle this
            if self.image_proc_view:
                self.image_proc_view.load_skeleton(None)  # Explicitly clear with None
            self.show_skeleton_checkbox.setChecked(False)
        self.update_button_states()

    def _toggle_detailed_processing_visibility(self, visible: bool):
        """Slot to control the visibility of the detailed processing steps group."""
        self.processing_steps_group.setVisible(visible)
        logging.info(f"Detailed processing steps visibility set to: {visible}")
    
    def extend_skeleton(self):
        """Extends the skeleton lengths by 10%."""
        if not self.main_window or not self.main_window.skeleton_manager:
            QMessageBox.warning(
                self,
                "Extend Skeleton",
                "No skeleton manager available."
            )
            return
            
        if not self.main_window.skeleton_manager.standardized_model:
            QMessageBox.warning(
                self,
                "Extend Skeleton",
                "No skeleton loaded. Please process an image or load a skeleton first."
            )
            return
            
        # Confirm action with user
        reply = QMessageBox.question(
            self,
            "Extend Skeleton",
            "This will increase all skeleton bone lengths by 10%. This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.main_window.skeleton_manager.extend_skeleton_lengths(1.1):
                # Update the view with the modified skeleton
                if self.skeleton_data and self.image_proc_view:
                    # Get the updated skeleton data
                    updated_skeleton = self.main_window.skeleton_manager.standardized_model.model_dump()
                    self.skeleton_data = updated_skeleton
                    self.image_proc_view.load_skeleton(updated_skeleton)
                    
                QMessageBox.information(
                    self,
                    "Extend Skeleton",
                    "Skeleton lengths extended by 10% successfully."
                )
                self.main_window.statusBar().showMessage("Skeleton extended by 10%", 3000)
            else:
                QMessageBox.critical(
                    self,
                    "Extend Skeleton",
                    "Failed to extend skeleton lengths."
                )
    
    def show_lock_joints_dialog(self):
        """Shows a dialog for locking/unlocking specific joints."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QLabel
        from PyQt6.QtCore import Qt
        
        if not self.main_window or not self.main_window.skeleton_manager:
            QMessageBox.warning(
                self,
                "Lock/Unlock Joints",
                "No skeleton manager available."
            )
            return
            
        if not self.main_window.skeleton_manager.standardized_model:
            QMessageBox.warning(
                self,
                "Lock/Unlock Joints",
                "No skeleton loaded. Please process an image or load a skeleton first."
            )
            return
            
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Lock/Unlock Joints")
        dialog.setModal(True)
        dialog.resize(300, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Add instructions
        label = QLabel("Check joints to lock them during IK solving:")
        layout.addWidget(label)
        
        # Create list widget with checkable items
        list_widget = QListWidget()
        
        # Get current locked joints
        locked_joints = self.main_window.skeleton_manager.get_locked_joints()
        
        # Add all joints to the list
        skeleton_model = self.main_window.skeleton_manager.standardized_model
        for joint_id, joint in skeleton_model.joints.items():
            item = QListWidgetItem(f"{joint.name} ({joint_id})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if joint.is_locked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, joint_id)  # Store joint ID
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        # Add buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)
        
        def accept_changes():
            # Update joint lock states
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                joint_id = item.data(Qt.ItemDataRole.UserRole)
                is_locked = item.checkState() == Qt.CheckState.Checked
                self.main_window.skeleton_manager.lock_joint(joint_id, is_locked)
            
            # Update the view if needed
            if self.skeleton_data and self.image_proc_view:
                updated_skeleton = self.main_window.skeleton_manager.standardized_model.model_dump()
                self.skeleton_data = updated_skeleton
                self.image_proc_view.load_skeleton(updated_skeleton)
                
            dialog.accept()
        
        button_box.accepted.connect(accept_changes)
        button_box.rejected.connect(dialog.reject)
        
        dialog.exec()
