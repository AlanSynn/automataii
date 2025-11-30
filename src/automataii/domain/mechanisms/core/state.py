"""
Core state dataclasses for mechanism computation results

These immutable dataclasses represent computed mechanism state at a point in time.

Architecture Note:
- This is DOMAIN layer - NO Qt dependencies allowed
- Use pure Python types (tuple, dataclass) instead of QPointF, QColor
- Color represented as RGBA tuple (r, g, b, a) with values 0-255
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Type aliases for pure Python types (no Qt)
Point2D = tuple[float, float]
ColorRGBA = tuple[int, int, int, int]  # (r, g, b, a) each 0-255


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


# Default colors for force types (RGBA)
_FORCE_COLORS: dict[ForceType, ColorRGBA] = {
    ForceType.REACTION: (255, 69, 0, 200),
    ForceType.APPLIED: (0, 123, 255, 200),
    ForceType.CONSTRAINT: (255, 140, 0, 200),
    ForceType.FRICTION: (128, 128, 128, 200),
    ForceType.GRAVITY: (139, 69, 19, 200),
}
_DEFAULT_COLOR: ColorRGBA = (100, 100, 100, 200)


@dataclass(frozen=True)
class ForceVector:
    """Force vector with position, magnitude, angle, and type."""
    position: Point2D  # (x, y) coordinates
    magnitude: float
    angle: float  # degrees
    force_type: ForceType
    label: str = ""
    color: ColorRGBA | None = None

    def __post_init__(self) -> None:
        if self.color is None:
            default_color = _FORCE_COLORS.get(self.force_type, _DEFAULT_COLOR)
            object.__setattr__(self, "color", default_color)

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
