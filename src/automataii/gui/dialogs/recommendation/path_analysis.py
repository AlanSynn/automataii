"""Path analysis utilities for mechanism recommendation."""

from typing import Optional
import numpy as np
from scipy.spatial.distance import directed_hausdorff
from PyQt6.QtGui import QPainterPath

from .constants import DEFAULT_NUM_SAMPLES_FOR_PATH


def qpainterpath_to_numpy_array(
    path: QPainterPath, num_points: int = DEFAULT_NUM_SAMPLES_FOR_PATH
) -> Optional[np.ndarray]:
    """Converts a QPainterPath to a numpy array of (x, y) coordinates.

    Args:
        path: The QPainterPath to convert.
        num_points: The number of points to sample along the path.

    Returns:
        A numpy array of shape (num_points, 2) or None if the path is empty or invalid.
    """
    if path.isEmpty() or num_points <= 0:
        return None

    points = []
    for i in range(num_points):
        percent = i / (num_points - 1) if num_points > 1 else 0
        pt = path.pointAtPercent(percent)
        points.append([pt.x(), pt.y()])
    return np.array(points)


def calculate_hausdorff_distance(
    path1_points: np.ndarray, path2_points: np.ndarray
) -> float:
    """Calculates the Hausdorff distance between two sets of points.

    Args:
        path1_points: Numpy array of points for the first path (N, 2).
        path2_points: Numpy array of points for the second path (M, 2).

    Returns:
        The Hausdorff distance. Returns float('inf') if either path is empty or invalid.
    """
    if (
        path1_points is None
        or path1_points.shape[0] == 0
        or path2_points is None
        or path2_points.shape[0] == 0
    ):
        return float("inf")

    # For a more robust measure, consider the maximum of the two directed distances
    dist_1_to_2 = directed_hausdorff(path1_points, path2_points)[0]
    dist_2_to_1 = directed_hausdorff(path2_points, path1_points)[0]
    return max(dist_1_to_2, dist_2_to_1)


def score_to_match_percentage(score: float) -> float:
    """Convert Hausdorff distance score to match percentage.
    
    Args:
        score: Hausdorff distance score (lower is better)
        
    Returns:
        Match percentage (0-100)
    """
    if score == 0:
        return 100.0
    else:
        # Exponential decay: e^(-score/50) gives good range
        # Score of 50 = ~37% match, Score of 100 = ~14% match
        import math
        return max(0, min(100, math.exp(-score / 50) * 100))