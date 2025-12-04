"""
Inverse Kinematics (IK) Manager for Automataii.

This class orchestrates IK-related functionality, delegating to specialized
components for specific responsibilities:

- IKSolverCore: Pure domain IK solving algorithms
- IKAnimationController: Animation timing and easing
- IKVisualUpdater: Visual state computation
- IKPathHandler: Motion path operations
- Joint configuration: From domain/kinematics/joint_config.py

Design Pattern: Facade (orchestrates multiple IK subsystems)
"""

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from PyQt6.QtCore import QElapsedTimer, QLineF, QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainterPath

# Domain components (pure logic, no Qt dependency)
from automataii.domain.kinematics import (
    IK_JOINT_TO_SOURCE_NAME,
    IK_PART_TO_ACTUAL_PART,
    IKAnimationController,
)
from automataii.domain.skeleton import (
    StandardizedJointModel,
    StandardizedSkeletonModel,
)

# Presentation components (Qt-coupled)
from automataii.presentation.qt.kinematics.components import (
    BendDirectionManager,
    IKPathHandler,
    TwoBoneIKSolver,
)
from automataii.presentation.qt.models import PartInfo

from ..graphics_items.part_item import CharacterPartItem

# Use module-level logger for fine-grained control
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from automataii.application.managers import SkeletonManager


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

        # --- State Data ---
        self.sim_joints_config: dict[str, dict[str, Any]] = {}
        self.sim_limb_configs: dict[str, dict[str, Any]] = {}
        self.sim_limb_lengths: dict[str, float] = {}
        self.sim_selectable_components: list[dict[str, Any]] = []
        self.sim_two_bone_ik_effectors: list[str] = []
        # sim_joint_bend_directions is now a property delegating to _bend_direction_manager
        self._sim_dynamic_joints_data: dict[str, dict[str, Any]] = {}
        self.scene_joints_snapshot: dict[str, Any] = {}

        # --- Use domain constants for joint mappings (SRP extraction) ---
        self.ik_part_to_actual_part_name: dict[str, str] = dict(IK_PART_TO_ACTUAL_PART)
        self.ik_joint_ids_to_source_names: dict[str, str] = dict(IK_JOINT_TO_SOURCE_NAME)

        # --- Extracted Components (SRP) ---
        self._path_handler = IKPathHandler()
        self._two_bone_solver = TwoBoneIKSolver()
        self._bend_direction_manager = BendDirectionManager()

        self._active_path_definition_target_joint_id: str | None = None

        # --- Animation Timer ---
        self.ik_animation_timer = QTimer(self)
        self.ik_animation_timer.setInterval(30)
        self.ik_animation_timer.timeout.connect(self._run_ik_animation_step)

        self.ik_animation_speed: float = 0.5
        self.animation_duration: int = 3000
        self._animation_start_time_qelapsed: QElapsedTimer | None = None
        self._current_animation_progress: float = 0.0
        self._timing_profile: str = "linear"  # linear | ease_in | ease_out | ease_in_out

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

        # Extracted components (god class decomposition)
        self._animation_controller = IKAnimationController()
        self._animation_controller.duration_ms = self.animation_duration

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
        self.__internal_current_skeleton_data = value

    def set_animation_duration(self, duration_ms: int):
        """Sets the total duration for one loop of the IK animation. Delegates to IKAnimationController."""
        if duration_ms > 0:
            self.animation_duration = duration_ms
            if hasattr(self, '_animation_controller'):
                self._animation_controller.duration_ms = duration_ms

    def set_timing_profile(self, profile: str):
        """Set timing profile. Delegates to IKAnimationController."""
        if hasattr(self, '_animation_controller'):
            self._animation_controller.timing_profile = profile
        # Keep legacy field for backwards compatibility
        allowed = {"linear", "ease_in", "ease_out", "ease_in_out"}
        p = str(profile).lower().replace('-', '_').replace(' ', '_')
        self._timing_profile = p if p in allowed else "linear"

    def _apply_timing_curve(self, t: float) -> float:
        """Apply timing curve. Delegates to IKAnimationController."""
        return self._animation_controller.apply_timing(max(0.0, min(1.0, t)))

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
        Refactored to reduce cyclomatic complexity (C901) by extracting helper methods.

        Returns:
            True if successful, False otherwise.
        """
        if not self._current_skeleton_data or not self._current_skeleton_data.get("joints"):
            return False
        if not self.project_parts_data:
            return False

        self.ik_solver = "DummySolver"

        # Step 1: Setup joint configs from skeleton data
        self._setup_joint_configs_from_skeleton()

        # Step 2: Define IK selectable components and limb configs
        self._define_ik_components()

        # Step 3: Initialize bend directions for middle joints
        self._initialize_bend_directions()

        # Step 4: Initialize rest angles
        if not hasattr(self, "sim_joint_rest_angles"):
            self.sim_joint_rest_angles = {
                "left_shoulder": 180.0,
                "right_shoulder": 0.0,
                "left_hip": -90.0,
                "right_hip": -90.0,
            }

        # Step 5: Calculate limb lengths
        self._calculate_limb_lengths()

        return True

    def _setup_joint_configs_from_skeleton(self) -> None:
        """
        Setup joint configurations from skeleton data.

        Populates sim_joints_config and _sim_dynamic_joints_data from skeleton joints.
        Calculates initial angles and creates initial snapshot.
        """
        self._sim_dynamic_joints_data.clear()
        self.sim_joints_config.clear()
        self._initial_snapshot.clear()

        # Populate joint configs from skeleton
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

                # Add to dynamic joints (excluding static joints)
                if not self._is_static_joint(joint_id):
                    self._sim_dynamic_joints_data[joint_id] = self.sim_joints_config[joint_id].copy()

        # Calculate angles from parent-child relationships
        for _joint_id, joint_data in self.sim_joints_config.items():
            parent_id = joint_data.get("parent")
            if parent_id and parent_id in self.sim_joints_config:
                parent_pos = self.sim_joints_config[parent_id]["position"]
                child_pos = joint_data["position"]

                dx = child_pos.x() - parent_pos.x()
                dy = child_pos.y() - parent_pos.y()
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)

                joint_data["angle"] = angle_deg

        # Create initial snapshot
        self._initial_snapshot = {
            name: data.copy() for name, data in self.sim_joints_config.items()
        }

    def _is_static_joint(self, joint_id: str) -> bool:
        """Check if a joint is static (shouldn't be in dynamic joints)."""
        joint_lower = joint_id.lower()
        return (
            "hip" in joint_lower
            or "neck" in joint_lower
            or joint_lower == "head"
            or joint_lower == "torso"
        )

    def _define_ik_components(self) -> None:
        """
        Define IK selectable components, effectors, and limb configurations.

        Sets up sim_selectable_components, sim_two_bone_ik_effectors, and sim_limb_configs.
        """
        self.sim_selectable_components = [
            {"name": "Head Control", "partName": "head", "targetJointId": "neck"},
            {"name": "Left Hand Control", "partName": "left_arm_lower", "targetJointId": "left_hand"},
            {"name": "Right Hand Control", "partName": "right_arm_lower", "targetJointId": "right_hand"},
            {"name": "Left Foot Control", "partName": "left_leg_lower", "targetJointId": "left_foot"},
            {"name": "Right Foot Control", "partName": "right_leg_lower", "targetJointId": "right_foot"},
            {"name": "Torso Control", "partName": "torso", "targetJointId": "torso"},
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

    def _initialize_bend_directions(self) -> None:
        """
        Initialize bend directions for middle joints (elbows and knees).

        Uses skeleton data if available, preserves existing values, or calculates geometrically.
        """
        # Initialize if doesn't exist
        if not hasattr(self, 'sim_joint_bend_directions'):
            self.sim_joint_bend_directions = {}

        # Preserve existing bend directions
        existing_bend_directions = self.sim_joint_bend_directions.copy()

        logger.debug("IKManager._initialize_bend_directions: Existing: %s", existing_bend_directions)
        if self._current_skeleton_data and "joint_map" in self._current_skeleton_data:
            logger.debug("IKManager._initialize_bend_directions: joint_map = %s", self._current_skeleton_data['joint_map'])

        middle_joints = ["left_elbow", "right_elbow", "left_knee", "right_knee"]

        for middle_joint_name in middle_joints:
            self._initialize_single_bend_direction(middle_joint_name, existing_bend_directions)

        logger.debug("IKManager._initialize_bend_directions: Final = %s", self.sim_joint_bend_directions)

    def _initialize_single_bend_direction(
        self, middle_joint_name: str, existing_directions: dict[str, int]
    ) -> None:
        """Initialize bend direction for a single middle joint."""
        logger.debug("IKManager: Processing joint '%s'", middle_joint_name)

        std_id = self._get_standardized_joint_id(middle_joint_name)
        logger.debug("IKManager: '%s' -> standardized ID: '%s'", middle_joint_name, std_id)

        if not std_id or std_id not in self.sim_joints_config:
            logging.warning(f"IKManager: Could not find standardized ID for '{middle_joint_name}'")
            return

        # Priority 1: Use bend_direction from skeleton data
        bend_dir = self._get_bend_direction_from_skeleton_joint(std_id)
        if bend_dir is not None:
            self._store_bend_direction(middle_joint_name, std_id, bend_dir)
            logger.debug("IKManager: Using skeleton bend_direction %s for '%s'", bend_dir, middle_joint_name)
            return

        # Priority 2: Preserve existing bend direction
        if middle_joint_name in existing_directions:
            self._store_bend_direction(middle_joint_name, std_id, existing_directions[middle_joint_name])
            logger.debug("IKManager: Preserving existing %s for '%s'", existing_directions[middle_joint_name], middle_joint_name)
            return
        if std_id in existing_directions:
            self._store_bend_direction(middle_joint_name, std_id, existing_directions[std_id])
            logger.debug("IKManager: Preserving existing %s for '%s'", existing_directions[std_id], std_id)
            return

        # Priority 3: Calculate geometrically
        direction = self._calculate_bend_direction_geometrically(middle_joint_name, std_id)
        if direction is not None:
            self._store_bend_direction(middle_joint_name, std_id, direction)
            logger.debug("IKManager: Calculated bend_direction = %s for '%s'", direction, middle_joint_name)

    def _get_bend_direction_from_skeleton_joint(self, std_id: str) -> int | None:
        """Get bend direction from skeleton data if available."""
        if not self._current_skeleton_data or "joints" not in self._current_skeleton_data:
            return None
        joint_data = self._current_skeleton_data["joints"].get(std_id, {})
        bend_dir = joint_data.get("bend_direction")
        logger.debug("IKManager: Skeleton bend_direction for '%s': %s", std_id, bend_dir)
        return bend_dir

    def _store_bend_direction(self, abstract_name: str, std_id: str, direction: int) -> None:
        """Store bend direction for both abstract name and standardized ID."""
        self.sim_joint_bend_directions[abstract_name] = direction
        if std_id:
            self.sim_joint_bend_directions[std_id] = direction

    def _calculate_bend_direction_geometrically(
        self, middle_joint_name: str, std_id: str
    ) -> int | None:
        """Calculate bend direction geometrically using cross product."""
        logger.debug("IKManager: Calculating bend_direction geometrically for '%s'", middle_joint_name)
        p1_pos = self.sim_joints_config[std_id]["position"]

        # Get parent joint position
        limb_config = self.sim_limb_configs.get(middle_joint_name)
        if not limb_config:
            return None
        parent_name = limb_config.get("parentAnchor")
        if not parent_name:
            return None
        parent_std_id = self._get_standardized_joint_id(parent_name)
        if not parent_std_id or parent_std_id not in self.sim_joints_config:
            return None
        p0_pos = self.sim_joints_config[parent_std_id]["position"]

        # Get child joint position
        child_std_id = self._find_child_joint_id(middle_joint_name)
        if not child_std_id or child_std_id not in self.sim_joints_config:
            return None
        p2_pos = self.sim_joints_config[child_std_id]["position"]

        # Calculate cross product for bend direction
        vec_to_root = p0_pos - p1_pos
        vec_to_end = p2_pos - p1_pos
        cross_product = (vec_to_root.x() * vec_to_end.y()) - (vec_to_root.y() * vec_to_end.x())

        if abs(cross_product) < 1e-4:
            return 1 if "left" in middle_joint_name else -1
        return -1 if cross_product > 0 else 1

    def _find_child_joint_id(self, middle_joint_name: str) -> str | None:
        """Find the child joint ID for a middle joint."""
        for effector_name, config in self.sim_limb_configs.items():
            if config.get("parentAnchor") == middle_joint_name:
                return self._get_standardized_joint_id(effector_name)
        return None

    def _calculate_limb_lengths(self) -> None:
        """Calculate limb lengths from joint positions or part ROI data."""
        self.sim_limb_lengths.clear()

        for limb_key, config in self.sim_limb_configs.items():
            part_label = config.get("label")
            parent_anchor = config.get("parentAnchor")

            if not part_label:
                continue

            # Try to calculate from joint positions
            length = self._calculate_length_from_joints(limb_key, parent_anchor)
            if length is not None and length > 0:
                self.sim_limb_lengths[part_label] = length
                continue

            # Fallback to part ROI data
            length = self._calculate_length_from_part_roi(part_label)
            self.sim_limb_lengths[part_label] = length if length > 0 else 50

    def _calculate_length_from_joints(
        self, child_key: str, parent_anchor: str | None
    ) -> float | None:
        """Calculate bone length from joint positions."""
        if not parent_anchor or not self.sim_joints_config:
            return None

        child_std_id = self._get_standardized_joint_id(child_key)
        parent_std_id = self._get_standardized_joint_id(parent_anchor)

        if not (child_std_id and parent_std_id):
            return None
        if child_std_id not in self.sim_joints_config:
            return None
        if parent_std_id not in self.sim_joints_config:
            return None

        child_pos = self.sim_joints_config[child_std_id].get("position")
        parent_pos = self.sim_joints_config[parent_std_id].get("position")

        if child_pos and parent_pos:
            return QLineF(parent_pos, child_pos).length()
        return None

    def _calculate_length_from_part_roi(self, part_label: str) -> float:
        """Calculate length from part ROI data."""
        if part_label not in self.project_parts_data:
            return 0

        part_info = self.project_parts_data[part_label]
        if part_info.roi and len(part_info.roi) == 4:
            return float(part_info.roi[3])
        return 0

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
                        logger.debug("IKManager.on_skeleton_data_updated: Joint '%s' has bend_direction = %s", joint_id, bend_dir)

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
                        logger.debug("IKManager.on_skeleton_data_updated (after model_dump): Joint '%s' has bend_direction = %s", joint_id, bend_dir)

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
        # Try skeleton_manager first (most authoritative source)
        if self._try_update_bend_directions_from_manager():
            return

        # Fallback to skeleton data
        self._update_bend_directions_from_skeleton_data()

    def _try_update_bend_directions_from_manager(self) -> bool:
        """Try to update bend directions from skeleton_manager. Returns True if successful."""
        if not self.skeleton_manager_ref:
            return False

        logger.debug("IKManager: Getting bend directions from skeleton_manager")
        bend_directions = self.skeleton_manager_ref.get_all_joint_bend_directions()

        if not bend_directions:
            return False

        self.sim_joint_bend_directions.clear()
        self._apply_bend_directions(bend_directions, "skeleton_manager")
        logger.debug("IKManager: Final bend_directions from skeleton_manager = %s", self.sim_joint_bend_directions)
        return True

    def _update_bend_directions_from_skeleton_data(self) -> None:
        """Update bend directions from skeleton data (fallback)."""
        if not self._current_skeleton_data or "joints" not in self._current_skeleton_data:
            logging.warning("IKManager: No skeleton data available for bend directions")
            return

        logger.debug("IKManager: Using skeleton data (fallback)...")

        # Clear existing directions
        old_directions = self.sim_joint_bend_directions.copy()
        self.sim_joint_bend_directions.clear()
        logger.debug("IKManager: Cleared old directions: %s", old_directions)

        # Extract bend directions from skeleton joints
        bend_directions = {}
        for joint_id, joint_data in self._current_skeleton_data["joints"].items():
            bend_dir = joint_data.get("bend_direction")
            if bend_dir is not None:
                bend_directions[joint_id] = bend_dir

        self._apply_bend_directions(bend_directions, "skeleton_data")
        logger.debug("IKManager: Final bend_directions = %s", self.sim_joint_bend_directions)

        self._warn_unexpected_bend_directions()

    def _apply_bend_directions(self, bend_directions: dict[str, int], source: str) -> None:
        """Apply bend directions to sim_joint_bend_directions."""
        for joint_id, bend_dir in bend_directions.items():
            self.sim_joint_bend_directions[joint_id] = bend_dir

            # Also store with abstract name for compatibility
            if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                abstract_name = '_'.join(joint_id.split('_')[:-1])
                self.sim_joint_bend_directions[abstract_name] = bend_dir

            if 'elbow' in joint_id or 'knee' in joint_id:
                logger.debug("IKManager: Updated bend_direction for '%s' to %s from %s", joint_id, bend_dir, source)

    def _warn_unexpected_bend_directions(self) -> None:
        """Warn about unexpected joints having bend directions."""
        unexpected_joints = ('shoulder', 'hip', 'torso', 'neck', 'hand', 'foot', 'root')
        for key, value in self.sim_joint_bend_directions.items():
            if any(joint in key for joint in unexpected_joints):
                logging.warning(f"IKManager: Unexpected joint '{key}' has bend_direction = {value}")

    def _clear_ik_definitions(self, emit_signal=True, preserve_bend_directions=False) -> None:
        """Clears IK solver-derived configurations and resets animation state."""
        self.stop_animation()
        self.ik_solver = None

        # Save bend directions if needed
        saved_directions = self._save_bend_directions() if preserve_bend_directions else {}

        # Clear all config dictionaries
        self._clear_config_dicts()

        # Restore saved bend directions
        if saved_directions:
            self.sim_joint_bend_directions.update(saved_directions)

        if emit_signal:
            self.ik_solver_initialized.emit(False, {})

    def _save_bend_directions(self) -> dict[str, int]:
        """Save current bend directions for preservation."""
        if hasattr(self, "sim_joint_bend_directions"):
            return self.sim_joint_bend_directions.copy()
        return {}

    def _clear_config_dicts(self) -> None:
        """Clear all IK configuration dictionaries."""
        attrs_to_clear = [
            "_sim_dynamic_joints_data",
            "sim_joints_config",
            "sim_limb_configs",
            "sim_limb_lengths",
            "scene_joints_snapshot",
            "sim_selectable_components",
            "sim_two_bone_ik_effectors",
            "sim_joint_bend_directions",
        ]
        for attr in attrs_to_clear:
            if hasattr(self, attr):
                getattr(self, attr).clear()

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
        Delegates to TwoBoneIKSolver component.

        Returns (middle_joint_pos, end_effector_pos) or None if unsolvable.
        """
        # Find bend direction for this limb
        bend_direction = self._get_bend_direction_for_root(root_joint_std_id)

        # Update solver rest angles from current state
        if hasattr(self, "sim_joint_rest_angles"):
            self._two_bone_solver.set_rest_angles(self.sim_joint_rest_angles)

        # Delegate to solver
        result = self._two_bone_solver.solve(
            root_pos=root_pos,
            target_pos=target_pos,
            length1=length1,
            length2=length2,
            bend_direction=bend_direction,
            root_joint_id=root_joint_std_id,
        )

        if result:
            return result.middle_pos, result.end_pos
        return None

    def _get_bend_direction_for_root(self, root_joint_std_id: str) -> float:
        """
        Get bend direction for a limb based on its root joint.
        Delegates to BendDirectionManager.
        """
        hierarchy = None
        if self._current_skeleton_data and "hierarchy" in self._current_skeleton_data:
            hierarchy = self._current_skeleton_data.get("hierarchy", {})

        return self._bend_direction_manager.get_for_root_joint(root_joint_std_id, hierarchy)

    def _apply_ik_to_limb_chains(
        self, editor_items: dict[str, CharacterPartItem]
    ) -> None:
        """Applies FABRIK IK to arm and leg chains to maintain proper joint constraints."""
        from .fabraik_solver import (
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

        for _effector_joint, chain_config in limb_chains.items():
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

            # Get bend directions formatted for FABRIK (abstract names like 'left_elbow')
            converted_bend_directions = self._bend_direction_manager.get_for_fabrik()

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
        if not (self._current_skeleton_data and "joint_map" in self._current_skeleton_data):
            logging.error("IKManager FK: Missing skeleton data or joint_map for FK update.")
            return

        if hasattr(self.main_window, "editor_tab") and self.main_window.editor_tab:
            editor_items = self.main_window.editor_tab.current_editor_items
            self._apply_ik_to_limb_chains(editor_items)

        updated: dict[str, dict[str, Any]] = {}
        processed_parts: set[str] = set()

        # Process limb configurations
        self._update_limb_visuals(updated, processed_parts)

        # Process remaining selectable components
        self._update_component_visuals(updated, processed_parts)

        if updated:
            self.character_visuals_updated.emit(updated)

    def _get_joint_position(self, joint_id: str) -> QPointF | None:
        """Get position for a joint from sim_joints_config."""
        return self.sim_joints_config.get(joint_id, {}).get("position")

    def _get_initial_joint_angle(self, joint_id: str) -> float:
        """Get initial angle for a joint from the snapshot."""
        if self._initial_snapshot and joint_id in self._initial_snapshot:
            return self._initial_snapshot[joint_id].get("angle", 0.0)
        return 0.0

    def _angle_between_points(self, p1: QPointF, p2: QPointF) -> float:
        """Calculate angle between two points in degrees."""
        return math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))

    def _update_limb_visuals(
        self, updated: dict[str, dict[str, Any]], processed_parts: set[str]
    ) -> None:
        """Update visuals for limb configurations."""
        for eff_abs, limb in self.sim_limb_configs.items():
            part_name = limb.get("label")
            parent_id = self._get_standardized_joint_id(limb.get("parentAnchor"))
            child_id = self._get_standardized_joint_id(eff_abs)

            if not (part_name and parent_id and child_id):
                continue

            p_parent = self._get_joint_position(parent_id)
            p_child = self._get_joint_position(child_id)
            if not (p_parent and p_child):
                continue

            # Calculate rotation delta from initial
            current_angle = self._angle_between_points(p_parent, p_child)
            initial_angle = self._get_initial_limb_angle(parent_id, child_id)
            rotation_delta = current_angle - initial_angle

            updated[parent_id] = {
                "scene_position": p_parent,
                "world_rotation_degrees": rotation_delta,
            }

            child_current = self.sim_joints_config[child_id].get("angle", 0.0)
            child_initial = self._get_initial_joint_angle(child_id)
            updated[child_id] = {
                "scene_position": p_child,
                "world_rotation_degrees": child_current - child_initial,
            }
            processed_parts.add(part_name)

    def _get_initial_limb_angle(self, parent_id: str, child_id: str) -> float:
        """Get initial angle between parent and child joints."""
        if not self._initial_snapshot:
            return 0.0
        parent_pos = self._initial_snapshot.get(parent_id, {}).get("position")
        child_pos = self._initial_snapshot.get(child_id, {}).get("position")
        if parent_pos and child_pos:
            return self._angle_between_points(parent_pos, child_pos)
        return 0.0

    def _update_component_visuals(
        self, updated: dict[str, dict[str, Any]], processed_parts: set[str]
    ) -> None:
        """Update visuals for selectable components not yet processed."""
        for comp in self.sim_selectable_components:
            part_name = comp.get("partName")
            if not part_name or part_name in processed_parts:
                continue

            jid = self._get_standardized_joint_id(comp.get("targetJointId"))
            pj = self._get_joint_position(jid)
            if not (jid and pj):
                continue

            # Calculate current angle
            current_angle = self.sim_joints_config[jid].get("angle", 0.0)
            parent_id = self.sim_joints_config[jid].get("parent")
            if parent_id:
                parent_pos = self._get_joint_position(parent_id)
                if parent_pos:
                    current_angle = self._angle_between_points(parent_pos, pj)

            # Calculate rotation delta
            initial_angle = self._get_initial_joint_angle(jid)
            rotation_delta = current_angle - initial_angle

            updated[jid] = {
                "scene_position": pj,
                "world_rotation_degrees": rotation_delta,
            }
            processed_parts.add(part_name)

    def start_animation(self) -> bool:
        """Starts the IK-driven animation.

        Returns:
            True if animation started successfully, False otherwise.
        """
        try:
            self.main_window.statusBar().showMessage("Playing IK Animation...", 2000)

            # CRITICAL FIX: Update bend directions from skeleton before starting animation
            # This ensures user-set bend directions are used during animation
            if hasattr(self, 'sim_joint_bend_directions') and self._current_skeleton_data:
                self._update_bend_directions_from_skeleton()
                logger.debug("IKManager.start_animation: Updated bend directions: %s", self.sim_joint_bend_directions)

            if self._animation_start_time_qelapsed is None:
                self._animation_start_time_qelapsed = QElapsedTimer()
            self._animation_start_time_qelapsed.start()
            self._current_animation_progress = 0.0

            if not self.ik_animation_timer.isActive():
                self.ik_animation_timer.start()

            self.animation_state_changed.emit("playing")
            return True

        except Exception as e:
            logger.error(f"Failed to start animation: {e}", exc_info=True)
            # Ensure timer is stopped on error
            if self.ik_animation_timer.isActive():
                self.ik_animation_timer.stop()
            self.animation_state_changed.emit("error")
            return False

    def stop_animation(self):
        """Stops the IK-driven animation."""
        if self.ik_animation_timer.isActive():
            self.ik_animation_timer.stop()
            self.main_window.statusBar().showMessage("IK Animation stopped.", 2000)
        self.animation_state_changed.emit("stopped")

    def reset_animation_state(self) -> bool:
        """Resets the animation state to initial state.

        Returns:
            True if reset successful, False otherwise.
        """
        # Always stop animation first
        self.stop_animation()

        if not self._initial_snapshot:
            logger.warning("Cannot reset animation: no initial snapshot available")
            return False

        try:
            # Restore joint configs from snapshot
            self._restore_joint_configs_from_snapshot()

            # Restore bend directions from skeleton_manager
            self._restore_bend_directions_from_manager()

            # Restore editor items to initial state
            self._restore_editor_items_to_initial()

            self._current_animation_progress = 0.0
            self._update_character_part_visuals_from_ik()

            self.main_window.statusBar().showMessage("IK Animation reset to initial pose.", 2000)
            self.animation_state_changed.emit("reset")
            return True

        except Exception as e:
            logger.error(f"Failed to reset animation state: {e}", exc_info=True)
            self.animation_state_changed.emit("error")
            return False

    def _restore_joint_configs_from_snapshot(self) -> None:
        """Restore joint configs from initial snapshot."""
        self.sim_joints_config = {
            k: v.copy() for k, v in self._initial_snapshot.items()
        }
        self._sim_dynamic_joints_data = {
            k: v.copy()
            for k, v in self._initial_snapshot.items()
            if k in self._sim_dynamic_joints_data
        }

    def _restore_bend_directions_from_manager(self) -> None:
        """Restore bend directions from skeleton_manager."""
        if not self.skeleton_manager_ref:
            return

        bend_directions = self.skeleton_manager_ref.get_all_joint_bend_directions()
        if not bend_directions:
            return

        logger.debug("IKManager.reset: Restoring bend directions: %s", bend_directions)
        self.sim_joint_bend_directions.clear()

        for joint_id, bend_dir in bend_directions.items():
            self.sim_joint_bend_directions[joint_id] = bend_dir

            # Also store with abstract name for compatibility
            if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                abstract_name = '_'.join(joint_id.split('_')[:-1])
                self.sim_joint_bend_directions[abstract_name] = bend_dir

            logger.debug("IKManager.reset: Restored bend_direction for '%s' to %s", joint_id, bend_dir)

    def _restore_editor_items_to_initial(self) -> None:
        """Restore editor items to their initial positions and rotations."""
        if not hasattr(self.main_window, "editor_tab") or not self.main_window.editor_tab:
            return

        editor_items = self.main_window.editor_tab.current_editor_items
        for part_name, part_item in editor_items.items():
            self._restore_single_editor_item(part_name, part_item)

    def _restore_single_editor_item(self, part_name: str, part_item: Any) -> None:
        """Restore a single editor item to its initial state."""
        # Restore rotation
        initial_rotation = getattr(part_item, "_initial_world_rotation", 0.0)
        part_item.setRotation(initial_rotation)

        if part_name not in self.project_parts_data:
            return

        # Restore position from part info
        part_info = self.project_parts_data[part_name]
        if hasattr(part_info, "x") and hasattr(part_info, "y"):
            part_item.setPos(QPointF(part_info.x, part_info.y))

        # Restore position from joint snapshot
        self._restore_item_position_from_joint(part_name, part_item)

    def _restore_item_position_from_joint(self, part_name: str, part_item: Any) -> None:
        """Restore item position from its associated joint in the snapshot."""
        for comp in self.sim_selectable_components:
            if comp.get("partName") != part_name:
                continue

            target_joint_id = comp.get("targetJointId")
            if not target_joint_id:
                continue

            std_joint_id = self._get_standardized_joint_id(target_joint_id)
            if not std_joint_id or std_joint_id not in self._initial_snapshot:
                continue

            joint_pos = self._initial_snapshot[std_joint_id].get("position")
            if joint_pos:
                part_item.set_scene_position_from_anchor(joint_pos, bypass_validation=True)
                break

    def _extract_points_from_painter_path(self, painter_path) -> list[QPointF]:
        """Extracts QPointF coordinates from a QPainterPath. Delegates to IKPathHandler."""
        return self._path_handler.extract_points_from_painter_path(painter_path)

    def _get_point_on_path(self, path_obj: Any, progress: float) -> QPointF | None:
        """Get interpolated point on path. Delegates to IKPathHandler."""
        return self._path_handler.get_point_on_path(path_obj, progress)

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


    def _calculate_animation_progress(self) -> bool:
        """Calculate animation progress. Returns False if animation not active."""
        if (
            not self._animation_start_time_qelapsed
            or not self.ik_animation_timer.isActive()
        ):
            return False

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

        return True

    def _validate_animation_preconditions(self) -> bool:
        """Check if all required data is available for animation."""
        if not self.project_parts_data:
            return False
        if not self.sim_joints_config:
            return False
        if not self.sim_selectable_components:
            return False
        if not self._current_skeleton_data or "joint_map" not in self._current_skeleton_data:
            logging.error(
                "IKManager._run_ik_animation_step: Missing skeleton data or joint_map."
            )
            return False
        return True

    def _clamp_bone_length(
        self, current_length: float | None, original_length: float | None
    ) -> float | None:
        """Clamp bone length to ±10% of original length."""
        if current_length is None or original_length is None or original_length <= 0:
            return current_length
        min_length = original_length * 0.9
        max_length = original_length * 1.1
        return max(min_length, min(max_length, current_length))

    def _finalize_joint_positions_and_emit(self) -> None:
        """Apply mechanism targets, sync dynamic joints, and emit pose update."""
        # Apply mechanism position targets
        for mech_joint_id, mech_target_pos in self._mechanism_position_targets.items():
            if mech_joint_id in self.sim_joints_config:
                self.sim_joints_config[mech_joint_id]["position"] = mech_target_pos

        # Sync to dynamic joints
        for joint_std_id, joint_data in self.sim_joints_config.items():
            pos = joint_data.get("position")
            if pos is not None and hasattr(pos, 'x') and hasattr(pos, 'y'):
                self.dynamic_joints[joint_std_id] = (pos.x(), pos.y())

        # Recalculate angles and update visuals
        self._recalculate_all_bone_angles_after_ik()
        self._update_character_part_visuals_from_ik()

        # Emit pose update
        animated_joint_scene_positions: dict[str, tuple[float, float]] = {}
        if self.sim_joints_config:
            for joint_std_id, joint_data in self.sim_joints_config.items():
                pos = joint_data.get("position")
                if pos is not None:
                    animated_joint_scene_positions[joint_std_id] = (pos.x(), pos.y())

        if animated_joint_scene_positions:
            self.skeleton_pose_updated.emit(animated_joint_scene_positions)

    def _run_ik_animation_step(self):
        """
        Run one step of IK animation.

        Refactored to reduce cyclomatic complexity by extracting helper methods.
        """
        if not self._calculate_animation_progress():
            return

        if not self._validate_animation_preconditions():
            return

        # Step 1: Apply mechanism position targets
        self._apply_mechanism_targets_to_joints()

        # Step 2: Process each selectable component
        progress = self._apply_timing_curve(self._current_animation_progress)
        for component in self.sim_selectable_components:
            self._process_animation_component(component, progress)

        # Step 3: Finalize positions and emit updates
        self._finalize_joint_positions_and_emit()

    def _apply_mechanism_targets_to_joints(self) -> None:
        """Apply mechanism position targets to joints."""
        for mech_joint_id, mech_target_pos in self._mechanism_position_targets.items():
            if mech_joint_id in self.dynamic_joints:
                self.dynamic_joints[mech_joint_id] = (mech_target_pos.x(), mech_target_pos.y())
            elif mech_joint_id in self.sim_joints_config:
                self.sim_joints_config[mech_joint_id]["position"] = mech_target_pos

    def _process_animation_component(
        self, component: dict[str, Any], progress: float
    ) -> None:
        """Process a single animation component for one frame."""
        target_joint_name = component.get("targetJointId")
        if not target_joint_name:
            return

        # Get target position from mechanism or motion path
        target_pos = self._get_target_position_for_component(component, progress)
        if not target_pos:
            return

        # Check if mechanism-controlled and override position
        target_std_id = self._get_standardized_joint_id(target_joint_name)
        is_mechanism_controlled = target_std_id and target_std_id in self._mechanism_position_targets
        if is_mechanism_controlled:
            target_pos = self._mechanism_position_targets[target_std_id]

        # Route to appropriate IK solver
        if target_joint_name in self.sim_two_bone_ik_effectors:
            self._process_two_bone_ik_component(target_joint_name, target_pos, is_mechanism_controlled)
        else:
            self._process_single_bone_or_direct_component(target_joint_name, target_pos)

    def _get_target_position_for_component(
        self, component: dict[str, Any], progress: float
    ) -> QPointF | None:
        """Get target position for a component from mechanism or motion path."""
        target_joint_name = component.get("targetJointId")
        target_std_id = self._get_standardized_joint_id(target_joint_name)

        # Check mechanism targets first
        if target_std_id and target_std_id in self._mechanism_position_targets:
            return self._mechanism_position_targets[target_std_id]

        # Check motion path
        part_name = component.get("partName")
        part_info = self.project_parts_data.get(part_name)
        if part_info and part_info.motion_path_data:
            return self._get_point_on_path(part_info.motion_path_data, progress)

        return None

    def _process_two_bone_ik_component(
        self, target_joint_name: str, target_pos: QPointF, is_mechanism_controlled: bool
    ) -> None:
        """Process two-bone IK for effector joints (hands, feet)."""
        # Resolve the two-bone IK chain
        chain = self._resolve_two_bone_chain(target_joint_name)
        if not chain:
            return

        root_id, middle_id, effector_id, label_l1, label_l2 = chain

        # Calculate bone lengths
        lengths = self._calculate_two_bone_lengths(root_id, middle_id, effector_id, label_l1, label_l2)
        if not lengths:
            return

        # Solve IK and apply results
        root_pos = self.sim_joints_config[root_id]["position"]
        solved = self._solve_two_bone_ik(root_pos, target_pos, lengths[0], lengths[1], root_id)

        if solved:
            self._apply_two_bone_ik_result(solved, middle_id, effector_id, is_mechanism_controlled)

    def _resolve_two_bone_chain(
        self, effector_name: str
    ) -> tuple[str, str, str, str, str] | None:
        """Resolve two-bone IK chain from effector to root."""
        effector_config = self.sim_limb_configs.get(effector_name)
        if not effector_config:
            return None

        middle_name = effector_config.get("parentAnchor")
        label_l2 = effector_config.get("label")
        if not middle_name or not label_l2:
            return None

        middle_config = self.sim_limb_configs.get(middle_name)
        if not middle_config:
            return None

        root_name = middle_config.get("parentAnchor")
        label_l1 = middle_config.get("label")
        if not root_name or not label_l1:
            return None

        # Get standardized IDs
        root_id = self._get_standardized_joint_id(root_name)
        middle_id = self._get_standardized_joint_id(middle_name)
        effector_id = self._get_standardized_joint_id(effector_name)

        if not (root_id and middle_id and effector_id):
            return None

        if root_id not in self.sim_joints_config:
            return None
        if "position" not in self.sim_joints_config[root_id]:
            return None

        return root_id, middle_id, effector_id, label_l1, label_l2

    def _apply_two_bone_ik_result(
        self,
        solved: tuple[QPointF, QPointF],
        middle_id: str,
        effector_id: str,
        is_mechanism_controlled: bool,
    ) -> None:
        """Apply solved IK positions to joints."""
        middle_pos, effector_pos = solved

        if middle_id in self.sim_joints_config:
            self.sim_joints_config[middle_id]["position"] = middle_pos
        if effector_id in self.sim_joints_config:
            self.sim_joints_config[effector_id]["position"] = effector_pos

        # Override with mechanism exact position if controlled
        if is_mechanism_controlled and effector_id in self._mechanism_position_targets:
            self.sim_joints_config[effector_id]["position"] = self._mechanism_position_targets[effector_id]

    def _calculate_two_bone_lengths(
        self, root_id: str, middle_id: str, effector_id: str, label_l1: str, label_l2: str
    ) -> tuple[float, float] | None:
        """Calculate and clamp two-bone lengths for IK."""
        root_pos = self.sim_joints_config[root_id].get("position")
        middle_pos = self.sim_joints_config.get(middle_id, {}).get("position")
        effector_pos = self.sim_joints_config.get(effector_id, {}).get("position")

        if middle_pos and effector_pos:
            length1 = QLineF(root_pos, middle_pos).length()
            length2 = QLineF(middle_pos, effector_pos).length()
        else:
            length1 = self.sim_limb_lengths.get(label_l1)
            length2 = self.sim_limb_lengths.get(label_l2)

        original_l1 = self.sim_limb_lengths.get(label_l1)
        original_l2 = self.sim_limb_lengths.get(label_l2)

        length1 = self._clamp_bone_length(length1, original_l1)
        length2 = self._clamp_bone_length(length2, original_l2)

        if length1 is None or length2 is None or length1 <= 0 or length2 <= 0:
            return None
        return length1, length2

    def _process_single_bone_or_direct_component(
        self, target_joint_name: str, target_pos: QPointF
    ) -> None:
        """Process single-bone IK or direct position update."""
        limb_config = self.sim_limb_configs.get(target_joint_name)
        anchor_name = limb_config.get("parentAnchor") if limb_config else None

        if anchor_name:
            # Single-bone IK
            solved = self._solve_single_bone_ik(
                target_joint_name,
                anchor_name,
                np.array([target_pos.x(), target_pos.y()]),
            )
            if solved:
                for joint_id, data in solved.items():
                    if joint_id in self.sim_joints_config:
                        self.sim_joints_config[joint_id].update(data)
                    else:
                        self.sim_joints_config[joint_id] = data
        else:
            # Direct position update with bone length clamping
            self._update_joint_position_direct(target_joint_name, target_pos)

    def _update_joint_position_direct(
        self, target_joint_name: str, target_pos: QPointF
    ) -> None:
        """Update joint position directly with bone length constraint."""
        target_std_id = self._get_standardized_joint_id(target_joint_name)
        if not target_std_id or target_std_id not in self.sim_joints_config:
            return

        final_pos = target_pos
        limb_config = self.sim_limb_configs.get(target_joint_name)
        anchor_name = limb_config.get("parentAnchor") if limb_config else None

        if anchor_name:
            final_pos = self._clamp_position_to_bone_length(
                target_std_id, anchor_name, target_pos
            )

        self.sim_joints_config[target_std_id]["position"] = final_pos

    def _clamp_position_to_bone_length(
        self, target_std_id: str, anchor_name: str, target_pos: QPointF
    ) -> QPointF:
        """Clamp target position to maintain bone length constraint."""
        anchor_std_id = self._get_standardized_joint_id(anchor_name)
        if not anchor_std_id or anchor_std_id not in self.sim_joints_config:
            return target_pos

        anchor_pos = self.sim_joints_config[anchor_std_id]["position"]
        anchor_current = self.sim_joints_config[anchor_std_id].get("position")
        target_current = self.sim_joints_config[target_std_id].get("position")

        if not anchor_current or not target_current:
            return target_pos

        original_bone_length = QLineF(anchor_current, target_current).length()
        if original_bone_length <= 0:
            return target_pos

        current_distance = QLineF(anchor_pos, target_pos).length()
        min_length = original_bone_length * 0.9
        max_length = original_bone_length * 1.1

        if min_length <= current_distance <= max_length:
            return target_pos

        if current_distance < 1e-6:
            return QPointF(anchor_pos.x(), anchor_pos.y() + original_bone_length)

        clamped_length = max(min_length, min(max_length, current_distance))
        direction_x = (target_pos.x() - anchor_pos.x()) / current_distance
        direction_y = (target_pos.y() - anchor_pos.y()) / current_distance

        return QPointF(
            anchor_pos.x() + direction_x * clamped_length,
            anchor_pos.y() + direction_y * clamped_length
        )


    @property
    def dynamic_joints(self) -> dict[str, dict[str, Any]]:
        return self._sim_dynamic_joints_data

    @dynamic_joints.setter
    def dynamic_joints(self, value: dict[str, dict[str, Any]]):
        self._sim_dynamic_joints_data = value

    @property
    def sim_joint_bend_directions(self) -> dict[str, int]:
        """Bend directions for IK joints. Delegates to BendDirectionManager."""
        return self._bend_direction_manager._bend_directions

    @sim_joint_bend_directions.setter
    def sim_joint_bend_directions(self, value: dict[str, int]):
        """Set bend directions. For backwards compatibility."""
        self._bend_direction_manager._bend_directions = value

    def _recalculate_all_bone_angles_after_ik(self):
        """Recalculate all bone angles after IK position updates."""
        if not self.sim_joints_config or not self._initial_snapshot:
            return

        # Update angles for limb-connected joints
        self._update_limb_joint_angles()

        # Update angles for non-limb joints
        self._update_non_limb_joint_angles()

    def _update_limb_joint_angles(self) -> None:
        """Update angles for joints connected by limb configs."""
        for eff_abs, limb_config in self.sim_limb_configs.items():
            part_name = limb_config.get("label")
            parent_abs = limb_config.get("parentAnchor")

            if not (part_name and parent_abs):
                continue

            parent_std_id = self._get_standardized_joint_id(parent_abs)
            child_std_id = self._get_standardized_joint_id(eff_abs)

            if not (parent_std_id and child_std_id):
                continue

            angle_delta = self._compute_limb_angle_delta(parent_std_id, child_std_id)
            if angle_delta is not None and child_std_id in self.sim_joints_config:
                self.sim_joints_config[child_std_id]["angle"] = angle_delta

    def _compute_limb_angle_delta(self, parent_id: str, child_id: str) -> float | None:
        """Compute angle delta between current and initial limb positions."""
        parent_pos = self._get_joint_position(parent_id)
        child_pos = self._get_joint_position(child_id)

        if not (parent_pos and child_pos):
            return None

        current_angle = self._angle_between_points(parent_pos, child_pos)
        initial_angle = self._get_initial_limb_angle(parent_id, child_id)

        return current_angle - initial_angle

    def _update_non_limb_joint_angles(self) -> None:
        """Update angles for joints not handled by limb configs."""
        limb_parent_ids = self._get_limb_parent_joint_ids()

        for joint_id, joint_data in self.sim_joints_config.items():
            if "angle" not in joint_data:
                continue
            if joint_id in limb_parent_ids:
                continue

            self._update_joint_angle_from_movement(joint_id, joint_data)

    def _get_limb_parent_joint_ids(self) -> set[str]:
        """Get set of joint IDs that are parents in limb configs."""
        parent_ids = set()
        for limb_config in self.sim_limb_configs.values():
            parent_abs = limb_config.get("parentAnchor")
            if parent_abs:
                parent_id = self._get_standardized_joint_id(parent_abs)
                if parent_id:
                    parent_ids.add(parent_id)
        return parent_ids

    def _update_joint_angle_from_movement(
        self, joint_id: str, joint_data: dict[str, Any]
    ) -> None:
        """Update a joint's angle based on its movement from initial position."""
        current_pos = joint_data.get("position")
        if not current_pos or joint_id not in self._initial_snapshot:
            return

        initial_pos = self._initial_snapshot[joint_id].get("position")
        if not initial_pos:
            return

        dx = current_pos.x() - initial_pos.x()
        dy = current_pos.y() - initial_pos.y()

        if dx == 0 and dy == 0:
            return

        movement_angle = math.degrees(math.atan2(dy, dx))
        initial_angle = self._initial_snapshot[joint_id].get("angle", 0.0)
        self.sim_joints_config[joint_id]["angle"] = initial_angle + movement_angle

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
