"""Mode management for the editor view."""

import logging
from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt, QObject, pyqtSignal

from .constants import EditorMode, MODE_CURSORS


class ModeManager(QObject):
    """Manages editor interaction modes and state transitions."""
    
    mode_changed = pyqtSignal(str, str)  # old_mode, new_mode
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.current_mode = EditorMode.SELECT
        self._mode_data = {}  # Store mode-specific data
        
    def set_mode(self, mode: str):
        """Sets the interaction mode of the editor view."""
        if mode == self.current_mode:
            return
            
        logging.info(f"Setting EditorView mode from {self.current_mode} to {mode}")
        previous_mode = self.current_mode
        self.current_mode = mode
        
        # Cleanup previous mode
        self._cleanup_mode(previous_mode)
        
        # Configure view for new mode
        self._configure_mode(mode)
        
        # Emit mode change signal
        self.mode_changed.emit(previous_mode, mode)
        
    def _cleanup_mode(self, mode: str):
        """Cleans up state when leaving a mode."""
        if mode == EditorMode.DEFINE_JOINT:
            self._cleanup_joint_definition()
        elif mode == EditorMode.DEFINE_MOTION_PATH:
            self._cleanup_motion_path()
        elif mode == EditorMode.SELECT_END_EFFECTOR:
            self._mode_data.pop('target_part', None)
        elif mode == EditorMode.SIMULATION:
            self._restore_interactivity()
            
    def _configure_mode(self, mode: str):
        """Configures view settings for the new mode."""
        # Set cursor
        cursor = MODE_CURSORS.get(mode, Qt.CursorShape.ArrowCursor)
        self.view.viewport().setCursor(cursor)
        
        # Configure drag mode and interactivity
        if mode == EditorMode.SIMULATION:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setInteractive(False)
        elif mode == EditorMode.SELECT:
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.view.setInteractive(True)
        elif mode.startswith("select_") or mode == EditorMode.DEFINE_JOINT:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setInteractive(True)
        elif mode == EditorMode.DEFINE_MOTION_PATH:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setInteractive(True)
        else:  # Default/fallback
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.view.setInteractive(True)
            
    def _cleanup_joint_definition(self):
        """Cleans up joint definition mode data."""
        self._mode_data.pop('joint_parent_item', None)
        self._mode_data.pop('joint_parent_pos', None)
        
    def _cleanup_motion_path(self):
        """Cleans up motion path mode data."""
        self._mode_data.pop('motion_path_points', None)
        self._mode_data.pop('is_drawing', None)
        
    def _restore_interactivity(self):
        """Restores view interactivity after simulation mode."""
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setInteractive(True)
        
    def store_mode_data(self, key: str, value):
        """Stores mode-specific data."""
        self._mode_data[key] = value
        
    def get_mode_data(self, key: str, default=None):
        """Retrieves mode-specific data."""
        return self._mode_data.get(key, default)
        
    def clear_mode_data(self, key: str = None):
        """Clears mode-specific data."""
        if key:
            self._mode_data.pop(key, None)
        else:
            self._mode_data.clear()
            
    def is_in_mode(self, mode: str) -> bool:
        """Checks if currently in the specified mode."""
        return self.current_mode == mode
        
    def is_selection_mode(self) -> bool:
        """Checks if in any selection mode."""
        return self.current_mode.startswith("select")
        
    def is_drawing_mode(self) -> bool:
        """Checks if in any drawing mode."""
        return self.current_mode in [EditorMode.DEFINE_MOTION_PATH, EditorMode.DEFINE_JOINT]