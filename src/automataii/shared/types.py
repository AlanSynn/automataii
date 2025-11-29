"""
Common Types - Shared across all layers.

Pure Python types with NO external dependencies.
These types are used across domain, application, and infrastructure layers.
"""

from __future__ import annotations

from typing import NamedTuple, NewType

__all__ = [
    "Point2D",
    "PathID",
    "MechanismID",
    "PartID",
]


class Point2D(NamedTuple):
    """
    Immutable 2D point.

    Uses NamedTuple for:
    - Immutability
    - Memory efficiency
    - Tuple unpacking support
    - Named attribute access

    Example:
        p = Point2D(10.0, 20.0)
        x, y = p  # Unpacking
        print(p.x, p.y)  # Named access
    """

    x: float
    y: float

    def __add__(self, other: Point2D) -> Point2D:  # type: ignore[override]
        """Vector addition (intentionally overrides tuple concatenation)."""
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point2D) -> Point2D:
        """Vector subtraction."""
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point2D:  # type: ignore[override]
        """Scalar multiplication (intentionally overrides tuple repetition)."""
        return Point2D(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> Point2D:  # type: ignore[override]
        """Scalar multiplication (reversed)."""
        return self.__mul__(scalar)

    def distance_to(self, other: Point2D) -> float:
        """Euclidean distance to another point."""
        dx = self.x - other.x
        dy = self.y - other.y
        return float((dx * dx + dy * dy) ** 0.5)

    def magnitude(self) -> float:
        """Distance from origin."""
        return float((self.x * self.x + self.y * self.y) ** 0.5)

    def normalized(self) -> Point2D:
        """Returns unit vector in same direction."""
        mag = self.magnitude()
        if mag == 0:
            return Point2D(0.0, 0.0)
        return Point2D(self.x / mag, self.y / mag)

    def dot(self, other: Point2D) -> float:
        """Dot product."""
        return self.x * other.x + self.y * other.y

    def cross(self, other: Point2D) -> float:
        """2D cross product (returns scalar)."""
        return self.x * other.y - self.y * other.x

    @classmethod
    def from_tuple(cls, t: tuple[float, float]) -> Point2D:
        """Create from tuple."""
        return cls(t[0], t[1])

    def to_tuple(self) -> tuple[float, float]:
        """Convert to plain tuple."""
        return (self.x, self.y)


# Type-safe ID types using NewType
PathID = NewType("PathID", str)
MechanismID = NewType("MechanismID", str)
PartID = NewType("PartID", str)
