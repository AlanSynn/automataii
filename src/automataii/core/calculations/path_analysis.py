"""Pure functions for path analysis."""

import math
from typing import List, Tuple, Optional
from .geometry import calculate_distance, calculate_angle


def calculate_path_length(points: List[Tuple[float, float]]) -> float:
    """Calculate total length of a path.
    
    Args:
        points: List of path points (x, y)
        
    Returns:
        Total path length
    """
    if len(points) < 2:
        return 0.0
    
    total_length = 0.0
    for i in range(1, len(points)):
        total_length += calculate_distance(points[i-1], points[i])
    
    return total_length


def sample_path_points(
    points: List[Tuple[float, float]], 
    num_samples: int
) -> List[Tuple[float, float]]:
    """Sample points uniformly along a path.
    
    Args:
        points: Original path points
        num_samples: Number of samples to generate
        
    Returns:
        List of sampled points
    """
    if num_samples <= 0 or len(points) < 2:
        return points.copy()
    
    # Calculate segment lengths
    segments = []
    total_length = 0.0
    for i in range(1, len(points)):
        length = calculate_distance(points[i-1], points[i])
        segments.append(length)
        total_length += length
    
    if total_length < 1e-10:
        return [points[0]] * num_samples
    
    # Sample points
    sampled = []
    step = total_length / (num_samples - 1)
    
    for i in range(num_samples):
        target_distance = i * step
        
        # Find segment containing target distance
        accumulated = 0.0
        for j, seg_length in enumerate(segments):
            if accumulated + seg_length >= target_distance:
                # Interpolate within segment
                t = (target_distance - accumulated) / seg_length if seg_length > 0 else 0
                p1 = points[j]
                p2 = points[j + 1]
                
                x = p1[0] + t * (p2[0] - p1[0])
                y = p1[1] + t * (p2[1] - p1[1])
                sampled.append((x, y))
                break
            accumulated += seg_length
        else:
            # If we didn't break, add last point
            sampled.append(points[-1])
    
    return sampled


def simplify_path(
    points: List[Tuple[float, float]], 
    tolerance: float
) -> List[Tuple[float, float]]:
    """Simplify path using Douglas-Peucker algorithm.
    
    Args:
        points: Original path points
        tolerance: Maximum distance tolerance
        
    Returns:
        Simplified path points
    """
    if len(points) <= 2:
        return points.copy()
    
    def perpendicular_distance(point: Tuple[float, float], 
                             line_start: Tuple[float, float], 
                             line_end: Tuple[float, float]) -> float:
        """Calculate perpendicular distance from point to line."""
        # If line is actually a point
        if line_start == line_end:
            return calculate_distance(point, line_start)
        
        # Calculate perpendicular distance
        x0, y0 = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
        denominator = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
        
        if denominator < 1e-10:
            return 0.0
        
        return numerator / denominator
    
    def douglas_peucker(start: int, end: int) -> List[int]:
        """Recursive Douglas-Peucker implementation."""
        if end - start <= 1:
            return []
        
        # Find point with maximum distance
        max_dist = 0.0
        max_idx = start
        
        for i in range(start + 1, end):
            dist = perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        
        # If max distance is greater than tolerance, recursively simplify
        if max_dist > tolerance:
            left = douglas_peucker(start, max_idx)
            right = douglas_peucker(max_idx, end)
            return left + [max_idx] + right
        
        return []
    
    # Get indices to keep
    indices = [0] + douglas_peucker(0, len(points) - 1) + [len(points) - 1]
    indices = sorted(set(indices))  # Remove duplicates and sort
    
    # Return points at kept indices
    return [points[i] for i in indices]


def calculate_path_curvature(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float]
) -> float:
    """Calculate curvature at middle point of three consecutive points.
    
    Args:
        p1, p2, p3: Three consecutive points
        
    Returns:
        Curvature value (1/radius)
    """
    # Calculate side lengths
    a = calculate_distance(p2, p3)
    b = calculate_distance(p1, p3)
    c = calculate_distance(p1, p2)
    
    # Handle degenerate cases
    if a < 1e-10 or b < 1e-10 or c < 1e-10:
        return 0.0
    
    # Calculate area using Heron's formula
    s = (a + b + c) / 2
    area_sq = s * (s - a) * (s - b) * (s - c)
    
    if area_sq < 0:
        return 0.0
    
    area = math.sqrt(area_sq)
    
    # Curvature = 4 * area / (a * b * c)
    if area < 1e-10:
        return 0.0
    
    return 4 * area / (a * b * c)


def find_path_intersections(
    path1: List[Tuple[float, float]],
    path2: List[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """Find all intersections between two paths.
    
    Args:
        path1: First path points
        path2: Second path points
        
    Returns:
        List of intersection points
    """
    from .geometry import calculate_line_intersection
    
    intersections = []
    
    # Check each segment pair
    for i in range(len(path1) - 1):
        for j in range(len(path2) - 1):
            intersection = calculate_line_intersection(
                path1[i], path1[i + 1],
                path2[j], path2[j + 1]
            )
            if intersection:
                intersections.append(intersection)
    
    return intersections


def calculate_path_bounds(
    points: List[Tuple[float, float]]
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Calculate bounding box of a path.
    
    Args:
        points: Path points
        
    Returns:
        Tuple of (min_point, max_point)
    """
    from .geometry import calculate_bounds
    return calculate_bounds(points)


def calculate_path_direction(
    points: List[Tuple[float, float]],
    t: float
) -> float:
    """Calculate direction angle at parametric position along path.
    
    Args:
        points: Path points
        t: Parametric position (0.0 to 1.0)
        
    Returns:
        Direction angle in radians
    """
    if len(points) < 2:
        return 0.0
    
    # Clamp t
    t = max(0.0, min(1.0, t))
    
    # Find segment
    total_segments = len(points) - 1
    segment_index = int(t * total_segments)
    
    # Handle edge case
    if segment_index >= total_segments:
        segment_index = total_segments - 1
    
    # Calculate direction from segment
    return calculate_angle(points[segment_index], points[segment_index + 1])


def is_path_closed(
    points: List[Tuple[float, float]],
    tolerance: float = 1e-6
) -> bool:
    """Check if a path is closed (first and last points are same).
    
    Args:
        points: Path points
        tolerance: Distance tolerance for considering points equal
        
    Returns:
        True if path is closed
    """
    if len(points) < 2:
        return False
    
    return calculate_distance(points[0], points[-1]) < tolerance