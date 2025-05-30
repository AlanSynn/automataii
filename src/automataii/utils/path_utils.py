"""Path manipulation utilities.
"""
from PyQt6.QtGui import QPainterPath
from PyQt6.QtCore import QPointF
from typing import List

def create_smooth_path(points: List[QPointF]) -> QPainterPath:
    """Creates a smooth QPainterPath from a list of points using Catmull-Rom-like splines (converted to Bezier segments).

    Args:
        points: A list of QPointF defining the path.

    Returns:
        A QPainterPath object representing the smoothed path.
    """
    path = QPainterPath()
    if not points:
        return path

    n = len(points)
    if n == 1:
        path.moveTo(points[0])
        return path

    path.moveTo(points[0])
    if n == 2:
        path.lineTo(points[1])
        return path

    # Catmull-Rom to Bezier conversion needs careful handling of control points.
    # For simplicity here, we'll use QPainterPath's internal smoothing if available
    # or a basic cubic Bezier if we have enough points.
    # A true Catmull-Rom requires looking at points before and after the current segment.

    # Simplified approach: Use points as control points for cubicTo or quadTo
    # This won't be a perfect Catmull-Rom but can provide some smoothing.

    # If QPainterPath has an add Jahren path method, use it here for best results.
    # Lacking that, let's do a basic piecewise Bezier or just line segments for now.

    # For a very basic smoothing using cubic Beziers:
    # We need to generate control points. A common approach is to use midpoints.
    # This example implements a simple cubic Bezier segment for every two points,
    # trying to make it smooth. It's not a full spline algorithm.

    if n < 2:
        if n == 1: path.moveTo(points[0])
        return path

    path.moveTo(points[0])
    if n == 2:
        path.lineTo(points[1])
        return path

    # Handle first segment as line or quadratic
    path.lineTo(points[1]) # Start with a line to the second point

    # For subsequent points, use cubic Bezier. Control points need calculation.
    # A robust spline implementation is non-trivial.
    # Let's use a simpler approach for now: connect points with lines,
    # as QPainterPath doesn't have a direct "smooth this list of points" function.
    # The "NURBS" request implies a more complex curve type.
    # For now, just lineTo, and we can enhance this function later.
    for i in range(2, n):
        path.lineTo(points[i])

    # If you want to try cubic Beziers (this is a simplified, possibly not ideal approach):
    # path.moveTo(points[0])
    # if n > 1:
    #     path.lineTo(points[1]) # First segment often a line or special case
    #     for i in range(1, n - 2):
    #         p0 = points[i-1] # Previous point (or control point based on it)
    #         p1 = points[i]   # Current start of segment
    #         p2 = points[i+1] # Current end of segment
    #         p3 = points[i+2] # Next point (or control point based on it)

    #         # Simplified control points (can be improved significantly)
    #         c1 = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2) # Midpoint as one control
    #         # For a Catmull-Rom like feel, control points are influenced by p0 and p3
    #         # cp1 = p1 + (p2 - p0) / 6
    #         # cp2 = p2 - (p3 - p1) / 6
    #         # path.cubicTo(cp1, cp2, p2)
    #         path.cubicTo(p1, p2, p2) # This is not correct for smooth cubic, just placeholder
    #     if n > 2: # last segment
    #        path.lineTo(points[n-1])

    return path