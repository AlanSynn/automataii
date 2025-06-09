"""
Mechanism placement optimization algorithms.

This module implements various algorithms for optimizing the placement
of mechanism components on automata bases, considering constraints like
collision avoidance, balance, and mechanical requirements.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
import math
import random
from copy import deepcopy

from automataii.modules.automata_base.models.dimensions import Point2D
from automataii.modules.automata_base.data.mechanism_placement_dataset import (
    MechanismComponent, PlacementConstraint, BaseLayout, PlacementScenario
)


class PlacementStatus(Enum):
    """Status of component placement."""
    UNPLACED = "unplaced"
    PLACED = "placed"
    FAILED = "failed"


@dataclass
class ComponentPlacement:
    """Represents the placement of a component."""
    component_id: str
    position: Point2D
    rotation: float  # degrees
    status: PlacementStatus = PlacementStatus.UNPLACED
    score: float = 0.0


@dataclass
class PlacementSolution:
    """Complete placement solution."""
    placements: Dict[str, ComponentPlacement]
    total_score: float
    is_valid: bool
    violations: List[str]
    metrics: Dict[str, float]


class PlacementOptimizer:
    """Base class for placement optimization algorithms."""
    
    def __init__(self, scenario: PlacementScenario):
        """
        Initialize optimizer with a placement scenario.
        
        Args:
            scenario: The placement scenario to optimize
        """
        self.scenario = scenario
        self.base_layout = scenario.base_layout
        self.components = {c.id: c for c in scenario.components}
        self.constraints = scenario.constraints
        
        # Grid resolution for spatial indexing (mm)
        self.grid_resolution = 5.0
        
    def optimize(self) -> PlacementSolution:
        """
        Optimize component placement.
        
        Returns:
            PlacementSolution with optimized placements
        """
        raise NotImplementedError("Subclasses must implement optimize()")
    
    def is_valid_position(self, component: MechanismComponent, 
                         position: Point2D, rotation: float,
                         placed_components: Dict[str, ComponentPlacement]) -> Tuple[bool, List[str]]:
        """
        Check if a position is valid for a component.
        
        Args:
            component: Component to place
            position: Proposed position
            rotation: Rotation angle in degrees
            placed_components: Already placed components
            
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        # Check if within mounting zones
        if not self._is_in_mounting_zone(component, position, rotation):
            violations.append(f"Component {component.id} outside mounting zone")
        
        # Check obstacle collisions
        if self._collides_with_obstacles(component, position, rotation):
            violations.append(f"Component {component.id} collides with obstacle")
        
        # Check component collisions
        for placed_id, placement in placed_components.items():
            if self._components_collide(
                component, position, rotation,
                self.components[placed_id], placement.position, placement.rotation
            ):
                violations.append(f"Component {component.id} collides with {placed_id}")
        
        # Check constraints
        constraint_violations = self._check_constraints(
            component, position, rotation, placed_components
        )
        violations.extend(constraint_violations)
        
        return len(violations) == 0, violations
    
    def _is_in_mounting_zone(self, component: MechanismComponent,
                            position: Point2D, rotation: float) -> bool:
        """Check if component is within mounting zones."""
        # Get component bounds at position
        bounds = self._get_component_bounds(component, position, rotation)
        
        for zone in self.base_layout.mounting_zones:
            if zone["type"] == "rectangle":
                if (bounds[0] >= zone["x"] and 
                    bounds[1] >= zone["y"] and
                    bounds[2] <= zone["x"] + zone["width"] and
                    bounds[3] <= zone["y"] + zone["height"]):
                    return True
                    
            elif zone["type"] == "circle":
                # Check if all corners are within circle
                corners = [
                    (bounds[0], bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[2], bounds[3]),
                    (bounds[0], bounds[3])
                ]
                all_in = True
                for cx, cy in corners:
                    dist = math.sqrt((cx - zone["center_x"])**2 + 
                                   (cy - zone["center_y"])**2)
                    if dist > zone["radius"]:
                        all_in = False
                        break
                if all_in:
                    return True
        
        return False
    
    def _collides_with_obstacles(self, component: MechanismComponent,
                                position: Point2D, rotation: float) -> bool:
        """Check collision with obstacles."""
        for obstacle in self.base_layout.obstacles:
            if obstacle["type"] == "circle":
                # Simple distance check with clearance
                dist = math.sqrt((position.x - obstacle["center_x"])**2 + 
                               (position.y - obstacle["center_y"])**2)
                if dist < obstacle["radius"] + component.clearance_radius:
                    return True
        
        return False
    
    def _components_collide(self, comp1: MechanismComponent, pos1: Point2D, rot1: float,
                           comp2: MechanismComponent, pos2: Point2D, rot2: float) -> bool:
        """Check if two components collide."""
        # Simple circle-based collision detection
        dist = math.sqrt((pos1.x - pos2.x)**2 + (pos1.y - pos2.y)**2)
        min_dist = comp1.clearance_radius + comp2.clearance_radius
        
        return dist < min_dist
    
    def _get_component_bounds(self, component: MechanismComponent,
                             position: Point2D, rotation: float) -> Tuple[float, float, float, float]:
        """Get axis-aligned bounding box of rotated component."""
        # Calculate rotated dimensions
        angle_rad = math.radians(rotation)
        cos_a = abs(math.cos(angle_rad))
        sin_a = abs(math.sin(angle_rad))
        
        rotated_width = component.width * cos_a + component.height * sin_a
        rotated_height = component.width * sin_a + component.height * cos_a
        
        min_x = position.x - rotated_width / 2
        min_y = position.y - rotated_height / 2
        max_x = position.x + rotated_width / 2
        max_y = position.y + rotated_height / 2
        
        return (min_x, min_y, max_x, max_y)
    
    def _check_constraints(self, component: MechanismComponent, position: Point2D,
                          rotation: float, placed_components: Dict[str, ComponentPlacement]) -> List[str]:
        """Check if placement violates constraints."""
        violations = []
        
        for constraint in self.constraints:
            if component.id not in constraint.component_ids:
                continue
            
            if constraint.type == "distance":
                # Check distance constraints
                for other_id in constraint.component_ids:
                    if other_id != component.id and other_id in placed_components:
                        other_placement = placed_components[other_id]
                        dist = math.sqrt((position.x - other_placement.position.x)**2 + 
                                       (position.y - other_placement.position.y)**2)
                        
                        min_dist = constraint.parameters.get("min_distance", 0)
                        max_dist = constraint.parameters.get("max_distance", float('inf'))
                        
                        if dist < min_dist:
                            violations.append(
                                f"Distance {dist:.1f} between {component.id} and {other_id} "
                                f"less than minimum {min_dist}"
                            )
                        elif dist > max_dist:
                            violations.append(
                                f"Distance {dist:.1f} between {component.id} and {other_id} "
                                f"greater than maximum {max_dist}"
                            )
            
            elif constraint.type == "alignment":
                # Check alignment constraints
                for other_id in constraint.component_ids:
                    if other_id != component.id and other_id in placed_components:
                        other_placement = placed_components[other_id]
                        axis = constraint.parameters.get("axis", "horizontal")
                        tolerance = constraint.parameters.get("tolerance", 10.0)
                        
                        if axis == "horizontal":
                            diff = abs(position.y - other_placement.position.y)
                        else:
                            diff = abs(position.x - other_placement.position.x)
                        
                        if diff > tolerance:
                            violations.append(
                                f"{component.id} not aligned with {other_id} "
                                f"on {axis} axis (diff: {diff:.1f})"
                            )
            
            elif constraint.type == "zone":
                # Check zone constraints
                zone_type = constraint.parameters.get("zone")
                margin = constraint.parameters.get("margin", 0)
                
                if zone_type == "lower_half":
                    if position.y < self.base_layout.height / 2 - margin:
                        violations.append(
                            f"{component.id} not in lower half of base"
                        )
                elif zone_type == "upper_half":
                    if position.y > self.base_layout.height / 2 + margin:
                        violations.append(
                            f"{component.id} not in upper half of base"
                        )
        
        return violations
    
    def calculate_placement_score(self, solution: Dict[str, ComponentPlacement]) -> float:
        """
        Calculate overall score for a placement solution.
        
        Args:
            solution: Dictionary of component placements
            
        Returns:
            Total score (higher is better)
        """
        score = 0.0
        
        # Balance score (center of mass close to base center)
        com_score = self._calculate_balance_score(solution)
        score += com_score * 10.0
        
        # Compactness score (components close together)
        compact_score = self._calculate_compactness_score(solution)
        score += compact_score * 5.0
        
        # Preferred zone score
        zone_score = self._calculate_zone_score(solution)
        score += zone_score * 3.0
        
        # Constraint satisfaction bonus
        if self._all_constraints_satisfied(solution):
            score += 50.0
        
        return score
    
    def _calculate_balance_score(self, solution: Dict[str, ComponentPlacement]) -> float:
        """Calculate balance score based on center of mass."""
        if not solution:
            return 0.0
        
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        
        for comp_id, placement in solution.items():
            if placement.status != PlacementStatus.PLACED:
                continue
                
            comp = self.components[comp_id]
            # Adjust COM for rotation
            angle_rad = math.radians(placement.rotation)
            com_x = (comp.center_of_mass.x * math.cos(angle_rad) - 
                    comp.center_of_mass.y * math.sin(angle_rad))
            com_y = (comp.center_of_mass.x * math.sin(angle_rad) + 
                    comp.center_of_mass.y * math.cos(angle_rad))
            
            weighted_x += comp.weight * (placement.position.x + com_x)
            weighted_y += comp.weight * (placement.position.y + com_y)
            total_weight += comp.weight
        
        if total_weight == 0:
            return 0.0
        
        # Calculate center of mass
        com_x = weighted_x / total_weight
        com_y = weighted_y / total_weight
        
        # Calculate distance from base center
        base_center_x = self.base_layout.width / 2
        base_center_y = self.base_layout.height / 2
        
        distance = math.sqrt((com_x - base_center_x)**2 + (com_y - base_center_y)**2)
        max_distance = math.sqrt(base_center_x**2 + base_center_y**2)
        
        # Normalize score (1.0 when perfectly centered, 0.0 at corners)
        return max(0.0, 1.0 - distance / max_distance)
    
    def _calculate_compactness_score(self, solution: Dict[str, ComponentPlacement]) -> float:
        """Calculate how compact the placement is."""
        if len(solution) < 2:
            return 1.0
        
        positions = [p.position for p in solution.values() if p.status == PlacementStatus.PLACED]
        if len(positions) < 2:
            return 1.0
        
        # Calculate average distance between components
        total_dist = 0.0
        count = 0
        
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = math.sqrt((positions[i].x - positions[j].x)**2 + 
                               (positions[i].y - positions[j].y)**2)
                total_dist += dist
                count += 1
        
        if count == 0:
            return 1.0
        
        avg_dist = total_dist / count
        max_possible_dist = math.sqrt(self.base_layout.width**2 + self.base_layout.height**2)
        
        # Normalize (1.0 when very compact, 0.0 when spread out)
        return max(0.0, 1.0 - avg_dist / max_possible_dist)
    
    def _calculate_zone_score(self, solution: Dict[str, ComponentPlacement]) -> float:
        """Calculate score based on preferred zone placement."""
        if not self.base_layout.preferred_zones:
            return 0.0
        
        total_score = 0.0
        placed_count = 0
        
        for comp_id, placement in solution.items():
            if placement.status != PlacementStatus.PLACED:
                continue
            
            placed_count += 1
            comp = self.components[comp_id]
            
            # Check if in any preferred zone
            for zone in self.base_layout.preferred_zones:
                if zone["type"] == "rectangle":
                    if (placement.position.x >= zone["x"] and
                        placement.position.x <= zone["x"] + zone["width"] and
                        placement.position.y >= zone["y"] and
                        placement.position.y <= zone["y"] + zone["height"]):
                        # Weight heavy components more
                        weight_factor = comp.weight / 100.0  # Normalize by 100g
                        total_score += zone.get("weight", 1.0) * weight_factor
        
        if placed_count == 0:
            return 0.0
        
        return total_score / placed_count
    
    def _all_constraints_satisfied(self, solution: Dict[str, ComponentPlacement]) -> bool:
        """Check if all constraints are satisfied."""
        for comp_id, placement in solution.items():
            if placement.status != PlacementStatus.PLACED:
                continue
            
            violations = self._check_constraints(
                self.components[comp_id],
                placement.position,
                placement.rotation,
                {k: v for k, v in solution.items() if k != comp_id and v.status == PlacementStatus.PLACED}
            )
            
            if violations:
                return False
        
        return True


class GreedyPlacementOptimizer(PlacementOptimizer):
    """Greedy algorithm for placement optimization."""
    
    def optimize(self) -> PlacementSolution:
        """
        Optimize using greedy approach - place components one by one
        in priority order, choosing best position for each.
        """
        # Sort components by priority (higher first)
        sorted_components = sorted(
            self.scenario.components,
            key=lambda c: c.priority,
            reverse=True
        )
        
        placements = {}
        violations = []
        
        for component in sorted_components:
            best_placement = self._find_best_position(component, placements)
            
            if best_placement:
                placements[component.id] = best_placement
            else:
                # Failed to place component
                placements[component.id] = ComponentPlacement(
                    component_id=component.id,
                    position=Point2D(0, 0),
                    rotation=0,
                    status=PlacementStatus.FAILED
                )
                violations.append(f"Failed to place component {component.id}")
        
        # Calculate final score
        total_score = self.calculate_placement_score(placements)
        
        # Check if solution is valid
        is_valid = all(p.status == PlacementStatus.PLACED for p in placements.values())
        
        # Calculate metrics
        metrics = {
            "placed_count": sum(1 for p in placements.values() if p.status == PlacementStatus.PLACED),
            "failed_count": sum(1 for p in placements.values() if p.status == PlacementStatus.FAILED),
            "balance_score": self._calculate_balance_score(placements),
            "compactness_score": self._calculate_compactness_score(placements),
            "zone_score": self._calculate_zone_score(placements)
        }
        
        return PlacementSolution(
            placements=placements,
            total_score=total_score,
            is_valid=is_valid,
            violations=violations,
            metrics=metrics
        )
    
    def _find_best_position(self, component: MechanismComponent,
                           placed_components: Dict[str, ComponentPlacement]) -> Optional[ComponentPlacement]:
        """Find best position for a component."""
        best_placement = None
        best_score = -float('inf')
        
        # Generate candidate positions
        candidates = self._generate_candidate_positions(component, placed_components)
        
        for position, rotation in candidates:
            # Check if valid
            is_valid, violations = self.is_valid_position(
                component, position, rotation, placed_components
            )
            
            if is_valid:
                # Create temporary placement
                temp_placement = ComponentPlacement(
                    component_id=component.id,
                    position=position,
                    rotation=rotation,
                    status=PlacementStatus.PLACED
                )
                
                # Evaluate score
                temp_placements = placed_components.copy()
                temp_placements[component.id] = temp_placement
                score = self.calculate_placement_score(temp_placements)
                
                if score > best_score:
                    best_score = score
                    best_placement = temp_placement
                    best_placement.score = score
        
        return best_placement
    
    def _generate_candidate_positions(self, component: MechanismComponent,
                                     placed_components: Dict[str, ComponentPlacement]) -> List[Tuple[Point2D, float]]:
        """Generate candidate positions for component placement."""
        candidates = []
        
        # Grid-based sampling
        step_size = max(10, min(component.width, component.height) / 2)
        
        for zone in self.base_layout.mounting_zones:
            if zone["type"] == "rectangle":
                x_start = zone["x"] + component.width / 2
                x_end = zone["x"] + zone["width"] - component.width / 2
                y_start = zone["y"] + component.height / 2
                y_end = zone["y"] + zone["height"] - component.height / 2
                
                for x in np.arange(x_start, x_end, step_size):
                    for y in np.arange(y_start, y_end, step_size):
                        # Try different rotations if allowed
                        if component.rotation_allowed:
                            for angle in np.arange(0, 360, component.rotation_step):
                                candidates.append((Point2D(x, y), angle))
                        else:
                            candidates.append((Point2D(x, y), 0))
            
            elif zone["type"] == "circle":
                # Sample points in circle
                center_x = zone["center_x"]
                center_y = zone["center_y"]
                radius = zone["radius"] - max(component.width, component.height) / 2
                
                if radius > 0:
                    # Grid sampling within circle
                    for r in np.arange(0, radius, step_size):
                        num_points = max(1, int(2 * np.pi * r / step_size))
                        for i in range(num_points):
                            angle = 2 * np.pi * i / num_points
                            x = center_x + r * np.cos(angle)
                            y = center_y + r * np.sin(angle)
                            
                            if component.rotation_allowed:
                                for rot in np.arange(0, 360, component.rotation_step):
                                    candidates.append((Point2D(x, y), rot))
                            else:
                                candidates.append((Point2D(x, y), 0))
        
        # Add some positions near already placed components for better coupling
        if placed_components:
            for placed in placed_components.values():
                if placed.status == PlacementStatus.PLACED:
                    # Generate positions around this component
                    for angle in np.arange(0, 360, 45):
                        dist = component.clearance_radius + self.components[placed.component_id].clearance_radius + 10
                        x = placed.position.x + dist * np.cos(np.radians(angle))
                        y = placed.position.y + dist * np.sin(np.radians(angle))
                        
                        if component.rotation_allowed:
                            candidates.append((Point2D(x, y), angle))
                        else:
                            candidates.append((Point2D(x, y), 0))
        
        return candidates


class SimulatedAnnealingOptimizer(PlacementOptimizer):
    """Simulated annealing algorithm for placement optimization."""
    
    def __init__(self, scenario: PlacementScenario, 
                 initial_temp: float = 100.0,
                 cooling_rate: float = 0.95,
                 min_temp: float = 0.1,
                 max_iterations: int = 1000):
        """
        Initialize SA optimizer.
        
        Args:
            scenario: Placement scenario
            initial_temp: Starting temperature
            cooling_rate: Temperature reduction factor
            min_temp: Minimum temperature before stopping
            max_iterations: Maximum iterations
        """
        super().__init__(scenario)
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.min_temp = min_temp
        self.max_iterations = max_iterations
    
    def optimize(self) -> PlacementSolution:
        """Optimize using simulated annealing."""
        # Start with greedy solution
        greedy = GreedyPlacementOptimizer(self.scenario)
        current_solution = greedy.optimize()
        best_solution = deepcopy(current_solution)
        
        temperature = self.initial_temp
        iteration = 0
        
        while temperature > self.min_temp and iteration < self.max_iterations:
            # Generate neighbor solution
            neighbor = self._generate_neighbor(current_solution)
            
            # Calculate energy difference
            current_energy = -current_solution.total_score  # Negative because we maximize
            neighbor_energy = -neighbor.total_score
            delta_e = neighbor_energy - current_energy
            
            # Accept or reject
            if delta_e < 0 or random.random() < math.exp(-delta_e / temperature):
                current_solution = neighbor
                
                # Update best if improved
                if neighbor.total_score > best_solution.total_score:
                    best_solution = deepcopy(neighbor)
            
            # Cool down
            temperature *= self.cooling_rate
            iteration += 1
        
        return best_solution
    
    def _generate_neighbor(self, solution: PlacementSolution) -> PlacementSolution:
        """Generate a neighbor solution by making small changes."""
        new_placements = deepcopy(solution.placements)
        
        # Choose random component to modify
        placed_components = [p for p in new_placements.values() 
                           if p.status == PlacementStatus.PLACED]
        
        if not placed_components:
            return solution
        
        # Select random component
        comp_to_move = random.choice(placed_components)
        component = self.components[comp_to_move.component_id]
        
        # Try different modifications
        modification_type = random.choice(["move", "rotate", "swap"])
        
        if modification_type == "move":
            # Small position change
            dx = random.uniform(-20, 20)
            dy = random.uniform(-20, 20)
            new_pos = Point2D(
                comp_to_move.position.x + dx,
                comp_to_move.position.y + dy
            )
            
            # Check validity
            other_placements = {k: v for k, v in new_placements.items() 
                              if k != comp_to_move.component_id}
            is_valid, _ = self.is_valid_position(
                component, new_pos, comp_to_move.rotation, other_placements
            )
            
            if is_valid:
                new_placements[comp_to_move.component_id].position = new_pos
        
        elif modification_type == "rotate" and component.rotation_allowed:
            # Change rotation
            new_rotation = (comp_to_move.rotation + component.rotation_step) % 360
            
            # Check validity
            other_placements = {k: v for k, v in new_placements.items() 
                              if k != comp_to_move.component_id}
            is_valid, _ = self.is_valid_position(
                component, comp_to_move.position, new_rotation, other_placements
            )
            
            if is_valid:
                new_placements[comp_to_move.component_id].rotation = new_rotation
        
        elif modification_type == "swap" and len(placed_components) >= 2:
            # Swap two components
            comp1, comp2 = random.sample(placed_components, 2)
            
            # Try swapping positions
            other_placements = {k: v for k, v in new_placements.items() 
                              if k not in [comp1.component_id, comp2.component_id]}
            
            # Check if swap is valid
            valid1, _ = self.is_valid_position(
                self.components[comp1.component_id], 
                comp2.position, comp1.rotation, other_placements
            )
            valid2, _ = self.is_valid_position(
                self.components[comp2.component_id], 
                comp1.position, comp2.rotation, other_placements
            )
            
            if valid1 and valid2:
                new_placements[comp1.component_id].position = comp2.position
                new_placements[comp2.component_id].position = comp1.position
        
        # Recalculate score and validity
        total_score = self.calculate_placement_score(new_placements)
        is_valid = all(p.status == PlacementStatus.PLACED for p in new_placements.values())
        
        # Calculate metrics
        metrics = {
            "placed_count": sum(1 for p in new_placements.values() if p.status == PlacementStatus.PLACED),
            "failed_count": sum(1 for p in new_placements.values() if p.status == PlacementStatus.FAILED),
            "balance_score": self._calculate_balance_score(new_placements),
            "compactness_score": self._calculate_compactness_score(new_placements),
            "zone_score": self._calculate_zone_score(new_placements)
        }
        
        return PlacementSolution(
            placements=new_placements,
            total_score=total_score,
            is_valid=is_valid,
            violations=[],
            metrics=metrics
        )


def optimize_placement(scenario: PlacementScenario, 
                      algorithm: str = "greedy") -> PlacementSolution:
    """
    Optimize component placement for a scenario.
    
    Args:
        scenario: Placement scenario
        algorithm: Algorithm to use ("greedy" or "sa")
    
    Returns:
        Optimized placement solution
    """
    if algorithm == "greedy":
        optimizer = GreedyPlacementOptimizer(scenario)
    elif algorithm == "sa":
        optimizer = SimulatedAnnealingOptimizer(scenario)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    
    return optimizer.optimize()