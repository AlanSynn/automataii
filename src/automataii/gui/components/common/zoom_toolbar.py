"""Zoom toolbar component for view controls."""

import logging
from typing import Optional, List

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt


class ZoomToolbar(QWidget):
    """Reusable zoom toolbar component.
    
    This component provides zoom controls that can be used
    with any QGraphicsView-based view.
    """
    
    # Signals
    zoom_changed = pyqtSignal(float)  # zoom_factor
    fit_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._default_zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self._current_zoom = 1.0  # 100%
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # Add stretch to right-align controls
        layout.addStretch()
        
        # Zoom combo box
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedSize(70, 28)
        self.zoom_combo.addItems(self._default_zoom_levels)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom level")
        
        # Apply styling
        self.zoom_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """)
        
        # Fit button
        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setFixedSize(45, 28)
        self.fit_btn.setToolTip("Zoom to fit all items")
        
        # Apply styling
        self.fit_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 4px;
                background-color: white;
                font-size: 13px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        
        # Add to layout
        layout.addWidget(self.zoom_combo)
        layout.addWidget(self.fit_btn)
        
        # Connect signals
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_text_changed)
        self.zoom_combo.lineEdit().editingFinished.connect(self._on_zoom_edited)
        self.fit_btn.clicked.connect(self.fit_requested.emit)
        
        # Style the toolbar itself
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 8px;
            }
        """)
    
    def set_zoom_levels(self, levels: List[str]) -> None:
        """Set custom zoom levels.
        
        Args:
            levels: List of zoom level strings (e.g., ["50%", "100%", "200%"])
        """
        current_text = self.zoom_combo.currentText()
        self.zoom_combo.clear()
        self.zoom_combo.addItems(levels)
        
        # Try to restore previous selection
        index = self.zoom_combo.findText(current_text)
        if index >= 0:
            self.zoom_combo.setCurrentIndex(index)
        else:
            self.zoom_combo.setCurrentText(current_text)
    
    def set_zoom(self, zoom_factor: float) -> None:
        """Set the zoom level programmatically.
        
        Args:
            zoom_factor: Zoom factor (1.0 = 100%)
        """
        self._current_zoom = zoom_factor
        zoom_percent = int(zoom_factor * 100)
        self.zoom_combo.setCurrentText(f"{zoom_percent}%")
    
    def get_zoom(self) -> float:
        """Get the current zoom factor.
        
        Returns:
            Current zoom factor
        """
        return self._current_zoom
    
    def _on_zoom_text_changed(self, text: str) -> None:
        """Handle zoom combo text change."""
        if not text:
            return
        
        # Don't process if text hasn't actually changed to a valid value
        zoom_value = self._parse_zoom_text(text)
        if zoom_value is not None and abs(zoom_value - self._current_zoom) > 0.001:
            self._current_zoom = zoom_value
            self.zoom_changed.emit(zoom_value)
    
    def _on_zoom_edited(self) -> None:
        """Handle manual zoom entry."""
        text = self.zoom_combo.currentText()
        zoom_value = self._parse_zoom_text(text)
        
        if zoom_value is not None:
            # Clamp to reasonable range
            zoom_value = max(0.1, min(5.0, zoom_value))
            self._current_zoom = zoom_value
            
            # Update text to normalized format
            self.zoom_combo.setCurrentText(f"{int(zoom_value * 100)}%")
            self.zoom_changed.emit(zoom_value)
        else:
            # Reset to current zoom on invalid input
            self.zoom_combo.setCurrentText(f"{int(self._current_zoom * 100)}%")
    
    def _parse_zoom_text(self, text: str) -> Optional[float]:
        """Parse zoom text to float value.
        
        Args:
            text: Zoom text (e.g., "100%", "1.5", "150")
            
        Returns:
            Zoom factor or None if invalid
        """
        try:
            # Remove % sign if present
            text = text.strip().rstrip('%')
            
            # Parse as float
            value = float(text)
            
            # If value > 5, assume it's a percentage
            if value > 5:
                value = value / 100.0
            
            return value
        except ValueError:
            return None
    
    def enable_controls(self, enabled: bool) -> None:
        """Enable or disable zoom controls.
        
        Args:
            enabled: Whether to enable controls
        """
        self.zoom_combo.setEnabled(enabled)
        self.fit_btn.setEnabled(enabled)