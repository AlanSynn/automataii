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


@dataclass
class RenderSettings:
    """Unified rendering settings for consistent styling"""
    # Line weights (engineering drawing style)
    thin_line: float = 1.0
    medium_line: float = 2.0
    thick_line: float = 3.0
    construction_line: float = 0.5

    # Colors and styling options
    background_color: QColor = None
    grid: GridSettings = None
    link_color: QColor = None
    joint_color: QColor = None
    ground_joint_color: QColor = None
    highlight_color: QColor = None
    force_color: QColor = None
    velocity_color: QColor = None
    acceleration_color: QColor = None
    constraint_color: QColor = None
    motion_trail_color: QColor = None
    selection_color: QColor = None
    text_color: QColor = None
    dimension_color: QColor = None

    def __post_init__(self):
        # Background
        if self.background_color is None:
            self.background_color = QColor(250, 250, 250)

        # Grid
        if self.grid is None:
            self.grid = GridSettings()

        # Mechanism parts
        if self.link_color is None:
            self.link_color = QColor(70, 130, 180)
        if self.joint_color is None:
            self.joint_color = QColor(220, 20, 60)
        if self.ground_joint_color is None:
            self.ground_joint_color = QColor(105, 105, 105)
        if self.highlight_color is None:
            self.highlight_color = QColor(255, 140, 0)

        # Physics visualization
        if self.force_color is None:
            self.force_color = QColor(255, 69, 0, 200)
        if self.velocity_color is None:
            self.velocity_color = QColor(50, 205, 50, 200)
        if self.acceleration_color is None:
            self.acceleration_color = QColor(138, 43, 226, 200)
        if self.constraint_color is None:
            self.constraint_color = QColor(70, 130, 180, 100)

        # Visual feedback
        if self.motion_trail_color is None:
            self.motion_trail_color = QColor(255, 215, 0, 150)
        if self.selection_color is None:
            self.selection_color = QColor(0, 123, 255, 100)

        # Text and annotations
        if self.text_color is None:
            self.text_color = QColor(60, 60, 60)
        if self.dimension_color is None:
            self.dimension_color = QColor(100, 100, 100)


