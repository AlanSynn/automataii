# src/automataii/domain/kinematics/interfaces/solver_protocol.py

from typing import Protocol, Tuple, List


class IKSolverProtocol(Protocol):
    """
    Protocol for inverse kinematics solvers.

    This defines the interface that all IK solvers must implement.
    """

    def solve(self, chain: "IKChain", target: Tuple[float, float]) -> List[Tuple[float, float]]:
        """
        Solve inverse kinematics for a chain to reach a target position.

        Args:
            chain: The kinematic chain to solve
            target: The target position to reach as (x, y) tuple

        Returns:
            List of joint positions after solving as (x, y) tuples
        """
        ...

    def set_constraints(self, joint_limits: dict) -> None:
        """
        Set joint angle constraints for the solver.

        Args:
            joint_limits: Dictionary mapping joint names to (min_angle, max_angle) tuples
        """
        ...

    def get_error(self) -> float:
        """
        Get the current error/residual of the solver.

        Returns:
            Error value (lower is better)
        """
        ...
