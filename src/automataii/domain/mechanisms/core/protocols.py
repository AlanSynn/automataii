"""
Core protocols for mechanism domain logic and rendering

These protocols define the interface contract for all mechanism implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from automataii.mechanisms.core.state import MechanismState, RenderConfig


@runtime_checkable
class Mechanism(Protocol):
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


@runtime_checkable
class MechanismRenderer(Protocol):
    def render(
        self,
        state: MechanismState,
        scene: QGraphicsScene,
        config: RenderConfig,
    ) -> list[QGraphicsItem]: ...
