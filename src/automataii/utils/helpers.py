import os
import sys
import logging
from typing import List  # Add this import
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QTransform  # Import QTransform from QtGui
import json  # Added import
import numpy as np  # Added import

# --- Environment Setup ---


def setup_high_dpi_environment():
    """Sets environment variables for better High DPI scaling in Qt.

    This should be called early in the application startup, before QApplication is instantiated.
    """
    # Force specific DPI (less common, usually use auto scale)
    # os.environ["QT_FONT_DPI"] = "96"
    # Enable automatic scaling based on monitor DPI
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    # Explicitly disable manual scaling factor if auto is enabled
    # os.environ["QT_SCALE_FACTOR"] = "1"
    # If specific per-screen factors are needed:
    # os.environ["QT_SCREEN_SCALE_FACTORS"] = "Display1=1;Display2=1.5"
    logging.info("High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1).")


# --- Transformation Helpers ---


def transform_to_dict(transform: QTransform) -> dict:
    """Converts a QTransform object to a serializable dictionary."""
    return {
        "m11": transform.m11(),
        "m12": transform.m12(),
        "m13": transform.m13(),
        "m21": transform.m21(),
        "m22": transform.m22(),
        "m23": transform.m23(),
        "m31": transform.m31(),
        "m32": transform.m32(),
        "m33": transform.m33(),
    }


def dict_to_transform(data: dict) -> QTransform:
    """Converts a dictionary back to a QTransform object."""
    if not data or len(data) != 9:
        logging.warning(
            "Invalid data format for dict_to_transform. Returning identity."
        )
        return QTransform()  # Return identity transform
    return QTransform(
        data.get("m11", 1.0),
        data.get("m12", 0.0),
        data.get("m13", 0.0),
        data.get("m21", 0.0),
        data.get("m22", 1.0),
        data.get("m23", 0.0),
        data.get("m31", 0.0),
        data.get("m32", 0.0),
        data.get("m33", 1.0),
    )


# --- Path Helpers ---


def qpainterpath_to_points(path) -> list:
    """Converts a QPainterPath to a list of dictionaries representing elements."""
    points = []
    for i in range(path.elementCount()):
        el = path.elementAt(i)
        # Store type as string for better readability/JSON compatibility
        el_type_str = str(el.type).split(".")[-1]  # e.g., "MoveToElement"
        points.append({"x": el.x, "y": el.y, "type": el_type_str})
    return points


def points_to_qpainterpath(points_data: list):
    """Converts a list of point dictionaries back to a QPainterPath."""
    from PyQt6.QtGui import QPainterPath  # Local import to avoid circular deps

    path = QPainterPath()
    if not points_data:
        return path

    for p_data in points_data:
        x = p_data.get("x", 0.0)
        y = p_data.get("y", 0.0)
        el_type_str = p_data.get("type", "")

        # Convert type string back to QPainterPath.ElementType enum
        # This is a bit fragile; assumes names don't change.
        el_type = getattr(QPainterPath.ElementType, el_type_str, None)

        if el_type == QPainterPath.ElementType.MoveToElement:
            path.moveTo(x, y)
        elif el_type == QPainterPath.ElementType.LineToElement:
            path.lineTo(x, y)
        elif el_type == QPainterPath.ElementType.CurveToElement:
            # Need control points - this simple conversion loses them!
            # To properly restore curves, need to save control points too.
            logging.warning(
                "CurveToElement cannot be fully restored from points alone. Using LineTo."
            )
            path.lineTo(x, y)
        elif el_type == QPainterPath.ElementType.CurveToDataElement:
            # This stores control points, but needs careful handling during restore.
            # For simplicity, treating as LineTo.
            logging.warning(
                "CurveToDataElement restoration not implemented. Using LineTo."
            )
            # path.lineTo(x, y) # Data element isn't a vertex
            pass
        else:
            logging.warning(f"Unknown or unsupported path element type: {el_type_str}")

    return path


# --- Geometry Helpers ---


def angle_between_vectors(v1: QPointF, v2: QPointF) -> float:
    """Calculates the signed angle (in degrees) from v1 to v2."""
    import math

    dot = QPointF.dotProduct(v1, v2)
    det = v1.x() * v2.y() - v1.y() * v2.x()  # Cross product Z component
    angle_rad = math.atan2(det, dot)
    return math.degrees(angle_rad)


def distance(p1: QPointF, p2: QPointF) -> float:
    """Calculates the Euclidean distance between two QPointF points."""
    return QLineF(p1, p2).length()


def points_to_closed_bezier_path(
    points: List[QPointF], tension: float = 1 / 6
) -> "QPainterPath":
    """Converts a list of QPointF objects to a closed, smooth QPainterPath using Bezier curves.

    Args:
        points: A list of QPointF objects defining the vertices of the polygon.
        tension: A factor to control the "tightness" of the curve. Default is 1/6.

    Returns:
        A QPainterPath representing the smooth, closed Bezier curve.
        Returns an empty path if fewer than 3 points are provided.
    """
    from PyQt6.QtGui import QPainterPath  # Local import

    num_points = len(points)
    if num_points < 3:
        # For 0 or 1 point, return empty path
        # For 2 points, could return a line, but for a "closed Bezier curve" it's ambiguous
        logging.warning(
            "Cannot generate a closed Bezier path with fewer than 3 points."
        )
        path = QPainterPath()
        if num_points == 1:
            path.moveTo(points[0])
        elif num_points == 2:
            path.moveTo(points[0])
            path.lineTo(points[1])
            # path.closeSubpath() # Technically makes it a degenerate closed shape
        return path

    path = QPainterPath()
    path.moveTo(points[0])

    for i in range(num_points):
        p0 = points[i]
        p1 = points[(i + 1) % num_points]
        p2 = points[(i + 2) % num_points]
        p_minus_1 = points[(i - 1 + num_points) % num_points]

        # Calculate control points for the segment from p0 to p1
        # This is based on Catmull-Rom to Bezier conversion
        cp1 = p0 + (p1 - p_minus_1) * tension
        cp2 = p1 - (p2 - p0) * tension

        path.cubicTo(cp1, cp2, p1)

    # The loop should naturally close the path by ending at points[0] (which was p1 when i = num_points-1)
    # QPainterPath.closeSubpath() can be used to explicitly close the current subpath if needed,
    # but for a well-formed loop of cubicTo, it should already connect.
    # Let's ensure it's explicitly closed if the path isn't already at the start point.
    if path.currentPosition() != points[0]:
        # This shouldn't happen with the loop structure, but as a safeguard
        # path.lineTo(points[0]) # Force close if not already there
        pass  # The cubicTo should handle the closure to p[0] in the last iteration.

    return path


# --- JSON Helpers ---
class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy types."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)
