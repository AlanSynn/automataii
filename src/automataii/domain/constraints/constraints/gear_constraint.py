"""
Gear Meshing Constraint Implementation

Implements constraints for gear train design and meshing requirements.
"""

import numpy as np
from typing import Optional, Tuple
from ..base import BaseConstraint, ConstraintType


class GearMeshingConstraint(BaseConstraint):
    """
    Constraint for gear meshing requirements.
    
    Ensures that two gears mesh properly by enforcing:
    1. Correct center distance: distance = r1 + r2
    2. Proper gear ratio relationships
    3. Angular velocity relationships
    """
    
    def __init__(self, name: str, gear_a_id: str, gear_b_id: str, 
                 target_center_distance: float, gear_ratio: Optional[float] = None):
        """
        Initialize gear meshing constraint.
        
        Args:
            name: Constraint name
            gear_a_id: ID of first gear
            gear_b_id: ID of second gear
            target_center_distance: Required center distance
            gear_ratio: Required gear ratio (r_b / r_a), None for automatic
        """
        super().__init__(name, ConstraintType.EQUALITY)
        
        self.gear_a_id = gear_a_id
        self.gear_b_id = gear_b_id
        self.target_center_distance = target_center_distance
        self.gear_ratio = gear_ratio
        
        # Tolerances
        self.distance_tolerance = 0.1  # mm
        self.ratio_tolerance = 0.01
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate gear meshing constraint.
        
        State vector format: [r1, r2, x1, y1, x2, y2, ...]
        where r1, r2 are radii and (x1,y1), (x2,y2) are center positions
        
        Args:
            state: Current state vector
            
        Returns:
            Constraint violation values
        """
        if len(state) < 6:
            return np.array([1000.0])  # Large violation for invalid state
        
        # Extract parameters
        r1, r2, x1, y1, x2, y2 = state[:6]
        
        # Calculate current center distance
        current_distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Main meshing constraint: r1 + r2 = center_distance
        distance_error = current_distance - (r1 + r2)
        
        errors = [distance_error]
        
        # Add gear ratio constraint if specified
        if self.gear_ratio is not None and r1 > 0:
            current_ratio = r2 / r1
            ratio_error = current_ratio - self.gear_ratio
            errors.append(ratio_error)
        
        # Add center distance constraint
        center_distance_error = current_distance - self.target_center_distance
        errors.append(center_distance_error)
        
        return np.array(errors)
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of gear meshing constraint.
        
        Args:
            state: Current state vector
            
        Returns:
            Gradient matrix
        """
        if len(state) < 6:
            return np.zeros((1, len(state)))
        
        r1, r2, x1, y1, x2, y2 = state[:6]
        
        # Calculate current center distance
        dx = x2 - x1
        dy = y2 - y1
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance < 1e-12:
            # Avoid division by zero
            return np.zeros((3, len(state)))
        
        # Gradient components
        grad = np.zeros((3, len(state)))
        
        # Distance constraint gradient: d/d_state (distance - (r1 + r2))
        grad[0, 0] = -1.0                    # d/dr1
        grad[0, 1] = -1.0                    # d/dr2
        grad[0, 2] = -dx / distance          # d/dx1
        grad[0, 3] = -dy / distance          # d/dy1
        grad[0, 4] = dx / distance           # d/dx2
        grad[0, 5] = dy / distance           # d/dy2
        
        # Gear ratio constraint gradient (if applicable)
        if self.gear_ratio is not None and r1 > 0:
            grad[1, 0] = -r2 / (r1**2)       # d/dr1
            grad[1, 1] = 1.0 / r1            # d/dr2
            # Position derivatives are 0 for ratio constraint
        
        # Center distance constraint gradient: d/d_state (distance - target)
        grad[2, 0] = 0.0                     # d/dr1
        grad[2, 1] = 0.0                     # d/dr2
        grad[2, 2] = -dx / distance          # d/dx1
        grad[2, 3] = -dy / distance          # d/dy1
        grad[2, 4] = dx / distance           # d/dx2
        grad[2, 5] = dy / distance           # d/dy2
        
        return grad
    
    def is_satisfied(self, state: np.ndarray) -> bool:
        """
        Check if constraint is satisfied within tolerance.
        
        Args:
            state: Current state vector
            
        Returns:
            True if constraint is satisfied
        """
        violations = self.evaluate(state)
        
        # Check distance constraint
        if abs(violations[0]) > self.distance_tolerance:
            return False
        
        # Check gear ratio constraint if applicable
        if len(violations) > 1 and self.gear_ratio is not None:
            if abs(violations[1]) > self.ratio_tolerance:
                return False
        
        # Check center distance constraint
        if len(violations) > 2:
            if abs(violations[2]) > self.distance_tolerance:
                return False
        
        return True
    
    def update_target_distance(self, new_distance: float):
        """Update target center distance."""
        self.target_center_distance = new_distance
    
    def update_gear_ratio(self, new_ratio: Optional[float]):
        """Update required gear ratio."""
        self.gear_ratio = new_ratio