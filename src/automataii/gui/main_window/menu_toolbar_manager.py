"""Menu and toolbar management for the main window."""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QToolBar

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class MenuToolbarManager:
    """Handles menu and toolbar creation and management."""
    
    def __init__(self, main_window: 'AutomataDesigner'):
        self.main_window = main_window
        
    def create_menus(self):
        """Creates the main application menus using the ActionManager."""
        menubar = self.main_window.menuBar()
        self.main_window.action_manager.setup_menus(menubar)
        
    def create_toolbar(self):
        """Creates the main application toolbar using the ActionManager."""
        self.main_window.main_toolbar = QToolBar("Main Toolbar")
        self.main_window.main_toolbar.setMovable(False)
        
        # Setup toolbar using the action manager
        self.main_window.action_manager.setup_toolbar(self.main_window.main_toolbar)
        
        # Add to main window and hide by default
        self.main_window.addToolBar(self.main_window.main_toolbar)
        self.main_window.main_toolbar.hide()
        
    def toggle_toolbar_visibility(self, visible: bool):
        """Toggles the visibility of the main toolbar."""
        if self.main_window.main_toolbar:
            self.main_window.main_toolbar.setVisible(visible)
            logging.info(f"Main toolbar visibility set to: {visible}")
        else:
            logging.warning("toggle_toolbar_visibility called but main_toolbar is None.")