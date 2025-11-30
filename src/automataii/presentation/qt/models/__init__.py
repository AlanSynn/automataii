"""
Qt-specific runtime models.

These models contain Qt types (QPainterPath, QPointF, etc.)
and are used for runtime representation in the UI layer.
"""

from automataii.presentation.qt.models.part_info import PartInfo
from automataii.presentation.qt.models.skeleton_colors import JOINT_COLORS

__all__ = [
    "PartInfo",
    "JOINT_COLORS",
]
