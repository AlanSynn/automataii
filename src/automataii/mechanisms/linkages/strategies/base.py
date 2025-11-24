"""Base abstraction for linkage computation strategies.

Lines: ~80
Public API: LinkageStrategy (ABC)
Deps In: 0 (strategies implement this)
Deps Out: 1 (core.types)
Coupling: Low (ABC only)
Cohesion: Feature (strategy contract)
Owner: Alan Synn
Last Updated: 2025-11-14
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.mechanisms.core.types import ForceVector


class LinkageStrategy(ABC):
    """Abstract base class for linkage computation strategies.

    Each linkage type (3/4/5/6-bar) implements this interface to provide
    type-specific kinematics and dynamics computation.

    Strategy pattern enables:
    - Runtime selection based on bar_count
    - Independent implementation per linkage type
    - Easy addition of new linkage types (7-bar, etc.)
    """

    @abstractmethod
    def compute_positions(
        self,
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, tuple[float, float]]:
        """Compute joint positions for given input angle.

        Args:
            parameters: Mechanism-specific parameters (link lengths, etc.)
            input_angle: Input angle in degrees

        Returns:
            Dictionary mapping joint names to (x, y) positions in mm

        Raises:
            ValueError: If parameters are invalid or incomplete
        """
        ...

    @abstractmethod
    def compute_forces(
        self,
        positions: dict[str, tuple[float, float]],
        parameters: dict[str, float],
        input_angle: float,
    ) -> dict[str, ForceVector] | None:
        """Compute force vectors at joints.

        Args:
            positions: Joint positions from compute_positions()
            parameters: Mechanism parameters
            input_angle: Input angle in degrees

        Returns:
            Dictionary mapping force IDs to ForceVector objects, or None if N/A
        """
        ...

    @abstractmethod
    def required_parameters(self) -> frozenset[str]:
        """Return set of required parameter names for this strategy.

        Returns:
            Frozenset of parameter names (e.g., {'ground_link', 'input_link', ...})
        """
        ...

    @property
    @abstractmethod
    def bar_count(self) -> int:
        """Number of bars in this linkage type.

        Returns:
            Integer bar count (3, 4, 5, 6, etc.)
        """
        ...
