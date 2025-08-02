"""
Position and Distance Constraint Implementations

Implements spatial positioning constraints for mechanism design.
"""

import numpy as np
from typing import Tuple, Optional
from ..base import BaseConstraint, ConstraintType


class PositionConstraint(BaseConstraint):
    """
    Constraint to fix a point at a specific position.
    
    Useful for fixing anchor points, ground connections, or other
    spatial references in mechanism design.
    """
    
    def __init__(self, name: str, target_position: Tuple[float, float], 
                 point_index: int = 0, tolerance: float = 0.1):
        """
        Initialize position constraint.
        
        Args:
            name: Constraint name
            target_position: Target (x, y) position
            point_index: Index of point in state vector (0-based)
            tolerance: Position tolerance
        """
        super().__init__(name, ConstraintType.EQUALITY)
        
        self.target_position = target_position
        self.point_index = point_index
        self.tolerance = tolerance
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate position constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Position error [x_error, y_error]
        """
        if len(state) < (self.point_index + 1) * 2:
            return np.array([1000.0, 1000.0])  # Large violation
        
        # Extract current position
        x_idx = self.point_index * 2
        y_idx = self.point_index * 2 + 1
        
        current_x = state[x_idx]
        current_y = state[y_idx]
        
        # Calculate errors
        target_x, target_y = self.target_position
        x_error = current_x - target_x
        y_error = current_y - target_y
        
        return np.array([x_error, y_error])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of position constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Gradient matrix
        """
        grad = np.zeros((2, len(state)))
        
        if len(state) >= (self.point_index + 1) * 2:
            x_idx = self.point_index * 2
            y_idx = self.point_index * 2 + 1
            
            # Gradient is 1 for the constrained coordinates
            grad[0, x_idx] = 1.0  # dx_error/dx
            grad[1, y_idx] = 1.0  # dy_error/dy
        
        return grad
    
    def is_satisfied(self, state: np.ndarray) -> bool:
        """
        Check if constraint is satisfied within tolerance.
        
        Args:
            state: Current state vector
            
        Returns:
            True if constraint is satisfied
        """
        errors = self.evaluate(state)
        error_magnitude = np.linalg.norm(errors)
        return error_magnitude <= self.tolerance
    
    def update_target(self, new_position: Tuple[float, float]):
        """Update target position."""
        self.target_position = new_position


class DistanceConstraint(BaseConstraint):
    """
    Constraint to maintain a specific distance between two points.
    
    Useful for maintaining link lengths, joint separations, or other
    distance relationships in mechanism design.
    """
    
    def __init__(self, name: str, point_a_index: int, point_b_index: int,
                 target_distance: float, tolerance: float = 0.1):
        """
        Initialize distance constraint.
        
        Args:
            name: Constraint name
            point_a_index: Index of first point (0-based)
            point_b_index: Index of second point (0-based)
            target_distance: Target distance between points
            tolerance: Distance tolerance
        """
        super().__init__(name, ConstraintType.EQUALITY)
        
        self.point_a_index = point_a_index
        self.point_b_index = point_b_index
        self.target_distance = target_distance
        self.tolerance = tolerance
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate distance constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Distance error
        """
        required_length = max(self.point_a_index + 1, self.point_b_index + 1) * 2
        
        if len(state) < required_length:
            return np.array([1000.0])  # Large violation
        
        # Extract point positions
        xa_idx = self.point_a_index * 2
        ya_idx = self.point_a_index * 2 + 1
        xb_idx = self.point_b_index * 2
        yb_idx = self.point_b_index * 2 + 1
        
        xa, ya = state[xa_idx], state[ya_idx]
        xb, yb = state[xb_idx], state[yb_idx]
        
        # Calculate current distance
        current_distance = np.sqrt((xb - xa)**2 + (yb - ya)**2)
        
        # Distance error
        distance_error = current_distance - self.target_distance
        
        return np.array([distance_error])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of distance constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Gradient matrix
        """
        grad = np.zeros((1, len(state)))
        
        required_length = max(self.point_a_index + 1, self.point_b_index + 1) * 2
        
        if len(state) < required_length:
            return grad
        
        # Extract point positions
        xa_idx = self.point_a_index * 2
        ya_idx = self.point_a_index * 2 + 1
        xb_idx = self.point_b_index * 2
        yb_idx = self.point_b_index * 2 + 1
        
        xa, ya = state[xa_idx], state[ya_idx]
        xb, yb = state[xb_idx], state[yb_idx]
        
        # Calculate current distance
        dx = xb - xa
        dy = yb - ya
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance < 1e-12:
            # Avoid division by zero
            return grad
        
        # Gradient components
        grad[0, xa_idx] = -dx / distance  # d/dxa
        grad[0, ya_idx] = -dy / distance  # d/dya
        grad[0, xb_idx] = dx / distance   # d/dxb
        grad[0, yb_idx] = dy / distance   # d/dyb
        
        return grad
    
    def is_satisfied(self, state: np.ndarray) -> bool:
        """
        Check if constraint is satisfied within tolerance.
        
        Args:
            state: Current state vector
            
        Returns:
            True if constraint is satisfied
        """
        error = self.evaluate(state)[0]
        return abs(error) <= self.tolerance
    
    def update_target_distance(self, new_distance: float):
        """Update target distance."""
        self.target_distance = new_distance