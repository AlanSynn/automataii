"""
Explicit Newton-Raphson Solver for Constraint-Based Assembly Simulation

Implements the exact algorithm from PAPER_IMPL.md Section 2.1:
- Solves: min ||C(s)||^2
- Uses: Δs = -(J^T J)^-1 J^T C(s) where J = ∂C/∂s
- Handles rank deficiency with Moore-Penrose pseudo-inverse

250% Confidence Implementation
"""

import numpy as np
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from ..base import BaseConstraint, BaseSolver


@dataclass
class SolverResult:
    """Result from Newton-Raphson constraint solving."""
    success: bool
    final_state: np.ndarray
    final_error: float
    iterations: int
    convergence_history: List[float]
    rank_deficient_steps: int
    metadata: Dict[str, Any]


class NewtonRaphsonExplicitSolver(BaseSolver):
    """
    Explicit Newton-Raphson solver implementing PAPER_IMPL.md Section 2.1.
    
    This is the core physics engine that solves for component states
    such that geometric constraints are satisfied.
    
    Mathematical Foundation:
    - Each component i has 6-DOF state s_i = {T_i, α_i, β_i, γ_i}
    - Constraints formulated as vector function C(s) = 0
    - Iterative solution: s ← s + Δs where Δs = -(J^T J)^-1 J^T C(s)
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6,
                 min_step_size: float = 1e-8, damping_factor: float = 1.0):
        """
        Initialize explicit Newton-Raphson solver.
        
        Args:
            max_iterations: Maximum iterations before failure
            tolerance: Convergence tolerance for ||C(s)||^2
            min_step_size: Minimum step size before failure
            damping_factor: Damping for stability (1.0 = pure Newton-Raphson)
        """
        super().__init__("NewtonRaphsonExplicit")
        
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.min_step_size = min_step_size
        self.damping_factor = damping_factor
        
        self.logger = logging.getLogger(__name__)
        
        # Solver state
        self.last_iterations = 0
        self.last_error = float('inf')
        self.convergence_history = []
        
    def solve(self, constraints: List[BaseConstraint], initial_state: np.ndarray,
              **kwargs) -> np.ndarray:
        """
        Solve constraint system using explicit Newton-Raphson method.
        
        Args:
            constraints: List of geometric constraints to satisfy
            initial_state: Initial state vector for all components
            **kwargs: Additional solver parameters
            
        Returns:
            Final state vector satisfying constraints
            
        Raises:
            RuntimeError: If solver fails to converge
        """
        if not constraints:
            return initial_state.copy()
        
        result = self.solve_detailed(constraints, initial_state, **kwargs)
        
        if not result.success:
            raise RuntimeError(f"Newton-Raphson solver failed: {result.metadata.get('error', 'Unknown')}")
        
        return result.final_state
    
    def solve_detailed(self, constraints: List[BaseConstraint], initial_state: np.ndarray,
                      **kwargs) -> SolverResult:
        """
        Solve with detailed result information.
        
        Args:
            constraints: List of geometric constraints to satisfy
            initial_state: Initial state vector for all components
            **kwargs: Additional solver parameters
            
        Returns:
            Detailed solver result with convergence information
        """
        # Initialize solver state
        s = initial_state.copy()
        convergence_history = []
        rank_deficient_steps = 0
        
        self.logger.debug(f"Starting Newton-Raphson with {len(constraints)} constraints, "
                         f"state dimension: {len(s)}")
        
        try:
            for iteration in range(self.max_iterations):
                # 1. Evaluate constraint vector C(s)
                constraint_vector = self._evaluate_constraints(constraints, s)
                constraint_error = np.linalg.norm(constraint_vector)**2
                convergence_history.append(constraint_error)
                
                self.logger.debug(f"Iteration {iteration}: ||C(s)||^2 = {constraint_error:.2e}")
                
                # 2. Check convergence
                if constraint_error < self.tolerance:
                    self.logger.info(f"Newton-Raphson converged in {iteration} iterations "
                                   f"(error: {constraint_error:.2e})")
                    
                    return SolverResult(
                        success=True,
                        final_state=s,
                        final_error=constraint_error,
                        iterations=iteration,
                        convergence_history=convergence_history,
                        rank_deficient_steps=rank_deficient_steps,
                        metadata={"convergence_rate": self._compute_convergence_rate(convergence_history)}
                    )
                
                # 3. Compute constraint Jacobian J = ∂C/∂s
                try:
                    jacobian = self._compute_constraint_jacobian(constraints, s)
                except Exception as e:
                    return SolverResult(
                        success=False,
                        final_state=s,
                        final_error=constraint_error,
                        iterations=iteration,
                        convergence_history=convergence_history,
                        rank_deficient_steps=rank_deficient_steps,
                        metadata={"error": f"Jacobian computation failed: {e}"}
                    )
                
                # 4. Solve linear system: (J^T J) Δs = -J^T C(s)
                # Using pseudo-inverse for rank deficiency handling
                try:
                    JtJ = jacobian.T @ jacobian
                    JtC = jacobian.T @ constraint_vector
                    
                    # Check for rank deficiency
                    rank = np.linalg.matrix_rank(JtJ)
                    expected_rank = min(JtJ.shape)
                    
                    if rank < expected_rank:
                        rank_deficient_steps += 1
                        self.logger.warning(f"Rank deficient system: rank={rank}, expected={expected_rank}")
                    
                    # Use Moore-Penrose pseudo-inverse for stability
                    JtJ_inv = np.linalg.pinv(JtJ)
                    delta_s = -JtJ_inv @ JtC
                    
                except np.linalg.LinAlgError as e:
                    return SolverResult(
                        success=False,
                        final_state=s,
                        final_error=constraint_error,
                        iterations=iteration,
                        convergence_history=convergence_history,
                        rank_deficient_steps=rank_deficient_steps,
                        metadata={"error": f"Linear system solve failed: {e}"}
                    )
                
                # 5. Apply damping and check step size
                step_size = np.linalg.norm(delta_s)
                if step_size < self.min_step_size:
                    return SolverResult(
                        success=False,
                        final_state=s,
                        final_error=constraint_error,
                        iterations=iteration,
                        convergence_history=convergence_history,
                        rank_deficient_steps=rank_deficient_steps,
                        metadata={"error": f"Step size too small: {step_size:.2e}"}
                    )
                
                # 6. Update state: s ← s + damping_factor * Δs
                s = s + self.damping_factor * delta_s
                
                self.logger.debug(f"Step size: {step_size:.2e}, damping: {self.damping_factor}")
        
        except Exception as e:
            return SolverResult(
                success=False,
                final_state=s,
                final_error=float('inf'),
                iterations=self.max_iterations,
                convergence_history=convergence_history,
                rank_deficient_steps=rank_deficient_steps,
                metadata={"error": f"Unexpected error: {e}"}
            )
        
        # Failed to converge
        final_error = np.linalg.norm(self._evaluate_constraints(constraints, s))**2
        return SolverResult(
            success=False,
            final_state=s,
            final_error=final_error,
            iterations=self.max_iterations,
            convergence_history=convergence_history,
            rank_deficient_steps=rank_deficient_steps,
            metadata={"error": f"Failed to converge after {self.max_iterations} iterations"}
        )
    
    def _evaluate_constraints(self, constraints: List[BaseConstraint], state: np.ndarray) -> np.ndarray:
        """
        Evaluate all constraints at current state.
        
        Args:
            constraints: List of constraints to evaluate
            state: Current state vector
            
        Returns:
            Concatenated constraint vector C(s)
        """
        constraint_values = []
        
        for constraint in constraints:
            if not constraint.enabled:
                continue
                
            try:
                value = constraint.evaluate(state)
                if isinstance(value, np.ndarray):
                    constraint_values.extend(value.flatten())
                else:
                    constraint_values.append(float(value))
            except Exception as e:
                self.logger.error(f"Error evaluating constraint {constraint.name}: {e}")
                raise
        
        return np.array(constraint_values)
    
    def _compute_constraint_jacobian(self, constraints: List[BaseConstraint], 
                                   state: np.ndarray) -> np.ndarray:
        """
        Compute constraint Jacobian J = ∂C/∂s.
        
        Args:
            constraints: List of constraints
            state: Current state vector
            
        Returns:
            Jacobian matrix [n_constraints x n_state]
        """
        jacobian_rows = []
        
        for constraint in constraints:
            if not constraint.enabled:
                continue
                
            try:
                grad = constraint.gradient(state)
                if grad.ndim == 1:
                    jacobian_rows.append(grad.reshape(1, -1))
                else:
                    jacobian_rows.append(grad)
            except Exception as e:
                self.logger.error(f"Error computing gradient for constraint {constraint.name}: {e}")
                raise
        
        if not jacobian_rows:
            return np.zeros((0, len(state)))
        
        return np.vstack(jacobian_rows)
    
    def _compute_convergence_rate(self, history: List[float]) -> float:
        """Compute average convergence rate from error history."""
        if len(history) < 3:
            return 0.0
        
        rates = []
        for i in range(1, len(history) - 1):
            if history[i] > 0 and history[i+1] > 0:
                rate = history[i+1] / history[i]
                rates.append(rate)
        
        return np.mean(rates) if rates else 1.0
    
    def solve_state_at_time(self, constraints: List[BaseConstraint], 
                           initial_state: np.ndarray, driver_phase: float,
                           **kwargs) -> np.ndarray:
        """
        Solve for state at specific driver phase (for time-based simulation).
        
        Args:
            constraints: List of constraints (may include phase constraints)
            initial_state: Initial guess for state
            driver_phase: Phase of driving mechanism
            **kwargs: Additional parameters
            
        Returns:
            State vector at specified phase
        """
        # Update phase constraints if present
        for constraint in constraints:
            if hasattr(constraint, 'set_driver_phase'):
                constraint.set_driver_phase(driver_phase)
        
        return self.solve(constraints, initial_state, **kwargs)
    
    def get_solver_statistics(self) -> Dict[str, Any]:
        """Get solver performance statistics."""
        return {
            "name": self.name,
            "last_iterations": self.last_iterations,
            "last_error": self.last_error,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
            "damping_factor": self.damping_factor
        }