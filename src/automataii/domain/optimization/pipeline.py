"""
Optimization Pipeline

Implements the Builder/Director pattern for complex multi-stage optimizations
as described in PAPER_IMPL.md Section 4.
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np

from automataii.domain.constraints.base import BaseConstraint, BaseSolver, ConstraintManager
from automataii.domain.constraints.solvers import BFGSSolver, NewtonRaphsonSolver


class OptimizationStage(Enum):
    """Stages in the optimization pipeline."""
    INITIALIZATION = "initialization"
    COARSE_SEARCH = "coarse_search"
    FINE_TUNING = "fine_tuning"
    VALIDATION = "validation"
    FINALIZATION = "finalization"


@dataclass
class OptimizationResult:
    """Result of an optimization run."""
    success: bool
    final_parameters: np.ndarray
    final_error: float
    iterations: int
    stage_results: Dict[OptimizationStage, Any]
    metadata: Dict[str, Any]


class OptimizationPipeline:
    """
    Multi-stage optimization pipeline.
    
    Implements the Builder/Director pattern to coordinate complex optimizations
    that require multiple solvers and stages.
    
    Based on PAPER_IMPL.md Section 4:
    1. Coarse Search: Database lookup for initial parameters
    2. Fine Tuning: BFGS optimization with implicit gradients
    3. Validation: Constraint checking and verification
    """
    
    def __init__(self, name: str = "OptimizationPipeline"):
        """
        Initialize optimization pipeline.
        
        Args:
            name: Pipeline name for logging
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # Pipeline configuration
        self.stages: List[OptimizationStage] = []
        self.stage_configs: Dict[OptimizationStage, Dict[str, Any]] = {}
        self.stage_solvers: Dict[OptimizationStage, BaseSolver] = {}
        
        # Constraint management
        self.constraint_manager = ConstraintManager()
        
        # Results tracking
        self.results_history: List[OptimizationResult] = []
        self.current_parameters: Optional[np.ndarray] = None
        
        # Callbacks
        self.stage_callbacks: Dict[OptimizationStage, List[Callable]] = {}
        self.progress_callback: Optional[Callable[[str, float], None]] = None
    
    def add_stage(self, stage: OptimizationStage, solver: BaseSolver, 
                  config: Optional[Dict[str, Any]] = None):
        """
        Add an optimization stage to the pipeline.
        
        Args:
            stage: Stage type
            solver: Solver to use for this stage
            config: Stage-specific configuration
        """
        if stage not in self.stages:
            self.stages.append(stage)
        
        self.stage_solvers[stage] = solver
        self.stage_configs[stage] = config or {}
        
        self.logger.debug(f"Added stage {stage.value} with solver {solver.name}")
    
    def add_constraint(self, constraint: BaseConstraint):
        """Add a constraint to the optimization problem."""
        self.constraint_manager.add_constraint(constraint)
    
    def add_solver(self, solver: BaseSolver, set_as_default: bool = False):
        """Add a solver to the constraint manager."""
        self.constraint_manager.add_solver(solver, set_as_default)
    
    def add_stage_callback(self, stage: OptimizationStage, callback: Callable):
        """Add a callback function for a specific stage."""
        if stage not in self.stage_callbacks:
            self.stage_callbacks[stage] = []
        self.stage_callbacks[stage].append(callback)
    
    def set_progress_callback(self, callback: Callable[[str, float], None]):
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    def optimize(self, initial_parameters: np.ndarray, **kwargs) -> OptimizationResult:
        """
        Run the complete optimization pipeline.
        
        Args:
            initial_parameters: Starting parameter values
            **kwargs: Additional optimization parameters
            
        Returns:
            OptimizationResult with final parameters and metadata
        """
        self.logger.info(f"Starting optimization pipeline with {len(self.stages)} stages")
        
        # Initialize result
        result = OptimizationResult(
            success=False,
            final_parameters=initial_parameters.copy(),
            final_error=float('inf'),
            iterations=0,
            stage_results={},
            metadata=kwargs.copy()
        )
        
        current_params = initial_parameters.copy()
        total_iterations = 0
        
        try:
            # Execute each stage in sequence
            for i, stage in enumerate(self.stages):
                stage_progress = i / len(self.stages)
                
                if self.progress_callback:
                    self.progress_callback(f"Stage: {stage.value}", stage_progress)
                
                self.logger.info(f"Executing stage {stage.value}")
                
                # Run stage callbacks (pre-stage)
                for callback in self.stage_callbacks.get(stage, []):
                    callback(stage, current_params, "pre")
                
                # Execute stage
                stage_result = self._execute_stage(stage, current_params, **kwargs)
                result.stage_results[stage] = stage_result
                
                # Update parameters if stage was successful
                if stage_result.get('success', False):
                    current_params = stage_result['parameters']
                    total_iterations += stage_result.get('iterations', 0)
                    
                    self.logger.info(f"Stage {stage.value} completed successfully "
                                   f"(error: {stage_result.get('error', 'N/A')})")
                else:
                    self.logger.warning(f"Stage {stage.value} failed: {stage_result.get('error', 'Unknown')}")
                    
                    # Decide whether to continue or abort
                    if stage_result.get('critical', False):
                        break
                
                # Run stage callbacks (post-stage)
                for callback in self.stage_callbacks.get(stage, []):
                    callback(stage, current_params, "post")
        
        except Exception as e:
            self.logger.error(f"Optimization pipeline failed: {e}")
            result.metadata['error'] = str(e)
            return result
        
        # Finalize result
        result.final_parameters = current_params
        result.iterations = total_iterations
        result.success = self._validate_final_result(current_params, **kwargs)
        
        if result.success:
            result.final_error = self._compute_final_error(current_params, **kwargs)
        
        self.results_history.append(result)
        self.current_parameters = current_params
        
        if self.progress_callback:
            self.progress_callback("Optimization complete", 1.0)
        
        self.logger.info(f"Optimization pipeline completed (success: {result.success})")
        return result
    
    def _execute_stage(self, stage: OptimizationStage, parameters: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Execute a specific optimization stage."""
        solver = self.stage_solvers.get(stage)
        config = self.stage_configs.get(stage, {})
        
        if solver is None:
            return {'success': False, 'error': f'No solver for stage {stage.value}'}
        
        try:
            if stage == OptimizationStage.INITIALIZATION:
                return self._execute_initialization(parameters, solver, config, **kwargs)
            
            elif stage == OptimizationStage.COARSE_SEARCH:
                return self._execute_coarse_search(parameters, solver, config, **kwargs)
            
            elif stage == OptimizationStage.FINE_TUNING:
                return self._execute_fine_tuning(parameters, solver, config, **kwargs)
            
            elif stage == OptimizationStage.VALIDATION:
                return self._execute_validation(parameters, solver, config, **kwargs)
            
            elif stage == OptimizationStage.FINALIZATION:
                return self._execute_finalization(parameters, solver, config, **kwargs)
            
            else:
                return {'success': False, 'error': f'Unknown stage: {stage.value}'}
                
        except Exception as e:
            self.logger.error(f"Stage {stage.value} execution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_initialization(self, parameters: np.ndarray, solver: BaseSolver, 
                               config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute initialization stage."""
        # Validate initial parameters
        if len(parameters) == 0:
            return {'success': False, 'error': 'Empty initial parameters'}
        
        # Check parameter bounds
        bounds = config.get('bounds')
        if bounds:
            for i, (min_val, max_val) in enumerate(bounds):
                if i < len(parameters):
                    parameters[i] = np.clip(parameters[i], min_val, max_val)
        
        # Add noise for better exploration if requested
        noise_scale = config.get('noise_scale', 0.0)
        if noise_scale > 0:
            noise = np.random.normal(0, noise_scale, len(parameters))
            parameters = parameters + noise
        
        return {
            'success': True,
            'parameters': parameters,
            'iterations': 0,
            'error': 0.0
        }
    
    def _execute_coarse_search(self, parameters: np.ndarray, solver: BaseSolver,
                              config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute coarse search stage (database lookup)."""
        # This would typically involve searching a precomputed database
        # For now, we'll use the current parameters as a starting point
        
        database = config.get('database')
        search_radius = config.get('search_radius', 0.1)
        
        if database is None:
            # No database available, keep current parameters
            return {
                'success': True,
                'parameters': parameters,
                'iterations': 0,
                'error': 0.0,
                'found_in_database': False
            }
        
        # TODO: Implement actual database search
        # For now, return current parameters
        return {
            'success': True,
            'parameters': parameters,
            'iterations': 1,
            'error': 0.0,
            'found_in_database': False
        }
    
    def _execute_fine_tuning(self, parameters: np.ndarray, solver: BaseSolver,
                            config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute fine-tuning stage using constraint optimization."""
        try:
            # Use constraint manager to solve optimization problem
            constraints = [c for c in self.constraint_manager.constraints if c.enabled]
            
            if not constraints:
                # No constraints, just return current parameters
                return {
                    'success': True,
                    'parameters': parameters,
                    'iterations': 0,
                    'error': 0.0
                }
            
            # Execute optimization with the specified solver
            optimized_params = solver.solve(constraints, parameters, **config, **kwargs)
            
            # Calculate final error
            error = self._compute_constraint_error(optimized_params)
            
            return {
                'success': True,
                'parameters': optimized_params,
                'iterations': solver.last_iterations,
                'error': error
            }
            
        except Exception as e:
            self.logger.error(f"Fine-tuning failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'parameters': parameters,  # Return original on failure
                'iterations': 0
            }
    
    def _execute_validation(self, parameters: np.ndarray, solver: BaseSolver,
                           config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute validation stage."""
        tolerance = config.get('tolerance', 1e-3)
        
        # Check all constraints
        violations = self.constraint_manager.check_all_constraints(parameters, tolerance)
        
        max_violation = max(violations.values()) if violations else 0.0
        is_valid = max_violation <= tolerance
        
        return {
            'success': is_valid,
            'parameters': parameters,
            'iterations': 0,
            'error': max_violation,
            'violations': violations
        }
    
    def _execute_finalization(self, parameters: np.ndarray, solver: BaseSolver,
                             config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute finalization stage."""
        # Apply any final parameter adjustments
        final_params = parameters.copy()
        
        # Round discrete parameters if specified
        discrete_indices = config.get('discrete_indices', [])
        for i in discrete_indices:
            if i < len(final_params):
                final_params[i] = round(final_params[i])
        
        # Apply final bounds
        bounds = config.get('bounds')
        if bounds:
            for i, (min_val, max_val) in enumerate(bounds):
                if i < len(final_params):
                    final_params[i] = np.clip(final_params[i], min_val, max_val)
        
        return {
            'success': True,
            'parameters': final_params,
            'iterations': 0,
            'error': 0.0
        }
    
    def _validate_final_result(self, parameters: np.ndarray, **kwargs) -> bool:
        """Validate the final optimization result."""
        # Check if any constraints are violated
        tolerance = kwargs.get('final_tolerance', 1e-3)
        violations = self.constraint_manager.check_all_constraints(parameters, tolerance)
        
        max_violation = max(violations.values()) if violations else 0.0
        return max_violation <= tolerance
    
    def _compute_final_error(self, parameters: np.ndarray, **kwargs) -> float:
        """Compute the final optimization error."""
        return self._compute_constraint_error(parameters)
    
    def _compute_constraint_error(self, parameters: np.ndarray) -> float:
        """Compute total constraint violation magnitude."""
        total_error = 0.0
        
        for constraint in self.constraint_manager.constraints:
            if constraint.enabled:
                violation = constraint.evaluate(parameters)
                error = np.linalg.norm(violation) * constraint.weight
                total_error += error
        
        return total_error
    
    def get_optimization_history(self) -> List[OptimizationResult]:
        """Get the history of optimization results."""
        return self.results_history.copy()
    
    def get_current_parameters(self) -> Optional[np.ndarray]:
        """Get the current best parameters."""
        return self.current_parameters.copy() if self.current_parameters is not None else None
    
    def clear_history(self):
        """Clear optimization history."""
        self.results_history.clear()
        self.current_parameters = None
    
    def create_standard_pipeline(self, use_database: bool = True) -> 'OptimizationPipeline':
        """
        Create a standard optimization pipeline configuration.
        
        Args:
            use_database: Whether to include database search stage
            
        Returns:
            Configured pipeline ready for use
        """
        # Add standard stages
        self.add_stage(OptimizationStage.INITIALIZATION, NewtonRaphsonSolver("init"))
        
        if use_database:
            self.add_stage(OptimizationStage.COARSE_SEARCH, NewtonRaphsonSolver("coarse"))
        
        self.add_stage(OptimizationStage.FINE_TUNING, BFGSSolver())
        self.add_stage(OptimizationStage.VALIDATION, NewtonRaphsonSolver("validation"))
        self.add_stage(OptimizationStage.FINALIZATION, NewtonRaphsonSolver("final"))
        
        return self