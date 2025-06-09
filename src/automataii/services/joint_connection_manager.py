"""
Joint Connection Manager for integrating smooth joint connections with the animation system.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap

from automataii.processing.animation.joint_connection_system import (
    JointConnectionRenderer,
    ConnectionType,
    QtJointConnectionHelper
)
from automataii.core.models.skeleton import StandardizedSkeletonModel

logger = logging.getLogger(__name__)


class JointConnectionManager(QObject):
    """Manages the joint connection system and integrates it with the animation pipeline."""
    
    # Signals
    connections_updated = pyqtSignal(int)  # Emits number of connections found
    rendering_complete = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = JointConnectionRenderer(enabled=False)
        self.skeleton_data = None
        self.parts_info = None
        self.enabled = False
        self.connection_type = ConnectionType.MESH_DEFORM
        self.stiffness = 0.7
        
    def set_enabled(self, enabled: bool):
        """Enable or disable the joint connection system."""
        self.enabled = enabled
        self.renderer.set_enabled(enabled)
        logger.info(f"Joint connection system {'enabled' if enabled else 'disabled'}")
        
    def set_connection_type(self, type_name: str):
        """Set the connection type from string name."""
        type_map = {
            "Mesh Deform": ConnectionType.MESH_DEFORM,
            "Blend": ConnectionType.BLEND,
            "Elastic": ConnectionType.ELASTIC,
            "Rigid": ConnectionType.RIGID
        }
        
        if type_name in type_map:
            self.connection_type = type_map[type_name]
            # Update existing connections
            for connection in self.renderer.connections:
                connection.connection_type = self.connection_type
            logger.info(f"Connection type set to: {type_name}")
            
    def set_stiffness(self, stiffness: float):
        """Set the stiffness for joint connections."""
        self.stiffness = max(0.1, min(1.0, stiffness))
        # Update existing connections
        for connection in self.renderer.connections:
            connection.stiffness = self.stiffness
        logger.info(f"Joint stiffness set to: {self.stiffness}")
        
    def analyze_skeleton(self, skeleton: StandardizedSkeletonModel, parts_info: Dict[str, Any]):
        """Analyze skeleton structure to identify joint connections."""
        if not self.enabled:
            return
            
        try:
            # Convert skeleton model to dict format expected by renderer
            skeleton_data = {
                'joints': {
                    joint_id: {
                        'position': joint.position,
                        'parent_id': joint.parent_id,
                        'name': joint.name
                    }
                    for joint_id, joint in skeleton.joints.items()
                },
                'hierarchy': skeleton.hierarchy,
                'root_joint_ids': skeleton.root_joint_ids
            }
            
            self.skeleton_data = skeleton_data
            self.parts_info = parts_info
            
            # Analyze connections
            self.renderer.analyze_and_setup(skeleton_data, parts_info)
            
            # Update connection properties
            for connection in self.renderer.connections:
                connection.connection_type = self.connection_type
                connection.stiffness = self.stiffness
                
            self.connections_updated.emit(len(self.renderer.connections))
            logger.info(f"Found {len(self.renderer.connections)} joint connections")
            
        except Exception as e:
            logger.error(f"Error analyzing skeleton: {e}")
            self.error_occurred.emit(str(e))
            
    def apply_to_animation_frame(self, parts_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply joint connections to a single animation frame.
        
        Args:
            parts_data: Dictionary of part names to their current frame data
            
        Returns:
            Modified parts data with joint connections applied
        """
        if not self.enabled or not self.renderer.connections:
            return parts_data
            
        try:
            # Render connected parts
            rendered_images = self.renderer.render_connected_parts(parts_data)
            
            # Update parts data with rendered images
            for part_name, image in rendered_images.items():
                if part_name in parts_data:
                    parts_data[part_name]['image'] = image
                    
            return parts_data
            
        except Exception as e:
            logger.error(f"Error applying joint connections: {e}")
            self.error_occurred.emit(str(e))
            return parts_data
            
    def apply_to_scene_items(self, part_items: Dict[str, Any]):
        """
        Apply joint connections to Qt graphics scene items.
        
        Args:
            part_items: Dictionary of part names to QGraphicsPixmapItem instances
        """
        if not self.enabled or not self.skeleton_data:
            return
            
        try:
            QtJointConnectionHelper.apply_joint_connections_to_scene(
                self.renderer, part_items, self.skeleton_data
            )
            self.rendering_complete.emit()
            
        except Exception as e:
            logger.error(f"Error applying to scene items: {e}")
            self.error_occurred.emit(str(e))
            
    def create_debug_overlay(self, image_size: Tuple[int, int], 
                           parts_data: Dict[str, Dict[str, Any]]) -> Optional[QPixmap]:
        """Create a debug visualization overlay showing joint connections."""
        if not self.enabled:
            return None
            
        try:
            debug_image = self.renderer.create_debug_visualization(image_size, parts_data)
            return QtJointConnectionHelper.numpy_to_qpixmap(debug_image)
            
        except Exception as e:
            logger.error(f"Error creating debug overlay: {e}")
            return None
            
    def get_connection_info(self) -> List[Dict[str, Any]]:
        """Get information about current joint connections."""
        info = []
        for conn in self.renderer.connections:
            info.append({
                'part1': conn.part1_name,
                'part2': conn.part2_name,
                'joint': conn.joint_id,
                'type': conn.connection_type.value,
                'stiffness': conn.stiffness,
                'position': conn.joint_position
            })
        return info
        
    def reset(self):
        """Reset the joint connection system."""
        self.renderer.connections.clear()
        self.skeleton_data = None
        self.parts_info = None
        logger.info("Joint connection system reset")