"""
Collision Constraint Implementation

Implements collision detection and avoidance constraints for spatial planning.
"""

import numpy as np
from typing import List, Tuple, Optional
from ..base import BaseConstraint, ConstraintType


class CollisionConstraint(BaseConstraint):
    """
    Constraint to prevent collisions between two geometric objects.
    
    Implements collision detection using axis-aligned bounding boxes (AABB)
    and distance-based separation constraints.
    """
    
    def __init__(self, name: str, object_a_bounds: Tuple[float, float, float, float],
                 object_b_bounds: Tuple[float, float, float, float], 
                 min_separation: float = 5.0):
        """
        Initialize collision constraint.
        
        Args:
            name: Constraint name
            object_a_bounds: Bounds of first object (x1, y1, x2, y2)
            object_b_bounds: Bounds of second object (x1, y1, x2, y2)
            min_separation: Minimum required separation distance
        """
        super().__init__(name, ConstraintType.INEQUALITY)
        
        self.object_a_bounds = object_a_bounds
        self.object_b_bounds = object_b_bounds
        self.min_separation = min_separation
        
        # Store original bounds for reference
        self.original_a_bounds = object_a_bounds
        self.original_b_bounds = object_b_bounds
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate collision constraint.
        
        Returns positive value when objects are safely separated,
        negative value when collision occurs.
        
        Args:
            state: Current state vector (includes positions of both objects)
            
        Returns:
            Constraint violation value
        """
        if len(state) < 4:
            return np.array([0.0])
        
        # Extract positions (assuming first 4 elements are x1, y1, x2, y2)
        x1, y1, x2, y2 = state[:4]
        
        # Update object bounds based on current positions
        ax1, ay1, ax2, ay2 = self.object_a_bounds
        bx1, by1, bx2, by2 = self.object_b_bounds
        
        # Translate bounds to current positions
        a_bounds = (ax1 + x1, ay1 + y1, ax2 + x1, ay2 + y1)
        b_bounds = (bx1 + x2, by1 + y2, bx2 + x2, by2 + y2)
        
        # Calculate minimum distance between bounding boxes
        distance = self._calculate_box_distance(a_bounds, b_bounds)
        
        # Constraint: distance >= min_separation
        # Return positive when satisfied, negative when violated
        return np.array([distance - self.min_separation])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of collision constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Gradient vector
        """
        if len(state) < 4:
            return np.zeros((1, len(state)))
        
        # Numerical gradient approximation
        epsilon = 1e-6
        grad = np.zeros((1, len(state)))
        
        f0 = self.evaluate(state)[0]
        
        for i in range(min(4, len(state))):  # Only compute for position variables
            state_plus = state.copy()
            state_plus[i] += epsilon
            f_plus = self.evaluate(state_plus)[0]
            grad[0, i] = (f_plus - f0) / epsilon
        
        return grad
    
    def _calculate_box_distance(self, bounds_a: Tuple[float, float, float, float],
                               bounds_b: Tuple[float, float, float, float]) -> float:
        """
        Calculate minimum distance between two axis-aligned bounding boxes.
        
        Args:
            bounds_a: First box bounds (x1, y1, x2, y2)
            bounds_b: Second box bounds (x1, y1, x2, y2)
            
        Returns:
            Minimum distance between boxes (0 if overlapping)
        """
        ax1, ay1, ax2, ay2 = bounds_a
        bx1, by1, bx2, by2 = bounds_b
        
        # Calculate separation in each dimension
        dx = max(0, max(ax1 - bx2, bx1 - ax2))
        dy = max(0, max(ay1 - by2, by1 - ay2))
        
        # Return Euclidean distance
        return np.sqrt(dx**2 + dy**2)
    
    def update_bounds(self, object_a_bounds: Optional[Tuple[float, float, float, float]] = None,
                     object_b_bounds: Optional[Tuple[float, float, float, float]] = None):
        """
        Update object bounds.
        
        Args:
            object_a_bounds: New bounds for object A
            object_b_bounds: New bounds for object B
        """
        if object_a_bounds is not None:
            self.object_a_bounds = object_a_bounds
        if object_b_bounds is not None:
            self.object_b_bounds = object_b_bounds