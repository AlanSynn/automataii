"""
Ultra-optimized Draggable Handle for Parametric Design
Complete rewrite with proper mouse capture and coordinate handling

Author: AI Engineering Assistant
Architecture: ULTRATHINK - Deep understanding of Qt event system
"""

import logging
from typing import Optional, Callable, Any

from PyQt6.QtCore import QPointF, Qt, QRectF
from PyQt6.QtGui import QBrush, QColor, QPen, QCursor
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, 
    QGraphicsItem, 
    QGraphicsSceneMouseEvent,
    QGraphicsSceneHoverEvent
)


class DraggableHandle(QGraphicsEllipseItem):
    """
    ULTRATHINK Solution: Perfect draggable handle implementation
    
    Key insights:
    1. Use ItemIsMovable=True but control movement via itemChange()
    2. Properly handle coordinate transformations
    3. Ensure mouse capture works correctly
    """
    
    # Visual constants
    RADIUS_NORMAL = 15.0
    RADIUS_HOVER = 18.0
    RADIUS_DRAG = 20.0
    
    # Colors
    COLOR_NORMAL = QColor(255, 50, 50)      # Bright red
    COLOR_HOVER = QColor(255, 100, 100)     # Light red
    COLOR_DRAG = QColor(255, 150, 150)      # Very light red
    
    def __init__(self, 
                 handle_id: str,
                 initial_pos: QPointF,
                 update_callback: Optional[Callable[[str, QPointF], None]] = None,
                 parent=None):
        """
        Initialize draggable handle with PROPER event handling.
        
        Args:
            handle_id: Unique identifier for this handle
            initial_pos: Initial position in scene coordinates
            update_callback: Function to call when handle moves
            parent: Parent item (usually None for scene coordinates)
        """
        super().__init__(parent)
        
        self.handle_id = handle_id
        self.update_callback = update_callback
        
        # State tracking
        self._is_hovering = False
        self._is_dragging = False
        self._drag_offset = QPointF()
        
        # Setup appearance
        self._setup_appearance()
        
        # CRITICAL: Set position in scene coordinates
        self.setPos(initial_pos)
        
        # CRITICAL FLAGS for proper dragging
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)  # MUST be True
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        
        # Accept hover events
        self.setAcceptHoverEvents(True)
        
        # Set cursor
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # Maximum Z-value to be on top
        self.setZValue(1000000)
        
        logging.info(f"[DRAGGABLE] Created handle {handle_id} at {initial_pos}")
    
    def _setup_appearance(self):
        """Setup visual appearance."""
        self._update_visual_state()
    
    def _update_visual_state(self):
        """Update visual based on current state."""
        if self._is_dragging:
            radius = self.RADIUS_DRAG
            color = self.COLOR_DRAG
            pen_width = 4
        elif self._is_hovering:
            radius = self.RADIUS_HOVER
            color = self.COLOR_HOVER
            pen_width = 3
        else:
            radius = self.RADIUS_NORMAL
            color = self.COLOR_NORMAL
            pen_width = 2
        
        # Set geometry
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        
        # Set pen and brush
        pen = QPen(color.darker(120), pen_width)
        brush = QBrush(color)
        self.setPen(pen)
        self.setBrush(brush)
        
        # Force update
        self.update()
    
    # CRITICAL: Override itemChange to control movement
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        ULTRATHINK: Control item movement through itemChange.
        This is called BEFORE the position changes.
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # value is the new position
            new_pos = value  # This is already a QPointF
            
            # Log the movement
            old_pos = self.pos()
            if old_pos != new_pos:
                logging.info(f"[DRAGGABLE] 🔥 {self.handle_id} moving from {old_pos} to {new_pos}")
                
                # ALWAYS call update callback during drag (don't check _is_dragging)
                if self.update_callback:
                    logging.info(f"[DRAGGABLE] 🚀 Calling callback for {self.handle_id}")
                    self.update_callback(self.handle_id, new_pos)
                else:
                    logging.warning(f"[DRAGGABLE] ❌ No callback for {self.handle_id}")
            
            # Return the new position to allow movement
            return new_pos
        
        return super().itemChange(change, value)
    
    # Mouse event handlers
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        """Handle mouse enter."""
        self._is_hovering = True
        self._update_visual_state()
        logging.info(f"[DRAGGABLE] Hover enter {self.handle_id}")
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        """Handle mouse leave."""
        self._is_hovering = False
        self._update_visual_state()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_offset = event.pos()  # Store offset for smooth dragging
            self._update_visual_state()
            logging.info(f"[DRAGGABLE] Started dragging {self.handle_id}")
            
            # CRITICAL: Call super to enable automatic dragging
            super().mousePressEvent(event)
        else:
            event.ignore()
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse move - Qt will automatically move the item."""
        # Let Qt handle the movement automatically
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            self._update_visual_state()
            
            final_pos = self.pos()
            logging.info(f"[DRAGGABLE] Finished dragging {self.handle_id} at {final_pos}")
            
            # Final callback
            if self.update_callback:
                self.update_callback(self.handle_id, final_pos)
            
            super().mouseReleaseEvent(event)
        else:
            event.ignore()
    
    def get_handle_id(self) -> str:
        """Get the handle ID."""
        return self.handle_id