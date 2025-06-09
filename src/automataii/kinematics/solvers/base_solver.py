"""Base class for IK solvers."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from PyQt6.QtCore import QPointF


@dataclass
class IKSolution:
    """Result of an IK solve operation."""
    success: bool
    joint_positions: Dict[str, QPointF]
    joint_angles: Dict[str, float]
    error: Optional[str] = None
    iterations: int = 0
    residual: float = 0.0


class BaseSolver(ABC):
    """Abstract base class for IK solvers.
    
    All IK solvers should inherit from this class and implement
    the solve method.
    """
    
    def __init__(self, tolerance: float = 0.01, max_iterations: int = 100):
        """Initialize solver.
        
        Args:
            tolerance: Position tolerance for convergence
            max_iterations: Maximum iterations before giving up
        """
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self._last_solution: Optional[IKSolution] = None
        
        logging.debug(f"{self.__class__.__name__} initialized")
    
    @abstractmethod
    def solve(self, 
              target: QPointF,
              joint_positions: Dict[str, QPointF],
              constraints: Dict[str, Any]) -> IKSolution:
        """Solve IK for given target and constraints.
        
        Args:
            target: Target position for end effector
            joint_positions: Current joint positions
            constraints: Solver-specific constraints
            
        Returns:
            IKSolution with results
        """
        pass
    
    @abstractmethod
    def validate_input(self, 
                      target: QPointF,
                      joint_positions: Dict[str, QPointF],
                      constraints: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input parameters.
        
        Args:
            target: Target position
            joint_positions: Joint positions
            constraints: Constraints
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @property
    def last_solution(self) -> Optional[IKSolution]:
        """Get the last computed solution."""
        return self._last_solution
    
    def reset(self) -> None:
        """Reset solver state."""
        self._last_solution = None
    
    @staticmethod
    def distance(p1: QPointF, p2: QPointF) -> float:
        """Calculate distance between two points."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        return (dx * dx + dy * dy) ** 0.5
    
    @staticmethod
    def angle_between(p1: QPointF, p2: QPointF) -> float:
        """Calculate angle from p1 to p2 in degrees."""
        import math
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        return math.degrees(math.atan2(dy, dx))
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        """Normalize angle to [-180, 180] range."""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle