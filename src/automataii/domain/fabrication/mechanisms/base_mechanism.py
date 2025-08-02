"""
Base mechanism class for the mechanism dictionary.
All concrete mechanisms inherit from this class.
"""

import math
from abc import abstractmethod
from typing import Dict, List, Tuple, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import QGraphicsItem


class MechanismPoint:
    """Represents a point in the mechanism with position and constraints."""
    
    def __init__(self, x: float, y: float, fixed: bool = False):
        self.x = x
        self.y = y
        self.fixed = fixed
        self.connections: List['MechanismLink'] = []
    
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)
    
    def set_position(self, x: float, y: float):
        if not self.fixed:
            self.x = x
            self.y = y


class MechanismLink:
    """Represents a link between two points in the mechanism."""
    
    def __init__(self, point1: MechanismPoint, point2: MechanismPoint, length: Optional[float] = None):
        self.point1 = point1
        self.point2 = point2
        self.length = length or self._calculate_length()
        
        # Add this link to both points
        point1.connections.append(self)
        point2.connections.append(self)
    
    def _calculate_length(self) -> float:
        """Calculate the distance between the two points."""
        dx = self.point2.x - self.point1.x
        dy = self.point2.y - self.point1.y
        return math.sqrt(dx * dx + dy * dy)
    
    def get_length(self) -> float:
        return self.length
    
    def get_current_length(self) -> float:
        """Get the current distance between points (may differ from target length)."""
        return self._calculate_length()


class BaseMechanism(QObject):
    """
    Abstract base class for all mechanisms.
    
    Provides common functionality for mechanism animation, parameter management,
    and rendering.
    """
    
    # Signals for animation and state changes
    position_changed = pyqtSignal()
    parameter_changed = pyqtSignal(str, object)  # parameter_name, new_value
    animation_step = pyqtSignal(float)  # animation_time
    
    def __init__(self, mechanism_id: str, parameters: Optional[Dict[str, Any]] = None):
        super().__init__()
        
        self.mechanism_id = mechanism_id
        self.parameters = parameters or {}
        self.animation_time = 0.0
        self.animation_speed = 1.0
        self.is_animating = False
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animation_step)
        self.animation_timer.setInterval(16)  # ~60 FPS
        
        # Mechanism geometry
        self.points: List[MechanismPoint] = []
        self.links: List[MechanismLink] = []
        
        # Visual properties
        self.link_color = QColor(50, 50, 50)
        self.point_color = QColor(200, 50, 50)
        self.fixed_point_color = QColor(100, 100, 100)
        self.link_width = 3
        self.point_radius = 5
        
        # Initialize the mechanism
        self._initialize_geometry()
    
    def _initialize_geometry(self):
        """Initialize the mechanism's points and links. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _initialize_geometry")
    
    def _update_positions(self, time: float):
        """Update mechanism positions for the given animation time. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _update_positions")
    
    def get_parameter_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about this mechanism's parameters. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_parameter_info")
    
    def set_parameter(self, name: str, value: Any):
        """Set a mechanism parameter and trigger updates."""
        if name in self.parameters:
            old_value = self.parameters[name]
            self.parameters[name] = value
            
            if old_value != value:
                self._on_parameter_changed(name, value)
                self.parameter_changed.emit(name, value)
    
    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a mechanism parameter value."""
        return self.parameters.get(name, default)
    
    def _on_parameter_changed(self, name: str, value: Any):
        """Called when a parameter changes. Override in subclasses for custom behavior."""
        # Reinitialize geometry when parameters change
        self._initialize_geometry()
    
    def start_animation(self):
        """Start the mechanism animation."""
        self.is_animating = True
        self.animation_timer.start()
    
    def stop_animation(self):
        """Stop the mechanism animation."""
        self.is_animating = False
        self.animation_timer.stop()
    
    def reset_animation(self):
        """Reset animation to the beginning."""
        self.animation_time = 0.0
        self._update_positions(self.animation_time)
        self.position_changed.emit()
    
    def set_animation_speed(self, speed: float):
        """Set the animation speed multiplier."""
        self.animation_speed = max(0.1, min(5.0, speed))
    
    def _animation_step(self):
        """Internal animation step called by timer."""
        if self.is_animating:
            # Advance animation time
            dt = 0.016 * self.animation_speed  # ~16ms at 1x speed
            self.animation_time += dt
            
            # Update positions
            self._update_positions(self.animation_time)
            
            # Emit signals
            self.position_changed.emit()
            self.animation_step.emit(self.animation_time)
    
    def get_bounding_rect(self) -> Tuple[float, float, float, float]:
        """Get the bounding rectangle of the mechanism (min_x, min_y, width, height)."""
        if not self.points:
            return (0, 0, 100, 100)
        
        min_x = min(point.x for point in self.points)
        max_x = max(point.x for point in self.points)
        min_y = min(point.y for point in self.points)
        max_y = max(point.y for point in self.points)
        
        # Add some padding
        padding = 20
        return (min_x - padding, min_y - padding, 
                max_x - min_x + 2 * padding, max_y - min_y + 2 * padding)
    
    def render(self, painter: QPainter, scale: float = 1.0):
        """
        Render the mechanism using QPainter with enhanced mechanical appearance.
        
        Args:
            painter: QPainter instance for drawing
            scale: Scale factor for rendering
        """
        painter.save()
        
        # Scale the rendering
        painter.scale(scale, scale)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw links first with enhanced appearance
        self._draw_enhanced_links(painter)
        
        # Draw joints with bearings and bolts
        self._draw_enhanced_joints(painter)
        
        painter.restore()
    
    def _draw_enhanced_links(self, painter: QPainter):
        """Draw links with enhanced mechanical appearance."""
        for link in self.links:
            # Calculate link properties
            dx = link.point2.x - link.point1.x
            dy = link.point2.y - link.point1.y
            length = math.sqrt(dx*dx + dy*dy)
            
            if length < 0.1:
                continue
                
            # Link direction
            angle = math.atan2(dy, dx)
            
            # Draw main link body (thicker)
            link_width = 8
            link_color = QColor(70, 70, 70)  # Dark gray metal
            
            # Create link polygon for 3D effect
            half_width = link_width / 2
            
            # Calculate perpendicular offset
            perp_x = -math.sin(angle) * half_width
            perp_y = math.cos(angle) * half_width
            
            # Link corners
            x1, y1 = link.point1.x, link.point1.y
            x2, y2 = link.point2.x, link.point2.y
            
            link_points = [
                (x1 + perp_x, y1 + perp_y),
                (x2 + perp_x, y2 + perp_y),
                (x2 - perp_x, y2 - perp_y),
                (x1 - perp_x, y1 - perp_y)
            ]
            
            # Draw link body
            painter.setPen(QPen(link_color.darker(), 1))
            painter.setBrush(QBrush(link_color))
            
            from PyQt6.QtCore import QPointF
            from PyQt6.QtGui import QPolygonF
            polygon = QPolygonF([QPointF(x, y) for x, y in link_points])
            painter.drawPolygon(polygon)
            
            # Add highlight for 3D effect
            highlight_color = link_color.lighter(150)
            painter.setPen(QPen(highlight_color, 2))
            painter.drawLine(
                int(x1 + perp_x), int(y1 + perp_y),
                int(x2 + perp_x), int(y2 + perp_y)
            )
            
            # Add link center decoration
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Small rivet in center
            rivet_color = QColor(50, 50, 50)
            painter.setPen(QPen(rivet_color.darker(), 1))
            painter.setBrush(QBrush(rivet_color))
            painter.drawEllipse(int(center_x - 2), int(center_y - 2), 4, 4)
    
    def _draw_enhanced_joints(self, painter: QPainter):
        """Draw joints with bearings and mechanical details."""
        for point in self.points:
            if point.fixed:
                self._draw_fixed_joint(painter, point)
            else:
                self._draw_moving_joint(painter, point)
    
    def _draw_fixed_joint(self, painter: QPainter, point: MechanismPoint):
        """Draw a fixed joint with ground symbol."""
        # Main bearing
        bearing_radius = 12
        bearing_color = QColor(100, 100, 100)
        
        painter.setPen(QPen(bearing_color.darker(), 2))
        painter.setBrush(QBrush(bearing_color))
        painter.drawEllipse(
            int(point.x - bearing_radius), int(point.y - bearing_radius),
            bearing_radius * 2, bearing_radius * 2
        )
        
        # Inner bearing
        inner_radius = 6
        inner_color = QColor(80, 80, 80)
        painter.setBrush(QBrush(inner_color))
        painter.drawEllipse(
            int(point.x - inner_radius), int(point.y - inner_radius),
            inner_radius * 2, inner_radius * 2
        )
        
        # Ground symbol (hatched triangle)
        ground_size = 20
        ground_color = QColor(60, 60, 60)
        painter.setPen(QPen(ground_color, 3))
        painter.setBrush(QBrush(ground_color))
        
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF
        
        triangle = QPolygonF([
            QPointF(point.x - ground_size/2, point.y + bearing_radius + 5),
            QPointF(point.x + ground_size/2, point.y + bearing_radius + 5),
            QPointF(point.x, point.y + bearing_radius - ground_size/3)
        ])
        painter.drawPolygon(triangle)
        
        # Hatching lines
        painter.setPen(QPen(ground_color.darker(), 1))
        for i in range(4):
            offset = (i - 1.5) * 6
            painter.drawLine(
                int(point.x - ground_size/2 + offset), int(point.y + bearing_radius + 5),
                int(point.x - ground_size/2 + offset - 4), int(point.y + bearing_radius + 12)
            )
    
    def _draw_moving_joint(self, painter: QPainter, point: MechanismPoint):
        """Draw a moving joint with bearing and bolt."""
        # Outer bearing ring
        bearing_radius = 10
        bearing_color = QColor(120, 120, 120)
        
        painter.setPen(QPen(bearing_color.darker(), 2))
        painter.setBrush(QBrush(bearing_color))
        painter.drawEllipse(
            int(point.x - bearing_radius), int(point.y - bearing_radius),
            bearing_radius * 2, bearing_radius * 2
        )
        
        # Inner bearing
        inner_radius = 6
        inner_color = QColor(90, 90, 90)
        painter.setPen(QPen(inner_color.darker(), 1))
        painter.setBrush(QBrush(inner_color))
        painter.drawEllipse(
            int(point.x - inner_radius), int(point.y - inner_radius),
            inner_radius * 2, inner_radius * 2
        )
        
        # Center bolt
        bolt_radius = 3
        bolt_color = QColor(40, 40, 40)
        painter.setBrush(QBrush(bolt_color))
        painter.drawEllipse(
            int(point.x - bolt_radius), int(point.y - bolt_radius),
            bolt_radius * 2, bolt_radius * 2
        )
        
        # Bolt head highlight
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawArc(
            int(point.x - bolt_radius), int(point.y - bolt_radius),
            bolt_radius * 2, bolt_radius * 2,
            45 * 16, 90 * 16  # 45 to 135 degrees
        )
    
    def add_point(self, x: float, y: float, fixed: bool = False) -> MechanismPoint:
        """Add a point to the mechanism."""
        point = MechanismPoint(x, y, fixed)
        self.points.append(point)
        return point
    
    def add_link(self, point1: MechanismPoint, point2: MechanismPoint, 
                 length: Optional[float] = None) -> MechanismLink:
        """Add a link between two points."""
        link = MechanismLink(point1, point2, length)
        self.links.append(link)
        return link
    
    def clear_geometry(self):
        """Clear all points and links."""
        self.points.clear()
        self.links.clear()
    
    def get_description(self) -> str:
        """Get a description of the mechanism."""
        return f"{self.__class__.__name__} mechanism"
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get the current state of the mechanism for serialization."""
        return {
            "mechanism_id": self.mechanism_id,
            "parameters": self.parameters.copy(),
            "animation_time": self.animation_time,
            "animation_speed": self.animation_speed,
            "is_animating": self.is_animating
        }
    
    def set_state(self, state: Dict[str, Any]):
        """Set the mechanism state from serialized data."""
        self.parameters = state.get("parameters", {})
        self.animation_time = state.get("animation_time", 0.0)
        self.animation_speed = state.get("animation_speed", 1.0)
        self.is_animating = state.get("is_animating", False)
        
        # Reinitialize geometry with new parameters
        self._initialize_geometry()
        self._update_positions(self.animation_time)