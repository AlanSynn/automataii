# src/automataii/ui/tabs/editor/scene_manager.py

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPointF, pyqtSignal
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsScene

from automataii.models.runtime import PartInfo
from automataii.ui.graphics_items.part_item import CharacterPartItem
from automataii.ui.graphics_items.skeleton_item import SkeletonGraphicsItem
from automataii.config.z_indices import Z_SKELETON_OVERLAY

logger = logging.getLogger(__name__)

class EditorSceneManager:
    """Manages the QGraphicsScene for the EditorTab."""

    def __init__(self, scene: QGraphicsScene, state, parent) -> None:
        self.scene = scene
        self.state = state
        self.parent = parent
        self.current_editor_items: Dict[str, CharacterPartItem] = {}
        self.skeleton_item: Optional[SkeletonGraphicsItem] = None

    def set_parts_data(self, parts_info: Dict[str, PartInfo], project_dir: str) -> None:
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
                else:
                    missing_joints.append((part_name, p_info.anchor_joint_id))
                    logger.warning(f"Part '{part_name}' references missing joint '{p_info.anchor_joint_id}'")
        
        if missing_joints:
            logger.error(f"Skeleton-Part mismatch detected! {len(missing_joints)} parts have invalid joint references.")
            # This indicates skeleton and parts are from different sources

    def update_visuals_from_animation_data(self, ik_results: Dict[str, Any]) -> None:
        """Update part visuals and skeleton from IK animation data."""
        # Update part positions
        for part_name, data in ik_results.items():
            if part_name in self.current_editor_items:
                item = self.current_editor_items[part_name]
                if "position" in data:
                    item.setPos(QPointF(data["position"][0], data["position"][1]))
                if "rotation" in data:
                    item.setRotation(data["rotation"])
        
        # Update skeleton visualization if it exists
        if self.skeleton_item and "joints" in ik_results:
            self.skeleton_item.set_animated_pose(ik_results["joints"])
        
        self.scene.update()

    def visualize_skeleton(self, skeleton_for_view: List[Dict[str, Any]], hierarchy: Dict[str, Any]) -> None:
        """Create and display skeleton visualization in the editor scene."""
        logger.info(f"EditorSceneManager: Visualizing skeleton with {len(skeleton_for_view)} joints")
        
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
            mechanism_mode=False  # Editor mode, not mechanism mode
        )
        
        # Set Z-value to show skeleton behind parts but visible
        self.skeleton_item.setZValue(Z_SKELETON_OVERLAY)
        
        # Add to scene
        self.scene.addItem(self.skeleton_item)
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
            skeleton_for_view.append({
                "id": joint_id,
                "position": joint_data.get("position", [0, 0]),
                "parent": joint_data.get("parent_id"),
                "name": joint_data.get("name", joint_id),
                "color": "lightblue"  # Default color for editor skeleton
            })
        
        if skeleton_for_view:
            self.visualize_skeleton(skeleton_for_view, hierarchy)
    
    def ensure_skeleton_visualization(self) -> None:
        """Ensure skeleton is visualized (public method for external calls)."""
        self._update_skeleton_visualization()
