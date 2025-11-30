"""
Skeleton joint colors - Qt-specific.

QColor definitions for skeleton joint visualization.
"""

from PyQt6.QtGui import QColor

# Joint colors for visualization
JOINT_COLORS: dict[str, QColor] = {
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
    "left_ankle": QColor(255, 0, 200),
}
