"""
Interface for interactive handles.
Defines the contract for draggable control points.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsItem


@dataclass
class HandleConstraints:
    """Constraints for handle movement."""
    min_x: Optional[float] = None
    max_x: Optional[float] = None
    min_y: Optional[float] = None
    max_y: Optional[float] = None
    fixed_x: Optional[float] = None
    fixed_y: Optional[float] = None
    snap_grid: Optional[float] = None
    min_distance: Optional[Dict[str, float]] = None  # from other handles
    max_distance: Optional[Dict[str, float]] = None  # from other handles
    circular_constraint: Optional[Dict[str, Any]] = None  # center and radius
    
    def apply(self, position: QPointF) -> QPointF:
        """Apply constraints to position."""
        x, y = position.x(), position.y()
        
        # Fixed constraints override all others
        if self.fixed_x is not None:
            x = self.fixed_x
        elif self.min_x is not None or self.max_x is not None:
            if self.min_x is not None:
                x = max(x, self.min_x)
            if self.max_x is not None:
                x = min(x, self.max_x)
        
        if self.fixed_y is not None:
            y = self.fixed_y
        elif self.min_y is not None or self.max_y is not None:
            if self.min_y is not None:
                y = max(y, self.min_y)
            if self.max_y is not None:
                y = min(y, self.max_y)
        
        # Grid snapping
        if self.snap_grid is not None:
            x = round(x / self.snap_grid) * self.snap_grid
            y = round(y / self.snap_grid) * self.snap_grid
        
        return QPointF(x, y)


class HandleInterface(ABC):
    """
    Abstract base class for interactive handles.
    
    Provides draggable control points for mechanism editing.
    """
    
    @abstractmethod
    def __init__(self, 
                 handle_id: str,
                 position: QPointF,
                 constraints: Optional[HandleConstraints] = None):
        """
        Initialize handle.
        
        Args:
            handle_id: Unique identifier
            position: Initial position
            constraints: Movement constraints
        """
        pass
    
    @abstractmethod
    def set_position(self, position: QPointF) -> None:
        """Set handle position."""
        pass
    
    @abstractmethod
    def get_position(self) -> QPointF:
        """Get current position."""
        pass
    
    @abstractmethod
    def set_constraints(self, constraints: HandleConstraints) -> None:
        """Update movement constraints."""
        pass
    
    @abstractmethod
    def set_visible(self, visible: bool) -> None:
        """Set visibility."""
        pass
    
    @abstractmethod
    def set_enabled(self, enabled: bool) -> None:
        """Set interaction enabled state."""
        pass
    
    @abstractmethod
    def set_style(self, color: QColor, size: float) -> None:
        """Set visual style."""
        pass
    
    @abstractmethod
    def connect_moved_callback(self, callback: Callable[[str, QPointF], None]) -> None:
        """Connect position change callback."""
        pass
    
    @property
    @abstractmethod
    def graphics_item(self) -> QGraphicsItem:
        """Get the underlying graphics item."""
        pass