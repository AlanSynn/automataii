"""
Core protocols for mechanism domain logic.

These protocols define the interface contract for all mechanism implementations.

Architecture Note:
- This is DOMAIN layer - NO Qt dependencies allowed
- Rendering protocols belong in PRESENTATION layer
- Domain only defines computation contracts
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .state import MechanismState


@runtime_checkable
class Mechanism(Protocol):
    """Protocol for mechanism computation logic (Domain layer)."""

    @property
    def mechanism_type(self) -> str: ...

    @property
    def required_parameters(self) -> frozenset[str]: ...

    def compute_state(
        self,
        parameters: Mapping[str, float],
        input_angle: float,
    ) -> MechanismState: ...

    def validate_parameters(self, parameters: Mapping[str, float]) -> None: ...


# NOTE: MechanismRenderer protocol has been moved to presentation layer
# See: automataii.presentation.qt.mechanisms.protocols.MechanismRenderer
