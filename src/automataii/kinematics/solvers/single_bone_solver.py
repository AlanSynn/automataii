"""Single bone IK solver implementation."""

import logging
import math
from typing import Dict, Any, Optional, Tuple

from PyQt6.QtCore import QPointF

from .base_solver import BaseSolver, IKSolution


class SingleBoneSolver(BaseSolver):
    """IK solver for single bone chains (2 joints).
    
    This solver handles simple rotation-only IK, where one joint
    rotates to point toward a target.
    """
    
    def solve(self, 
              target: QPointF,
              joint_positions: Dict[str, QPointF],
              constraints: Dict[str, Any]) -> IKSolution:
        """Solve single bone IK.
        
        Args:
            target: Target position for end effector
            joint_positions: Dict with 'root' and 'end' positions
            constraints: Dict with optional 'min_angle', 'max_angle'
            
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
        end_pos = joint_positions['end']
        
        # Calculate current bone vector
        bone_vec = QPointF(end_pos.x() - root_pos.x(), 
                          end_pos.y() - root_pos.y())
        bone_length = self.distance(root_pos, end_pos)
        
        # Calculate target vector
        target_vec = QPointF(target.x() - root_pos.x(),
                           target.y() - root_pos.y())
        target_dist = self.distance(root_pos, target)
        
        # If target is too close, adjust it
        if target_dist < bone_length * 0.1:
            target_dist = bone_length * 0.1
            scale = target_dist / (self.distance(QPointF(0, 0), target_vec) + 1e-6)
            target_vec = QPointF(target_vec.x() * scale, target_vec.y() * scale)
            target = QPointF(root_pos.x() + target_vec.x(),
                           root_pos.y() + target_vec.y())
        
        # Calculate angle to target
        current_angle = math.atan2(bone_vec.y(), bone_vec.x())
        target_angle = math.atan2(target_vec.y(), target_vec.x())
        
        # Apply constraints
        min_angle = constraints.get('min_angle', -180)
        max_angle = constraints.get('max_angle', 180)
        
        target_angle_deg = math.degrees(target_angle)
        target_angle_deg = self.normalize_angle(target_angle_deg)
        target_angle_deg = max(min_angle, min(max_angle, target_angle_deg))
        target_angle = math.radians(target_angle_deg)
        
        # Calculate new end position
        new_end_x = root_pos.x() + bone_length * math.cos(target_angle)
        new_end_y = root_pos.y() + bone_length * math.sin(target_angle)
        new_end_pos = QPointF(new_end_x, new_end_y)
        
        # Calculate residual error
        residual = self.distance(new_end_pos, target)
        
        # Prepare solution
        solution = IKSolution(
            success=True,
            joint_positions={
                'root': root_pos,
                'end': new_end_pos
            },
            joint_angles={
                'root': target_angle_deg
            },
            iterations=1,
            residual=residual
        )
        
        self._last_solution = solution
        
        logging.debug(f"SingleBoneSolver: angle={target_angle_deg:.2f}°, residual={residual:.3f}")
        
        return solution
    
    def validate_input(self, 
                      target: QPointF,
                      joint_positions: Dict[str, QPointF],
                      constraints: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input parameters."""
        # Check required joints
        if 'root' not in joint_positions:
            return False, "Missing 'root' joint position"
        if 'end' not in joint_positions:
            return False, "Missing 'end' joint position"
        
        # Check for valid positions
        root_pos = joint_positions['root']
        end_pos = joint_positions['end']
        
        if root_pos is None or end_pos is None:
            return False, "Joint positions cannot be None"
        
        # Check bone length
        bone_length = self.distance(root_pos, end_pos)
        if bone_length < 0.01:
            return False, "Bone length too small"
        
        # Validate constraints
        if 'min_angle' in constraints and 'max_angle' in constraints:
            if constraints['min_angle'] > constraints['max_angle']:
                return False, "min_angle cannot be greater than max_angle"
        
        return True, None