"""Pure geometry calculation functions."""

import math
from typing import Tuple, List, Optional


def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points.
    
    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        
    Returns:
        Distance between points
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.sqrt(dx * dx + dy * dy)


def calculate_angle(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate angle from p1 to p2 in radians.
    
    Args:
        p1: Start point (x, y)
        p2: End point (x, y)
        
    Returns:
        Angle in radians (-π to π)
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.atan2(dy, dx)


def calculate_midpoint(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float]:
    """Calculate midpoint between two points.
    
    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        
    Returns:
        Midpoint (x, y)
    """
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


def normalize_vector(v: Tuple[float, float]) -> Tuple[float, float]:
    """Normalize a 2D vector.
    
    Args:
        v: Vector (x, y)
        
    Returns:
        Normalized vector or (0, 0) if zero vector
    """
    magnitude = math.sqrt(v[0] * v[0] + v[1] * v[1])
    if magnitude < 1e-10:
        return (0.0, 0.0)
    return (v[0] / magnitude, v[1] / magnitude)


def rotate_point(
    point: Tuple[float, float], 
    angle: float, 
    origin: Tuple[float, float] = (0, 0)
) -> Tuple[float, float]:
    """Rotate a point around an origin.
    
    Args:
        point: Point to rotate (x, y)
        angle: Rotation angle in radians
        origin: Center of rotation (x, y)
        
    Returns:
        Rotated point (x, y)
    """
    # Translate to origin
    x = point[0] - origin[0]
    y = point[1] - origin[1]
    
    # Rotate
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rx = x * cos_a - y * sin_a
    ry = x * sin_a + y * cos_a
    
    # Translate back
    return (rx + origin[0], ry + origin[1])


def calculate_bounds(points: List[Tuple[float, float]]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Calculate bounding box of points.
    
    Args:
        points: List of points (x, y)
        
    Returns:
        Tuple of (min_point, max_point)
    """
    if not points:
        return ((0, 0), (0, 0))
    
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    
    for x, y in points:
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
    
    return ((min_x, min_y), (max_x, max_y))


def point_on_line_closest_to_point(
    line_start: Tuple[float, float],
    line_end: Tuple[float, float],
    point: Tuple[float, float]
) -> Tuple[float, float]:
    """Find the point on a line segment closest to a given point.
    
    Args:
        line_start: Start of line segment (x, y)
        line_end: End of line segment (x, y)
        point: Point to find closest to (x, y)
        
    Returns:
        Closest point on line segment (x, y)
    """
    # Vector from line start to end
    line_dx = line_end[0] - line_start[0]
    line_dy = line_end[1] - line_start[1]
    
    # If line is actually a point
    line_length_sq = line_dx * line_dx + line_dy * line_dy
    if line_length_sq < 1e-10:
        return line_start
    
    # Vector from line start to point
    dx = point[0] - line_start[0]
    dy = point[1] - line_start[1]
    
    # Project point onto line (parameter t)
    t = (dx * line_dx + dy * line_dy) / line_length_sq
    
    # Clamp t to [0, 1] to stay on segment
    t = max(0, min(1, t))
    
    # Calculate closest point
    return (
        line_start[0] + t * line_dx,
        line_start[1] + t * line_dy
    )


def calculate_line_intersection(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """Calculate intersection point of two line segments.
    
    Args:
        p1, p2: First line segment endpoints
        p3, p4: Second line segment endpoints
        
    Returns:
        Intersection point or None if no intersection
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    # Lines are parallel
    if abs(denom) < 1e-10:
        return None
    
    t1 = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    t2 = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    
    # Check if intersection is within both segments
    if 0 <= t1 <= 1 and 0 <= t2 <= 1:
        return (
            x1 + t1 * (x2 - x1),
            y1 + t1 * (y2 - y1)
        )
    
    return None


def calculate_polygon_area(points: List[Tuple[float, float]]) -> float:
    """Calculate area of a polygon using the shoelace formula.
    
    Args:
        points: List of polygon vertices in order
        
    Returns:
        Area of polygon (positive for CCW, negative for CW)
    """
    if len(points) < 3:
        return 0.0
    
    area = 0.0
    n = len(points)
    
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    
    return area / 2.0


def is_point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Check if a point is inside a polygon using ray casting.
    
    Args:
        point: Point to test (x, y)
        polygon: List of polygon vertices
        
    Returns:
        True if point is inside polygon
    """
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside