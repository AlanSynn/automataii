# src/automataii/ui/views/editor/state_manager.py

import logging
from enum import Enum

from PyQt6.QtCore import QObject, QPointF, pyqtSignal

logger = logging.getLogger(__name__)


class EditorMode(Enum):
    """Available interaction modes for the editor view."""

    PAN_ZOOM = "pan_zoom"
    DEFINE_JOINTS = "define_joints"
    MOTION_PATH = "motion_path"
    END_EFFECTOR_SELECTION = "end_effector_selection"
    SIMULATION = "simulation"


class EditorViewState(QObject):
    """
    Manages state for the EditorView.
    Handles current mode, view settings, and temporary state.
    """

    # Signals for state changes
    mode_changed = pyqtSignal(EditorMode)
    zoom_changed = pyqtSignal(float)
    selected_part_changed = pyqtSignal(str)  # part name
    joint_map_changed = pyqtSignal(dict)
    display_unit_changed = pyqtSignal(str)
    state_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Current interaction mode
        self.current_mode: EditorMode = EditorMode.PAN_ZOOM

        # View settings
        self.zoom_level: float = 1.0
        self.display_unit: str = "cm"

        # Selection state
        self.selected_part_name: str | None = None
        self.selected_item = None  # Reference to actual graphics item

        # Joint mapping for skeleton
        self.joint_map: dict[str, str] | None = None

        # Temporary state for interactions
        self.is_defining_joint: bool = False
        self.is_drawing_motion_path: bool = False
        self.is_selecting_end_effector: bool = False
        self.is_simulating: bool = False

        # Motion path state
        self.motion_path_target_item = None
        self.motion_path_points: list[QPointF] = []

        # Joint definition state
        self.joint_definition_state = {
            "target_parent_item": None,
            "target_child_item": None,
            "awaiting_parent": True,
            "awaiting_child": False,
        }

        # End effector selection state
        self.end_effector_target_item = None

    def set_mode(self, mode: EditorMode) -> None:
        """Set the current interaction mode."""
        if self.current_mode != mode:
            old_mode = self.current_mode
            self.current_mode = mode
            self.mode_changed.emit(mode)
            self.state_changed.emit()
            logger.info(f"Editor mode changed from {old_mode.value} to {mode.value}")

            # Reset mode-specific state when changing modes
            self._reset_mode_state(old_mode)

    def _reset_mode_state(self, old_mode: EditorMode) -> None:
        """Reset state when exiting a mode."""
        if old_mode == EditorMode.DEFINE_JOINTS:
            self.is_defining_joint = False
            self.joint_definition_state = {
                "target_parent_item": None,
                "target_child_item": None,
                "awaiting_parent": True,
                "awaiting_child": False,
            }
        elif old_mode == EditorMode.MOTION_PATH:
            self.is_drawing_motion_path = False
            self.motion_path_target_item = None
            self.motion_path_points.clear()
        elif old_mode == EditorMode.END_EFFECTOR_SELECTION:
            self.is_selecting_end_effector = False
            self.end_effector_target_item = None
        elif old_mode == EditorMode.SIMULATION:
            self.is_simulating = False

    def set_zoom_level(self, zoom: float) -> None:
        """Set the current zoom level."""
        if self.zoom_level != zoom:
            self.zoom_level = zoom
            self.zoom_changed.emit(zoom)
            self.state_changed.emit()

    def set_selected_part(self, part_name: str | None, item=None) -> None:
        """Set the currently selected part."""
        if self.selected_part_name != part_name:
            self.selected_part_name = part_name
            self.selected_item = item
            self.selected_part_changed.emit(part_name or "")
            self.state_changed.emit()

    def set_joint_map(self, joint_map: dict[str, str] | None) -> None:
        """Set the joint mapping for skeleton."""
        if self.joint_map != joint_map:
            self.joint_map = joint_map
            self.joint_map_changed.emit(joint_map or {})
            self.state_changed.emit()

    def set_display_unit(self, unit: str) -> None:
        """Set the display unit."""
        if self.display_unit != unit:
            self.display_unit = unit
            self.display_unit_changed.emit(unit)
            self.state_changed.emit()

    def start_joint_definition(self, parent_item, child_item) -> None:
        """Start joint definition mode."""
        self.is_defining_joint = True
        self.joint_definition_state = {
            "target_parent_item": parent_item,
            "target_child_item": child_item,
            "awaiting_parent": True,
            "awaiting_child": False,
        }
        self.set_mode(EditorMode.DEFINE_JOINTS)

    def start_motion_path_drawing(self, target_item) -> None:
        """Start motion path drawing mode."""
        self.is_drawing_motion_path = True
        self.motion_path_target_item = target_item
        self.motion_path_points.clear()
        self.set_mode(EditorMode.MOTION_PATH)

    def start_end_effector_selection(self, target_item) -> None:
        """Start end effector selection mode."""
        self.is_selecting_end_effector = True
        self.end_effector_target_item = target_item
        self.set_mode(EditorMode.END_EFFECTOR_SELECTION)

    def start_simulation(self) -> None:
        """Start simulation mode."""
        self.is_simulating = True
        self.set_mode(EditorMode.SIMULATION)

    def stop_simulation(self) -> None:
        """Stop simulation and return to pan/zoom mode."""
        self.is_simulating = False
        self.set_mode(EditorMode.PAN_ZOOM)

    def get_current_mode(self) -> EditorMode:
        """Get the current interaction mode."""
        return self.current_mode

    def is_in_mode(self, mode: EditorMode) -> bool:
        """Check if currently in the specified mode."""
        return self.current_mode == mode

    def clear_all_temporary_state(self) -> None:
        """Clear all temporary interaction state."""
        self.is_defining_joint = False
        self.is_drawing_motion_path = False
        self.is_selecting_end_effector = False
        self.is_simulating = False
        self.motion_path_points.clear()
        self.joint_definition_state = {
            "target_parent_item": None,
            "target_child_item": None,
            "awaiting_parent": True,
            "awaiting_child": False,
        }
        self.motion_path_target_item = None
        self.end_effector_target_item = None
        logger.info("All temporary editor state cleared")
