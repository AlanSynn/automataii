import os
import json
import logging
import yaml  # Added for char_cfg.yaml parsing
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, QRectF, QPointF
from pydantic import (
    ValidationError,
    BaseModel,
    Field,
    validator,
    RootModel,
    field_validator,
)

# Import runtime PartInfo and Pydantic models
from .models import PartInfo  # Runtime PartInfo class
from .models_pydantic import (
    ProjectFileModel as PydanticProjectFileModel,
    CharacterDataModel as PydanticCharacterDataModel,
    PartInfoModel as PydanticPartInfoModel,
    SkeletonJointModel as PydanticSkeletonJointModel,
)  # Pydantic models


class ProjectDataManager(QObject):
    """
    Manages loading, storing, and accessing project-specific data,
    primarily character parts and skeleton information from parts_info.json,
    using Pydantic models for validation.
    """

    # project_data_loaded signal now emits validated Pydantic models or runtime PartInfo as needed.
    # For simplicity, let's assume MainWindow/EditorTab eventually need runtime PartInfo instances.
    # The raw skeleton data can be the list of dicts from Pydantic model directly.
    project_data_loaded = pyqtSignal(
        bool, str, dict
    )  # success: bool, project_directory_path: str, parts_info: Dict[str, PartInfo]
    project_data_cleared = pyqtSignal()
    error_occurred = pyqtSignal(str)  # For reporting errors

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._project_dir: Optional[Path] = None
        # self._raw_parts_data: Optional[Dict[str, Any]] = None # Replaced by Pydantic model parsing
        self._validated_project_data: Optional[PydanticProjectFileModel] = (
            None  # Store the validated Pydantic model
        )

        self._parts: Dict[str, PartInfo] = {}  # Runtime PartInfo objects
        self._raw_skeleton_data: Optional[List[Dict[str, Any]]] = (
            None  # For SkeletonManager
        )
        self._effective_bounding_box_offset: QPointF = QPointF(0, 0)

        logging.info("ProjectDataManager initialized.")

    @property
    def project_dir(self) -> Optional[Path]:
        return self._project_dir

    @property
    def parts(self) -> Dict[str, PartInfo]:
        """Returns a dictionary of runtime PartInfo objects."""
        return self._parts.copy()

    @property
    def raw_skeleton_data(self) -> Optional[List[Dict[str, Any]]]:
        """Returns the raw skeleton data (list of joint dicts) as validated by Pydantic."""
        # This can be directly from the Pydantic model's skeleton_joints if they are dicts
        if self._validated_project_data and self._validated_project_data.character:
            # Convert Pydantic SkeletonJointModel instances to dicts if SkeletonManager expects dicts
            return [
                joint.model_dump()
                for joint in self._validated_project_data.character.skeleton_joints
            ]
        return None

    @property
    def effective_bounding_box_offset(self) -> QPointF:
        return self._effective_bounding_box_offset

    def load_project_from_file(self, filepath: str) -> bool:
        logging.info(f"ProjectDataManager: Attempting to load project from: {filepath}")
        self.clear_project_data()

        try:
            fp = Path(filepath)
            if not fp.exists() or not fp.is_file():
                logging.error(f"File not found: {filepath}")
                self.error_occurred.emit(f"File not found: {filepath}")
                self.project_data_loaded.emit(
                    False, "", {}
                )  # Keep existing signal emission for failure
                return False

            self._project_dir = fp.parent

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate data with Pydantic models
            validated_data = PydanticProjectFileModel.model_validate(data)
            self._validated_project_data = validated_data

            # Attempt to load skeleton from char_cfg.yaml if not present in main project file
            self._try_load_supplemental_skeleton_data()

            # Prepare runtime PartInfo objects and calculate bounding box
            all_part_rects = []
            parsed_parts_temp: Dict[str, PartInfo] = {}

            if (
                self._validated_project_data.character
                and self._validated_project_data.character.parts
            ):
                for (
                    part_name,
                    pydantic_part_model,
                ) in self._validated_project_data.character.parts.items():
                    # The name should already be in pydantic_part_model due to the validator
                    # If not, ensure pydantic_part_model.name = part_name here if necessary.
                    # The current validator in CharacterDataModel populates this.

                    # Create runtime PartInfo from Pydantic model
                    runtime_part_info = PartInfo.from_pydantic(
                        pydantic_part_model, project_dir=self._project_dir
                    )
                    parsed_parts_temp[part_name] = runtime_part_info

                    if runtime_part_info.roi:  # roi is [x, y, width, height]
                        all_part_rects.append(
                            QRectF(
                                runtime_part_info.roi[0],
                                runtime_part_info.roi[1],
                                runtime_part_info.roi[2],
                                runtime_part_info.roi[3],
                            )
                        )

            if all_part_rects:
                overall_bounds = QRectF()
                for rect in all_part_rects:
                    overall_bounds = overall_bounds.united(rect)
                self._effective_bounding_box_offset = -overall_bounds.center()
            else:
                self._effective_bounding_box_offset = QPointF(0, 0)

            self._parts = parsed_parts_temp
            # self._raw_skeleton_data is now implicitly handled by the raw_skeleton_data property

            num_loaded_parts = len(self._parts)
            num_skeleton_joints = (
                len(self._validated_project_data.character.skeleton_joints)
                if self._validated_project_data.character
                else 0
            )

            logging.info(
                f"ProjectDataManager: Successfully validated and parsed {num_loaded_parts} parts. Project dir: {self._project_dir}"
            )
            if num_skeleton_joints > 0:
                logging.info(
                    f"ProjectDataManager: Validated {num_skeleton_joints} skeleton joints."
                )

            self.project_data_loaded.emit(
                True, str(self._project_dir), self._parts.copy()
            )
            # MainWindow's _handle_project_data_loaded will need adjustment if it expects raw dicts vs PartInfo
            # For now, it receives parts_info: Dict[str, PartInfo] which is what self.parts provides.
            # And editor_graphics_items: Dict[str, CharacterPartItem] which is created in MainWindow.
            return True

        except ValidationError as ve:
            logging.error(
                f"ProjectDataManager: Pydantic validation error in {filepath}. {ve}",
                exc_info=True,
            )
            self.error_occurred.emit(
                f"Invalid project file format: {ve.errors()}"
            )  # Send Pydantic errors
        except json.JSONDecodeError as je:
            logging.error(
                f"ProjectDataManager: Invalid JSON in {filepath}. {je}", exc_info=True
            )
            self.error_occurred.emit(f"Invalid JSON file: {je.msg}")
        except Exception as e:
            logging.error(
                f"ProjectDataManager: Error loading project from {filepath}: {e}",
                exc_info=True,
            )
            self.error_occurred.emit(f"Failed to load project: {e}")

        self.clear_project_data()  # Ensure clean state on error
        # Emit failure with empty parts dict
        self.project_data_loaded.emit(False, "", {})
        return False

    def _try_load_supplemental_skeleton_data(self):
        """
        Attempts to load skeleton data from char_cfg.yaml if not found or empty
        in the primary project data (e.g., parts_info.json).
        Updates self._validated_project_data.character.skeleton_joints.
        """
        if (
            not self._project_dir
            or not self._validated_project_data
            or not self._validated_project_data.character
        ):
            logging.debug(
                "Project dir or character data not available for supplemental skeleton load."
            )
            return

        # Check if skeleton data is already populated from the main project file
        if (
            self._validated_project_data.character.skeleton_joints
            and len(self._validated_project_data.character.skeleton_joints) > 0
        ):
            logging.info(
                "Skeleton data already present in main project file. Skipping supplemental load."
            )
            return

        char_cfg_path = self._project_dir / "char_cfg.yaml"
        if not char_cfg_path.exists():
            logging.info(
                f"char_cfg.yaml not found at {char_cfg_path}, no supplemental skeleton to load."
            )
            return

        logging.info(
            f"Attempting to load supplemental skeleton data from {char_cfg_path}"
        )
        try:
            with open(char_cfg_path, "r", encoding="utf-8") as f:
                char_cfg_data = yaml.safe_load(f)

            if (
                not char_cfg_data
                or "skeleton" not in char_cfg_data
                or not isinstance(char_cfg_data["skeleton"], list)
            ):
                logging.warning(
                    f"Invalid or missing 'skeleton' list in {char_cfg_path}."
                )
                return

            supplemental_joints_raw = char_cfg_data["skeleton"]
            pydantic_skeleton_joints: List[PydanticSkeletonJointModel] = []
            for joint_data_raw in supplemental_joints_raw:
                if not isinstance(joint_data_raw, dict):
                    logging.warning(
                        f"Skipping non-dict joint data in char_cfg.yaml: {joint_data_raw}"
                    )
                    continue
                try:
                    # Adapt the raw data from char_cfg.yaml to PydanticSkeletonJointModel fields
                    joint_name = joint_data_raw.get("name")
                    joint_loc = joint_data_raw.get("loc")
                    joint_parent = joint_data_raw.get("parent")

                    if not joint_name:
                        logging.warning(
                            f"Skipping joint in char_cfg.yaml with missing name: {joint_data_raw}"
                        )
                        continue
                    if not joint_loc or not (
                        isinstance(joint_loc, list) and len(joint_loc) == 2
                    ):
                        logging.warning(
                            f"Skipping joint '{joint_name}' in char_cfg.yaml with invalid or missing 'loc': {joint_loc}"
                        )
                        continue

                    adapted_joint_data = {
                        "id": joint_name,  # Use name as id
                        "name": joint_name,
                        "position": [
                            float(joint_loc[0]),
                            float(joint_loc[1]),
                        ],  # Ensure floats
                        "parent": (
                            str(joint_parent) if joint_parent is not None else None
                        ),
                    }

                    # Ensure parent is a string or None (already handled above)
                    # if 'parent' in adapted_joint_data and adapted_joint_data['parent'] is None:
                    #     pass # None is fine
                    # elif 'parent' in adapted_joint_data and not isinstance(adapted_joint_data['parent'], str):
                    #      adapted_joint_data['parent'] = str(adapted_joint_data['parent'])

                    pydantic_joint = PydanticSkeletonJointModel.model_validate(
                        adapted_joint_data
                    )
                    pydantic_skeleton_joints.append(pydantic_joint)
                except ValidationError as ve_joint:
                    logging.warning(
                        f"Validation error for a joint in char_cfg.yaml: {joint_data_raw}. Error: {ve_joint}"
                    )
                except Exception as e_joint:
                    logging.warning(
                        f"Error processing a joint in char_cfg.yaml: {joint_data_raw}. Error: {e_joint}"
                    )

            if pydantic_skeleton_joints:
                self._validated_project_data.character.skeleton_joints = (
                    pydantic_skeleton_joints
                )
                logging.info(
                    f"Successfully loaded and validated {len(pydantic_skeleton_joints)} joints from {char_cfg_path}."
                )
            else:
                logging.info(
                    f"No valid joints found in {char_cfg_path} to load supplementally."
                )

        except yaml.YAMLError as ye:
            logging.error(
                f"Error parsing YAML from {char_cfg_path}: {ye}", exc_info=True
            )
        except Exception as e:
            logging.error(
                f"Unexpected error loading supplemental skeleton from {char_cfg_path}: {e}",
                exc_info=True,
            )

    def clear_project_data(self):
        logging.info("ProjectDataManager: Clearing project data.")
        self._project_dir = None
        self._validated_project_data = None
        self._parts.clear()
        self._raw_skeleton_data = None  # Explicitly clear this
        self._effective_bounding_box_offset = QPointF(0, 0)
        self.project_data_cleared.emit()

    def get_part_info(self, part_name: str) -> Optional[PartInfo]:
        return self._parts.get(part_name)

    def get_all_parts(self) -> Dict[str, PartInfo]:
        return self.parts

    def clear_all_motion_paths(self) -> None:
        if not self._parts:
            logging.info(
                "ProjectDataManager: No parts loaded to clear motion paths from."
            )
            return
        cleared_count = 0
        for part_info in self._parts.values():  # Iterate through runtime PartInfo
            path_cleared = False
            if (
                hasattr(part_info, "motion_path_data")
                and part_info.motion_path_data is not None
            ):
                part_info.motion_path_data = None  # Clear QPainterPath
                path_cleared = True
            # If PartInfoModel was also stored and needed update, do it here. But primarily runtime PartInfo.
            if path_cleared:
                cleared_count += 1
        if cleared_count > 0:
            logging.info(
                f"ProjectDataManager: Cleared motion paths for {cleared_count} parts."
            )
        else:
            logging.info("ProjectDataManager: No motion paths found to clear.")

    def get_current_parts_data(self) -> Optional[Dict[str, PartInfo]]:
        if self._parts:
            return self._parts.copy()
        return None

    # --- Methods for project saving (to be implemented using Pydantic models) ---
    def save_project_to_file(self, filepath: str) -> bool:
        logging.info(f"ProjectDataManager: Attempting to save project to: {filepath}")
        if (
            not self._validated_project_data
            or not self._validated_project_data.character
        ):
            logging.warning("No project data to save.")
            self.error_occurred.emit("No project data available to save.")
            return False

        try:
            # Update Pydantic models from runtime PartInfo objects if they have changed
            # This is crucial if runtime PartInfo (e.g., motion_path_data) can be modified
            # and these changes need to be reflected back into the Pydantic model before saving.
            current_parts_pydantic: Dict[str, PydanticPartInfoModel] = {}
            for name, runtime_part in self._parts.items():
                # This is a simplification. A full conversion from runtime PartInfo to PydanticPartInfoModel
                # would be needed here, especially for complex types like motion_path_data.
                # For now, assume self._validated_project_data.character.parts holds the latest structural data
                # and we are just updating fields that might have changed if PartInfo was directly modified.
                # This section needs careful implementation if bidirectional sync is complex.

                # Simplistic: Re-create Pydantic model from runtime PartInfo
                # This assumes PartInfo has all necessary fields or can be converted to a dict for Pydantic model creation.
                # This is non-trivial if PartInfo contains Qt objects directly.
                # A better approach: modify the existing self._validated_project_data.character.parts objects.

                # For now, let's assume the Pydantic model that was loaded is mostly up-to-date
                # or changes are managed by updating the Pydantic model instance itself elsewhere.
                # The ideal way is to have a method PartInfo.to_pydantic_model() -> PydanticPartInfoModel.
                pass  # Placeholder for update logic

            # For demonstration, we serialize the stored _validated_project_data
            # In a real app, ensure _validated_project_data reflects all runtime changes.
            json_data_to_save = self._validated_project_data.model_dump(
                mode="json", by_alias=True
            )

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(json_data_to_save, f, indent=4)

            logging.info(f"Project successfully saved to {filepath}")
            self._project_dir = Path(filepath).parent  # Update project dir
            # Optionally, emit a signal for project_saved
            return True

        except Exception as e:
            logging.error(f"Error saving project to {filepath}: {e}", exc_info=True)
            self.error_occurred.emit(
                f"Error saving project to {Path(filepath).name}: {e}"
            )
            return False

    # Methods for MainWindow to call for dialogs
    def new_project(self):
        # Similar to clear_project_data but maybe with different logging/signals
        logging.info("ProjectDataManager: New project requested.")
        self.clear_project_data()
        # self.project_newed_signal.emit() # Or reuse project_data_cleared

    def load_project_dialog(self):
        from PyQt6.QtWidgets import QFileDialog  # Local import

        start_dir = (
            str(self._project_dir) if self._project_dir else os.path.expanduser("~")
        )
        filepath, _ = QFileDialog.getOpenFileName(
            None,  # Parent can be None for a static method or if no obvious parent
            "Load Project File",
            start_dir,
            "JSON files (*.json);;All files (*)",
        )
        if filepath:
            self.load_project_from_file(filepath)

    def save_project_dialog(self):
        from PyQt6.QtWidgets import QFileDialog  # Local import

        if not self._project_dir or not self._parts:
            logging.warning("No project data loaded to save. Use Save As.")
            # self.error_occurred.emit("No project loaded. Use Save As.") # Not an error, just guidance
            self.save_project_as_dialog()  # Fallback to Save As if no current project path
            return

        # Default to current project name if available
        default_filename = "parts_info.json"
        if self._project_dir:
            # Attempt to find the original filename if project was loaded
            # This assumes a specific naming or needs to be stored from load_project_from_file
            # For simplicity, let's stick to a common name or improve this to remember loaded filename.
            pass

        # Since we don't store the exact loaded filename, saving to self._project_dir / default_filename
        # might overwrite a differently named file if the project was loaded from e.g. "my_char.json"
        # For now, let's assume we save to a fixed name in the current project_dir or prompt.
        # Better: if self.loaded_filepath: self.save_project_to_file(self.loaded_filepath)
        # else: self.save_project_as_dialog()
        # For now, let's just save to a fixed name in the project directory
        # This is a simplification for the example.
        if self._project_dir:  # Ensure project_dir is set
            potential_save_path = self._project_dir / default_filename
            self.save_project_to_file(str(potential_save_path))
        else:
            self.save_project_as_dialog()  # Should not happen if self._parts is true

    def save_project_as_dialog(self):
        from PyQt6.QtWidgets import QFileDialog  # Local import

        start_dir = (
            str(self._project_dir) if self._project_dir else os.path.expanduser("~")
        )
        default_save_name = "parts_info.json"
        if (
            self._project_dir
            and self._validated_project_data
            and self._validated_project_data.character
        ):
            # Use character name for a more descriptive default, if available
            char_name = self._validated_project_data.character.name
            safe_char_name = "".join(
                c if c.isalnum() or c in (" ", "_", "-") else "" for c in char_name
            ).strip()
            if safe_char_name:
                default_save_name = f"{safe_char_name}_parts_info.json"

        filepath, _ = QFileDialog.getSaveFileName(
            None,
            "Save Project As",
            os.path.join(start_dir, default_save_name),
            "JSON files (*.json);;All files (*)",
        )
        if filepath:
            self.save_project_to_file(filepath)


# Example Usage (for testing or understanding)
if __name__ == "__main__":
    # This __main__ block needs to be updated significantly to test Pydantic integration
    # For now, it's left as a reference to the old structure.
    logging.basicConfig(level=logging.DEBUG)

    # Mock PartInfo and models.py location for standalone test
    # class PartInfo: (old mock)

    # Create a dummy parts_info.json for testing
    dummy_parts_info_content = {
        "character": {
            "name": "DummyCharacterPydantic",
            "parts": {
                "head": {
                    "name": "head",
                    "svg_path_file": "head.svg",
                    "roi": [10, 10, 20, 20],
                    "z_value": 1,
                },
                "torso": {
                    "name": "torso",
                    "svg_path_file": "torso.svg",
                    "roi": [0, 30, 40, 50],
                    "z_value": 0,
                },
            },
            "skeleton_joints": [
                {"id": "j1", "name": "neck", "position": [20, 30]},
                {"id": "j2", "name": "head_top", "position": [20, 10], "parent": "j1"},
            ],
        }
    }
    dummy_filepath = "./dummy_project_pydantic.json"
    with open(dummy_filepath, "w") as f:
        json.dump(dummy_parts_info_content, f, indent=4)

    # Test with an invalid file (e.g. missing character key)
    invalid_dummy_content = {"char": {}}
    invalid_filepath = "./invalid_project_pydantic.json"
    with open(invalid_filepath, "w") as f:
        json.dump(invalid_dummy_content, f, indent=4)

    manager = ProjectDataManager()

    def on_loaded_pydantic(success, proj_dir, parts_info):
        logging.info(
            f"PYDANTIC TEST: Caught project_data_loaded: Success={success}, Dir='{proj_dir}'"
        )
        if success:
            logging.info(f"  Offset: {manager.effective_bounding_box_offset}")
            all_runtime_parts = parts_info
            logging.info(
                f"  Loaded runtime parts ({len(all_runtime_parts)}): {list(all_runtime_parts.keys())}"
            )
            if all_runtime_parts.get("head"):
                logging.info(f"    Head ROI (runtime): {all_runtime_parts['head'].roi}")
                logging.info(
                    f"    Head QPainterPath (runtime): {all_runtime_parts['head'].qpainter_path}"
                )
            raw_skel_data = manager.raw_skeleton_data
            if raw_skel_data:
                logging.info(
                    f"  Raw skeleton joints from Pydantic ({len(raw_skel_data)}): {raw_skel_data[0] if raw_skel_data else 'None'}"
                )

    def on_cleared_pydantic():
        logging.info("PYDANTIC TEST: Caught project_data_cleared")

    def on_error_pydantic(msg):
        logging.error(f"PYDANTIC TEST: Caught error: {msg}")

    manager.project_data_loaded.connect(on_loaded_pydantic)
    manager.project_data_cleared.connect(on_cleared_pydantic)
    manager.error_occurred.connect(on_error_pydantic)

    logging.info("--- PYDANTIC TEST: Loading valid file ---")
    manager.load_project_from_file(dummy_filepath)

    # Test saving
    if manager._validated_project_data:  # Check if data loaded successfully
        save_test_path = "./dummy_project_pydantic_saved.json"
        logging.info(f"--- PYDANTIC TEST: Saving to {save_test_path} ---")
        manager.save_project_to_file(save_test_path)
        # Try loading the saved file
        logging.info(f"--- PYDANTIC TEST: Loading saved file {save_test_path} ---")
        manager.load_project_from_file(save_test_path)
        os.remove(save_test_path)

    logging.info("--- PYDANTIC TEST: Loading invalid file (validation error) ---")
    manager.load_project_from_file(invalid_filepath)

    logging.info("--- PYDANTIC TEST: Loading non-existent file ---")
    manager.load_project_from_file("non_existent_pydantic.json")

    manager.clear_project_data()
    logging.info("--- PYDANTIC TEST: After clear ---")
    logging.info(f"Parts after clear: {manager.get_all_parts()}")

    # Clean up dummy files
    if os.path.exists(dummy_filepath):
        os.remove(dummy_filepath)
    if os.path.exists(invalid_filepath):
        os.remove(invalid_filepath)
    print(f"Pydantic test dummy files removed or were not created.")
