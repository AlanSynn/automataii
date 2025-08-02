"""
Newton-Raphson Solver Implementation

Implements the Newton-Raphson method for constraint solving as specified in PAPER_IMPL.md.
This solver uses analytical gradients and is suitable for well-conditioned constraint systems.
"""

from typing import List
import numpy as np
from scipy.linalg import pinv, norm, LinAlgError

from ..base import BaseSolver, BaseConstraint, ConstraintViolationError


class NewtonRaphsonSolver(BaseSolver):
    """
    Newton-Raphson constraint solver.
    
    Solves the nonlinear least-squares problem: min ||C(s)||²
    where C(s) is the constraint vector and s is the system state.
    
    Based on PAPER_IMPL.md Section 3.1:
    - Uses Newton-Raphson iteration: Δs = -(J^T J)^(-1) J^T C(s)
    - Where J = ∂C/∂s is the constraint Jacobian
    - Iterates: s ← s + Δs until ||C(s)||² < tolerance
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6, 
                 damping_factor: float = 1.0, min_damping: float = 0.1):
        """
        Initialize Newton-Raphson solver.
        
        Args:
            max_iterations: Maximum number of iterations
            tolerance: Convergence tolerance for ||C(s)||
            damping_factor: Initial damping factor for step size
            min_damping: Minimum damping factor to prevent divergence
        """
        super().__init__("NewtonRaphson", max_iterations, tolerance)
        self.damping_factor = damping_factor
        self.min_damping = min_damping
        self.use_adaptive_damping = True
    
    def solve(self, constraints: List[BaseConstraint], initial_state: np.ndarray, **kwargs) -> np.ndarray:
        """
        Solve constraints using Newton-Raphson method.
        
        Args:
            constraints: List of constraints to satisfy
            initial_state: Initial guess for system state
            **kwargs: Additional parameters:
                - damping: Override damping factor
                - adaptive_damping: Enable/disable adaptive damping
                
        Returns:
            Final state that satisfies constraints
            
        Raises:
            ConstraintViolationError: If solver fails to converge
        """
        self.total_solves += 1
        
        # Filter active constraints
        active_constraints = [c for c in constraints if c.enabled]
        if not active_constraints:
            self.logger.warning("No active constraints for Newton-Raphson solver")
            self.last_iterations = 0
            return initial_state.copy()
        
        # Initialize
        state = initial_state.copy()
        damping = kwargs.get('damping', self.damping_factor)
        use_adaptive = kwargs.get('adaptive_damping', self.use_adaptive_damping)
        
        self.logger.debug(f"Solving {len(active_constraints)} constraints with Newton-Raphson")
        
        prev_error = float('inf')
        
        for iteration in range(self.max_iterations):
            try:
                # Evaluate all constraint violations
                constraint_values = []
                jacobian_rows = []
                
                for constraint in active_constraints:
                    # Get constraint violation
                    c_val = constraint.evaluate(state)
                    if c_val.size == 0:
                        continue
                    
                    # Apply constraint weight
                    weighted_c_val = c_val * constraint.weight
                    constraint_values.append(weighted_c_val)
                    
                    # Get constraint Jacobian
                    jacobian = constraint.gradient(state)
                    if jacobian.size == 0:
                        continue
                    
                    # Apply constraint weight
                    weighted_jacobian = jacobian * constraint.weight
                    jacobian_rows.append(weighted_jacobian)
                
                if not constraint_values:
                    self.logger.warning("No valid constraint evaluations")
                    break
                
                # Assemble global constraint vector and Jacobian
                C = np.concatenate(constraint_values)
                J = np.vstack(jacobian_rows)
                
                # Check convergence
                error = norm(C)
                self.last_error = error
                
                if error < self.tolerance:
                    self.logger.debug(f"Newton-Raphson converged in {iteration} iterations (error: {error:.2e})")
                    self.last_iterations = iteration
                    self.successful_solves += 1
                    return state
                
                # Adaptive damping: reduce damping if error increased
                if use_adaptive and error > prev_error:
                    damping = max(damping * 0.5, self.min_damping)
                    self.logger.debug(f"Reducing damping to {damping:.3f}")
                elif use_adaptive and error < prev_error * 0.9:
                    damping = min(damping * 1.1, self.damping_factor)
                
                prev_error = error
                
                # Solve Newton step: J^T J Δs = -J^T C
                # Using pseudo-inverse for robustness with rank-deficient systems
                try:
                    JTJ = J.T @ J
                    JTC = J.T @ C
                    
                    # Add regularization for numerical stability
                    regularization = 1e-8 * np.eye(JTJ.shape[0])
                    JTJ_reg = JTJ + regularization
                    
                    delta_s = -np.linalg.solve(JTJ_reg, JTC)
                    
                except (LinAlgError, np.linalg.LinAlgError):
                    # Fallback to pseudo-inverse
                    self.logger.debug("Using pseudo-inverse for Newton step")
                    delta_s = -pinv(J) @ C
                
                # Apply damped update
                state += damping * delta_s
                
                # Log progress
                if iteration % 10 == 0:
                    self.logger.debug(f"Iteration {iteration}: error = {error:.2e}, damping = {damping:.3f}")
                
            except Exception as e:
                self.logger.error(f"Error in Newton-Raphson iteration {iteration}: {e}")
                raise ConstraintViolationError("NewtonRaphson", error, f"Solver error: {e}")
        
        # Did not converge
        self.last_iterations = self.max_iterations
        final_error = norm(np.concatenate([c.evaluate(state) * c.weight for c in active_constraints if c.enabled]))
        
        if final_error < self.tolerance * 10:  # Accept "close enough" solutions
            self.logger.warning(f"Newton-Raphson converged slowly (error: {final_error:.2e})")
            self.successful_solves += 1
            return state
        else:
            self.logger.error(f"Newton-Raphson failed to converge (final error: {final_error:.2e})")
            raise ConstraintViolationError("NewtonRaphson", final_error, 
                                         f"Failed to converge after {self.max_iterations} iterations")
    
    def solve_with_line_search(self, constraints: List[BaseConstraint], initial_state: np.ndarray, **kwargs) -> np.ndarray:
        """
        Solve with line search for improved convergence.
        
        This variant uses backtracking line search to ensure that each step
        reduces the constraint violation.
        
        Args:
            constraints: List of constraints to satisfy
            initial_state: Initial guess for system state
            **kwargs: Additional parameters
                
        Returns:
            Final state that satisfies constraints
        """
        self.total_solves += 1
        
        active_constraints = [c for c in constraints if c.enabled]
        if not active_constraints:
            return initial_state.copy()
        
        state = initial_state.copy()
        alpha = 1.0  # Step size
        beta = 0.5   # Step reduction factor
        sigma = 0.1  # Armijo parameter
        
        def evaluate_objective(s):
            """Evaluate ||C(s)||² objective function."""
            total = 0.0
            for constraint in active_constraints:
                c_val = constraint.evaluate(s)
                if c_val.size > 0:
                    total += np.sum((c_val * constraint.weight) ** 2)
            return total
        
        for iteration in range(self.max_iterations):
            # Evaluate constraints and Jacobian
            constraint_values = []
            jacobian_rows = []
            
            for constraint in active_constraints:
                c_val = constraint.evaluate(state)
                if c_val.size == 0:
                    continue
                
                weighted_c_val = c_val * constraint.weight
                constraint_values.append(weighted_c_val)
                
                jacobian = constraint.gradient(state)
                if jacobian.size == 0:
                    continue
                
                weighted_jacobian = jacobian * constraint.weight
                jacobian_rows.append(weighted_jacobian)
            
            if not constraint_values:
                break
            
            C = np.concatenate(constraint_values)
            J = np.vstack(jacobian_rows)
            
            # Check convergence
            error = norm(C)
            if error < self.tolerance:
                self.last_iterations = iteration
                self.successful_solves += 1
                return state
            
            # Compute Newton direction
            try:
                delta_s = -pinv(J) @ C
            except:
                self.logger.error("Failed to compute Newton direction")
                break
            
            # Line search
            current_obj = evaluate_objective(state)
            gradient_dot_direction = -2 * C.T @ J @ delta_s  # Gradient of ||C||² dot direction
            
            alpha = 1.0
            for _ in range(20):  # Max line search iterations
                new_state = state + alpha * delta_s
                new_obj = evaluate_objective(new_state)
                
                # Armijo condition
                if new_obj <= current_obj + sigma * alpha * gradient_dot_direction:
                    break
                
                alpha *= beta
            else:
                self.logger.warning("Line search failed")
                alpha = 0.01  # Very small step
            
            # Update state
            state += alpha * delta_s
        
        # Final check
        final_error = norm(np.concatenate([c.evaluate(state) * c.weight for c in active_constraints if c.enabled]))
        self.last_iterations = self.max_iterations
        
        if final_error < self.tolerance * 10:
            self.successful_solves += 1
        else:
            raise ConstraintViolationError("NewtonRaphsonLS", final_error, "Line search failed to converge")
        
        return state
    
    def get_condition_number(self, constraints: List[BaseConstraint], state: np.ndarray) -> float:
        """
        Estimate the condition number of the constraint Jacobian.
        
        This can be used to detect ill-conditioned constraint systems.
        
        Args:
            constraints: List of constraints
            state: Current system state
            
        Returns:
            Condition number (higher = more ill-conditioned)
        """
        active_constraints = [c for c in constraints if c.enabled]
        
        jacobian_rows = []
        for constraint in active_constraints:
            jacobian = constraint.gradient(state)
            if jacobian.size > 0:
                jacobian_rows.append(jacobian * constraint.weight)
        
        if not jacobian_rows:
            return 1.0
        
        J = np.vstack(jacobian_rows)
        
        try:
            return np.linalg.cond(J)
        except:
            return float('inf')