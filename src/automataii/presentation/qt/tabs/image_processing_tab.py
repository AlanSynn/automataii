import os
import tempfile
import time
from pathlib import Path

import cv2
import yaml
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import AnnotationResults, image_to_annotations
from automataii.presentation.qt.dialogs.camera_dialog import CameraDialog
from automataii.presentation.qt.image_view import ImageProcessingView
from automataii.presentation.qt.widgets.processing_steps_group import ProcessingStepsGroup

from automataii.core.telemetry import telemetry_span


class ImageProcessingTab(QWidget):
    parts_generated = pyqtSignal(dict, str)
    skeleton_updated = pyqtSignal(dict)
    request_editor_tab_switch = pyqtSignal()

    def __init__(self, main_window, parent=None, editing_mode: bool = False):
        super().__init__(parent)
        self.main_window = main_window
        self.editing_mode = editing_mode

        self.input_image_path: str | None = None
        self.character_dir: str | None = None
        self.current_temp_char_dir: str | None = None
        self.current_annotation_results: AnnotationResults | None = None
        self.skeleton_data: dict | None = None
        self.active_camera_dialogs: list = []

        self.image_proc_scene = QGraphicsScene(self)
        self.image_proc_view = ImageProcessingView(self.image_proc_scene, self)

        self.processing_steps_group = ProcessingStepsGroup()
        self.processing_steps_group.setVisible(False)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        control_panel = QWidget()
        control_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(5, 10, 5, 10)
        panel_layout.setSpacing(10)

        input_group = QGroupBox("Input Drawing")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        self.load_image_btn = QPushButton("Load Image File")
        self.capture_image_btn = QPushButton("Capture Camera")
        input_layout.addWidget(self.load_image_btn)
        input_layout.addWidget(self.capture_image_btn)
        panel_layout.addWidget(input_group)

        panel_layout.addWidget(self.processing_steps_group)

        # Add Manual Segmentation Editing group when in editing mode
        if self.editing_mode:
            editing_group = QGroupBox("Manual Editing")
            editing_layout = QVBoxLayout(editing_group)
            editing_layout.setSpacing(10)

            # Manual Segmentation Editing button (same style as other buttons)
            self.manual_segmentation_btn = QPushButton("Manual Segmentation Editing")
            self.manual_segmentation_btn.setToolTip(
                "Open interactive editor to manually define body part boundaries by clicking"
            )
            self.manual_segmentation_btn.clicked.connect(self.open_manual_segmentation_editor)
            self.manual_segmentation_btn.setEnabled(False)  # Enabled when image is loaded
            editing_layout.addWidget(self.manual_segmentation_btn)

            panel_layout.addWidget(editing_group)

        view_controls_group = QGroupBox("View Controls")
        view_controls_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        view_controls_layout = QVBoxLayout(view_controls_group)

        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)

        zoom_button_style = """
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

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_out_btn)

        self.zoom_fit_btn = QPushButton("⌖")
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)

        self.zoom_reset_btn = QPushButton("1:1")
        self.zoom_reset_btn.setToolTip("Reset Zoom (100%)")
        self.zoom_reset_btn.setStyleSheet(zoom_button_style)
        self.zoom_reset_btn.setMinimumWidth(35)
        zoom_controls_layout.addWidget(self.zoom_reset_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        panel_layout.addWidget(view_controls_group)

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

        self.load_image_btn.clicked.connect(self.load_input_image)
        self.capture_image_btn.clicked.connect(self.capture_image)
        self.processing_steps_group.processImageClicked.connect(self.process_image)
        self.processing_steps_group.editSkeletonClicked.connect(self.edit_skeleton)
        self.processing_steps_group.saveSkeletonClicked.connect(self.save_skeleton)
        self.processing_steps_group.generatePartsClicked.connect(
            self.create_parts_from_skeleton
        )
        self.processing_steps_group.extendSkeletonClicked.connect(self.extend_skeleton)
        self.processing_steps_group.lockJointsClicked.connect(self.show_lock_joints_dialog)

        self.image_zoom_combo.currentTextChanged.connect(self._handle_image_zoom_change)
        self.image_fit_btn.clicked.connect(self._handle_image_zoom_change_fit)

        self.zoom_in_btn.clicked.connect(lambda: self.image_proc_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.image_proc_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.image_proc_view.zoom_to_fit)
        self.zoom_reset_btn.clicked.connect(self.image_proc_view.reset_view)

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

            # Enable manual segmentation editing button if in editing mode
            if self.editing_mode and hasattr(self, 'manual_segmentation_btn'):
                self.manual_segmentation_btn.setEnabled(True)

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
            # Automatically try to process if an image is loaded
            # self.process_image() # Or user clicks process button
            if self.input_image_path and self.character_dir:
                self.process_image()  # This will internally call load_skeleton
                # Check if skeleton was loaded successfully before creating parts
                if self.skeleton_data:  # Check if skeleton_data was set by process_image (via load_skeleton)
                    self.create_parts_from_skeleton()
                else:
                    QMessageBox.warning(
                        self,
                        "Processing Step Skipped",
                        "Skeleton not found after image processing. Body part generation was skipped.",
                    )
        else:
            QMessageBox.warning(self, "Load Error", f"Could not load image: {filepath}")

    def open_manual_segmentation_editor(self):
        """Open interactive manual segmentation editor"""
        if not self.input_image_path:
            QMessageBox.warning(
                self, "No Image", "Please load an image first before opening the manual editor."
            )
            return

        try:
            from automataii.presentation.qt.interactive_segmentation_editor import InteractiveSegmentationEditor

            # Create dialog
            editor_dialog = InteractiveSegmentationEditor(
                image_path=self.input_image_path,
                skeleton_data=self.skeleton_data,
                parent=self
            )

            # Show dialog and handle result
            if editor_dialog.exec() == QDialog.DialogCode.Accepted:
                # Get the edited segmentation results
                edited_results = editor_dialog.get_segmentation_results()

                if edited_results:
                    # Apply the manually edited segmentation results
                    self._apply_manual_segmentation_results(edited_results)
                    self.main_window.statusBar().showMessage("Manual segmentation applied successfully!")
                else:
                    self.main_window.statusBar().showMessage("No segmentation changes were made.")
            else:
                self.main_window.statusBar().showMessage("Manual segmentation editing cancelled.")

        except ImportError as e:
            QMessageBox.critical(
                self, "Import Error",
                f"Could not load interactive segmentation editor: {e}\n\n"
                "Make sure all required dependencies are installed."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Editor Error",
                f"Error opening manual segmentation editor: {e}"
            )

    def _apply_manual_segmentation_results(self, segmentation_results):
        """Apply manually edited segmentation results to the current workflow"""
        try:
            # Save the manual segmentation results
            if self.character_dir:
                output_dir = os.path.join(self.character_dir, "manual_segmentation")
                os.makedirs(output_dir, exist_ok=True)

                # Save individual part masks
                for part_name, mask_data in segmentation_results.items():
                    if mask_data is not None and len(mask_data) > 0:
                        mask_path = os.path.join(output_dir, f"{part_name}_mask.png")
                        cv2.imwrite(mask_path, mask_data)

                # Update the current workflow with manual results
                self.current_annotation_results = segmentation_results

                # Trigger parts generation with manual data
                self._generate_parts_from_manual_segmentation(segmentation_results)

                QMessageBox.information(
                    self, "Success",
                    f"Manual segmentation results saved to:\n{output_dir}"
                )
            else:
                QMessageBox.warning(
                    self, "No Directory",
                    "No character directory set. Results were not saved."
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Apply Error",
                f"Error applying manual segmentation results: {e}"
            )

    def _generate_parts_from_manual_segmentation(self, segmentation_results):
        """Generate body parts from manual segmentation results"""
        try:
            # Create body parts using manual segmentation masks
            # This integrates with the existing parts generation workflow

            if not self.character_dir or not self.input_image_path:
                return

            # Create character data structure
            char_data = {
                "width": 0,  # Will be set from image
                "height": 0,
                "parts": {},
                "skeleton": self.skeleton_data.get("skeleton", []) if self.skeleton_data else [],
                "joint_map": {}
            }

            # Load original image to get dimensions
            import cv2
            original_image = cv2.imread(self.input_image_path, cv2.IMREAD_UNCHANGED)
            if original_image is not None:
                char_data["height"], char_data["width"] = original_image.shape[:2]

            # Process each part from manual segmentation
            for part_name, mask_data in segmentation_results.items():
                if mask_data is not None and len(mask_data) > 0:
                    # Extract part information from mask
                    part_info = self._extract_part_info_from_mask(
                        part_name, mask_data, original_image
                    )
                    if part_info:
                        char_data["parts"][part_name] = part_info

            # Emit signal to main window
            if char_data["parts"]:
                self.parts_generated.emit(char_data, self.character_dir)
                self.main_window.statusBar().showMessage(
                    f"Generated {len(char_data['parts'])} body parts from manual segmentation"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error",
                f"Error generating parts from manual segmentation: {e}"
            )

    def _extract_part_info_from_mask(self, part_name: str, mask: any, original_image: any) -> dict:
        """Extract part information from a segmentation mask"""
        try:
            import cv2
            import numpy as np

            # Find bounding box of the mask
            if hasattr(mask, 'shape'):
                # mask is numpy array
                mask_array = mask
            else:
                # Convert to numpy array if needed
                mask_array = np.array(mask)

            # Find non-zero pixels
            coords = np.column_stack(np.where(mask_array > 0))
            if len(coords) == 0:
                return None

            # Calculate bounding box
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)

            roi_width = x_max - x_min + 1
            roi_height = y_max - y_min + 1

            # Extract part texture from original image
            if original_image is not None:
                part_texture = original_image[y_min:y_max+1, x_min:x_max+1]
                part_mask_roi = mask_array[y_min:y_max+1, x_min:x_max+1]

                # Create RGBA image with transparency
                if len(part_texture.shape) == 3:
                    part_rgba = cv2.cvtColor(part_texture, cv2.COLOR_BGR2BGRA)
                else:
                    part_rgba = cv2.cvtColor(part_texture, cv2.COLOR_GRAY2BGRA)

                # Apply mask as alpha channel
                part_rgba[:, :, 3] = part_mask_roi

                # Save part image
                if self.character_dir:
                    parts_dir = os.path.join(self.character_dir, "manual_parts")
                    os.makedirs(parts_dir, exist_ok=True)
                    part_image_path = os.path.join(parts_dir, f"{part_name}.png")
                    cv2.imwrite(part_image_path, part_rgba)

            # Create part info structure
            part_info = {
                "name": part_name,
                "roi": [float(x_min), float(y_min), float(roi_width), float(roi_height)],
                "image_path": f"manual_parts/{part_name}.png",
                "local_pivot_offset": [float(roi_width / 2), float(roi_height / 2)],
                "z_value": 0.0,
                "fixed": False,
                "fill_color": "rgba(128,128,128,0.5)"
            }

            return part_info

        except Exception as e:
            print(f"Error extracting part info for {part_name}: {e}")
            return None

    def _load_image_from_path(self, image_path: str):
        """Load an image directly from a given path (used by landing tab)."""
        if not os.path.exists(image_path):
            return False

        if self.image_proc_view.load_image(image_path):
            self.input_image_path = image_path
            potential_char_dir = os.path.dirname(image_path)
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
                )
            else:
                self.character_dir = potential_char_dir

            self.main_window.statusBar().showMessage(
                f"Loaded input image: {os.path.basename(image_path)}"
            )

            self.processing_steps_group.setVisible(True)
            self.update_button_states()
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
                    QMessageBox.critical(
                        self, "Save Error", f"Could not save captured image: {e}"
                    )
        except Exception as e:
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

        with telemetry_span(
            "ui.image_processing.process_image",
            editing_mode=self.editing_mode,
            input_source="file",
        ) as span:
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
                annotation_results = image_to_annotations(self.input_image_path)

                if annotation_results and annotation_results.get("char_cfg_path"):
                    self.current_annotation_results = annotation_results
                    self.current_temp_char_dir = annotation_results["output_dir"]
                    char_cfg_file_path = annotation_results["char_cfg_path"]

                    self.main_window.statusBar().showMessage(
                        f"Image processed. Temp files at {self.current_temp_char_dir}",
                        5000,
                    )

                    if self.load_skeleton_data_from_config(char_cfg_file_path):
                        if self.image_proc_view.load_image(
                            annotation_results["texture_path"]
                        ):
                            self.image_proc_view.load_skeleton(self.skeleton_data)
                            span.set(
                                status="success",
                                skeleton_loaded=bool(self.skeleton_data),
                                output_dir=self.current_temp_char_dir,
                            )
                        else:
                            span.set(status="failure", reason="texture_load_failed")
                    else:
                        span.set(status="failure", reason="skeleton_load_failed")
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Failed to load skeleton from {char_cfg_file_path}",
                        )
                else:
                    self.current_annotation_results = None
                    self.current_temp_char_dir = None
                    span.set(status="failure", reason="annotation_failure")
                    QMessageBox.critical(
                        self, "Error", "Image processing (image_to_annotations) failed."
                    )
                    self.main_window.statusBar().showMessage(
                        "Image processing failed.", 5000
                    )

            except Exception as e:
                span.set(status="error", error=str(e))
                self.current_annotation_results = None
                self.current_temp_char_dir = None
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
                QMessageBox.warning(
                    self,
                    "Load Error",
                    f"Skeleton file not found: {os.path.basename(char_cfg_filepath)}",
                )
            return False

        try:
            with open(char_cfg_filepath) as f:
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
                self.skeleton_updated.emit(self.skeleton_data)  # Emit signal
                self.update_button_states()  # Update states, which will include the new group
                return True
            else:
                raise RuntimeError("ImageProcessingView failed to load skeleton data.")

        except Exception as e:
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
            self.skeleton_updated.emit(self.skeleton_data)  # Emit signal

        except Exception as e:
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


        self.main_window.statusBar().showMessage("Generating character parts...", 5000)

        progress_dialog = QProgressDialog(
            "Generating body parts...", "Cancel", 0, 0, self
        )
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.show()
        QApplication.processEvents()  # Ensure dialog shows

        try:
            bpe_output_dir = Path(self.current_temp_char_dir) / "bpe_output"
            bpe_output_dir.mkdir(parents=True, exist_ok=True)

            # Copy original image as texture and image.png to preserve original quality
            import shutil
            if self.input_image_path:
                # Copy as texture.png (used by some parts of the system)
                processed_texture_path = Path(self.current_temp_char_dir) / "texture.png"
                shutil.copy2(self.input_image_path, processed_texture_path)

                # Copy as image.png (the main original image used by BodyPartsExtractor)
                original_image_path = Path(self.current_temp_char_dir) / "image.png"
                shutil.copy2(self.input_image_path, original_image_path)

            self.body_parts_extractor = BodyPartsExtractor(
                char_dir=str(
                    self.current_temp_char_dir
                ),  # This is the input dir containing char_cfg, texture, mask
                output_dir=str(
                    bpe_output_dir
                ),  # This is where parts_info.json and part SVGs should go
            )

            self.body_parts_extractor.process()

            actual_bpe_output_dir_from_extractor = Path(
                self.body_parts_extractor.output_dir
            )

            expected_parts_info_path = (
                actual_bpe_output_dir_from_extractor / "parts_info.json"
            )

            if not expected_parts_info_path.exists():
                QMessageBox.critical(
                    self,
                    "Parts Generation Error",
                    f"parts_info.json was not created by BodyPartsExtractor at the expected location:\\n{expected_parts_info_path}\\n\\nPlease check the application logs for errors from BodyPartsExtractor.",
                )
                progress_dialog.close()
                return
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
            self.update_button_states()

        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "Part Creation Error", f"An error occurred: {e}")
        finally:
            if progress_dialog.isVisible():
                progress_dialog.close()

    def _handle_image_zoom_change(self, zoom_text: str):
        """Handle zoom change from the combo box."""
        try:
            if zoom_text.lower() == "fit":
                self.image_proc_view.zoom_to_fit()
                return

            if zoom_text.endswith("%"):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text)

            zoom_value = max(0.1, min(zoom_value, 10.0))

            self.image_proc_view.set_zoom_level(zoom_value)

            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.image_zoom_combo.blockSignals(False)

        except ValueError:
            self.image_zoom_combo.blockSignals(True)
            self.image_zoom_combo.setCurrentText("100%")
            self.image_zoom_combo.blockSignals(False)
            self.image_proc_view.set_zoom_level(1.0)
        except Exception:
            pass

    def _handle_image_zoom_change_fit(self):
        self.image_proc_view.zoom_to_fit()
        current_scale = self.image_proc_view.transform().m11()
        zoom_percent = int(current_scale * 100)
        self.image_zoom_combo.blockSignals(True)
        self.image_zoom_combo.setCurrentText(f"{zoom_percent}%")
        self.image_zoom_combo.blockSignals(False)

    def update_button_states(self):
        """Updates the enabled/disabled state of buttons based on current tab state."""
        has_image = bool(self.input_image_path)
        has_skeleton = bool(self.skeleton_data)

        self.processing_steps_group.set_buttons_enabled_state(
            process_enabled=has_image,
            edit_enabled=has_skeleton,
            save_enabled=has_skeleton,
            generate_enabled=(has_skeleton and has_image),
            skeleton_tools_enabled=has_skeleton,
        )

    def on_parts_loaded_in_editor(self, _loaded: bool):
        """
        Slot to be called when parts are loaded/cleared in the editor.
        Updates the state of UI elements in this tab.
        """
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

    def on_skeleton_updated_externally(self, skeleton_data: dict | None):
        """
        Slot for when skeleton data is updated from an external source
        (e.g., loaded directly into SkeletonManager by MainWindow).
        Updates the view in this tab if a texture is loaded.
        """
        self.skeleton_data = skeleton_data
        texture_loaded = False
        if (
            self.image_proc_view
            and self.image_proc_view.image_item
            and not self.image_proc_view.image_item.pixmap().isNull()
        ):
            texture_loaded = True

        if texture_loaded and self.skeleton_data:
            self.image_proc_view.load_skeleton(self.skeleton_data)
        elif not self.skeleton_data:
            if self.image_proc_view:
                self.image_proc_view.load_skeleton(None)
        self.update_button_states()

    def clear_display_and_data(self) -> None:
        """Clear all display content and reset internal data.

        Called when project load fails or when a new project is started.
        Resets:
        - Image display (scene clear)
        - Skeleton data
        - Annotation results
        - Path references
        """
        logging.info("ImageProcessingTab: Clearing display and data")

        # Clear scene
        if self.image_proc_scene:
            self.image_proc_scene.clear()

        # Clear view's skeleton
        if self.image_proc_view:
            self.image_proc_view.load_skeleton(None)

        # Reset internal data
        self.input_image_path = None
        self.character_dir = None
        self.current_temp_char_dir = None
        self.current_annotation_results = None
        self.skeleton_data = None

        # Update UI state
        self.update_button_states()

    def _toggle_detailed_processing_visibility(self, visible: bool):
        """Slot to control the visibility of the detailed processing steps group."""
        self.processing_steps_group.setVisible(visible)

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
                if self.skeleton_data and self.image_proc_view:
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
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QListWidget,
            QListWidgetItem,
            QVBoxLayout,
        )

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

        dialog = QDialog(self)
        dialog.setWindowTitle("Lock/Unlock Joints")
        dialog.setModal(True)
        dialog.resize(300, 400)

        layout = QVBoxLayout(dialog)

        label = QLabel("Check joints to lock them during IK solving:")
        layout.addWidget(label)

        list_widget = QListWidget()


        skeleton_model = self.main_window.skeleton_manager.standardized_model
        for joint_id, joint in skeleton_model.joints.items():
            item = QListWidgetItem(f"{joint.name} ({joint_id})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if joint.is_locked else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, joint_id)
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(button_box)

        def accept_changes():
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                joint_id = item.data(Qt.ItemDataRole.UserRole)
                is_locked = item.checkState() == Qt.CheckState.Checked
                self.main_window.skeleton_manager.lock_joint(joint_id, is_locked)

            if self.skeleton_data and self.image_proc_view:
                updated_skeleton = self.main_window.skeleton_manager.standardized_model.model_dump()
                self.skeleton_data = updated_skeleton
                self.image_proc_view.load_skeleton(updated_skeleton)

            dialog.accept()

        button_box.accepted.connect(accept_changes)
        button_box.rejected.connect(dialog.reject)

        dialog.exec()
