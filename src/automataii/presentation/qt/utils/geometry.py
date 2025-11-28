"""
Qt Geometry Utilities.

Shared utility functions for converting between Qt geometry types
and numpy arrays.
"""
import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath


def qpainterpath_to_numpy_array(path: QPainterPath, num_points: int = 100) -> np.ndarray | None:
    """Convert QPainterPath to numpy array of points.

    Args:
        path: QPainterPath to convert
        num_points: Number of points to extract (not used in current implementation)

    Returns:
        numpy array of shape (n, 2) containing x, y coordinates, or None if path is empty
    """
    if path.isEmpty():
        return None
    points = np.array(
        [[path.elementAt(i).x, path.elementAt(i).y] for i in range(path.elementCount())]
    )
    return points


def numpy_array_to_qpointfs(array: np.ndarray) -> list[QPointF]:
    """Convert numpy array to list of QPointF.

    Args:
        array: numpy array of shape (n, 2)

    Returns:
        List of QPointF points
    """
    if array is None or len(array) == 0:
        return []
    return [QPointF(float(x), float(y)) for x, y in array]


def qpointfs_to_numpy_array(points: list[QPointF]) -> np.ndarray:
    """Convert list of QPointF to numpy array.

    Args:
        points: List of QPointF

    Returns:
        numpy array of shape (n, 2)
    """
    if not points:
        return np.array([])
    return np.array([[p.x(), p.y()] for p in points])
