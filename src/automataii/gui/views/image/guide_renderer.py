"""Perpendicular cut guide rendering for skeleton joints."""

import logging
from typing import Optional, List, Any
from PyQt6.QtWidgets import QGraphicsLineItem
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtCore import Qt, QPointF, QLineF


def normalize_vector(vector: QPointF) -> QPointF:
    """Normalizes a QPointF vector."""
    line = QLineF(QPointF(0, 0), vector)
    length = line.length()
    if length == 0:
        return QPointF(0, 0)
    return vector / length


def perpendicular_vector(vector: QPointF) -> QPointF:
    """Returns a vector perpendicular to the input vector (rotated 90 deg counter-clockwise)."""
    return QPointF(-vector.y(), vector.x())


class GuideRenderer:
    """Handles perpendicular cut guide rendering for skeleton joints."""
    
    def __init__(self, view):
        self.view = view
        self.current_guide_lines: List[QGraphicsLineItem] = []
        self.last_active_joint_for_guide = None
    
    def calculate_perpendicular_cut_guide(self, joint) -> Optional[QLineF]:
        """Calculates a perpendicular line segment at the joint, oriented along its bone(s)."""
        if not joint or not joint.scene():
            return None
        
        joint_pos = joint.pos()  # Parent (image_item) coordinates
        
        # Get connected lines from skeleton manager
        connected_lines = []
        if hasattr(self.view, 'skeleton_manager'):
            connected_lines = self.view.skeleton_manager.get_lines_connected_to_joint(joint)
        
        guide_direction = QPointF(0, 0)
        
        if not connected_lines:
            logging.debug(
                f"No connected lines for joint to calculate guide."
            )
            return None
        
        if len(connected_lines) == 1:
            # Terminal joint (connected to one bone)
            line = connected_lines[0]
            other_joint = line.joint1 if line.joint2 == joint else line.joint2
            if not other_joint:
                return None
            
            bone_vector = other_joint.pos() - joint_pos
            guide_direction = perpendicular_vector(bone_vector)
            
        else:  # len(connected_lines) >= 2 (intermediate joint)
            # For simplicity, consider the first two connected lines
            line1 = connected_lines[0]
            other_joint1 = line1.joint1 if line1.joint2 == joint else line1.joint2
            if not other_joint1:
                return None
            
            line2 = connected_lines[1]
            other_joint2 = line2.joint1 if line2.joint2 == joint else line2.joint2
            if not other_joint2:
                return None
            
            vec1 = other_joint1.pos() - joint_pos
            vec2 = other_joint2.pos() - joint_pos
            
            norm_vec1 = normalize_vector(vec1)
            norm_vec2 = normalize_vector(vec2)
            
            if (norm_vec1 + norm_vec2).isNull():
                guide_direction = perpendicular_vector(norm_vec1)
            else:
                bisector_direction = normalize_vector(norm_vec1 + norm_vec2)
                guide_direction = perpendicular_vector(bisector_direction)
        
        if guide_direction.isNull():
            logging.debug(f"Guide direction is null")
            return None
        
        normalized_guide_dir = normalize_vector(guide_direction)
        guide_length = 60  # pixels in local image_item scale
        
        # Guide line points are relative to the joint's position
        p1_local = joint_pos + normalized_guide_dir * (guide_length / 2)
        p2_local = joint_pos - normalized_guide_dir * (guide_length / 2)
        
        # If image_item exists, map these local points to scene coordinates
        if hasattr(self.view, 'image_manager') and self.view.image_manager.image_item:
            p1_scene = self.view.image_manager.image_item.mapToScene(p1_local)
            p2_scene = self.view.image_manager.image_item.mapToScene(p2_local)
            return QLineF(p1_scene, p2_scene)
        else:
            # Fallback if no image_item
            return QLineF(
                joint_pos + normalized_guide_dir * (guide_length / 2),
                joint_pos - normalized_guide_dir * (guide_length / 2),
            )
    
    def update_and_draw_cut_guides(self, active_joint: Optional[Any]):
        """Updates and draws perpendicular cut guides for the active joint."""
        # Clear existing guide lines
        for item in self.current_guide_lines:
            if item.scene():
                self.view.scene().removeItem(item)
        self.current_guide_lines = []
        
        if not active_joint or not self.view.scene():
            return
        
        guide_line_data = self.calculate_perpendicular_cut_guide(active_joint)
        
        if guide_line_data:
            pen = QPen(QColor("cyan"), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)  # Keep pen width constant regardless of zoom
            guide_item = self.view.scene().addLine(guide_line_data, pen)
            guide_item.setZValue(150)  # Ensure it's visible above most things
            self.current_guide_lines.append(guide_item)
            logging.debug(f"Drew cut guide for joint")
    
    def clear_guides(self):
        """Clear all guide lines."""
        for item in self.current_guide_lines:
            if item.scene():
                self.view.scene().removeItem(item)
        self.current_guide_lines = []
        self.last_active_joint_for_guide = None