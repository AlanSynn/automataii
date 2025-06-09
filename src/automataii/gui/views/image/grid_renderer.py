"""Grid rendering for the image view background."""

import logging
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QLineF


class GridRenderer:
    """Handles grid rendering for the view background."""
    
    def __init__(self, view):
        self.view = view
    
    def draw_grid(self, painter: QPainter, rect: QRectF):
        """Draws a grid background based on the current display unit."""
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        if self.view.display_unit == "cm":
            cm_to_inch = 1 / 2.54
            grid_size_pixels = int(self.view.dpi * cm_to_inch)  # 1 cm in pixels
        elif self.view.display_unit == "inch":
            grid_size_pixels = int(self.view.dpi)  # 1 inch in pixels
        else:  # Default to pixels or if unit is 'px'
            grid_size_pixels = 20  # Default pixel grid size
        
        if grid_size_pixels <= 0:  # Safety check
            grid_size_pixels = 20
            logging.warning(
                f"Calculated grid size is invalid ({grid_size_pixels}), defaulting to 20px."
            )
        
        light_pen = QPen(QColor(230, 230, 230), 1)
        dark_pen = QPen(QColor(200, 200, 200), 1.5)
        
        major_interval = 1 if self.view.display_unit in ["cm", "inch"] else 5
        
        visible_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        
        left = int(visible_rect.left() / grid_size_pixels) * grid_size_pixels
        top = int(visible_rect.top() / grid_size_pixels) * grid_size_pixels
        right = visible_rect.right()
        bottom = visible_rect.bottom()
        
        x = left
        count_v = int(round(visible_rect.left() / grid_size_pixels))
        while x < right:
            painter.setPen(dark_pen if count_v % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(x, top, x, bottom))
            x += grid_size_pixels
            count_v += 1
        
        y = top
        count_h = int(round(visible_rect.top() / grid_size_pixels))
        while y < bottom:
            painter.setPen(dark_pen if count_h % major_interval == 0 else light_pen)
            painter.drawLine(QLineF(left, y, right, y))
            y += grid_size_pixels
            count_h += 1
        
        painter.restore()