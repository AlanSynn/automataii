"""
Base Interactive Handle for Parametric Design

Provides foundation for all draggable mechanism manipulation handles.
Implements Observer pattern for parameter updates and visual feedback.

Author: AI Engineering Assistant  
Architecture: Jeff Dean Performance + Kent Beck Simplicity + Rob Pike Clarity
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
import logging
import math

from PyQt6.QtCore import QPointF, pyqtSignal as Signal, QObject, Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QCursor
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsScene, QApplication
)


class BaseHandle(QGraphicsEllipseItem):
    """
    Base class for all interactive mechanism manipulation handles.
    
    Features:
    - Drag and drop manipulation
    - Visual feedback (hover, active, disabled states)  
    - Parameter update notifications
    - Constraint validation integration
    - Performance-optimized event handling
    """
    
    # Handle appearance constants - make them larger for easier interaction
    HANDLE_RADIUS = 15.0
    HOVER_RADIUS = 18.0
    ACTIVE_RADIUS = 22.0
    
    # Colors for different states
    COLOR_NORMAL = QColor(70, 130, 180)      # Steel blue
    COLOR_HOVER = QColor(100, 149, 237)      # Cornflower blue  
    COLOR_ACTIVE = QColor(65, 105, 225)      # Royal blue
    COLOR_DISABLED = QColor(169, 169, 169)   # Dark gray
    COLOR_ERROR = QColor(220, 20, 60)        # Crimson
    
    def __init__(self, 
                 mechanism_id: str,
                 param_name: str, 
                 initial_position: QPointF,
                 constraint_validator: Optional[Callable] = None,
                 parameter_changed_callback: Optional[Callable] = None,
                 parent=None):
        """
        Initialize interactive handle.
        
        Args:
            mechanism_id: Unique mechanism identifier
            param_name: Parameter name this handle controls
            initial_position: Starting position in scene coordinates
            constraint_validator: Optional function to validate parameter changes
            parent: Qt parent object
        """
        super().__init__(parent)
        
        self.mechanism_id = mechanism_id
        self.param_name = param_name
        self.constraint_validator = constraint_validator
        self.parameter_changed_callback = parameter_changed_callback
        
        # Handle state
        self._is_dragging = False
        self._is_enabled = True
        self._is_hovered = False
        self._drag_start_pos = QPointF()
        self._initial_param_value = None
        
        # Setup visual appearance
        self._setup_appearance()
        
        # Set initial position
        self.setPos(initial_position)
        
        # Enable ALL necessary interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsToShape, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        
        # CRITICAL: Accept all mouse events and force interaction
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # FORCE this item to be on top and interactive
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresParentOpacity, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemDoesntPropagateOpacityToChildren, True)
        
        # MAXIMUM Z-value to appear above everything
        self.setZValue(999999)
        
        logging.debug(f"Created {self.__class__.__name__} for {mechanism_id}:{param_name}")
    
    def _setup_appearance(self):
        """Setup initial visual appearance."""
        # Set rectangular bounds for the handle
        self.setRect(-self.HANDLE_RADIUS, -self.HANDLE_RADIUS, 
                    self.HANDLE_RADIUS * 2, self.HANDLE_RADIUS * 2)
        
        # Initial pen and brush
        self._update_visual_state()
    
    def _update_visual_state(self):
        """Update visual appearance based on current state."""
        if not self._is_enabled:
            color = self.COLOR_DISABLED
            radius = self.HANDLE_RADIUS
        elif self._is_dragging:
            color = self.COLOR_ACTIVE  
            radius = self.ACTIVE_RADIUS
        elif self._is_hovered:
            color = self.COLOR_HOVER
            radius = self.HOVER_RADIUS
        else:
            color = self.COLOR_NORMAL
            radius = self.HANDLE_RADIUS
            
        # Update geometry
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        
        # Update pen and brush
        pen = QPen(color.darker(120), 2.0)
        brush = QBrush(color.lighter(110))
        
        self.setPen(pen)
        self.setBrush(brush)
        
        # Add subtle shadow effect when active
        if self._is_dragging:
            shadow_pen = QPen(QColor(0, 0, 0, 100), 1.0)
            # Note: Shadow implementation would require additional graphics items
    
    def setEnabled(self, enabled: bool):
        """Enable or disable handle interaction."""
        self._is_enabled = enabled
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, enabled)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, enabled)
        self._update_visual_state()
        
        cursor = QCursor(Qt.CursorShape.PointingHandCursor if enabled 
                        else Qt.CursorShape.ForbiddenCursor)
        self.setCursor(cursor)
    
    def isEnabled(self) -> bool:
        """Check if handle is enabled."""
        return self._is_enabled
    
    # Event Handlers
    
    def hoverEnterEvent(self, event):
        """Handle mouse enter event."""
        logging.info(f"[HANDLE] 🔥 HOVER ENTER {self.param_name}")
        if self._is_enabled:
            self._is_hovered = True
            self._update_visual_state()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Handle mouse leave event."""
        self._is_hovered = False
        self._update_visual_state()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press - start drag operation."""
        logging.info(f"[HANDLE] 🔥 MOUSE PRESS {self.param_name} button={event.button()}")
        
        if not self._is_enabled or event.button() != Qt.MouseButton.LeftButton:
            logging.info(f"[HANDLE] ❌ Ignoring press - enabled:{self._is_enabled} button:{event.button()}")
            return
            
        self._is_dragging = True
        self._drag_start_pos = event.pos()
        self._initial_param_value = self.get_current_parameter_value()
        
        self._update_visual_state()
        logging.info(f"[HANDLE] ✅ Started dragging {self.param_name}")
        
        # Capture parameter state for potential undo
        self._capture_initial_state()
        
        super().mousePressEvent(event)
        logging.debug(f"Started dragging {self.param_name} handle")
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse move - update parameter during drag."""
        if not self._is_dragging or not self._is_enabled:
            return
            
        # Calculate new parameter value based on position change
        new_value = self._calculate_parameter_from_position(event.scenePos())
        
        # Validate against constraints
        if self.constraint_validator:
            validated_value = self.constraint_validator(self.param_name, new_value)
            if validated_value != new_value:
                # Constraint violation - provide visual feedback
                self._show_constraint_feedback()
                new_value = validated_value
        
        # Update parameter if changed
        if new_value != self._initial_param_value:
            if self.parameter_changed_callback:
                self.parameter_changed_callback(self.mechanism_id, self.param_name, new_value)
            self._apply_parameter_change(new_value)
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release - finish drag operation."""
        if not self._is_dragging:
            return
            
        self._is_dragging = False
        self._update_visual_state()
        
        # Finalize parameter change
        final_value = self.get_current_parameter_value()
        logging.info(f"[HANDLE] Finished dragging {self.param_name}: {final_value}")
        
        super().mouseReleaseEvent(event)
        logging.debug(f"Finished dragging {self.param_name} handle: {final_value}")
    
    def _show_constraint_feedback(self):
        """Show visual feedback for constraint violations."""
        # Temporarily change color to indicate constraint violation
        original_brush = self.brush()
        error_brush = QBrush(self.COLOR_ERROR.lighter(140))
        self.setBrush(error_brush)
        
        # Schedule return to normal appearance
        QApplication.processEvents()  # Force immediate update
        # Note: In production, use QTimer.singleShot for delayed reset
    
    # Abstract Methods (Template Method Pattern)
    
    @abstractmethod
    def _calculate_parameter_from_position(self, scene_pos: QPointF) -> Any:
        """
        Calculate parameter value from handle position.
        
        Args:
            scene_pos: Current handle position in scene coordinates
            
        Returns:
            New parameter value based on position
        """
        pass
    
    @abstractmethod
    def _apply_parameter_change(self, new_value: Any):
        """
        Apply parameter change to mechanism.
        
        Args:
            new_value: New parameter value to apply
        """
        pass
    
    @abstractmethod
    def get_current_parameter_value(self) -> Any:
        """
        Get current parameter value from mechanism.
        
        Returns:
            Current parameter value
        """
        pass
    
    def _capture_initial_state(self):
        """Capture initial parameter state for undo functionality."""
        # Implementation for undo/redo system
        # Store in parameter history for Command pattern
        pass
    
    # Utility Methods
    
    def distance_to_point(self, point: QPointF) -> float:
        """Calculate distance from handle center to point."""
        handle_center = self.pos()
        dx = point.x() - handle_center.x()
        dy = point.y() - handle_center.y()
        return math.sqrt(dx * dx + dy * dy)
    
    def is_near_point(self, point: QPointF, threshold: float = 20.0) -> bool:
        """Check if handle is near a specific point."""
        return self.distance_to_point(point) <= threshold
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}({self.mechanism_id}:{self.param_name})"