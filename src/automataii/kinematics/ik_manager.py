"""
Inverse Kinematics (IK) Manager for Automataii.

This class will handle the logic and data related to the IK system,
including skeleton definition for IK, solving IK for limbs, and managing
IK-driven animation state.
"""

import inspect
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from PyQt6.QtCore import QElapsedTimer, QLineF, QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainterPath, QTransform

from automataii.core.models import PartInfo
from automataii.core.models_skeleton import (
    StandardizedJointModel,
    StandardizedSkeletonModel,
)
from automataii.gui.graphics_items.part_item import CharacterPartItem

if TYPE_CHECKING:
    from ..core.skeleton_manager import SkeletonManager


class IKManager(QObject):
    """Manages IK related data, setup, and solving."""

    character_visuals_updated = pyqtSignal(dict)
    animation_state_changed = pyqtSignal(str)
    ik_solver_initialized = pyqtSignal(bool, dict)
    error_occurred = pyqtSignal(str)
    simulation_data_generated = pyqtSignal(dict)
    skeleton_pose_updated = pyqtSignal(dict)

    def __init__(self, main_window_ref, parent: QObject | None = None):
        super().__init__(parent)
        self.main_window = main_window_ref

        self.sim_joints_config: dict[str, dict[str, Any]] = {}
        self.sim_limb_configs: dict[str, dict[str, Any]] = {}
        self.sim_limb_lengths: dict[str, float] = {}
        self.sim_selectable_components: list[dict[str, Any]] = []
        self.sim_two_bone_ik_effectors: list[str] = []
        self.sim_joint_bend_directions: dict[str, int] = {}
        self._sim_dynamic_joints_data: dict[str, dict[str, Any]] = {}
        self.scene_joints_snapshot: dict[str, Any] = {}

        self.ik_part_to_actual_part_name: dict[str, str] = {
            "head": "head",
            "torso": "torso",
            "left_upper_arm": "left_arm_upper",
            "left_forearm": "left_arm_lower",
            "right_upper_arm": "right_arm_upper",
            "right_forearm": "right_arm_lower",
            "left_thigh": "left_leg_upper",
            "left_calf": "left_leg_lower",
            "right_thigh": "right_leg_upper",
            "right_calf": "right_leg_lower",
        }

        self.ik_joint_ids_to_source_names: dict[str, str] = {
            "j_neck_base": "hip",
            "j_head_tip": "head",
            "j_left_shoulder": "left_shoulder",
            "j_right_shoulder": "right_shoulder",
            "j_left_hip": "left_hip",
            "j_right_hip": "right_hip",
            "j_left_elbow": "left_elbow",
            "j_left_wrist": "left_hand",
            "j_right_elbow": "right_elbow",
            "j_right_wrist": "right_hand",
            "j_left_knee": "left_knee",
            "j_left_ankle": "left_foot",
            "j_right_knee": "right_knee",
            "j_right_ankle": "right_foot",
        }

        self._active_path_definition_target_joint_id: str | None = None

        self.ik_animation_timer = QTimer(self)
        self.ik_animation_timer.setInterval(30)
        self.ik_animation_timer.timeout.connect(self._run_ik_animation_step)

        self.ik_animation_speed: float = 0.5
        self.animation_duration: int = 3000
        self._animation_start_time_qelapsed: QElapsedTimer | None = None
        self._current_animation_progress: float = 0.0

        self.skeleton_manager_ref: SkeletonManager | None = None
        self.project_dir: Path | None = None
        self.project_parts_data: dict[str, PartInfo] = {}

        self.__internal_current_skeleton_data: dict[str, Any] | None = None
        self._current_joint_connections: list[tuple[str, str]] | None = None
        self._pending_motion_paths: dict[str, QPainterPath] = {}
        self._initial_snapshot: dict[str, Any] = {}

        self._mechanism_position_targets: dict[str, QPointF] = {}
        self._mechanism_controlled_joints: set[str] = set()

        self._init_attempts = 0

    def _get_standardized_joint_id(self, abstract_or_original_name: str) -> str | None:
        """Looks up the standardized joint ID from an abstract IK rig name or original source name."""
        if not self._current_skeleton_data or "joint_map" not in self._current_skeleton_data:
            return None

        joint_map = self._current_skeleton_data["joint_map"]

        if abstract_or_original_name in joint_map:
            return joint_map[abstract_or_original_name]

        if abstract_or_original_name in self.sim_joints_config:
            return abstract_or_original_name

        return None

    @property
    def _current_skeleton_data(self) -> dict[str, Any] | None:
        return self.__internal_current_skeleton_data

    @_current_skeleton_data.setter
    def _current_skeleton_data(self, value: dict[str, Any] | None):
        try:
            caller_function = inspect.stack()[1].function
        except IndexError:
            caller_function = "unknown_caller"

        self.__internal_current_skeleton_data = value

    def set_animation_duration(self, duration_ms: int):
        """Sets the total duration for one loop of the IK animation."""
        if duration_ms > 0:
            self.animation_duration = duration_ms

    def set_skeleton_manager(self, skeleton_manager_instance: Optional["SkeletonManager"]):
        if self.skeleton_manager_ref:
            try:
                self.skeleton_manager_ref.skeleton_updated.disconnect(
                    self.on_skeleton_data_updated_from_manager
                )
            except (TypeError, RuntimeError):
                pass

        self.skeleton_manager_ref = skeleton_manager_instance

        if self.skeleton_manager_ref:
            try:
                self.skeleton_manager_ref.skeleton_updated.connect(
                    self.on_skeleton_data_updated_from_manager
                )
            except Exception as e:
                logging.error(f"IKManager: Failed to connect to SkeletonManager: {e}")

    def set_project_parts_data(self, parts_data: dict[str, PartInfo]):
        """Sets the parts data from the current project, used for animation paths etc."""
        self.project_parts_data = parts_data.copy()

        for part_name, path in self._pending_motion_paths.items():
            if part_name in self.project_parts_data:
                self.project_parts_data[part_name].motion_path_data = path

        self._pending_motion_paths.clear()
        self._try_initialize_solver()

    def _try_initialize_solver(self) -> None:
        """
        Attempts to initialize the IK solver if all necessary data (skeleton, parts) is present.
        """
        self._init_attempts += 1

        if not self._current_skeleton_data or not self._current_skeleton_data.get("joints"):
            return

        if not self.project_parts_data:
            return

        self.stop_animation()
        self.ik_solver = None
        self.dynamic_joints.clear()
        self.scene_joints_snapshot.clear()
        # CRITICAL FIX: Preserve bend directions when clearing definitions
        self._clear_ik_definitions(emit_signal=False, preserve_bend_directions=True)

        success = self.initialize_ik_solver()
        if success:
            self.ik_solver_initialized.emit(True, self.sim_joints_config.copy())
        else:
            self.ik_solver_initialized.emit(False, {})

    def initialize_ik_solver(self) -> bool:
        """
        Initializes the IK solver with the current skeleton and parts data.
        This involves defining IK chains, end-effectors, and their motion paths.
        Returns True if successful, False otherwise.
        """
        if not self._current_skeleton_data or not self._current_skeleton_data.get("joints"):
            return False
        if not self.project_parts_data:
            return False

        self.ik_solver = "DummySolver"

        self._sim_dynamic_joints_data.clear()
        self.sim_joints_config.clear()
        self._initial_snapshot.clear()

        for joint_id, joint_data_dict in self._current_skeleton_data["joints"].items():
            pos_list = joint_data_dict.get("position")

            if pos_list and len(pos_list) == 2:
                self.sim_joints_config[joint_id] = {
                    "position": QPointF(pos_list[0], pos_list[1]),
                    "angle": 0.0,
                    "parent": joint_data_dict.get("parent_id"),
                    "name": joint_id,
                    "children": joint_data_dict.get("child_ids", []),
                }

                if (
                    "hip" not in joint_id.lower()
                    and "neck" not in joint_id.lower()
                    and "head" != joint_id.lower()
                    and "torso" != joint_id.lower()
                ):
                    self._sim_dynamic_joints_data[joint_id] = self.sim_joints_config[joint_id].copy()

        for joint_id, joint_data in self.sim_joints_config.items():
            parent_id = joint_data.get("parent")
            if parent_id and parent_id in self.sim_joints_config:
                parent_pos = self.sim_joints_config[parent_id]["position"]
                child_pos = joint_data["position"]

                dx = child_pos.x() - parent_pos.x()
                dy = child_pos.y() - parent_pos.y()
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)

                joint_data["angle"] = angle_deg

        self._initial_snapshot = {
            name: data.copy() for name, data in self.sim_joints_config.items()
        }

        self.sim_selectable_components = [
            {
                "name": "Head Control",
                "partName": "head",
                "targetJointId": "neck",
            },
            {
                "name": "Left Hand Control",
                "partName": "left_arm_lower",
                "targetJointId": "left_hand",
            },
            {
                "name": "Right Hand Control",
                "partName": "right_arm_lower",
                "targetJointId": "right_hand",
            },
            {
                "name": "Left Foot Control",
                "partName": "left_leg_lower",
                "targetJointId": "left_foot",
            },
            {
                "name": "Right Foot Control",
                "partName": "right_leg_lower",
                "targetJointId": "right_foot",
            },
            {
                "name": "Torso Control",
                "partName": "torso",
                "targetJointId": "torso",
            },
        ]

        self.sim_two_bone_ik_effectors = [
            "left_hand",
            "right_hand",
            "left_foot",
            "right_foot",
        ]

        self.sim_limb_configs = {
            "left_elbow": {"parentAnchor": "left_shoulder", "label": "left_arm_upper"},
            "left_hand": {"parentAnchor": "left_elbow", "label": "left_arm_lower"},
            "right_elbow": {"parentAnchor": "right_shoulder", "label": "right_arm_upper"},
            "right_hand": {"parentAnchor": "right_elbow", "label": "right_arm_lower"},
            "left_knee": {"parentAnchor": "left_hip", "label": "left_leg_upper"},
            "left_foot": {"parentAnchor": "left_knee", "label": "left_leg_lower"},
            "right_knee": {"parentAnchor": "right_hip", "label": "right_leg_upper"},
            "right_foot": {"parentAnchor": "right_knee", "label": "right_leg_lower"},
        }

        # CRITICAL FIX: Don't reset sim_joint_bend_directions, preserve existing values
        # Only initialize if it doesn't exist or is empty
        if not hasattr(self, 'sim_joint_bend_directions'):
            self.sim_joint_bend_directions = {}

        # Store existing bend directions to preserve user changes
        existing_bend_directions = self.sim_joint_bend_directions.copy()

        # Debug logging
        logging.info(f"IKManager.initialize_ik_solver: Existing bend directions: {existing_bend_directions}")
        if self._current_skeleton_data and "joint_map" in self._current_skeleton_data:
            logging.info(f"IKManager.initialize_ik_solver: joint_map = {self._current_skeleton_data['joint_map']}")

        middle_joints_to_process = [
            "left_elbow",
            "right_elbow",
            "left_knee",
            "right_knee",
        ]

        # First, check if skeleton has bend_direction values and use them
        for middle_joint_abstract_name in middle_joints_to_process:
            logging.info(f"IKManager.initialize_ik_solver: Processing joint '{middle_joint_abstract_name}'")

            p1_std_id = self._get_standardized_joint_id(middle_joint_abstract_name)
            logging.info(f"IKManager.initialize_ik_solver: '{middle_joint_abstract_name}' -> standardized ID: '{p1_std_id}'")

            if not p1_std_id or p1_std_id not in self.sim_joints_config:
                logging.warning(f"IKManager.initialize_ik_solver: Could not find standardized ID for '{middle_joint_abstract_name}'")
                continue

            # Check if this joint has a bend_direction in the skeleton data
            bend_dir_from_skeleton = None
            if self._current_skeleton_data and "joints" in self._current_skeleton_data:
                joint_data = self._current_skeleton_data["joints"].get(p1_std_id, {})
                bend_dir_from_skeleton = joint_data.get("bend_direction")
                logging.info(f"IKManager.initialize_ik_solver: Skeleton bend_direction for '{p1_std_id}': {bend_dir_from_skeleton}")

            if bend_dir_from_skeleton is not None:
                # Use the bend direction from skeleton (user-defined or default)
                self.sim_joint_bend_directions[middle_joint_abstract_name] = bend_dir_from_skeleton
                # Also store with standardized ID for compatibility
                self.sim_joint_bend_directions[p1_std_id] = bend_dir_from_skeleton
                logging.info(f"IKManager: Using bend_direction {bend_dir_from_skeleton} from skeleton for joint '{middle_joint_abstract_name}' (ID: '{p1_std_id}')")
                continue

            # Check if we have an existing bend direction (from previous initialization or user action)
            if middle_joint_abstract_name in existing_bend_directions:
                self.sim_joint_bend_directions[middle_joint_abstract_name] = existing_bend_directions[middle_joint_abstract_name]
                # Also store with standardized ID
                if p1_std_id:
                    self.sim_joint_bend_directions[p1_std_id] = existing_bend_directions[middle_joint_abstract_name]
                logging.info(f"IKManager: Preserving existing bend_direction {existing_bend_directions[middle_joint_abstract_name]} for joint '{middle_joint_abstract_name}'")
                continue
            elif p1_std_id in existing_bend_directions:
                self.sim_joint_bend_directions[p1_std_id] = existing_bend_directions[p1_std_id]
                self.sim_joint_bend_directions[middle_joint_abstract_name] = existing_bend_directions[p1_std_id]
                logging.info(f"IKManager: Preserving existing bend_direction {existing_bend_directions[p1_std_id]} for joint '{p1_std_id}'")
                continue

            # If no bend_direction in skeleton or existing values, calculate it geometrically
            logging.info(f"IKManager.initialize_ik_solver: Calculating bend_direction geometrically for '{middle_joint_abstract_name}'")
            p1_pos = self.sim_joints_config[p1_std_id]["position"]

            middle_joint_limb_config = self.sim_limb_configs.get(middle_joint_abstract_name)
            if not middle_joint_limb_config:
                continue
            p0_abstract_name = middle_joint_limb_config.get("parentAnchor")
            if not p0_abstract_name:
                continue
            p0_std_id = self._get_standardized_joint_id(p0_abstract_name)
            if not p0_std_id or p0_std_id not in self.sim_joints_config:
                continue
            p0_pos = self.sim_joints_config[p0_std_id]["position"]

            p2_std_id = None
            p2_abstract_name = None
            for effector_abs_name, config_data in self.sim_limb_configs.items():
                if config_data.get("parentAnchor") == middle_joint_abstract_name:
                    p2_abstract_name = effector_abs_name
                    p2_std_id = self._get_standardized_joint_id(effector_abs_name)
                    break

            if not p2_std_id or p2_std_id not in self.sim_joints_config:
                continue
            p2_pos = self.sim_joints_config[p2_std_id]["position"]

            vec_to_root = QPointF(p0_pos.x() - p1_pos.x(), p0_pos.y() - p1_pos.y())
            vec_to_end = QPointF(p2_pos.x() - p1_pos.x(), p2_pos.y() - p1_pos.y())

            angle_to_root = math.atan2(vec_to_root.y(), vec_to_root.x())
            angle_to_end = math.atan2(vec_to_end.y(), vec_to_end.x())

            angle_diff = angle_to_end - angle_to_root

            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi

            vec_to_root = p0_pos - p1_pos
            vec_to_end = p2_pos - p1_pos

            cross_product = (vec_to_root.x() * vec_to_end.y()) - (vec_to_root.y() * vec_to_end.x())

            if abs(cross_product) < 1e-4:
                direction = 1 if "left" in middle_joint_abstract_name else -1
            else:
                direction = -1 if cross_product > 0 else 1

            self.sim_joint_bend_directions[middle_joint_abstract_name] = direction
            # Also store with standardized ID
            if p1_std_id:
                self.sim_joint_bend_directions[p1_std_id] = direction
            logging.info(f"IKManager.initialize_ik_solver: Calculated bend_direction = {direction} for '{middle_joint_abstract_name}' (ID: '{p1_std_id}')")

        logging.info(f"IKManager.initialize_ik_solver: Final sim_joint_bend_directions = {self.sim_joint_bend_directions}")

        if not hasattr(self, "sim_joint_rest_angles"):
            self.sim_joint_rest_angles = {
                "left_shoulder": 180.0,
                "right_shoulder": 0.0,
                "left_hip": -90.0,
                "right_hip": -90.0,
            }

        self.sim_limb_lengths.clear()

        if (hasattr(self, 'sim_joints_config') and
            self.sim_joints_config and
            hasattr(self, 'sim_limb_configs')):

            for limb_effector_key, config in self.sim_limb_configs.items():
                part_label_for_length = config.get("label")
                parent_anchor = config.get("parentAnchor")

                if part_label_for_length and parent_anchor:
                    child_std_id = self._get_standardized_joint_id(limb_effector_key)
                    parent_std_id = self._get_standardized_joint_id(parent_anchor)

                    if (child_std_id and parent_std_id and
                        child_std_id in self.sim_joints_config and
                        parent_std_id in self.sim_joints_config):

                        child_pos = self.sim_joints_config[child_std_id].get("position")
                        parent_pos = self.sim_joints_config[parent_std_id].get("position")

                        if child_pos and parent_pos:
                            actual_bone_length = QLineF(parent_pos, child_pos).length()

                            if actual_bone_length > 0:
                                self.sim_limb_lengths[part_label_for_length] = actual_bone_length
                                continue

                if (part_label_for_length and
                    part_label_for_length in self.project_parts_data):
                    part_info = self.project_parts_data[part_label_for_length]
                    length = 0
                    if part_info.roi and len(part_info.roi) == 4:
                        length = float(part_info.roi[3])
                    if length <= 0:
                        length = 50
                    self.sim_limb_lengths[part_label_for_length] = length
                elif part_label_for_length:
                    self.sim_limb_lengths[part_label_for_length] = 50
        else:
            for limb_effector_key, config in self.sim_limb_configs.items():
                part_label_for_length = config.get("label")
                if (part_label_for_length and
                    part_label_for_length in self.project_parts_data):
                    part_info = self.project_parts_data[part_label_for_length]
                    length = 0
                    if part_info.roi and len(part_info.roi) == 4:
                        length = float(part_info.roi[3])
                    if length <= 0:
                        length = 50
                    self.sim_limb_lengths[part_label_for_length] = length
                elif part_label_for_length:
                    self.sim_limb_lengths[part_label_for_length] = 50

        return True

    def on_skeleton_data_updated_from_manager(
        self, standardized_skeleton_dict: dict | None
    ):
        """Called when SkeletonManager emits its skeleton_updated signal (with a dict)."""
        if not standardized_skeleton_dict:
            self._clear_ik_definitions()
            self.ik_solver_initialized.emit(False, {})
            self._current_skeleton_data = None
            return

        try:
            # Debug logging to check bend_direction values
            if "joints" in standardized_skeleton_dict:
                for joint_id, joint_data in standardized_skeleton_dict["joints"].items():
                    if "elbow" in joint_id or "knee" in joint_id:
                        bend_dir = joint_data.get("bend_direction")
                        logging.info(f"IKManager.on_skeleton_data_updated: Joint '{joint_id}' has bend_direction = {bend_dir}")

            standardized_model = StandardizedSkeletonModel.model_validate(
                standardized_skeleton_dict
            )
            self._current_skeleton_data = standardized_model.model_dump()
            self._current_joint_connections = standardized_model.hierarchy

            # Debug logging after model_dump
            if "joints" in self._current_skeleton_data:
                for joint_id, joint_data in self._current_skeleton_data["joints"].items():
                    if "elbow" in joint_id or "knee" in joint_id:
                        bend_dir = joint_data.get("bend_direction")
                        logging.info(f"IKManager.on_skeleton_data_updated (after model_dump): Joint '{joint_id}' has bend_direction = {bend_dir}")

            # Update bend directions if IK solver is already initialized
            if hasattr(self, 'sim_joint_bend_directions') and self.sim_joint_bend_directions:
                self._update_bend_directions_from_skeleton()

            self._try_initialize_solver()
        except Exception as e:
            logging.error(
                f"IKManager (id:{id(self)}): Error processing standardized skeleton dict: {e}",
                exc_info=True,
            )
            self._clear_ik_definitions()
            self._current_skeleton_data = None
            self.ik_solver_initialized.emit(False, {})
            self.error_occurred.emit(f"Error initializing IK from skeleton: {e}")

    def _update_bend_directions_from_skeleton(self):
        """Update bend directions from the current skeleton data or skeleton_manager."""
        # First try to get from skeleton_manager (most authoritative source)
        if self.skeleton_manager_ref:
            logging.info("IKManager._update_bend_directions_from_skeleton: Getting bend directions from skeleton_manager")
            bend_directions = self.skeleton_manager_ref.get_all_joint_bend_directions()

            if bend_directions:
                # Clear existing and update with fresh data
                self.sim_joint_bend_directions.clear()

                for joint_id, bend_dir in bend_directions.items():
                    # Store with standardized ID
                    self.sim_joint_bend_directions[joint_id] = bend_dir

                    # Also store with abstract name for compatibility
                    if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                        abstract_name = '_'.join(joint_id.split('_')[:-1])
                        self.sim_joint_bend_directions[abstract_name] = bend_dir

                    logging.info(f"IKManager: Updated bend_direction for '{joint_id}' to {bend_dir} from skeleton_manager")

                logging.info(f"IKManager._update_bend_directions_from_skeleton: Final bend_directions from skeleton_manager = {self.sim_joint_bend_directions}")
                return

        # Fallback to skeleton data if skeleton_manager not available
        if not self._current_skeleton_data or "joints" not in self._current_skeleton_data:
            logging.warning("IKManager._update_bend_directions_from_skeleton: No skeleton data available")
            return

        # Debug: log all joints with bend_direction in skeleton
        logging.info("IKManager._update_bend_directions_from_skeleton: Using skeleton data (fallback)...")
        joints_with_bend_dir = {}
        for joint_id, joint_data in self._current_skeleton_data["joints"].items():
            bend_dir = joint_data.get("bend_direction")
            if bend_dir is not None:
                joints_with_bend_dir[joint_id] = bend_dir

        logging.info(f"IKManager._update_bend_directions_from_skeleton: Found {len(joints_with_bend_dir)} joints with bend_direction in skeleton: {joints_with_bend_dir}")

        # Clear ALL existing bend directions first to avoid stale values
        # We'll only keep those that are explicitly set in the skeleton
        old_directions = self.sim_joint_bend_directions.copy()
        self.sim_joint_bend_directions.clear()
        logging.info(f"IKManager._update_bend_directions_from_skeleton: Cleared old directions: {old_directions}")

        # Store bend directions for both standardized IDs and abstract names
        for joint_id, joint_data in self._current_skeleton_data["joints"].items():
            bend_dir = joint_data.get("bend_direction")
            if bend_dir is not None:
                # Store with standardized ID (e.g., 'left_elbow_8')
                self.sim_joint_bend_directions[joint_id] = bend_dir

                # Also store with abstract name for compatibility
                # Extract abstract name (e.g., 'left_elbow_8' -> 'left_elbow')
                if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                    abstract_name = '_'.join(joint_id.split('_')[:-1])
                    self.sim_joint_bend_directions[abstract_name] = bend_dir

                    # Only log for actual middle joints
                    if 'elbow' in joint_id or 'knee' in joint_id:
                        logging.info(f"IKManager: Updated bend_direction for '{joint_id}' (and '{abstract_name}') to {bend_dir}")

        # Log the final state
        logging.info(f"IKManager._update_bend_directions_from_skeleton: Final bend_directions = {self.sim_joint_bend_directions}")

        # Double-check: Are there any unexpected values?
        for key, value in self.sim_joint_bend_directions.items():
            if 'shoulder' in key or 'hip' in key or 'torso' in key or 'neck' in key or 'hand' in key or 'foot' in key or 'root' in key:
                logging.warning(f"IKManager._update_bend_directions_from_skeleton: Unexpected joint '{key}' has bend_direction = {value}. This joint should not have a bend_direction!")

    def _clear_ik_definitions(self, emit_signal=True, preserve_bend_directions=False) -> None:
        """Clears IK solver-derived configurations and resets animation state.
        Does NOT clear input data like _current_skeleton_data or project_parts_data.
        
        Args:
            emit_signal: Whether to emit the ik_solver_initialized signal
            preserve_bend_directions: If True, preserves user-set bend directions
        """
        self.stop_animation()
        self.ik_solver = None

        # Store bend directions before clearing if we need to preserve them
        saved_bend_directions = {}
        if preserve_bend_directions and hasattr(self, "sim_joint_bend_directions"):
            saved_bend_directions = self.sim_joint_bend_directions.copy()

        if hasattr(self, "_sim_dynamic_joints_data"):
            self._sim_dynamic_joints_data.clear()
        if hasattr(self, "sim_joints_config"):
            self.sim_joints_config.clear()
        if hasattr(self, "sim_limb_configs"):
            self.sim_limb_configs.clear()
        if hasattr(self, "sim_limb_lengths"):
            self.sim_limb_lengths.clear()
        if hasattr(self, "scene_joints_snapshot"):
            self.scene_joints_snapshot.clear()
        if hasattr(self, "sim_selectable_components"):
            self.sim_selectable_components.clear()
        if hasattr(self, "sim_two_bone_ik_effectors"):
            self.sim_two_bone_ik_effectors.clear()
        if hasattr(self, "sim_joint_bend_directions"):
            self.sim_joint_bend_directions.clear()
            # Restore saved bend directions if needed
            if preserve_bend_directions and saved_bend_directions:
                self.sim_joint_bend_directions.update(saved_bend_directions)

        if emit_signal:
            self.ik_solver_initialized.emit(False, {})

    def reset_all_ik_systems_and_data(self) -> None:
        """Clears ALL data including project parts, current skeleton, and IK definitions."""
        self.project_parts_data.clear()
        self._pending_motion_paths.clear()
        self._current_skeleton_data = None
        self._current_joint_connections = None
        self._clear_ik_definitions(emit_signal=True)

    def _solve_single_bone_ik(
        self,
        target_joint_abstract_name: str,
        anchor_joint_abstract_name: str,
        target_position: np.ndarray,
    ) -> dict[str, dict[str, Any]]:
        """
        Solves IK for a single bone (e.g., head controlled by neck, anchored at torso).
        The target_joint_abstract_name ('neck') is placed at target_position.
        The anchor_joint_abstract_name ('torso') is its base.
        """
        updated_configs: dict[str, dict[str, Any]] = {}

        target_joint_id_std = self._get_standardized_joint_id(target_joint_abstract_name)
        if not target_joint_id_std:
            return {}

        anchor_joint_id_std = self._get_standardized_joint_id(anchor_joint_abstract_name)
        if not anchor_joint_id_std:
            return {}

        if anchor_joint_id_std not in self.sim_joints_config:
            logging.error(
                f"IKM._solve_single_bone_ik: Anchor joint ID '{anchor_joint_id_std}' "
                f"NOT FOUND in sim_joints_config. Available keys: {list(self.sim_joints_config.keys())}"
            )
            return {}

        base_joint_pos = self.sim_joints_config[anchor_joint_id_std]["position"]

        original_bone_length = None
        if (anchor_joint_id_std in self.sim_joints_config and
            target_joint_id_std in self.sim_joints_config):
            anchor_current = self.sim_joints_config[anchor_joint_id_std].get("position")
            target_current = self.sim_joints_config[target_joint_id_std].get("position")
            if anchor_current and target_current:
                original_bone_length = QLineF(anchor_current, target_current).length()

        desired_pos = QPointF(target_position[0], target_position[1])

        if original_bone_length and original_bone_length > 0:
            current_distance = QLineF(base_joint_pos, desired_pos).length()

            min_length = original_bone_length * 0.9
            max_length = original_bone_length * 1.1

            if current_distance < min_length or current_distance > max_length:
                if current_distance > 1e-6:
                    clamped_length = max(min_length, min(max_length, current_distance))
                    direction_x = (desired_pos.x() - base_joint_pos.x()) / current_distance
                    direction_y = (desired_pos.y() - base_joint_pos.y()) / current_distance

                    final_pos = QPointF(
                        base_joint_pos.x() + direction_x * clamped_length,
                        base_joint_pos.y() + direction_y * clamped_length
                    )
                else:
                    final_pos = QPointF(base_joint_pos.x(), base_joint_pos.y() + original_bone_length)
            else:
                final_pos = desired_pos
        else:
            final_pos = desired_pos

        updated_configs[target_joint_id_std] = {
            "position": final_pos,
            "angle": 0.0,
            "parent": anchor_joint_id_std,
            "name": target_joint_id_std,
            "children": [],
        }

        return updated_configs

    def _solve_two_bone_ik(
        self,
        root_pos: QPointF,
        target_pos: QPointF,
        length1: float,
        length2: float,
        root_joint_std_id: str,
    ) -> tuple[QPointF, QPointF] | None:
        """
        Solves 2-bone IK for a given root, target, and bone lengths.
        Returns (middle_joint_pos, end_effector_pos) or None if unsolvable.
        """
        p0 = root_pos
        target = target_pos
        l1 = length1
        l2 = length2

        if l1 <= 0 or l2 <= 0:
            safe_l1 = l1 if l1 > 0 else 1.0
            safe_l2 = l2 if l2 > 0 else 1.0
            p1_bail = QPointF(p0.x(), p0.y() + safe_l1)
            p2_bail = QPointF(p1_bail.x(), p1_bail.y() + safe_l2)
            return p1_bail, p2_bail

        dx = target.x() - p0.x()
        dy = target.y() - p0.y()
        dist_sq = dx * dx + dy * dy
        dist = math.sqrt(dist_sq) if dist_sq > 1e-12 else 0.0

        middle_joint_id = None
        if "shoulder" in root_joint_std_id:
            middle_joint_id = root_joint_std_id.replace("shoulder", "elbow")
        elif "hip" in root_joint_std_id:
            middle_joint_id = root_joint_std_id.replace("hip", "knee")

        # Get bend direction from configuration
        bend_direction = 1.0

        # Find the actual middle joint from skeleton hierarchy
        middle_joint_std_id = None

        # Try to find the middle joint from skeleton hierarchy
        if self._current_skeleton_data and "hierarchy" in self._current_skeleton_data:
            hierarchy = self._current_skeleton_data.get("hierarchy", {})
            children = hierarchy.get(root_joint_std_id, [])

            # Find the child that contains "elbow" or "knee"
            for child_id in children:
                if "shoulder" in root_joint_std_id and "elbow" in child_id:
                    middle_joint_std_id = child_id
                    break
                elif "hip" in root_joint_std_id and "knee" in child_id:
                    middle_joint_std_id = child_id
                    break

        # Fallback to hardcoded mapping if hierarchy lookup fails
        if not middle_joint_std_id:
            # Known mappings from actual skeleton structure
            joint_mapping = {
                "left_shoulder_7": "left_elbow_8",
                "right_shoulder_4": "right_elbow_5",
                "left_hip_13": "left_knee_14",
                "right_hip_10": "right_knee_11",
            }
            middle_joint_std_id = joint_mapping.get(root_joint_std_id)

        # Look up bend direction using multiple possible keys
        if middle_joint_std_id:
            # First try the exact standardized ID
            if middle_joint_std_id in self.sim_joint_bend_directions:
                bend_direction = float(self.sim_joint_bend_directions[middle_joint_std_id])
                logging.info(f"IK: Using bend_direction {bend_direction} for middle joint '{middle_joint_std_id}'")
            else:
                # Try the abstract name (e.g., 'left_elbow' without the number)
                abstract_name = None
                if '_' in middle_joint_std_id and middle_joint_std_id.split('_')[-1].isdigit():
                    abstract_name = '_'.join(middle_joint_std_id.split('_')[:-1])
                    if abstract_name in self.sim_joint_bend_directions:
                        bend_direction = float(self.sim_joint_bend_directions[abstract_name])
                        logging.info(f"IK: Using bend_direction {bend_direction} for middle joint '{abstract_name}' (from '{middle_joint_std_id}')")

                if abstract_name is None or abstract_name not in self.sim_joint_bend_directions:
                    logging.debug(f"IK: No bend_direction found for '{middle_joint_std_id}', using default {bend_direction}")

        _max_elbow_flexion_deg = getattr(self, "_max_elbow_flexion_deg", 160.0)
        _epsilon_dist = getattr(self, "_epsilon_dist", 1.0)
        _near_max_reach_threshold = getattr(self, "_near_max_reach_threshold", 5.0)
        _near_min_reach_threshold = getattr(self, "_near_min_reach_threshold", 5.0)

        min_elbow_internal_angle_rad = math.pi - math.radians(_max_elbow_flexion_deg)
        min_elbow_internal_angle_rad = max(0.0, min(math.pi, min_elbow_internal_angle_rad))

        cos_min_elbow_angle = math.cos(min_elbow_internal_angle_rad)
        d_min_sq_with_limit = l1 * l1 + l2 * l2 - 2 * l1 * l2 * cos_min_elbow_angle
        if d_min_sq_with_limit < 0:
            d_min_sq_with_limit = 0
        d_min_with_limit = math.sqrt(d_min_sq_with_limit)

        if dist < _epsilon_dist:
            base_angle_rad = math.radians(
                self.sim_joint_rest_angles.get(root_joint_std_id, 90.0)
            )
            p1_x = p0.x() + l1 * math.cos(base_angle_rad)
            p1_y = p0.y() + l1 * math.sin(base_angle_rad)
            p1_new = QPointF(p1_x, p1_y)
            angle_of_bone2_from_p1 = base_angle_rad + bend_direction * (
                math.pi - min_elbow_internal_angle_rad
            )
            p2_x = p1_new.x() + l2 * math.cos(angle_of_bone2_from_p1)
            p2_y = p1_new.y() + l2 * math.sin(angle_of_bone2_from_p1)
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        elif dist >= (l1 + l2 - _near_max_reach_threshold):
            angle_root_to_target = math.atan2(dy, dx)
            p1_x = p0.x() + l1 * math.cos(angle_root_to_target)
            p1_y = p0.y() + l1 * math.sin(angle_root_to_target)
            p1_new = QPointF(p1_x, p1_y)
            p2_x = p1_new.x() + l2 * math.cos(angle_root_to_target)
            p2_y = p1_new.y() + l2 * math.sin(angle_root_to_target)
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        elif dist < (d_min_with_limit + _near_min_reach_threshold):
            angle_root_to_target = math.atan2(dy, dx)
            dist_eff = d_min_with_limit

            if dist_eff < _epsilon_dist:
                base_angle_rad = math.radians(
                    self.sim_joint_rest_angles.get(root_joint_std_id, 90.0)
                )
                p1_x = p0.x() + l1 * math.cos(base_angle_rad)
                p1_y = p0.y() + l1 * math.sin(base_angle_rad)
                p1_new = QPointF(p1_x, p1_y)
                angle_of_bone2_from_p1 = base_angle_rad + bend_direction * (
                    math.pi - min_elbow_internal_angle_rad
                )
                p2_x = p1_new.x() + l2 * math.cos(angle_of_bone2_from_p1)
                p2_y = p1_new.y() + l2 * math.sin(angle_of_bone2_from_p1)
                p2_new = QPointF(p2_x, p2_y)
                return p1_new, p2_new

            cos_alpha_eff_numerator = dist_eff * dist_eff + l1 * l1 - l2 * l2
            cos_alpha_eff_denominator = 2 * dist_eff * l1

            if abs(cos_alpha_eff_denominator) < 1e-9:
                p1_x_f = p0.x() + l1 * math.cos(angle_root_to_target)
                p1_y_f = p0.y() + l1 * math.sin(angle_root_to_target)
                p1_new_f = QPointF(p1_x_f, p1_y_f)
                angle_bone2_world_f = angle_root_to_target + bend_direction * (
                    math.pi - min_elbow_internal_angle_rad
                )
                p2_x_f = p1_new_f.x() + l2 * math.cos(angle_bone2_world_f)
                p2_y_f = p1_new_f.y() + l2 * math.sin(angle_bone2_world_f)
                p2_new_f = QPointF(p2_x_f, p2_y_f)
                return p1_new_f, p2_new_f

            cos_alpha_eff = cos_alpha_eff_numerator / cos_alpha_eff_denominator
            cos_alpha_eff = max(-1.0, min(1.0, cos_alpha_eff))
            alpha_eff_rad = math.acos(cos_alpha_eff)

            angle1_final_rad = angle_root_to_target - (bend_direction * alpha_eff_rad)

            p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
            p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
            p1_new = QPointF(p1_x, p1_y)

            angle_elbow_bend_from_bone1_line_rad = bend_direction * (
                math.pi - min_elbow_internal_angle_rad
            )

            p2_x = p1_new.x() + l2 * math.cos(
                angle1_final_rad + angle_elbow_bend_from_bone1_line_rad
            )
            p2_y = p1_new.y() + l2 * math.sin(
                angle1_final_rad + angle_elbow_bend_from_bone1_line_rad
            )
            p2_new = QPointF(p2_x, p2_y)
            return p1_new, p2_new

        else:
            l1_sq = l1 * l1
            l2_sq = l2 * l2

            cos_angle2_numerator = l1_sq + l2_sq - dist_sq
            cos_angle2_denominator = 2 * l1 * l2

            if abs(cos_angle2_denominator) < 1e-9:
                angle_root_to_target_s = math.atan2(dy, dx)
                p1_x_s = p0.x() + l1 * math.cos(angle_root_to_target_s)
                p1_y_s = p0.y() + l1 * math.sin(angle_root_to_target_s)
                p1_new_s = QPointF(p1_x_s, p1_y_s)
                p2_x_s = p1_new_s.x() + l2 * math.cos(angle_root_to_target_s)
                p2_y_s = p1_new_s.y() + l2 * math.sin(angle_root_to_target_s)
                p2_new_s = QPointF(p2_x_s, p2_y_s)
                return p1_new_s, p2_new_s

            cos_angle2 = cos_angle2_numerator / cos_angle2_denominator
            cos_angle2 = max(-1.0, min(1.0, cos_angle2))
            angle2_triangle_rad = math.acos(cos_angle2)

            angle2_triangle_rad = max(angle2_triangle_rad, min_elbow_internal_angle_rad)

            cos_alpha_numerator = dist_sq + l1_sq - l2_sq
            cos_alpha_denominator = 2 * dist * l1

            if abs(cos_alpha_denominator) < 1e-9:
                angle_root_to_target_s2 = math.atan2(dy, dx)
                p1_x_s2 = p0.x() + l1 * math.cos(angle_root_to_target_s2)
                p1_y_s2 = p0.y() + l1 * math.sin(angle_root_to_target_s2)
                p1_new_s2 = QPointF(p1_x_s2, p1_y_s2)
                angle_bone2_world_s2 = angle_root_to_target_s2 + bend_direction * (
                    math.pi - angle2_triangle_rad
                )
                p2_x_s2 = p1_new_s2.x() + l2 * math.cos(angle_bone2_world_s2)
                p2_y_s2 = p1_new_s2.y() + l2 * math.sin(angle_bone2_world_s2)
                p2_new_s2 = QPointF(p2_x_s2, p2_y_s2)
                return p1_new_s2, p2_new_s2

            cos_alpha = cos_alpha_numerator / cos_alpha_denominator
            cos_alpha = max(-1.0, min(1.0, cos_alpha))
            alpha_rad = math.acos(cos_alpha)

            angle_root_to_target_rad = math.atan2(dy, dx)
            angle1_final_rad = angle_root_to_target_rad - (bend_direction * alpha_rad)

            p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
            p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
            p1_new = QPointF(p1_x, p1_y)

            angle_elbow_bend_from_bone1_line_rad = bend_direction * (
                math.pi - angle2_triangle_rad
            )

            p2_x = p1_new.x() + l2 * math.cos(
                angle1_final_rad + angle_elbow_bend_from_bone1_line_rad
            )
            p2_y = p1_new.y() + l2 * math.sin(
                angle1_final_rad + angle_elbow_bend_from_bone1_line_rad
            )
            p2_new = QPointF(p2_x, p2_y)

            return p1_new, p2_new

    def _apply_ik_to_limb_chains(
        self, editor_items: dict[str, CharacterPartItem]
    ) -> None:
        """Applies FABRIK IK to arm and leg chains to maintain proper joint constraints."""
        from ..kinematics.solvers.fabraik_solver import (
            solve_ik_fabrik_with_constraints as solve_ik_ccd,
        )

        limb_chains = {
            "left_hand": {
                "chain_parts": ["torso", "left_arm_upper", "left_arm_lower"],
                "target_joint": "left_hand",
            },
            "right_hand": {
                "chain_parts": ["torso", "right_arm_upper", "right_arm_lower"],
                "target_joint": "right_hand",
            },
            "left_foot": {
                "chain_parts": ["torso", "left_leg_upper", "left_leg_lower"],
                "target_joint": "left_foot",
            },
            "right_foot": {
                "chain_parts": ["torso", "right_leg_upper", "right_leg_lower"],
                "target_joint": "right_foot",
            },
        }

        for effector_joint, chain_config in limb_chains.items():
            chain_parts = chain_config["chain_parts"]
            target_joint = chain_config["target_joint"]

            chain = []
            all_parts_available = True

            for part_name in chain_parts:
                if part_name in editor_items:
                    part_item = editor_items[part_name]
                    chain.append(part_item)
                else:
                    all_parts_available = False
                    break

            if not all_parts_available or len(chain) < 2:
                continue

            target_joint_std = self._get_standardized_joint_id(target_joint)
            if not target_joint_std or target_joint_std not in self.sim_joints_config:
                continue

            target_pos = self.sim_joints_config[target_joint_std].get("position")
            if not target_pos:
                continue

            original_lengths = self._get_bone_lengths_for_chain(chain_parts)

            # Convert bend_directions from standardized IDs to abstract names for FABRIK solver
            # FABRIK expects keys like 'left_elbow', but we have 'left_elbow_8'
            # Only pass bend directions for actual middle joints (elbow, knee)
            converted_bend_directions = {}
            for std_id, bend_dir in self.sim_joint_bend_directions.items():
                # Only process joints that are actually middle joints (elbow, knee)
                if 'elbow' in std_id or 'knee' in std_id:
                    # For standardized IDs like 'left_elbow_8', extract 'left_elbow'
                    if '_' in std_id:
                        parts = std_id.split('_')
                        # Assuming format is like 'left_elbow_8' or 'right_knee_11'
                        if len(parts) >= 3 and parts[-1].isdigit():
                            abstract_name = '_'.join(parts[:-1])  # Join all parts except the last digit
                        else:
                            abstract_name = std_id
                    else:
                        abstract_name = std_id

                    converted_bend_directions[abstract_name] = bend_dir
                    logging.info(f"IK: Passing bend direction to FABRIK: '{abstract_name}' = {bend_dir}")

            solve_ik_ccd(chain, target_pos, original_lengths, bend_directions=converted_bend_directions, iterations=10, tolerance=1.0)

    def _get_bone_lengths_for_chain(self, chain_parts: list[str]) -> list[float]:
        """Get original bone lengths for a chain of parts to preserve skeleton structure."""
        bone_lengths = []

        for i in range(len(chain_parts) - 1):
            part_name = chain_parts[i + 1]

            if part_name in self.sim_limb_lengths:
                length = self.sim_limb_lengths[part_name]
                bone_lengths.append(length)
            else:
                default_length = 50.0
                bone_lengths.append(default_length)

        return bone_lengths

    def _update_character_part_visuals_from_ik(self) -> None:
        """Updates character part visuals using proper IK chains for arms and legs."""
        if not (
            self._current_skeleton_data and "joint_map" in self._current_skeleton_data
        ):
            logging.error(
                "IKManager FK: Missing skeleton data or joint_map for FK update."
            )
            return

        if hasattr(self.main_window, "editor_tab") and self.main_window.editor_tab:
            editor_items = self.main_window.editor_tab.current_editor_items
            self._apply_ik_to_limb_chains(editor_items)

        updated: dict[str, dict[str, Any]] = {}
        processed_parts: set[str] = set()

        std = self._get_standardized_joint_id

        def pos(jid: str):
            return self.sim_joints_config.get(jid, {}).get("position")

        def angle_between(a, b):
            return math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))

        def get_initial_angle(jid: str):
            """Get the initial angle for a joint from the initial snapshot"""
            if self._initial_snapshot and jid in self._initial_snapshot:
                return self._initial_snapshot[jid].get("angle", 0.0)
            return 0.0

        for eff_abs, limb in self.sim_limb_configs.items():
            part_name = limb.get("label")
            parent_id = std(limb.get("parentAnchor"))
            child_id = std(eff_abs)
            if not (part_name and parent_id and child_id):
                continue

            p_parent, p_child = pos(parent_id), pos(child_id)
            if not (p_parent and p_child):
                continue

            current_angle = angle_between(p_parent, p_child)

            initial_parent_pos = None
            initial_child_pos = None
            if self._initial_snapshot:
                if parent_id in self._initial_snapshot:
                    initial_parent_pos = self._initial_snapshot[parent_id].get(
                        "position"
                    )
                if child_id in self._initial_snapshot:
                    initial_child_pos = self._initial_snapshot[child_id].get("position")

            initial_angle = 0.0
            if initial_parent_pos and initial_child_pos:
                initial_angle = angle_between(initial_parent_pos, initial_child_pos)

            joint_angle_delta = current_angle - initial_angle

            part_world_rotation = 0.0 + joint_angle_delta

            updated[parent_id] = {
                "scene_position": p_parent,
                "world_rotation_degrees": part_world_rotation,
            }
            child_current_angle = self.sim_joints_config[child_id].get("angle", 0.0)
            child_initial_angle = get_initial_angle(child_id)
            child_rotation_delta = child_current_angle - child_initial_angle

            updated[child_id] = {
                "scene_position": p_child,
                "world_rotation_degrees": child_rotation_delta,
            }
            processed_parts.add(part_name)

        for comp in self.sim_selectable_components:
            part_name = comp.get("partName")
            if not part_name or part_name in processed_parts:
                continue

            jid = std(comp.get("targetJointId"))
            pj = pos(jid)
            if not (jid and pj):
                continue

            current_angle = self.sim_joints_config[jid].get("angle", 0.0)
            parent_id = self.sim_joints_config[jid].get("parent")

            if parent_id and pos(parent_id):
                current_angle = angle_between(pos(parent_id), pj)

            initial_joint_angle = get_initial_angle(jid)

            joint_angle_delta = current_angle - initial_joint_angle

            part_world_rotation = 0.0 + joint_angle_delta

            updated[jid] = {
                "scene_position": pj,
                "world_rotation_degrees": part_world_rotation,
            }
            processed_parts.add(part_name)

        if updated:
            self.character_visuals_updated.emit(updated)

    def start_animation(self):
        """Starts the IK-driven animation."""
        self.main_window.statusBar().showMessage("Playing IK Animation...", 2000)

        # CRITICAL FIX: Update bend directions from skeleton before starting animation
        # This ensures user-set bend directions are used during animation
        if hasattr(self, 'sim_joint_bend_directions') and self._current_skeleton_data:
            self._update_bend_directions_from_skeleton()
            logging.info(f"IKManager.start_animation: Updated bend directions: {self.sim_joint_bend_directions}")

        if self._animation_start_time_qelapsed is None:
            self._animation_start_time_qelapsed = QElapsedTimer()
        self._animation_start_time_qelapsed.start()
        self._current_animation_progress = 0.0
        if not self.ik_animation_timer.isActive():
            self.ik_animation_timer.start()

        self.animation_state_changed.emit("playing")
        return True

    def stop_animation(self):
        """Stops the IK-driven animation."""
        if self.ik_animation_timer.isActive():
            self.ik_animation_timer.stop()
            self.main_window.statusBar().showMessage("IK Animation stopped.", 2000)
        self.animation_state_changed.emit("stopped")

    def reset_animation_state(self):
        """Resets the animation state to initial state."""
        self.stop_animation()

        if self._initial_snapshot:
            self.sim_joints_config = {
                k: v.copy() for k, v in self._initial_snapshot.items()
            }
            self._sim_dynamic_joints_data = {
                k: v.copy()
                for k, v in self._initial_snapshot.items()
                if k in self._sim_dynamic_joints_data
            }
        else:
            return

        # CRITICAL FIX: Restore bend directions from skeleton_manager after reset
        # This ensures user-set bend directions persist through reset
        if self.skeleton_manager_ref:
            bend_directions = self.skeleton_manager_ref.get_all_joint_bend_directions()
            if bend_directions:
                logging.info(f"IKManager.reset_animation_state: Restoring bend directions from skeleton_manager: {bend_directions}")
                self.sim_joint_bend_directions.clear()

                for joint_id, bend_dir in bend_directions.items():
                    # Store with standardized ID
                    self.sim_joint_bend_directions[joint_id] = bend_dir

                    # Also store with abstract name for compatibility
                    if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                        abstract_name = '_'.join(joint_id.split('_')[:-1])
                        self.sim_joint_bend_directions[abstract_name] = bend_dir

                    logging.info(f"IKManager.reset_animation_state: Restored bend_direction for '{joint_id}' to {bend_dir}")

        if hasattr(self.main_window, "editor_tab") and self.main_window.editor_tab:
            editor_items = self.main_window.editor_tab.current_editor_items
            for part_name, part_item in editor_items.items():
                initial_rotation = getattr(part_item, "_initial_world_rotation", 0.0)
                part_item.setRotation(initial_rotation)

                if part_name in self.project_parts_data:
                    part_info = self.project_parts_data[part_name]
                    if hasattr(part_info, "x") and hasattr(part_info, "y"):
                        part_item.setPos(QPointF(part_info.x, part_info.y))

                    for comp in self.sim_selectable_components:
                        if comp.get("partName") == part_name:
                            target_joint_id = comp.get("targetJointId")
                            if target_joint_id:
                                std_joint_id = self._get_standardized_joint_id(
                                    target_joint_id
                                )
                                if (
                                    std_joint_id
                                    and std_joint_id in self._initial_snapshot
                                ):
                                    joint_pos = self._initial_snapshot[
                                        std_joint_id
                                    ].get("position")
                                    if joint_pos:
                                        part_item.set_scene_position_from_anchor(
                                            joint_pos
                                        )
                                        break

        self._current_animation_progress = 0.0

        self._update_character_part_visuals_from_ik()

        self.main_window.statusBar().showMessage(
            "IK Animation reset to initial pose.", 2000
        )
        self.animation_state_changed.emit("reset")

    def _extract_points_from_painter_path(self, painter_path) -> list[QPointF]:
        """Extracts QPointF coordinates from a QPainterPath."""
        points = []
        if (
            not painter_path
            or not hasattr(painter_path, "elementCount")
            or painter_path.elementCount() == 0
        ):
            return points
        for i in range(painter_path.elementCount()):
            element = painter_path.elementAt(i)
            points.append(QPointF(element.x, element.y))
        return points

    def _get_point_on_path(self, path_obj: Any, progress: float) -> QPointF | None:
        path_points: list[QPointF] = []
        if isinstance(path_obj, list):
            if all(isinstance(p, QPointF) for p in path_obj):
                path_points = path_obj
            else:
                try:
                    path_points = [
                        QPointF(p[0], p[1])
                        for p in path_obj
                        if isinstance(p, (list, tuple)) and len(p) == 2
                    ]
                except:
                    return None
        elif hasattr(path_obj, "elementCount"):
            path_points = self._extract_points_from_painter_path(path_obj)
        else:
            return None

        if not path_points:
            return None
        if len(path_points) == 1:
            return path_points[0]

        total_length = 0
        segment_lengths = []
        for i in range(len(path_points) - 1):
            p1 = path_points[i]
            p2 = path_points[i + 1]
            segment_length = QPointF(p2 - p1).manhattanLength()
            segment_lengths.append(segment_length)
            total_length += segment_length

        if total_length < 1e-5:
            return path_points[0]

        target_dist = progress * total_length
        target_dist = max(0, min(target_dist, total_length))

        current_dist = 0
        for i in range(len(segment_lengths)):
            segment_len = segment_lengths[i]
            if current_dist + segment_len >= target_dist - 1e-5:
                p1 = path_points[i]
                p2 = path_points[i + 1]
                remaining_dist = target_dist - current_dist
                if segment_len < 1e-5:
                    return p1
                segment_progress = remaining_dist / segment_len
                segment_progress = max(0.0, min(1.0, segment_progress))

                interpolated_x = p1.x() + (p2.x() - p1.x()) * segment_progress
                interpolated_y = p1.y() + (p2.y() - p1.y()) * segment_progress
                return QPointF(interpolated_x, interpolated_y)
            current_dist += segment_len

        return path_points[-1]

    def set_mechanism_position_target(self, joint_id: str, target_pos: QPointF):
        """Set a direct position target for a joint (used by mechanism animation)."""
        std_joint_id = self._get_standardized_joint_id(joint_id)
        if not std_joint_id:
            return

        self._mechanism_position_targets[std_joint_id] = target_pos
        self._mechanism_controlled_joints.add(std_joint_id)

    def clear_mechanism_position_targets(self):
        """Clear all mechanism position targets."""
        self._mechanism_position_targets.clear()
        self._mechanism_controlled_joints.clear()

    def clear_mechanism_position_target(self, joint_id: str):
        """Clear mechanism position target for a specific joint."""
        std_joint_id = self._get_standardized_joint_id(joint_id)
        if std_joint_id:
            self._mechanism_position_targets.pop(std_joint_id, None)
            self._mechanism_controlled_joints.discard(std_joint_id)

    def _run_ik_animation_step(self):
        if (
            not self._animation_start_time_qelapsed
            or not self.ik_animation_timer.isActive()
        ):
            return

        elapsed_ms = self._animation_start_time_qelapsed.elapsed()
        if self.animation_duration <= 0:
            self._current_animation_progress = 0.0
        else:
            self._current_animation_progress = (
                elapsed_ms % self.animation_duration
            ) / float(self.animation_duration)

        if elapsed_ms >= self.animation_duration and self.animation_duration > 0:
            self._animation_start_time_qelapsed.start()

        if self._current_animation_progress >= 1.0:
            self._current_animation_progress = 0.0

        if not self.project_parts_data:
            return

        if not self.sim_joints_config:
            return

        if not self.sim_selectable_components:
            return

        if (
            not self._current_skeleton_data
            or "joint_map" not in self._current_skeleton_data
        ):
            logging.error(
                "IKManager._run_ik_animation_step: Missing skeleton data or joint_map."
            )
            return

        for mech_joint_id, mech_target_pos in self._mechanism_position_targets.items():
            if mech_joint_id in self.dynamic_joints:
                self.dynamic_joints[mech_joint_id] = (mech_target_pos.x(), mech_target_pos.y())
            elif mech_joint_id in self.sim_joints_config:
                self.sim_joints_config[mech_joint_id]["position"] = mech_target_pos

        for component in self.sim_selectable_components:
            target_ik_joint_abstract_name = component.get("targetJointId")
            if not target_ik_joint_abstract_name:
                continue

            part_name_for_path = component.get("partName")
            part_info = self.project_parts_data.get(part_name_for_path)

            target_std_id = self._get_standardized_joint_id(target_ik_joint_abstract_name)
            target_pos_on_path = None

            if target_std_id and target_std_id in self._mechanism_position_targets:
                target_pos_on_path = self._mechanism_position_targets[target_std_id]
            elif part_info and part_info.motion_path_data:
                motion_path_obj = part_info.motion_path_data
                target_pos_on_path = self._get_point_on_path(
                    motion_path_obj, self._current_animation_progress
                )

            if target_pos_on_path:
                target_std_id = self._get_standardized_joint_id(target_ik_joint_abstract_name)
                is_mechanism_controlled = target_std_id and target_std_id in self._mechanism_position_targets

                if is_mechanism_controlled:
                    mechanism_target_pos = self._mechanism_position_targets[target_std_id]
                    target_pos_on_path = mechanism_target_pos

                # Check if this is a two-bone IK chain
                if target_ik_joint_abstract_name in self.sim_two_bone_ik_effectors:
                    effector_limb_config = self.sim_limb_configs.get(
                        target_ik_joint_abstract_name
                    )
                    if not effector_limb_config:
                        continue

                    middle_joint_abstract_name = effector_limb_config.get("parentAnchor")
                    part_label_for_l2 = effector_limb_config.get("label")

                    if not middle_joint_abstract_name or not part_label_for_l2:
                        continue

                    middle_limb_config = self.sim_limb_configs.get(
                        middle_joint_abstract_name
                    )
                    if not middle_limb_config:
                        continue

                    root_joint_abstract_name = middle_limb_config.get("parentAnchor")
                    part_label_for_l1 = middle_limb_config.get("label")

                    if not root_joint_abstract_name or not part_label_for_l1:
                        continue

                    root_std_id = self._get_standardized_joint_id(
                        root_joint_abstract_name
                    )
                    middle_std_id = self._get_standardized_joint_id(
                        middle_joint_abstract_name
                    )
                    effector_std_id = self._get_standardized_joint_id(
                        target_ik_joint_abstract_name
                    )

                    if not root_std_id or not middle_std_id or not effector_std_id:
                        continue

                    if (
                        root_std_id not in self.sim_joints_config
                        or "position" not in self.sim_joints_config[root_std_id]
                    ):
                        continue
                    current_root_pos_for_ik = self.sim_joints_config[root_std_id][
                        "position"
                    ]

                    current_middle_pos = self.sim_joints_config[middle_std_id].get("position")
                    current_effector_pos = self.sim_joints_config[effector_std_id].get("position")

                    if current_middle_pos and current_effector_pos:
                        length1 = QLineF(current_root_pos_for_ik, current_middle_pos).length()
                        length2 = QLineF(current_middle_pos, current_effector_pos).length()
                    else:
                        length1 = self.sim_limb_lengths.get(part_label_for_l1)
                        length2 = self.sim_limb_lengths.get(part_label_for_l2)

                    original_length1 = self.sim_limb_lengths.get(part_label_for_l1)
                    original_length2 = self.sim_limb_lengths.get(part_label_for_l2)

                    if original_length1 and original_length1 > 0:
                        max_length1 = original_length1 * 1.1
                        min_length1 = original_length1 * 0.9
                        if length1 > max_length1:
                            length1 = max_length1
                        elif length1 < min_length1:
                            length1 = min_length1

                    if original_length2 and original_length2 > 0:
                        max_length2 = original_length2 * 1.1
                        min_length2 = original_length2 * 0.9
                        if length2 > max_length2:
                            length2 = max_length2
                        elif length2 < min_length2:
                            length2 = min_length2

                    if (
                        length1 is None
                        or length2 is None
                        or length1 <= 0
                        or length2 <= 0
                    ):
                        continue

                    solved_points = self._solve_two_bone_ik(
                        current_root_pos_for_ik,
                        target_pos_on_path,
                        length1,
                        length2,
                        root_std_id,
                    )

                    if solved_points:
                        p1_new, p2_new = solved_points
                        if middle_std_id in self.sim_joints_config:
                            self.sim_joints_config[middle_std_id]["position"] = p1_new

                        if effector_std_id in self.sim_joints_config:
                            self.sim_joints_config[effector_std_id]["position"] = p2_new

                        if is_mechanism_controlled and effector_std_id in self._mechanism_position_targets:
                            mechanism_exact_pos = self._mechanism_position_targets[effector_std_id]
                            if effector_std_id in self.sim_joints_config:
                                self.sim_joints_config[effector_std_id]["position"] = mechanism_exact_pos
                else:
                    limb_config = self.sim_limb_configs.get(
                        target_ik_joint_abstract_name
                    )
                    anchor_joint_abstract_name = (
                        limb_config.get("parentAnchor") if limb_config else None
                    )
                    if anchor_joint_abstract_name:
                        solved_single_bone_data = self._solve_single_bone_ik(
                            target_ik_joint_abstract_name,
                            anchor_joint_abstract_name,
                            np.array(
                                [target_pos_on_path.x(), target_pos_on_path.y()]
                            ),
                        )
                        if solved_single_bone_data:
                            for (
                                joint_std_id,
                                data_updates,
                            ) in solved_single_bone_data.items():
                                if joint_std_id in self.sim_joints_config:
                                    self.sim_joints_config[joint_std_id].update(
                                        data_updates
                                    )
                                else:
                                    self.sim_joints_config[joint_std_id] = (
                                        data_updates
                                    )
                    else:
                        target_std_id = self._get_standardized_joint_id(
                            target_ik_joint_abstract_name
                        )
                        if (
                            target_std_id
                            and target_std_id in self.sim_joints_config
                        ):
                            final_target_pos = target_pos_on_path

                            target_limb_config = self.sim_limb_configs.get(target_ik_joint_abstract_name)
                            anchor_joint_abstract = target_limb_config.get("parentAnchor") if target_limb_config else None

                            if anchor_joint_abstract:
                                anchor_std_id = self._get_standardized_joint_id(anchor_joint_abstract)
                                if anchor_std_id and anchor_std_id in self.sim_joints_config:
                                    anchor_pos = self.sim_joints_config[anchor_std_id]["position"]

                                    if (anchor_std_id in self.sim_joints_config and
                                        target_std_id in self.sim_joints_config):
                                        anchor_current = self.sim_joints_config[anchor_std_id].get("position")
                                        target_current = self.sim_joints_config[target_std_id].get("position")
                                        if anchor_current and target_current:
                                            original_bone_length = QLineF(anchor_current, target_current).length()

                                        if original_bone_length and original_bone_length > 0:
                                            current_distance = QLineF(anchor_pos, target_pos_on_path).length()
                                            min_length = original_bone_length * 0.9
                                            max_length = original_bone_length * 1.1

                                            if current_distance < min_length or current_distance > max_length:
                                                if current_distance > 1e-6:
                                                    clamped_length = max(min_length, min(max_length, current_distance))
                                                    direction_x = (target_pos_on_path.x() - anchor_pos.x()) / current_distance
                                                    direction_y = (target_pos_on_path.y() - anchor_pos.y()) / current_distance

                                                    final_target_pos = QPointF(
                                                        anchor_pos.x() + direction_x * clamped_length,
                                                        anchor_pos.y() + direction_y * clamped_length
                                                    )
                                                else:
                                                    final_target_pos = QPointF(anchor_pos.x(), anchor_pos.y() + original_bone_length)

                            self.sim_joints_config[target_std_id]["position"] = final_target_pos

        for mech_joint_id, mech_target_pos in self._mechanism_position_targets.items():
            if mech_joint_id in self.sim_joints_config:
                self.sim_joints_config[mech_joint_id]["position"] = mech_target_pos

        for joint_std_id, joint_data in self.sim_joints_config.items():
            pos = joint_data.get("position")
            if pos is not None and hasattr(pos, 'x') and hasattr(pos, 'y'):
                if joint_std_id in self.dynamic_joints:
                    self.dynamic_joints[joint_std_id] = (pos.x(), pos.y())
                else:
                    self.dynamic_joints[joint_std_id] = (pos.x(), pos.y())

        self._recalculate_all_bone_angles_after_ik()

        self._update_character_part_visuals_from_ik()

        animated_joint_scene_positions: dict[str, tuple[float, float]] = {}
        if self.sim_joints_config:
            for joint_std_id, joint_data in self.sim_joints_config.items():
                pos = joint_data.get("position")
                if pos is not None:
                    animated_joint_scene_positions[joint_std_id] = (pos.x(), pos.y())

        if animated_joint_scene_positions:
            self.skeleton_pose_updated.emit(animated_joint_scene_positions)

    def get_world_rotation_degrees(self, transform: QTransform) -> float:
        """Extracts rotation in degrees from a QTransform object."""
        angle_rad = math.atan2(transform.m21(), transform.m11())
        return math.degrees(angle_rad)

    @property
    def dynamic_joints(self) -> dict[str, dict[str, Any]]:
        return self._sim_dynamic_joints_data

    @dynamic_joints.setter
    def dynamic_joints(self, value: dict[str, dict[str, Any]]):
        self._sim_dynamic_joints_data = value

    def _recalculate_all_bone_angles_after_ik(self):
        """Recalculate all bone angles after IK position updates to ensure natural skeleton movement."""
        if not self.sim_joints_config or not self._initial_snapshot:
            return

        def angle_between_points(p1, p2):
            """Calculate angle from p1 to p2 in degrees"""
            return math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))

        angles_updated = 0

        for eff_abs, limb_config in self.sim_limb_configs.items():
            part_name = limb_config.get("label")
            parent_abs = limb_config.get("parentAnchor")

            if not (part_name and parent_abs):
                continue

            parent_std_id = self._get_standardized_joint_id(parent_abs)
            child_std_id = self._get_standardized_joint_id(eff_abs)

            if not (parent_std_id and child_std_id):
                continue

            parent_pos = self.sim_joints_config.get(parent_std_id, {}).get("position")
            child_pos = self.sim_joints_config.get(child_std_id, {}).get("position")

            if not (parent_pos and child_pos):
                continue

            current_angle = angle_between_points(parent_pos, child_pos)

            initial_parent_pos = None
            initial_child_pos = None
            if parent_std_id in self._initial_snapshot:
                initial_parent_pos = self._initial_snapshot[parent_std_id].get("position")
            if child_std_id in self._initial_snapshot:
                initial_child_pos = self._initial_snapshot[child_std_id].get("position")

            initial_angle = 0.0
            if initial_parent_pos and initial_child_pos:
                initial_angle = angle_between_points(initial_parent_pos, initial_child_pos)

            angle_delta = current_angle - initial_angle

            if child_std_id in self.sim_joints_config:
                new_angle = 0.0 + angle_delta
                self.sim_joints_config[child_std_id]["angle"] = new_angle
                angles_updated += 1

        for joint_std_id, joint_data in self.sim_joints_config.items():
            if "angle" not in joint_data:
                continue

            handled_by_limb = False
            for limb_config in self.sim_limb_configs.values():
                if self._get_standardized_joint_id(limb_config.get("parentAnchor")) == joint_std_id:
                    handled_by_limb = True
                    break

            if not handled_by_limb:
                current_pos = joint_data.get("position")
                if current_pos and joint_std_id in self._initial_snapshot:
                    initial_pos = self._initial_snapshot[joint_std_id].get("position")
                    if initial_pos:
                        dx = current_pos.x() - initial_pos.x()
                        dy = current_pos.y() - initial_pos.y()
                        if dx != 0 or dy != 0:
                            movement_angle = math.degrees(math.atan2(dy, dx))
                            initial_angle = self._initial_snapshot[joint_std_id].get("angle", 0.0)
                            new_angle = initial_angle + movement_angle
                            self.sim_joints_config[joint_std_id]["angle"] = new_angle

    def update_part_motion_path(self, part_name: str, motion_qpath: QPainterPath):
        """Updates the motion path for a specific part in the IKManager's project_parts_data."""
        if not self.project_parts_data:
            self._pending_motion_paths[part_name] = motion_qpath
            return

        if part_name in self.project_parts_data:
            part_info = self.project_parts_data[part_name]
            part_info.motion_path_data = motion_qpath
        else:
            self._pending_motion_paths[part_name] = motion_qpath

        self._try_initialize_solver()


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)

    class MockMainWindow(QObject):
        def __init__(self):
            super().__init__()
            self.skeleton_manager_ref = None
            self.project_parts_data = {
                "left_arm_lower": {
                    "motion_path_data": [
                        QPointF(10, 10),
                        QPointF(20, 20),
                        QPointF(10, 30),
                    ],
                    "name": "left_arm_lower",
                }
            }
            self.editor_tab = type(
                "MockEditorTab",
                (object,),
                {
                    "on_simulation_state_changed": lambda self,
                    is_playing,
                    can_reset: logging.debug(
                        f"MockEditorTab: Sim state changed: playing={is_playing}, can_reset={can_reset}"
                    )
                },
            )()

        def statusBar(self):
            class MockStatusBar:
                def showMessage(self, msg, timeout=0):
                    logging.debug(f"STATUS: {msg}")

            return MockStatusBar()

    class MockSkeletonManagerForIK(QObject):
        skeleton_updated = pyqtSignal(dict)

        def __init__(self):
            super().__init__()
            self.standardized_model_instance: StandardizedSkeletonModel | None = None

        def load_and_emit_sample_skeleton(self):
            sample_joints = {
                "std_hip": StandardizedJointModel(
                    id="std_hip",
                    name="Hip",
                    position=(50, 200),
                    parent_id=None,
                    label="hip_cfg",
                ),
                "std_lshoulder": StandardizedJointModel(
                    id="std_lshoulder",
                    name="LShoulder",
                    position=(30, 180),
                    parent_id="std_hip",
                    label="left_shoulder_cfg",
                ),
                "std_lelbow": StandardizedJointModel(
                    id="std_lelbow",
                    name="LElbow",
                    position=(10, 180),
                    parent_id="std_lshoulder",
                    label="left_elbow_cfg",
                ),
                "std_lhand": StandardizedJointModel(
                    id="std_lhand",
                    name="LHand",
                    position=(-10, 180),
                    parent_id="std_lelbow",
                    label="left_hand_cfg",
                ),
            }
            sample_model = StandardizedSkeletonModel(
                joints=sample_joints,
                root_joint_ids=["std_hip"],
                hierarchy={
                    "std_hip": ["std_lshoulder"],
                    "std_lshoulder": ["std_lelbow"],
                    "std_lelbow": ["std_lhand"],
                },
                joint_map={
                    "hip": "std_hip",
                    "left_shoulder": "std_lshoulder",
                    "left_elbow": "std_lelbow",
                    "left_hand": "std_lhand",
                },
                limb_lengths={
                    "left_upper_arm": 20.0,
                    "left_forearm": 20.0,
                },
            )
            self.standardized_model_instance = sample_model
            self.skeleton_updated.emit(sample_model.model_dump())

    mock_main = MockMainWindow()
    ik_manager = IKManager(main_window_ref=mock_main)

    mock_skeleton_manager = MockSkeletonManagerForIK()
    ik_manager.set_skeleton_manager(mock_skeleton_manager)

    ik_manager.set_project_parts_data(mock_main.project_parts_data)

    mock_skeleton_manager.load_and_emit_sample_skeleton()

    if ik_manager.ik_solver_initialized:
        ik_manager.set_animation_duration(1000)
        if ik_manager.start_animation():
            QTimer.singleShot(1200, ik_manager.stop_animation)
            QTimer.singleShot(1300, ik_manager.reset_animation_state)
            QTimer.singleShot(1500, app.quit)
            sys.exit(app.exec())
        else:
            app.quit()
    else:
        app.quit()
