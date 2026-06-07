import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml  # Added for char_cfg.yaml parsing
from pydantic import (
    ValidationError,
)
from PyQt6.QtCore import QObject, QPointF, QRectF, pyqtSignal

from automataii.domain.project import (
    ProjectFileModel as PydanticProjectFileModel,
)
from automataii.domain.project import (
    SkeletonJointModel as PydanticSkeletonJointModel,
)

# Import runtime PartInfo and Pydantic models
from automataii.presentation.qt.models import PartInfo


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

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._project_dir: Path | None = None
        # self._raw_parts_data: Optional[Dict[str, Any]] = None # Replaced by Pydantic model parsing
        self._validated_project_data: PydanticProjectFileModel | None = (
            None  # Store the validated Pydantic model
        )

        self._parts: dict[str, PartInfo] = {}  # Runtime PartInfo objects
        self._raw_skeleton_data: list[dict[str, Any]] | None = None  # For SkeletonManager
        self._effective_bounding_box_offset: QPointF = QPointF(0, 0)

        logging.info("ProjectDataManager initialized.")

    @property
    def project_dir(self) -> Path | None:
        return self._project_dir

    @property
    def parts(self) -> dict[str, PartInfo]:
        """Returns a dictionary of runtime PartInfo objects."""
        return self._parts.copy()

    @property
    def raw_skeleton_data(self) -> list[dict[str, Any]] | None:
        """Returns the raw skeleton data (list of joint dicts) as validated by Pydantic."""
        # This can be directly from the Pydantic model's skeleton_joints if they are dicts
        if self._validated_project_data and self._validated_project_data.character:
            skeleton_joints = self._validated_project_data.character.skeleton_joints
            if skeleton_joints:
                # Convert Pydantic SkeletonJointModel instances to dicts if SkeletonManager expects dicts
                return [joint.model_dump() for joint in skeleton_joints]
        return None

    @property
    def effective_bounding_box_offset(self) -> QPointF:
        return self._effective_bounding_box_offset

    def load_project_from_file(self, filepath: str) -> bool:
        """Load and validate a project file.

        Args:
            filepath: Path to the project JSON file.

        Returns:
            True if successful, False otherwise.
        """
        logging.info(f"ProjectDataManager: Attempting to load project from: {filepath}")
        self.clear_project_data(emit_signal=False)

        try:
            if not self._validate_and_load_json(filepath):
                return False

            self._try_load_supplemental_skeleton_data()
            self._process_character_parts()
            self._log_load_success()

            self.project_data_loaded.emit(True, str(self._project_dir), self._parts.copy())
            return True

        except ValidationError as ve:
            self._handle_validation_error(filepath, ve)
        except json.JSONDecodeError as je:
            self._handle_json_error(filepath, je)
        except Exception as e:
            self._handle_generic_error(filepath, e)

        self.clear_project_data()
        self.project_data_loaded.emit(False, "", {})
        return False

    def _validate_and_load_json(self, filepath: str) -> bool:
        """Validate file exists and load JSON data.

        Args:
            filepath: Path to the project file.

        Returns:
            True if successful, False otherwise.
        """
        fp = Path(filepath)
        if not fp.exists() or not fp.is_file():
            logging.error(f"File not found: {filepath}")
            self.error_occurred.emit(f"File not found: {filepath}")
            self.project_data_loaded.emit(False, "", {})
            return False

        self._project_dir = fp.parent

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        self._validated_project_data = PydanticProjectFileModel.model_validate(data)
        return True

    def _process_character_parts(self) -> None:
        """Process character parts and calculate bounding box."""
        all_part_rects: list[QRectF] = []
        parsed_parts: dict[str, PartInfo] = {}

        if (
            self._validated_project_data
            and self._validated_project_data.character
            and self._validated_project_data.character.parts
        ):
            for (
                part_name,
                pydantic_part_model,
            ) in self._validated_project_data.character.parts.items():
                runtime_part = PartInfo.from_pydantic(
                    pydantic_part_model, project_dir=self._project_dir
                )
                parsed_parts[part_name] = runtime_part

                if runtime_part.roi:
                    all_part_rects.append(
                        QRectF(
                            runtime_part.roi[0],
                            runtime_part.roi[1],
                            runtime_part.roi[2],
                            runtime_part.roi[3],
                        )
                    )

        self._parts = parsed_parts
        self._effective_bounding_box_offset = self._calculate_bounding_box_offset(all_part_rects)

    def _calculate_bounding_box_offset(self, part_rects: list[QRectF]) -> QPointF:
        """Calculate the bounding box offset from part rectangles.

        Args:
            part_rects: List of part bounding rectangles.

        Returns:
            The negative center of the overall bounding box, or origin if empty.
        """
        if not part_rects:
            return QPointF(0, 0)

        overall_bounds = QRectF()
        for rect in part_rects:
            overall_bounds = overall_bounds.united(rect)
        return -overall_bounds.center()

    def _log_load_success(self) -> None:
        """Log successful project load information."""
        num_parts = len(self._parts)
        num_joints = 0
        if self._validated_project_data and self._validated_project_data.character:
            skeleton_joints = self._validated_project_data.character.skeleton_joints
            if skeleton_joints:
                num_joints = len(skeleton_joints)

        logging.info(
            f"ProjectDataManager: Successfully validated {num_parts} parts. Project dir: {self._project_dir}"
        )
        if num_joints > 0:
            logging.info(f"ProjectDataManager: Validated {num_joints} skeleton joints.")

    def _handle_validation_error(self, filepath: str, ve: ValidationError) -> None:
        """Handle Pydantic validation errors."""
        logging.error(
            f"ProjectDataManager: Pydantic validation error in {filepath}. {ve}", exc_info=True
        )
        self.error_occurred.emit(f"Invalid project file format: {ve.errors()}")

    def _handle_json_error(self, filepath: str, je: json.JSONDecodeError) -> None:
        """Handle JSON decode errors."""
        logging.error(f"ProjectDataManager: Invalid JSON in {filepath}. {je}", exc_info=True)
        self.error_occurred.emit(f"Invalid JSON file: {je.msg}")

    def _handle_generic_error(self, filepath: str, e: Exception) -> None:
        """Handle generic errors during project load."""
        logging.error(
            f"ProjectDataManager: Error loading project from {filepath}: {e}", exc_info=True
        )
        self.error_occurred.emit(f"Failed to load project: {e}")

    def _try_load_supplemental_skeleton_data(self) -> None:
        """
        Attempts to load skeleton data from char_cfg.yaml if not found or empty
        in the primary project data (e.g., parts_info.json).
        Updates self._validated_project_data.character.skeleton_joints.
        """
        if not self._should_load_supplemental_skeleton():
            return

        char_cfg_path = self._project_dir / "char_cfg.yaml"
        if not char_cfg_path.exists():
            logging.info(
                f"char_cfg.yaml not found at {char_cfg_path}, no supplemental skeleton to load."
            )
            return

        logging.info(f"Attempting to load supplemental skeleton data from {char_cfg_path}")
        self._load_skeleton_from_yaml(char_cfg_path)

    def _should_load_supplemental_skeleton(self) -> bool:
        """Check if supplemental skeleton data should be loaded.

        Returns:
            True if supplemental load should proceed, False otherwise.
        """
        if not self._project_dir or not self._validated_project_data:
            logging.debug(
                "Project dir or validated data not available for supplemental skeleton load."
            )
            return False

        if not self._validated_project_data.character:
            logging.debug("Character data not available for supplemental skeleton load.")
            return False

        # Check if skeleton data is already populated
        existing_joints = self._validated_project_data.character.skeleton_joints
        if existing_joints and len(existing_joints) > 0:
            logging.info(
                "Skeleton data already present in main project file. Skipping supplemental load."
            )
            return False

        return True

    def _load_skeleton_from_yaml(self, char_cfg_path: Path) -> None:
        """Load skeleton data from a char_cfg.yaml file.

        Args:
            char_cfg_path: Path to the char_cfg.yaml file.
        """
        try:
            with open(char_cfg_path, encoding="utf-8") as f:
                char_cfg_data = yaml.safe_load(f)

            skeleton_list = self._extract_skeleton_list(char_cfg_data, char_cfg_path)
            if skeleton_list is None:
                return

            pydantic_joints = self._parse_yaml_joints(skeleton_list)
            self._apply_parsed_joints(pydantic_joints, char_cfg_path)

        except yaml.YAMLError as ye:
            logging.error(f"Error parsing YAML from {char_cfg_path}: {ye}", exc_info=True)
        except Exception as e:
            logging.error(
                f"Unexpected error loading supplemental skeleton from {char_cfg_path}: {e}",
                exc_info=True,
            )

    def _extract_skeleton_list(
        self, char_cfg_data: dict[str, Any] | None, char_cfg_path: Path
    ) -> list[dict[str, Any]] | None:
        """Extract and validate the skeleton list from char_cfg data.

        Args:
            char_cfg_data: Parsed YAML data.
            char_cfg_path: Path for logging.

        Returns:
            The skeleton list if valid, None otherwise.
        """
        if not char_cfg_data or "skeleton" not in char_cfg_data:
            logging.warning(f"Missing 'skeleton' key in {char_cfg_path}.")
            return None

        skeleton = char_cfg_data["skeleton"]
        if isinstance(skeleton, list):
            return skeleton

        # Some pipelines emit a standardized structure:
        # skeleton: {joints: {id -> {name, position/loc, parent_id/parent}}, hierarchy: {...}}
        # Normalize that into the list form expected by the existing YAML joint parser.
        if isinstance(skeleton, dict):
            joints_payload = skeleton.get("joints", {})
            if not isinstance(joints_payload, dict):
                logging.warning(f"Invalid 'skeleton.joints' (not a dict) in {char_cfg_path}.")
                return None

            normalized: list[dict[str, Any]] = []
            for joint_id, joint_data in joints_payload.items():
                if not isinstance(joint_data, dict):
                    continue

                joint_name = joint_data.get("name") or joint_data.get("id") or str(joint_id)
                loc = (
                    joint_data.get("loc")
                    or joint_data.get("coordinates")
                    or joint_data.get("position")
                )
                parent = joint_data.get("parent")
                if parent is None:
                    parent = joint_data.get("parent_id")

                if not isinstance(loc, list | tuple) or len(loc) != 2:
                    continue

                normalized.append(
                    {
                        "name": str(joint_name),
                        "parent": str(parent) if parent is not None else None,
                        "loc": [float(loc[0]), float(loc[1])],
                    }
                )

            if normalized:
                logging.info(
                    "Normalized %d joints from standardized char_cfg skeleton in %s",
                    len(normalized),
                    char_cfg_path,
                )
                return normalized

            logging.warning(
                f"No valid joints found under standardized 'skeleton.joints' in {char_cfg_path}."
            )
            return None

        logging.warning(f"Invalid 'skeleton' (unsupported type) in {char_cfg_path}.")
        return None

    def _parse_yaml_joints(
        self, joints_raw: list[dict[str, Any]]
    ) -> list[PydanticSkeletonJointModel]:
        """Parse raw joint data into Pydantic models.

        Args:
            joints_raw: Raw joint data from YAML.

        Returns:
            List of validated PydanticSkeletonJointModel instances.
        """
        pydantic_joints: list[PydanticSkeletonJointModel] = []

        for joint_data in joints_raw:
            parsed = self._parse_single_yaml_joint(joint_data)
            if parsed:
                pydantic_joints.append(parsed)

        return pydantic_joints

    def _parse_single_yaml_joint(self, joint_data: Any) -> PydanticSkeletonJointModel | None:
        """Parse a single joint entry from YAML.

        Args:
            joint_data: Raw joint data (should be a dict).

        Returns:
            PydanticSkeletonJointModel if valid, None otherwise.
        """
        if not isinstance(joint_data, dict):
            logging.warning(f"Skipping non-dict joint data in char_cfg.yaml: {joint_data}")
            return None

        joint_name = joint_data.get("name")
        joint_loc = joint_data.get("loc")
        joint_parent = joint_data.get("parent")

        if not joint_name:
            logging.warning(f"Skipping joint with missing name: {joint_data}")
            return None

        if not joint_loc or not (isinstance(joint_loc, list) and len(joint_loc) == 2):
            logging.warning(f"Skipping joint '{joint_name}' with invalid 'loc': {joint_loc}")
            return None

        try:
            adapted_data = {
                "id": joint_name,
                "name": joint_name,
                "position": [float(joint_loc[0]), float(joint_loc[1])],
                "parent": str(joint_parent) if joint_parent is not None else None,
            }
            return PydanticSkeletonJointModel.model_validate(adapted_data)
        except ValidationError as ve:
            logging.warning(f"Validation error for joint: {joint_data}. Error: {ve}")
            return None
        except Exception as e:
            logging.warning(f"Error processing joint: {joint_data}. Error: {e}")
            return None

    def _apply_parsed_joints(
        self, pydantic_joints: list[PydanticSkeletonJointModel], char_cfg_path: Path
    ) -> None:
        """Apply parsed joints to the project data.

        Args:
            pydantic_joints: List of validated joint models.
            char_cfg_path: Path for logging.
        """
        if not pydantic_joints:
            logging.info(f"No valid joints found in {char_cfg_path} to load supplementally.")
            return

        # Validate project data structure before assignment
        if not self._validated_project_data or not self._validated_project_data.character:
            logging.warning(
                f"Cannot apply joints from {char_cfg_path}: project data or character not available."
            )
            return

        self._validated_project_data.character.skeleton_joints = pydantic_joints
        logging.info(f"Successfully loaded {len(pydantic_joints)} joints from {char_cfg_path}.")

    def clear_project_data(self, *, emit_signal: bool = True):
        logging.info("ProjectDataManager: Clearing project data.")
        self._project_dir = None
        self._validated_project_data = None
        self._parts.clear()
        self._raw_skeleton_data = None  # Explicitly clear this
        self._effective_bounding_box_offset = QPointF(0, 0)
        if emit_signal:
            self.project_data_cleared.emit()

    def get_all_parts(self) -> dict[str, PartInfo]:
        return self.parts

    def clear_all_motion_paths(self) -> None:
        if not self._parts:
            logging.info("ProjectDataManager: No parts loaded to clear motion paths from.")
            return
        cleared_count = 0
        for part_info in self._parts.values():  # Iterate through runtime PartInfo
            path_cleared = False
            if hasattr(part_info, "motion_path_data") and part_info.motion_path_data is not None:
                part_info.motion_path_data = None  # Clear QPainterPath
                path_cleared = True
            # If PartInfoModel was also stored and needed update, do it here. But primarily runtime PartInfo.
            if path_cleared:
                cleared_count += 1
        if cleared_count > 0:
            logging.info(f"ProjectDataManager: Cleared motion paths for {cleared_count} parts.")
        else:
            logging.info("ProjectDataManager: No motion paths found to clear.")

    def get_current_parts_data(self) -> dict[str, PartInfo] | None:
        if self._parts:
            return self._parts.copy()
        return None

    # --- Methods for project saving (to be implemented using Pydantic models) ---
    def save_project_to_file(self, filepath: str) -> bool:
        logging.info(f"ProjectDataManager: Attempting to save project to: {filepath}")
        message = (
            "Legacy ProjectDataManager direct save is disabled because it cannot "
            "guarantee a complete runtime snapshot. Use the MotionSmith .automataii "
            "project save path instead."
        )
        logging.warning(message)
        self.error_occurred.emit(message)
        return False

    # Methods for MainWindow to call for dialogs
    # self.project_newed_signal.emit() # Or reuse project_data_cleared

    def load_project_dialog(self):
        from PyQt6.QtWidgets import QFileDialog  # Local import

        start_dir = str(self._project_dir) if self._project_dir else os.path.expanduser("~")
        filepath, _ = QFileDialog.getOpenFileName(
            None,  # Parent can be None for a static method or if no obvious parent
            "Load Project File",
            start_dir,
            "JSON files (*.json);;All files (*)",
        )
        if filepath:
            self.load_project_from_file(filepath)

    def save_project_dialog(self):
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

        start_dir = str(self._project_dir) if self._project_dir else os.path.expanduser("~")
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
    from ..utils.paths import get_project_root

    project_root = get_project_root()
    dummy_filepath = project_root / "dummy_project_pydantic.json"
    with open(dummy_filepath, "w") as f:
        json.dump(dummy_parts_info_content, f, indent=4)

    # Test with an invalid file (e.g. missing character key)
    invalid_dummy_content = {"char": {}}
    invalid_filepath = project_root / "invalid_project_pydantic.json"
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
        save_test_path = project_root / "dummy_project_pydantic_saved.json"
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
    print("Pydantic test dummy files removed or were not created.")
