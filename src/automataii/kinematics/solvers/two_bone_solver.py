"""Two bone IK solver implementation."""

import logging
import math
from typing import Dict, Any, Optional, Tuple

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform

from .base_solver import BaseSolver, IKSolution


class TwoBoneSolver(BaseSolver):
    """IK solver for two bone chains (3 joints).
    
    This solver handles typical arm/leg IK with shoulder/hip,
    elbow/knee, and wrist/ankle joints.
    """
    
    def solve(self, 
              target: QPointF,
              joint_positions: Dict[str, QPointF],
              constraints: Dict[str, Any]) -> IKSolution:
        """Solve two bone IK using law of cosines.
        
        Args:
            target: Target position for end effector
            joint_positions: Dict with 'root', 'middle', 'end' positions
            constraints: Dict with 'bend_direction', angle limits, etc.
            
        Returns:
            IKSolution with results
        """
        # Validate input
        is_valid, error_msg = self.validate_input(target, joint_positions, constraints)
        if not is_valid:
            return IKSolution(
                success=False,
                joint_positions=joint_positions,
                joint_angles={},
                error=error_msg
            )
        
        # Extract positions
        root_pos = joint_positions['root']
        middle_pos = joint_positions['middle']
        end_pos = joint_positions['end']
        
        # Calculate bone lengths
        bone1_length = self.distance(root_pos, middle_pos)
        bone2_length = self.distance(middle_pos, end_pos)
        
        # Calculate distance to target
        target_dist = self.distance(root_pos, target)
        
        # Check if target is reachable
        max_reach = bone1_length + bone2_length
        min_reach = abs(bone1_length - bone2_length)
        
        if target_dist > max_reach:
            # Target too far - stretch toward it
            direction = QPointF(target.x() - root_pos.x(), 
                              target.y() - root_pos.y())
            scale = max_reach / target_dist
            target = QPointF(root_pos.x() + direction.x() * scale,
                           root_pos.y() + direction.y() * scale)
            target_dist = max_reach
        elif target_dist < min_reach:
            # Target too close
            direction = QPointF(target.x() - root_pos.x(),
                              target.y() - root_pos.y())
            if target_dist < 0.01:  # Avoid division by zero
                direction = QPointF(1, 0)
                target_dist = 0.01
            scale = min_reach / target_dist
            target = QPointF(root_pos.x() + direction.x() * scale,
                           root_pos.y() + direction.y() * scale)
            target_dist = min_reach
        
        # Use law of cosines to find angles
        # cos(C) = (a² + b² - c²) / (2ab)
        
        # Angle at root joint
        cos_angle1 = (bone1_length * bone1_length + target_dist * target_dist - 
                     bone2_length * bone2_length) / (2 * bone1_length * target_dist)
        cos_angle1 = max(-1, min(1, cos_angle1))  # Clamp to valid range
        angle1 = math.acos(cos_angle1)
        
        # Angle at middle joint
        cos_angle2 = (bone1_length * bone1_length + bone2_length * bone2_length - 
                     target_dist * target_dist) / (2 * bone1_length * bone2_length)
        cos_angle2 = max(-1, min(1, cos_angle2))  # Clamp to valid range
        angle2 = math.acos(cos_angle2)
        
        # Calculate base angle (angle from root to target)
        base_angle = math.atan2(target.y() - root_pos.y(), 
                               target.x() - root_pos.x())
        
        # Apply bend direction
        bend_direction = constraints.get('bend_direction', 1)
        final_angle1 = base_angle - angle1 * bend_direction
        
        # Calculate new joint positions
        new_middle_x = root_pos.x() + bone1_length * math.cos(final_angle1)
        new_middle_y = root_pos.y() + bone1_length * math.sin(final_angle1)
        new_middle_pos = QPointF(new_middle_x, new_middle_y)
        
        # Calculate end position
        middle_angle = final_angle1 + math.pi - angle2 * bend_direction
        new_end_x = new_middle_x + bone2_length * math.cos(middle_angle)
        new_end_y = new_middle_y + bone2_length * math.sin(middle_angle)
        new_end_pos = QPointF(new_end_x, new_end_y)
        
        # Calculate residual error
        residual = self.distance(new_end_pos, target)
        
        # Prepare solution
        solution = IKSolution(
            success=True,
            joint_positions={
                'root': root_pos,
                'middle': new_middle_pos,
                'end': new_end_pos
            },
            joint_angles={
                'root': math.degrees(final_angle1),
                'middle': math.degrees(angle2)  # Relative angle
            },
            iterations=1,
            residual=residual
        )
        
        self._last_solution = solution
        
        logging.debug(f"TwoBoneSolver: residual={residual:.3f}")
        
        return solution
    
    def validate_input(self, 
                      target: QPointF,
                      joint_positions: Dict[str, QPointF],
                      constraints: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input parameters."""
        # Check required joints
        required_joints = ['root', 'middle', 'end']
        for joint in required_joints:
            if joint not in joint_positions:
                return False, f"Missing '{joint}' joint position"
            if joint_positions[joint] is None:
                return False, f"Joint position '{joint}' cannot be None"
        
        # Check bone lengths
        root_pos = joint_positions['root']
        middle_pos = joint_positions['middle']
        end_pos = joint_positions['end']
        
        bone1_length = self.distance(root_pos, middle_pos)
        bone2_length = self.distance(middle_pos, end_pos)
        
        if bone1_length < 0.01:
            return False, "First bone length too small"
        if bone2_length < 0.01:
            return False, "Second bone length too small"
        
        # Validate bend direction
        bend_dir = constraints.get('bend_direction', 1)
        if bend_dir not in [-1, 1]:
            return False, "bend_direction must be 1 or -1"
        
        return True, None
    
    def calculate_pole_vector_position(self,
                                     root: QPointF,
                                     middle: QPointF,
                                     end: QPointF,
                                     distance: float = 1.0) -> QPointF:
        """Calculate pole vector position for IK constraint.
        
        The pole vector helps control the bend direction of the middle joint.
        
        Args:
            root: Root joint position
            middle: Middle joint position  
            end: End joint position
            distance: Distance from the chain to place pole vector
            
        Returns:
            Pole vector position
        """
        # Calculate midpoint of the chain
        mid_x = (root.x() + end.x()) / 2
        mid_y = (root.y() + end.y()) / 2
        midpoint = QPointF(mid_x, mid_y)
        
        # Calculate perpendicular direction
        chain_dir = QPointF(end.x() - root.x(), end.y() - root.y())
        perp_dir = QPointF(-chain_dir.y(), chain_dir.x())
        
        # Normalize perpendicular direction
        length = self.distance(QPointF(0, 0), perp_dir)
        if length > 0:
            perp_dir = QPointF(perp_dir.x() / length, perp_dir.y() / length)
        
        # Calculate pole position
        pole_x = midpoint.x() + perp_dir.x() * distance
        pole_y = midpoint.y() + perp_dir.y() * distance
        
        return QPointF(pole_x, pole_y)