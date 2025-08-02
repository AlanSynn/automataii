"""
Constraint and Solver Framework

Unified constraint satisfaction system implementing the paper's vision of
constraint-based assembly simulation and optimization.

Based on PAPER_IMPL.md Section 3: Constraint-Based Assembly Simulation
"""

from .base import BaseConstraint, BaseSolver, ConstraintViolationError
from .solvers import FABRIKSolver, NewtonRaphsonSolver, BFGSSolver
from .constraints import (
    IKConstraint,
    LayerConstraint,
    CollisionConstraint,
    GearMeshingConstraint,
    PositionConstraint,
    DistanceConstraint
)

__all__ = [
    # Base interfaces
    'BaseConstraint', 
    'BaseSolver', 
    'ConstraintViolationError',
    
    # Solvers
    'FABRIKSolver',
    'NewtonRaphsonSolver', 
    'BFGSSolver',
    
    # Constraints
    'IKConstraint',
    'LayerConstraint',
    'CollisionConstraint', 
    'GearMeshingConstraint',
    'PositionConstraint',
    'DistanceConstraint'
]