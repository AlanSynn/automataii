"""Simulation control for the editor view."""

import logging
from typing import Dict, Any, Tuple, List, Optional
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QTransform

from ...graphics_items.part_item import CharacterPartItem
from ...graphics_items.skeleton_item import SkeletonGraphicsItem
from ....config.z_indices import Z_SKELETON_OVERLAY


class SimulationController(QObject):
    """Controls simulation state and animation updates."""
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
        # Simulation state
        self._animation_time = 0.0
        self._animation_duration = 30.0
        self._original_transforms: Dict[str, QTransform] = {}
        
        # Skeleton visualization
        self._skeleton_item: SkeletonGraphicsItem = None
        self._joint_map: Dict[str, str] = {}  # original_name -> std_id
        
    def set_joint_map(self, joint_map: Dict[str, str]):
        """Sets the joint mapping for animation updates."""
        self._joint_map = joint_map or {}
        logging.debug(f"Joint map set with {len(self._joint_map)} entries")
        
    def start_simulation(self):
        """Prepares for simulation mode."""
        self._save_original_transforms()
        self._animation_time = 0.0
        
    def stop_simulation(self):
        """Ends simulation mode."""
        self.reset_simulation()
        
    def reset_simulation(self):
        """Resets to initial state."""
        self._restore_original_transforms()
        self._animation_time = 0.0
        
    def update_animation_time(self, time: float):
        """Updates the current animation time."""
        self._animation_time = time % self._animation_duration
        
    def visualize_skeleton(
        self, 
        skeleton_data: List[Dict[str, Any]], 
        hierarchy_data: Dict[str, List[str]]
    ):
        """Visualizes the skeleton structure."""
        logging.debug(
            f"Visualizing skeleton with {len(skeleton_data)} joints"
        )
        
        if not self.view.scene():
            logging.error("No scene available for skeleton visualization")
            return
            
        if not skeleton_data:
            # Clear skeleton
            if self._skeleton_item:
                self._skeleton_item.load_skeleton_data([], {})
            return
            
        if self._skeleton_item is None:
            # Create new skeleton item
            self._skeleton_item = SkeletonGraphicsItem(skeleton_data, hierarchy_data)
            self.view.scene().addItem(self._skeleton_item)
            self._skeleton_item.setZValue(Z_SKELETON_OVERLAY)
        else:
            # Update existing skeleton
            self._skeleton_item.load_skeleton_data(skeleton_data, hierarchy_data)
            
        self.view.scene().update()
        
    def update_skeleton_animation(
        self, 
        animated_positions: Dict[str, Tuple[float, float]]
    ):
        """Updates skeleton joint positions."""
        if self._skeleton_item:
            self._skeleton_item.set_animated_pose(animated_positions)
        else:
            logging.warning("No skeleton item to update")
            
    def update_visuals_from_animation_data(
        self, 
        joint_data: Dict[str, Dict[str, Any]]
    ):
        """Updates both skeleton and part visuals from animation data."""
        if not self.view.scene():
            logging.warning("No scene for animation update")
            return
            
        # Update skeleton positions
        joint_positions = {}
        for joint_id, data in joint_data.items():
            pos = data.get("scene_position")
            if pos and isinstance(pos, QPointF):
                joint_positions[joint_id] = (pos.x(), pos.y())
                
        if self._skeleton_item:
            self._skeleton_item.set_animated_pose(joint_positions)
            
        # Update part items
        self._update_part_items(joint_data)
        
        self.view.scene().update()
        
    def _update_part_items(self, joint_data: Dict[str, Dict[str, Any]]):
        """Updates CharacterPartItem positions and rotations."""
        if not hasattr(self.view, 'parent_window'):
            return
            
        if not hasattr(self.view.parent_window, 'current_editor_items'):
            return
            
        items = self.view.parent_window.current_editor_items
        if not isinstance(items, dict):
            return
            
        for part_item in items.values():
            if not isinstance(part_item, CharacterPartItem):
                continue
                
            # Get anchor joint
            original_anchor = part_item.anchor_joint_id
            if not original_anchor:
                continue
                
            # Map to standardized ID
            std_anchor = self._joint_map.get(original_anchor)
            if not std_anchor:
                logging.warning(
                    f"No standardized ID for anchor '{original_anchor}'"
                )
                continue
                
            # Get joint data
            if std_anchor not in joint_data:
                logging.warning(
                    f"No animation data for joint '{std_anchor}'"
                )
                continue
                
            # Apply transformation
            transform_data = joint_data[std_anchor]
            scene_pos = transform_data.get("scene_position")
            rotation = transform_data.get("world_rotation_degrees", part_item.rotation())
            
            if isinstance(scene_pos, QPointF):
                part_item.setRotation(float(rotation))
                part_item.set_scene_position_from_anchor(scene_pos)
                
    def _save_original_transforms(self):
        """Saves the current transforms of all part items."""
        self._original_transforms.clear()
        
        if not hasattr(self.view, 'parent_window'):
            return
            
        items = getattr(self.view.parent_window, 'editor_items', {})
        
        for name, item in items.items():
            if isinstance(item, CharacterPartItem):
                self._original_transforms[name] = item.transform()
                
        logging.debug(f"Saved {len(self._original_transforms)} transforms")
        
    def _restore_original_transforms(self):
        """Restores saved transforms."""
        logging.debug(f"Restoring {len(self._original_transforms)} transforms")
        
        for item_name, transform in self._original_transforms.items():
            item = self._get_part_item(item_name)
            if item and item.scene() == self.view.scene():
                item.setTransform(transform)
            else:
                logging.warning(f"Could not restore transform for {item_name}")
                
        self.view.scene().update()
        
    def _get_part_item(self, name: str) -> Optional[CharacterPartItem]:
        """Gets a part item by name."""
        if hasattr(self.view, 'parent_window'):
            items = getattr(self.view.parent_window, 'editor_items', {})
            return items.get(name)
        return None