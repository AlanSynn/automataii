"""Zoom and pan control for the editor view."""

import math
import logging
from PyQt6.QtCore import Qt, QPointF, QObject, pyqtSignal
from PyQt6.QtGui import QWheelEvent, QMouseEvent

from .constants import (
    ZOOM_FACTOR_BASE,
    MIN_ZOOM_LEVEL,
    MAX_ZOOM_LEVEL,
    ABSOLUTE_MIN_SCALE,
    ABSOLUTE_MAX_SCALE,
    PAN_SENSITIVITY,
    PAN_MULTIPLIER
)


class ZoomController(QObject):
    """Handles zoom and pan operations for the editor view."""
    
    zoom_changed = pyqtSignal(float)  # Emits new zoom scale
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
        # Zoom control variables
        self._zoom_level = 0
        self._zoom_factor_base = ZOOM_FACTOR_BASE
        self._min_zoom_level = MIN_ZOOM_LEVEL
        self._max_zoom_level = MAX_ZOOM_LEVEL
        
        # Pinch-to-zoom variables
        self._pinch_mode = False
        self._pinch_start_view_scale = 1.0
        
        # Panning variables
        self._panning = False
        self._pan_start_pos = QPointF()
        self._pan_sensitivity = PAN_SENSITIVITY
        
    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Handles mouse wheel for zooming. Returns True if handled."""
        if self._pinch_mode:
            return False
            
        delta = event.angleDelta().y()
        step = 0
        if delta > 0:
            step = 1
        elif delta < 0:
            step = -1
            
        if step != 0:
            self.zoom(step)
            return True
        return False
        
    def zoom(self, step: int):
        """Zooms the view by a given step."""
        if step == 0:
            return
            
        new_zoom_level = self._zoom_level + step
        new_zoom_level = max(self._min_zoom_level, min(new_zoom_level, self._max_zoom_level))
        
        if new_zoom_level != self._zoom_level:
            current_scale = self.view.transform().m11()
            target_scale = self._zoom_factor_base ** new_zoom_level
            target_scale = max(ABSOLUTE_MIN_SCALE, min(target_scale, ABSOLUTE_MAX_SCALE))
            
            # Check if already at limits
            if abs(target_scale - current_scale) < 0.00001 and (
                (step > 0 and self._zoom_level == self._max_zoom_level) or
                (step < 0 and self._zoom_level == self._min_zoom_level)
            ):
                self._zoom_level = new_zoom_level
                return
                
            if current_scale <= 0:  # Safeguard
                self.view.resetTransform()
                current_scale = 1.0
                self._zoom_level = 0
                
            factor_to_apply = target_scale / current_scale if current_scale != 0 else target_scale
            
            if abs(factor_to_apply - 1.0) > 0.000001:
                self.view.scale(factor_to_apply, factor_to_apply)
                
            self._zoom_level = new_zoom_level
            self.zoom_changed.emit(self.view.transform().m11())
            self.view.scene().update()
            
    def start_pan(self, pos: QPointF):
        """Starts panning operation."""
        self._panning = True
        self._pan_start_pos = pos
        self.view.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        
    def update_pan(self, pos: QPointF):
        """Updates pan position."""
        if not self._panning:
            return
            
        delta = pos - self._pan_start_pos
        self._pan_start_pos = pos
        
        hs = self.view.horizontalScrollBar()
        vs = self.view.verticalScrollBar()
        
        hs.setValue(hs.value() - int(delta.x() * self._pan_sensitivity * PAN_MULTIPLIER))
        vs.setValue(vs.value() - int(delta.y() * self._pan_sensitivity * PAN_MULTIPLIER))
        
    def end_pan(self):
        """Ends panning operation."""
        self._panning = False
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        
    def is_panning(self) -> bool:
        """Returns True if currently panning."""
        return self._panning
        
    def reset_view(self):
        """Resets zoom and pan to default."""
        self.view.resetTransform()
        self._zoom_level = 0
        self.view.centerOn(0, 0)
        self.zoom_changed.emit(1.0)
        
    def zoom_to_fit(self):
        """Zooms to fit all items in the view."""
        if not self.view.scene():
            return
            
        rect = self.view.scene().itemsBoundingRect()
        if not rect.isValid():
            return
            
        # Add padding
        padding = 20
        rect.adjust(-padding, -padding, padding, padding)
        
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        # Update zoom level to match new scale
        current_scale = self.view.transform().m11()
        if current_scale > 0 and self._zoom_factor_base > 1:
            self._zoom_level = round(math.log(current_scale, self._zoom_factor_base))
            self._zoom_level = max(self._min_zoom_level, min(self._zoom_level, self._max_zoom_level))
        else:
            self._zoom_level = 0
            
        self.zoom_changed.emit(current_scale)
        
    def set_zoom_level(self, zoom_factor: float):
        """Sets the zoom level directly."""
        current_transform = self.view.transform()
        current_scale_x = current_transform.m11()
        current_scale_y = current_transform.m22()
        
        if current_scale_x == 0 or current_scale_y == 0:
            logging.warning("Current scale is zero, resetting to new zoom_factor.")
            self.view.resetTransform()
            self.view.scale(zoom_factor, zoom_factor)
            return
            
        scale_x_needed = zoom_factor / current_scale_x
        scale_y_needed = zoom_factor / current_scale_y
        
        self.view.scale(scale_x_needed, scale_y_needed)
        
        # Update internal zoom level
        if zoom_factor > 0 and self._zoom_factor_base > 1:
            self._zoom_level = round(math.log(zoom_factor, self._zoom_factor_base))
            self._zoom_level = max(self._min_zoom_level, min(self._zoom_level, self._max_zoom_level))
            
        logging.info(f"Zoom set to {zoom_factor:.2f}x")
        
    def handle_pinch_start(self):
        """Handles the start of a pinch gesture."""
        self._pinch_mode = True
        self._pinch_start_view_scale = self.view.transform().m11()
        
    def handle_pinch_update(self, scale_factor: float):
        """Handles pinch gesture update."""
        if not self._pinch_mode:
            return
            
        target_scale = self._pinch_start_view_scale * scale_factor
        target_scale = max(ABSOLUTE_MIN_SCALE, min(target_scale, ABSOLUTE_MAX_SCALE))
        
        current_view_scale = self.view.transform().m11()
        if abs(target_scale - current_view_scale) > 0.001:
            zoom_factor_to_apply = target_scale / current_view_scale
            self.view.scale(zoom_factor_to_apply, zoom_factor_to_apply)
            self.zoom_changed.emit(self.view.transform().m11())
            
    def handle_pinch_end(self):
        """Handles the end of a pinch gesture."""
        self._pinch_mode = False
        
        # Update zoom level to match current scale
        current_scale = self.view.transform().m11()
        if current_scale > 0 and self._zoom_factor_base > 1:
            closest_zoom_level = round(math.log(current_scale, self._zoom_factor_base))
            self._zoom_level = max(self._min_zoom_level, min(closest_zoom_level, self._max_zoom_level))