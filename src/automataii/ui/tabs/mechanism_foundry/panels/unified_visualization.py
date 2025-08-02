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
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QLinearGradient, QRadialGradient,
    QPainterPath, QTransform, QPolygonF, QFont, QFontMetrics
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


class UnifiedMechanismRenderer:
    """
    Professional unified renderer for all mechanism visualizations.
    
    Provides consistent macanism-style rendering across all tabs with:
    - Engineering drawing aesthetics
    - Professional grid system
    - Physics visualization
    - Consistent styling and measurements
    """
    
    def __init__(self, settings: Optional[RenderSettings] = None):
        self.settings = settings or RenderSettings()
        self.viewport_rect = QRectF(0, 0, 800, 600)
        self.transform = QTransform()
        
        # Animation and interaction state
        self.animation_time = 0.0
        self.hover_element = None
        self.selected_elements = set()
        
        # Physics data
        self.forces = {}  # element_id -> (fx, fy)
        self.velocities = {}  # element_id -> (vx, vy)
        self.constraints = []  # list of constraint visualizations
        
    def set_viewport(self, rect: QRectF):
        """Set the viewport rectangle"""
        self.viewport_rect = rect
        
    def begin_render(self, painter: QPainter):
        """Initialize rendering context"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.viewport_rect, self.settings.background_color)
        
    def draw_grid(self, painter: QPainter):
        """Draw professional engineering-style grid"""
        if not self.settings.grid.show_grid:
            return
            
        painter.save()
        
        # Grid bounds
        left = int(self.viewport_rect.left())
        right = int(self.viewport_rect.right())
        top = int(self.viewport_rect.top())
        bottom = int(self.viewport_rect.bottom())
        
        grid_size = self.settings.grid.grid_size
        major_grid_size = self.settings.grid.major_grid_size
        
        # Draw minor grid lines
        painter.setPen(QPen(self.settings.grid.grid_color, 
                           self.settings.construction_line, 
                           Qt.PenStyle.DotLine))
        
        # Vertical minor grid lines
        for x in range(int(left // grid_size) * int(grid_size), right, int(grid_size)):
            if x % int(major_grid_size) != 0:  # Skip major grid positions
                painter.drawLine(x, top, x, bottom)
        
        # Horizontal minor grid lines  
        for y in range(int(top // grid_size) * int(grid_size), bottom, int(grid_size)):
            if y % int(major_grid_size) != 0:  # Skip major grid positions
                painter.drawLine(left, y, right, y)
        
        # Draw major grid lines
        painter.setPen(QPen(self.settings.grid.major_grid_color,
                           self.settings.thin_line,
                           Qt.PenStyle.SolidLine))
        
        # Vertical major grid lines
        for x in range(int(left // major_grid_size) * int(major_grid_size), right, int(major_grid_size)):
            painter.drawLine(x, top, x, bottom)
            
            # Add measurements
            if self.settings.grid.show_measurements and x != 0:
                painter.setPen(QPen(self.settings.dimension_color, self.settings.thin_line))
                painter.drawText(int(x + 5), int(top + 15), f"{x}")
                painter.setPen(QPen(self.settings.grid.major_grid_color, self.settings.thin_line))
        
        # Horizontal major grid lines
        for y in range(int(top // major_grid_size) * int(major_grid_size), bottom, int(major_grid_size)):
            painter.drawLine(left, y, right, y)
            
            # Add measurements
            if self.settings.grid.show_measurements and y != 0:
                painter.setPen(QPen(self.settings.dimension_color, self.settings.thin_line))
                painter.drawText(int(left + 5), int(y - 5), f"{y}")
                painter.setPen(QPen(self.settings.grid.major_grid_color, self.settings.thin_line))
        
        # Draw axes (origin)
        if self.settings.grid.show_origin:
            painter.setPen(QPen(self.settings.grid.axis_color,
                               self.settings.medium_line,
                               Qt.PenStyle.SolidLine))
            
            # Find origin in viewport
            center_x = self.viewport_rect.width() / 2
            center_y = self.viewport_rect.height() / 2
            
            # X-axis
            painter.drawLine(left, int(center_y), right, int(center_y))
            # Y-axis  
            painter.drawLine(int(center_x), top, int(center_x), bottom)
            
            # Origin marker
            painter.setBrush(QBrush(self.settings.grid.axis_color))
            painter.drawEllipse(QPointF(center_x, center_y), 3, 3)
            
            # Axis labels
            painter.setPen(QPen(self.settings.text_color, self.settings.thin_line))
            font = QFont("Arial", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(int(right - 20), int(center_y) - 10, "X")
            painter.drawText(int(center_x) + 10, int(top + 20), "Y")
        
        painter.restore()
        
    def draw_mechanism_link(self, painter: QPainter, start: QPointF, end: QPointF, 
                           width: float = 6.0, force: float = 0.0, selected: bool = False):
        """Draw a mechanism link with professional styling"""
        painter.save()
        
        # Calculate link properties
        length = math.sqrt((end.x() - start.x())**2 + (end.y() - start.y())**2)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        
        # Color based on force/stress
        link_color = self.settings.link_color
        if force > 0:
            # Compression - reddish
            intensity = min(force / 100.0, 1.0)
            link_color = QColor(
                int(255 * intensity + link_color.red() * (1 - intensity)),
                int(link_color.green() * (1 - intensity)),
                int(link_color.blue() * (1 - intensity))
            )
        elif force < 0:
            # Tension - bluish
            intensity = min(abs(force) / 100.0, 1.0)
            link_color = QColor(
                int(link_color.red() * (1 - intensity)),
                int(link_color.green() * (1 - intensity)),
                int(255 * intensity + link_color.blue() * (1 - intensity))
            )
        
        # Selection highlight
        if selected:
            link_color = self.settings.highlight_color
            
        # Draw link body
        painter.setPen(QPen(link_color.darker(120), self.settings.thin_line))
        painter.setBrush(QBrush(link_color))
        
        # Create link polygon (rounded rectangle)
        link_path = QPainterPath()
        
        # Calculate perpendicular offset
        perp_x = -math.sin(angle) * width / 2
        perp_y = math.cos(angle) * width / 2
        
        # Link outline points
        points = [
            QPointF(start.x() + perp_x, start.y() + perp_y),
            QPointF(start.x() - perp_x, start.y() - perp_y),
            QPointF(end.x() - perp_x, end.y() - perp_y),
            QPointF(end.x() + perp_x, end.y() + perp_y)
        ]
        
        polygon = QPolygonF(points)
        painter.drawPolygon(polygon)
        
        # Draw center line for engineering style
        painter.setPen(QPen(link_color.darker(150), self.settings.construction_line, Qt.PenStyle.DashLine))
        painter.drawLine(start, end)
        
        # Draw dimension if significant length
        if length > 50:
            self.draw_dimension_line(painter, start, end, f"{length:.1f}")
            
        painter.restore()
        
    def draw_mechanism_joint(self, painter: QPainter, position: QPointF, 
                           radius: float = 8.0, fixed: bool = False, 
                           selected: bool = False, joint_id: str = ""):
        """Draw a mechanism joint with professional styling"""
        painter.save()
        
        # Choose colors
        if fixed:
            joint_color = self.settings.ground_joint_color
            fill_color = joint_color.lighter(120)
        else:
            joint_color = self.settings.joint_color
            fill_color = joint_color.lighter(140)
            
        if selected:
            joint_color = self.settings.highlight_color
            fill_color = joint_color.lighter(120)
        
        # Draw joint body
        painter.setPen(QPen(joint_color, self.settings.medium_line))
        painter.setBrush(QBrush(fill_color))
        painter.drawEllipse(position, radius, radius)
        
        # Draw inner circle for non-fixed joints
        if not fixed:
            painter.setPen(QPen(joint_color.darker(130), self.settings.thin_line))
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawEllipse(position, radius * 0.6, radius * 0.6)
        
        # Fixed joint indication
        if fixed:
            # Draw ground symbol
            painter.setPen(QPen(joint_color, self.settings.medium_line))
            
            # Ground hatching
            for i in range(-3, 4):
                offset = i * 3
                painter.drawLine(
                    int(position.x() + offset - 6), int(position.y() + radius + 8),
                    int(position.x() + offset + 6), int(position.y() + radius + 12)
                )
            
            # Ground base line
            painter.drawLine(
                int(position.x() - 10), int(position.y() + radius + 6),
                int(position.x() + 10), int(position.y() + radius + 6)
            )
        
        # Joint label
        if joint_id and len(joint_id) > 0:
            painter.setPen(QPen(self.settings.text_color, self.settings.thin_line))
            font = QFont("Arial", 8, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(int(position.x() + radius + 5), int(position.y() - radius), joint_id)
            
        painter.restore()
        
    def draw_force_vector(self, painter: QPainter, position: QPointF, 
                         force: Tuple[float, float], scale: float = 1.0):
        """Draw force vector with proper engineering annotation"""
        if force[0] == 0 and force[1] == 0:
            return
            
        painter.save()
        
        fx, fy = force
        magnitude = math.sqrt(fx*fx + fy*fy)
        
        if magnitude < 0.1:  # Too small to draw
            painter.restore()
            return
            
        # Scale the vector for display
        display_scale = scale * 50.0 / max(magnitude, 1.0)
        end_x = position.x() + fx * display_scale
        end_y = position.y() + fy * display_scale
        end_point = QPointF(end_x, end_y)
        
        # Draw force vector
        painter.setPen(QPen(self.settings.force_color, self.settings.medium_line))
        painter.drawLine(position, end_point)
        
        # Draw arrowhead
        angle = math.atan2(fy, fx)
        arrow_length = 12
        arrow_angle = 0.4
        
        arrow_p1 = QPointF(
            end_x - arrow_length * math.cos(angle - arrow_angle),
            end_y - arrow_length * math.sin(angle - arrow_angle)
        )
        arrow_p2 = QPointF(
            end_x - arrow_length * math.cos(angle + arrow_angle),
            end_y - arrow_length * math.sin(angle + arrow_angle)
        )
        
        painter.setBrush(QBrush(self.settings.force_color))
        arrow_polygon = QPolygonF([end_point, arrow_p1, arrow_p2])
        painter.drawPolygon(arrow_polygon)
        
        # Force magnitude annotation
        painter.setPen(QPen(self.settings.text_color, self.settings.thin_line))
        font = QFont("Arial", 9)
        painter.setFont(font)
        
        # Position text to avoid overlapping with vector
        text_x = (position.x() + end_x) / 2 + 10
        text_y = (position.y() + end_y) / 2 - 5
        painter.drawText(int(text_x), int(text_y), f"F={magnitude:.1f}N")
        
        painter.restore()
        
    def draw_velocity_vector(self, painter: QPainter, position: QPointF,
                           velocity: Tuple[float, float], scale: float = 1.0):
        """Draw velocity vector"""
        if velocity[0] == 0 and velocity[1] == 0:
            return
            
        painter.save()
        
        vx, vy = velocity
        magnitude = math.sqrt(vx*vx + vy*vy)
        
        if magnitude < 0.1:
            painter.restore()
            return
            
        # Scale and draw
        display_scale = scale * 30.0 / max(magnitude, 1.0)
        end_point = QPointF(
            position.x() + vx * display_scale,
            position.y() + vy * display_scale
        )
        
        painter.setPen(QPen(self.settings.velocity_color, self.settings.thin_line, Qt.PenStyle.DashLine))
        painter.drawLine(position, end_point)
        
        # Simple arrow
        angle = math.atan2(vy, vx)
        arrow_size = 6
        arrow_p1 = QPointF(
            end_point.x() - arrow_size * math.cos(angle - 0.5),
            end_point.y() - arrow_size * math.sin(angle - 0.5)
        )
        arrow_p2 = QPointF(
            end_point.x() - arrow_size * math.cos(angle + 0.5),
            end_point.y() - arrow_size * math.sin(angle + 0.5)
        )
        
        painter.drawLine(end_point, arrow_p1)
        painter.drawLine(end_point, arrow_p2)
        
        painter.restore()
        
    def draw_dimension_line(self, painter: QPainter, start: QPointF, end: QPointF, 
                          text: str, offset: float = 20.0):
        """Draw engineering-style dimension line"""
        painter.save()
        
        # Calculate dimension line position
        mid_x = (start.x() + end.x()) / 2
        mid_y = (start.y() + end.y()) / 2
        
        # Calculate perpendicular offset
        length = math.sqrt((end.x() - start.x())**2 + (end.y() - start.y())**2)
        if length == 0:
            painter.restore()
            return
            
        # Unit perpendicular vector
        perp_x = -(end.y() - start.y()) / length * offset
        perp_y = (end.x() - start.x()) / length * offset
        
        # Dimension line endpoints
        dim_start = QPointF(start.x() + perp_x, start.y() + perp_y)
        dim_end = QPointF(end.x() + perp_x, end.y() + perp_y)
        
        # Draw dimension line
        painter.setPen(QPen(self.settings.dimension_color, self.settings.thin_line))
        painter.drawLine(dim_start, dim_end)
        
        # Draw extension lines
        painter.drawLine(start, QPointF(start.x() + perp_x * 1.2, start.y() + perp_y * 1.2))
        painter.drawLine(end, QPointF(end.x() + perp_x * 1.2, end.y() + perp_y * 1.2))
        
        # Draw dimension text
        text_pos = QPointF(mid_x + perp_x, mid_y + perp_y)
        
        painter.setPen(QPen(self.settings.text_color, self.settings.thin_line))
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        # Background for text
        metrics = QFontMetrics(font)
        text_rect = metrics.boundingRect(text)
        text_bg = QRectF(text_pos.x() - text_rect.width()/2 - 2,
                        text_pos.y() - text_rect.height()/2 - 2,
                        text_rect.width() + 4,
                        text_rect.height() + 4)
        
        painter.fillRect(text_bg, self.settings.background_color)
        painter.drawText(int(text_pos.x() - text_rect.width()/2), 
                        int(text_pos.y() + text_rect.height()/4), text)
        
        painter.restore()
        
    def draw_motion_trail(self, painter: QPainter, points: List[QPointF], alpha_fade: bool = True):
        """Draw motion trail with fading effect"""
        if len(points) < 2:
            return
            
        painter.save()
        
        # Draw trail segments
        for i in range(1, len(points)):
            if alpha_fade:
                # Fade from newest to oldest
                alpha = int(255 * i / len(points))
                color = QColor(self.settings.motion_trail_color)
                color.setAlpha(alpha)
            else:
                color = self.settings.motion_trail_color
                
            painter.setPen(QPen(color, self.settings.thin_line))
            painter.drawLine(points[i-1], points[i])
            
        # Draw points
        painter.setBrush(QBrush(self.settings.motion_trail_color))
        painter.setPen(QPen(self.settings.motion_trail_color, self.settings.thin_line))
        for point in points[::5]:  # Every 5th point
            painter.drawEllipse(point, 2, 2)
            
        painter.restore()
        
    def draw_info_panel(self, painter: QPainter, info: Dict[str, str], 
                       position: QPointF = None):
        """Draw information panel with mechanism data"""
        if not info:
            return
            
        painter.save()
        
        # Default position (top-left corner)
        if position is None:
            position = QPointF(10, 10)
            
        # Calculate panel size
        font = QFont("Arial", 10)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        
        max_width = 0
        total_height = 0
        line_height = metrics.height() + 4
        
        for key, value in info.items():
            text = f"{key}: {value}"
            width = metrics.horizontalAdvance(text)
            max_width = max(max_width, width)
            total_height += line_height
            
        # Draw panel background
        panel_rect = QRectF(position.x() - 5, position.y() - 5,
                           max_width + 15, total_height + 10)
        
        painter.fillRect(panel_rect, QColor(255, 255, 255, 240))
        painter.setPen(QPen(self.settings.dimension_color, self.settings.thin_line))
        painter.drawRect(panel_rect)
        
        # Draw info text
        painter.setPen(QPen(self.settings.text_color, self.settings.thin_line))
        y_offset = position.y() + line_height
        
        for key, value in info.items():
            text = f"{key}: {value}"
            painter.drawText(int(position.x()), int(y_offset), text)
            y_offset += line_height
            
        painter.restore()
        
    def update_physics_data(self, forces: Dict, velocities: Dict, constraints: List = None):
        """Update physics visualization data"""
        self.forces = forces or {}
        self.velocities = velocities or {}
        self.constraints = constraints or []
        
    def set_selection(self, selected_elements: set):
        """Set selected elements for highlighting"""
        self.selected_elements = selected_elements
        
    def set_hover(self, hover_element):
        """Set hovered element for highlighting"""
        self.hover_element = hover_element