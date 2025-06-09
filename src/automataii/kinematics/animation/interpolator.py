"""Interpolation utilities for smooth animation."""

import logging
from typing import Callable
import math

from PyQt6.QtCore import QPointF


class Interpolator:
    """Provides various interpolation methods for animation."""
    
    @staticmethod
    def linear(t: float) -> float:
        """Linear interpolation (no easing).
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return t
    
    @staticmethod
    def ease_in_quad(t: float) -> float:
        """Quadratic ease-in.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return t * t
    
    @staticmethod
    def ease_out_quad(t: float) -> float:
        """Quadratic ease-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return t * (2 - t)
    
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        """Quadratic ease-in-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        if t < 0.5:
            return 2 * t * t
        else:
            return -1 + (4 - 2 * t) * t
    
    @staticmethod
    def ease_in_cubic(t: float) -> float:
        """Cubic ease-in.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return t * t * t
    
    @staticmethod
    def ease_out_cubic(t: float) -> float:
        """Cubic ease-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        t -= 1
        return t * t * t + 1
    
    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        """Cubic ease-in-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        if t < 0.5:
            return 4 * t * t * t
        else:
            t = 2 * t - 2
            return 1 + t * t * t / 2
    
    @staticmethod
    def ease_in_sine(t: float) -> float:
        """Sinusoidal ease-in.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return 1 - math.cos(t * math.pi / 2)
    
    @staticmethod
    def ease_out_sine(t: float) -> float:
        """Sinusoidal ease-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return math.sin(t * math.pi / 2)
    
    @staticmethod
    def ease_in_out_sine(t: float) -> float:
        """Sinusoidal ease-in-out.
        
        Args:
            t: Progress value (0.0 to 1.0)
            
        Returns:
            Interpolated value
        """
        return -(math.cos(math.pi * t) - 1) / 2
    
    @staticmethod
    def interpolate_value(start: float, end: float, t: float,
                         easing: Callable[[float], float] = None) -> float:
        """Interpolate between two values.
        
        Args:
            start: Start value
            end: End value
            t: Progress (0.0 to 1.0)
            easing: Optional easing function
            
        Returns:
            Interpolated value
        """
        if easing:
            t = easing(t)
        return start + (end - start) * t
    
    @staticmethod
    def interpolate_point(start: QPointF, end: QPointF, t: float,
                         easing: Callable[[float], float] = None) -> QPointF:
        """Interpolate between two points.
        
        Args:
            start: Start point
            end: End point
            t: Progress (0.0 to 1.0)
            easing: Optional easing function
            
        Returns:
            Interpolated point
        """
        if easing:
            t = easing(t)
        
        x = start.x() + (end.x() - start.x()) * t
        y = start.y() + (end.y() - start.y()) * t
        
        return QPointF(x, y)
    
    @staticmethod
    def interpolate_angle(start: float, end: float, t: float,
                         easing: Callable[[float], float] = None) -> float:
        """Interpolate between two angles (in degrees).
        
        Takes the shortest path between angles.
        
        Args:
            start: Start angle in degrees
            end: End angle in degrees
            t: Progress (0.0 to 1.0)
            easing: Optional easing function
            
        Returns:
            Interpolated angle in degrees
        """
        if easing:
            t = easing(t)
        
        # Normalize angles to [0, 360)
        start = start % 360
        end = end % 360
        
        # Find shortest path
        diff = end - start
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        
        result = start + diff * t
        
        # Normalize result
        if result < 0:
            result += 360
        elif result >= 360:
            result -= 360
        
        return result