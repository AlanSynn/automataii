"""Context menu handling for the editor view."""

from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import QPointF, QObject


class ContextMenuHandler(QObject):
    """Handles context menu creation and actions."""
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
    def show_context_menu(self, pos: QPointF):
        """Shows the context menu at the given position."""
        menu = QMenu(self.view)
        
        # Zoom actions
        zoom_in_action = menu.addAction("Zoom In")
        zoom_out_action = menu.addAction("Zoom Out")
        zoom_fit_action = menu.addAction("Zoom to Fit")
        menu.addSeparator()
        reset_action = menu.addAction("Reset View")
        
        # Connect basic actions
        zoom_in_action.triggered.connect(lambda: self.view.scale(1.15, 1.15))
        zoom_out_action.triggered.connect(lambda: self.view.scale(1 / 1.15, 1 / 1.15))
        zoom_fit_action.triggered.connect(self.view.zoom_to_fit)
        reset_action.triggered.connect(self.view.reset_view)
        
        # Add item-specific actions
        self._add_item_actions(menu)
        
        # Execute menu
        global_pos = self.view.mapToGlobal(pos)
        menu.exec(global_pos)
        
    def _add_item_actions(self, menu: QMenu):
        """Adds actions for selected items."""
        selected_item = self._get_selected_item()
        
        if not selected_item:
            return
            
        menu.addSeparator()
        
        # Add cam follower action
        if hasattr(self.view, 'parent_window') and self.view.parent_window:
            menu.addAction(
                f"Set '{selected_item.part_info.name}' as Cam Follower",
                lambda: self.view.parent_window.set_cam_follower()
            )
            
    def _get_selected_item(self):
        """Gets the currently selected CharacterPartItem."""
        from ...graphics_items.part_item import CharacterPartItem
        
        selected_items = self.view.scene().selectedItems()
        if len(selected_items) == 1 and isinstance(selected_items[0], CharacterPartItem):
            return selected_items[0]
        return None