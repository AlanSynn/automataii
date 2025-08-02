"""
Base Constraint and Solver Interfaces

Implements the abstract base classes for the unified constraint framework
as specified in PAPER_IMPL.md Section 3.

This follows the Strategy pattern for solvers and Composite pattern for constraints.
"""

from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional, Tuple
import numpy as np
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    """Types of constraints in the system."""
    IK = "ik"
    COLLISION = "collision"
    LAYER = "layer"
    GEAR_MESHING = "gear_meshing"
    POSITION = "position"
    DISTANCE = "distance"
    ANGLE = "angle"
    VELOCITY = "velocity"


class ConstraintViolationError(Exception):
    """Raised when constraints cannot be satisfied."""
    
    def __init__(self, constraint_name: str, violation_magnitude: float, message: str = ""):
        self.constraint_name = constraint_name
        self.violation_magnitude = violation_magnitude
        super().__init__(f"Constraint '{constraint_name}' violated (magnitude: {violation_magnitude:.6f}): {message}")


class BaseConstraint(ABC):
    """
    Abstract base class for all constraints in the system.
    
    Each constraint represents a mathematical relationship that must be satisfied.
    Constraints can be equality (C(x) = 0) or inequality (C(x) <= 0) constraints.
    
    Based on PAPER_IMPL.md Section 3:
    - Each constraint contributes to the global constraint vector C(s)
    - Must provide evaluation and gradient methods for solvers
    """
    
    def __init__(self, name: str, constraint_type: ConstraintType, weight: float = 1.0):
        """
        Initialize constraint.
        
        Args:
            name: Human-readable constraint name
            constraint_type: Type of constraint
            weight: Relative importance (higher = more important)
        """
        self.name = name
        self.constraint_type = constraint_type
        self.weight = weight
        self.enabled = True
        self._last_violation = 0.0
    
    @abstractmethod
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """
        Evaluate the constraint equation(s).
        
        Args:
            state: Current system state vector
            
        Returns:
            Constraint violation vector. Should be zero when constraint is satisfied.
            For equality constraints: C(x) = 0
            For inequality constraints: C(x) <= 0 (negative values are acceptable)
        """
        pass
    
    @abstractmethod
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """
        Calculate the gradient (Jacobian) of the constraint function.
        
        Args:
            state: Current system state vector
            
        Returns:
            Jacobian matrix ∂C/∂state where each row corresponds to one constraint equation
            and each column corresponds to one state variable.
            Shape: (num_constraint_equations, len(state))
        """
        pass
    
    def check_violation(self, state: np.ndarray, tolerance: float = 1e-6) -> bool:
        """
        Check if constraint is violated beyond tolerance.
        
        Args:
            state: Current system state
            tolerance: Maximum acceptable violation
            
        Returns:
            True if constraint is violated beyond tolerance
        """
        violation = self.evaluate(state)
        violation_magnitude = np.linalg.norm(violation)
        self._last_violation = violation_magnitude
        
        return violation_magnitude > tolerance
    
    def get_violation_magnitude(self) -> float:
        """Get the magnitude of the last constraint violation."""
        return self._last_violation
    
    def is_equality_constraint(self) -> bool:
        """Check if this is an equality constraint (default: True)."""
        return True
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', type={self.constraint_type.value})"


class BaseSolver(ABC):
    """
    Abstract base class for all constraint solvers.
    
    Implements the Strategy pattern - different solvers can be used
    interchangeably depending on the problem characteristics.
    
    Based on PAPER_IMPL.md Section 3:
    - Solves min ||C(s)||² where C(s) is the constraint vector
    - Different strategies: Newton-Raphson, FABRIK, BFGS, etc.
    """
    
    def __init__(self, name: str, max_iterations: int = 100, tolerance: float = 1e-6):
        """
        Initialize solver.
        
        Args:
            name: Solver name for logging
            max_iterations: Maximum number of iterations
            tolerance: Convergence tolerance
        """
        self.name = name
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # Statistics
        self.last_iterations = 0
        self.last_error = 0.0
        self.total_solves = 0
        self.successful_solves = 0
    
    @abstractmethod
    def solve(self, constraints: List[BaseConstraint], initial_state: np.ndarray, **kwargs) -> np.ndarray:
        """
        Solve the system of constraints.
        
        Args:
            constraints: List of constraints to satisfy
            initial_state: Initial guess for the system state
            **kwargs: Solver-specific parameters
            
        Returns:
            Final state that satisfies constraints (or best approximation)
            
        Raises:
            ConstraintViolationError: If constraints cannot be satisfied
        """
        pass
    
    def check_convergence(self, constraints: List[BaseConstraint], state: np.ndarray) -> bool:
        """
        Check if the current state satisfies all constraints within tolerance.
        
        Args:
            constraints: List of constraints to check
            state: Current system state
            
        Returns:
            True if all constraints are satisfied
        """
        total_violation = 0.0
        
        for constraint in constraints:
            if not constraint.enabled:
                continue
                
            violation = constraint.evaluate(state)
            violation_magnitude = np.linalg.norm(violation) * constraint.weight
            total_violation += violation_magnitude
        
        self.last_error = total_violation
        return total_violation < self.tolerance
    
    def get_statistics(self) -> Dict[str, float]:
        """Get solver performance statistics."""
        success_rate = self.successful_solves / max(1, self.total_solves)
        
        return {
            'total_solves': self.total_solves,
            'successful_solves': self.successful_solves,
            'success_rate': success_rate,
            'last_iterations': self.last_iterations,
            'last_error': self.last_error,
            'average_iterations': self.last_iterations,  # Could be tracked more precisely
        }
    
    def reset_statistics(self):
        """Reset solver statistics."""
        self.total_solves = 0
        self.successful_solves = 0
        self.last_iterations = 0
        self.last_error = 0.0
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', max_iter={self.max_iterations})"


class CompositeConstraint(BaseConstraint):
    """
    A constraint that contains multiple sub-constraints.
    
    Implements the Composite pattern - allows treating groups of constraints
    as a single constraint for hierarchical problem solving.
    """
    
    def __init__(self, name: str, sub_constraints: List[BaseConstraint]):
        """
        Initialize composite constraint.
        
        Args:
            name: Name for this composite
            sub_constraints: List of constituent constraints
        """
        super().__init__(name, ConstraintType.POSITION)  # Generic type for composites
        self.sub_constraints = sub_constraints
    
    def evaluate(self, state: np.ndarray) -> np.ndarray:
        """Evaluate all sub-constraints and concatenate results."""
        violations = []
        
        for constraint in self.sub_constraints:
            if constraint.enabled:
                violation = constraint.evaluate(state)
                violations.append(violation * constraint.weight)
        
        if not violations:
            return np.array([])
        
        return np.concatenate(violations)
    
    def gradient(self, state: np.ndarray) -> np.ndarray:
        """Calculate combined gradient from all sub-constraints."""
        gradients = []
        
        for constraint in self.sub_constraints:
            if constraint.enabled:
                grad = constraint.gradient(state)
                gradients.append(grad * constraint.weight)
        
        if not gradients:
            return np.array([]).reshape(0, len(state))
        
        return np.vstack(gradients)
    
    def add_constraint(self, constraint: BaseConstraint):
        """Add a sub-constraint to this composite."""
        self.sub_constraints.append(constraint)
    
    def remove_constraint(self, constraint_name: str) -> bool:
        """
        Remove a sub-constraint by name.
        
        Args:
            constraint_name: Name of constraint to remove
            
        Returns:
            True if constraint was found and removed
        """
        for i, constraint in enumerate(self.sub_constraints):
            if constraint.name == constraint_name:
                del self.sub_constraints[i]
                return True
        return False
    
    def get_constraint_by_name(self, name: str) -> Optional[BaseConstraint]:
        """Get a sub-constraint by name."""
        for constraint in self.sub_constraints:
            if constraint.name == name:
                return constraint
        return None
    
    def enable_constraint(self, name: str):
        """Enable a specific sub-constraint."""
        constraint = self.get_constraint_by_name(name)
        if constraint:
            constraint.enabled = True
    
    def disable_constraint(self, name: str):
        """Disable a specific sub-constraint."""
        constraint = self.get_constraint_by_name(name)
        if constraint:
            constraint.enabled = False


class ConstraintManager:
    """
    Manages collections of constraints and provides utilities for constraint solving.
    
    This class acts as a facade for the constraint system, providing high-level
    operations for adding, removing, and solving constraints.
    """
    
    def __init__(self):
        self.constraints: List[BaseConstraint] = []
        self.solvers: Dict[str, BaseSolver] = {}
        self.default_solver_name: Optional[str] = None
        self.logger = logging.getLogger(__name__)
    
    def add_constraint(self, constraint: BaseConstraint):
        """Add a constraint to the system."""
        self.constraints.append(constraint)
        self.logger.debug(f"Added constraint: {constraint}")
    
    def remove_constraint(self, name: str) -> bool:
        """Remove a constraint by name."""
        for i, constraint in enumerate(self.constraints):
            if constraint.name == name:
                del self.constraints[i]
                self.logger.debug(f"Removed constraint: {name}")
                return True
        return False
    
    def get_constraint(self, name: str) -> Optional[BaseConstraint]:
        """Get a constraint by name."""
        for constraint in self.constraints:
            if constraint.name == name:
                return constraint
        return None
    
    def add_solver(self, solver: BaseSolver, set_as_default: bool = False):
        """Add a solver to the available solvers."""
        self.solvers[solver.name] = solver
        if set_as_default or self.default_solver_name is None:
            self.default_solver_name = solver.name
        self.logger.debug(f"Added solver: {solver}")
    
    def solve_constraints(self, initial_state: np.ndarray, solver_name: Optional[str] = None, **kwargs) -> np.ndarray:
        """
        Solve all active constraints.
        
        Args:
            initial_state: Initial guess for system state
            solver_name: Name of solver to use (None = use default)
            **kwargs: Additional arguments for solver
            
        Returns:
            Final state that satisfies constraints
            
        Raises:
            ValueError: If no solver available
            ConstraintViolationError: If constraints cannot be satisfied
        """
        if solver_name is None:
            solver_name = self.default_solver_name
        
        if solver_name is None or solver_name not in self.solvers:
            raise ValueError(f"No solver available: {solver_name}")
        
        solver = self.solvers[solver_name]
        active_constraints = [c for c in self.constraints if c.enabled]
        
        if not active_constraints:
            self.logger.warning("No active constraints to solve")
            return initial_state
        
        self.logger.info(f"Solving {len(active_constraints)} constraints with {solver.name}")
        return solver.solve(active_constraints, initial_state, **kwargs)
    
    def check_all_constraints(self, state: np.ndarray, tolerance: float = 1e-6) -> Dict[str, float]:
        """
        Check violation magnitude for all constraints.
        
        Args:
            state: Current system state
            tolerance: Tolerance for violation checking
            
        Returns:
            Dictionary mapping constraint names to violation magnitudes
        """
        violations = {}
        
        for constraint in self.constraints:
            if constraint.enabled:
                is_violated = constraint.check_violation(state, tolerance)
                violations[constraint.name] = constraint.get_violation_magnitude()
        
        return violations
    
    def get_solver_statistics(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all solvers."""
        return {name: solver.get_statistics() for name, solver in self.solvers.items()}
    
    def clear_constraints(self):
        """Remove all constraints."""
        self.constraints.clear()
        self.logger.info("Cleared all constraints")
    
    def clear_solvers(self):
        """Remove all solvers."""
        self.solvers.clear()
        self.default_solver_name = None
        self.logger.info("Cleared all solvers")