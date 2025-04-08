import os
import sys
import logging
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QTransform # Import QTransform from QtGui

# --- Environment Setup ---

def setup_high_dpi_environment():
    """Sets environment variables for better High DPI scaling in Qt.

    This should be called early in the application startup, before QApplication is instantiated.
    """
    # Enable automatic scaling based on monitor DPI
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    # Explicitly disable manual scaling factor if auto is enabled
    # os.environ["QT_SCALE_FACTOR"] = "1"
    # If specific per-screen factors are needed:
    # os.environ["QT_SCREEN_SCALE_FACTORS"] = "Display1=1;Display2=1.5"
    # Force specific DPI (less common, usually use auto scale)
    # os.environ["QT_FONT_DPI"] = "96"
    logging.info("High DPI environment variables set (QT_AUTO_SCREEN_SCALE_FACTOR=1).")

# --- Transformation Helpers ---

def transform_to_dict(transform: QTransform) -> dict:
    """Converts a QTransform object to a serializable dictionary."""
    return {
        "m11": transform.m11(), "m12": transform.m12(), "m13": transform.m13(),
        "m21": transform.m21(), "m22": transform.m22(), "m23": transform.m23(),
        "m31": transform.m31(), "m32": transform.m32(), "m33": transform.m33()
    }

def dict_to_transform(data: dict) -> QTransform:
    """Converts a dictionary back to a QTransform object."""
    if not data or len(data) != 9:
        logging.warning("Invalid data format for dict_to_transform. Returning identity.")
        return QTransform() # Return identity transform
    return QTransform(
        data.get("m11", 1.0), data.get("m12", 0.0), data.get("m13", 0.0),
        data.get("m21", 0.0), data.get("m22", 1.0), data.get("m23", 0.0),
        data.get("m31", 0.0), data.get("m32", 0.0), data.get("m33", 1.0)
    )

# --- Path Helpers ---

def qpainterpath_to_points(path) -> list:
    """Converts a QPainterPath to a list of dictionaries representing elements."""
    points = []
    for i in range(path.elementCount()):
        el = path.elementAt(i)
        # Store type as string for better readability/JSON compatibility
        el_type_str = str(el.type).split('.')[-1] # e.g., "MoveToElement"
        points.append({"x": el.x, "y": el.y, "type": el_type_str})
    return points

def points_to_qpainterpath(points_data: list):
    """Converts a list of point dictionaries back to a QPainterPath."""
    from PyQt6.QtGui import QPainterPath # Local import to avoid circular deps
    path = QPainterPath()
    if not points_data:
        return path

    for p_data in points_data:
        x = p_data.get('x', 0.0)
        y = p_data.get('y', 0.0)
        el_type_str = p_data.get('type', '')

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
            logging.warning("CurveToElement cannot be fully restored from points alone. Using LineTo.")
            path.lineTo(x, y)
        elif el_type == QPainterPath.ElementType.CurveToDataElement:
             # This stores control points, but needs careful handling during restore.
             # For simplicity, treating as LineTo.
             logging.warning("CurveToDataElement restoration not implemented. Using LineTo.")
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
    det = v1.x() * v2.y() - v1.y() * v2.x() # Cross product Z component
    angle_rad = math.atan2(det, dot)
    return math.degrees(angle_rad)

def distance(p1: QPointF, p2: QPointF) -> float:
     """Calculates the Euclidean distance between two QPointF points."""
     return QLineF(p1, p2).length()