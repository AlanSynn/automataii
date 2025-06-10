"""
Skeleton format detection and conversion module.

Handles conversion from various skeleton formats to the standardized format.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple

from pydantic import ValidationError

from .models import StandardizedJointModel, StandardizedSkeletonModel


class SkeletonFormatConverter:
    """Handles detection and conversion of skeleton data from various formats."""

    @staticmethod
    def detect_format(data: Dict[str, Any]) -> Optional[str]:
        """
        Detects the format of the provided skeleton data.

        Args:
            data: The skeleton data dictionary

        Returns:
            Format string ('animated_drawings', 'standard') or None if unknown
        """
        if SkeletonFormatConverter._is_animated_drawings_format(data):
            return "animated_drawings"
        elif SkeletonFormatConverter._is_already_standardized_format(data):
            return "standard"
        return None

    @staticmethod
    def _is_animated_drawings_format(data: Dict[str, Any]) -> bool:
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

    @staticmethod
    def _is_already_standardized_format(data: Dict[str, Any]) -> bool:
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

    @staticmethod
    def convert_from_dict(
        data: Dict[str, Any], source_format: str = "auto"
    ) -> Optional[StandardizedSkeletonModel]:
        """
        Converts skeleton data from a dictionary to StandardizedSkeletonModel.

        Args:
            data: The dictionary containing skeleton data
            source_format: 'auto', 'animated_drawings', or 'standard'

        Returns:
            StandardizedSkeletonModel instance or None if conversion failed
        """
        if not data or not isinstance(data, dict):
            logging.warning("No data provided or data is not a dictionary.")
            return None

        detected_format = source_format
        if source_format == "auto":
            detected_format = SkeletonFormatConverter.detect_format(data)
            if not detected_format:
                logging.warning("Could not auto-detect skeleton format.")
                # Try formats in order of likelihood
                for fmt in ["animated_drawings", "standard"]:
                    result = SkeletonFormatConverter._try_format(data, fmt)
                    if result:
                        return result
                return None

        if detected_format == "animated_drawings":
            return SkeletonFormatConverter._process_animated_drawings_format(data)
        elif detected_format == "standard":
            return SkeletonFormatConverter._process_already_standardized_format(data)
        else:
            logging.warning(f"Unknown source format '{source_format}'.")
            return None

    @staticmethod
    def _try_format(data: Dict[str, Any], format_type: str) -> Optional[StandardizedSkeletonModel]:
        """Try to process data as a specific format."""
        try:
            if format_type == "animated_drawings":
                return SkeletonFormatConverter._process_animated_drawings_format(data)
            elif format_type == "standard":
                return SkeletonFormatConverter._process_already_standardized_format(data)
        except Exception as e:
            logging.debug(f"Failed to process as {format_type}: {e}")
        return None

    @staticmethod
    def _process_animated_drawings_format(
        data: Dict[str, Any]
    ) -> Optional[StandardizedSkeletonModel]:
        """
        Processes skeleton data from the Animated Drawings format (e.g., char_cfg.yaml content).
        Populates and returns a StandardizedSkeletonModel.
        """
        raw_joints_list = data.get("skeleton", [])
        if not isinstance(raw_joints_list, list):
            # The data itself might be the list of joints.
            if isinstance(data, list):
                raw_joints_list = data
            else:
                logging.warning(
                    "Animated Drawings format: 'skeleton' key is not a list or is missing."
                )
                return None

        std_skeleton = StandardizedSkeletonModel(source_format="animated_drawings")
        temp_joint_name_to_id: Dict[str, str] = {}
        temp_id_to_parent_name: Dict[str, Optional[str]] = {}

        for i, joint_info_raw in enumerate(raw_joints_list):
            if not isinstance(joint_info_raw, dict):
                logging.warning(
                    f"Skipping non-dict joint entry in Animated Drawings skeleton: {joint_info_raw}"
                )
                continue

            joint_name = joint_info_raw.get("name")
            parent_name = joint_info_raw.get("parent")
            coords = joint_info_raw.get("coordinates") or joint_info_raw.get("loc")

            if coords is None and "position" in joint_info_raw:
                coords = joint_info_raw["position"]

            if not joint_name and "id" in joint_info_raw:
                joint_name = joint_info_raw["id"]

            if not joint_name or coords is None:
                logging.warning(
                    f"Skipping AD joint with missing name or coordinates: {joint_info_raw}"
                )
                continue

            unique_id_base = joint_name.replace(" ", "_").replace(".", "_")
            joint_id = f"{unique_id_base}_{i}"
            while joint_id in std_skeleton.joints:
                joint_id += "_dup"

            if not isinstance(coords, list) or len(coords) != 2:
                logging.warning(
                    f"Skipping AD joint '{joint_name}' due to invalid coordinates: {coords}"
                )
                continue

            try:
                position_tuple = (float(coords[0]), float(coords[1]))
            except (ValueError, TypeError):
                logging.warning(
                    f"Skipping AD joint '{joint_name}' due to non-numeric coordinates: {coords}"
                )
                continue

            std_joint = StandardizedJointModel(
                id=joint_id,
                name=joint_name,
                position=position_tuple,
                parent_id=None,
                label=joint_name,
                source_data=joint_info_raw.copy(),
                is_locked=False,
            )
            std_skeleton.joints[joint_id] = std_joint
            temp_joint_name_to_id[joint_name] = joint_id
            temp_id_to_parent_name[joint_id] = (
                parent_name
                if parent_name and str(parent_name).lower() != "none"
                else None
            )

            if std_skeleton.joint_map is not None:
                std_skeleton.joint_map[joint_name] = joint_id

        # Second pass: Resolve parent_ids and build hierarchy
        for joint_id, joint_model in std_skeleton.joints.items():
            parent_name = temp_id_to_parent_name.get(joint_id)
            if parent_name and parent_name in temp_joint_name_to_id:
                parent_id = temp_joint_name_to_id[parent_name]
                joint_model.parent_id = parent_id
                if std_skeleton.hierarchy is not None:
                    std_skeleton.hierarchy.setdefault(parent_id, []).append(joint_id)
            else:
                if std_skeleton.root_joint_ids is not None:
                    std_skeleton.root_joint_ids.append(joint_id)

        SkeletonFormatConverter._calculate_limb_lengths(std_skeleton, data)

        if not std_skeleton.joints:
            logging.warning("No valid joints processed from Animated Drawings format.")
            return None
        return std_skeleton

    @staticmethod
    def _calculate_limb_lengths(
        skeleton: StandardizedSkeletonModel, data: Dict[str, Any]
    ) -> None:
        """Calculate limb lengths from joint positions and additional data."""
        parts_data_for_lengths = data.get("parts_data_for_limb_lengths")
        if (
            parts_data_for_lengths
            and isinstance(parts_data_for_lengths, dict)
            and skeleton.limb_lengths is not None
        ):
            # Calculate distances between connected joints
            for joint_id_A, joint_A in skeleton.joints.items():
                if joint_A.parent_id and joint_A.parent_id in skeleton.joints:
                    joint_B = skeleton.joints[joint_A.parent_id]
                    dx = joint_A.position[0] - joint_B.position[0]
                    dy = joint_A.position[1] - joint_B.position[1]
                    length = math.sqrt(dx * dx + dy * dy)
                    # Try to find a descriptive name for this limb (e.g., parent_name-child_name)
                    limb_name_key = f"{joint_B.name}_to_{joint_A.name}"
                    skeleton.limb_lengths[limb_name_key] = length
                    # More sophisticated: Check 'limb_meta' if present in original 'data' from char_cfg
                    if "limb_meta" in data and isinstance(data["limb_meta"], dict):
                        for lm_key, lm_val in data["limb_meta"].items():
                            if isinstance(
                                lm_val, (int, float)
                            ):  # limb_meta often contains lengths directly
                                skeleton.limb_lengths[lm_key] = float(lm_val)

    @staticmethod
    def _process_already_standardized_format(
        data: Dict[str, Any]
    ) -> Optional[StandardizedSkeletonModel]:
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
                model.root_joint_ids = list(
                    model.joints.keys()
                )  # All are roots if no parents

            return model
        except ValidationError as ve:
            logging.error(
                f"Data validation failed for StandardizedSkeletonModel format: {ve}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logging.error(
                f"Unexpected error processing pre-standardized format: {e}",
                exc_info=True,
            )
            return None

    @staticmethod
    def convert_from_project_data(
        raw_skeleton_list: List[Dict[str, Any]],
        parts_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[StandardizedSkeletonModel]:
        """
        Converts skeleton data from a raw list of joint dictionaries.

        Args:
            raw_skeleton_list: A list of dictionaries, where each dictionary defines a joint
            parts_data: Optional dictionary of PartInfo objects/data

        Returns:
            StandardizedSkeletonModel instance or None if conversion failed
        """
        if not raw_skeleton_list:
            return StandardizedSkeletonModel()  # Return empty model

        # The _process_animated_drawings_format expects a dict like: {"skeleton": [...]}
        wrapper_dict = {"skeleton": raw_skeleton_list}
        if parts_data:
            wrapper_dict["parts_data_for_limb_lengths"] = parts_data

        return SkeletonFormatConverter.convert_from_dict(
            wrapper_dict, source_format="animated_drawings"
        )