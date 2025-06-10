"""Controller for editor operations, coordinating between UI and services."""

import logging
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from ..services import PathDrawingService, AnimationService, DrawingMode, AnimationState
from ..interfaces import IKManagerInterface, ProjectManagerInterface, SkeletonManagerInterface


@dataclass
class EditorState:
    """Represents the current state of the editor."""
    selected_part: Optional[str] = None
    drawing_mode: DrawingMode = DrawingMode.SELECT
    animation_state: AnimationState = AnimationState.STOPPED
    has_parts: bool = False
    has_skeleton: bool = False


class EditorController(QObject):
    """Controller for editor operations.

    This controller coordinates between the EditorTab UI and various services,
    reducing the complexity and responsibilities of the EditorTab.
    """

    # Signals for UI updates
    state_changed = pyqtSignal(EditorState)
    parts_updated = pyqtSignal(dict)  # parts_info
    skeleton_updated = pyqtSignal(dict)  # skeleton_data
    path_drawing_started = pyqtSignal(str)  # part_name
    path_drawing_completed = pyqtSignal(str, QPainterPath)  # part_name, path
    animation_frame_updated = pyqtSignal(dict)  # frame_data
    error_occurred = pyqtSignal(str)  # error_message

    def __init__(
        self,
        path_service: PathDrawingService,
        animation_service: AnimationService,
        ik_manager: IKManagerInterface,
        project_manager: ProjectManagerInterface,
        skeleton_manager: SkeletonManagerInterface
    ):
        super().__init__()

        # Services
        self._path_service = path_service
        self._animation_service = animation_service
        self._ik_manager = ik_manager
        self._project_manager = project_manager
        self._skeleton_manager = skeleton_manager

        # State
        self._state = EditorState()
        self._current_parts: Dict[str, Any] = {}
        self._active_path_id: Optional[str] = None

        # Connect service signals
        self._connect_service_signals()

        logging.info("EditorController initialized")

    def _connect_service_signals(self) -> None:
        """Connect signals from services."""
        # Path service signals
        self._path_service.path_started.connect(self._on_path_started)
        self._path_service.path_completed.connect(self._on_path_completed)
        self._path_service.path_cleared.connect(self._on_path_cleared)

        # Animation service signals
        self._animation_service.state_changed.connect(self._on_animation_state_changed)
        self._animation_service.frame_updated.connect(self._on_animation_frame_updated)

    # === Part Management ===

    def load_parts(self, parts_data: Dict[str, Any]) -> bool:
        """Load parts data into the editor.

        Args:
            parts_data: Dictionary of part information

        Returns:
            True if loaded successfully
        """
        if not parts_data:
            logging.warning("EditorController: No parts data to load")
            return False

        self._current_parts = parts_data.copy()
        self._state.has_parts = True

        # Clear any existing paths
        self._path_service.clear_all()

        # Update state and notify UI
        self._emit_state_change()
        self.parts_updated.emit(self._current_parts)

        logging.info(f"EditorController: Loaded {len(parts_data)} parts")
        return True

    def select_part(self, part_name: Optional[str]) -> None:
        """Select a part for editing.

        Args:
            part_name: Name of the part to select, or None to deselect
        """
        if part_name and part_name not in self._current_parts:
            logging.warning(f"EditorController: Part '{part_name}' not found")
            return

        self._state.selected_part = part_name
        self._emit_state_change()

        logging.info(f"EditorController: Selected part '{part_name}'")

    def get_selected_part(self) -> Optional[str]:
        """Get the currently selected part name."""
        return self._state.selected_part

    def clear_parts(self) -> None:
        """Clear all parts from the editor."""
        self._current_parts.clear()
        self._state.has_parts = False
        self._state.selected_part = None

        # Clear paths and stop animation
        self._path_service.clear_all()
        self._animation_service.stop()

        self._emit_state_change()
        self.parts_updated.emit({})

        logging.info("EditorController: Cleared all parts")

    # === Path Drawing ===

    def set_drawing_mode(self, mode: DrawingMode) -> None:
        """Set the drawing mode.

        Args:
            mode: Drawing mode to set
        """
        self._path_service.set_mode(mode)
        self._state.drawing_mode = mode
        self._emit_state_change()

    def start_path_drawing(self, start_point: QPointF) -> bool:
        """Start drawing a path for the selected part.

        Args:
            start_point: Starting point for the path

        Returns:
            True if started successfully
        """
        if not self._state.selected_part:
            self.error_occurred.emit("No part selected for path drawing")
            return False

        if self._state.animation_state == AnimationState.PLAYING:
            self.error_occurred.emit("Cannot draw path while animation is playing")
            return False

        # Start path in service
        path_id = self._path_service.start_path(self._state.selected_part, start_point)
        if path_id:
            self._active_path_id = path_id
            return True

        return False

    def add_path_point(self, point: QPointF) -> bool:
        """Add a point to the current path.

        Args:
            point: Point to add

        Returns:
            True if added successfully
        """
        if not self._active_path_id:
            return False

        return self._path_service.add_point(self._active_path_id, point)

    def complete_path_drawing(self) -> Optional[QPainterPath]:
        """Complete the current path drawing.

        Returns:
            Completed path or None
        """
        if not self._active_path_id:
            return None

        path = self._path_service.complete_path(self._active_path_id)
        self._active_path_id = None
        return path

    def cancel_path_drawing(self) -> None:
        """Cancel the current path drawing."""
        if self._active_path_id:
            self._path_service.cancel_path(self._active_path_id)
            self._active_path_id = None

    def clear_part_path(self, part_name: Optional[str] = None) -> bool:
        """Clear the path for a part.

        Args:
            part_name: Part name, or None to use selected part

        Returns:
            True if cleared successfully
        """
        target_part = part_name or self._state.selected_part
        if not target_part:
            return False

        return self._path_service.clear_path(target_part)

    def get_part_path(self, part_name: str) -> Optional[QPainterPath]:
        """Get the path for a part.

        Args:
            part_name: Name of the part

        Returns:
            Path or None
        """
        return self._path_service.get_path(part_name)

    def get_all_paths(self) -> Dict[str, QPainterPath]:
        """Get all paths."""
        return self._path_service.get_all_paths()

    # === Animation ===

    def play_animation(self) -> bool:
        """Start animation playback.

        Returns:
            True if started successfully
        """
        if not self._state.has_parts:
            self.error_occurred.emit("No parts loaded for animation")
            return False

        # Generate animation frames from paths
        paths = self._path_service.get_all_paths()
        if not paths:
            self.error_occurred.emit("No motion paths defined")
            return False

        # Get initial positions from parts
        initial_positions = {}
        for part_name, part_info in self._current_parts.items():
            if hasattr(part_info, 'position'):
                initial_positions[part_name] = part_info.position
            else:
                initial_positions[part_name] = QPointF(0, 0)

        # Generate frames and start animation
        if self._animation_service.generate_frames_from_paths(paths, initial_positions):
            return self._animation_service.play()

        return False

    def pause_animation(self) -> None:
        """Pause animation playback."""
        self._animation_service.pause()

    def stop_animation(self) -> None:
        """Stop animation playback."""
        self._animation_service.stop()

    def reset_animation(self) -> None:
        """Reset animation to beginning."""
        self._animation_service.reset()

    def set_animation_duration(self, duration_ms: int) -> None:
        """Set animation duration.

        Args:
            duration_ms: Duration in milliseconds
        """
        self._animation_service.set_duration(duration_ms)
        self._ik_manager.set_animation_duration(duration_ms)

    def seek_animation(self, progress: float) -> None:
        """Seek to animation position.

        Args:
            progress: Progress value (0.0 to 1.0)
        """
        self._animation_service.seek_to_progress(progress)

    # === Skeleton Management ===

    def load_skeleton(self, skeleton_data: Dict[str, Any]) -> bool:
        """Load skeleton data into the editor."""
        # Prevents recursion by not reloading if data is the same
        if (
            self._state.has_skeleton
            and self._skeleton_manager.get_skeleton_as_dict() == skeleton_data
        ):
            self.skeleton_updated.emit(skeleton_data)
            return True

        if not self._skeleton_manager.load_skeleton_from_dict(skeleton_data):
            self.skeleton_updated.emit({})  # Emit empty on failure
            return False

        self._state.has_skeleton = True
        # skeleton_data from skeleton_manager is emitted
        standardized_skeleton = self._skeleton_manager.get_skeleton_as_dict()
        self.skeleton_updated.emit(standardized_skeleton)
        logging.info(f"EditorController: Loaded skeleton data")

        return True

    # === State Management ===

    def get_current_state(self) -> EditorState:
        """Get the current editor state."""
        return self._state

    def can_draw_path(self) -> bool:
        """Check if path drawing is allowed."""
        return (
            self._state.has_parts and
            self._state.selected_part is not None and
            self._state.animation_state != AnimationState.PLAYING
        )

    def can_play_animation(self) -> bool:
        """Check if animation can be played."""
        return (
            self._state.has_parts and
            bool(self._path_service.get_all_paths()) and
            self._state.animation_state != AnimationState.PLAYING
        )

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        # Check if paths have been drawn but not saved
        current_paths = self._path_service.get_all_paths()
        saved_paths = self._project_manager.get_motion_paths()

        return current_paths != saved_paths

    # === Event Handlers ===

    def _on_path_started(self, path_id: str, part_name: str) -> None:
        """Handle path started event from service."""
        self.path_drawing_started.emit(part_name)

    def _on_path_completed(self, path_id: str, part_name: str, path: QPainterPath) -> None:
        """Handle path completed event from service."""
        self.path_drawing_completed.emit(part_name, path)

        # Update project data
        motion_paths = self._project_manager.get_motion_paths()
        motion_paths[part_name] = path
        self._project_manager.set_motion_paths(motion_paths)

    def _on_path_cleared(self, part_name: str) -> None:
        """Handle path cleared event from service."""
        # Update project data
        motion_paths = self._project_manager.get_motion_paths()
        if part_name in motion_paths:
            del motion_paths[part_name]
            self._project_manager.set_motion_paths(motion_paths)

    def _on_animation_state_changed(self, state: AnimationState) -> None:
        """Handle animation state change."""
        self._state.animation_state = state
        self._emit_state_change()

    def _on_animation_frame_updated(self, frame) -> None:
        """Handle animation frame update."""
        # Convert frame to dictionary for UI
        frame_data = {
            'timestamp': frame.timestamp,
            'positions': frame.positions,
            'rotations': frame.rotations
        }
        self.animation_frame_updated.emit(frame_data)

    def _emit_state_change(self) -> None:
        """Emit state change signal."""
        self.state_changed.emit(self._state)

    # === Utility Methods ===

    def export_animation_data(self) -> Dict[str, Any]:
        """Export animation data for saving.

        Returns:
            Dictionary of animation data
        """
        return {
            'paths': {
                part: self._serialize_path(path)
                for part, path in self._path_service.get_all_paths().items()
            },
            'duration': self._animation_service._duration_ms,
            'fps': self._animation_service._fps,
            'frames': self._animation_service.export_frames()
        }

    def _serialize_path(self, path: QPainterPath) -> List[Dict[str, float]]:
        """Serialize a QPainterPath.

        Args:
            path: Path to serialize

        Returns:
            List of point dictionaries
        """
        points = []
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            points.append({'x': element.x, 'y': element.y})
        return points