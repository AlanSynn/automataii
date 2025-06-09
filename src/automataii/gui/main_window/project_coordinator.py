"""Project-related operations coordination for the main window."""

import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Any
import shutil

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import pyqtSlot, QObject

from automataii.core.models.mechanism import PartInfo
from automataii.core.models.project import ProjectFileModel

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class ProjectCoordinator(QObject):
    """Coordinates project-related operations."""

    def __init__(self, main_window: 'AutomataDesigner'):
        super().__init__()
        self.main_window = main_window
        self.current_temp_char_dir: Optional[Path] = None

    def load_parts_dialog(self):
        """Opens a file dialog to load parts from a JSON file."""
        start_dir = (
            str(self.main_window.project_data_manager.project_dir)
            if self.main_window.project_data_manager.project_dir
            else os.path.expanduser("~")
        )

        filepath, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Load Character Parts File",
            start_dir,
            "JSON files (*.json);;All files (*)",
        )
        if filepath:
            self.main_window.project_data_manager.load_project_from_file(filepath)

    def save_project_dialog(self):
        """Opens a file dialog to save the current project."""
        if hasattr(self.main_window.project_data_manager, "save_project_dialog"):
            self.main_window.project_data_manager.save_project_dialog()
        else:
            logging.error("ProjectDataManager does not have save_project_dialog method.")
            QMessageBox.critical(
                self.main_window, "Error", "Save project functionality is not available."
            )

    def load_project_dialog(self):
        """Opens a file dialog to load a project."""
        if hasattr(self.main_window.project_data_manager, "load_project_dialog"):
            self.main_window.project_data_manager.load_project_dialog()
        else:
            logging.error("ProjectDataManager does not have load_project_dialog method.")
            QMessageBox.critical(
                self.main_window, "Error", "Load project functionality is not available."
            )

    @pyqtSlot(dict, str)
    def handle_parts_generated_from_tab(
        self, annotation_results: dict, final_bpe_char_dir_str: str
    ):
        """Handles the parts_generated signal from ImageProcessingTab."""
        logging.info(
            f"MainWindow: Received parts_generated. Annotation results output_dir: {annotation_results.get('output_dir')}, Final BPE dir: {final_bpe_char_dir_str}"
        )

        parts_info_json_path = Path(final_bpe_char_dir_str) / "parts_info.json"
        source_char_cfg_path_str = annotation_results.get("char_cfg_path")

        if not source_char_cfg_path_str:
            logging.error(
                "handle_parts_generated_from_tab: 'char_cfg_path' not found in annotation_results."
            )
            QMessageBox.critical(
                self.main_window, "Error", "char_cfg.yaml path not found in annotation data."
            )
            return

        source_char_cfg_path = Path(source_char_cfg_path_str)
        dest_char_cfg_path = Path(final_bpe_char_dir_str) / "char_cfg.yaml"

        if source_char_cfg_path.exists():
            try:
                shutil.copy2(source_char_cfg_path, dest_char_cfg_path)
                logging.info(
                    f"Copied {source_char_cfg_path} to {dest_char_cfg_path} for ProjectDataManager."
                )

                source_mask_path_str = annotation_results.get("mask_path")
                if source_mask_path_str:
                    source_mask_path = Path(source_mask_path_str)
                    dest_mask_path = Path(final_bpe_char_dir_str) / "mask.png"
                    if source_mask_path.exists():
                        shutil.copy2(source_mask_path, dest_mask_path)
                        logging.info(f"Copied {source_mask_path} to {dest_mask_path}.")
                    else:
                        logging.warning(
                            f"Source mask.png not found at {source_mask_path}, cannot copy."
                        )
                else:
                    logging.warning(
                        "'mask_path' not in annotation_results, cannot copy mask.png."
                    )

            except Exception as e:
                logging.error(
                    f"Failed to copy files to BPE output dir: {e}", exc_info=True
                )
                QMessageBox.warning(
                    self.main_window,
                    "File Copy Error",
                    f"Could not copy necessary files for project loading: {e}",
                )
        else:
            logging.warning(
                f"Source char_cfg.yaml not found at {source_char_cfg_path}, cannot copy to BPE output dir."
            )

        if not parts_info_json_path.exists():
            logging.error(
                f"CRITICAL ERROR IN MAINWINDOW: parts_info.json path derived as {parts_info_json_path} but file does not exist."
            )
            QMessageBox.critical(
                self.main_window,
                "Project Load Error",
                f"Internal error: Could not locate parts_info.json at {parts_info_json_path}.",
            )
            return

        logging.info(
            f"Attempting to load project data from parts_info.json: {parts_info_json_path}"
        )
        success = self.main_window.project_data_manager.load_project_from_file(
            str(parts_info_json_path)
        )

        if success:
            self.main_window.statusBar().showMessage("Part data loaded successfully.", 3000)
            self.current_temp_char_dir = Path(final_bpe_char_dir_str)
            logging.info(
                f"MainWindow: Project loaded. Updated current_temp_char_dir to BPE output: {self.current_temp_char_dir}"
            )
        else:
            self.main_window.statusBar().showMessage("Failed to load part data. Check logs.", 5000)

    @pyqtSlot(dict)
    def handle_skeleton_updated_from_tab(self, skeleton_data: dict):
        """Handles the skeleton_updated signal from ImageProcessingTab."""
        logging.info(
            "MainWindow: Received skeleton_updated signal from tab. Forwarding to SkeletonManager."
        )

        if self.main_window.skeleton_manager:
            self.main_window.skeleton_manager.load_skeleton_from_dict(
                skeleton_data, source_format="animated_drawings"
            )
            # Send skeleton to mechanism generation tab
            if hasattr(self.main_window, "mechanism_generation_tab") and hasattr(self.main_window.mechanism_generation_tab, "set_skeleton_data"):
                self.main_window.mechanism_generation_tab.set_skeleton_data(skeleton_data)
        else:
            logging.error(
                "MainWindow: SkeletonManager not available to handle skeleton update."
            )
            QMessageBox.warning(
                self.main_window,
                "Error",
                "SkeletonManager not initialized. Cannot process skeleton.",
            )

    @pyqtSlot(bool, str, object)
    def handle_project_data_loaded(
        self,
        success: bool,
        project_directory_path: str,
        parts_info: Dict[str, PartInfo],
    ):
        """Handles the project_data_loaded signal from ProjectDataManager."""
        logging.info(f"handle_project_data_loaded called with success={success}, parts_info keys: {list(parts_info.keys()) if parts_info else 'None'}")
        if success:
            logging.info(
                f"MainWindow: Project data loaded successfully from {project_directory_path}"
            )
            self.main_window.project_dir = Path(project_directory_path)

            # Pass PartInfo data to EditorTab
            self.main_window.editor_tab.set_parts_data(parts_info)

            # Pass PartInfo data to the ImageProcessingTab to ensure it has the validated data
            if hasattr(self.main_window, "image_proc_tab") and hasattr(
                self.main_window.image_proc_tab, "on_project_data_loaded"
            ):
                self.main_window.image_proc_tab.on_project_data_loaded(parts_info)

            # Pass PartInfo data to MechanismGenerationTab
            if hasattr(self.main_window, "mechanism_generation_tab") and hasattr(self.main_window.mechanism_generation_tab, "set_parts_data"):
                self.main_window.mechanism_generation_tab.set_parts_data(parts_info)

            # Update other tabs/managers as needed
            if hasattr(self.main_window.ik_manager, "set_project_parts_data"):
                self.main_window.ik_manager.set_project_parts_data(parts_info)

            current_skeleton_data_raw = self.main_window.project_data_manager.raw_skeleton_data
            if current_skeleton_data_raw:
                self.main_window.skeleton_manager.load_skeleton_from_project_data(
                    current_skeleton_data_raw, parts_info
                )
                # Send skeleton to mechanism generation tab
                if hasattr(self.main_window, "mechanism_generation_tab") and hasattr(self.main_window.mechanism_generation_tab, "set_skeleton_data"):
                    self.main_window.mechanism_generation_tab.set_skeleton_data(current_skeleton_data_raw)
            else:
                self.main_window.skeleton_manager.clear_data()
                if hasattr(self.main_window.editor_tab, "cache_initial_skeleton"):
                    self.main_window.editor_tab.cache_initial_skeleton(None)
                # Clear skeleton in mechanism generation tab
                if hasattr(self.main_window, "mechanism_generation_tab") and hasattr(self.main_window.mechanism_generation_tab, "set_skeleton_data"):
                    self.main_window.mechanism_generation_tab.set_skeleton_data(None)

            self.main_window.image_proc_tab.on_parts_loaded_in_editor(True)
            self.main_window.statusBar().showMessage(f"Project loaded: {project_directory_path}")
            self.main_window.action_manager.update_actions_for_project_state(True)

            if parts_info:
                logging.info(
                    f"MainWindow: Project and parts data ({len(parts_info)} parts) loaded. Switching to editor tab if needed."
                )
                if self.main_window.tab_widget.currentWidget() != self.main_window.editor_tab:
                    self.main_window.tab_manager.switch_to_editor_tab()
            else:
                logging.info(
                    "MainWindow: Project loaded, but no specific parts data found in parts_info dict."
                )
        else:
            logging.error(
                f"MainWindow: Project loading failed from {project_directory_path}"
            )
            self._clear_ui_for_failed_load()
            QMessageBox.critical(
                self.main_window,
                "Load Project Error",
                f"Failed to load project from {project_directory_path}.",
            )
            self.main_window.statusBar().showMessage("Project loading failed.")
            self.main_window.action_manager.update_actions_for_project_state(False)

    @pyqtSlot()
    def handle_project_data_cleared(self):
        """Handles the project_data_cleared signal from ProjectDataManager."""
        logging.info("MainWindow: Handling project data cleared signal.")
        self.main_window.editor_tab.clear_editor_content()
        self.main_window.skeleton_manager.clear_data()
        if self.main_window.ik_manager:
            self.main_window.ik_manager.reset_all_ik_systems_and_data()
        self.main_window.action_manager.update_actions_for_project_state(False)
        self.main_window.statusBar().showMessage("Project data cleared.")

    @pyqtSlot(str)
    def handle_project_manager_error(self, error_message: str):
        """Handles error signals from the ProjectDataManager."""
        logging.error(f"ProjectDataManager error: {error_message}")
        QMessageBox.critical(
            self.main_window, "Project Error", f"An error occurred: {error_message}"
        )

    @pyqtSlot()
    def save_character_alignment_impl(self):
        """Implementation for saving character alignment."""
        logging.info("MainWindow: Received request to save character alignment.")
        self.main_window.statusBar().showMessage("Character alignment save requested.")

    @pyqtSlot()
    def generate_blueprint_impl(self):
        """Implementation for generating blueprint."""
        logging.info("MainWindow: Received request to generate blueprint.")
        self.main_window.statusBar().showMessage("Blueprint generation requested.")

    def _clear_ui_for_failed_load(self):
        """Helper to clear relevant UI parts when project loading fails."""
        if hasattr(self.main_window, "editor_tab") and self.main_window.editor_tab:
            self.main_window.editor_tab.clear_editor_content()

        if hasattr(self.main_window.image_proc_tab, "clear_display_and_data"):
            self.main_window.image_proc_tab.clear_display_and_data()

        self.main_window.skeleton_manager.clear_data()
        self.main_window.ik_manager.clear_ik_data()
        logging.info("UI cleared due to failed project load.")
