# src/automataii/ui/views/editor/input_handler.py

import logging
from typing import Optional

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

from .modes import (
    EndEffectorSelectionMode,
    IInteractionMode,
    JointDefinitionMode,
    MotionPathMode,
    PanZoomMode,
    SimulationMode,
)
from .state_manager import EditorMode, EditorViewState

logger = logging.getLogger(__name__)


class EditorInputHandler(QObject):
    """
    Handles input events and delegates them to the appropriate interaction mode.
    Implements the Strategy pattern - different modes handle events differently.
    """

    def __init__(
        self,
        state_manager: EditorViewState,
        view_ref: Optional = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        self.state = state_manager
        self.view_ref = view_ref

        # Initialize available modes
        self._modes: dict[EditorMode, IInteractionMode] = {
            EditorMode.PAN_ZOOM: PanZoomMode(state_manager, view_ref),
            EditorMode.DEFINE_JOINTS: JointDefinitionMode(state_manager, view_ref),
            EditorMode.MOTION_PATH: MotionPathMode(state_manager, view_ref),
            EditorMode.END_EFFECTOR_SELECTION: EndEffectorSelectionMode(state_manager, view_ref),
            EditorMode.SIMULATION: SimulationMode(state_manager, view_ref),
        }

        # Current active mode
        self._current_mode: IInteractionMode = self._modes[EditorMode.PAN_ZOOM]

        # Connect to state changes
        self.state.mode_changed.connect(self._on_mode_changed)

        logger.info("EditorInputHandler initialized")

    def add_mode(self, mode_type: EditorMode, mode_instance: IInteractionMode) -> None:
        """Add a new interaction mode."""
        self._modes[mode_type] = mode_instance
        logger.debug(f"Added mode: {mode_type.value}")

    def get_current_mode(self) -> IInteractionMode:
        """Get the currently active mode."""
        return self._current_mode

    def set_view_reference(self, view_ref) -> None:
        """Set the view reference for all modes."""
        self.view_ref = view_ref
        for mode in self._modes.values():
            mode.view_ref = view_ref

    def _on_mode_changed(self, new_mode: EditorMode) -> None:
        """Handle mode changes from the state manager."""
        if new_mode in self._modes:
            # Exit current mode
            self._current_mode.exit_mode()

            # Switch to new mode
            self._current_mode = self._modes[new_mode]

            # Enter new mode
            self._current_mode.enter_mode()

            logger.info(f"Switched to mode: {new_mode.value}")
        else:
            logger.warning(f"Mode {new_mode.value} not implemented, staying in current mode")

    # Event handling methods that delegate to current mode

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Handle mouse press events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())
        return self._current_mode.handle_mouse_press(event, scene_pos)

    def handle_mouse_move(self, event: QMouseEvent) -> bool:
        """Handle mouse move events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())
        return self._current_mode.handle_mouse_move(event, scene_pos)

    def handle_mouse_release(self, event: QMouseEvent) -> bool:
        """Handle mouse release events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())
        return self._current_mode.handle_mouse_release(event, scene_pos)

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        """Handle mouse double click events."""
        if not self.view_ref:
            return False

        scene_pos = self.view_ref.mapToScene(event.pos())
        return self._current_mode.handle_mouse_double_click(event, scene_pos)

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle wheel events."""
        return self._current_mode.handle_wheel_event(event)

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key press events."""
        return self._current_mode.handle_key_press(event)

    # Public API for mode switching

    def set_pan_zoom_mode(self) -> None:
        """Switch to pan/zoom mode."""
        self.state.set_mode(EditorMode.PAN_ZOOM)

    def set_joint_definition_mode(self) -> None:
        """Switch to joint definition mode."""
        self.state.set_mode(EditorMode.DEFINE_JOINTS)

    def set_motion_path_mode(self) -> None:
        """Switch to motion path mode."""
        self.state.set_mode(EditorMode.MOTION_PATH)

    def set_end_effector_selection_mode(self) -> None:
        """Switch to end effector selection mode."""
        self.state.set_mode(EditorMode.END_EFFECTOR_SELECTION)

    def set_simulation_mode(self) -> None:
        """Switch to simulation mode."""
        self.state.set_mode(EditorMode.SIMULATION)

    # Convenience methods for common operations

    def zoom_in(self) -> None:
        """Zoom in if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_out()

    def reset_view(self) -> None:
        """Reset view if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.reset_view()

    def zoom_to_fit(self) -> None:
        """Zoom to fit if in pan/zoom mode."""
        if isinstance(self._current_mode, PanZoomMode):
            self._current_mode.zoom_to_fit()

    def clear_active_state(self) -> None:
        """Clear any active interaction state when tab is deactivated."""
        # Exit current mode to clean up state
        if self._current_mode:
            self._current_mode.exit_mode()
        
        # Reset to default pan/zoom mode
        self.state.set_mode(EditorMode.PAN_ZOOM)
        
        # Clear any temporary state in all modes
        for mode in self._modes.values():
            if hasattr(mode, 'clear_state'):
                mode.clear_state()
        
        logger.debug("EditorInputHandler active state cleared")
