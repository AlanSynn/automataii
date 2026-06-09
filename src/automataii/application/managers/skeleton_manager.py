"""
SkeletonManager module for managing skeleton data and conversions.
"""

import logging
import math  # For calculating limb lengths if needed
from typing import Any

from pydantic import ValidationError
from PyQt6.QtCore import QObject, pyqtSignal

# Import the new standardized models
from automataii.domain.skeleton import StandardizedJointModel, StandardizedSkeletonModel

# Define a structure for standardized joint info if needed, or use Dicts for now
# For example:
# @dataclass
# class Joint:
#     id: str
#     name: str
#     position: QPointF # or Tuple[float, float]
#     parent_id: Optional[str] = None
#     children_ids: List[str] = field(default_factory=list)


class SkeletonManager(QObject):
    """
    Manages skeleton data, including loading, processing, and providing access.
    Handles conversion from different formats (e.g., Animated Drawings) to a standard format.
    Internally uses StandardizedSkeletonModel.
    """

    skeleton_updated = pyqtSignal(dict)  # Emits the new standardized skeleton data as a dict
    error_occurred = pyqtSignal(str)  # Emits an error message
    skeleton_data_cleared = pyqtSignal()  # Emits when skeleton data is cleared

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._raw_input_skeleton_data: dict[str, Any] | None = (
            None  # Store the original input dict if needed for reprocessing
        )
        self._standardized_skeleton_model: StandardizedSkeletonModel | None = None
        logging.info("SkeletonManager initialized with new standardized models.")

    @property
    def standardized_model(self) -> StandardizedSkeletonModel | None:
        """Returns the current StandardizedSkeletonModel instance."""
        return self._standardized_skeleton_model

    @property
    def joint_positions(self) -> dict[str, tuple[float, float]]:
        """Returns a dictionary of joint ID to (x,y) position from the standardized model."""
        if not self._standardized_skeleton_model:
            return {}
        return {
            joint_id: joint.position
            for joint_id, joint in self._standardized_skeleton_model.joints.items()
        }

    def load_skeleton_from_dict(
        self, data: dict[str, Any] | None, source_format: str = "auto"
    ) -> bool:
        """
        Loads skeleton data from a dictionary, converting it to StandardizedSkeletonModel.

        Args:
            data: The dictionary containing skeleton data.
            source_format: 'auto', 'animated_drawings', or 'standard'.
                           If 'auto', tries to detect format.
        Returns:
            True if loading and processing were successful, False otherwise.
        """
        # Start fresh without emitting transient "empty skeleton" updates.
        self.clear_data(emit_signals=False)
        if not data or not isinstance(data, dict):
            logging.warning("SkeletonManager: No data provided or data is not a dictionary.")
            self.clear_data()
            return False

        self._raw_input_skeleton_data = data  # Store the input
        logging.info(
            f"SkeletonManager: Loading skeleton from dict. Source format hint: {source_format}"
        )

        processed_model: StandardizedSkeletonModel | None = None
        detected_format = source_format

        if source_format == "animated_drawings" or (
            source_format == "auto" and self._is_animated_drawings_format(data)
        ):
            logging.info(
                "SkeletonManager: Detected Animated Drawings format based on hint or content."
            )
            detected_format = "animated_drawings"
            processed_model = self._process_animated_drawings_format(data)
        elif source_format == "standard" or (
            source_format == "auto" and self._is_already_standardized_format(data)
        ):
            logging.info("SkeletonManager: Detected Standardized format based on hint or content.")
            detected_format = "standard"
            processed_model = self._process_already_standardized_format(data)
        else:  # Fallback or if auto-detection failed and no clear format
            logging.warning(
                f"SkeletonManager: Unknown source format '{source_format}'. Attempting to process as Animated Drawings, then as Standard."
            )
            # Try Animated Drawings first as it's more common for raw input
            processed_model = self._process_animated_drawings_format(data)
            if processed_model:
                detected_format = "animated_drawings"
            else:  # If AD processing failed, try standard
                logging.info(
                    "SkeletonManager: Animated Drawings processing failed, trying as Standardized format."
                )
                processed_model = self._process_already_standardized_format(data)
                if processed_model:
                    detected_format = "standard"

        if processed_model:
            self._standardized_skeleton_model = processed_model
            self._standardized_skeleton_model.source_format = detected_format
            logging.info(
                f"SkeletonManager: Skeleton data processed successfully as {detected_format}."
            )
            self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
            return True
        else:
            logging.error("SkeletonManager: Failed to process skeleton data into any known format.")
            self.clear_data()  # clear_data emits its own signals
            self.error_occurred.emit(
                "Failed to process skeleton data (unknown format or invalid content)."
            )
            return False

    def load_skeleton_from_project_data(
        self,
        raw_skeleton_list: list[dict[str, Any]] | None,
        parts_data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Loads skeleton data from a raw list of joint dictionaries (e.g., from ProjectDataManager's
        parsed PydanticCharacterDataModel.skeleton_joints) and converts to StandardizedSkeletonModel.

        Args:
            raw_skeleton_list: A list of dictionaries, where each dictionary defines a joint.
                               Expected to be in a format similar to Animated Drawings' 'skeleton' list
                               or PydanticSkeletonJointModel.model_dump() output.
            parts_data: Optional dictionary of PartInfo objects/data. Currently used for context like limb lengths.

        Returns:
            True if loading and processing were successful, False otherwise.
        """
        logging.info(
            f"SkeletonManager: Attempting to load skeleton from project data list (joint count: {len(raw_skeleton_list) if raw_skeleton_list else 0})."
        )
        if not raw_skeleton_list:
            logging.info(
                "SkeletonManager: No raw skeleton list provided from project data. Clearing existing skeleton data."
            )
            self.clear_data()
            # self.skeleton_updated.emit({}) # Emitted by clear_data
            return True  # Successfully cleared/processed empty list

        # The _process_animated_drawings_format expects a dict like: {"skeleton": [...]}
        # It can also derive some limb lengths from parts_data if available.
        wrapper_dict: dict[str, Any] = {"skeleton": raw_skeleton_list}
        if parts_data:
            wrapper_dict["parts_data_for_limb_lengths"] = parts_data

        # This data typically comes from a parsed parts_info.json or char_cfg.yaml,
        # so it's likely 'animated_drawings' or a structure very close to it.
        return self.load_skeleton_from_dict(wrapper_dict, source_format="animated_drawings")

    def clear_data(self, *, emit_signals: bool = True) -> None:
        """Clears all internal skeleton data and emits relevant signals."""
        logging.info("SkeletonManager: Clearing all internal skeleton data.")
        self._raw_input_skeleton_data = None
        self._standardized_skeleton_model = None
        if emit_signals:
            self.skeleton_data_cleared.emit()
            self.skeleton_updated.emit({})  # Emit empty dict to signal state change to empty

    def _is_animated_drawings_format(self, data: dict[str, Any]) -> bool:
        """Checks if the provided data dictionary matches the Animated Drawings char_cfg.yaml structure."""
        if "skeleton" in data and isinstance(data["skeleton"], list):
            if not data["skeleton"]:
                return True  # Empty skeleton list is still valid AD format
            first_joint = data["skeleton"][0]
            if isinstance(first_joint, dict):
                # Common keys: 'name', 'parent', and either 'coordinates' or 'loc'
                return (
                    "name" in first_joint
                    and "parent" in first_joint
                    and ("coordinates" in first_joint or "loc" in first_joint)
                )
        return False

    def _is_already_standardized_format(self, data: dict[str, Any]) -> bool:
        """Checks if data is already in our target StandardizedSkeletonModel format (or close to it)."""
        # Check for key fields of StandardizedSkeletonModel
        if (
            "joints" in data
            and isinstance(data["joints"], dict)
            and "root_joint_ids" in data
            and isinstance(data["root_joint_ids"], list)
            and "hierarchy" in data
            and isinstance(data["hierarchy"], dict)
        ):
            if not data["joints"]:
                return True  # Valid empty standardized model

            # Check first joint if available
            first_joint_id = next(iter(data["joints"]), None)
            if first_joint_id:
                first_joint_data = data["joints"][first_joint_id]
                if (
                    isinstance(first_joint_data, dict)
                    and "id" in first_joint_data
                    and "name" in first_joint_data
                    and "position" in first_joint_data
                ):
                    return True
        return False

    def _process_animated_drawings_format(
        self, data: dict[str, Any]
    ) -> StandardizedSkeletonModel | None:
        """
        Processes skeleton data from the Animated Drawings format.
        Refactored to reduce cyclomatic complexity.
        """
        raw_joints_list = data.get("skeleton", [])
        if not isinstance(raw_joints_list, list):
            logging.warning("Animated Drawings format: 'skeleton' key is not a list or is missing.")
            return None

        std_skeleton = StandardizedSkeletonModel(source_format="animated_drawings")
        name_to_id: dict[str, str] = {}
        id_to_parent: dict[str, str | None] = {}

        # First pass: Create joint models
        for i, joint_raw in enumerate(raw_joints_list):
            result = self._process_single_ad_joint(joint_raw, i, std_skeleton)
            if result:
                joint_id, joint_name, parent_name = result
                name_to_id[joint_name] = joint_id
                id_to_parent[joint_id] = parent_name

        # Second pass: Resolve hierarchy
        self._resolve_ad_hierarchy(std_skeleton, name_to_id, id_to_parent)

        # Calculate limb lengths
        self._calculate_ad_limb_lengths(std_skeleton, data)

        if not std_skeleton.joints:
            logging.warning("No valid joints processed from Animated Drawings format.")
            return None
        return std_skeleton

    def _process_single_ad_joint(
        self, joint_raw: Any, index: int, skeleton: StandardizedSkeletonModel
    ) -> tuple[str, str, str | None] | None:
        """Process a single joint from Animated Drawings format."""
        if not isinstance(joint_raw, dict):
            logging.warning(f"Skipping non-dict joint entry: {joint_raw}")
            return None

        joint_name = joint_raw.get("name") or joint_raw.get("id")
        parent_name = joint_raw.get("parent")
        coords = joint_raw.get("coordinates") or joint_raw.get("loc") or joint_raw.get("position")

        if not joint_name or coords is None:
            logging.warning(f"Skipping AD joint with missing name or coordinates: {joint_raw}")
            return None

        # Validate coordinates
        position = self._parse_ad_coordinates(coords, joint_name)
        if position is None:
            return None

        # Generate unique ID
        joint_id = self._generate_unique_joint_id(joint_name, index, skeleton.joints)

        # Create joint model
        bend_dir = 1.0 if ("elbow" in joint_name.lower() or "knee" in joint_name.lower()) else None

        std_joint = StandardizedJointModel(
            id=joint_id,
            name=joint_name,
            position=position,
            parent_id=None,
            label=joint_name,
            source_data=joint_raw.copy(),
            is_locked=False,
            bend_direction=bend_dir,
        )
        skeleton.joints[joint_id] = std_joint

        if skeleton.joint_map is not None:
            skeleton.joint_map[joint_name] = joint_id

        # Normalize parent name
        normalized_parent = (
            parent_name if parent_name and str(parent_name).lower() != "none" else None
        )
        return joint_id, joint_name, normalized_parent

    def _parse_ad_coordinates(self, coords: Any, joint_name: str) -> tuple[float, float] | None:
        """Parse and validate coordinates for AD joint."""
        if not isinstance(coords, list) or len(coords) != 2:
            logging.warning(
                f"Skipping AD joint '{joint_name}' due to invalid coordinates: {coords}"
            )
            return None
        try:
            return (float(coords[0]), float(coords[1]))
        except (ValueError, TypeError):
            logging.warning(
                f"Skipping AD joint '{joint_name}' due to non-numeric coordinates: {coords}"
            )
            return None

    def _generate_unique_joint_id(
        self, joint_name: str, index: int, existing_joints: dict[str, Any]
    ) -> str:
        """Generate a unique joint ID."""
        base_id = joint_name.replace(" ", "_").replace(".", "_")
        joint_id = f"{base_id}_{index}"
        while joint_id in existing_joints:
            joint_id += "_dup"
        return joint_id

    def _resolve_ad_hierarchy(
        self,
        skeleton: StandardizedSkeletonModel,
        name_to_id: dict[str, str],
        id_to_parent: dict[str, str | None],
    ) -> None:
        """Resolve parent IDs and build hierarchy."""
        for joint_id, joint_model in skeleton.joints.items():
            parent_name = id_to_parent.get(joint_id)
            if parent_name and parent_name in name_to_id:
                parent_id = name_to_id[parent_name]
                joint_model.parent_id = parent_id
                if skeleton.hierarchy is not None:
                    skeleton.hierarchy.setdefault(parent_id, []).append(joint_id)
            elif skeleton.root_joint_ids is not None:
                skeleton.root_joint_ids.append(joint_id)

    def _calculate_ad_limb_lengths(
        self, skeleton: StandardizedSkeletonModel, data: dict[str, Any]
    ) -> None:
        """Calculate limb lengths from joint positions (only if parts_data provided)."""
        if skeleton.limb_lengths is None:
            return

        # Only calculate if parts_data_for_limb_lengths is provided
        parts_data = data.get("parts_data_for_limb_lengths")
        if not parts_data or not isinstance(parts_data, dict):
            return

        # Calculate from joint distances
        for joint_a in skeleton.joints.values():
            if not joint_a.parent_id or joint_a.parent_id not in skeleton.joints:
                continue
            joint_b = skeleton.joints[joint_a.parent_id]
            dx = joint_a.position[0] - joint_b.position[0]
            dy = joint_a.position[1] - joint_b.position[1]
            length = math.sqrt(dx * dx + dy * dy)
            limb_key = f"{joint_b.name}_to_{joint_a.name}"
            skeleton.limb_lengths[limb_key] = length

        # Add lengths from limb_meta if available
        limb_meta = data.get("limb_meta")
        if isinstance(limb_meta, dict):
            for key, val in limb_meta.items():
                if isinstance(val, int | float):
                    skeleton.limb_lengths[key] = float(val)

    def _process_already_standardized_format(
        self, data: dict[str, Any]
    ) -> StandardizedSkeletonModel | None:
        """
        Processes data that is already expected to be in StandardizedSkeletonModel format.
        Mainly involves validation using Pydantic.
        """
        try:
            model = StandardizedSkeletonModel.model_validate(data)
            # Ensure basic consistency if loaded from raw dict (Pydantic does a lot, but double check hierarchy)
            if (
                not model.hierarchy and model.joints
            ):  # Rebuild hierarchy if missing but joints exist
                for joint_id, joint in model.joints.items():
                    if joint.parent_id and joint.parent_id in model.joints:
                        model.hierarchy.setdefault(joint.parent_id, []).append(joint_id)
                    elif not joint.parent_id:
                        if joint_id not in model.root_joint_ids:
                            model.root_joint_ids.append(joint_id)
            if (
                not model.root_joint_ids
                and model.joints
                and not any(j.parent_id for j in model.joints.values())
            ):
                model.root_joint_ids = list(model.joints.keys())  # All are roots if no parents

            return model
        except ValidationError as ve:
            logging.error(
                f"Data validation failed for StandardizedSkeletonModel format: {ve}",
                exc_info=True,
            )
            self.error_occurred.emit(f"Invalid standardized skeleton data: {ve.errors()}")
            return None
        except Exception as e:
            logging.error(
                f"Unexpected error processing pre-standardized format: {e}",
                exc_info=True,
            )
            self.error_occurred.emit(f"Error processing skeleton: {e}")
            return None

    # --- Getter methods for specific joint information ---
    def get_joint_by_id(self, joint_id: str) -> StandardizedJointModel | None:
        if (
            self._standardized_skeleton_model
            and joint_id in self._standardized_skeleton_model.joints
        ):
            return self._standardized_skeleton_model.joints[joint_id]
        return None

    def get_joint_by_name(self, name: str) -> StandardizedJointModel | None:
        """Gets a joint by its 'name' field. Assumes names are reasonably unique or returns first match."""
        if self._standardized_skeleton_model:
            for joint in self._standardized_skeleton_model.joints.values():
                if joint.name == name:
                    return joint
        return None

    def get_joint_position(self, joint_id_or_name: str) -> tuple[float, float] | None:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        return joint.position if joint else None

    def get_parent_joint(self, joint_id_or_name: str) -> StandardizedJointModel | None:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        if joint and joint.parent_id and self._standardized_skeleton_model:
            return self._standardized_skeleton_model.joints.get(joint.parent_id)
        return None

    def get_child_joints(self, joint_id_or_name: str) -> list[StandardizedJointModel]:
        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        if joint and self._standardized_skeleton_model:
            child_ids = self._standardized_skeleton_model.hierarchy.get(joint.id, [])
            return [
                self._standardized_skeleton_model.joints[child_id]
                for child_id in child_ids
                if child_id in self._standardized_skeleton_model.joints
            ]
        return []

    def get_limb_length(self, descriptive_limb_name: str) -> float | None:
        """Gets a pre-calculated or defined limb length by its descriptive name."""
        if self._standardized_skeleton_model and self._standardized_skeleton_model.limb_lengths:
            length = self._standardized_skeleton_model.limb_lengths.get(descriptive_limb_name)
            return float(length) if length is not None else None
        return None

    def extend_skeleton_lengths(self, scale_factor: float = 1.1) -> bool:
        """Extends all skeleton bone lengths by the given scale factor.

        Args:
            scale_factor: The factor to scale bone lengths by (default 1.1 for 10% increase)

        Returns:
            True if successful, False otherwise
        """
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded to extend")
            return False

        try:
            logging.info(f"Extending skeleton lengths by factor {scale_factor}")

            model = self._standardized_skeleton_model
            processed_joints: set[str] = set()

            # Start scaling from each root
            for root_id in model.root_joint_ids:
                if root_id in model.joints:
                    self._scale_joint_tree(root_id, None, scale_factor, processed_joints, model)

            # Scale all limb lengths (may double-scale some, but ensures consistency)
            self._scale_all_limb_lengths(scale_factor, model)

            # Emit update signal
            self.skeleton_updated.emit(model.model_dump())
            logging.info(f"Successfully extended skeleton lengths by {scale_factor}")
            return True

        except Exception as e:
            logging.error(f"Error extending skeleton lengths: {e}", exc_info=True)
            return False

    def _scale_joint_tree(
        self,
        joint_id: str,
        parent_pos: tuple[float, float] | None,
        scale_factor: float,
        processed_joints: set[str],
        model: StandardizedSkeletonModel,
    ) -> None:
        """Recursively scale joint positions in the skeleton tree.

        Args:
            joint_id: Current joint to process
            parent_pos: Position of the parent joint (None for roots)
            scale_factor: Scale factor to apply
            processed_joints: Set of already processed joint IDs
            model: The skeleton model to modify
        """
        if joint_id in processed_joints:
            return

        processed_joints.add(joint_id)
        joint = model.joints.get(joint_id)
        if not joint:
            return

        # Scale position relative to parent if not a root
        if parent_pos is not None and joint.parent_id:
            self._scale_joint_position(joint, parent_pos, scale_factor, model)

        # Process children recursively
        current_pos = joint.position
        for child_id in model.hierarchy.get(joint_id, []):
            self._scale_joint_tree(child_id, current_pos, scale_factor, processed_joints, model)

    def _scale_joint_position(
        self,
        joint: StandardizedJointModel,
        parent_pos: tuple[float, float],
        scale_factor: float,
        model: StandardizedSkeletonModel,
    ) -> None:
        """Scale a single joint's position relative to its parent.

        Args:
            joint: The joint to scale
            parent_pos: Position of the parent joint
            scale_factor: Scale factor to apply
            model: The skeleton model (for updating limb lengths)
        """
        # Calculate and scale vector from parent
        dx = joint.position[0] - parent_pos[0]
        dy = joint.position[1] - parent_pos[1]
        new_dx = dx * scale_factor
        new_dy = dy * scale_factor

        # Set new position
        joint.position = (parent_pos[0] + new_dx, parent_pos[1] + new_dy)

        # Update limb length if it exists
        self._update_limb_length_for_joint(joint, scale_factor, model)

    def _update_limb_length_for_joint(
        self,
        joint: StandardizedJointModel,
        scale_factor: float,
        model: StandardizedSkeletonModel,
    ) -> None:
        """Update the limb length entry for a joint if it exists.

        Args:
            joint: The joint whose limb length to update
            scale_factor: Scale factor to apply
            model: The skeleton model containing limb lengths
        """
        if not joint.parent_id or not model.limb_lengths:
            return

        parent_joint = model.joints.get(joint.parent_id)
        if not parent_joint:
            return

        limb_key = f"{parent_joint.name}_to_{joint.name}"
        if limb_key in model.limb_lengths:
            model.limb_lengths[limb_key] *= scale_factor

    def _scale_all_limb_lengths(
        self,
        scale_factor: float,
        model: StandardizedSkeletonModel,
    ) -> None:
        """Scale all limb lengths in the model.

        Args:
            scale_factor: Scale factor to apply
            model: The skeleton model containing limb lengths
        """
        if not model.limb_lengths:
            return

        for limb_name in list(model.limb_lengths.keys()):
            model.limb_lengths[limb_name] *= scale_factor

    def lock_joint(self, joint_id_or_name: str, locked: bool = True) -> bool:
        """Locks or unlocks a specific joint for IK solving.

        Args:
            joint_id_or_name: The ID or name of the joint to lock/unlock
            locked: True to lock, False to unlock

        Returns:
            True if successful, False otherwise
        """
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded")
            return False

        joint = self.get_joint_by_id(joint_id_or_name) or self.get_joint_by_name(joint_id_or_name)
        if not joint:
            logging.warning(f"Joint '{joint_id_or_name}' not found")
            return False

        joint.is_locked = locked
        logging.info(f"Joint '{joint.name}' (ID: {joint.id}) {'locked' if locked else 'unlocked'}")

        # Emit update signal
        self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return True

    def get_locked_joints(self) -> list[str]:
        """Returns a list of joint IDs that are currently locked."""
        if not self._standardized_skeleton_model:
            return []

        return [
            joint_id
            for joint_id, joint in self._standardized_skeleton_model.joints.items()
            if joint.is_locked
        ]

    def get_current_skeleton_data(self) -> dict[str, Any] | None:
        """Returns the current skeleton data as a dictionary, or None if no skeleton is loaded."""
        if not self._standardized_skeleton_model:
            return None
        result: dict[str, Any] = self._standardized_skeleton_model.model_dump()
        return result

    def set_joint_bend_direction(self, joint_id: str, direction: float) -> None:
        """
        Set the bend direction for a specific joint.

        Args:
            joint_id: The standardized ID of the joint
            direction: The bend direction (1.0 for default, -1.0 for inverted)
        """
        if not self._standardized_skeleton_model:
            logging.warning(
                f"SkeletonManager: Cannot set bend direction for joint '{joint_id}' - no skeleton loaded"
            )
            return

        if joint_id in self._standardized_skeleton_model.joints:
            self._standardized_skeleton_model.joints[joint_id].bend_direction = direction
            logging.info(
                f"SkeletonManager: Set bend direction for joint '{joint_id}' to {direction}"
            )

            # Emit skeleton updated signal
            self.skeleton_updated.emit(self.get_current_skeleton_data())
        else:
            logging.warning(f"SkeletonManager: Joint '{joint_id}' not found in skeleton model")

    def get_all_joint_bend_directions(self) -> dict[str, float]:
        """
        Get bend directions for all joints.

        Returns:
            Dictionary mapping joint IDs to their bend directions
        """
        if not self._standardized_skeleton_model:
            return {}

        return {
            joint_id: joint.bend_direction
            for joint_id, joint in self._standardized_skeleton_model.joints.items()
        }

    def unlock_all_joints(self) -> bool:
        """Unlocks all joints in the skeleton.

        Returns:
            True if successful, False otherwise
        """
        if not self._standardized_skeleton_model:
            logging.warning("No skeleton model loaded")
            return False

        for joint in self._standardized_skeleton_model.joints.values():
            joint.is_locked = False

        logging.info("All joints unlocked")
        self.skeleton_updated.emit(self._standardized_skeleton_model.model_dump())
        return True


if __name__ == "__main__":
    # Example Usage
    logging.basicConfig(level=logging.INFO)
    manager = SkeletonManager()

    # Example 1: Animated Drawings Format
    ad_skeleton_data = {
        "skeleton": [
            {"name": "hip", "parent": None, "coordinates": [0, 0]},
            {"name": "neck", "parent": "hip", "coordinates": [0, 50]},
            {
                "name": "head",
                "parent": "neck",
                "coordinates": [0, 70],
                "label_AD": "actual_head_part",
            },
            {"name": "left_shoulder", "parent": "neck", "coordinates": [-20, 50]},
            {"name": "left_elbow", "parent": "left_shoulder", "coordinates": [-40, 50]},
        ],
        "limb_meta": {  # Example of how Animated Drawings might store some lengths
            "head_limb": 20.0,
            "left_upper_arm_limb": 25.0,
        },
    }
    print("\n--- Loading Animated Drawings Skeleton ---")
    if manager.load_skeleton_from_dict(ad_skeleton_data):
        print("Successfully loaded AD skeleton.")
        if manager.standardized_model:
            print(f"  Model Source Format: {manager.standardized_model.source_format}")
            print(f"  Root joint IDs: {manager.standardized_model.root_joint_ids}")
            hip_joint = manager.get_joint_by_name("hip")
            if hip_joint:
                print(f"  Hip joint position: {hip_joint.position}")
                print(
                    f"  Children of hip: {[child.name for child in manager.get_child_joints(hip_joint.id)]}"
                )
            head_joint = manager.get_joint_by_name("head")
            if head_joint:
                print(f"  Head joint label from AD: {head_joint.label}")  # Should be 'head'
                print(
                    f"  Head parent: {manager.get_parent_joint(head_joint.id).name if manager.get_parent_joint(head_joint.id) else 'None'}"
                )
            # Test limb lengths
            print(f"  Limb length 'hip_to_neck': {manager.get_limb_length('hip_to_neck')}")
            print(
                f"  Limb length from limb_meta 'head_limb': {manager.get_limb_length('head_limb')}"
            )

    else:
        print("Failed to load AD skeleton.")

    # Example 2: Simulate loading data that's already standardized
    # (e.g. from a file saved by this manager previously)
    if manager.standardized_model:
        standard_data_to_simulate_load = manager.standardized_model.model_dump()
        print("\n--- Loading Already Standardized Skeleton (from previous AD load) ---")
        new_manager = SkeletonManager()  # Use a new manager
        if new_manager.load_skeleton_from_dict(
            standard_data_to_simulate_load, source_format="standard"
        ):
            print("Successfully loaded standard skeleton.")
            if new_manager.standardized_model:
                print(f"  Root joint IDs: {new_manager.standardized_model.root_joint_ids}")
                neck_joint = new_manager.get_joint_by_name("neck")
                if neck_joint:
                    print(f"  Neck position: {neck_joint.position}")
        else:
            print("Failed to load standard skeleton.")

    # Example 3: Invalid/Empty Data
    print("\n--- Loading Empty Skeleton (None) ---")
    if not manager.load_skeleton_from_dict(None):
        print("Correctly handled Noneskeleton data.")

    print("\n--- Loading Empty Skeleton (empty dict) ---")
    if not manager.load_skeleton_from_dict(
        {}
    ):  # This might be treated as invalid rather than empty
        print("Correctly handled empty dict as invalid or unprocessable.")

    print("\n--- Loading Empty AD Skeleton (skeleton: []) ---")
    empty_ad = {"skeleton": []}
    if manager.load_skeleton_from_dict(empty_ad, source_format="animated_drawings"):
        print("Successfully loaded empty AD skeleton.")
        if manager.standardized_model:
            print(f"  Joint count: {len(manager.standardized_model.joints)}")
    else:
        print("Failed to load empty AD skeleton.")

    def handle_skel_update(new_skel_dict: dict):
        print("\n--- skeleton_updated SIGNAL received (dict representation): ---")
        # print(new_skel_dict)
        if new_skel_dict and "root_joint_ids" in new_skel_dict:
            print(f"Signal: Root joint IDs from dict: {new_skel_dict['root_joint_ids']}")
        # To access full model data, the receiver would typically call manager.standardized_model
        # Or, if the dict is complete, deserialize it: StandardizedSkeletonModel.model_validate(new_skel_dict)
        current_model = manager.standardized_model  # Accessing via the manager instance
        if current_model:
            print(
                f"Signal: Neck position from manager model: {current_model.joints.get(current_model.joint_map.get('neck')).position if current_model.joint_map and current_model.joint_map.get('neck') in current_model.joints else 'N/A'}"
            )

    manager.skeleton_updated.connect(handle_skel_update)
    print("\n--- Re-Loading Animated Drawings Skeleton to trigger signal ---")
    manager.load_skeleton_from_dict(ad_skeleton_data)

    # Test get functions with non-existent joint
    print("\n--- Testing non-existent joint ---")
    print(
        "Position of 'non_existent_joint':",
        manager.get_joint_position("non_existent_joint"),
    )
    print(
        "Parent of 'non_existent_joint':",
        manager.get_parent_joint("non_existent_joint"),
    )
    print(
        "Children of 'non_existent_joint':",
        manager.get_child_joints("non_existent_joint"),
    )

    # Test loading project data (list of dicts)
    project_skeleton_list = [
        {
            "id": "proj_hip",
            "name": "Hip",
            "position": [10, 10],
            "parent": None,
        },  # Pydantic model's .model_dump() output
        {
            "id": "proj_spine",
            "name": "Spine",
            "position": [10, 60],
            "parent_id": "proj_hip",
        },  # Note: key used 'parent_id' vs 'parent'
    ]
    # To align with AD processing, it expects 'name', 'parent', 'coordinates'
    # So, this direct list might need adjustment or the processor needs to be more flexible.
    # For _process_animated_drawings_format, it would be:
    project_skeleton_list_for_ad_style = [
        {
            "name": "ProjectHip",
            "parent": None,
            "coordinates": [10, 10],
            "source_id": "proj_hip",
        },
        {
            "name": "ProjectSpine",
            "parent": "ProjectHip",
            "coordinates": [10, 60],
            "source_id": "proj_spine",
        },
    ]

    print("\n--- Loading Skeleton from Project Data (AD-style list) ---")
    if manager.load_skeleton_from_project_data(project_skeleton_list_for_ad_style):
        print("Successfully loaded skeleton from project data list.")
        if manager.standardized_model:
            print(f"  Root joint ID from project data: {manager.standardized_model.root_joint_ids}")
            spine_joint = manager.get_joint_by_name("ProjectSpine")
            if spine_joint:
                print(f"  ProjectSpine position: {spine_joint.position}")
                print(
                    f"  ProjectSpine original source_id: {spine_joint.source_data.get('source_id') if spine_joint.source_data else 'N/A'}"
                )
    else:
        print("Failed to load skeleton from project data list.")
