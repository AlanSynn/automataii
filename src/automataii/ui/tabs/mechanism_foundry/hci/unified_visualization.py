"""
Unified Visualization System - Macanism-style mechanism rendering

Professional engineering-style visualization system inspired by github.com/AlanSynn/macanism
with consistent grid, force visualization, and mechanical drawing aesthetics across all tabs.

Features:
- Professional grid system with measurement units
- Engineering drawing style with precise lines
- Force vector visualization with proper scaling
- Constraint visualization with proper annotations
- Consistent styling across all mechanism types
- Real-time physics feedback
"""

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)


@dataclass
class GridSettings:
    """Grid visualization settings"""
    show_grid: bool = True
    grid_size: float = 20.0  # pixels
    major_grid_size: float = 100.0  # pixels
    show_measurements: bool = True
    show_origin: bool = True
    grid_color: QColor = None
    major_grid_color: QColor = None
    axis_color: QColor = None

    def __post_init__(self):
        if self.grid_color is None:
            self.grid_color = QColor(200, 200, 200, 100)
        if self.major_grid_color is None:
            self.major_grid_color = QColor(150, 150, 150, 150)
        if self.axis_color is None:
            self.axis_color = QColor(100, 100, 100, 200)





