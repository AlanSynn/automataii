"""
Layer Constraint Implementation

Implements layering constraints for the CSP-based layering system.
"""

import numpy as np
from typing import List, Dict, Any

from ..base import BaseConstraint, ConstraintType


class LayerConstraint(BaseConstraint):
    """
    Layer separation constraint.
    
    Ensures that two components are assigned to different layers
    if they would otherwise collide.
    
    Constraint: layer(A) ≠ layer(B) for colliding components A and B
    """
    
    def __init__(self, name: str, component_a: str, component_b: str, weight: float = 1.0):
        """
        Initialize layer constraint.
        
        Args:
            name: Constraint name
            component_a: First component ID
            component_b: Second component ID
            weight: Constraint weight
        """
        super().__init__(name, ConstraintType.LAYER, weight)
        self.component_a = component_a
        self.component_b = component_b
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate layer constraint violation.
        
        Args:
            state: Layer assignments as [layer_comp1, layer_comp2, ...]
                  Component order must be consistent with constraint setup
            
        Returns:
            Constraint violation (0 if satisfied, 1 if violated)
        """
        # This is a discrete constraint that should be handled by CSP solver
        # For continuous optimization, we can define a penalty function
        
        # Extract layer assignments (simplified for demo)
        # In practice, this would need proper component ID to index mapping
        if len(state) < 2:
            return np.array([1.0])  # Violation if insufficient state
        
        layer_a = int(round(state[0]))
        layer_b = int(round(state[1]))
        
        # Violation if components are on the same layer
        violation = 1.0 if layer_a == layer_b else 0.0
        
        return np.array([violation])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate gradient of layer constraint.
        
        Since this is a discrete constraint, the gradient is not well-defined.
        For continuous relaxation, we can use a smooth approximation.
        
        Args:
            state: Layer assignments
            
        Returns:
            Gradient matrix (1 x len(state))
        """
        if len(state) < 2:
            return np.zeros((1, len(state))) if len(state) > 0 else np.zeros((1, 2))
        
        # For discrete constraints, gradient is typically zero or undefined
        # We could use a smooth approximation like sigmoid functions
        gradient = np.zeros((1, len(state)))
        
        layer_a = state[0]
        layer_b = state[1]
        
        # Smooth approximation: penalty increases as layers get closer
        diff = layer_a - layer_b
        
        # Sigmoid-based smooth constraint: penalty when |diff| < 1
        # f(diff) = 1 / (1 + exp(k * (|diff| - threshold)))
        # where k controls steepness and threshold is the minimum separation
        
        k = 10.0  # Steepness parameter
        threshold = 1.0  # Minimum layer separation
        
        abs_diff = abs(diff)
        sigmoid = 1.0 / (1.0 + np.exp(k * (abs_diff - threshold)))
        
        # Gradient with respect to layer_a and layer_b
        if abs(diff) > 1e-9:
            sign_diff = np.sign(diff)
            
            # d(sigmoid)/d(layer_a) = d(sigmoid)/d(abs_diff) * d(abs_diff)/d(layer_a)
            dsigmoid_d_abs_diff = -k * sigmoid * (1 - sigmoid)
            
            gradient[0, 0] = dsigmoid_d_abs_diff * sign_diff  # d/d(layer_a)
            gradient[0, 1] = dsigmoid_d_abs_diff * (-sign_diff)  # d/d(layer_b)
        
        return gradient
    
    def is_equality_constraint(self) -> bool:
        """Layer constraints are inequality constraints."""
        return False
    
    def __repr__(self) -> str:
        return (f"LayerConstraint(name='{self.name}', "
                f"components=({self.component_a}, {self.component_b}), "
                f"weight={self.weight})")


class ConnectionLayerConstraint(BaseConstraint):
    """
    Connection layer constraint.
    
    Ensures that a connector component is placed on a layer that doesn't
    interfere with the components it connects.
    
    Constraint: layer(C) < min(layer(A), layer(B)) OR layer(C) > max(layer(A), layer(B))
    where C is the connector and A, B are the connected components.
    """
    
    def __init__(self, name: str, connector: str, component_a: str, component_b: str, weight: float = 1.0):
        """
        Initialize connection layer constraint.
        
        Args:
            name: Constraint name
            connector: Connector component ID (pin, gear mesh, etc.)
            component_a: First connected component ID
            component_b: Second connected component ID
            weight: Constraint weight
        """
        super().__init__(name, ConstraintType.LAYER, weight)
        self.connector = connector
        self.component_a = component_a
        self.component_b = component_b
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate connection layer constraint violation.
        
        Args:
            state: Layer assignments [layer_connector, layer_a, layer_b, ...]
            
        Returns:
            Constraint violation (0 if satisfied, positive if violated)
        """
        if len(state) < 3:
            return np.array([1.0])  # Violation if insufficient state
        
        layer_connector = state[0]
        layer_a = state[1]
        layer_b = state[2]
        
        min_layer = min(layer_a, layer_b)
        max_layer = max(layer_a, layer_b)
        
        # Constraint is satisfied if:
        # layer_connector < min_layer OR layer_connector > max_layer
        
        if layer_connector < min_layer or layer_connector > max_layer:
            return np.array([0.0])  # Satisfied
        else:
            # Violation: connector is between the connected components
            # Penalty based on how far into the forbidden zone
            if layer_connector <= (min_layer + max_layer) / 2:
                violation = min_layer - layer_connector
            else:
                violation = layer_connector - max_layer
            
            return np.array([max(0.0, violation)])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """Calculate gradient of connection layer constraint."""
        if len(state) < 3:
            return np.zeros((1, len(state))) if len(state) > 0 else np.zeros((1, 3))
        
        gradient = np.zeros((1, len(state)))
        
        layer_connector = state[0]
        layer_a = state[1]
        layer_b = state[2]
        
        min_layer = min(layer_a, layer_b)
        max_layer = max(layer_a, layer_b)
        
        # Only compute gradient if constraint is violated
        if min_layer <= layer_connector <= max_layer:
            if layer_connector <= (min_layer + max_layer) / 2:
                # Gradient pushes connector to lower layer
                gradient[0, 0] = -1.0  # d/d(layer_connector)
                
                # Which component determines min_layer?
                if layer_a < layer_b:
                    gradient[0, 1] = 1.0   # d/d(layer_a)
                else:
                    gradient[0, 2] = 1.0   # d/d(layer_b)
            else:
                # Gradient pushes connector to higher layer
                gradient[0, 0] = 1.0   # d/d(layer_connector)
                
                # Which component determines max_layer?
                if layer_a > layer_b:
                    gradient[0, 1] = -1.0  # d/d(layer_a)
                else:
                    gradient[0, 2] = -1.0  # d/d(layer_b)
        
        return gradient
    
    def is_equality_constraint(self) -> bool:
        """Connection constraints are inequality constraints."""
        return False
    
    def __repr__(self) -> str:
        return (f"ConnectionLayerConstraint(name='{self.name}', "
                f"connector={self.connector}, "
                f"components=({self.component_a}, {self.component_b}), "
                f"weight={self.weight})")


class LayerOrderConstraint(BaseConstraint):
    """
    Layer ordering constraint.
    
    Enforces a specific ordering relationship between layers.
    E.g., background must be behind mechanisms, mechanisms behind assembly.
    """
    
    def __init__(self, name: str, lower_component: str, upper_component: str, 
                 min_separation: float = 1.0, weight: float = 1.0):
        """
        Initialize layer order constraint.
        
        Args:
            name: Constraint name
            lower_component: Component that should be on a lower layer
            upper_component: Component that should be on a higher layer
            min_separation: Minimum layer separation required
            weight: Constraint weight
        """
        super().__init__(name, ConstraintType.LAYER, weight)
        self.lower_component = lower_component
        self.upper_component = upper_component
        self.min_separation = min_separation
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate layer order constraint violation.
        
        Args:
            state: Layer assignments [layer_lower, layer_upper, ...]
            
        Returns:
            Constraint violation (0 if satisfied, positive if violated)
        """
        if len(state) < 2:
            return np.array([1.0])
        
        layer_lower = state[0]
        layer_upper = state[1]
        
        # Required: layer_upper - layer_lower >= min_separation
        required_separation = layer_upper - layer_lower
        
        if required_separation >= self.min_separation:
            return np.array([0.0])  # Satisfied
        else:
            violation = self.min_separation - required_separation
            return np.array([violation])
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """Calculate gradient of layer order constraint."""
        if len(state) < 2:
            return np.zeros((1, len(state))) if len(state) > 0 else np.zeros((1, 2))
        
        gradient = np.zeros((1, len(state)))
        
        layer_lower = state[0]
        layer_upper = state[1]
        required_separation = layer_upper - layer_lower
        
        # Only non-zero gradient if constraint is violated
        if required_separation < self.min_separation:
            gradient[0, 0] = 1.0   # d/d(layer_lower) - increase violation
            gradient[0, 1] = -1.0  # d/d(layer_upper) - decrease violation
        
        return gradient
    
    def is_equality_constraint(self) -> bool:
        """Order constraints are inequality constraints."""
        return False
    
    def __repr__(self) -> str:
        return (f"LayerOrderConstraint(name='{self.name}', "
                f"order=({self.lower_component} < {self.upper_component}), "
                f"min_sep={self.min_separation}, weight={self.weight})")