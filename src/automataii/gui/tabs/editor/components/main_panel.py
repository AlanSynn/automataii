"""Main panel for editor tab containing the view."""

import logging

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from ....components.common import ZoomToolbar
from ..handlers import ViewHandler


class EditorMainPanel(QWidget):
    """Main panel containing the editor view and zoom controls."""
    
    def __init__(self, editor_view, view_handler: ViewHandler, parent=None):
        super().__init__(parent)
        
        self._view = editor_view
        self._view_handler = view_handler
        
        # Components
        self._zoom_toolbar = ZoomToolbar()
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Add view
        layout.addWidget(self._view)
        
        # Position zoom toolbar as overlay
        self._zoom_toolbar.setParent(self)
        self._position_zoom_toolbar()
        
        # Make sure toolbar is on top
        self._zoom_toolbar.raise_()
    
    def _connect_signals(self):
        """Connect signals."""
        # Zoom toolbar
        self._zoom_toolbar.zoom_changed.connect(self._view_handler.set_zoom)
        self._zoom_toolbar.fit_requested.connect(self._view_handler.fit_to_contents)
        
        # View handler
        self._view_handler.zoom_changed.connect(self._update_zoom_display)
    
    def _position_zoom_toolbar(self):
        """Position zoom toolbar in bottom-right corner."""
        if not self.isVisible():
            return
        
        toolbar_width = self._zoom_toolbar.sizeHint().width()
        toolbar_height = self._zoom_toolbar.sizeHint().height()
        
        x = self.width() - toolbar_width - 10
        y = self.height() - toolbar_height - 10
        
        self._zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)
    
    def _update_zoom_display(self, zoom_level: float):
        """Update zoom display in toolbar."""
        self._zoom_toolbar.set_zoom(zoom_level)
    
    def resizeEvent(self, event):
        """Handle resize to reposition toolbar."""
        super().resizeEvent(event)
        self._position_zoom_toolbar()
    
    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self._position_zoom_toolbar()