"""
Core state dataclasses for mechanism computation results

These immutable dataclasses represent computed mechanism state at a point in time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor


class SafetyLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"


class ForceType(Enum):
    REACTION = "reaction"
    APPLIED = "applied"
    CONSTRAINT = "constraint"
    FRICTION = "friction"
    GRAVITY = "gravity"


@dataclass(frozen=True)
class SafetyStatus:
    level: SafetyLevel
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForceVector:
    position: QPointF
    magnitude: float
    angle: float
    force_type: ForceType
    label: str = ""
    color: QColor | None = None

    def __post_init__(self):
        if self.color is None:
            colors = {
                ForceType.REACTION: QColor(255, 69, 0, 200),
                ForceType.APPLIED: QColor(0, 123, 255, 200),
                ForceType.CONSTRAINT: QColor(255, 140, 0, 200),
                ForceType.FRICTION: QColor(128, 128, 128, 200),
                ForceType.GRAVITY: QColor(139, 69, 19, 200),
            }
            object.__setattr__(
                self, "color", colors.get(self.force_type, QColor(100, 100, 100, 200))
            )

    def to_components(self) -> tuple[float, float]:
        import math

        angle_rad = math.radians(self.angle)
        return (
            self.magnitude * math.cos(angle_rad),
            self.magnitude * math.sin(angle_rad),
        )


@dataclass(frozen=True)
class MechanismState:
    positions: dict[str, tuple[float, float]]
    velocities: dict[str, tuple[float, float]] | None = None
    forces: dict[str, ForceVector] | None = None
    safety_status: SafetyStatus = field(default_factory=lambda: SafetyStatus(SafetyLevel.SAFE))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderConfig:
    show_forces: bool = True
    show_safety_zones: bool = True
    show_labels: bool = True
    show_trails: bool = False
    color_scheme: str = "default"
    scale: float = 1.0
