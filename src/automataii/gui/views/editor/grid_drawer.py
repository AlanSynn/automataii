"""Grid drawing functionality for the editor view."""

import logging
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtCore import QRectF, QLineF, Qt

from .constants import (
    DEFAULT_PIXEL_GRID_SIZE,
    GRID_LIGHT_COLOR,
    GRID_DARK_COLOR,
    GRID_LIGHT_WIDTH,
    GRID_DARK_WIDTH,
    GRID_MAJOR_INTERVAL_PIXEL,
    GRID_MAJOR_INTERVAL_UNIT,
)


class GridDrawer:
    """Handles grid drawing for the editor view."""
    
    def __init__(self, view):
        self.view = view
        self.display_unit = "cm"
        self.dpi = 96
        
    def set_display_unit(self, unit: str):
        """Sets the display unit for the grid."""
        if unit.lower() in ["cm", "inch", "px"]:
            self.display_unit = unit.lower()
            logging.info(f"GridDrawer: Display unit set to {self.display_unit}")
        else:
            logging.warning(
                f"GridDrawer: Invalid display unit '{unit}'. Using current: {self.display_unit}"
            )
            
    def set_dpi(self, dpi: int):
        """Sets the DPI for grid calculations."""
        self.dpi = dpi
        
    def draw_background(self, painter: QPainter, rect: QRectF):
        """Draws a grid background based on the current display unit."""
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Calculate grid size in pixels
        grid_size_pixels = self._calculate_grid_size()
        
        if grid_size_pixels <= 0:  # Safety check
            grid_size_pixels = DEFAULT_PIXEL_GRID_SIZE
            logging.warning(
                f"Calculated grid size is invalid ({grid_size_pixels}), defaulting to {DEFAULT_PIXEL_GRID_SIZE}px."
            )
            
        # Set up pens
        light_pen = QPen(QColor(*GRID_LIGHT_COLOR), GRID_LIGHT_WIDTH)
        dark_pen = QPen(QColor(*GRID_DARK_COLOR), GRID_DARK_WIDTH)
        
        # Determine major interval
        major_interval = (
            GRID_MAJOR_INTERVAL_UNIT 
            if self.display_unit in ["cm", "inch"] 
            else GRID_MAJOR_INTERVAL_PIXEL
        )
        
        # Get visible area
        visible_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        
        # Calculate grid boundaries
        left = int(visible_rect.left() / grid_size_pixels) * grid_size_pixels
        top = int(visible_rect.top() / grid_size_pixels) * grid_size_pixels
        right = visible_rect.right()
        bottom = visible_rect.bottom()
        
        # Draw vertical lines
        self._draw_grid_lines(
            painter, left, right, top, bottom, 
            grid_size_pixels, major_interval, 
            light_pen, dark_pen, True
        )
        
        # Draw horizontal lines
        self._draw_grid_lines(
            painter, top, bottom, left, right,
            grid_size_pixels, major_interval,
            light_pen, dark_pen, False
        )
        
        painter.restore()
        
    def _calculate_grid_size(self) -> int:
        """Calculates grid size in pixels based on display unit and DPI."""
        if self.display_unit == "cm":
            cm_to_inch = 1 / 2.54
            return int(self.dpi * cm_to_inch)  # 1 cm in pixels
        elif self.display_unit == "inch":
            return int(self.dpi)  # 1 inch in pixels
        else:  # Default to pixels or if unit is 'px'
            return DEFAULT_PIXEL_GRID_SIZE
            
    def _draw_grid_lines(
        self, painter: QPainter, 
        start: float, end: float, 
        cross_start: float, cross_end: float,
        grid_size: int, major_interval: int,
        light_pen: QPen, dark_pen: QPen,
        is_vertical: bool
    ):
        """Draws a set of grid lines (either vertical or horizontal)."""
        position = start
        visible_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        
        # Calculate starting count for major line determination
        if is_vertical:
            count = int(round(visible_rect.left() / grid_size))
        else:
            count = int(round(visible_rect.top() / grid_size))
            
        while position < end:
            # Set pen based on whether this is a major line
            painter.setPen(dark_pen if count % major_interval == 0 else light_pen)
            
            # Draw the line
            if is_vertical:
                painter.drawLine(QLineF(position, cross_start, position, cross_end))
            else:
                painter.drawLine(QLineF(cross_start, position, cross_end, position))
                
            position += grid_size
            count += 1