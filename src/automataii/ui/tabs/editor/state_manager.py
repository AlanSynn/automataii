# src/automataii/ui/tabs/editor/state_manager.py
import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainterPath

from automataii.models.runtime import PartInfo

logger = logging.getLogger(__name__)


class EditorStateManager(QObject):
    """Manages the state of the EditorTab."""

    state_changed = pyqtSignal()
    part_selection_changed = pyqtSignal(str)
    simulation_state_changed = pyqtSignal(bool, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.selected_part_name: str | None = None
        self.current_parts_info: dict[str, PartInfo] = {}
        self.joints: list[dict[str, Any]] = []
        self.initial_skeleton_data_cache: dict[str, Any] | None = None
        self.simulation_state: str = "stopped"
        self.path_data: dict[str, QPainterPath] = {}

    def set_selected_part(self, part_name: str | None) -> None:
        logger.debug(f"SET_SELECTED_PART: Attempting to set selected part to: {part_name}")
        logger.debug(f"SET_SELECTED_PART: Current selected part: {self.selected_part_name}")
        if self.selected_part_name != part_name:
            self.selected_part_name = part_name
            logger.debug(f"SET_SELECTED_PART: Selected part changed to: {part_name}")
            self.part_selection_changed.emit(part_name or "")
            self.state_changed.emit()
        else:
            logger.debug(f"SET_SELECTED_PART: Part name unchanged, no action taken")

    def set_parts_data(self, parts_info: dict[str, PartInfo]) -> None:
        self.current_parts_info = parts_info
        self.state_changed.emit()

    def cache_initial_skeleton(self, skeleton_data: dict[str, Any] | None) -> None:
        self.initial_skeleton_data_cache = skeleton_data
        self.state_changed.emit()

    def set_simulation_state(self, state: str) -> None:
        if self.simulation_state != state:
            self.simulation_state = state
            is_playing = state == "playing"
            can_reset = state != "stopped"
            self.simulation_state_changed.emit(is_playing, can_reset)
            self.state_changed.emit()

    def add_joint(self, joint_data: dict[str, Any]) -> None:
        self.joints.append(joint_data)
        self.state_changed.emit()

    def clear_joints(self) -> None:
        self.joints.clear()
        self.state_changed.emit()

    def update_path_data(self, path_data: dict[str, QPainterPath]) -> None:
        self.path_data = path_data
        self.state_changed.emit()

    def clear_path_for_part(self, part_name: str) -> None:
        if part_name in self.path_data:
            del self.path_data[part_name]
            self.state_changed.emit()

    def clear_all_paths(self) -> None:
        self.path_data.clear()
        self.state_changed.emit()

    def clear_all(self) -> None:
        self.selected_part_name = None
        self.current_parts_info.clear()
        self.joints.clear()
        self.initial_skeleton_data_cache = None
        self.simulation_state = "stopped"
        self.path_data.clear()
        self.state_changed.emit()
