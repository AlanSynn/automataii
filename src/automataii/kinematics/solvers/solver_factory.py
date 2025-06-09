"""Factory for creating IK solvers."""

import logging
from typing import Dict, Any, Optional, List

from ..core import SolverType
from .base_solver import BaseSolver
from .single_bone_solver import SingleBoneSolver
from .two_bone_solver import TwoBoneSolver


class SolverFactory:
    """Factory class for creating IK solver instances."""
    
    # Registry of available solvers
    _solvers: Dict[SolverType, type] = {
        SolverType.SINGLE_BONE: SingleBoneSolver,
        SolverType.TWO_BONE: TwoBoneSolver,
    }
    
    @classmethod
    def create_solver(cls, 
                     solver_type: SolverType,
                     config: Optional[Dict[str, Any]] = None) -> BaseSolver:
        """Create a solver instance.
        
        Args:
            solver_type: Type of solver to create
            config: Optional configuration for solver
            
        Returns:
            Solver instance
            
        Raises:
            ValueError: If solver type is not supported
        """
        if solver_type not in cls._solvers:
            raise ValueError(f"Unsupported solver type: {solver_type}")
        
        solver_class = cls._solvers[solver_type]
        
        # Extract common config
        config = config or {}
        tolerance = config.get('tolerance', 0.01)
        max_iterations = config.get('max_iterations', 100)
        
        # Create solver
        solver = solver_class(tolerance=tolerance, max_iterations=max_iterations)
        
        logging.info(f"Created {solver_type.value} solver")
        
        return solver
    
    @classmethod
    def register_solver(cls, solver_type: SolverType, solver_class: type) -> None:
        """Register a custom solver.
        
        Args:
            solver_type: Type identifier for the solver
            solver_class: Solver class (must inherit from BaseSolver)
        """
        if not issubclass(solver_class, BaseSolver):
            raise TypeError(f"{solver_class} must inherit from BaseSolver")
        
        cls._solvers[solver_type] = solver_class
        logging.info(f"Registered custom solver: {solver_type.value}")
    
    @classmethod
    def get_available_solvers(cls) -> List[SolverType]:
        """Get list of available solver types."""
        return list(cls._solvers.keys())