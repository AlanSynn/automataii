"""
Gear Train Optimizer

Implements gear train optimization as specified in PAPER_IMPL.md Section 6.1.
Connects multiple mechanisms to a single driver using constrained optimization.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from scipy.optimize import minimize

from automataii.domain.constraints.base import BaseConstraint, ConstraintType
from automataii.domain.optimization.pipeline import OptimizationPipeline, OptimizationStage


class GearType(Enum):
    """Types of gears in the train."""
    DRIVER = "driver"           # Input gear (connected to motor)
    INTERMEDIATE = "intermediate"  # Intermediate gears for ratio/direction
    OUTPUT = "output"          # Output gears (connected to mechanisms)


@dataclass
class GearSpec:
    """Specification for a gear in the train."""
    gear_id: str
    gear_type: GearType
    target_radius: float       # Desired radius (mm)
    min_radius: float = 10.0   # Minimum allowable radius
    max_radius: float = 100.0  # Maximum allowable radius
    position: Optional[Tuple[float, float]] = None  # Fixed position if known
    mechanism_id: Optional[str] = None  # Connected mechanism ID
    target_rpm: Optional[float] = None  # Target rotation speed


@dataclass
class GearMeshConstraint:
    """Constraint for two meshing gears."""
    gear_a: str
    gear_b: str
    center_distance: float     # Distance between gear centers
    gear_ratio: Optional[float] = None  # Required gear ratio (r_b / r_a)


@dataclass
class GearTrainSolution:
    """Solution for gear train optimization."""
    success: bool
    gear_radii: Dict[str, float]
    gear_positions: Dict[str, Tuple[float, float]]
    gear_ratios: Dict[Tuple[str, str], float]
    total_error: float
    individual_errors: Dict[str, float]
    metadata: Dict[str, Any]


class GearTrainOptimizer:
    """
    Gear train optimizer using constrained optimization.
    
    Implements the algorithm from PAPER_IMPL.md Section 6.1:
    - Objective: Minimize deviation from target radii
    - Constraints: Gear meshing equations, alignment, non-intersection
    - Method: Sequential Quadratic Programming (SQP)
    """
    
    def __init__(self, driver_rpm: float = 60.0):
        """
        Initialize gear train optimizer.
        
        Args:
            driver_rpm: Driver gear rotation speed (RPM)
        """
        self.driver_rpm = driver_rpm
        self.logger = logging.getLogger(__name__)
        
        # Problem specification
        self.gears: Dict[str, GearSpec] = {}
        self.mesh_constraints: List[GearMeshConstraint] = []
        self.alignment_constraints: List[Dict[str, Any]] = []
        
        # Optimization settings
        self.max_iterations = 200
        self.tolerance = 1e-6
        self.penalty_weight = 1000.0
        
        # Results
        self.last_solution: Optional[GearTrainSolution] = None
        self.optimization_history: List[Dict[str, Any]] = []
    
    def add_gear(self, gear_spec: GearSpec):
        """Add a gear to the train specification."""
        self.gears[gear_spec.gear_id] = gear_spec
        self.logger.debug(f"Added gear {gear_spec.gear_id} (type: {gear_spec.gear_type.value})")
    
    def add_mesh_constraint(self, gear_a: str, gear_b: str, center_distance: float,
                           gear_ratio: Optional[float] = None):
        """
        Add a meshing constraint between two gears.
        
        Args:
            gear_a: First gear ID
            gear_b: Second gear ID
            center_distance: Distance between gear centers
            gear_ratio: Required gear ratio (r_b / r_a), None for auto-calculate
        """
        if gear_a not in self.gears or gear_b not in self.gears:
            raise ValueError(f"Unknown gears: {gear_a}, {gear_b}")
        
        constraint = GearMeshConstraint(gear_a, gear_b, center_distance, gear_ratio)
        self.mesh_constraints.append(constraint)
        
        self.logger.debug(f"Added mesh constraint: {gear_a} <-> {gear_b} "
                         f"(distance: {center_distance:.1f}mm)")
    
    def add_alignment_constraint(self, gear_ids: List[str], axis: str = 'x', 
                               tolerance: float = 1.0):
        """
        Add alignment constraint for multiple gears.
        
        Args:
            gear_ids: List of gear IDs that should be aligned
            axis: Alignment axis ('x' or 'y')
            tolerance: Alignment tolerance (mm)
        """
        constraint = {
            'type': 'alignment',
            'gear_ids': gear_ids,
            'axis': axis,
            'tolerance': tolerance
        }
        self.alignment_constraints.append(constraint)
        
        self.logger.debug(f"Added alignment constraint: {gear_ids} on {axis}-axis")
    
    def optimize(self, initial_positions: Optional[Dict[str, Tuple[float, float]]] = None,
                 weights: Optional[Dict[str, float]] = None) -> GearTrainSolution:
        """
        Optimize the gear train configuration.
        
        Args:
            initial_positions: Initial gear center positions
            weights: Objective function weights for different criteria
            
        Returns:
            GearTrainSolution with optimized gear configuration
        """
        if not self.gears:
            raise ValueError("No gears specified")
        
        if not self.mesh_constraints:
            raise ValueError("No mesh constraints specified")
        
        self.logger.info(f"Optimizing gear train with {len(self.gears)} gears "
                        f"and {len(self.mesh_constraints)} mesh constraints")
        
        # Setup optimization variables
        gear_ids = list(self.gears.keys())
        n_gears = len(gear_ids)
        
        # Variables: [r1, r2, ..., rn, x1, y1, x2, y2, ..., xn, yn]
        # where r_i is radius of gear i, (x_i, y_i) is position of gear i
        n_vars = n_gears * 3  # radius + x + y for each gear
        
        # Initial guess
        x0 = self._create_initial_guess(gear_ids, initial_positions)
        
        # Bounds
        bounds = self._create_bounds(gear_ids)
        
        # Objective function
        def objective(x):
            return self._objective_function(x, gear_ids, weights or {})
        
        # Constraints
        constraints = self._create_optimization_constraints(gear_ids)
        
        # Run optimization
        try:
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={
                    'maxiter': self.max_iterations,
                    'ftol': self.tolerance,
                    'disp': False
                }
            )
            
            # Parse solution
            solution = self._parse_solution(result, gear_ids)
            
            self.last_solution = solution
            self.optimization_history.append({
                'success': solution.success,
                'error': solution.total_error,
                'iterations': result.nit,
                'function_evaluations': result.nfev
            })
            
            if solution.success:
                self.logger.info(f"Gear train optimization succeeded "
                               f"(error: {solution.total_error:.2e}, iterations: {result.nit})")
            else:
                self.logger.warning(f"Gear train optimization failed: {result.message}")
            
            return solution
            
        except Exception as e:
            self.logger.error(f"Gear train optimization failed: {e}")
            return GearTrainSolution(
                success=False,
                gear_radii={},
                gear_positions={},
                gear_ratios={},
                total_error=float('inf'),
                individual_errors={},
                metadata={'error': str(e)}
            )
    
    def _create_initial_guess(self, gear_ids: List[str], 
                             initial_positions: Optional[Dict[str, Tuple[float, float]]]) -> np.ndarray:
        """Create initial guess for optimization variables."""
        n_gears = len(gear_ids)
        x0 = np.zeros(n_gears * 3)
        
        for i, gear_id in enumerate(gear_ids):
            gear_spec = self.gears[gear_id]
            
            # Initial radius (middle of allowed range)
            r_init = gear_spec.target_radius
            if r_init < gear_spec.min_radius or r_init > gear_spec.max_radius:
                r_init = (gear_spec.min_radius + gear_spec.max_radius) / 2
            
            x0[i] = r_init
            
            # Initial position
            if initial_positions and gear_id in initial_positions:
                x_init, y_init = initial_positions[gear_id]
            elif gear_spec.position is not None:
                x_init, y_init = gear_spec.position
            else:
                # Default grid layout
                row = i // 3
                col = i % 3
                x_init = col * 100.0
                y_init = row * 100.0
            
            x0[n_gears + 2*i] = x_init      # x position
            x0[n_gears + 2*i + 1] = y_init  # y position
        
        return x0
    
    def _create_bounds(self, gear_ids: List[str]) -> List[Tuple[float, float]]:
        """Create bounds for optimization variables."""
        bounds = []
        n_gears = len(gear_ids)
        
        # Radius bounds
        for gear_id in gear_ids:
            gear_spec = self.gears[gear_id]
            bounds.append((gear_spec.min_radius, gear_spec.max_radius))
        
        # Position bounds (generous workspace)
        for gear_id in gear_ids:
            gear_spec = self.gears[gear_id]
            if gear_spec.position is not None:
                # Fixed position
                x_fixed, y_fixed = gear_spec.position
                bounds.append((x_fixed, x_fixed))  # x
                bounds.append((y_fixed, y_fixed))  # y
            else:
                # Free position within workspace
                bounds.append((-500.0, 500.0))  # x
                bounds.append((-500.0, 500.0))  # y
        
        return bounds
    
    def _objective_function(self, x: np.ndarray, gear_ids: List[str], 
                           weights: Dict[str, float]) -> float:
        """
        Objective function: minimize deviation from target radii.
        
        Based on PAPER_IMPL.md Section 6.1: "Minimize deviation from target radii"
        """
        n_gears = len(gear_ids)
        
        # Extract radii
        radii = x[:n_gears]
        
        # Objective: sum of squared deviations from target radii
        total_cost = 0.0
        
        for i, gear_id in enumerate(gear_ids):
            gear_spec = self.gears[gear_id]
            target_radius = gear_spec.target_radius
            current_radius = radii[i]
            
            # Quadratic penalty for deviation from target
            deviation = (current_radius - target_radius) ** 2
            weight = weights.get(gear_id, 1.0)
            total_cost += weight * deviation
        
        # Additional objectives can be added here
        # e.g., minimize total volume, minimize manufacturing cost, etc.
        
        return total_cost
    
    def _create_optimization_constraints(self, gear_ids: List[str]) -> List[Dict[str, Any]]:
        """Create constraints for scipy optimization."""
        constraints = []
        
        # Mesh constraints
        for mesh in self.mesh_constraints:
            constraint = {
                'type': 'eq',
                'fun': lambda x, m=mesh: self._mesh_constraint(x, gear_ids, m)
            }
            constraints.append(constraint)
        
        # Non-intersection constraints
        for i, gear_a in enumerate(gear_ids):
            for j, gear_b in enumerate(gear_ids):
                if i < j:  # Avoid duplicate constraints
                    # Check if they're supposed to mesh
                    is_meshing = any(
                        (m.gear_a == gear_a and m.gear_b == gear_b) or
                        (m.gear_a == gear_b and m.gear_b == gear_a)
                        for m in self.mesh_constraints
                    )
                    
                    if not is_meshing:
                        constraint = {
                            'type': 'ineq',
                            'fun': lambda x, ga=gear_a, gb=gear_b: self._non_intersection_constraint(x, gear_ids, ga, gb)
                        }
                        constraints.append(constraint)
        
        # Alignment constraints
        for align in self.alignment_constraints:
            if align['type'] == 'alignment':
                constraint = {
                    'type': 'eq',
                    'fun': lambda x, a=align: self._alignment_constraint(x, gear_ids, a)
                }
                constraints.append(constraint)
        
        return constraints
    
    def _mesh_constraint(self, x: np.ndarray, gear_ids: List[str], 
                        mesh: GearMeshConstraint) -> float:
        """
        Meshing constraint: r_a + r_b = center_distance
        
        Returns 0 when constraint is satisfied.
        """
        n_gears = len(gear_ids)
        
        # Get gear indices
        idx_a = gear_ids.index(mesh.gear_a)
        idx_b = gear_ids.index(mesh.gear_b)
        
        # Extract radii and positions
        r_a = x[idx_a]
        r_b = x[idx_b]
        
        x_a = x[n_gears + 2*idx_a]
        y_a = x[n_gears + 2*idx_a + 1]
        x_b = x[n_gears + 2*idx_b]
        y_b = x[n_gears + 2*idx_b + 1]
        
        # Current center distance
        current_distance = np.sqrt((x_b - x_a)**2 + (y_b - y_a)**2)
        
        # Constraint: r_a + r_b = center_distance
        required_distance = r_a + r_b
        
        return current_distance - required_distance
    
    def _non_intersection_constraint(self, x: np.ndarray, gear_ids: List[str],
                                   gear_a: str, gear_b: str) -> float:
        """
        Non-intersection constraint: distance between centers > r_a + r_b + clearance
        
        Returns positive value when constraint is satisfied.
        """
        n_gears = len(gear_ids)
        clearance = 5.0  # Minimum clearance between gears (mm)
        
        # Get gear indices
        idx_a = gear_ids.index(gear_a)
        idx_b = gear_ids.index(gear_b)
        
        # Extract radii and positions
        r_a = x[idx_a]
        r_b = x[idx_b]
        
        x_a = x[n_gears + 2*idx_a]
        y_a = x[n_gears + 2*idx_a + 1]
        x_b = x[n_gears + 2*idx_b]
        y_b = x[n_gears + 2*idx_b + 1]
        
        # Current center distance
        current_distance = np.sqrt((x_b - x_a)**2 + (y_b - y_a)**2)
        
        # Required minimum distance
        min_distance = r_a + r_b + clearance
        
        return current_distance - min_distance
    
    def _alignment_constraint(self, x: np.ndarray, gear_ids: List[str],
                             align: Dict[str, Any]) -> float:
        """
        Alignment constraint: gears should be aligned on specified axis.
        
        Returns 0 when perfectly aligned.
        """
        n_gears = len(gear_ids)
        gear_list = align['gear_ids']
        axis = align['axis']
        
        if len(gear_list) < 2:
            return 0.0
        
        # Get positions of all gears in the alignment group
        positions = []
        for gear_id in gear_list:
            idx = gear_ids.index(gear_id)
            if axis == 'x':
                pos = x[n_gears + 2*idx]      # x position
            else:  # axis == 'y'
                pos = x[n_gears + 2*idx + 1]  # y position
            positions.append(pos)
        
        # Constraint: all positions should be equal
        # Return variance (0 when all equal)
        mean_pos = np.mean(positions)
        variance = np.sum((np.array(positions) - mean_pos)**2)
        
        return variance
    
    def _parse_solution(self, result, gear_ids: List[str]) -> GearTrainSolution:
        """Parse optimization result into GearTrainSolution."""
        n_gears = len(gear_ids)
        
        if result.success and hasattr(result, 'x'):
            x = result.x
            
            # Extract gear radii
            gear_radii = {}
            for i, gear_id in enumerate(gear_ids):
                gear_radii[gear_id] = x[i]
            
            # Extract gear positions
            gear_positions = {}
            for i, gear_id in enumerate(gear_ids):
                x_pos = x[n_gears + 2*i]
                y_pos = x[n_gears + 2*i + 1]
                gear_positions[gear_id] = (x_pos, y_pos)
            
            # Calculate gear ratios
            gear_ratios = {}
            for mesh in self.mesh_constraints:
                r_a = gear_radii[mesh.gear_a]
                r_b = gear_radii[mesh.gear_b]
                ratio = r_b / r_a if r_a > 0 else 1.0
                gear_ratios[(mesh.gear_a, mesh.gear_b)] = ratio
            
            # Calculate individual errors
            individual_errors = {}
            for gear_id in gear_ids:
                target = self.gears[gear_id].target_radius
                actual = gear_radii[gear_id]
                individual_errors[gear_id] = abs(actual - target)
            
            return GearTrainSolution(
                success=True,
                gear_radii=gear_radii,
                gear_positions=gear_positions,
                gear_ratios=gear_ratios,
                total_error=result.fun,
                individual_errors=individual_errors,
                metadata={
                    'iterations': result.nit,
                    'function_evaluations': result.nfev,
                    'message': result.message
                }
            )
        else:
            return GearTrainSolution(
                success=False,
                gear_radii={},
                gear_positions={},
                gear_ratios={},
                total_error=float('inf'),
                individual_errors={},
                metadata={
                    'message': result.message if hasattr(result, 'message') else 'Optimization failed'
                }
            )
    
    def calculate_gear_ratios_to_mechanisms(self, solution: GearTrainSolution) -> Dict[str, float]:
        """
        Calculate gear ratios from driver to each mechanism.
        
        Args:
            solution: Optimized gear train solution
            
        Returns:
            Dictionary mapping mechanism_id to gear ratio from driver
        """
        if not solution.success:
            return {}
        
        ratios = {}
        
        # Find driver gear
        driver_id = None
        for gear_id, gear_spec in self.gears.items():
            if gear_spec.gear_type == GearType.DRIVER:
                driver_id = gear_id
                break
        
        if driver_id is None:
            self.logger.error("No driver gear found")
            return {}
        
        # Calculate path to each mechanism
        for gear_id, gear_spec in self.gears.items():
            if gear_spec.mechanism_id is not None:
                # Find path from driver to this gear
                ratio = self._calculate_gear_ratio_path(driver_id, gear_id, solution.gear_ratios)
                if ratio is not None:
                    ratios[gear_spec.mechanism_id] = ratio
        
        return ratios
    
    def _calculate_gear_ratio_path(self, from_gear: str, to_gear: str, 
                                  gear_ratios: Dict[Tuple[str, str], float]) -> Optional[float]:
        """Calculate total gear ratio along path from one gear to another."""
        # Simple implementation for direct connections
        # A full implementation would use graph traversal
        
        # Check direct connection
        for (gear_a, gear_b), ratio in gear_ratios.items():
            if gear_a == from_gear and gear_b == to_gear:
                return ratio
            elif gear_a == to_gear and gear_b == from_gear:
                return 1.0 / ratio
        
        # TODO: Implement multi-hop path finding for complex gear trains
        return None
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """Get optimization performance statistics."""
        if not self.optimization_history:
            return {}
        
        successes = [h['success'] for h in self.optimization_history]
        errors = [h['error'] for h in self.optimization_history if h['success']]
        
        return {
            'total_optimizations': len(self.optimization_history),
            'success_rate': sum(successes) / len(successes),
            'average_error': np.mean(errors) if errors else float('inf'),
            'best_error': min(errors) if errors else float('inf'),
            'last_solution_success': self.last_solution.success if self.last_solution else False
        }