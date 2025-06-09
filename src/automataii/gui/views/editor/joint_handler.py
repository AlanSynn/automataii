"""Joint definition handling for the editor view."""

import logging
from PyQt6.QtCore import QObject, QPointF, pyqtSignal
from PyQt6.QtWidgets import QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QColor, QBrush

from ...graphics_items.part_item import CharacterPartItem
from .constants import EditorMode


class JointHandler(QObject):
    """Handles joint definition operations."""
    
    joint_defined = pyqtSignal(dict)  # Emits joint definition data
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
        # Joint definition state
        self._parent_item = None
        self._parent_pos = None
        self._parent_marker = None
        
    def start_joint_definition(self):
        """Initiates joint definition mode."""
        self._reset_state()
        self._show_status_message("Define Joint: 1. Click parent part.")
        
    def handle_click(self, scene_pos: QPointF, view_pos: QPointF) -> bool:
        """Handles a click during joint definition. Returns True if handled."""
        item_at_click = self.view.itemAt(view_pos)
        
        if not isinstance(item_at_click, CharacterPartItem):
            logging.debug("Joint definition click missed a character part.")
            return False
            
        if self._parent_item is None:
            # First click: select parent
            self._parent_item = item_at_click
            self._parent_pos = item_at_click.mapFromScene(scene_pos)
            
            logging.info(
                f"Joint parent selected: {self._parent_item.part_info.name}, "
                f"local pos: {self._parent_pos}"
            )
            self._show_status_message(
                f"Selected {self._parent_item.part_info.name} as parent. "
                "Click another part to define joint."
            )
            
            # Create visual marker
            self._create_parent_marker()
            return True
            
        else:
            # Second click: select child
            if item_at_click == self._parent_item:
                logging.debug("Clicked the same item again. Resetting.")
                self._reset_state()
                self._show_status_message("Joint definition reset. Click first part.")
                return True
                
            child_item = item_at_click
            child_pos = item_at_click.mapFromScene(scene_pos)
            
            logging.info(
                f"Joint child selected: {child_item.part_info.name}, "
                f"local pos: {child_pos}"
            )
            
            # Emit joint definition
            self.joint_defined.emit({
                "parent_item_name": self._parent_item.part_info.name,
                "child_item_name": child_item.part_info.name,
                "parent_pos_local": self._parent_pos,
                "child_pos_local": child_pos,
            })
            
            self._show_status_message(
                f"Joint defined: {self._parent_item.part_info.name} <> "
                f"{child_item.part_info.name}. Define another or switch mode."
            )
            
            # Reset for next joint
            self._reset_state()
            return True
            
    def cancel(self):
        """Cancels the current joint definition."""
        self._cleanup_visuals()
        self._reset_state()
        self._show_status_message("Joint definition cancelled.")
        
    def _create_parent_marker(self):
        """Creates a visual marker for the parent joint position."""
        if self._parent_marker:
            self._cleanup_visuals()
            
        # Create marker at parent position
        marker_size = 10
        self._parent_marker = QGraphicsEllipseItem(
            -marker_size/2, -marker_size/2, marker_size, marker_size
        )
        self._parent_marker.setPen(QPen(QColor(255, 0, 0), 2))
        self._parent_marker.setBrush(QBrush(QColor(255, 0, 0, 100)))
        
        # Position marker at parent joint location
        scene_pos = self._parent_item.mapToScene(self._parent_pos)
        self._parent_marker.setPos(scene_pos)
        
        self.view.scene().addItem(self._parent_marker)
        
    def _cleanup_visuals(self):
        """Removes visual markers."""
        if self._parent_marker and self._parent_marker.scene():
            self.view.scene().removeItem(self._parent_marker)
            self._parent_marker = None
            
    def _reset_state(self):
        """Resets internal state."""
        self._parent_item = None
        self._parent_pos = None
        # Note: visuals are not cleaned here to keep them visible
        
    def _show_status_message(self, message: str):
        """Shows a status message."""
        if hasattr(self.view, 'parent_window') and self.view.parent_window:
            if hasattr(self.view.parent_window, 'statusBar'):
                self.view.parent_window.statusBar().showMessage(message, 5000)
        else:
            logging.info(f"Status: {message}")