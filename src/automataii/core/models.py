import os
from PyQt6.QtGui import QPainterPath, QColor
from PyQt6.QtCore import QPointF
import logging

try:
    from svgpathtools import svg2paths, Path, Line, Arc, CubicBezier, QuadraticBezier
    HAS_SVGPATH = True
except ImportError:
    logging.warning("svgpathtools not found. SVG parsing will be unavailable. pip install svgpathtools")
    HAS_SVGPATH = False
    # Define dummy classes if the library is missing
    class Path: pass
    class Line: pass
    class Arc: pass
    class CubicBezier: pass
    class QuadraticBezier: pass

# --- Constants ---
SKELETON_JOINTS = ["head", "neck", "right_shoulder", "right_elbow", "right_wrist",
                  "left_shoulder", "left_elbow", "left_wrist", "right_hip",
                  "right_knee", "right_ankle", "left_hip", "left_knee", "left_ankle"]

JOINT_CONNECTIONS = [
    ("head", "neck"),
    ("neck", "right_shoulder"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("neck", "left_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("neck", "right_hip"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
    ("neck", "left_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle")
]

JOINT_COLORS = {
    "head": QColor(255, 0, 0),
    "neck": QColor(255, 100, 0),
    "right_shoulder": QColor(255, 200, 0),
    "right_elbow": QColor(200, 255, 0),
    "right_wrist": QColor(100, 255, 0),
    "left_shoulder": QColor(0, 255, 0),
    "left_elbow": QColor(0, 255, 100),
    "left_wrist": QColor(0, 255, 200),
    "right_hip": QColor(0, 200, 255),
    "right_knee": QColor(0, 100, 255),
    "right_ankle": QColor(0, 0, 255),
    "left_hip": QColor(100, 0, 255),
    "left_knee": QColor(200, 0, 255),
    "left_ankle": QColor(255, 0, 200)
}

class PartInfo:
    """Store information about character parts"""
    def __init__(self, name, data):
        self.name = name
        self.roi = data.get('roi')
        self.svg_path_file = data.get('svg_path') # SVG file path
        self.image_path = data.get('image_path') # PNG file path (optional)
        self.fill_color = data.get('fill_color', 'rgba(128,128,128,0.5)') # Default gray
        self.z_value = data.get('z_value', 0) # Z-layer value

        self.svg_paths = [] # Parsed SVG path data (svgpathtools Path objects list)
        self.qpainter_path = QPainterPath() # Path to draw in PyQt

        if HAS_SVGPATH:
            self._parse_svg()

    def _parse_svg(self):
        if self.svg_path_file and os.path.exists(self.svg_path_file):
            try:
                paths, attributes, svg_attribs = svg2paths(self.svg_path_file, return_svg_attributes=True)
                # TODO: Handle viewBox and transformations if present in svg_attribs
                self.svg_paths = paths
                path = QPainterPath()
                for p in paths:
                    if not p: continue
                    path.moveTo(QPointF(p.start.real, p.start.imag))
                    for segment in p:
                        if isinstance(segment, Line):
                            path.lineTo(QPointF(segment.end.real, segment.end.imag))
                        elif isinstance(segment, CubicBezier):
                            path.cubicTo(QPointF(segment.control1.real, segment.control1.imag),
                                         QPointF(segment.control2.real, segment.control2.imag),
                                         QPointF(segment.end.real, segment.end.imag))
                        elif isinstance(segment, QuadraticBezier):
                            path.quadTo(QPointF(segment.control.real, segment.control.imag),
                                        QPointF(segment.end.real, segment.end.imag))
                        elif isinstance(segment, Arc):
                             # QPainterPath doesn't directly support SVG Arc parameters (radius, rotation, flags)
                             # Approximate arc with lines or Bezier curves (complex)
                             # Simple approximation: line to end point
                             logging.warning(f"SVG Arc in {self.name} approximated as LineTo.")
                             path.lineTo(QPointF(segment.end.real, segment.end.imag))
                        else:
                            # For all other segment types, fall back to lineTo
                            path.lineTo(QPointF(segment.end.real, segment.end.imag))

                self.qpainter_path = path.simplified() # Simplify path
            except Exception as e:
                logging.error(f"Error parsing SVG {self.svg_path_file}: {e}")
        else:
             logging.warning(f"SVG file not found or path not specified for {self.name}: {self.svg_path_file}")

class Joint:
    """Joint connecting two parts"""
    def __init__(self, parent_item, child_item, parent_pos, child_pos, name=""):
        self.parent_item = parent_item
        self.child_item = child_item
        self.parent_pos = parent_pos # Joint position in parent local coordinates
        self.child_pos = child_pos   # Joint position in child local coordinates
        self.name = name or f"Joint_{parent_item.part_info.name}_{child_item.part_info.name}"
        self.angle = 0.0 # Current joint angle (relative to parent, in degrees)

    def get_global_pos(self):
        """Get joint's global position (based on parent item)"""
        if self.parent_item:
            # Need to access scene through item
            if self.parent_item.scene():
                 return self.parent_item.mapToScene(self.parent_pos)
            else:
                 # Fallback if item not in scene yet (might happen during setup)
                 logging.warning(f"Joint {self.name} parent item not yet in scene.")
                 return self.parent_item.pos() + self.parent_pos # Approximate
        return QPointF(0, 0) # If no parent (Scene basis)