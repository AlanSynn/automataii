"""Base view configuration and setup."""

import logging
from PyQt6.QtWidgets import QGraphicsView, QApplication
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt


class BaseImageView(QGraphicsView):
    """Base view with common configuration for image processing."""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # View setup
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        # Touch/Pinch setup
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.grabGesture(Qt.GestureType.PinchGesture)
        
        # Rounded corners and white background for the viewport
        self.viewport().setStyleSheet("background-color: white; border-radius: 10px;")
        
        # Unit and DPI settings
        self.display_unit = "cm"  # Default unit: 'cm', 'inch', or 'px'
        try:
            self.dpi = QApplication.primaryScreen().logicalDotsPerInch()
        except AttributeError:
            self.dpi = 96  # Common default DPI
            logging.warning(f"Could not get screen DPI, defaulting to {self.dpi} DPI.")
        
        logging.info(
            f"BaseImageView initialized with DPI: {self.dpi}, default unit: {self.display_unit}"
        )
    
    def set_display_unit(self, unit: str):
        """Sets the display unit for the grid and updates the view."""
        if unit.lower() in ["cm", "inch", "px"]:
            self.display_unit = unit.lower()
            logging.info(
                f"BaseImageView: Display unit set to {self.display_unit}"
            )
            self.viewport().update()  # Trigger a repaint of the background
        else:
            logging.warning(
                f"BaseImageView: Invalid display unit '{unit}'. Using current: {self.display_unit}"
            )