"""Base abstraction for linkage validation strategies.

Lines: ~75
Public API: LinkageValidator (ABC)
Deps In: 0 (validators implement this)
Deps Out: 1 (core.types)
Coupling: Low (ABC only)
Cohesion: Feature (validator contract)
Owner: Alan Synn
Last Updated: 2025-11-14
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automataii.mechanisms.core.types import SafetyStatus


class LinkageValidator(ABC):
    """Abstract base class for linkage validation strategies.

    Each linkage type implements type-specific validation rules:
    - Four-bar: Grashof condition, transmission angle
    - Five-bar: Workspace bounds, singularity detection
    - Six-bar: Configuration-specific rules (Stephenson/Watt)

    Validator pattern enables:
    - Type-specific safety/quality checks
    - Independent validation logic per linkage type
    - Easy extension of validation rules
    """

    @abstractmethod
    def validate_safety(
        self,
        parameters: dict[str, float],
        positions: dict[str, tuple[float, float]],
        input_angle: float,
    ) -> SafetyStatus:
        """Evaluate safety and configuration quality.

        Args:
            parameters: Mechanism parameters (link lengths, etc.)
            positions: Joint positions from strategy computation
            input_angle: Current input angle in degrees

        Returns:
            SafetyStatus with level (SAFE/WARNING/DANGER) and message

        Notes:
            - Should check geometric constraints (reachability, interference)
            - Should evaluate mechanical quality (transmission, singularities)
            - Should provide actionable feedback in message
        """
        ...

    @property
    @abstractmethod
    def bar_count(self) -> int:
        """Number of bars this validator applies to.

        Returns:
            Integer bar count (3, 4, 5, 6, etc.)
        """
        ...
