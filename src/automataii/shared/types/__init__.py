"""
Shared type definitions for cross-module communication.

Contains protocols, type aliases, and common data structures
used across presentation and application layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

# Coordinate type aliases
Point2D: TypeAlias = tuple[float, float]
BoundingBox: TypeAlias = tuple[float, float, float, float]  # x, y, width, height
PointDict: TypeAlias = dict[str, Point2D]


@dataclass(frozen=True)
class Coordinate:
    """Immutable 2D coordinate with arithmetic operations."""

    x: float
    y: float

    def __add__(self, other: Coordinate) -> Coordinate:
        return Coordinate(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Coordinate) -> Coordinate:
        return Coordinate(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Coordinate:
        return Coordinate(self.x * scalar, self.y * scalar)

    def to_tuple(self) -> Point2D:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, point: Point2D) -> Coordinate:
        return cls(point[0], point[1])


@runtime_checkable
class Renderable(Protocol):
    """Protocol for objects that can be rendered to a scene."""

    def render(self) -> None:
        """Render the object."""
        ...


@runtime_checkable
class Disposable(Protocol):
    """Protocol for objects with cleanup requirements."""

    def dispose(self) -> None:
        """Clean up resources."""
        ...


__all__ = [
    "Point2D",
    "BoundingBox",
    "PointDict",
    "Coordinate",
    "Renderable",
    "Disposable",
]
