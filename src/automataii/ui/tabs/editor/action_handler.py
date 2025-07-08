# src/automataii/ui/tabs/editor/action_handler.py

import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainterPath

logger = logging.getLogger(__name__)

class EditorActionHandler(QObject):
    """Handles user actions for the EditorTab."""
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    motion_path_updated = pyqtSignal(str, QPainterPath)

    def __init__(self, state, scene_manager, parent=None):
        super().__init__(parent)
        self.state = state
        self.scene_manager = scene_manager

    def handle_play_simulation(self):
        self.request_play_simulation.emit()

    def handle_stop_simulation(self):
        self.request_stop_simulation.emit()

    def handle_reset_simulation(self):
        self.request_reset_simulation.emit()

    def handle_clear_motion_path(self):
        part_name = self.state.selected_part_name
        if part_name:
            self.state.clear_path_for_part(part_name)
            self.scene_manager.update_part_path(part_name, QPainterPath())
            self.motion_path_updated.emit(part_name, QPainterPath())

    def handle_freehand_path_completed(self, path_points):
        part_name = self.state.selected_part_name
        if not part_name:
            return

        # Path creation logic would be here
        path = QPainterPath()
        if path_points:
            path.moveTo(path_points[0])
            for point in path_points[1:]:
                path.lineTo(point)

        self.state.path_data[part_name] = path
        self.scene_manager.update_part_path(part_name, path)
        self.motion_path_updated.emit(part_name, path)
        self.state.state_changed.emit()  # Notify UI of path data changes
