"""
Dimensional models for automata base system.

This module provides classes for representing dimensions, bounding boxes,
and mounting points in both 2D and 3D space.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
from enum import Enum


class Unit(Enum):
    """Units of measurement."""
    MM = "mm"
    CM = "cm"
    INCH = "inch"
    
    def to_mm(self, value: float) -> float:
        """Convert value to millimeters."""
        conversions = {
            self.MM: 1.0,
            self.CM: 10.0,
            self.INCH: 25.4,
        }
        return value * conversions[self]
    
    def from_mm(self, value: float) -> float:
        """Convert value from millimeters."""
        conversions = {
            self.MM: 1.0,
            self.CM: 0.1,
            self.INCH: 0.0393701,
        }
        return value * conversions[self]


@dataclass
class Dimensions2D:
    """2D dimensions (width and height)."""
    
    width: float
    height: float
    unit: Unit = Unit.MM
    
    def __post_init__(self):
        """Validate dimensions."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Dimensions must be positive")
    
    @property
    def area(self) -> float:
        """Calculate area in current units."""
        return self.width * self.height
    
    @property
    def perimeter(self) -> float:
        """Calculate perimeter in current units."""
        return 2 * (self.width + self.height)
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate width/height ratio."""
        return self.width / self.height
    
    def to_unit(self, target_unit: Unit) -> "Dimensions2D":
        """Convert to different unit."""
        if self.unit == target_unit:
            return self
        
        # Convert to mm first, then to target
        width_mm = self.unit.to_mm(self.width)
        height_mm = self.unit.to_mm(self.height)
        
        return Dimensions2D(
            width=target_unit.from_mm(width_mm),
            height=target_unit.from_mm(height_mm),
            unit=target_unit
        )
    
    def scale(self, factor: float) -> "Dimensions2D":
        """Scale dimensions by factor."""
        return Dimensions2D(
            width=self.width * factor,
            height=self.height * factor,
            unit=self.unit
        )


@dataclass
class Dimensions3D:
    """3D dimensions (width, height, and depth)."""
    
    width: float
    height: float
    depth: float
    unit: Unit = Unit.MM
    
    def __post_init__(self):
        """Validate dimensions."""
        if self.width <= 0 or self.height <= 0 or self.depth <= 0:
            raise ValueError("Dimensions must be positive")
    
    @property
    def volume(self) -> float:
        """Calculate volume in current units."""
        return self.width * self.height * self.depth
    
    @property
    def surface_area(self) -> float:
        """Calculate surface area in current units."""
        return 2 * (self.width * self.height + 
                   self.width * self.depth + 
                   self.height * self.depth)
    
    @property
    def diagonal(self) -> float:
        """Calculate space diagonal."""
        import math
        return math.sqrt(self.width**2 + self.height**2 + self.depth**2)
    
    def to_unit(self, target_unit: Unit) -> "Dimensions3D":
        """Convert to different unit."""
        if self.unit == target_unit:
            return self
        
        # Convert to mm first, then to target
        width_mm = self.unit.to_mm(self.width)
        height_mm = self.unit.to_mm(self.height)
        depth_mm = self.unit.to_mm(self.depth)
        
        return Dimensions3D(
            width=target_unit.from_mm(width_mm),
            height=target_unit.from_mm(height_mm),
            depth=target_unit.from_mm(depth_mm),
            unit=target_unit
        )
    
    def scale(self, factor: float) -> "Dimensions3D":
        """Scale dimensions by factor."""
        return Dimensions3D(
            width=self.width * factor,
            height=self.height * factor,
            depth=self.depth * factor,
            unit=self.unit
        )
    
    def to_2d(self, exclude_axis: str = "depth") -> Dimensions2D:
        """Convert to 2D by excluding one axis."""
        if exclude_axis == "depth":
            return Dimensions2D(self.width, self.height, self.unit)
        elif exclude_axis == "height":
            return Dimensions2D(self.width, self.depth, self.unit)
        elif exclude_axis == "width":
            return Dimensions2D(self.height, self.depth, self.unit)
        else:
            raise ValueError(f"Invalid axis: {exclude_axis}")


@dataclass
class Point2D:
    """2D point coordinates."""
    x: float
    y: float
    
    def distance_to(self, other: "Point2D") -> float:
        """Calculate distance to another point."""
        import math
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class Point3D:
    """3D point coordinates."""
    x: float
    y: float
    z: float
    
    def distance_to(self, other: "Point3D") -> float:
        """Calculate distance to another point."""
        import math
        return math.sqrt((self.x - other.x)**2 + 
                        (self.y - other.y)**2 + 
                        (self.z - other.z)**2)
    
    def to_2d(self, plane: str = "xy") -> Point2D:
        """Project to 2D plane."""
        if plane == "xy":
            return Point2D(self.x, self.y)
        elif plane == "xz":
            return Point2D(self.x, self.z)
        elif plane == "yz":
            return Point2D(self.y, self.z)
        else:
            raise ValueError(f"Invalid plane: {plane}")


@dataclass
class BoundingBox:
    """Bounding box for 3D objects."""
    
    min_point: Point3D
    max_point: Point3D
    unit: Unit = Unit.MM
    
    def __post_init__(self):
        """Validate bounding box."""
        if (self.min_point.x > self.max_point.x or
            self.min_point.y > self.max_point.y or
            self.min_point.z > self.max_point.z):
            raise ValueError("Invalid bounding box: min > max")
    
    @property
    def dimensions(self) -> Dimensions3D:
        """Get dimensions of bounding box."""
        return Dimensions3D(
            width=self.max_point.x - self.min_point.x,
            height=self.max_point.y - self.min_point.y,
            depth=self.max_point.z - self.min_point.z,
            unit=self.unit
        )
    
    @property
    def center(self) -> Point3D:
        """Get center point of bounding box."""
        return Point3D(
            x=(self.min_point.x + self.max_point.x) / 2,
            y=(self.min_point.y + self.max_point.y) / 2,
            z=(self.min_point.z + self.max_point.z) / 2
        )
    
    def contains_point(self, point: Point3D) -> bool:
        """Check if point is inside bounding box."""
        return (self.min_point.x <= point.x <= self.max_point.x and
                self.min_point.y <= point.y <= self.max_point.y and
                self.min_point.z <= point.z <= self.max_point.z)
    
    def intersects(self, other: "BoundingBox") -> bool:
        """Check if bounding box intersects with another."""
        return not (self.max_point.x < other.min_point.x or
                   self.min_point.x > other.max_point.x or
                   self.max_point.y < other.min_point.y or
                   self.min_point.y > other.max_point.y or
                   self.max_point.z < other.min_point.z or
                   self.min_point.z > other.max_point.z)


@dataclass
class MountingPoint:
    """Mounting point definition."""
    
    position: Union[Point2D, Point3D]
    hole_diameter: float
    hole_depth: Optional[float] = None  # None for through holes
    thread_type: Optional[str] = None  # e.g., "M3", "M4", "#6-32"
    countersink: bool = False
    countersink_diameter: Optional[float] = None
    countersink_angle: float = 90.0  # degrees
    
    def is_threaded(self) -> bool:
        """Check if mounting point is threaded."""
        return self.thread_type is not None
    
    def is_through_hole(self) -> bool:
        """Check if hole goes completely through."""
        return self.hole_depth is None