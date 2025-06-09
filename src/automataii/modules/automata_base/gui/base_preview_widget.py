"""
Base preview widget for visualizing base configurations.
"""

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
    from PyQt6.QtCore import Qt, QRectF, pyqtSignal
    from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
    from PyQt5.QtCore import Qt, QRectF, pyqtSignal
    from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont

import sys
import math
from typing import Optional

from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.enums.base_types import BaseType


class BasePreviewWidget(QWidget):
    """Widget for previewing base configurations."""
    
    # Signals
    zoom_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        """Initialize the preview widget."""
        super().__init__(parent)
        self.base_config: Optional[BaseConfiguration] = None
        self.zoom_level = 1.0
        self.show_dimensions = True
        self.show_mounting_points = True
        self.show_grid = True
        self.grid_size = 10  # mm
        
        self.setup_ui()
        self.setMinimumSize(400, 400)
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Preview area
        self.preview_area = QWidget()
        self.preview_area.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.preview_area.setMinimumSize(380, 350)
        layout.addWidget(self.preview_area, 1)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_label)
        
        layout.addLayout(zoom_layout)
    
    def set_base_configuration(self, config: BaseConfiguration):
        """Set the base configuration to preview."""
        self.base_config = config
        self.update()
    
    def paintEvent(self, event):
        """Paint the preview."""
        super().paintEvent(event)
        
        if not self.base_config:
            return
        
        painter = QPainter(self.preview_area)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        widget_rect = self.preview_area.rect()
        widget_width = widget_rect.width()
        widget_height = widget_rect.height()
        
        # Get base dimensions in mm
        base_width = self.base_config.dimensions.width
        base_height = self.base_config.dimensions.height if hasattr(
            self.base_config.dimensions, 'height'
        ) else self.base_config.dimensions.depth
        
        # Calculate scale to fit in widget
        scale_x = (widget_width - 40) / base_width
        scale_y = (widget_height - 40) / base_height
        base_scale = min(scale_x, scale_y) * self.zoom_level
        
        # Center the base
        offset_x = (widget_width - base_width * base_scale) / 2
        offset_y = (widget_height - base_height * base_scale) / 2
        
        # Draw grid if enabled
        if self.show_grid:
            self._draw_grid(painter, widget_rect, base_scale)
        
        # Draw base outline
        self._draw_base_outline(painter, offset_x, offset_y, base_scale)
        
        # Draw mounting points
        if self.show_mounting_points and self.base_config.mounting_points:
            self._draw_mounting_points(painter, offset_x, offset_y, base_scale)
        
        # Draw dimensions
        if self.show_dimensions:
            self._draw_dimensions(painter, offset_x, offset_y, base_scale)
        
        # Draw info text
        self._draw_info_text(painter, widget_rect)
    
    def _draw_grid(self, painter: QPainter, rect: QRectF, scale: float):
        """Draw background grid."""
        pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        grid_spacing = self.grid_size * scale
        
        # Vertical lines
        x = grid_spacing
        while x < rect.width():
            painter.drawLine(int(x), 0, int(x), rect.height())
            x += grid_spacing
        
        # Horizontal lines
        y = grid_spacing
        while y < rect.height():
            painter.drawLine(0, int(y), rect.width(), int(y))
            y += grid_spacing
    
    def _draw_base_outline(self, painter: QPainter, offset_x: float, offset_y: float, scale: float):
        """Draw the base outline."""
        pen = QPen(QColor(0, 0, 0), 2)
        painter.setPen(pen)
        
        base_type = self.base_config.base_type
        width = self.base_config.dimensions.width * scale
        height = self.base_config.dimensions.height * scale if hasattr(
            self.base_config.dimensions, 'height'
        ) else self.base_config.dimensions.depth * scale
        
        if base_type == BaseType.FLAT_RECTANGULAR:
            painter.drawRect(int(offset_x), int(offset_y), int(width), int(height))
            
        elif base_type == BaseType.FLAT_CIRCULAR:
            # Draw circle
            diameter = min(width, height)
            center_x = offset_x + width / 2
            center_y = offset_y + height / 2
            painter.drawEllipse(
                int(center_x - diameter / 2),
                int(center_y - diameter / 2),
                int(diameter),
                int(diameter)
            )
            
        elif base_type in [BaseType.BOX_OPEN, BaseType.BOX_ENCLOSED]:
            # Draw box with 3D effect
            painter.drawRect(int(offset_x), int(offset_y), int(width), int(height))
            
            # Draw depth lines for 3D effect
            depth_offset = 20
            pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            # Top-right corner
            painter.drawLine(
                int(offset_x + width), int(offset_y),
                int(offset_x + width + depth_offset), int(offset_y - depth_offset)
            )
            # Bottom-right corner
            painter.drawLine(
                int(offset_x + width), int(offset_y + height),
                int(offset_x + width + depth_offset), int(offset_y + height - depth_offset)
            )
            # Top edge
            painter.drawLine(
                int(offset_x + width + depth_offset), int(offset_y - depth_offset),
                int(offset_x + depth_offset), int(offset_y - depth_offset)
            )
            # Right edge
            painter.drawLine(
                int(offset_x + width + depth_offset), int(offset_y - depth_offset),
                int(offset_x + width + depth_offset), int(offset_y + height - depth_offset)
            )
            
        elif base_type == BaseType.PEDESTAL:
            # Draw tapered pedestal
            taper = 0.7
            top_width = width * taper
            top_offset = (width - top_width) / 2
            
            points = [
                (offset_x, offset_y + height),  # Bottom left
                (offset_x + width, offset_y + height),  # Bottom right
                (offset_x + width - top_offset, offset_y),  # Top right
                (offset_x + top_offset, offset_y),  # Top left
            ]
            
            for i in range(len(points)):
                next_i = (i + 1) % len(points)
                painter.drawLine(
                    int(points[i][0]), int(points[i][1]),
                    int(points[next_i][0]), int(points[next_i][1])
                )
                
        elif base_type == BaseType.WALL_MOUNTED:
            # Draw wall mount with brackets
            painter.drawRect(int(offset_x), int(offset_y), int(width), int(height))
            
            # Draw mounting brackets
            bracket_size = min(width, height) * 0.15
            bracket_pen = QPen(QColor(50, 50, 50), 2)
            painter.setPen(bracket_pen)
            
            # Top-left bracket
            painter.drawRect(
                int(offset_x - 10),
                int(offset_y - 10),
                int(bracket_size),
                int(bracket_size)
            )
            # Top-right bracket
            painter.drawRect(
                int(offset_x + width - bracket_size + 10),
                int(offset_y - 10),
                int(bracket_size),
                int(bracket_size)
            )
    
    def _draw_mounting_points(self, painter: QPainter, offset_x: float, offset_y: float, scale: float):
        """Draw mounting points."""
        pen = QPen(QColor(255, 0, 0), 1)
        painter.setPen(pen)
        brush = QBrush(QColor(255, 200, 200))
        painter.setBrush(brush)
        
        for mp in self.base_config.mounting_points:
            x = offset_x + mp.position.x * scale
            y = offset_y + mp.position.y * scale
            radius = mp.hole_diameter * scale / 2
            
            # Draw circle for hole
            painter.drawEllipse(
                int(x - radius),
                int(y - radius),
                int(radius * 2),
                int(radius * 2)
            )
            
            # Draw crosshair
            painter.drawLine(int(x - radius - 5), int(y), int(x + radius + 5), int(y))
            painter.drawLine(int(x), int(y - radius - 5), int(x), int(y + radius + 5))
            
            # Draw thread type label
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(int(x + radius + 5), int(y - 5), mp.thread_type or "")
    
    def _draw_dimensions(self, painter: QPainter, offset_x: float, offset_y: float, scale: float):
        """Draw dimension lines and labels."""
        pen = QPen(QColor(0, 0, 255), 1)
        painter.setPen(pen)
        
        width = self.base_config.dimensions.width * scale
        height = self.base_config.dimensions.height * scale if hasattr(
            self.base_config.dimensions, 'height'
        ) else self.base_config.dimensions.depth * scale
        
        # Width dimension
        dim_offset = 20
        y_pos = offset_y + height + dim_offset
        
        # Draw dimension line
        painter.drawLine(int(offset_x), int(y_pos), int(offset_x + width), int(y_pos))
        
        # Draw end markers
        painter.drawLine(int(offset_x), int(y_pos - 5), int(offset_x), int(y_pos + 5))
        painter.drawLine(int(offset_x + width), int(y_pos - 5), int(offset_x + width), int(y_pos + 5))
        
        # Draw dimension text
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        
        width_text = f"{self.base_config.dimensions.width} {self.base_config.dimensions.unit.value}"
        text_rect = painter.fontMetrics().boundingRect(width_text)
        painter.drawText(
            int(offset_x + width / 2 - text_rect.width() / 2),
            int(y_pos - 5),
            width_text
        )
        
        # Height dimension
        x_pos = offset_x + width + dim_offset
        
        # Draw dimension line
        painter.drawLine(int(x_pos), int(offset_y), int(x_pos), int(offset_y + height))
        
        # Draw end markers
        painter.drawLine(int(x_pos - 5), int(offset_y), int(x_pos + 5), int(offset_y))
        painter.drawLine(int(x_pos - 5), int(offset_y + height), int(x_pos + 5), int(offset_y + height))
        
        # Draw dimension text
        height_value = self.base_config.dimensions.height if hasattr(
            self.base_config.dimensions, 'height'
        ) else self.base_config.dimensions.depth
        height_text = f"{height_value} {self.base_config.dimensions.unit.value}"
        
        # Rotate text for vertical dimension
        painter.save()
        painter.translate(x_pos + 15, offset_y + height / 2)
        painter.rotate(-90)
        painter.drawText(0, 0, height_text)
        painter.restore()
    
    def _draw_info_text(self, painter: QPainter, rect: QRectF):
        """Draw information text."""
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        pen = QPen(QColor(100, 100, 100))
        painter.setPen(pen)
        
        info_text = f"{self.base_config.name} - {self.base_config.base_type.value}"
        painter.drawText(10, rect.height() - 10, info_text)
    
    def _on_zoom_changed(self, value):
        """Handle zoom slider change."""
        self.zoom_level = value / 100.0
        self.zoom_label.setText(f"{value}%")
        self.zoom_changed.emit(self.zoom_level)
        self.update()
    
    def set_show_dimensions(self, show: bool):
        """Set whether to show dimensions."""
        self.show_dimensions = show
        self.update()
    
    def set_show_mounting_points(self, show: bool):
        """Set whether to show mounting points."""
        self.show_mounting_points = show
        self.update()
    
    def set_show_grid(self, show: bool):
        """Set whether to show grid."""
        self.show_grid = show
        self.update()
    
    def export_image(self, filename: str, width: int = 800, height: int = 600):
        """Export the preview as an image."""
        if 'PyQt5' in sys.modules:
            from PyQt5.QtGui import QPixmap
        else:
            from PyQt6.QtGui import QPixmap
        
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.white)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Temporarily set size for rendering
        old_rect = self.preview_area.rect()
        self.preview_area.setGeometry(0, 0, width, height)
        
        # Trigger paint
        self.paintEvent(None)
        
        # Restore size
        self.preview_area.setGeometry(old_rect)
        
        painter.end()
        pixmap.save(filename)