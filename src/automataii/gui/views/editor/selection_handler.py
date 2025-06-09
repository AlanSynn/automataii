"""Selection handling for the editor view."""

import logging
from typing import Optional, Dict
from PyQt6.QtCore import QObject, QPointF, pyqtSignal
from PyQt6.QtWidgets import QGraphicsEllipseItem
from PyQt6.QtGui import QPen, QColor, QBrush

from ...graphics_items.part_item import CharacterPartItem
from .constants import EditorMode


class SelectionHandler(QObject):
    """Handles various selection operations in the editor."""
    
    # Selection signals
    end_effector_selected = pyqtSignal(QPointF, QPointF)  # local_pos, scene_pos
    cam_center_selected = pyqtSignal(QPointF)
    pivot_a_selected = pyqtSignal(QPointF)
    pivot_d_selected = pyqtSignal(QPointF)
    driver_center_selected = pyqtSignal(QPointF)
    driven_center_selected = pyqtSignal(QPointF)
    part_item_clicked = pyqtSignal(CharacterPartItem)
    part_item_double_clicked = pyqtSignal(CharacterPartItem)
    part_item_moved = pyqtSignal(CharacterPartItem, QPointF)
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
        # Selection state
        self._target_part_for_end_effector: Optional[CharacterPartItem] = None
        self._selection_markers: Dict[str, QGraphicsEllipseItem] = {}
        
    def handle_selection_click(self, mode: str, scene_pos: QPointF) -> bool:
        """Handles clicks for various selection modes. Returns True if handled."""
        if mode == EditorMode.SELECT_END_EFFECTOR:
            return self._handle_end_effector_selection(scene_pos)
        elif mode == EditorMode.SELECT_CAM_CENTER:
            self.cam_center_selected.emit(scene_pos)
            return True
        elif mode == EditorMode.SELECT_PIVOT_A:
            self.pivot_a_selected.emit(scene_pos)
            return True
        elif mode == EditorMode.SELECT_PIVOT_D:
            self.pivot_d_selected.emit(scene_pos)
            return True
        elif mode == EditorMode.SELECT_DRIVER_CENTER:
            self.driver_center_selected.emit(scene_pos)
            return True
        elif mode == EditorMode.SELECT_DRIVEN_CENTER:
            self.driven_center_selected.emit(scene_pos)
            return True
            
        return False
        
    def start_end_effector_selection(self, target_item: CharacterPartItem):
        """Prepares for end effector selection on the given item."""
        if not isinstance(target_item, CharacterPartItem):
            logging.warning("Invalid target item for end effector selection")
            return
            
        self._target_part_for_end_effector = target_item
        self._show_status_message(
            f"Select End Effector: Click desired point on '{target_item.part_info.name}'. "
            "Esc to cancel."
        )
        
    def handle_part_click(self, item: CharacterPartItem):
        """Handles clicks on part items."""
        if isinstance(item, CharacterPartItem):
            self.part_item_clicked.emit(item)
            
    def handle_part_double_click(self, item: CharacterPartItem):
        """Handles double clicks on part items."""
        if isinstance(item, CharacterPartItem):
            self.part_item_double_clicked.emit(item)
            
    def get_selected_item(self) -> Optional[CharacterPartItem]:
        """Returns the single selected CharacterPartItem, or None."""
        selected_items = self.view.scene().selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], CharacterPartItem):
            return selected_items[0]
        return None
        
    def set_selected_part(
        self, 
        part_name: Optional[str], 
        part_items: Dict[str, CharacterPartItem]
    ):
        """Sets the visual state for the selected part."""
        logging.debug(f"Setting selected part to: {part_name}")
        
        for name, item in part_items.items():
            if isinstance(item, CharacterPartItem):
                is_selected = name == part_name
                item.set_selected(is_selected)
            else:
                logging.warning(f"Item '{name}' is not a CharacterPartItem")
                
        if self.view.scene():
            self.view.scene().update()
            
    def add_selection_marker(self, key: str, pos: QPointF, color: QColor = None):
        """Adds a visual marker at the given position."""
        # Remove old marker if exists
        self.remove_selection_marker(key)
        
        # Create new marker
        marker_size = 10
        marker = QGraphicsEllipseItem(
            -marker_size/2, -marker_size/2, marker_size, marker_size
        )
        
        if color is None:
            color = QColor(255, 0, 0)  # Default red
            
        marker.setPen(QPen(color, 2))
        marker.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 100)))
        marker.setPos(pos)
        
        self.view.scene().addItem(marker)
        self._selection_markers[key] = marker
        
    def remove_selection_marker(self, key: str):
        """Removes a selection marker."""
        marker = self._selection_markers.pop(key, None)
        if marker and marker.scene():
            self.view.scene().removeItem(marker)
            
    def clear_all_markers(self):
        """Removes all selection markers."""
        for marker in self._selection_markers.values():
            if marker.scene():
                self.view.scene().removeItem(marker)
        self._selection_markers.clear()
        
    def _handle_end_effector_selection(self, scene_pos: QPointF) -> bool:
        """Handles end effector selection click."""
        if not self._target_part_for_end_effector:
            return False
            
        local_pos = self._target_part_for_end_effector.mapFromScene(scene_pos)
        
        # Emit signal
        self.end_effector_selected.emit(local_pos, scene_pos)
        
        # Update item directly
        self._target_part_for_end_effector.end_effector_offset = local_pos
        self._target_part_for_end_effector._update_end_effector_marker()
        
        self._show_status_message(
            f"End effector set for '{self._target_part_for_end_effector.part_info.name}'"
        )
        
        self._target_part_for_end_effector = None
        return True
        
    def _show_status_message(self, message: str):
        """Shows a status message."""
        if hasattr(self.view, 'parent_window') and self.view.parent_window:
            if hasattr(self.view.parent_window, 'statusBar'):
                self.view.parent_window.statusBar().showMessage(message, 5000)
        else:
            logging.info(f"Status: {message}")