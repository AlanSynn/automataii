"""
Mechanism Optimizer with Implicit Function Theorem

Implements PAPER_IMPL.md Section 2.2 exact algorithm:
- BFGS optimization with analytical gradients
- Implicit Function Theorem: ∂s_t/∂p = -(∂C/∂s_t)^-1(∂C/∂p)
- Performance-critical gradient calculation

250% Confidence Implementation
"""

import numpy as np
import logging
from typing import List, Dict, Any, Optional, Callable
from scipy.optimize import minimize
from dataclasses import dataclass

from .mechanism import MotionCurve
from ..constraints.base import BaseConstraint
from ..constraints.solvers.newton_raphson_explicit_solver import NewtonRaphsonExplicitSolver


@dataclass
class OptimizationResult:
    """Result from mechanism optimization."""
    success: bool
    optimized_parameters: np.ndarray
    final_error: float
    iterations: int
    convergence_history: List[float]
    gradient_evaluations: int
    implicit_gradient_time: float
    metadata: Dict[str, Any]


class MechanismOptimizer:
    """
    BFGS mechanism optimizer with Implicit Function Theorem gradients.
    
    Implements the exact algorithm from PAPER_IMPL.md Section 2.2:
    
    Objective Function: F(p) = ∫ ||x(p, s_t) - x_target_t||^2 dt
    
    Key Innovation: Analytical gradient calculation using Implicit Function Theorem
    ∂s_t/∂p = -(∂C/∂s_t)^-1(∂C/∂p)
    
    This avoids expensive finite differences on the full simulation,
    enabling real-time interactive optimization.
    """
    
    def __init__(self, simulation_engine, max_iterations: int = 50, 
                 tolerance: float = 1e-6):
        """
        Initialize mechanism optimizer.
        
        Args:
            simulation_engine: Constraint-based simulation engine
            max_iterations: Maximum BFGS iterations
            tolerance: Convergence tolerance for objective function
        """
        self.simulation_engine = simulation_engine
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        
        self.logger = logging.getLogger(__name__)
        
        # Optimization state tracking
        self.gradient_evaluations = 0
        self.implicit_gradient_times = []
        self.convergence_history = []
        
        # Time steps for objective function integration
        self.time_steps = 50  # Configurable resolution
        
    def optimize(self, mechanism, target_curve: MotionCurve, 
                initial_parameters: Optional[np.ndarray] = None) -> OptimizationResult:
        """
        Optimize mechanism parameters to match target curve.
        
        Args:
            mechanism: Mechanism object with constraints and attachment point
            target_curve: Target motion curve to match
            initial_parameters: Initial parameter guess (if None, use mechanism defaults)
            
        Returns:
            Optimization result with optimized parameters
        """
        self.logger.info(f"Starting mechanism optimization with {self.time_steps} time steps")
        
        # Initialize parameters
        if initial_parameters is None:
            initial_parameters = mechanism.get_default_parameters()
        
        p0 = np.array(initial_parameters, dtype=float)
        
        # Reset tracking variables
        self.gradient_evaluations = 0
        self.implicit_gradient_times = []
        self.convergence_history = []
        
        # Define objective function
        def objective_function(p):
            return self._compute_objective(p, mechanism, target_curve)
        
        # Define gradient function using Implicit Function Theorem
        def gradient_function(p):
            return self._compute_gradient_implicit(p, mechanism, target_curve)
        
        try:
            # Run BFGS optimization
            result = minimize(
                objective_function,
                p0,
                method='BFGS',
                jac=gradient_function,
                options={
                    'maxiter': self.max_iterations,
                    'gtol': self.tolerance,
                    'disp': False
                }
            )
            
            # Create detailed result
            optimization_result = OptimizationResult(
                success=result.success,
                optimized_parameters=result.x,
                final_error=result.fun,
                iterations=result.nit,
                convergence_history=self.convergence_history,
                gradient_evaluations=self.gradient_evaluations,
                implicit_gradient_time=np.sum(self.implicit_gradient_times),
                metadata={
                    'message': result.message,
                    'function_evaluations': result.nfev,
                    'average_gradient_time': np.mean(self.implicit_gradient_times) if self.implicit_gradient_times else 0,
                    'optimization_method': 'BFGS',
                    'implicit_theorem_used': True
                }
            )
            
            if result.success:
                self.logger.info(f"Optimization converged in {result.nit} iterations "
                               f"(final error: {result.fun:.2e})")
            else:
                self.logger.warning(f"Optimization failed: {result.message}")
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Optimization failed with exception: {e}")
            return OptimizationResult(
                success=False,
                optimized_parameters=p0,
                final_error=float('inf'),
                iterations=0,
                convergence_history=[],
                gradient_evaluations=0,
                implicit_gradient_time=0.0,
                metadata={'error': str(e)}
            )
    
    def _compute_objective(self, p: np.ndarray, mechanism, target_curve: MotionCurve) -> float:
        """
        Compute objective function F(p) = ∫ ||x(p, s_t) - x_target_t||^2 dt.
        
        Args:
            p: Mechanism parameters
            mechanism: Mechanism with constraints and attachment point
            target_curve: Target motion curve
            
        Returns:
            Objective function value (squared error)
        """
        total_error = 0.0
        
        # Generate time steps for integration
        t_values = np.linspace(0, 2 * np.pi, self.time_steps)
        
        for i, t in enumerate(t_values):
            try:
                # 1. Solve for state s_t at current time/phase
                constraints = mechanism.get_constraints_at_time(t, p)
                initial_state = mechanism.get_initial_state_guess()
                
                # Use explicit Newton-Raphson solver
                solver = NewtonRaphsonExplicitSolver()
                s_t = solver.solve_state_at_time(constraints, initial_state, t)
                
                # 2. Get attachment point position x(p, s_t)
                marker_pos = mechanism.get_attachment_point(s_t, p)
                
                # 3. Get target position at this time
                target_pos = target_curve.get_position_at_time(t)
                
                # 4. Compute squared error
                error = np.linalg.norm(marker_pos - target_pos)**2
                total_error += error
                
            except Exception as e:
                self.logger.warning(f"Error at time step {i}: {e}")
                # Penalize heavily for simulation failures
                total_error += 1e6
        
        # Average over time steps
        avg_error = total_error / self.time_steps
        self.convergence_history.append(avg_error)
        
        return avg_error
    
    def _compute_gradient_implicit(self, p: np.ndarray, mechanism, 
                                 target_curve: MotionCurve) -> np.ndarray:
        """
        Compute gradient using Implicit Function Theorem.
        
        CRITICAL IMPLEMENTATION from PAPER_IMPL.md Section 2.2:
        
        Since C(p, s_t(p)) = 0, we have:
        ∂s_t/∂p = -(∂C/∂s_t)^-1(∂C/∂p)
        
        Then: ∂F/∂p = ∂F/∂x * (∂x/∂s * ∂s/∂p + ∂x/∂p)
        
        Args:
            p: Current mechanism parameters
            mechanism: Mechanism object
            target_curve: Target motion curve
            
        Returns:
            Gradient vector ∂F/∂p
        """
        import time
        start_time = time.time()
        
        self.gradient_evaluations += 1
        
        total_gradient = np.zeros_like(p)
        t_values = np.linspace(0, 2 * np.pi, self.time_steps)
        
        for i, t in enumerate(t_values):
            try:
                # 1. Solve for state s_t at current parameters and time
                constraints = mechanism.get_constraints_at_time(t, p)
                initial_state = mechanism.get_initial_state_guess()
                
                solver = NewtonRaphsonExplicitSolver()
                s_t = solver.solve_state_at_time(constraints, initial_state, t)
                
                # 2. Compute constraint Jacobians for Implicit Function Theorem
                # ∂C/∂s_t (constraint Jacobian w.r.t. state)
                dC_ds = self._compute_constraint_jacobian_state(constraints, s_t)
                
                # ∂C/∂p (constraint Jacobian w.r.t. parameters) - cheap finite differences
                dC_dp = self._compute_constraint_jacobian_params(constraints, s_t, p, mechanism, t)
                
                # 3. Apply Implicit Function Theorem: ∂s_t/∂p = -(∂C/∂s_t)^-1(∂C/∂p)
                try:
                    dC_ds_inv = np.linalg.pinv(dC_ds)  # Moore-Penrose for rank deficiency
                    ds_dp = -dC_ds_inv @ dC_dp
                except np.linalg.LinAlgError:
                    self.logger.warning(f"Singular constraint Jacobian at time {t}")
                    ds_dp = np.zeros((len(s_t), len(p)))
                
                # 4. Compute attachment point Jacobians
                marker_pos = mechanism.get_attachment_point(s_t, p)
                target_pos = target_curve.get_position_at_time(t)
                error = marker_pos - target_pos
                
                # ∂x/∂s (attachment point Jacobian w.r.t. state)
                dx_ds = mechanism.get_attachment_point_jacobian_state(s_t, p)
                
                # ∂x/∂p (attachment point Jacobian w.r.t. parameters)
                dx_dp = mechanism.get_attachment_point_jacobian_params(s_t, p)
                
                # 5. Apply chain rule: ∂F/∂p = ∂F/∂x * (∂x/∂s * ∂s/∂p + ∂x/∂p)
                # ∂F/∂x = 2 * error (derivative of squared error)
                dF_dx = 2 * error
                
                # Chain rule application
                gradient_at_t = dF_dx @ (dx_ds @ ds_dp + dx_dp)
                total_gradient += gradient_at_t
                
            except Exception as e:
                self.logger.warning(f"Gradient computation error at time step {i}: {e}")
                # Skip this time step
                continue
        
        # Average gradient over time steps
        avg_gradient = total_gradient / self.time_steps
        
        # Record timing
        gradient_time = time.time() - start_time
        self.implicit_gradient_times.append(gradient_time)
        
        self.logger.debug(f"Gradient computation took {gradient_time:.3f}s "
                         f"(avg: {np.mean(self.implicit_gradient_times):.3f}s)")
        
        return avg_gradient
    
    def _compute_constraint_jacobian_state(self, constraints: List[BaseConstraint], 
                                         state: np.ndarray) -> np.ndarray:
        """
        Compute ∂C/∂s analytically.
        
        Args:
            constraints: List of constraints
            state: Current state vector
            
        Returns:
            Constraint Jacobian matrix [n_constraints x n_state]
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
                self.logger.error(f"Error computing constraint gradient: {e}")
                raise
        
        if not jacobian_rows:
            return np.zeros((0, len(state)))
        
        return np.vstack(jacobian_rows)
    
    def _compute_constraint_jacobian_params(self, constraints: List[BaseConstraint],
                                          state: np.ndarray, params: np.ndarray,
                                          mechanism, time: float) -> np.ndarray:
        """
        Compute ∂C/∂p using efficient finite differences.
        
        This is cheap because it doesn't require re-solving the constraint system.
        
        Args:
            constraints: List of constraints
            state: Current state vector (fixed)
            params: Current parameters
            mechanism: Mechanism object
            time: Current time
            
        Returns:
            Parameter Jacobian matrix [n_constraints x n_params]
        """
        epsilon = 1e-8
        n_constraints = sum(len(c.evaluate(state)) for c in constraints if c.enabled)
        n_params = len(params)
        
        jacobian = np.zeros((n_constraints, n_params))
        
        # Evaluate constraints at current parameters
        C_base = self._evaluate_all_constraints(constraints, state)
        
        # Finite differences for each parameter
        for i in range(n_params):
            params_plus = params.copy()
            params_plus[i] += epsilon
            
            # Update constraints with new parameters
            constraints_plus = mechanism.get_constraints_at_time(time, params_plus)
            C_plus = self._evaluate_all_constraints(constraints_plus, state)
            
            # Finite difference
            jacobian[:, i] = (C_plus - C_base) / epsilon
        
        return jacobian
    
    def _evaluate_all_constraints(self, constraints: List[BaseConstraint], 
                                state: np.ndarray) -> np.ndarray:
        """Evaluate all constraints and concatenate results."""
        constraint_values = []
        
        for constraint in constraints:
            if not constraint.enabled:
                continue
            value = constraint.evaluate(state)
            if isinstance(value, np.ndarray):
                constraint_values.extend(value.flatten())
            else:
                constraint_values.append(float(value))
        
        return np.array(constraint_values)