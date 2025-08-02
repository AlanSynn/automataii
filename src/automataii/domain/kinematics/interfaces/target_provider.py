# src/automataii/domain/kinematics/interfaces/target_provider.py

from typing import Protocol, Tuple


class MechanismTargetProvider(Protocol):
    """
    Protocol for objects that can provide mechanism targets.

    This allows the kinematics system to get targets from mechanism tabs
    without creating circular dependencies.
    """

    def get_mechanism_targets(self, progress: float) -> dict[str, Tuple[float, float]]:
        """
        Get mechanism targets for the given animation progress.

        Args:
            progress: Animation progress from 0.0 to 1.0

        Returns:
            Dictionary mapping effector IDs to target positions as (x, y) tuples
        """
        ...
