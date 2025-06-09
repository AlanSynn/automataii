"""Widget for previewing automata base with mechanisms."""

from typing import Dict, Any, Optional, List
import math
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent


class BasePreviewWidget(QWidget):
    """Widget for 2D/3D preview of automata base."""
    
    # Signals
    mechanism_selected = pyqtSignal(str)  # Mechanism ID selected
    position_changed = pyqtSignal(str, float, float)  # Mechanism moved
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_config = {}
        self.mechanisms = {}  # ID -> placement info
        self.selected_mechanism = None
        self.view_mode = '2D'  # '2D' or '3D'
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self.dragging = False
        self.last_mouse_pos = None
        
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        
        # Control bar
        control_layout = QHBoxLayout()
        
        # View mode toggle
        self.mode_btn = QPushButton("Switch to 3D")
        self.mode_btn.clicked.connect(self._toggle_view_mode)
        control_layout.addWidget(self.mode_btn)
        
        # Zoom controls
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setMaximumWidth(30)
        zoom_in_btn.clicked.connect(lambda: self._zoom(1.2))
        control_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setMaximumWidth(30)
        zoom_out_btn.clicked.connect(lambda: self._zoom(0.8))
        control_layout.addWidget(zoom_out_btn)
        
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self._reset_view)
        control_layout.addWidget(reset_btn)
        
        control_layout.addStretch()
        
        # Info label
        self.info_label = QLabel("Ready")
        control_layout.addWidget(self.info_label)
        
        layout.addLayout(control_layout)
        
        # Set minimum size for preview area
        self.setMinimumSize(600, 400)
        self.setMouseTracking(True)
        
    def set_base_configuration(self, config: Dict[str, Any]):
        """Set the base configuration to preview."""
        self.base_config = config
        self.update()
        
    def add_mechanism(self, mechanism_id: str, placement_info: Dict[str, Any]):
        """Add a mechanism to the preview."""
        self.mechanisms[mechanism_id] = placement_info
        self.update()
        
    def remove_mechanism(self, mechanism_id: str):
        """Remove a mechanism from the preview."""
        if mechanism_id in self.mechanisms:
            del self.mechanisms[mechanism_id]
            if self.selected_mechanism == mechanism_id:
                self.selected_mechanism = None
            self.update()
            
    def clear_mechanisms(self):
        """Clear all mechanisms."""
        self.mechanisms.clear()
        self.selected_mechanism = None
        self.update()
        
    def paintEvent(self, event):
        """Paint the preview."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Transform to center coordinates
        painter.translate(self.width() / 2, self.height() / 2)
        painter.translate(self.offset)
        painter.scale(self.scale, self.scale)
        
        if self.view_mode == '2D':
            self._draw_2d(painter)
        else:
            self._draw_3d(painter)
            
    def _draw_2d(self, painter: QPainter):
        """Draw 2D top-down view."""
        # Draw grid
        self._draw_grid(painter)
        
        # Draw base
        base_type = self.base_config.get('type', 'rectangular')
        
        if base_type == 'rectangular':
            width = self.base_config.get('width', 200)
            depth = self.base_config.get('depth', 150)
            
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.setBrush(QBrush(QColor(200, 200, 200, 100)))
            painter.drawRect(int(-width/2), int(-depth/2), width, depth)
            
        elif base_type == 'cylindrical':
            radius = self.base_config.get('radius', 100)
            
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.setBrush(QBrush(QColor(200, 200, 200, 100)))
            painter.drawEllipse(QPointF(0, 0), radius, radius)
            
        # Draw mechanisms
        for mech_id, info in self.mechanisms.items():
            self._draw_mechanism_2d(painter, mech_id, info)
            
    def _draw_3d(self, painter: QPainter):
        """Draw pseudo-3D isometric view."""
        # Simple isometric projection
        iso_angle = math.radians(30)
        
        # Draw base in isometric
        base_type = self.base_config.get('type', 'rectangular')
        
        if base_type == 'rectangular':
            width = self.base_config.get('width', 200)
            depth = self.base_config.get('depth', 150)
            height = self.base_config.get('height', 50)
            
            # Calculate isometric points
            points = []
            # Bottom face
            points.append(QPointF(-width/2, depth/2))
            points.append(QPointF(width/2, depth/2))
            points.append(QPointF(width/2, -depth/2))
            points.append(QPointF(-width/2, -depth/2))
            
            # Transform to isometric
            iso_points = []
            for p in points:
                x_iso = p.x() * math.cos(iso_angle) - p.y() * math.sin(iso_angle)
                y_iso = p.x() * math.sin(iso_angle) * 0.5 + p.y() * math.cos(iso_angle) * 0.5
                iso_points.append(QPointF(x_iso, y_iso))
                
            # Draw bottom face
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.setBrush(QBrush(QColor(180, 180, 180)))
            painter.drawPolygon(iso_points)
            
            # Draw vertical edges
            for i, p in enumerate(iso_points):
                painter.drawLine(p, QPointF(p.x(), p.y() - height))
                
            # Draw top face
            top_points = [QPointF(p.x(), p.y() - height) for p in iso_points]
            painter.setBrush(QBrush(QColor(220, 220, 220)))
            painter.drawPolygon(top_points)
            
        # Draw mechanisms in 3D
        for mech_id, info in self.mechanisms.items():
            self._draw_mechanism_3d(painter, mech_id, info)
            
    def _draw_grid(self, painter: QPainter):
        """Draw background grid."""
        grid_size = 50
        grid_count = 10
        
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        
        for i in range(-grid_count, grid_count + 1):
            x = i * grid_size
            painter.drawLine(x, -grid_count * grid_size, x, grid_count * grid_size)
            painter.drawLine(-grid_count * grid_size, x, grid_count * grid_size, x)
            
    def _draw_mechanism_2d(self, painter: QPainter, mech_id: str, info: Dict[str, Any]):
        """Draw a mechanism in 2D."""
        pos = info.get('position', (0, 0, 0))
        connections = info.get('connection_points', [])
        
        # Highlight if selected
        if mech_id == self.selected_mechanism:
            painter.setPen(QPen(QColor(0, 100, 200), 3))
        else:
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 2))
            
        # Draw mechanism bounding box (simplified)
        size = 40
        painter.drawRect(int(pos[0] - size/2), int(pos[1] - size/2), size, size)
        
        # Draw connection points
        for conn in connections:
            cp_pos = conn.get('position', (0, 0, 0))
            cp_type = conn.get('type', 'support')
            
            color = {
                'motor': QColor(255, 0, 0),
                'support': QColor(0, 0, 255),
                'output': QColor(0, 255, 0)
            }.get(cp_type, QColor(128, 128, 128))
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(), 1))
            
            x = pos[0] + cp_pos[0]
            y = pos[1] + cp_pos[1]
            painter.drawEllipse(QPointF(x, y), 5, 5)
            
    def _draw_mechanism_3d(self, painter: QPainter, mech_id: str, info: Dict[str, Any]):
        """Draw a mechanism in pseudo-3D."""
        # Similar to 2D but with height offset
        pos = info.get('position', (0, 0, 0))
        
        # Simple height representation
        base_height = self.base_config.get('height', 50)
        y_offset = -base_height - 20
        
        if mech_id == self.selected_mechanism:
            painter.setPen(QPen(QColor(0, 100, 200), 3))
        else:
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 2))
            
        size = 40
        painter.drawRect(int(pos[0] - size/2), int(pos[1] - size/2 + y_offset), size, size)
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a mechanism
            click_pos = self._screen_to_world(event.position())
            
            for mech_id, info in self.mechanisms.items():
                pos = info.get('position', (0, 0, 0))
                if abs(click_pos.x() - pos[0]) < 20 and abs(click_pos.y() - pos[1]) < 20:
                    self.selected_mechanism = mech_id
                    self.mechanism_selected.emit(mech_id)
                    self.update()
                    return
                    
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.dragging = True
            self.last_mouse_pos = event.position()
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move."""
        if self.dragging and self.last_mouse_pos:
            delta = event.position() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = event.position()
            self.update()
            
        # Update info label
        world_pos = self._screen_to_world(event.position())
        self.info_label.setText(f"X: {world_pos.x():.1f}, Y: {world_pos.y():.1f}")
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.dragging = False
            
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(0.9)
            
    def _screen_to_world(self, screen_pos: QPointF) -> QPointF:
        """Convert screen coordinates to world coordinates."""
        x = (screen_pos.x() - self.width() / 2 - self.offset.x()) / self.scale
        y = (screen_pos.y() - self.height() / 2 - self.offset.y()) / self.scale
        return QPointF(x, y)
        
    def _toggle_view_mode(self):
        """Toggle between 2D and 3D view."""
        if self.view_mode == '2D':
            self.view_mode = '3D'
            self.mode_btn.setText("Switch to 2D")
        else:
            self.view_mode = '2D'
            self.mode_btn.setText("Switch to 3D")
        self.update()
        
    def _zoom(self, factor: float):
        """Zoom the view."""
        self.scale *= factor
        self.scale = max(0.1, min(5.0, self.scale))
        self.update()
        
    def _reset_view(self):
        """Reset view to default."""
        self.scale = 1.0
        self.offset = QPointF(0, 0)
        self.update()