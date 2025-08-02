# src/automataii/ui/tabs/base/tab.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from ...design_system import design_system, DesignSystem, ThemeMode


class BaseTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._design_system = design_system
        
        # Apply base styling
        self._setup_base_styling()
        
        # Connect to theme changes
        self._design_system.theme_changed.connect(self._on_theme_changed)
    
    def _setup_base_styling(self):
        """Apply base styling to the tab"""
        self.setObjectName("BaseTab")
        
        # Don't create layout here - let subclasses handle it
        # This prevents QLayout conflicts
    
    def _on_theme_changed(self, theme: ThemeMode):
        """Handle theme changes"""
        self._apply_theme_styles()
    
    def _apply_theme_styles(self):
        """Apply theme-specific styles - override in subclasses"""
        pass

    def activate_tab(self):
        """Called when the tab becomes active."""
        self._apply_theme_styles()

    def deactivate_tab(self):
        """Called when the tab becomes inactive."""
        pass

    def cleanup(self):
        """Clean up all resources used by the tab."""
        # Disconnect theme change signal
        try:
            self._design_system.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        
        # Default implementation calls deactivate_tab
        self.deactivate_tab()

        # Force garbage collection
        import gc

        gc.collect()
