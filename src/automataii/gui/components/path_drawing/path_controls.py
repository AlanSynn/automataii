"""Path drawing controls widget."""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QPushButton,
    QHBoxLayout, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt


class PathControlsWidget(QGroupBox):
    """Widget for path drawing controls.
    
    This component provides controls for drawing and managing motion paths.
    """
    
    # Signals
    define_path_requested = pyqtSignal()
    clear_path_requested = pyqtSignal()
    drawing_mode_changed = pyqtSignal(bool)  # is_drawing
    
    def __init__(self, parent=None):
        super().__init__("2 Motion Path", parent)
        
        self._is_drawing_mode = False
        self._selected_part: Optional[str] = None
        self._has_path = False
        
        self._init_ui()
        self._connect_signals()
        
        # Start disabled
        self._update_button_states()
    
    def _init_ui(self) -> None:
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Status label
        self.status_label = QLabel("Select a part to define motion path")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        
        # Define/Edit button
        self.define_path_btn = QPushButton("Define Path")
        self.define_path_btn.setCheckable(True)
        self.define_path_btn.setToolTip("Click to start drawing a motion path")
        self.define_path_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:checked {
                background-color: #0969da;
                color: white;
                border-color: #0860ca;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        
        # Clear button
        self.clear_path_btn = QPushButton("Clear")
        self.clear_path_btn.setToolTip("Clear the motion path for selected part")
        self.clear_path_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #ffebe9;
                border-color: #ff8182;
                color: #d1242f;
            }
            QPushButton:pressed {
                background-color: #ffcecb;
            }
            QPushButton:disabled {
                background-color: #f6f8fa;
                color: #8c959f;
                border-color: #d1d9e0;
            }
        """)
        
        button_layout.addWidget(self.define_path_btn)
        button_layout.addWidget(self.clear_path_btn)
        layout.addLayout(button_layout)
        
        # Instructions
        self.instructions_label = QLabel("")
        self.instructions_label.setWordWrap(True)
        self.instructions_label.setStyleSheet("""
            QLabel {
                color: #0969da;
                font-size: 11px;
                padding: 4px;
                background-color: #ddf4ff;
                border-radius: 4px;
            }
        """)
        self.instructions_label.hide()
        layout.addWidget(self.instructions_label)
        
        # Apply group box styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: white;
            }
        """)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.define_path_btn.toggled.connect(self._on_define_toggled)
        self.clear_path_btn.clicked.connect(self._on_clear_clicked)
    
    def set_selected_part(self, part_name: Optional[str], has_path: bool = False) -> None:
        """Set the currently selected part.
        
        Args:
            part_name: Name of the selected part, or None
            has_path: Whether the part already has a path
        """
        self._selected_part = part_name
        self._has_path = has_path
        
        # Update status
        if part_name:
            display_name = part_name.replace('_', ' ').title()
            if has_path:
                self.status_label.setText(f"{display_name} - Path defined")
                self.status_label.setStyleSheet("color: green;")
            else:
                self.status_label.setText(f"{display_name} - No path")
                self.status_label.setStyleSheet("color: #666;")
        else:
            self.status_label.setText("Select a part to define motion path")
            self.status_label.setStyleSheet("color: #666;")
        
        # Update button states
        self._update_button_states()
    
    def set_drawing_mode(self, is_drawing: bool) -> None:
        """Set whether currently in drawing mode.
        
        Args:
            is_drawing: Whether drawing mode is active
        """
        self._is_drawing_mode = is_drawing
        self.define_path_btn.setChecked(is_drawing)
        
        # Update UI based on mode
        if is_drawing:
            self.define_path_btn.setText("Stop Drawing")
            self.instructions_label.setText(
                "Click points in the view to draw path. "
                "Click 'Stop Drawing' when done."
            )
            self.instructions_label.show()
        else:
            self.define_path_btn.setText("Define Path")
            self.instructions_label.hide()
        
        self._update_button_states()
    
    def set_enabled_state(self, has_selection: bool, is_animating: bool = False) -> None:
        """Update enabled state based on conditions.
        
        Args:
            has_selection: Whether a part is selected
            is_animating: Whether animation is playing
        """
        # Can't draw while animating
        can_draw = has_selection and not is_animating
        self.setEnabled(can_draw)
        
        if is_animating:
            self.status_label.setText("Cannot edit paths during animation")
            self.status_label.setStyleSheet("color: #d1242f;")
    
    def _update_button_states(self) -> None:
        """Update button enabled states."""
        has_selection = self._selected_part is not None
        
        # Define button enabled when part selected and not animating
        self.define_path_btn.setEnabled(has_selection)
        
        # Clear button enabled when part has path and not drawing
        self.clear_path_btn.setEnabled(
            has_selection and 
            self._has_path and 
            not self._is_drawing_mode
        )
    
    def _on_define_toggled(self, checked: bool) -> None:
        """Handle define button toggle.
        
        Args:
            checked: Whether button is now checked
        """
        if checked:
            # Start drawing mode
            self.define_path_requested.emit()
            self.drawing_mode_changed.emit(True)
            logging.info(f"PathControlsWidget: Starting path drawing for '{self._selected_part}'")
        else:
            # Stop drawing mode
            self.drawing_mode_changed.emit(False)
            logging.info("PathControlsWidget: Stopped path drawing")
        
        self.set_drawing_mode(checked)
    
    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        if self._selected_part:
            self.clear_path_requested.emit()
            logging.info(f"PathControlsWidget: Clearing path for '{self._selected_part}'")