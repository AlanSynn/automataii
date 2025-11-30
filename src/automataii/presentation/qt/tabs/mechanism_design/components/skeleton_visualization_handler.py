"""
Skeleton Visualization Handler - Skeleton updates, visualization, and IK integration.

Extracted from MechanismDesignTab god class. Handles skeleton visualization,
IK manager connections, and skeleton data formatting.

Design Pattern: Handler (processes external events and updates state)
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

    from automataii.presentation.qt.models import PartInfo
    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
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

        # Callbacks for external state access
        self._get_main_window: Callable[[], Any] = lambda: None
        self._get_current_editor_items: Callable[[], dict[str, CharacterPartItem]] = lambda: {}
        self._get_parts_data: Callable[[], dict[str, PartInfo]] = lambda: {}
        self._is_animation_running: Callable[[], bool] = lambda: False
        self._position_parts_at_anchor_joints: Callable[[], None] = lambda: None

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
        """Connect to IK manager signals for skeleton animation."""
        main_window = self._get_main_window()
        if not main_window:
            return

        if hasattr(main_window, 'ik_manager') and main_window.ik_manager:
            try:
                # Connect to skeleton pose updates
                main_window.ik_manager.skeleton_pose_updated.connect(self.on_skeleton_updated)
            except Exception as e:
                logging.debug(f"SkeletonVisualizationHandler: Failed to connect to ik_manager: {e}")

        # Also connect to skeleton_manager for bend_direction updates
        if hasattr(main_window, 'skeleton_manager') and main_window.skeleton_manager:
            try:
                main_window.skeleton_manager.skeleton_updated.connect(self.on_skeleton_manager_updated)
            except Exception as e:
                logging.debug(f"SkeletonVisualizationHandler: Failed to connect to skeleton_manager: {e}")

    # --- Skeleton Updates ---

    @pyqtSlot(dict)
    def on_skeleton_manager_updated(self, skeleton_data: dict | None) -> None:
        """Handle skeleton updates from skeleton_manager (for bend_direction sync)."""
        if not skeleton_data:
            return

        # Update skeleton visualization with new bend_direction values
        if hasattr(self._mechanism_view, 'skeleton_graphics_item') and self._mechanism_view.skeleton_graphics_item:
            try:
                # Check if skeleton graphics item is valid
                _ = self._mechanism_view.skeleton_graphics_item.boundingRect()

                # Update bend directions in the skeleton graphics item
                joints_dict = skeleton_data.get("joints", {})
                for joint_id, joint_data in joints_dict.items():
                    bend_dir = joint_data.get("bend_direction")
                    if bend_dir is not None and ('elbow' in joint_id or 'knee' in joint_id):
                        self._mechanism_view.skeleton_graphics_item.set_joint_bend_direction(joint_id, bend_dir)

                # Update the visual
                self._mechanism_view.skeleton_graphics_item.update()

            except RuntimeError:
                # Skeleton item was deleted, will be recreated on next update
                pass

    @pyqtSlot(dict)
    def on_skeleton_updated(self, skeleton_data: dict | None) -> None:
        """
        Handle skeleton updates from IK manager with improved error handling.

        Args:
            skeleton_data: Skeleton data from IK manager
        """
        # Validate skeleton_data first
        if not skeleton_data:
            return

        # Check if mechanism_view exists
        if not self._mechanism_view:
            return

        # Validate skeleton data structure
        is_valid_data = False
        if isinstance(skeleton_data, dict):
            if skeleton_data.get("joints") and len(skeleton_data["joints"]) > 0:
                is_valid_data = True
            elif all(isinstance(v, tuple | list) and len(v) == 2 for v in skeleton_data.values()):
                is_valid_data = True

        if not is_valid_data:
            return

        try:
            # Check if we received raw animation data from IK manager
            if skeleton_data and all(isinstance(v, tuple | list) and len(v) == 2 for v in skeleton_data.values()):
                # Convert IK manager format Dict[str, Tuple[float, float]] to expected format
                transformed_data = {
                    "joints": {
                        joint_id: {
                            "scene_position": list(pos),
                            "id": joint_id
                        }
                        for joint_id, pos in skeleton_data.items()
                    }
                }

                # Ensure skeleton is initialized before animation
                self.ensure_skeleton_visualization(transformed_data)

                # Now update skeleton animation using the transformed data
                if hasattr(self._mechanism_view, 'update_skeleton_animation'):
                    self._mechanism_view.update_skeleton_animation(skeleton_data)

                skeleton_data = transformed_data
            else:
                # Standard skeleton model format - ensure skeleton visualization is set up
                self.ensure_skeleton_visualization(skeleton_data)

            # Update part positions from skeleton during animation
            self._update_parts_from_skeleton(skeleton_data)

            self.skeleton_updated.emit()

        except Exception as e:
            # Don't let skeleton errors crash the mechanism animation
            logging.debug(f"SkeletonVisualizationHandler: Error in on_skeleton_updated: {e}")

    def _update_parts_from_skeleton(self, skeleton_data: dict) -> None:
        """
        Update part positions and rotations based on skeleton joint movements.

        Time Complexity: O(p) where p = number of parts
        """
        joints_dict = skeleton_data.get("joints", {})
        current_editor_items = self._get_current_editor_items()
        parts_data = self._get_parts_data()

        for part_name, part_item in current_editor_items.items():
            part_info = parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            anchor_joint_id = part_info.anchor_joint_id
            if anchor_joint_id not in joints_dict:
                continue

            joint_data = joints_dict[anchor_joint_id]

            # 1. UPDATE POSITION (unconditionally)
            scene_pos_to_set = None
            position_data = joint_data.get("scene_position") or joint_data.get("position")
            if isinstance(position_data, list | tuple) and len(position_data) >= 2:
                scene_pos_to_set = QPointF(position_data[0], position_data[1])
                part_item.set_scene_position_from_anchor(scene_pos_to_set)

            # 2. UPDATE ROTATION
            self._update_part_rotation(part_item, joint_data, joints_dict, scene_pos_to_set)

        self.parts_updated.emit()

    def _update_part_rotation(
        self,
        part_item: CharacterPartItem,
        joint_data: dict,
        joints_dict: dict,
        scene_pos: QPointF | None,
    ) -> None:
        """Update part rotation from joint data."""
        # Try multiple rotation data sources
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

        # FALLBACK: Calculate bone angle from parent-child relationship
        parent_joint_id = joint_data.get("parent_id") or joint_data.get("parent")
        if parent_joint_id and parent_joint_id in joints_dict:
            parent_data = joints_dict[parent_joint_id]
            parent_pos_data = parent_data.get("scene_position") or parent_data.get("position")

            if (scene_pos and parent_pos_data and
                isinstance(parent_pos_data, list | tuple) and len(parent_pos_data) >= 2):

                dx = scene_pos.x() - parent_pos_data[0]
                dy = scene_pos.y() - parent_pos_data[1]

                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    bone_angle_rad = math.atan2(dy, dx)
                    bone_angle_deg = math.degrees(bone_angle_rad)
                    part_item.setRotation(bone_angle_deg)

    # --- Skeleton Visualization ---

    def ensure_skeleton_visualization(self, skeleton_data: dict) -> None:
        """
        Ensure skeleton visualization is properly set up and updated.

        Args:
            skeleton_data: Skeleton data to visualize
        """
        if not hasattr(self._mechanism_view, 'visualize_skeleton'):
            return

        try:
            # Check if skeleton graphics item exists and is valid
            skeleton_item = getattr(self._mechanism_view, 'skeleton_graphics_item', None)
            needs_initialization = False

            if not skeleton_item:
                needs_initialization = True
            else:
                try:
                    # Test if the skeleton item is still valid (not deleted by C++)
                    _ = skeleton_item.boundingRect()
                    # Check if skeleton has joint items for animation
                    if not hasattr(skeleton_item, '_joint_items') or not skeleton_item._joint_items:
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
                    if hasattr(self._mechanism_view, 'skeleton_graphics_item') and self._mechanism_view.skeleton_graphics_item:
                        self._mechanism_view.skeleton_graphics_item.setZValue(self.Z_SKELETON_OVERLAY)
            else:
                # Skeleton exists, just update animation
                if skeleton_item and hasattr(skeleton_item, 'set_animated_pose'):
                    pose_data = self.convert_skeleton_data_for_animation(skeleton_data)
                    if pose_data:
                        skeleton_item.set_animated_pose(pose_data)

        except Exception as e:
            logging.debug(f"SkeletonVisualizationHandler: Error in ensure_skeleton_visualization: {e}")

    def format_skeleton_for_visualization(self, skeleton_data: dict) -> tuple[list[dict], dict[str, list[str]]]:
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
                "label": joint_name
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

    def convert_skeleton_data_for_animation(self, skeleton_data: dict) -> dict[str, tuple[float, float]]:
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
        self._initial_skeleton_data_cache = skeleton_data_dict.copy() if skeleton_data_dict else None

        if self._initial_skeleton_data_cache:
            if self._mechanism_view and hasattr(self._mechanism_view, "set_joint_map"):
                self._mechanism_view.set_joint_map(self._initial_skeleton_data_cache.get("joint_map"))

            # Ensure skeleton visualization is initialized
            self.ensure_skeleton_visualization(self._initial_skeleton_data_cache)

            # Only position parts at anchor joints if animation is NOT running
            if not self._is_animation_running():
                self._position_parts_at_anchor_joints()
