"""Zoom and pan handling for the image view."""

import math
import logging
from typing import Optional
from PyQt6.QtCore import Qt, QEvent, QPointF
from PyQt6.QtWidgets import QGraphicsView


class ZoomHandler:
    """Handles zoom and pan operations for a graphics view."""
    
    def __init__(self, view: QGraphicsView):
        self.view = view
        
        # Pinch gesture state
        self._pinch_mode = False
        self._pinch_start_view_scale = 1.0
        
        # Zoom control variables
        self._zoom_level = 0
        self._zoom_factor_base = 1.05  # Base factor for low sensitivity (each step is 5% zoom)
        self._min_zoom_level = -47  # Approx 1.05^-47 ~= 0.1
        self._max_zoom_level = 47   # Approx 1.05^47 ~= 10.0
    
    def handle_gesture_event(self, event: QEvent) -> bool:
        """Handle pinch gestures."""
        gesture = event.gesture(Qt.GestureType.PinchGesture)
        if gesture:
            self._pinch_triggered(gesture)
            return True
        return False
    
    def _pinch_triggered(self, gesture):
        """Handle pinch gesture logic for zooming."""
        if gesture.state() == Qt.GestureState.GestureStarted:
            self._pinch_mode = True
            self._pinch_start_view_scale = self.view.transform().m11()
        elif gesture.state() == Qt.GestureState.GestureUpdated and self._pinch_mode:
            target_scale = self._pinch_start_view_scale * gesture.scaleFactor()
            
            # Clamp the target scale
            target_scale = max(
                self._zoom_factor_base**self._min_zoom_level,
                min(target_scale, self._zoom_factor_base**self._max_zoom_level),
            )
            target_scale = max(0.1, min(target_scale, 10.0))  # Absolute limits
            
            current_view_scale = self.view.transform().m11()
            if abs(target_scale - current_view_scale) > 0.001:
                zoom_factor_to_apply = target_scale / current_view_scale
                self.view.scale(zoom_factor_to_apply, zoom_factor_to_apply)
        elif gesture.state() == Qt.GestureState.GestureFinished:
            self._pinch_mode = False
            # Update zoom level to closest discrete step after pinch zooming
            current_scale = self.view.transform().m11()
            if (
                current_scale > 0
                and self._zoom_factor_base > 1
                and self._zoom_factor_base != 0
            ):
                closest_zoom_level = round(
                    math.log(current_scale, self._zoom_factor_base)
                )
                self._zoom_level = max(
                    self._min_zoom_level, min(closest_zoom_level, self._max_zoom_level)
                )
    
    def zoom(self, step: int):
        """Zooms the view by a given step, adjusting the discrete zoom level."""
        if step == 0:
            return
        
        new_zoom_level = self._zoom_level + step
        new_zoom_level = max(
            self._min_zoom_level, min(new_zoom_level, self._max_zoom_level)
        )
        
        if new_zoom_level != self._zoom_level:
            current_scale = self.view.transform().m11()
            target_scale = self._zoom_factor_base**new_zoom_level
            target_scale = max(0.1, min(target_scale, 10.0))  # Absolute limits
            
            if abs(target_scale - current_scale) < 0.00001 and (
                (step > 0 and self._zoom_level == self._max_zoom_level)
                or (step < 0 and self._zoom_level == self._min_zoom_level)
            ):
                self._zoom_level = new_zoom_level  # Ensure level is updated
                return
            
            if current_scale <= 0:  # Safeguard
                self.view.resetTransform()
                current_scale = 1.0
                self._zoom_level = 0
                effective_step = (
                    max(self._min_zoom_level, min(step, self._max_zoom_level))
                    if step != 0
                    else 0
                )
                new_zoom_level = self._zoom_level + effective_step
                new_zoom_level = max(
                    self._min_zoom_level, min(new_zoom_level, self._max_zoom_level)
                )
                target_scale = self._zoom_factor_base**new_zoom_level
                target_scale = max(0.1, min(target_scale, 10.0))
            
            factor_to_apply = (
                target_scale / current_scale if current_scale != 0 else target_scale
            )
            if abs(factor_to_apply - 1.0) > 0.000001:
                self.view.scale(factor_to_apply, factor_to_apply)
            
            self._zoom_level = new_zoom_level
            self.view.scene().update()
    
    def handle_wheel_event(self, delta: int):
        """Handle mouse wheel for zooming."""
        if self._pinch_mode:
            return
        
        step = 0
        if delta > 0:
            step = 1
        elif delta < 0:
            step = -1
        
        self.zoom(step)
    
    def reset_zoom(self):
        """Reset zoom to 100%."""
        self.view.resetTransform()
        self._zoom_level = 0
        
        # Calculate the required factor to reach 1.0 scale
        current_scale_m11 = self.view.transform().m11()
        if current_scale_m11 == 0:
            current_scale_m11 = 1.0
        
        factor_to_apply = 1.0 / current_scale_m11
        self.view.scale(factor_to_apply, factor_to_apply)
        self._zoom_level = 0
    
    def update_zoom_level_from_scale(self):
        """Update internal zoom level based on current view scale."""
        current_scale = self.view.transform().m11()
        if (
            current_scale > 0
            and self._zoom_factor_base > 1
            and self._zoom_factor_base != 0
        ):
            self._zoom_level = round(
                math.log(current_scale, self._zoom_factor_base)
            )
            self._zoom_level = max(
                self._min_zoom_level,
                min(self._zoom_level, self._max_zoom_level),
            )
        else:
            self._zoom_level = 0
    
    @property
    def is_in_pinch_mode(self) -> bool:
        """Check if currently in pinch mode."""
        return self._pinch_mode