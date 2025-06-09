"""Theme and styling management for the main window."""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSlot, QObject

from ...utils.styling import LIGHT_STYLE, DARK_STYLE

if TYPE_CHECKING:
    from .main_window import AutomataDesigner


class ThemeManager(QObject):
    """Manages application themes and styling."""
    
    def __init__(self, main_window: 'AutomataDesigner'):
        super().__init__()
        self.main_window = main_window
        self.light_style = LIGHT_STYLE
        self.dark_style = DARK_STYLE
        
    @pyqtSlot(str)
    def apply_theme(self, theme_name: str):
        """Applies the selected theme (stylesheet) to the application."""
        if theme_name.lower() == "dark":
            self.main_window.setStyleSheet(self.dark_style)
            logging.info("Applied dark theme")
        elif theme_name.lower() == "light":
            self.main_window.setStyleSheet(self.light_style)
            logging.info("Applied light theme")
        else:
            logging.warning(f"Unknown theme requested: {theme_name}")
            # Default to light theme
            self.main_window.setStyleSheet(self.light_style)
        
        # Update status bar
        self.main_window.statusBar().showMessage(f"Theme changed to: {theme_name}", 3000)
    
    @pyqtSlot(str)
    def handle_unit_changed(self, unit: str):
        """Handles the unit system change from OptionsTab."""
        logging.info(f"MainWindow: Unit system changed to: {unit}")
        
        # Pass the new unit to EditorView
        if hasattr(self.main_window.editor_tab, "editor_view") and hasattr(
            self.main_window.editor_tab.editor_view, "set_display_unit"
        ):
            self.main_window.editor_tab.editor_view.set_display_unit(unit)
        else:
            logging.warning(
                "MainWindow: EditorView or its set_display_unit method not found."
            )
        
        # Pass the new unit to ImageProcessingView (via ImageProcessingTab)
        if hasattr(self.main_window.image_proc_tab, "image_proc_view") and hasattr(
            self.main_window.image_proc_tab.image_proc_view, "set_display_unit"
        ):
            self.main_window.image_proc_tab.image_proc_view.set_display_unit(unit)
        else:
            logging.warning(
                "MainWindow: ImageProcessingView or its set_display_unit method not found."
            )
        
        self.main_window.statusBar().showMessage(f"Display unit set to {unit}", 3000)