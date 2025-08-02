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
        # Reset parts to initial pose when simulation is stopped
        self.scene_manager.reset_parts_to_initial_pose()
        self.request_stop_simulation.emit()

    def handle_reset_simulation(self):
        # Reset parts to initial pose when simulation is reset
        self.scene_manager.reset_parts_to_initial_pose()
        self.request_reset_simulation.emit()

    def handle_clear_motion_path(self):
        part_name = self.state.selected_part_name
        if part_name:
            self.state.clear_path_for_part(part_name)
            self.scene_manager.update_part_path(part_name, QPainterPath())
            self.motion_path_updated.emit(part_name, QPainterPath())

    def handle_freehand_path_completed(self, path_points):
        logger.debug(f"HANDLE_FREEHAND: Motion path completed callback called with {len(path_points) if path_points else 0} points")
        part_name = self.state.selected_part_name
        logger.debug(f"HANDLE_FREEHAND: Current selected part: {part_name}")
        
        if not part_name:
            logger.warning("HANDLE_FREEHAND: No part selected, cannot process motion path")
            return

        # Clear any existing path for this part to ensure only one path per part
        if part_name in self.state.path_data:
            logger.debug(f"HANDLE_FREEHAND: Replacing existing path for part: {part_name}")

        # Path creation logic would be here
        path = QPainterPath()
        if path_points:
            path.moveTo(path_points[0])
            for point in path_points[1:]:
                path.lineTo(point)

        # Store only the latest path for this part
        self.state.path_data[part_name] = path
        logger.debug(f"HANDLE_FREEHAND: Stored path data for part: {part_name}")
        
        self.scene_manager.update_part_path(part_name, path)
        logger.debug(f"HANDLE_FREEHAND: Updated scene manager with path for part: {part_name}")
        
        self.motion_path_updated.emit(part_name, path)
        logger.debug(f"HANDLE_FREEHAND: Emitted motion_path_updated signal for part: {part_name}")
        
        # Emit path_data_changed signal to update MechanismDesign tab with all path data
        if hasattr(self.parent(), 'path_data_changed'):
            self.parent().path_data_changed.emit(self.state.path_data)
            logger.debug(f"HANDLE_FREEHAND: Emitted path_data_changed signal for MechanismDesign tab with {len(self.state.path_data)} paths")
        
        self.state.state_changed.emit()  # Notify UI of path data changes
        logger.debug("HANDLE_FREEHAND: Motion path animation setup completed")

    def resume_animations(self) -> None:
        """Resume any paused animations when tab is activated."""
        logger.debug("EditorActionHandler: Resuming animations")
        # For editor tab, this could resume any paused character or mechanism animations
        # Currently no long-running animation tasks to resume
        pass

    def pause_animations(self) -> None:
        """Pause any running animations when tab is deactivated."""
        logger.debug("EditorActionHandler: Pausing animations")
        # For editor tab, this could pause any running character or mechanism animations
        # Currently no long-running animation tasks to pause
        pass

    def handle_smoothness_changed(self, part_name: str, smoothness: int):
        """Handle smoothness changes for existing paths."""
        if part_name in self.state.path_data:
            # Get the original path data
            original_path = self.state.path_data[part_name]

            # Apply smoothness and update visualization
            smoothed_path = self._apply_smoothness_to_path(original_path, smoothness)
            self.scene_manager.update_part_path(part_name, smoothed_path)
            self.motion_path_updated.emit(part_name, smoothed_path)

            logger.debug(f"Applied {smoothness}% smoothness to path for {part_name}")

    def _apply_smoothness_to_path(self, path: QPainterPath, smoothness: int) -> QPainterPath:
        """Apply spline smoothing to a path based on smoothness percentage."""
        import numpy as np
        from scipy.interpolate import UnivariateSpline

        # Extract points from QPainterPath
        points = self._extract_points_from_path(path)
        if len(points) < 3:
            return path  # Need at least 3 points for spline

        # Convert smoothness percentage to spline smoothing factor
        # 0% = high smoothing factor (more faithful to original)
        # 100% = low smoothing factor (more smoothed)
        smoothing_factor = max(0.01, (100 - smoothness) / 100.0 * len(points))

        # Create spline for x and y coordinates
        t = np.linspace(0, 1, len(points))
        x_coords = [p.x() for p in points]
        y_coords = [p.y() for p in points]

        try:
            # For small number of points, use lower degree spline
            # k = degree of spline, must be < number of points
            k = min(3, len(x_coords) - 1) if len(x_coords) < 4 else 3

            spline_x = UnivariateSpline(t, x_coords, s=smoothing_factor, k=k)
            spline_y = UnivariateSpline(t, y_coords, s=smoothing_factor, k=k)

            # Sample 16 points evenly along the spline
            t_new = np.linspace(0, 1, 16)
            x_new = spline_x(t_new)
            y_new = spline_y(t_new)

            # Create new path
            from PyQt6.QtCore import QPointF

            new_path = QPainterPath()
            new_path.moveTo(QPointF(x_new[0], y_new[0]))
            for i in range(1, len(x_new)):
                new_path.lineTo(QPointF(x_new[i], y_new[i]))

            return new_path

        except Exception as e:
            logger.warning(f"Failed to apply spline smoothing: {e}")
            return path  # Return original path if smoothing fails

    def _extract_points_from_path(self, path: QPainterPath) -> list:
        """Extract points from a QPainterPath."""
        from PyQt6.QtCore import QPointF

        points = []

        # Iterate through path elements
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            points.append(QPointF(element.x, element.y))

        return points
