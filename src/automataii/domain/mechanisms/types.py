"""Domain types for mechanism design system.

This module defines immutable value objects and DTOs used across
the mechanism design domain layer.

All types are pure Python (no PyQt dependencies).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NewType

__all__ = [
    "PathID",
    "StoredPath",
    "MechanismSpec",
    "MechanismResult",
    "BoundingBox",
]

# Type aliases
PathID = NewType("PathID", str)
Point2D = tuple[float, float]
PathPoints = tuple[Point2D, ...]


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in 2D space.

    Invariants:
        - max_x >= min_x
        - max_y >= min_y
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x:
            raise ValueError(f"Invalid bbox: max_x ({self.max_x}) < min_x ({self.min_x})")
        if self.max_y < self.min_y:
            raise ValueError(f"Invalid bbox: max_y ({self.max_y}) < min_y ({self.min_y})")

    @property
    def width(self) -> float:
        """Width of bounding box."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Height of bounding box."""
        return self.max_y - self.min_y

    @property
    def center(self) -> Point2D:
        """Center point of bounding box."""
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)

    @property
    def area(self) -> float:
        """Area of bounding box."""
        return self.width * self.height


@dataclass(frozen=True)
class StoredPath:
    """Immutable stored motion path.

    Represents a user-drawn or generated path associated with a character part.
    """

    id: PathID
    part_name: str
    points: PathPoints
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.part_name:
            raise ValueError("part_name cannot be empty")
        if len(self.points) < 2:
            raise ValueError(f"Path must have at least 2 points, got {len(self.points)}")
        if self.timestamp < 0:
            raise ValueError(f"timestamp must be non-negative, got {self.timestamp}")


@dataclass(frozen=True)
class MechanismSpec:
    """Immutable mechanism generation specification.

    Defines all parameters needed to generate a mechanism that follows
    a target path.
    """

    mechanism_type: str  # 'fourbar', 'cam', 'threebar', etc.
    parameters: dict[str, float]
    target_path: PathPoints
    part_name: str

    def __post_init__(self) -> None:
        if not self.mechanism_type:
            raise ValueError("mechanism_type cannot be empty")
        if not self.part_name:
            raise ValueError("part_name cannot be empty")
        # Note: target_path can be empty for mechanisms like fourbar/threebar
        # that generate their own paths (not path-tracing mechanisms)
        # Validation of target_path is mechanism-type specific and done
        # by the generation service


@dataclass(frozen=True)
class MechanismResult:
    """Result of mechanism generation.

    Contains generated path, key points (pivots, joints), and validity status.
    """

    mechanism_id: str
    mechanism_type: str
    part_name: str
    generated_path: PathPoints
    parameters: dict[str, float]
    key_points: dict[str, Point2D]  # Pivots, joints, etc.
    is_valid: bool
    error_message: str | None = None
    path_error_rms: float | None = None  # RMS error vs. target path

    def __post_init__(self) -> None:
        # Validate invariants
        if self.is_valid:
            if len(self.generated_path) == 0:
                raise ValueError("Valid mechanism must have non-empty generated_path")
            if self.error_message is not None:
                raise ValueError("Valid mechanism cannot have error_message")
        else:
            if self.error_message is None:
                raise ValueError("Invalid mechanism must have error_message")
