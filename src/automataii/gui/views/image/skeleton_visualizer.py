"""
Manages the visualization of skeleton data in a QGraphicsScene.
"""

import logging
from typing import Dict, Optional

from PyQt6.QtWidgets import QGraphicsScene

from automataii.gui.graphics_items import BoneItem, JointItem

class SkeletonVisualizer:
    """Manages the VISUALIZATION of skeleton data in a QGraphicsScene."""

    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self._joint_items: Dict[str, JointItem] = {}
        self._bone_items: Dict[str, BoneItem] = {}
        logging.info("SkeletonVisualizer initialized.")

    def load_skeleton(self, skeleton_data: Optional[dict]):
        """
        Loads skeleton data to create or update visual items.
        Expects data from the core SkeletonManager (StandardizedSkeletonModel format).
        """
        self.clear()

        if not skeleton_data or not isinstance(skeleton_data, dict):
            logging.info("Skeleton visualizer: No skeleton data provided to display.")
            return

        joints_data = skeleton_data.get("joints", {})
        hierarchy_data = skeleton_data.get("hierarchy", {})

        if not joints_data:
            logging.warning("Skeleton visualizer: Skeleton data has no 'joints'.")
            return

        # Create Joint Items
        for joint_id, joint_info in joints_data.items():
            pos = joint_info.get("position", (0, 0))
            joint_item = JointItem(joint_id, pos[0], pos[1])
            self._joint_items[joint_id] = joint_item
            self.scene.addItem(joint_item)

        # Create Bone Items
        for parent_id, child_ids in hierarchy_data.items():
            parent_item = self._joint_items.get(parent_id)
            if not parent_item:
                continue
            for child_id in child_ids:
                child_item = self._joint_items.get(child_id)
                if child_item:
                    bone_id = f"{parent_id}-{child_id}"
                    bone_item = BoneItem(parent_item, child_item)
                    self._bone_items[bone_id] = bone_item
                    self.scene.addItem(bone_item)

        logging.info(f"Skeleton visualizer: Displayed {len(self._joint_items)} joints and {len(self._bone_items)} bones.")

    def clear(self):
        """Clears all skeleton-related graphics items from the scene."""
        for item in self._joint_items.values():
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        for item in self._bone_items.values():
            if item.scene() == self.scene:
                self.scene.removeItem(item)

        self._joint_items.clear()
        self._bone_items.clear()
        logging.info("Skeleton visualizer: Cleared all visual items.")

    def set_visibility(self, visible: bool):
        """Sets the visibility of all skeleton items."""
        for item in self._joint_items.values():
            item.setVisible(visible)
        for item in self._bone_items.values():
            item.setVisible(visible)
        logging.info(f"Skeleton visualizer: Set visibility to {visible}.")