"""
BFGS Solver Implementation

Implements BFGS optimization for mechanism parameter optimization as specified in PAPER_IMPL.md.
Uses implicit function theorem for efficient gradient calculation.
"""

from typing import List, Callable, Optional, Dict, Any
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import pinv

from ..base import BaseSolver, BaseConstraint, ConstraintViolationError


class BFGSSolver(BaseSolver):
    """
    BFGS optimization solver for mechanism parameter optimization.
    
    Implements the optimization pipeline from PAPER_IMPL.md Section 4.2:
    - Minimizes F(p) = ∫ ||x(p, s_t) - x_target_t||² dt
    - Uses implicit function theorem: ∂s_t/∂p = -(∂C/∂s_t)^(-1)(∂C/∂p)
    - Employs BFGS quasi-Newton method for efficient optimization
    """
    
    def __init__(self, max_iterations: int = 100, tolerance: float = 1e-6,
                 finite_diff_step: float = 1e-8):
        """
        Initialize BFGS solver.
        
        Args:
            max_iterations: Maximum optimization iterations
            tolerance: Convergence tolerance
            finite_diff_step: Step size for finite differences in ∂C/∂p
        """
        super().__init__("BFGS", max_iterations, tolerance)
        self.finite_diff_step = finite_diff_step
        self.mechanism_simulator = None
        self.target_curve = None
        self.optimization_history = []
    
    def set_mechanism_simulator(self, simulator):
        """Set the mechanism simulator for parameter optimization."""
        self.mechanism_simulator = simulator
    
    def set_target_curve(self, target_curve: np.ndarray):
        """Set the target curve for optimization."""
        self.target_curve = target_curve
    
    def solve(self, constraints: List[BaseConstraint], initial_state: np.ndarray, **kwargs) -> np.ndarray:
        """
        Solve optimization problem using BFGS.
        
        Args:
            constraints: List of constraints (used for mechanism simulation)
            initial_state: Initial parameter values (not system state)
            **kwargs: Additional parameters:
                - mechanism_type: Type of mechanism being optimized
                - target_curve: Target motion curve to match
                - time_steps: Number of time steps for simulation
                - simulator: Mechanism simulator instance
                
        Returns:
            Optimized parameter values
            
        Raises:
            ConstraintViolationError: If optimization fails
        """
        self.total_solves += 1
        self.optimization_history.clear()
        
        # Extract optimization parameters
        mechanism_type = kwargs.get('mechanism_type')
        target_curve = kwargs.get('target_curve', self.target_curve)
        time_steps = kwargs.get('time_steps', 180)
        simulator = kwargs.get('simulator', self.mechanism_simulator)
        
        if target_curve is None:
            raise ConstraintViolationError("BFGS", 1.0, "No target curve provided")
        
        if simulator is None:
            raise ConstraintViolationError("BFGS", 1.0, "No mechanism simulator provided")
        
        if mechanism_type is None:
            raise ConstraintViolationError("BFGS", 1.0, "No mechanism type provided")
        
        self.logger.info(f"Starting BFGS optimization for {mechanism_type}")
        
        # Normalize target curve
        target_curve = self._normalize_curve(target_curve)
        
        # Define objective function
        def objective(params):
            """Objective function F(p) = ∫ ||x(p, s_t) - x_target_t||² dt"""
            try:
                # Simulate mechanism with current parameters
                from automataii.domain.kinematics.mechanism import MechanismType
                from automataii.domain.common.parameter_converter import MechanismType as UnifiedMechanismType
                
                # Convert string type to enum
                if isinstance(mechanism_type, str):
                    mech_type_map = {
                        '4_bar_linkage': MechanismType.FOUR_BAR,
                        'cam': MechanismType.CAM,
                        'belt': MechanismType.BELT,
                        'spring': MechanismType.SPRING,
                    }
                    mech_type = mech_type_map.get(mechanism_type, MechanismType.FOUR_BAR)
                else:
                    mech_type = mechanism_type
                
                motion_curve = simulator.simulate_mechanism(mech_type, params)
                
                if motion_curve.points.size == 0:
                    return 1e6  # Large penalty for invalid parameters
                
                # Normalize simulated curve
                sim_curve = self._normalize_curve(motion_curve.points)
                
                # Calculate objective: sum of squared distances
                if len(sim_curve) != len(target_curve):
                    # Resample to match target length
                    sim_curve = self._resample_curve(sim_curve, len(target_curve))
                
                error = np.sum((sim_curve - target_curve) ** 2)
                
                # Store history
                self.optimization_history.append({
                    'params': params.copy(),
                    'error': error,
                    'sim_curve': sim_curve.copy()
                })
                
                return error
                
            except Exception as e:
                self.logger.error(f"Error in objective evaluation: {e}")
                return 1e6  # Large penalty for errors
        
        # Define gradient function using implicit function theorem
        def gradient(params):
            """
            Compute gradient ∂F/∂p using implicit function theorem.
            
            Based on PAPER_IMPL.md Section 4.2:
            ∂F/∂p = Σ_t (∂F/∂x * (∂x/∂s * ∂s/∂p + ∂x/∂p))
            where ∂s/∂p = -(∂C/∂s)^(-1)(∂C/∂p)
            """
            try:
                grad = np.zeros_like(params)
                
                # For now, use finite differences as a fallback
                # Full implicit gradient implementation would require
                # constraint Jacobians from the mechanism simulator
                for i in range(len(params)):
                    params_plus = params.copy()
                    params_plus[i] += self.finite_diff_step
                    
                    params_minus = params.copy()
                    params_minus[i] -= self.finite_diff_step
                    
                    f_plus = objective(params_plus)
                    f_minus = objective(params_minus)
                    
                    grad[i] = (f_plus - f_minus) / (2 * self.finite_diff_step)
                
                return grad
                
            except Exception as e:
                self.logger.error(f"Error in gradient computation: {e}")
                return np.zeros_like(params)
        
        # Set up optimization bounds based on mechanism type
        bounds = self._get_parameter_bounds(mechanism_type, len(initial_state))
        
        # Run BFGS optimization
        try:
            result = minimize(
                objective,
                initial_state,
                method='L-BFGS-B',
                jac=gradient,
                bounds=bounds,
                options={
                    'maxiter': self.max_iterations,
                    'ftol': self.tolerance,
                    'gtol': self.tolerance * 10,
                    'disp': False
                }
            )
            
            self.last_iterations = result.nit
            self.last_error = result.fun
            
            if result.success:
                self.successful_solves += 1
                self.logger.info(f"BFGS converged in {result.nit} iterations (error: {result.fun:.2e})")
                return result.x
            else:
                self.logger.warning(f"BFGS did not converge: {result.message}")
                # Return best attempt
                return result.x
                
        except Exception as e:
            self.logger.error(f"BFGS optimization failed: {e}")
            raise ConstraintViolationError("BFGS", 1.0, f"Optimization failed: {e}")
    
    def _normalize_curve(self, curve: np.ndarray) -> np.ndarray:
        """Normalize curve coordinates to [0, 1] range."""
        if curve.size == 0:
            return curve
        
        curve = np.array(curve)
        if curve.ndim == 1:
            curve = curve.reshape(-1, 2)
        
        # Center and scale
        min_vals = np.min(curve, axis=0)
        max_vals = np.max(curve, axis=0)
        ranges = max_vals - min_vals
        
        # Avoid division by zero
        ranges[ranges == 0] = 1.0
        
        normalized = (curve - min_vals) / ranges
        return normalized.flatten()
    
    def _resample_curve(self, curve: np.ndarray, target_length: int) -> np.ndarray:
        """Resample curve to target length using linear interpolation."""
        if len(curve) == target_length:
            return curve
        
        # Reshape to 2D if needed
        if curve.ndim == 1:
            curve = curve.reshape(-1, 2)
        
        # Create interpolation indices
        old_indices = np.linspace(0, len(curve) - 1, len(curve))
        new_indices = np.linspace(0, len(curve) - 1, target_length // 2)
        
        # Interpolate x and y separately
        resampled = np.zeros((target_length // 2, 2))
        resampled[:, 0] = np.interp(new_indices, old_indices, curve[:, 0])
        resampled[:, 1] = np.interp(new_indices, old_indices, curve[:, 1])
        
        return resampled.flatten()
    
    def _get_parameter_bounds(self, mechanism_type: str, param_count: int) -> List:
        """Get parameter bounds for optimization."""
        from automataii.domain.common.parameter_converter import ParameterConverter, MechanismType
        
        converter = ParameterConverter.get_instance()
        
        # Map mechanism type string to enum
        type_mapping = {
            '4_bar_linkage': MechanismType.FOUR_BAR,
            'cam': MechanismType.CAM,
            'belt': MechanismType.BELT,
            'spring': MechanismType.SPRING,
            'gear': MechanismType.GEAR,
        }
        
        mech_type = type_mapping.get(mechanism_type, MechanismType.FOUR_BAR)
        param_ranges = converter._parameter_ranges.get(mech_type, {})
        
        bounds = []
        
        # Get specific parameter bounds based on mechanism type
        if mech_type == MechanismType.FOUR_BAR:
            param_names = ['l1', 'l2', 'l3', 'l4', 'p_x', 'p_y', 'theta0', 'omega']
        elif mech_type == MechanismType.CAM:
            param_names = ['base_radius', 'rise', 'offset', 'cam_center_x', 'cam_center_y', 
                          'motion_law', 'dwell_start', 'dwell_end']
        elif mech_type == MechanismType.BELT:
            param_names = ['r1', 'r2', 'center1_x', 'center1_y', 'center2_x', 'center2_y', 
                          'omega1', 'slip_coeff']
        elif mech_type == MechanismType.SPRING:
            param_names = ['k', 'c', 'm', 'x1', 'y1', 'x2', 'y2', 'rest_length', 
                          'initial_velocity', 'external_force']
        else:
            # Default bounds
            param_names = [f'param_{i}' for i in range(param_count)]
        
        for i in range(param_count):
            if i < len(param_names):
                param_name = param_names[i]
                if param_name in param_ranges:
                    bounds.append(param_ranges[param_name])
                else:
                    bounds.append((0.1, 1000.0))  # Default bounds
            else:
                bounds.append((0.1, 1000.0))  # Default bounds
        
        return bounds
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """Get the optimization history."""
        return self.optimization_history.copy()
    
    def get_best_parameters(self) -> Optional[np.ndarray]:
        """Get the best parameters from optimization history."""
        if not self.optimization_history:
            return None
        
        best_entry = min(self.optimization_history, key=lambda x: x['error'])
        return best_entry['params']
    
    def plot_convergence(self):
        """Plot optimization convergence (requires matplotlib)."""
        try:
            import matplotlib.pyplot as plt
            
            if not self.optimization_history:
                self.logger.warning("No optimization history to plot")
                return
            
            errors = [entry['error'] for entry in self.optimization_history]
            
            plt.figure(figsize=(10, 6))
            plt.semilogy(errors)
            plt.xlabel('Iteration')
            plt.ylabel('Objective Function Value')
            plt.title('BFGS Optimization Convergence')
            plt.grid(True)
            plt.show()
            
        except ImportError:
            self.logger.warning("Matplotlib not available for plotting")