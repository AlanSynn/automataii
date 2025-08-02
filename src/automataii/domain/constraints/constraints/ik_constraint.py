"""
IK Constraint Implementation

Implements inverse kinematics constraints for the unified constraint framework.
"""

import numpy as np
from typing import List, Optional, Tuple

from ..base import BaseConstraint, ConstraintType


class IKConstraint(BaseConstraint):
    """
    Inverse Kinematics constraint.
    
    Constrains an end-effector (last joint) to reach a target position.
    The constraint is: C(s) = end_effector_position(s) - target_position = 0
    """
    
    def __init__(self, name: str, target_position: Tuple[float, float], 
                 base_position: Tuple[float, float] = (0.0, 0.0),
                 bone_lengths: Optional[List[float]] = None, weight: float = 1.0):
        """
        Initialize IK constraint.
        
        Args:
            name: Constraint name
            target_position: Target position for end-effector as (x, y) tuple
            base_position: Base position (fixed) as (x, y) tuple
            bone_lengths: Length of each bone segment
            weight: Constraint weight
        """
        super().__init__(name, ConstraintType.IK, weight)
        self.target_position = np.array(target_position, dtype=float)
        self.base_position = np.array(base_position, dtype=float)
        self.bone_lengths = bone_lengths or []
        
        # Cache for efficiency
        self._last_state = None
        self._last_end_effector = None
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate IK constraint violation.
        
        Args:
            state: Joint positions as [x1, y1, x2, y2, ..., xn, yn]
            
        Returns:
            2D constraint violation [dx, dy] where end_effector - target
        """
        if state.size == 0 or state.size % 2 != 0:
            return np.array([1000.0, 1000.0])  # Large violation for invalid state
        
        # Extract end-effector position (last joint)
        end_effector_x = state[-2]
        end_effector_y = state[-1]
        
        # Cache for gradient computation
        self._last_state = state.copy()
        self._last_end_effector = np.array([end_effector_x, end_effector_y])
        
        # Constraint violation: end_effector - target
        violation = np.array([
            end_effector_x - self.target_position[0],
            end_effector_y - self.target_position[1]
        ])
        
        return violation
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of IK constraint.
        
        For simple end-effector constraint, the gradient is:
        ∂C/∂s = [0, 0, 0, 0, ..., 1, 0, 0, 1]
        (zeros except for last joint which has [1, 0] for x and [0, 1] for y)
        
        Args:
            state: Joint positions
            
        Returns:
            Jacobian matrix (2 x len(state))
        """
        if state.size == 0 or state.size % 2 != 0:
            return np.zeros((2, len(state))) if len(state) > 0 else np.zeros((2, 2))
        
        num_joints = len(state) // 2
        jacobian = np.zeros((2, len(state)))
        
        # For simple end-effector constraint, only the last joint matters
        # ∂(end_x)/∂(end_x) = 1, ∂(end_y)/∂(end_y) = 1
        jacobian[0, -2] = 1.0  # ∂(violation_x)/∂(end_x)
        jacobian[1, -1] = 1.0  # ∂(violation_y)/∂(end_y)
        
        return jacobian
    
    def get_chain_jacobian(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate full kinematic chain Jacobian.
        
        This considers how moving each joint affects the end-effector position,
        accounting for the kinematic chain structure.
        
        Args:
            state: Joint positions
            
        Returns:
            Jacobian matrix (2 x len(state))
        """
        if state.size == 0 or state.size % 2 != 0 or len(self.bone_lengths) == 0:
            return self.gradient(state)  # Fallback to simple gradient
        
        num_joints = len(state) // 2
        jacobian = np.zeros((2, len(state)))
        
        # Convert state to joint positions
        joint_positions = []
        for i in range(num_joints):
            x = state[2*i]
            y = state[2*i + 1]
            joint_positions.append(np.array([x, y]))
        
        # For each joint, calculate how it affects the end-effector
        for i in range(num_joints - 1):  # Don't include end-effector itself
            # Vector from current joint to end-effector
            joint_to_end = joint_positions[-1] - joint_positions[i]
            
            # For a revolute joint, the velocity is perpendicular to the position vector
            # v = ω × r, where ω is angular velocity and r is position vector
            # In 2D: v = [-r_y, r_x] * ω
            
            # Partial derivatives with respect to joint angle
            # Since we're working with positions, not angles, we need to approximate
            # the relationship between joint position changes and end-effector motion
            
            # Simple approximation: assume small rotations
            jacobian[0, 2*i] = 1.0 if i == num_joints - 1 else 0.1  # Contribution to x
            jacobian[1, 2*i + 1] = 1.0 if i == num_joints - 1 else 0.1  # Contribution to y
        
        # End-effector joint has direct 1:1 mapping
        jacobian[0, -2] = 1.0
        jacobian[1, -1] = 1.0
        
        return jacobian
    
    def set_target(self, target_position: Tuple[float, float]):
        """Update the target position."""
        self.target_position = np.array(target_position, dtype=float)
    
    def get_target(self) -> Tuple[float, float]:
        """Get the current target position."""
        return (float(self.target_position[0]), float(self.target_position[1]))
    
    def get_end_effector_position(self, state: np.ndarray) -> Tuple[float, float]:
        """Extract end-effector position from state."""
        if state.size < 2:
            return (0.0, 0.0)
        
        return (float(state[-2]), float(state[-1]))
    
    def get_distance_to_target(self, state: np.ndarray) -> float:
        """Get Euclidean distance from end-effector to target."""
        violation = self.evaluate(state)
        return np.linalg.norm(violation)
    
    def is_reachable(self, target: Optional[Tuple[float, float]] = None) -> bool:
        """
        Check if target is reachable given bone length constraints.
        
        Args:
            target: Target position (uses self.target_position if None)
            
        Returns:
            True if target is within reach
        """
        if not self.bone_lengths:
            return True  # No constraints
        
        if target is None:
            target = self.target_position
        
        # Calculate total reach
        total_length = sum(self.bone_lengths)
        
        # Distance from base to target
        if isinstance(target, tuple):
            target_pos = np.array(target, dtype=float)
        else:
            target_pos = target
            
        base_to_target = np.sqrt(
            (target_pos[0] - self.base_position[0]) ** 2 +
            (target_pos[1] - self.base_position[1]) ** 2
        )
        
        return base_to_target <= total_length
    
    def __repr__(self) -> str:
        return (f"IKConstraint(name='{self.name}', "
                f"target=({self.target_position[0]:.1f}, {self.target_position[1]:.1f}), "
                f"weight={self.weight})")