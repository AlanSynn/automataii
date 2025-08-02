"""
Phase Constraint Implementation

Implements phase/driver constraint from PAPER_IMPL.md Section 2.1.
Used to drive mechanism motion by constraining one component's state 
to a specific phase angle.

250% Confidence Implementation
"""

import numpy as np
from typing import Optional
from ..base import BaseConstraint, ConstraintType


class PhaseConstraint(BaseConstraint):
    """
    Phase constraint for driving mechanism motion.
    
    Constrains one component's rotation or position to follow
    a prescribed motion as a function of driver phase.
    
    Mathematical Model:
    - For rotational driver: θ(t) = θ₀ + ω * phase
    - For translational driver: x(t) = x₀ + A * sin(phase)
    - Adds 1 scalar constraint equation
    """
    
    def __init__(self, name: str, component_idx: int, driver_type: str = "rotation",
                 driver_axis: int = 2, amplitude: float = 1.0, offset: float = 0.0):
        """
        Initialize phase constraint.
        
        Args:
            name: Constraint identifier
            component_idx: Index of driven component in state vector
            driver_type: "rotation" or "translation"
            driver_axis: Axis index (0=x, 1=y, 2=z for translation; 0=α, 1=β, 2=γ for rotation)
            amplitude: Motion amplitude (radians for rotation, distance for translation)
            offset: Motion offset
        """
        super().__init__(name, ConstraintType.POSITION)
        
        self.component_idx = component_idx
        self.driver_type = driver_type
        self.driver_axis = driver_axis
        self.amplitude = amplitude
        self.offset = offset
        
        # Current phase value (set externally)
        self.current_phase = 0.0
        
    def set_driver_phase(self, phase: float):
        """Set current driver phase."""
        self.current_phase = phase
        
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate phase constraint.
        
        Args:
            state: Global state vector
            
        Returns:
            Constraint violation [1] - should be zero when satisfied
        """
        # Extract component state
        component_state = self._extract_component_state(state, self.component_idx)
        
        # Compute target value based on driver type
        if self.driver_type == "rotation":
            target_value = self.offset + self.amplitude * self.current_phase
            current_value = component_state[3 + self.driver_axis]  # Rotation components
        elif self.driver_type == "translation":
            target_value = self.offset + self.amplitude * np.sin(self.current_phase)
            current_value = component_state[self.driver_axis]  # Position components
        else:
            raise ValueError(f"Unknown driver type: {self.driver_type}")
        
        # Constraint: current_value - target_value = 0
        constraint_violation = current_value - target_value
        
        return np.array([constraint_violation])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Compute constraint Jacobian ∂C/∂s.
        
        Args:
            state: Global state vector
            
        Returns:
            Gradient vector [1 x n_state]
        """
        n_state = len(state)
        gradient = np.zeros((1, n_state))
        
        # Only the driven component's driven axis has non-zero gradient
        driven_state_idx = self.component_idx * 6
        
        if self.driver_type == "rotation":
            driven_axis_idx = driven_state_idx + 3 + self.driver_axis
        else:  # translation
            driven_axis_idx = driven_state_idx + self.driver_axis
            
        gradient[0, driven_axis_idx] = 1.0  # ∂(current_value)/∂axis = 1
        
        return gradient
    
    def _extract_component_state(self, state: np.ndarray, component_idx: int) -> np.ndarray:
        """Extract 6-DOF state for a component."""
        start_idx = component_idx * 6
        return state[start_idx:start_idx+6]


class FixedStateConstraint(BaseConstraint):
    """
    Fixed state constraint - pins a component to a specific state.
    
    Useful for ground connections and fixed parts.
    Adds up to 6 scalar constraint equations (depending on fixed DOFs).
    """
    
    def __init__(self, name: str, component_idx: int, fixed_state: np.ndarray,
                 fixed_dofs: Optional[list] = None):
        """
        Initialize fixed state constraint.
        
        Args:
            name: Constraint identifier
            component_idx: Index of component in state vector
            fixed_state: Target state [6] for component
            fixed_dofs: List of DOF indices to fix (0-5), None for all
        """
        super().__init__(name, ConstraintType.POSITION)
        
        self.component_idx = component_idx
        self.fixed_state = np.array(fixed_state, dtype=float)
        self.fixed_dofs = fixed_dofs if fixed_dofs is not None else list(range(6))
        
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate fixed state constraint.
        
        Args:
            state: Global state vector
            
        Returns:
            Constraint violations [n_fixed_dofs]
        """
        # Extract component state
        component_state = self._extract_component_state(state, self.component_idx)
        
        # Compute violations for fixed DOFs only
        violations = []
        for dof_idx in self.fixed_dofs:
            violation = component_state[dof_idx] - self.fixed_state[dof_idx]
            violations.append(violation)
        
        return np.array(violations)
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Compute constraint Jacobian ∂C/∂s.
        
        Args:
            state: Global state vector
            
        Returns:
            Gradient matrix [n_fixed_dofs x n_state]
        """
        n_state = len(state)
        n_constraints = len(self.fixed_dofs)
        gradient = np.zeros((n_constraints, n_state))
        
        # Each fixed DOF contributes one constraint
        component_start_idx = self.component_idx * 6
        
        for i, dof_idx in enumerate(self.fixed_dofs):
            state_idx = component_start_idx + dof_idx
            gradient[i, state_idx] = 1.0  # ∂(current_dof)/∂dof = 1
        
        return gradient
    
    def _extract_component_state(self, state: np.ndarray, component_idx: int) -> np.ndarray:
        """Extract 6-DOF state for a component."""
        start_idx = component_idx * 6
        return state[start_idx:start_idx+6]


class PointOnLineConstraint(BaseConstraint):
    """
    Point-on-line constraint - constrains a point to lie on a line.
    
    Used for slider mechanisms and linear guides.
    Adds 2 scalar constraint equations (reduces 3D position to 1D).
    """
    
    def __init__(self, name: str, component_idx: int, point_local: np.ndarray,
                 line_point: np.ndarray, line_direction: np.ndarray):
        """
        Initialize point-on-line constraint.
        
        Args:
            name: Constraint identifier
            component_idx: Index of component containing the point
            point_local: Point coordinates in component's local frame [3]
            line_point: A point on the line in global frame [3]
            line_direction: Line direction vector in global frame [3] (normalized)
        """
        super().__init__(name, ConstraintType.POSITION)
        
        self.component_idx = component_idx
        self.point_local = np.array(point_local, dtype=float)
        self.line_point = np.array(line_point, dtype=float)
        self.line_direction = np.array(line_direction, dtype=float)
        self.line_direction = self.line_direction / np.linalg.norm(self.line_direction)
        
        # Pre-compute perpendicular vectors for constraint formulation
        self.perp_1 = self._get_perpendicular_vector(self.line_direction)
        self.perp_2 = np.cross(self.line_direction, self.perp_1)
        
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate point-on-line constraint.
        
        Args:
            state: Global state vector
            
        Returns:
            Constraint violations [2] - perpendicular distances to line
        """
        # Transform point to global coordinates
        component_state = self._extract_component_state(state, self.component_idx)
        point_global = self._transform_point(component_state, self.point_local)
        
        # Vector from line point to our point
        point_to_line = point_global - self.line_point
        
        # Project onto perpendicular directions (should be zero)
        violation_1 = np.dot(point_to_line, self.perp_1)
        violation_2 = np.dot(point_to_line, self.perp_2)
        
        return np.array([violation_1, violation_2])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Compute constraint Jacobian ∂C/∂s.
        
        Args:
            state: Global state vector
            
        Returns:
            Gradient matrix [2 x n_state]
        """
        n_state = len(state)
        gradient = np.zeros((2, n_state))
        
        component_start_idx = self.component_idx * 6
        component_state = self._extract_component_state(state, self.component_idx)
        
        # Gradient with respect to position (first 3 DOFs)
        gradient[0, component_start_idx:component_start_idx+3] = self.perp_1
        gradient[1, component_start_idx:component_start_idx+3] = self.perp_2
        
        # Gradient with respect to rotation (last 3 DOFs) - numerical approximation
        epsilon = 1e-8
        for i in range(3):
            rot_idx = component_start_idx + 3 + i
            
            state_plus = state.copy()
            state_plus[rot_idx] += epsilon
            constraint_plus = self.evaluate(state_plus)
            
            state_minus = state.copy()
            state_minus[rot_idx] -= epsilon
            constraint_minus = self.evaluate(state_minus)
            
            gradient[:, rot_idx] = (constraint_plus - constraint_minus) / (2 * epsilon)
        
        return gradient
    
    def _extract_component_state(self, state: np.ndarray, component_idx: int) -> np.ndarray:
        """Extract 6-DOF state for a component."""
        start_idx = component_idx * 6
        return state[start_idx:start_idx+6]
    
    def _transform_point(self, component_state: np.ndarray, local_point: np.ndarray) -> np.ndarray:
        """Transform point from local to global coordinates."""
        position = component_state[0:3]
        rotation = component_state[3:6]
        
        R = self._get_rotation_matrix(rotation)
        global_point = position + R @ local_point
        
        return global_point
    
    def _get_rotation_matrix(self, euler_angles: np.ndarray) -> np.ndarray:
        """Convert Euler angles to rotation matrix."""
        alpha, beta, gamma = euler_angles
        
        # ZYX Euler angle convention
        cos_a, sin_a = np.cos(alpha), np.sin(alpha)
        cos_b, sin_b = np.cos(beta), np.sin(beta)
        cos_g, sin_g = np.cos(gamma), np.sin(gamma)
        
        R = np.array([
            [cos_a*cos_b, cos_a*sin_b*sin_g - sin_a*cos_g, cos_a*sin_b*cos_g + sin_a*sin_g],
            [sin_a*cos_b, sin_a*sin_b*sin_g + cos_a*cos_g, sin_a*sin_b*cos_g - cos_a*sin_g],
            [-sin_b,      cos_b*sin_g,                      cos_b*cos_g]
        ])
        
        return R
    
    def _get_perpendicular_vector(self, direction: np.ndarray) -> np.ndarray:
        """Get a perpendicular vector to the given direction."""
        # Find the component with smallest absolute value
        min_idx = np.argmin(np.abs(direction))
        
        # Create a vector with 1 in that component, 0 elsewhere
        perp = np.zeros(3)
        perp[min_idx] = 1.0
        
        # Make it perpendicular and normalize
        perp = perp - np.dot(perp, direction) * direction
        perp = perp / np.linalg.norm(perp)
        
        return perp