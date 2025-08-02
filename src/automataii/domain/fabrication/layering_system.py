"""
CSP-based Layering System

Implements collision-free layering using Constraint Satisfaction Problem (CSP) solver
as specified in PAPER_IMPL.md Section 6.2.

This system automatically assigns mechanisms and components to discrete layers
to avoid collisions during fabrication and operation.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
import numpy as np

try:
    from constraint import Problem, BacktrackingSolver, RecursiveBacktrackingSolver
    CSP_AVAILABLE = True
except ImportError:
    CSP_AVAILABLE = False
    logging.warning("python-constraint not available. CSP layering will be disabled.")

logger = logging.getLogger(__name__)


class LayerType(Enum):
    """Types of layers in the fabrication stack."""
    BACKGROUND = 0      # Background image/character parts
    MECHANISM_1 = 1     # First mechanism layer
    MECHANISM_2 = 2     # Second mechanism layer  
    MECHANISM_3 = 3     # Third mechanism layer
    CONNECTION = 4      # Gear connections and pins
    SUPPORT = 5         # Support structures
    ASSEMBLY = 6        # Assembly hardware


@dataclass
class ComponentBounds:
    """Bounding box for a component in 2D space."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    
    def overlaps_with(self, other: 'ComponentBounds', margin: float = 2.0) -> bool:
        """Check if this bounds overlaps with another (with safety margin)."""
        return not (
            self.x_max + margin <= other.x_min or
            other.x_max + margin <= self.x_min or
            self.y_max + margin <= other.y_min or
            other.y_max + margin <= self.y_min
        )
    
    def area(self) -> float:
        """Calculate area of the bounding box."""
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)
    
    def center(self) -> Tuple[float, float]:
        """Get center point of the bounds."""
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2
        )


@dataclass
class LayerAssignment:
    """Assignment of a component to a specific layer."""
    component_id: str
    layer: LayerType
    z_order: int
    bounds: ComponentBounds
    component_type: str
    priority: int = 1
    
    def get_z_index(self) -> int:
        """Get the final z-index for rendering."""
        # Base z-index from layer type, plus fine ordering within layer
        base_z = {
            LayerType.BACKGROUND: 0,
            LayerType.MECHANISM_1: 100,
            LayerType.MECHANISM_2: 200,
            LayerType.MECHANISM_3: 300,
            LayerType.CONNECTION: 400,
            LayerType.SUPPORT: 500,
            LayerType.ASSEMBLY: 600,
        }
        return base_z[self.layer] + self.z_order


class CSPLayeringSystem:
    """
    CSP-based collision-free layering system.
    
    Implements the layering algorithm from PAPER_IMPL.md Section 6.2:
    - Variables: layer_index for each component
    - Constraints: layer(A) ≠ layer(B) if components A and B collide
    - Additional: layer(C) < layer(A) OR layer(C) > layer(B) if C connects A and B
    """
    
    def __init__(self, max_layers: int = 6, solver_type: str = "backtrack"):
        """
        Initialize CSP layering system.
        
        Args:
            max_layers: Maximum number of layers available
            solver_type: CSP solver type ("backtrack" or "recursive")
        """
        self.max_layers = max_layers
        self.solver_type = solver_type
        self.logger = logging.getLogger(__name__)
        
        # Component data
        self.components: Dict[str, Dict[str, Any]] = {}
        self.collision_pairs: Set[Tuple[str, str]] = set()
        self.connection_constraints: List[Tuple[str, str, str]] = []  # (connector, comp_a, comp_b)
        
        # Current layer assignments
        self.layer_assignments: Dict[str, LayerAssignment] = {}
        
        # Statistics
        self.solve_time = 0.0
        self.total_constraints = 0
        self.successful_solves = 0
        self.total_solves = 0
        
        if not CSP_AVAILABLE:
            self.logger.error("python-constraint not available. CSP layering is disabled.")
    
    def add_component(self, component_id: str, bounds: ComponentBounds, 
                     component_type: str, priority: int = 1, **metadata):
        """
        Add a component to the layering system.
        
        Args:
            component_id: Unique identifier for the component
            bounds: 2D bounding box of the component
            component_type: Type of component (mechanism, gear, pin, etc.)
            priority: Priority for layer assignment (higher = prefer lower layers)
            **metadata: Additional component metadata
        """
        self.components[component_id] = {
            'bounds': bounds,
            'type': component_type,
            'priority': priority,
            **metadata
        }
        
        self.logger.debug(f"Added component {component_id} (type: {component_type})")
        
        # Update collision detection
        self._detect_collisions(component_id)
    
    def remove_component(self, component_id: str):
        """Remove a component from the system."""
        if component_id in self.components:
            del self.components[component_id]
            
            # Remove from collision pairs
            self.collision_pairs = {
                pair for pair in self.collision_pairs 
                if component_id not in pair
            }
            
            # Remove from connection constraints
            self.connection_constraints = [
                constraint for constraint in self.connection_constraints
                if component_id not in constraint
            ]
            
            # Remove layer assignment
            if component_id in self.layer_assignments:
                del self.layer_assignments[component_id]
            
            self.logger.debug(f"Removed component {component_id}")
    
    def add_connection_constraint(self, connector_id: str, component_a: str, component_b: str):
        """
        Add a connection constraint between components.
        
        This enforces that the connector (pin, gear mesh, etc.) must be on a layer
        that doesn't interfere with the connected components.
        
        Args:
            connector_id: ID of the connecting component (pin, gear mesh)
            component_a: First connected component
            component_b: Second connected component
        """
        if (connector_id in self.components and 
            component_a in self.components and 
            component_b in self.components):
            
            constraint = (connector_id, component_a, component_b)
            if constraint not in self.connection_constraints:
                self.connection_constraints.append(constraint)
                self.logger.debug(f"Added connection constraint: {constraint}")
    
    def _detect_collisions(self, new_component_id: str):
        """Detect collisions between new component and existing components."""
        new_bounds = self.components[new_component_id]['bounds']
        
        for other_id, other_data in self.components.items():
            if other_id == new_component_id:
                continue
            
            other_bounds = other_data['bounds']
            
            if new_bounds.overlaps_with(other_bounds):
                # Add collision pair (sorted for consistency)
                pair = tuple(sorted([new_component_id, other_id]))
                self.collision_pairs.add(pair)
                self.logger.debug(f"Detected collision: {pair}")
    
    def solve_layer_assignment(self) -> bool:
        """
        Solve the CSP problem to assign layers to all components.
        
        Returns:
            True if a valid solution was found
            
        Raises:
            RuntimeError: If CSP solver is not available
        """
        if not CSP_AVAILABLE:
            raise RuntimeError("python-constraint library not available")
        
        self.total_solves += 1
        
        if not self.components:
            self.logger.warning("No components to assign layers")
            return True
        
        self.logger.info(f"Solving layer assignment for {len(self.components)} components")
        
        import time
        start_time = time.time()
        
        # Create CSP problem
        problem = Problem()
        
        # Choose solver
        if self.solver_type == "recursive":
            solver = RecursiveBacktrackingSolver()
        else:
            solver = BacktrackingSolver()
        
        problem.setSolver(solver)
        
        # Add variables: each component can be assigned to any layer
        available_layers = list(range(self.max_layers))
        for component_id in self.components:
            problem.addVariable(component_id, available_layers)
        
        # Add collision constraints: colliding components must be on different layers
        for comp_a, comp_b in self.collision_pairs:
            problem.addConstraint(
                lambda layer_a, layer_b: layer_a != layer_b,
                (comp_a, comp_b)
            )
        
        # Add connection constraints
        for connector_id, comp_a, comp_b in self.connection_constraints:
            # Connector must be on a layer that doesn't interfere
            # Either: layer(connector) < min(layer(A), layer(B))
            # Or: layer(connector) > max(layer(A), layer(B))
            def connection_constraint(layer_conn, layer_a, layer_b):
                min_layer = min(layer_a, layer_b)
                max_layer = max(layer_a, layer_b)
                return layer_conn < min_layer or layer_conn > max_layer
            
            problem.addConstraint(connection_constraint, (connector_id, comp_a, comp_b))
        
        self.total_constraints = len(self.collision_pairs) + len(self.connection_constraints)
        
        # Add priority-based preferences (soft constraints)
        # Higher priority components prefer lower layers
        sorted_components = sorted(
            self.components.items(),
            key=lambda x: (-x[1]['priority'], x[0])  # Higher priority first, then alphabetical
        )
        
        # Try to solve
        try:
            solution = problem.getSolution()
            
            if solution:
                self._apply_solution(solution)
                self.successful_solves += 1
                
                solve_time = time.time() - start_time
                self.solve_time = solve_time
                
                self.logger.info(f"Layer assignment solved in {solve_time:.3f}s")
                self.logger.info(f"Constraints: {self.total_constraints}, "
                               f"Success rate: {self.successful_solves}/{self.total_solves}")
                
                return True
            else:
                self.logger.error("No valid layer assignment found")
                return False
                
        except Exception as e:
            self.logger.error(f"CSP solver failed: {e}")
            return False
    
    def _apply_solution(self, solution: Dict[str, int]):
        """Apply the CSP solution to create layer assignments."""
        self.layer_assignments.clear()
        
        # Group components by assigned layer
        layer_groups = {}
        for component_id, layer_index in solution.items():
            if layer_index not in layer_groups:
                layer_groups[layer_index] = []
            layer_groups[layer_index].append(component_id)
        
        # Create layer assignments with proper z-ordering within each layer
        for layer_index, component_ids in layer_groups.items():
            # Sort components within layer by priority and size
            sorted_components = sorted(
                component_ids,
                key=lambda cid: (
                    -self.components[cid]['priority'],
                    -self.components[cid]['bounds'].area(),
                    cid
                )
            )
            
            # Map to LayerType
            layer_type = self._index_to_layer_type(layer_index)
            
            for z_order, component_id in enumerate(sorted_components):
                component_data = self.components[component_id]
                
                assignment = LayerAssignment(
                    component_id=component_id,
                    layer=layer_type,
                    z_order=z_order,
                    bounds=component_data['bounds'],
                    component_type=component_data['type'],
                    priority=component_data['priority']
                )
                
                self.layer_assignments[component_id] = assignment
                
                self.logger.debug(f"Assigned {component_id} to {layer_type.name} "
                                f"(z_order: {z_order}, z_index: {assignment.get_z_index()})")
    
    def _index_to_layer_type(self, layer_index: int) -> LayerType:
        """Convert layer index to LayerType enum."""
        layer_map = {
            0: LayerType.BACKGROUND,
            1: LayerType.MECHANISM_1,
            2: LayerType.MECHANISM_2,
            3: LayerType.MECHANISM_3,
            4: LayerType.CONNECTION,
            5: LayerType.SUPPORT,
        }
        return layer_map.get(layer_index, LayerType.ASSEMBLY)
    
    def get_layer_assignment(self, component_id: str) -> Optional[LayerAssignment]:
        """Get layer assignment for a component."""
        return self.layer_assignments.get(component_id)
    
    def get_z_index(self, component_id: str) -> int:
        """Get z-index for a component (for UI rendering)."""
        assignment = self.get_layer_assignment(component_id)
        if assignment:
            return assignment.get_z_index()
        else:
            # Fallback to default z-index
            from automataii.config.z_indices import Z_MECHANISM_PIVOT
            return Z_MECHANISM_PIVOT
    
    def get_components_in_layer(self, layer: LayerType) -> List[str]:
        """Get all components assigned to a specific layer."""
        return [
            comp_id for comp_id, assignment in self.layer_assignments.items()
            if assignment.layer == layer
        ]
    
    def get_layer_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current layer assignment."""
        if not self.layer_assignments:
            return {}
        
        layer_counts = {}
        for assignment in self.layer_assignments.values():
            layer_name = assignment.layer.name
            layer_counts[layer_name] = layer_counts.get(layer_name, 0) + 1
        
        return {
            'total_components': len(self.layer_assignments),
            'layer_counts': layer_counts,
            'total_collision_pairs': len(self.collision_pairs),
            'connection_constraints': len(self.connection_constraints),
            'solve_time': self.solve_time,
            'success_rate': self.successful_solves / max(1, self.total_solves),
        }
    
    def visualize_layer_assignment(self) -> str:
        """Generate a text visualization of the layer assignment."""
        if not self.layer_assignments:
            return "No layer assignments available"
        
        lines = ["Layer Assignment:"]
        lines.append("=" * 50)
        
        # Group by layer
        by_layer = {}
        for assignment in self.layer_assignments.values():
            layer_name = assignment.layer.name
            if layer_name not in by_layer:
                by_layer[layer_name] = []
            by_layer[layer_name].append(assignment)
        
        # Sort layers by z-index
        for layer_name in sorted(by_layer.keys()):
            assignments = sorted(by_layer[layer_name], key=lambda a: a.z_order)
            lines.append(f"\n{layer_name}:")
            
            for assignment in assignments:
                bounds = assignment.bounds
                lines.append(f"  {assignment.component_id} "
                           f"(type: {assignment.component_type}, "
                           f"z: {assignment.get_z_index()}, "
                           f"bounds: [{bounds.x_min:.1f}, {bounds.y_min:.1f}, "
                           f"{bounds.x_max:.1f}, {bounds.y_max:.1f}])")
        
        # Add collision info
        if self.collision_pairs:
            lines.append(f"\nCollision Pairs ({len(self.collision_pairs)}):")
            for comp_a, comp_b in sorted(self.collision_pairs):
                layer_a = self.layer_assignments[comp_a].layer.name
                layer_b = self.layer_assignments[comp_b].layer.name
                lines.append(f"  {comp_a} ({layer_a}) <-> {comp_b} ({layer_b})")
        
        return "\n".join(lines)
    
    def clear(self):
        """Clear all components and assignments."""
        self.components.clear()
        self.collision_pairs.clear()
        self.connection_constraints.clear()
        self.layer_assignments.clear()
        self.logger.info("Cleared layering system")
    
    def validate_solution(self) -> Tuple[bool, List[str]]:
        """
        Validate the current layer assignment.
        
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        # Check collision constraints
        for comp_a, comp_b in self.collision_pairs:
            if comp_a in self.layer_assignments and comp_b in self.layer_assignments:
                layer_a = self.layer_assignments[comp_a].layer
                layer_b = self.layer_assignments[comp_b].layer
                
                if layer_a == layer_b:
                    violations.append(f"Collision: {comp_a} and {comp_b} on same layer {layer_a.name}")
        
        # Check connection constraints
        for connector_id, comp_a, comp_b in self.connection_constraints:
            if all(comp in self.layer_assignments for comp in [connector_id, comp_a, comp_b]):
                layer_conn = self.layer_assignments[connector_id].layer.value
                layer_a = self.layer_assignments[comp_a].layer.value
                layer_b = self.layer_assignments[comp_b].layer.value
                
                min_layer = min(layer_a, layer_b)
                max_layer = max(layer_a, layer_b)
                
                if not (layer_conn < min_layer or layer_conn > max_layer):
                    violations.append(f"Connection violation: {connector_id} between {comp_a} and {comp_b}")
        
        is_valid = len(violations) == 0
        return is_valid, violations


def create_bounds_from_mechanism_data(mechanism_data: Dict[str, Any]) -> ComponentBounds:
    """
    Create ComponentBounds from mechanism data.
    
    Args:
        mechanism_data: Dictionary with mechanism information
        
    Returns:
        ComponentBounds for the mechanism
    """
    # Extract bounds from different possible formats
    if 'bounds' in mechanism_data:
        bounds_data = mechanism_data['bounds']
        if isinstance(bounds_data, dict):
            return ComponentBounds(
                x_min=bounds_data.get('x', 0),
                y_min=bounds_data.get('y', 0),
                x_max=bounds_data.get('x', 0) + bounds_data.get('width', 100),
                y_max=bounds_data.get('y', 0) + bounds_data.get('height', 100)
            )
    
    # Extract from real_world_params if available
    if 'real_world_params' in mechanism_data:
        params = mechanism_data['real_world_params']
        
        # Estimate bounds based on mechanism type
        mech_type = mechanism_data.get('type', 'unknown')
        
        if mech_type == '4_bar_linkage':
            # Use link lengths to estimate bounds
            l1 = params.get('l1_mm', 100)
            l2 = params.get('l2_mm', 50)
            l3 = params.get('l3_mm', 80)
            l4 = params.get('l4_mm', 60)
            
            # Rough estimate of mechanism workspace
            max_reach = l1 + max(l2, l3, l4)
            return ComponentBounds(-max_reach/2, -max_reach/2, max_reach/2, max_reach/2)
        
        elif mech_type == 'cam':
            base_radius = params.get('base_radius_mm', 30)
            rise = params.get('rise_mm', 15)
            
            size = (base_radius + rise) * 2
            return ComponentBounds(-size/2, -size/2, size/2, size/2)
        
        elif mech_type in ['gear', 'belt']:
            r1 = params.get('r1_mm', 30)
            r2 = params.get('r2_mm', 30)
            
            size = max(r1, r2) * 3  # Account for both gears
            return ComponentBounds(-size/2, -size/2, size/2, size/2)
    
    # Default bounds
    return ComponentBounds(-50, -50, 50, 50)