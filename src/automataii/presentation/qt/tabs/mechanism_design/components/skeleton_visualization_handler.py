"""
Skeleton Visualization Handler - Skeleton updates, visualization, and IK integration.

Extracted from MechanismDesignTab god class. Handles skeleton visualization,
IK manager connections, and skeleton data formatting.

Design Pattern: Handler (processes external events and updates state)
"""

from __future__ import annotations

import copy
import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.models import PartInfo
    from automataii.presentation.qt.views.editor_view import EditorView


class SkeletonVisualizationHandler(QObject):
    """
    Handles skeleton visualization and IK integration for mechanism design.

    Responsibilities:
    - Connect to IK manager signals for skeleton animation
    - Process skeleton data updates for visualization
    - Format skeleton data for different visualization methods
    - Update part positions from skeleton joint movements
    - Ensure skeleton visualization is properly initialized

    Signals:
        skeleton_updated: Emitted after skeleton visualization update
        parts_updated: Emitted after parts are updated from skeleton
    """

    skeleton_updated = pyqtSignal()
    parts_updated = pyqtSignal()

    # Z-index for skeleton overlay
    Z_SKELETON_OVERLAY = 1000

    # Mapping from part name to the target joint (the joint at the END of the bone)
    # Used for calculating bone rotation: angle from anchor to target
    PART_TO_TARGET_JOINT = {
        # Arms - each part's bone extends from anchor to target
        "left_arm_upper": "left_elbow",
        "left_arm_lower": "left_hand",
        "right_arm_upper": "right_elbow",
        "right_arm_lower": "right_hand",
        # Legs
        "left_leg_upper": "left_knee",
        "left_leg_lower": "left_foot",
        "right_leg_upper": "right_knee",
        "right_leg_lower": "right_foot",
        # Special cases
        "head": "neck",
        "torso": "torso",
    }

    def __init__(
        self,
        mechanism_view: EditorView,
        mechanism_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize skeleton visualization handler.

        Args:
            mechanism_view: The EditorView for skeleton visualization
            mechanism_scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._mechanism_view = mechanism_view
        self._mechanism_scene = mechanism_scene

        # Skeleton cache
        self._initial_skeleton_data_cache: dict | None = None

        # Optimization: Cache for joint ID resolution (abstract -> resolved)
        self._joint_id_cache: dict[str, str | None] = {}

        # Callbacks for external state access
        self._get_main_window: Callable[[], Any] = lambda: None
        self._get_current_editor_items: Callable[[], dict[str, CharacterPartItem]] = lambda: {}
        self._get_parts_data: Callable[[], dict[str, PartInfo]] = lambda: {}
        self._is_animation_running: Callable[[], bool] = lambda: False
        self._position_parts_at_anchor_joints: Callable[[], None] = lambda: None
        self._connected_ik_manager: Any | None = None
        self._connected_skeleton_manager: Any | None = None

    def configure_callbacks(
        self,
        get_main_window: Callable[[], Any],
        get_current_editor_items: Callable[[], dict[str, CharacterPartItem]],
        get_parts_data: Callable[[], dict[str, PartInfo]],
        is_animation_running: Callable[[], bool],
        position_parts_at_anchor_joints: Callable[[], None],
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_main_window = get_main_window
        self._get_current_editor_items = get_current_editor_items
        self._get_parts_data = get_parts_data
        self._is_animation_running = is_animation_running
        self._position_parts_at_anchor_joints = position_parts_at_anchor_joints

    @property
    def initial_skeleton_data_cache(self) -> dict | None:
        """Get the cached initial skeleton data."""
        return self._initial_skeleton_data_cache

    @initial_skeleton_data_cache.setter
    def initial_skeleton_data_cache(self, value: dict | None) -> None:
        """Set the cached initial skeleton data."""
        self._initial_skeleton_data_cache = value

    # --- IK Manager Connection ---

    def connect_to_ik_manager(self) -> None:
        """Connect to IK/skeleton manager signals for skeleton animation.

        This method is called from UI-state refresh paths, so it must be
        idempotent. Qt permits duplicate connections to the same slot; without
        the guards below, each refresh would make skeleton updates fan out
        multiple times and inflate receiver counts.
        """
        main_window = self._get_main_window()
        if not main_window:
            return

        ik_manager = getattr(main_window, "ik_manager", None)
        if ik_manager is not None and self._connected_ik_manager is not ik_manager:
            if self._connected_ik_manager is not None:
                try:
                    self._connected_ik_manager.skeleton_pose_updated.disconnect(
                        self.on_skeleton_updated
                    )
                except (TypeError, RuntimeError):
                    pass
            try:
                # Connect to skeleton pose updates
                ik_manager.skeleton_pose_updated.connect(self.on_skeleton_updated)
                self._connected_ik_manager = ik_manager
            except Exception as e:
                logging.debug(f"SkeletonVisualizationHandler: Failed to connect to ik_manager: {e}")

        # Also connect to skeleton_manager for bend_direction updates
        skeleton_manager = getattr(main_window, "skeleton_manager", None)
        if (
            skeleton_manager is not None
            and self._connected_skeleton_manager is not skeleton_manager
        ):
            if self._connected_skeleton_manager is not None:
                try:
                    self._connected_skeleton_manager.skeleton_updated.disconnect(
                        self.on_skeleton_manager_updated
                    )
                except (TypeError, RuntimeError):
                    pass
            try:
                skeleton_manager.skeleton_updated.connect(self.on_skeleton_manager_updated)
                self._connected_skeleton_manager = skeleton_manager
            except Exception as e:
                logging.debug(
                    f"SkeletonVisualizationHandler: Failed to connect to skeleton_manager: {e}"
                )

    # --- Skeleton Updates ---

    @pyqtSlot(dict)
    def on_skeleton_manager_updated(self, skeleton_data: dict | None) -> None:
        """Handle skeleton updates from skeleton_manager (for bend_direction sync)."""
        if not skeleton_data:
            self._clear_skeleton_visualization()
            return

        # Update skeleton visualization with new bend_direction values
        if (
            hasattr(self._mechanism_view, "skeleton_graphics_item")
            and self._mechanism_view.skeleton_graphics_item
        ):
            try:
                # Check if skeleton graphics item is valid
                _ = self._mechanism_view.skeleton_graphics_item.boundingRect()

                # Update bend directions in the skeleton graphics item
                joints_dict = skeleton_data.get("joints", {})
                for joint_id, joint_data in joints_dict.items():
                    bend_dir = joint_data.get("bend_direction")
                    if bend_dir is not None and ("elbow" in joint_id or "knee" in joint_id):
                        self._mechanism_view.skeleton_graphics_item.set_joint_bend_direction(
                            joint_id, bend_dir
                        )

                # Update the visual
                self._mechanism_view.skeleton_graphics_item.update()

            except RuntimeError:
                # Skeleton item was deleted, will be recreated on next update
                pass

    def _is_skeleton_initialized(self) -> bool:
        """Check if skeleton graphics item is initialized and valid."""
        try:
            skeleton_item = getattr(self._mechanism_view, "skeleton_graphics_item", None)
            if not skeleton_item:
                return False
            # Check for valid C++ object
            _ = skeleton_item.boundingRect()
            # Check for internal state
            return hasattr(skeleton_item, "_joint_items") and bool(skeleton_item._joint_items)
        except (RuntimeError, AttributeError):
            return False

    @pyqtSlot(dict)
    def on_skeleton_updated(self, skeleton_data: dict | None) -> None:
        """
        Handle skeleton updates from IK manager with improved error handling.

        Args:
            skeleton_data: Skeleton data from IK manager
        """
        # Validate skeleton_data first
        if not skeleton_data:
            self._clear_skeleton_visualization()
            return

        # Check if mechanism_view exists
        if not self._mechanism_view:
            return

        # Optimization: Clear cache if skeleton structure changes drastically
        # (Heuristic: simple clear on update might be too aggressive if updates are frequent,
        # but safe if structure is stable during animation)
        # For animation frames, structure usually doesn't change, only positions.
        # We'll rely on the existence check in _find_matching_joint_id.

        # Validate skeleton data structure
        is_valid_data = False
        is_raw_data = False

        if isinstance(skeleton_data, dict):
            if skeleton_data.get("joints") and len(skeleton_data["joints"]) > 0:
                is_valid_data = True
            elif all(isinstance(v, tuple | list) and len(v) == 2 for v in skeleton_data.values()):
                is_valid_data = True
                is_raw_data = True

        if not is_valid_data:
            self._clear_skeleton_visualization()
            return

        try:
            # FAST PATH: Raw animation data (dict[str, tuple]) AND skeleton already initialized
            if is_raw_data and self._is_skeleton_initialized():
                # Update skeleton visual directly without data conversion
                if hasattr(self._mechanism_view, "skeleton_graphics_item"):
                    self._mechanism_view.skeleton_graphics_item.set_animated_pose(skeleton_data)

                # Update parts directly
                self._update_parts_from_skeleton(skeleton_data, is_raw_format=True)

                self.skeleton_updated.emit()
                return

            # SLOW PATH: First run or complex data structure
            if is_raw_data:
                # Convert IK manager format Dict[str, Tuple[float, float]] to expected format
                transformed_data = {
                    "joints": {
                        joint_id: {"scene_position": list(pos), "id": joint_id}
                        for joint_id, pos in skeleton_data.items()
                    }
                }

                # Ensure skeleton is initialized before animation
                self.ensure_skeleton_visualization(transformed_data)

                # Now update skeleton animation using the transformed data
                if hasattr(self._mechanism_view, "update_skeleton_animation"):
                    self._mechanism_view.update_skeleton_animation(skeleton_data)

                skeleton_data = transformed_data
            else:
                # Standard skeleton model format - ensure skeleton visualization is set up
                self.ensure_skeleton_visualization(skeleton_data)

            # Update part positions from skeleton during animation
            self._update_parts_from_skeleton(skeleton_data, is_raw_format=False)

            self.skeleton_updated.emit()

        except Exception as e:
            # Don't let skeleton errors crash the mechanism animation
            logging.debug(f"SkeletonVisualizationHandler: Error in on_skeleton_updated: {e}")

    def _find_matching_joint_id(
        self, anchor_joint_id: str, joints_dict: dict[str, Any]
    ) -> str | None:
        """
        Find matching joint ID with prefix matching support.

        Optimized: Uses caching to avoid O(N) linear scan on every frame.
        """
        # 1. Check cache first
        if anchor_joint_id in self._joint_id_cache:
            resolved_id = self._joint_id_cache[anchor_joint_id]
            # Verify the resolved ID still exists in the current joints_dict
            # (Skeleton structure might have changed)
            if resolved_id and resolved_id in joints_dict:
                return resolved_id
            # If invalid, continue to re-resolve

        # 2. Exact match
        if anchor_joint_id in joints_dict:
            self._joint_id_cache[anchor_joint_id] = anchor_joint_id
            return anchor_joint_id

        # 3. Prefix matching for suffixed joint IDs (e.g., left_hand -> left_hand_9)
        for joint_id in joints_dict:
            # Check if joint_id starts with anchor_joint_id + "_" or equals it
            if joint_id.startswith(anchor_joint_id + "_"):
                self._joint_id_cache[anchor_joint_id] = joint_id
                return joint_id
            # Also check for numeric suffix without underscore (e.g., left_hand9)
            if joint_id.startswith(anchor_joint_id) and len(joint_id) > len(anchor_joint_id):
                suffix = joint_id[len(anchor_joint_id) :]
                if suffix[0].isdigit() or suffix[0] == "_":
                    self._joint_id_cache[anchor_joint_id] = joint_id
                    return joint_id

        # Cache negative result to avoid repeated scanning for non-existent joints
        self._joint_id_cache[anchor_joint_id] = None
        return None

    def _update_parts_from_skeleton(self, skeleton_data: dict, is_raw_format: bool = False) -> None:
        """
        Update part positions and rotations based on skeleton joint movements.

        Time Complexity: O(p * j) where p = number of parts, j = number of joints

        Args:
            skeleton_data: Skeleton data dict
            is_raw_format: If True, skeleton_data is dict[id, (x,y)].
                           If False, it's dict["joints"][id]["scene_position"]...
        """
        if is_raw_format:
            joints_dict = skeleton_data
        else:
            joints_dict = skeleton_data.get("joints", {})

        current_editor_items = self._get_current_editor_items()
        parts_data = self._get_parts_data()

        # Debug: Log state once per few frames
        if not hasattr(self, "_parts_update_log_counter"):
            self._parts_update_log_counter = 0
        self._parts_update_log_counter += 1

        if self._parts_update_log_counter <= 3:
            logging.debug(
                f"[PARTS-UPDATE] current_editor_items count: {len(current_editor_items)}, "
                f"parts_data count: {len(parts_data)}, joints count: {len(joints_dict)}"
            )

        parts_updated_count = 0
        for part_name, part_item in current_editor_items.items():
            part_info = parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            anchor_joint_id = part_info.anchor_joint_id
            # Use prefix matching to find the actual joint ID
            matched_joint_id = self._find_matching_joint_id(anchor_joint_id, joints_dict)
            if not matched_joint_id:
                if self._parts_update_log_counter <= 3:
                    logging.debug(f"[PARTS-UPDATE] No match for anchor '{anchor_joint_id}'")
                continue

            # Get position data based on format
            if is_raw_format:
                # Raw format: joints_dict[id] = (x, y)
                position_data = joints_dict[matched_joint_id]
                joint_data = {"position": position_data}  # Minimal wrap for rotation logic
            else:
                # Complex format: joints_dict[id] = {"scene_position": ...}
                joint_data = joints_dict[matched_joint_id]
                position_data = joint_data.get("scene_position") or joint_data.get("position")

            # 1. UPDATE POSITION (unconditionally)
            scene_pos_to_set = None
            if isinstance(position_data, list | tuple) and len(position_data) >= 2:
                scene_pos_to_set = QPointF(position_data[0], position_data[1])
                part_item.set_scene_position_from_anchor(scene_pos_to_set, bypass_validation=True)
                parts_updated_count += 1

            # 2. UPDATE ROTATION
            self._update_part_rotation(
                part_item, joint_data, joints_dict, scene_pos_to_set, is_raw_format
            )

        if self._parts_update_log_counter <= 3:
            logging.debug(f"[PARTS-UPDATE] Updated {parts_updated_count} parts from skeleton")

        self.parts_updated.emit()

    def _update_part_rotation(
        self,
        part_item: CharacterPartItem,
        joint_data: dict,
        joints_dict: dict,
        scene_pos: QPointF | None,
        is_raw_format: bool = False,
    ) -> None:
        """
        Update part rotation from joint data.

        Uses RELATIVE rotation: calculates the change in bone angle from initial state
        and applies that delta to the part's initial rotation.
        """
        # Try multiple rotation data sources from skeleton data
        # Note: Raw format usually only has positions, so explicit rotation keys might be missing
        if not is_raw_format:
            if "world_rotation_degrees" in joint_data:
                rotation = float(joint_data["world_rotation_degrees"])
                part_item.setRotation(rotation)
                return

            if "angle" in joint_data:
                angle = joint_data["angle"]
                if isinstance(angle, int | float):
                    rotation_degrees = math.degrees(angle) if abs(angle) <= 2 * math.pi else angle
                    part_item.setRotation(rotation_degrees)
                    return

            if "rotation" in joint_data:
                rotation = joint_data["rotation"]
                if isinstance(rotation, int | float):
                    part_item.setRotation(rotation)
                    return

        # FALLBACK: Calculate RELATIVE bone angle change from anchor to target joint
        if scene_pos is None:
            return

        part_name = part_item.name() if hasattr(part_item, "name") else None
        if not part_name:
            return

        target_joint_id = self.PART_TO_TARGET_JOINT.get(part_name)
        if not target_joint_id:
            return

        # Find the target joint position using prefix matching
        matched_target_id = self._find_matching_joint_id(target_joint_id, joints_dict)
        if not matched_target_id:
            return

        # Get target pos
        if is_raw_format:
            target_pos_data = joints_dict[matched_target_id]
        else:
            target_data = joints_dict[matched_target_id]
            target_pos_data = target_data.get("scene_position") or target_data.get("position")

        if (
            not target_pos_data
            or not isinstance(target_pos_data, list | tuple)
            or len(target_pos_data) < 2
        ):
            return

        # Calculate current bone angle FROM anchor TO target
        dx = target_pos_data[0] - scene_pos.x()
        dy = target_pos_data[1] - scene_pos.y()

        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return

        current_bone_angle = math.degrees(math.atan2(dy, dx))

        # Store initial bone angle and part rotation on first call
        if not hasattr(part_item, "_initial_bone_angle"):
            part_item._initial_bone_angle = current_bone_angle
            part_item._initial_part_rotation = part_item.rotation()

        # Calculate angle delta and apply to initial rotation
        angle_delta = current_bone_angle - part_item._initial_bone_angle
        new_rotation = part_item._initial_part_rotation + angle_delta
        part_item.setRotation(new_rotation)

    # --- Skeleton Visualization ---

    def ensure_skeleton_visualization(self, skeleton_data: dict) -> None:
        """
        Ensure skeleton visualization is properly set up and updated.

        Args:
            skeleton_data: Skeleton data to visualize
        """
        if not hasattr(self._mechanism_view, "visualize_skeleton"):
            return

        try:
            # Check if skeleton graphics item exists and is valid
            skeleton_item = getattr(self._mechanism_view, "skeleton_graphics_item", None)
            needs_initialization = False

            if not skeleton_item:
                needs_initialization = True
            else:
                try:
                    # Test if the skeleton item is still valid (not deleted by C++)
                    _ = skeleton_item.boundingRect()
                    # Check if skeleton has joint items for animation
                    if not hasattr(skeleton_item, "_joint_items") or not skeleton_item._joint_items:
                        needs_initialization = True
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        needs_initialization = True
                    else:
                        raise

            if needs_initialization:
                # Format skeleton data for visualize_skeleton
                skeleton_for_view, hierarchy = self.format_skeleton_for_visualization(skeleton_data)
                if skeleton_for_view:
                    self._mechanism_view.visualize_skeleton(skeleton_for_view, hierarchy)

                    # Ensure proper Z-order after creation
                    if (
                        hasattr(self._mechanism_view, "skeleton_graphics_item")
                        and self._mechanism_view.skeleton_graphics_item
                    ):
                        self._mechanism_view.skeleton_graphics_item.setZValue(
                            self.Z_SKELETON_OVERLAY
                        )
            else:
                # Skeleton exists, just update animation
                if skeleton_item and hasattr(skeleton_item, "set_animated_pose"):
                    pose_data = self.convert_skeleton_data_for_animation(skeleton_data)
                    if pose_data:
                        skeleton_item.set_animated_pose(pose_data)

        except Exception as e:
            logging.debug(
                f"SkeletonVisualizationHandler: Error in ensure_skeleton_visualization: {e}"
            )

    def format_skeleton_for_visualization(
        self, skeleton_data: dict
    ) -> tuple[list[dict], dict[str, list[str]]]:
        """
        Format skeleton data for visualize_skeleton method.

        Args:
            skeleton_data: Raw skeleton data

        Returns:
            Tuple of (skeleton_for_view list, hierarchy dict)

        Time Complexity: O(j) where j = number of joints
        """
        skeleton_for_view: list[dict] = []
        hierarchy: dict[str, list[str]] = {}

        if "joints" not in skeleton_data:
            return skeleton_for_view, hierarchy

        joints_dict = skeleton_data["joints"]
        for joint_id, joint_info in joints_dict.items():
            # Handle different joint data formats
            if isinstance(joint_info, dict):
                position = joint_info.get("position") or joint_info.get("scene_position", [0, 0])
                parent_id = joint_info.get("parent")
                joint_name = joint_info.get("name", joint_id)
            elif isinstance(joint_info, list | tuple) and len(joint_info) >= 2:
                position = joint_info[:2]
                parent_id = None
                joint_name = joint_id
            else:
                continue

            # Convert position to QPointF
            if isinstance(position, QPointF):
                pos_qpoint = position
            elif isinstance(position, list | tuple) and len(position) >= 2:
                pos_qpoint = QPointF(float(position[0]), float(position[1]))
            else:
                continue

            joint_view_data = {
                "id": joint_id,
                "name": joint_name,
                "position": pos_qpoint,
                "parent": parent_id,
                "color": "blue",
                "label": joint_name,
            }
            skeleton_for_view.append(joint_view_data)

            # Build hierarchy
            if parent_id:
                if parent_id not in hierarchy:
                    hierarchy[parent_id] = []
                hierarchy[parent_id].append(joint_id)

        # Also check hierarchy from skeleton_data
        if "hierarchy" in skeleton_data:
            hierarchy.update(skeleton_data["hierarchy"])

        return skeleton_for_view, hierarchy

    def convert_skeleton_data_for_animation(
        self, skeleton_data: dict
    ) -> dict[str, tuple[float, float]]:
        """
        Convert skeleton data to format expected by set_animated_pose.

        Args:
            skeleton_data: Raw skeleton data

        Returns:
            Dict mapping joint_id to (x, y) position tuple

        Time Complexity: O(j) where j = number of joints
        """
        pose_data: dict[str, tuple[float, float]] = {}

        if "joints" not in skeleton_data:
            return pose_data

        joints_dict = skeleton_data["joints"]
        for joint_id, joint_info in joints_dict.items():
            if isinstance(joint_info, dict):
                position = joint_info.get("position") or joint_info.get("scene_position")
                if position and len(position) >= 2:
                    pose_data[joint_id] = (float(position[0]), float(position[1]))
            elif isinstance(joint_info, list | tuple) and len(joint_info) >= 2:
                pose_data[joint_id] = (float(joint_info[0]), float(joint_info[1]))

        return pose_data

    # --- Skeleton Cache Management ---

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None) -> None:
        """
        Cache the initial skeleton data dictionary.

        Args:
            skeleton_data_dict: Skeleton data to cache
        """
        self._initial_skeleton_data_cache = (
            copy.deepcopy(skeleton_data_dict) if skeleton_data_dict else None
        )

        if self._initial_skeleton_data_cache:
            if self._mechanism_view and hasattr(self._mechanism_view, "set_joint_map"):
                self._mechanism_view.set_joint_map(
                    self._initial_skeleton_data_cache.get("joint_map")
                )

            # Ensure skeleton visualization is initialized
            self.ensure_skeleton_visualization(self._initial_skeleton_data_cache)

            # Only position parts at anchor joints if animation is NOT running
            if not self._is_animation_running():
                self._position_parts_at_anchor_joints()
        else:
            self._clear_skeleton_visualization()

    def _clear_skeleton_visualization(self) -> None:
        """
        Clear skeleton overlay and related mapping/cache state.

        This is required when character/skeleton data is replaced so stale dummy
        skeleton visuals do not remain in Mechanism Design.
        """
        self._initial_skeleton_data_cache = None
        self._joint_id_cache.clear()

        if self._mechanism_view and hasattr(self._mechanism_view, "set_joint_map"):
            self._mechanism_view.set_joint_map(None)

        if self._mechanism_view and hasattr(self._mechanism_view, "visualize_skeleton"):
            try:
                self._mechanism_view.visualize_skeleton([], {})
            except Exception:
                logging.debug(
                    "SkeletonVisualizationHandler: Failed to clear skeleton visualization",
                    exc_info=True,
                )
