# src/automataii/ui/tabs/editor/scene_manager.py

import logging
import math
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsScene

from automataii.config.z_indices import Z_SKELETON_OVERLAY
from automataii.models.runtime import PartInfo
from automataii.ui.graphics_items.part_item import CharacterPartItem
from automataii.ui.graphics_items.skeleton_item import SkeletonGraphicsItem

logger = logging.getLogger(__name__)


class EditorSceneManager:
    """Manages the QGraphicsScene for the EditorTab."""

    def __init__(self, scene: QGraphicsScene, state, parent) -> None:
        self.scene = scene
        self.state = state
        self.parent = parent
        self.current_editor_items: dict[str, CharacterPartItem] = {}
        self.skeleton_item: SkeletonGraphicsItem | None = None

        # Connect to state changes for part selection
        self.state.part_selection_changed.connect(self._on_part_selection_changed)

    def set_parts_data(self, parts_info: dict[str, PartInfo], project_dir: Path) -> None:
        self.clear_scene()
        for part_name, p_info in parts_info.items():
            item = CharacterPartItem(part_info=p_info, project_dir=project_dir)
            self.scene.addItem(item)
            self.current_editor_items[part_name] = item
        self.position_parts_at_anchor_joints()
        self._update_skeleton_visualization()

    def clear_scene(self) -> None:
        for item in self.current_editor_items.values():
            self.scene.removeItem(item)
        self.current_editor_items.clear()

        # Clear skeleton item
        if self.skeleton_item:
            self.scene.removeItem(self.skeleton_item)
            self.skeleton_item = None

        # Clear any joint highlights
        if self.skeleton_item:
            self.skeleton_item.clear_highlights()

    def position_parts_at_anchor_joints(self) -> None:
        if not self.state.initial_skeleton_data_cache:
            return

        joints_dict = self.state.initial_skeleton_data_cache.get("joints", {})
        missing_joints = []

        for part_name, part_item in self.current_editor_items.items():
            p_info = self.state.current_parts_info.get(part_name)
            if p_info and p_info.anchor_joint_id:
                joint_data = joints_dict.get(p_info.anchor_joint_id)
                if joint_data and "position" in joint_data:
                    pos = joint_data["position"]
                    scene_pos = QPointF(pos[0], pos[1])
                    part_item.set_scene_position_from_anchor(scene_pos)

                    # Reset transformation to neutral state since parts are already
                    # correctly oriented from the pose detection phase
                    part_item.setRotation(0.0)
                    part_item.setScale(1.0)
                    logger.debug(f"Initialized part '{part_name}' at neutral pose (rotation=0, scale=1)")
                else:
                    missing_joints.append((part_name, p_info.anchor_joint_id))
                    logger.warning(
                        f"Part '{part_name}' references missing joint '{p_info.anchor_joint_id}'"
                    )

        if missing_joints:
            logger.error(
                f"Skeleton-Part mismatch detected! {len(missing_joints)} parts have invalid joint references."
            )
            # This indicates skeleton and parts are from different sources

    def update_visuals_from_animation_data(self, joint_positions: dict[str, tuple[float, float]]) -> None:
        """Update skeleton and parts from IK joint positions data."""

        # Since IKManager now sends tuples directly, we can use them directly
        joint_positions_qpointf = {}
        for joint_id, pos_tuple in joint_positions.items():
            joint_positions_qpointf[joint_id] = QPointF(pos_tuple[0], pos_tuple[1])

        # Update skeleton visualization if it exists
        if self.skeleton_item:
            self.skeleton_item.set_animated_pose(joint_positions)
            logger.debug(f"Updated skeleton with {len(joint_positions)} joint positions")
        else:
            logger.warning("SceneManager: No skeleton item to update")

        # Update part positions to follow their anchor joints
        self._update_parts_from_joint_positions(joint_positions_qpointf)

        self.scene.update()

    def _update_parts_from_joint_positions(self, joint_positions: dict[str, QPointF]) -> None:
        """Update part positions and orientations based on animated joint positions."""
        updated_parts = 0

        for part_name, part_item in self.current_editor_items.items():
            # Get part info to find anchor joint
            p_info = self.state.current_parts_info.get(part_name)
            if not p_info or not p_info.anchor_joint_id:
                continue

            target_joint_name = p_info.anchor_joint_id
            logger.debug(f"Looking for joint '{target_joint_name}' for part '{part_name}'")

            # Try exact match first
            found_joint = None
            if target_joint_name in joint_positions:
                found_joint = target_joint_name
            else:
                # Try to find joint by name prefix (e.g., 'neck' matches 'neck_3')
                for joint_id in joint_positions.keys():
                    if joint_id.startswith(target_joint_name + '_'):
                        found_joint = joint_id
                        break

            if found_joint:
                new_joint_pos = joint_positions[found_joint]

                # Update position and apply deformation to fill gaps
                self._update_part_with_deformation(
                    part_item, part_name, found_joint, new_joint_pos, joint_positions
                )

                updated_parts += 1
                logger.debug(f"Updated part '{part_name}' with skeleton-driven transformation for joint '{found_joint}'")
            else:
                logger.debug(f"No animated position found for part '{part_name}' anchor joint '{target_joint_name}'. Available joints: {list(joint_positions.keys())[:5]}...")

        logger.debug(f"SceneManager: Updated {updated_parts} parts from joint positions")

    def _update_part_with_deformation(self, part_item, part_name: str, anchor_joint_id: str,
                                    new_joint_pos: QPointF, all_joint_positions: dict[str, QPointF]) -> None:
        """Update part position and apply minimal deformation to fill gaps."""
        import math

        # Basic position update
        part_item.set_scene_position_from_anchor(new_joint_pos)

        # Get initial skeleton data for comparison
        if not self.state.initial_skeleton_data_cache:
            return

        initial_joints = self.state.initial_skeleton_data_cache.get("joints", {})

        # Find the part's associated joints for deformation calculation
        part_joint_connections = {
            "left_arm_upper": ("left_shoulder", "left_elbow"),
            "left_arm_lower": ("left_elbow", "left_hand"),
            "right_arm_upper": ("right_shoulder", "right_elbow"),
            "right_arm_lower": ("right_elbow", "right_hand"),
            "left_leg_upper": ("left_hip", "left_knee"),
            "left_leg_lower": ("left_knee", "left_foot"),
            "right_leg_upper": ("right_hip", "right_knee"),
            "right_leg_lower": ("right_knee", "right_foot"),
            "torso": ("hip", "torso"),
            "head": ("neck", "neck")  # Head doesn't deform much
        }

        if part_name not in part_joint_connections:
            return

        joint1_name, joint2_name = part_joint_connections[part_name]

        # Find corresponding standardized joint IDs
        joint1_id = self._find_standardized_joint_id(joint1_name, all_joint_positions)
        joint2_id = self._find_standardized_joint_id(joint2_name, all_joint_positions)

        if not joint1_id or not joint2_id:
            return

        # Get current and initial positions
        current_pos1 = all_joint_positions[joint1_id]
        current_pos2 = all_joint_positions[joint2_id]

        # Calculate rotation based on joint orientation change from initial state
        dx = current_pos2.x() - current_pos1.x()
        dy = current_pos2.y() - current_pos1.y()
        current_angle = math.atan2(dy, dx) * 180 / math.pi

        # Get initial angle
        initial_joint1 = self._get_initial_joint_pos(joint1_name, initial_joints)
        initial_joint2 = self._get_initial_joint_pos(joint2_name, initial_joints)

        rotation_offset = 0.0
        if initial_joint1 and initial_joint2:
            initial_dx = initial_joint2[0] - initial_joint1[0]
            initial_dy = initial_joint2[1] - initial_joint1[1]
            initial_angle = math.atan2(initial_dy, initial_dx) * 180 / math.pi

            # Apply only the rotation difference from initial pose
            rotation_offset = current_angle - initial_angle

        # Apply relative rotation (not absolute)
        part_item.setRotation(rotation_offset)

        # Calculate scale factor to fill gaps (relative to initial state)
        current_length = math.sqrt(dx * dx + dy * dy)

        scale_factor = 1.0  # Default to no scaling
        if initial_joint1 and initial_joint2:
            initial_dx = initial_joint2[0] - initial_joint1[0]
            initial_dy = initial_joint2[1] - initial_joint1[1]
            initial_length = math.sqrt(initial_dx * initial_dx + initial_dy * initial_dy)

            if initial_length > 0:
                # Scale relative to initial pose (1.0 = no change from detected pose)
                scale_factor = current_length / initial_length
                # Limit scaling to prevent extreme deformation
                scale_factor = max(0.5, min(2.0, scale_factor))

        part_item.setScale(scale_factor)
        logger.debug(f"Part '{part_name}': rotation_offset={rotation_offset:.1f}°, scale={scale_factor:.2f}")

    def _find_standardized_joint_id(self, joint_name: str, joint_positions: dict[str, QPointF]) -> str | None:
        """Find standardized joint ID from base name."""
        # Try exact match first
        if joint_name in joint_positions:
            return joint_name

        # Try prefix match (e.g., 'neck' -> 'neck_3')
        for joint_id in joint_positions.keys():
            if joint_id.startswith(joint_name + '_'):
                return joint_id
        return None

    def _get_initial_joint_pos(self, joint_name: str, initial_joints: dict) -> tuple[float, float] | None:
        """Get initial position of a joint by name."""
        for joint_id, joint_data in initial_joints.items():
            if joint_data.get("name") == joint_name or joint_id.startswith(joint_name):
                return joint_data.get("position")
        return None

    def reset_parts_to_initial_pose(self) -> None:
        """Reset all parts to their initial pose (neutral transformations)."""
        if not self.state.initial_skeleton_data_cache:
            logger.warning("Cannot reset parts: no initial skeleton data available")
            return

        joints_dict = self.state.initial_skeleton_data_cache.get("joints", {})
        reset_count = 0

        for part_name, part_item in self.current_editor_items.items():
            p_info = self.state.current_parts_info.get(part_name)
            if p_info and p_info.anchor_joint_id:
                joint_data = joints_dict.get(p_info.anchor_joint_id)
                if joint_data and "position" in joint_data:
                    # Reset to initial position
                    pos = joint_data["position"]
                    scene_pos = QPointF(pos[0], pos[1])
                    part_item.set_scene_position_from_anchor(scene_pos)

                    # Reset transformations to neutral state
                    part_item.setRotation(0.0)
                    part_item.setScale(1.0)

                    reset_count += 1

        logger.debug(f"Reset {reset_count} parts to initial pose")

    def visualize_skeleton(
        self, skeleton_for_view: list[dict[str, Any]], hierarchy: dict[str, Any]
    ) -> None:
        """Create and display skeleton visualization in the editor scene."""
        logger.info(
            f"EditorSceneManager: Visualizing skeleton with {len(skeleton_for_view)} joints"
        )

        # Remove existing skeleton item
        if self.skeleton_item:
            self.scene.removeItem(self.skeleton_item)
            self.skeleton_item = None

        if not skeleton_for_view or not hierarchy:
            logger.warning("EditorSceneManager: No skeleton data to visualize")
            return

        # Create new skeleton item
        self.skeleton_item = SkeletonGraphicsItem(
            skeleton_data=skeleton_for_view,
            hierarchy=hierarchy,
            mechanism_mode=False,  # Editor mode, not mechanism mode
        )

        # Set Z-value to show skeleton behind parts but visible
        self.skeleton_item.setZValue(Z_SKELETON_OVERLAY)

        # Add to scene
        self.scene.addItem(self.skeleton_item)

        # Connect skeleton interaction signals
        self.skeleton_item.signals.joint_clicked.connect(self._on_joint_clicked)
        self.skeleton_item.signals.joint_double_clicked.connect(self._on_joint_double_clicked)

        # Disable automatic bend direction toggle in skeleton item
        # We'll handle it manually to check simulation state
        self.skeleton_item.auto_toggle_bend_on_double_click = False

        logger.info("EditorSceneManager: Skeleton visualization added to scene")

    def update_part_path(self, part_name: str, path: QPainterPath) -> None:
        if part_name in self.current_editor_items:
            self.current_editor_items[part_name].set_motion_path(path)

    def _update_skeleton_visualization(self) -> None:
        """Update skeleton visualization based on current skeleton data."""
        if not self.state.initial_skeleton_data_cache:
            return

        # Convert skeleton data to format expected by SkeletonGraphicsItem
        skeleton_for_view = []
        joints_dict = self.state.initial_skeleton_data_cache.get("joints", {})
        hierarchy = self.state.initial_skeleton_data_cache.get("hierarchy", {})

        for joint_id, joint_data in joints_dict.items():
            skeleton_for_view.append(
                {
                    "id": joint_id,
                    "position": joint_data.get("position", [0, 0]),
                    "parent": joint_data.get("parent_id"),
                    "name": joint_data.get("name", joint_id),
                    "color": "lightblue",  # Default color for editor skeleton
                }
            )

        if skeleton_for_view:
            self.visualize_skeleton(skeleton_for_view, hierarchy)

    def ensure_skeleton_visualization(self) -> None:
        """Ensure skeleton is visualized (public method for external calls)."""
        self._update_skeleton_visualization()

    def _on_part_selection_changed(self, part_name: str) -> None:
        """Handle part selection changes to highlight associated joints."""
        if not self.skeleton_item:
            return

        # Clear previous highlights
        self.skeleton_item.clear_highlights()

        # Highlight joints for selected part
        if part_name:
            joint_ids = self._get_joint_ids_for_part(part_name)
            if joint_ids:
                self.skeleton_item.highlight_joints(joint_ids, "orange")
                logger.debug(
                    f"Highlighted {len(joint_ids)} joints for part '{part_name}': {joint_ids}"
                )

    def _get_joint_ids_for_part(self, part_name: str) -> list[str]:
        """Get the joint IDs associated with a part."""
        joint_ids = []

        # Get part info
        part_info = self.state.current_parts_info.get(part_name)
        if not part_info or not part_info.anchor_joint_id:
            return joint_ids

        # Add the anchor joint
        joint_ids.append(part_info.anchor_joint_id)

        # Add related joints based on part type
        # This mapping defines which joints are visually related to each part
        part_joint_mapping = {
            "left_arm_upper": ["left_shoulder", "left_elbow"],
            "left_arm_lower": ["left_elbow", "left_wrist"],
            "right_arm_upper": ["right_shoulder", "right_elbow"],
            "right_arm_lower": ["right_elbow", "right_wrist"],
            "left_leg_upper": ["left_hip", "left_knee"],
            "left_leg_lower": ["left_knee", "left_ankle"],
            "right_leg_upper": ["right_hip", "right_knee"],
            "right_leg_lower": ["right_knee", "right_ankle"],
            "torso": ["hip", "chest", "neck"],
            "head": ["neck", "head"],
            # Legacy names for backward compatibility
            "left_upper_arm": ["left_shoulder", "left_elbow"],
            "left_forearm": ["left_elbow", "left_wrist"],
            "right_upper_arm": ["right_shoulder", "right_elbow"],
            "right_forearm": ["right_elbow", "right_wrist"],
            "left_shin": ["left_knee", "left_ankle"],
            "right_shin": ["right_knee", "right_ankle"],
        }

        # Add related joints
        related_joints = part_joint_mapping.get(part_name, [])
        for joint_name in related_joints:
            # Try to find the actual joint ID from skeleton data
            if self.state.initial_skeleton_data_cache:
                joints_dict = self.state.initial_skeleton_data_cache.get("joints", {})

                # Look for joint by name (abstract name -> standardized ID)
                for joint_id, joint_data in joints_dict.items():
                    if joint_data.get("name") == joint_name or joint_id.startswith(joint_name):
                        if joint_id not in joint_ids:
                            joint_ids.append(joint_id)
                        break

        return joint_ids

    def _on_joint_clicked(self, joint_id: str) -> None:
        """Handle joint click events."""
        logger.debug(f"Joint clicked: {joint_id}")
        # You can add additional logic here, such as selecting the related part

    def _on_joint_double_clicked(self, joint_id: str) -> None:
        """Handle joint double-click events - only allowed when simulation is stopped."""
        # Check if simulation is stopped
        if self.state.simulation_state == "playing":
            logger.debug(f"Joint double-click ignored during animation playback")
            return

        logger.debug(f"Joint double-clicked: {joint_id} - toggling bend direction")

        if self.skeleton_item:
            # Manually toggle the bend direction since we disabled auto-toggle
            self.skeleton_item.toggle_joint_bend_direction(joint_id)

            # Get the new bend direction
            bend_direction = self.skeleton_item.get_joint_bend_direction(joint_id)
            logger.info(f"Joint {joint_id} bend direction set to: {bend_direction:.2f} radians ({math.degrees(bend_direction):.0f}°)")

            # Store bend directions for IK solver
            if not hasattr(self.state, 'joint_bend_directions'):
                self.state.joint_bend_directions = {}
            self.state.joint_bend_directions[joint_id] = bend_direction
