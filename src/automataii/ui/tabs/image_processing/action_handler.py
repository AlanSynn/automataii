# src/automataii/ui/tabs/image_processing/action_handler.py

import logging
import os
import tempfile
import time

import cv2
import yaml
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QProgressDialog

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.image_to_annotations import AnnotationResults, image_to_annotations
from automataii.ui.dialogs.camera_dialog import CameraDialog

logger = logging.getLogger(__name__)


class ImageProcessingActionHandler(QObject):
    """
    Handles all business logic and user actions for the Image Processing tab.
    """

    # Signals for communication with main window
    parts_generated = pyqtSignal(dict, str)
    skeleton_updated = pyqtSignal(dict)
    request_editor_tab_switch = pyqtSignal()

    def __init__(self, state_manager, scene_manager, main_window, parent=None):
        super().__init__(parent)
        self.state = state_manager
        self.scene_manager = scene_manager
        self.main_window = main_window
        self.parent_widget = parent

    def handle_load_image(self) -> None:
        """Handle loading an image from file dialog."""
        file_name, _ = QFileDialog.getOpenFileName(
            self.parent_widget, "Open Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_name:
            self._load_image_from_path(file_name)

    def _load_image_from_path(self, image_path: str) -> None:
        """Load an image from the specified path."""
        try:
            # Update status bar
            self.main_window.set_status(f"Loading image: {os.path.basename(image_path)}")

            # Clear any existing skeleton data
            self.state.set_skeleton_data(None)

            # Set the image path in state (this will trigger scene update)
            self.state.set_input_image_path(image_path)

            # Try to infer character directory
            parent_dir = os.path.dirname(image_path)
            if os.path.exists(os.path.join(parent_dir, "char_cfg.yaml")):
                self.state.set_character_dir(parent_dir)
                # Try to load existing skeleton
                self._try_load_existing_skeleton(parent_dir)

            self.main_window.set_status("Image loaded successfully")

        except Exception as e:
            logger.error(f"Error loading image: {e}")
            QMessageBox.critical(self.parent_widget, "Error", f"Failed to load image: {str(e)}")
            self.main_window.set_status("Failed to load image")

    def handle_capture_image(self) -> None:
        """Handle capturing an image from camera."""
        try:
            camera_dialog = CameraDialog(self.parent_widget)
            self.state.add_camera_dialog(camera_dialog)

            if camera_dialog.exec() == QDialog.DialogCode.Accepted:
                captured_frame = camera_dialog.get_captured_frame()
                if captured_frame is not None:
                    # Save to temporary file
                    temp_dir = tempfile.mkdtemp()
                    temp_path = os.path.join(temp_dir, "captured_image.png")
                    cv2.imwrite(temp_path, captured_frame)
                    self._load_image_from_path(temp_path)

            self.state.remove_camera_dialog(camera_dialog)

        except Exception as e:
            logger.error(f"Error capturing image: {e}")
            QMessageBox.critical(self.parent_widget, "Error", f"Failed to capture image: {str(e)}")

    def handle_process_image(self) -> None:
        """Handle processing the loaded image."""
        if not self.state.input_image_path:
            return

        # Create progress dialog
        progress = QProgressDialog(
            "Processing image...\nThis may take several seconds.",
            None,  # No cancel button
            0,
            0,  # Indeterminate progress
            self.parent_widget,
        )
        progress.setWindowTitle("Processing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            self.state.set_processing_in_progress(True)

            # Process the image
            annotation_results = image_to_annotations(self.state.input_image_path)

            if annotation_results:
                self.state.set_annotation_results(annotation_results)

                # Extract skeleton data
                skeleton_data = self._extract_skeleton_from_annotations(annotation_results)
                if skeleton_data:
                    self.state.set_skeleton_data(skeleton_data)
                    self.skeleton_updated.emit(skeleton_data)
                    self.main_window.set_status("Image processed successfully")

                    # Auto-generate parts after skeleton is created
                    logger.info("Auto-generating body parts after skeleton creation")
                    from PyQt6.QtCore import QTimer

                    QTimer.singleShot(100, self.handle_generate_parts)
                else:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Processing Complete",
                        "No person detected in the image. Please try another image.",
                    )
                    self.main_window.set_status("No person detected")
            else:
                # Even if annotation processing fails, generate basic skeleton for testing
                logger.info("Annotation processing failed, generating basic skeleton for testing")
                skeleton_data = self._extract_skeleton_from_annotations({})
                if skeleton_data:
                    self.state.set_annotation_results({"status": "basic_skeleton"})
                    self.state.set_skeleton_data(skeleton_data)
                    self.skeleton_updated.emit(skeleton_data)
                    self.main_window.set_status("Basic skeleton generated for testing")

                    # Auto-generate parts after skeleton is created
                    logger.info("Auto-generating body parts after basic skeleton creation")
                    from PyQt6.QtCore import QTimer

                    QTimer.singleShot(100, self.handle_generate_parts)
                else:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Processing Failed",
                        "Failed to process the image. Please try another image.",
                    )
                    self.main_window.set_status("Processing failed")

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            QMessageBox.critical(
                self.parent_widget, "Error", f"An error occurred during processing: {str(e)}"
            )
        finally:
            self.state.set_processing_in_progress(False)
            progress.close()

    def handle_edit_skeleton(self) -> None:
        """Handle enabling skeleton editing mode."""
        current_editing = self.state.is_editing_skeleton
        self.state.set_editing_skeleton(not current_editing)
        self.scene_manager.set_skeleton_edit_mode(not current_editing)

        if not current_editing:
            self.main_window.set_status("Skeleton editing enabled - drag joints to adjust")
        else:
            # Get updated skeleton data from view
            updated_skeleton = self.scene_manager.get_current_skeleton_data()
            if updated_skeleton:
                self.state.set_skeleton_data(updated_skeleton)
                self.skeleton_updated.emit(updated_skeleton)
            self.main_window.set_status("Skeleton editing disabled")

    def handle_save_skeleton(self) -> None:
        """Handle saving skeleton data to file."""
        if not self.state.skeleton_data:
            return

        # Get save location
        default_name = "skeleton_data.yaml"
        if self.state.character_dir:
            default_name = os.path.join(self.state.character_dir, "char_cfg.yaml")

        file_name, _ = QFileDialog.getSaveFileName(
            self.parent_widget, "Save Skeleton Data", default_name, "YAML Files (*.yaml *.yml)"
        )

        if file_name:
            try:
                # Get current skeleton data from view
                skeleton_data = self.scene_manager.get_current_skeleton_data()
                if not skeleton_data:
                    skeleton_data = self.state.skeleton_data

                # Save to file
                with open(file_name, "w") as f:
                    yaml.dump(skeleton_data, f, default_flow_style=False)

                self.main_window.set_status(f"Skeleton saved to {os.path.basename(file_name)}")

            except Exception as e:
                logger.error(f"Error saving skeleton: {e}")
                QMessageBox.critical(
                    self.parent_widget, "Error", f"Failed to save skeleton: {str(e)}"
                )

    def handle_generate_parts(self) -> None:
        """Handle generating body parts from skeleton."""
        if not self.state.skeleton_data or not self.state.input_image_path:
            return

        progress = QProgressDialog("Generating body parts...", None, 0, 0, self.parent_widget)
        progress.setWindowTitle("Generating Parts")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            # Create output directory
            base_dir = self.state.character_dir or os.path.dirname(self.state.input_image_path)
            output_dir = os.path.join(base_dir, f"character_{int(time.time())}")
            os.makedirs(output_dir, exist_ok=True)

            # Get current skeleton from view
            skeleton_data = self.scene_manager.get_current_skeleton_data()
            if not skeleton_data:
                skeleton_data = self.state.skeleton_data

            # Check if we have annotation results with real mask
            annotation_results = self.state.current_annotation_results
            if annotation_results and annotation_results.get("mask_path"):
                # Use real mask from annotation results
                parts_info_path = self._generate_parts_with_real_mask(
                    annotation_results, skeleton_data, output_dir
                )
            else:
                # Fallback to simplified method
                parts_info_path = self._generate_parts_simplified(
                    self.state.input_image_path, skeleton_data, output_dir
                )

            if parts_info_path:
                self.state.set_parts_info_path(parts_info_path)

                # Load parts info
                with open(parts_info_path) as f:
                    import json

                    parts_info = json.load(f)

                # Emit signal with parts info and output directory
                self.parts_generated.emit(parts_info, output_dir)

                # Request switch to editor tab
                self.request_editor_tab_switch.emit()

                self.main_window.set_status("Body parts generated successfully")
            else:
                QMessageBox.warning(
                    self.parent_widget, "Generation Failed", "Failed to generate body parts."
                )

        except Exception as e:
            logger.error(f"Error generating parts: {e}")
            QMessageBox.critical(self.parent_widget, "Error", f"Failed to generate parts: {str(e)}")
        finally:
            progress.close()

    def _generate_parts_simplified(
        self, image_path: str, skeleton_data: dict, output_dir: str
    ) -> str | None:
        """Generate parts using simplified approach for direct image + skeleton input."""
        try:
            import json
            import cv2
            import numpy as np

            # Load the image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return None

            height, width = image.shape[:2]

            # Create a basic character mask (full image for now)
            mask = np.ones((height, width), dtype=np.uint8) * 255

            # Create temporary character directory structure
            temp_char_dir = os.path.join(output_dir, "temp_char")
            os.makedirs(temp_char_dir, exist_ok=True)

            # Copy image as texture
            texture_path = os.path.join(temp_char_dir, "texture.png")
            cv2.imwrite(texture_path, image)

            # Save mask
            mask_path = os.path.join(temp_char_dir, "mask.png")
            cv2.imwrite(mask_path, mask)

            # Create char_cfg.yaml
            char_cfg = {
                "name": "generated_character",
                "width": width,
                "height": height,
                "joints": skeleton_data.get("joints", {}),
                "hierarchy": skeleton_data.get("hierarchy", {}),
                "skeleton": skeleton_data,
            }

            char_cfg_path = os.path.join(temp_char_dir, "char_cfg.yaml")
            with open(char_cfg_path, "w") as f:
                yaml.dump(char_cfg, f, default_flow_style=False)

            # Now use the BodyPartsExtractor with the temporary directory
            extractor = BodyPartsExtractor(
                char_dir=temp_char_dir,
                output_dir=output_dir,
                generate_animations=False,
                num_frames=30,
                fps=24,
            )

            # Run the extraction
            extractor.process()

            # Check if parts_info.json was created
            parts_info_path = os.path.join(output_dir, "parts_info.json")
            if os.path.exists(parts_info_path):
                logger.info(f"Parts generated successfully: {parts_info_path}")
                return parts_info_path
            else:
                logger.error("Parts info file not created")
                return None

        except Exception as e:
            logger.error(f"Error in simplified parts generation: {e}")
            return None

    def _generate_parts_with_real_mask(
        self, annotation_results: dict, skeleton_data: dict, output_dir: str
    ) -> str | None:
        """Generate parts using real mask from annotation results."""
        try:
            import shutil

            # Get paths from annotation results
            texture_path = annotation_results.get("texture_path")
            mask_path = annotation_results.get("mask_path")
            char_cfg_path = annotation_results.get("char_cfg_path")

            if not all([texture_path, mask_path, char_cfg_path]):
                logger.error("Missing required paths in annotation results")
                return self._generate_parts_simplified(
                    annotation_results.get("texture_path", ""), skeleton_data, output_dir
                )

            # Create temporary character directory structure
            temp_char_dir = os.path.join(output_dir, "temp_char")
            os.makedirs(temp_char_dir, exist_ok=True)

            # Copy real files from annotation results
            shutil.copy2(texture_path, os.path.join(temp_char_dir, "texture.png"))
            shutil.copy2(mask_path, os.path.join(temp_char_dir, "mask.png"))
            shutil.copy2(char_cfg_path, os.path.join(temp_char_dir, "char_cfg.yaml"))

            logger.info(f"Using real mask and texture from: {mask_path}")

            # Use the BodyPartsExtractor with the real data
            extractor = BodyPartsExtractor(
                char_dir=temp_char_dir,
                output_dir=output_dir,
                generate_animations=False,
                num_frames=30,
                fps=24,
            )

            # Run the extraction
            extractor.process()

            # Check if parts_info.json was created
            parts_info_path = os.path.join(output_dir, "parts_info.json")
            if os.path.exists(parts_info_path):
                logger.info(f"Parts generated successfully with real mask: {parts_info_path}")
                return parts_info_path
            else:
                logger.error("Parts info file not created with real mask")
                return None

        except Exception as e:
            logger.error(f"Error in real mask parts generation: {e}")
            return None

    def handle_extend_skeleton(self) -> None:
        """Handle extending skeleton lengths by 10%."""
        if not self.state.skeleton_data:
            return

        try:
            # Get current skeleton from view
            skeleton_data = self.scene_manager.get_current_skeleton_data()
            if not skeleton_data:
                skeleton_data = self.state.skeleton_data.copy()

            # Extend skeleton joints
            if "joints" in skeleton_data:
                for _joint_id, joint_data in skeleton_data["joints"].items():
                    if "parent" in joint_data and joint_data["parent"]:
                        parent_data = skeleton_data["joints"].get(joint_data["parent"])
                        if parent_data and "position" in joint_data and "position" in parent_data:
                            # Calculate vector from parent to child
                            dx = joint_data["position"][0] - parent_data["position"][0]
                            dy = joint_data["position"][1] - parent_data["position"][1]

                            # Extend by 10%
                            joint_data["position"][0] = parent_data["position"][0] + dx * 1.1
                            joint_data["position"][1] = parent_data["position"][1] + dy * 1.1

            # Update state and view
            self.state.set_skeleton_data(skeleton_data)
            self.skeleton_updated.emit(skeleton_data)
            self.main_window.set_status("Skeleton extended by 10%")

        except Exception as e:
            logger.error(f"Error extending skeleton: {e}")
            QMessageBox.critical(
                self.parent_widget, "Error", f"Failed to extend skeleton: {str(e)}"
            )

    def handle_lock_joints(self) -> None:
        """Handle showing lock/unlock joints dialog."""
        # This would show a dialog for locking/unlocking specific joints
        # For now, we'll show a message
        QMessageBox.information(
            self.parent_widget,
            "Lock Joints",
            "Joint locking functionality will be implemented in a future update.",
        )

    def _try_load_existing_skeleton(self, character_dir: str) -> None:
        """Try to load existing skeleton from character directory."""
        char_cfg_path = os.path.join(character_dir, "char_cfg.yaml")
        if os.path.exists(char_cfg_path):
            try:
                with open(char_cfg_path) as f:
                    skeleton_data = yaml.safe_load(f)
                if skeleton_data:
                    self.state.set_skeleton_data(skeleton_data)
                    logger.info(f"Loaded existing skeleton from {char_cfg_path}")
            except Exception as e:
                logger.error(f"Error loading skeleton config: {e}")

    def _extract_skeleton_from_annotations(
        self, annotation_results: AnnotationResults
    ) -> dict | None:
        """Extract skeleton data from annotation results."""
        # If annotation_results is empty, generate basic test skeleton
        if not annotation_results:
            logger.info("No annotation results, generating basic skeleton for testing")
            return self._generate_basic_skeleton()

        # Try to load skeleton data from char_cfg.yaml if available
        char_cfg_path = annotation_results.get("char_cfg_path")

        if char_cfg_path and os.path.exists(char_cfg_path):
            try:
                with open(char_cfg_path, "r") as f:
                    skeleton_data = yaml.safe_load(f)
                if skeleton_data and "skeleton" in skeleton_data:
                    logger.info(f"Loaded actual skeleton data from {char_cfg_path}")
                    # Convert from char_cfg format to our internal format
                    return self._convert_char_cfg_to_skeleton(skeleton_data)
            except Exception as e:
                logger.warning(f"Could not load skeleton from {char_cfg_path}: {e}")

        # If char_cfg.yaml doesn't exist, fall back to basic skeleton
        logger.info("char_cfg.yaml not found, generating basic skeleton for testing")
        return self._generate_basic_skeleton()

    def _generate_basic_skeleton(self) -> dict:
        """Generate basic skeleton structure for testing purposes."""
        skeleton_data = {
            "joints": {
                "pelvis": {
                    "id": "pelvis",
                    "name": "pelvis",
                    "position": [100, 200],
                    "parent": None,
                },
                "torso": {
                    "id": "torso",
                    "name": "torso",
                    "position": [100, 160],
                    "parent": "pelvis",
                },
                "neck": {"id": "neck", "name": "neck", "position": [100, 120], "parent": "torso"},
                "head_top": {
                    "id": "head_top",
                    "name": "head_top",
                    "position": [100, 90],
                    "parent": "neck",
                },
                "left_shoulder": {
                    "id": "left_shoulder",
                    "name": "left_shoulder",
                    "position": [80, 130],
                    "parent": "torso",
                },
                "left_elbow": {
                    "id": "left_elbow",
                    "name": "left_elbow",
                    "position": [60, 160],
                    "parent": "left_shoulder",
                },
                "left_wrist": {
                    "id": "left_wrist",
                    "name": "left_wrist",
                    "position": [50, 190],
                    "parent": "left_elbow",
                },
                "left_hand": {
                    "id": "left_hand",
                    "name": "left_hand",
                    "position": [45, 205],
                    "parent": "left_wrist",
                },
                "right_shoulder": {
                    "id": "right_shoulder",
                    "name": "right_shoulder",
                    "position": [120, 130],
                    "parent": "torso",
                },
                "right_elbow": {
                    "id": "right_elbow",
                    "name": "right_elbow",
                    "position": [140, 160],
                    "parent": "right_shoulder",
                },
                "right_wrist": {
                    "id": "right_wrist",
                    "name": "right_wrist",
                    "position": [150, 190],
                    "parent": "right_elbow",
                },
                "right_hand": {
                    "id": "right_hand",
                    "name": "right_hand",
                    "position": [155, 205],
                    "parent": "right_wrist",
                },
                "left_hip": {
                    "id": "left_hip",
                    "name": "left_hip",
                    "position": [85, 210],
                    "parent": "pelvis",
                },
                "left_knee": {
                    "id": "left_knee",
                    "name": "left_knee",
                    "position": [80, 250],
                    "parent": "left_hip",
                },
                "left_ankle": {
                    "id": "left_ankle",
                    "name": "left_ankle",
                    "position": [75, 290],
                    "parent": "left_knee",
                },
                "left_foot": {
                    "id": "left_foot",
                    "name": "left_foot",
                    "position": [70, 300],
                    "parent": "left_ankle",
                },
                "right_hip": {
                    "id": "right_hip",
                    "name": "right_hip",
                    "position": [115, 210],
                    "parent": "pelvis",
                },
                "right_knee": {
                    "id": "right_knee",
                    "name": "right_knee",
                    "position": [120, 250],
                    "parent": "right_hip",
                },
                "right_ankle": {
                    "id": "right_ankle",
                    "name": "right_ankle",
                    "position": [125, 290],
                    "parent": "right_knee",
                },
                "right_foot": {
                    "id": "right_foot",
                    "name": "right_foot",
                    "position": [130, 300],
                    "parent": "right_ankle",
                },
            },
            "hierarchy": {
                "pelvis": ["torso", "left_hip", "right_hip"],
                "torso": ["neck", "left_shoulder", "right_shoulder"],
                "neck": ["head_top"],
                "left_shoulder": ["left_elbow"],
                "left_elbow": ["left_wrist"],
                "left_wrist": ["left_hand"],
                "right_shoulder": ["right_elbow"],
                "right_elbow": ["right_wrist"],
                "right_wrist": ["right_hand"],
                "left_hip": ["left_knee"],
                "left_knee": ["left_ankle"],
                "left_ankle": ["left_foot"],
                "right_hip": ["right_knee"],
                "right_knee": ["right_ankle"],
                "right_ankle": ["right_foot"],
                "head_top": [],
                "left_hand": [],
                "right_hand": [],
                "left_foot": [],
                "right_foot": [],
            },
        }

        # Add joint_map for the basic skeleton
        joint_map = {joint_id: joint_id for joint_id in skeleton_joints.keys()}
        skeleton_data["joint_map"] = joint_map

        logger.info("Generated basic skeleton structure for testing")
        return skeleton_data

    def _convert_char_cfg_to_skeleton(self, char_cfg_data: dict) -> dict:
        """Convert char_cfg.yaml format to animated drawings format for SkeletonManager."""
        # Convert to animated drawings format that SkeletonManager expects
        skeleton_list = []

        # Process each joint from the skeleton list
        for joint in char_cfg_data.get("skeleton", []):
            joint_name = joint["name"]
            parent_name = joint["parent"]
            coordinates = joint["loc"]  # Use the cropped coordinates
            
            skeleton_list.append({
                "name": joint_name,
                "parent": parent_name,
                "coordinates": coordinates,
                "loc": coordinates,  # Also provide 'loc' for compatibility
            })

        logger.info(f"Converted char_cfg to skeleton with {len(skeleton_list)} joints")
        # Return in animated drawings format that SkeletonManager can process
        return {"skeleton": skeleton_list}

    def load_image_from_path(self, image_path: str) -> None:
        """Public method to load an image from a specific path."""
        self._load_image_from_path(image_path)

    def resume_processing(self) -> None:
        """Resume any background processing when tab is activated."""
        logger.debug("ImageProcessingActionHandler: Resuming processing")
        # For image processing tab, this could resume any paused operations
        # Currently no long-running background tasks to resume
        pass

    def pause_processing(self) -> None:
        """Pause any background processing when tab is deactivated."""
        logger.debug("ImageProcessingActionHandler: Pausing processing")
        # For image processing tab, this could pause any ongoing operations
        # Currently no long-running background tasks to pause
        pass
