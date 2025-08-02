"""
Enhanced mechanism renderer with physics visualization.
Provides visual feedback for forces, constraints, and motion.
"""

import math
from typing import List, Tuple, Optional
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPolygonF, QPainterPath
from automataii.domain.fabrication.mechanisms.base_mechanism import BaseMechanism, MechanismPoint, MechanismLink


class EnhancedMechanismRenderer:
    """Enhanced renderer for mechanism visualization with physics feedback."""
    
    def __init__(self):
        # Visual settings
        self.show_forces = True
        self.show_constraints = True
        self.show_velocity = True
        self.show_acceleration = False
        self.show_grid = True
        self.show_dimensions = True
        
        # Colors
        self.force_color = QColor(255, 100, 100, 180)  # Red with transparency
        self.velocity_color = QColor(100, 255, 100, 180)  # Green
        self.constraint_color = QColor(100, 100, 255, 100)  # Blue
        self.grid_color = QColor(200, 200, 200, 50)
        
        # Sizes
        self.force_scale = 0.5
        self.velocity_scale = 1.0
        self.arrow_size = 8
        
        # Physics data (calculated elsewhere)
        self.forces = {}  # point_id -> (fx, fy)
        self.velocities = {}  # point_id -> (vx, vy)
        self.stresses = {}  # link_id -> stress_value
        
    def render_enhanced(self, painter: QPainter, mechanism: BaseMechanism, scale: float = 1.0):
        """Render mechanism with enhanced visual feedback."""
        painter.save()
        painter.scale(scale, scale)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background grid
        if self.show_grid:
            self._draw_grid(painter, mechanism)
        
        # Draw constraint areas
        if self.show_constraints:
            self._draw_constraints(painter, mechanism)
        
        # Draw links with stress visualization
        self._draw_links_with_stress(painter, mechanism)
        
        # Draw points with enhanced styling
        self._draw_enhanced_points(painter, mechanism)
        
        # Draw force vectors
        if self.show_forces:
            self._draw_force_vectors(painter, mechanism)
        
        # Draw velocity vectors
        if self.show_velocity:
            self._draw_velocity_vectors(painter, mechanism)
        
        # Draw dimensions and measurements
        if self.show_dimensions:
            self._draw_dimensions(painter, mechanism)
        
        # Draw mechanism info
        self._draw_info_overlay(painter, mechanism)
        
        painter.restore()
    
    def _draw_grid(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw background grid for reference."""
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DotLine))
        
        # Get bounding rect
        bounds = mechanism.get_bounding_rect()
        x_min, y_min = bounds[0] - 50, bounds[1] - 50
        x_max, y_max = bounds[0] + bounds[2] + 50, bounds[1] + bounds[3] + 50
        
        # Draw vertical lines
        grid_size = 20
        x = int(x_min / grid_size) * grid_size
        while x <= x_max:
            painter.drawLine(int(x), int(y_min), int(x), int(y_max))
            x += grid_size
        
        # Draw horizontal lines
        y = int(y_min / grid_size) * grid_size
        while y <= y_max:
            painter.drawLine(int(x_min), int(y), int(x_max), int(y))
            y += grid_size
    
    def _draw_constraints(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw constraint visualization for fixed points."""
        painter.setPen(QPen(self.constraint_color, 2))
        painter.setBrush(QBrush(self.constraint_color))
        
        for point in mechanism.points:
            if point.fixed:
                # Draw ground symbol
                self._draw_ground_symbol(painter, point.x, point.y)
    
    def _draw_ground_symbol(self, painter: QPainter, x: float, y: float):
        """Draw ground/fixed constraint symbol."""
        # Draw triangular ground symbol
        size = 15
        triangle = QPolygonF([
            QPointF(x - size/2, y + 5),
            QPointF(x + size/2, y + 5),
            QPointF(x, y - size/2 + 5)
        ])
        painter.drawPolygon(triangle)
        
        # Draw hatching lines
        painter.setPen(QPen(self.constraint_color.darker(), 1))
        for i in range(4):
            offset = (i - 1.5) * 4
            painter.drawLine(
                int(x - size/2 + offset), int(y + 5),
                int(x - size/2 + offset - 3), int(y + 10)
            )
    
    def _draw_links_with_stress(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw links with thickness/color based on stress."""
        for i, link in enumerate(mechanism.links):
            # Get stress value (normalized 0-1)
            stress = self.stresses.get(i, 0.0)
            
            # Calculate thickness based on stress
            base_thickness = 3
            thickness = base_thickness + stress * 5
            
            # Color based on stress (blue=compression, red=tension)
            if stress > 0:  # Tension
                color = QColor(
                    int(255 * min(stress * 2, 1)),
                    int(100 * (1 - stress)),
                    100
                )
            else:  # Compression
                color = QColor(
                    100,
                    int(100 * (1 + stress)),
                    int(255 * min(-stress * 2, 1))
                )
            
            # Draw link
            pen = QPen(color, thickness)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            painter.drawLine(
                int(link.point1.x), int(link.point1.y),
                int(link.point2.x), int(link.point2.y)
            )
            
            # Draw link center decoration
            cx = (link.point1.x + link.point2.x) / 2
            cy = (link.point1.y + link.point2.y) / 2
            
            # Small circle at link center
            painter.setBrush(QBrush(color.lighter()))
            painter.drawEllipse(int(cx - 2), int(cy - 2), 4, 4)
    
    def _draw_enhanced_points(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw points with enhanced styling."""
        for point in mechanism.points:
            if point.fixed:
                # Fixed points - larger with double circle
                color = QColor(80, 80, 80)
                painter.setPen(QPen(color, 2))
                painter.setBrush(QBrush(color.lighter()))
                painter.drawEllipse(
                    int(point.x - 8), int(point.y - 8), 16, 16
                )
                painter.setBrush(QBrush(Qt.GlobalColor.white))
                painter.drawEllipse(
                    int(point.x - 4), int(point.y - 4), 8, 8
                )
            else:
                # Moving points - with motion blur effect
                color = QColor(50, 150, 250)
                
                # Draw motion trail
                if hasattr(point, 'prev_positions'):
                    painter.setPen(Qt.PenStyle.NoPen)
                    for i, (px, py) in enumerate(point.prev_positions[-5:]):
                        alpha = int(50 * (i + 1) / 5)
                        trail_color = QColor(color)
                        trail_color.setAlpha(alpha)
                        painter.setBrush(QBrush(trail_color))
                        size = 6 + i
                        painter.drawEllipse(
                            int(px - size/2), int(py - size/2), size, size
                        )
                
                # Draw main point
                painter.setPen(QPen(color.darker(), 2))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(
                    int(point.x - 6), int(point.y - 6), 12, 12
                )
    
    def _draw_force_vectors(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw force vectors at each point."""
        painter.setPen(QPen(self.force_color, 2))
        
        for i, point in enumerate(mechanism.points):
            if i in self.forces:
                fx, fy = self.forces[i]
                magnitude = math.sqrt(fx*fx + fy*fy)
                
                if magnitude > 0.1:  # Only draw significant forces
                    # Scale and draw arrow
                    end_x = point.x + fx * self.force_scale
                    end_y = point.y + fy * self.force_scale
                    
                    self._draw_arrow(
                        painter, point.x, point.y, end_x, end_y,
                        self.force_color, f"{magnitude:.1f}N"
                    )
    
    def _draw_velocity_vectors(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw velocity vectors at each point."""
        painter.setPen(QPen(self.velocity_color, 2))
        
        for i, point in enumerate(mechanism.points):
            if i in self.velocities and not point.fixed:
                vx, vy = self.velocities[i]
                magnitude = math.sqrt(vx*vx + vy*vy)
                
                if magnitude > 0.1:  # Only draw significant velocities
                    # Scale and draw arrow
                    end_x = point.x + vx * self.velocity_scale
                    end_y = point.y + vy * self.velocity_scale
                    
                    self._draw_arrow(
                        painter, point.x, point.y, end_x, end_y,
                        self.velocity_color
                    )
    
    def _draw_arrow(self, painter: QPainter, x1: float, y1: float, 
                    x2: float, y2: float, color: QColor, label: str = ""):
        """Draw an arrow from (x1,y1) to (x2,y2)."""
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        
        # Draw line
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Calculate arrow head
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = self.arrow_size
        arrow_angle = 0.5
        
        # Arrow head points
        ax1 = x2 - arrow_length * math.cos(angle - arrow_angle)
        ay1 = y2 - arrow_length * math.sin(angle - arrow_angle)
        ax2 = x2 - arrow_length * math.cos(angle + arrow_angle)
        ay2 = y2 - arrow_length * math.sin(angle + arrow_angle)
        
        # Draw arrow head
        arrow_head = QPolygonF([
            QPointF(x2, y2),
            QPointF(ax1, ay1),
            QPointF(ax2, ay2)
        ])
        painter.drawPolygon(arrow_head)
        
        # Draw label if provided
        if label:
            painter.setPen(QPen(color.darker(), 1))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(int((x1 + x2) / 2), int((y1 + y2) / 2), label)
    
    def _draw_dimensions(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw dimension lines for links."""
        painter.setPen(QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine))
        painter.setFont(QFont("Arial", 9))
        
        for link in mechanism.links:
            if link.length:
                # Calculate perpendicular offset for dimension line
                dx = link.point2.x - link.point1.x
                dy = link.point2.y - link.point1.y
                length = math.sqrt(dx*dx + dy*dy)
                
                if length > 0:
                    # Perpendicular unit vector
                    px = -dy / length * 15
                    py = dx / length * 15
                    
                    # Dimension line points
                    p1x = link.point1.x + px
                    p1y = link.point1.y + py
                    p2x = link.point2.x + px
                    p2y = link.point2.y + py
                    
                    # Draw dimension line
                    painter.drawLine(int(p1x), int(p1y), int(p2x), int(p2y))
                    
                    # Draw end marks
                    painter.drawLine(
                        int(link.point1.x), int(link.point1.y),
                        int(p1x), int(p1y)
                    )
                    painter.drawLine(
                        int(link.point2.x), int(link.point2.y),
                        int(p2x), int(p2y)
                    )
                    
                    # Draw length text
                    mid_x = (p1x + p2x) / 2
                    mid_y = (p1y + p2y) / 2
                    painter.drawText(
                        int(mid_x - 20), int(mid_y - 5),
                        40, 20,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{link.length:.0f}"
                    )
    
    def _draw_info_overlay(self, painter: QPainter, mechanism: BaseMechanism):
        """Draw mechanism information overlay."""
        painter.setPen(QPen(QColor(50, 50, 50), 1))
        painter.setFont(QFont("Arial", 10))
        
        # Get mechanism info
        info_text = f"{mechanism.__class__.__name__}"
        if hasattr(mechanism, 'crank_angle'):
            info_text += f"\nAngle: {math.degrees(mechanism.crank_angle):.1f}°"
        
        # Draw info box
        bounds = mechanism.get_bounding_rect()
        info_x = bounds[0] + 10
        info_y = bounds[1] + bounds[3] + 20
        
        painter.drawText(int(info_x), int(info_y), info_text)
    
    def update_physics_data(self, forces: dict, velocities: dict, stresses: dict):
        """Update physics visualization data."""
        self.forces = forces
        self.velocities = velocities
        self.stresses = stresses