# src/automataii/ui/views/editor/modes/motion_path_mode.py

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem

from automataii.core.event_bus import get_global_event_bus
from automataii.core.events import (
    MotionPathCancelledEvent,
    MotionPathCompletedEvent,
    MotionPathPointAddedEvent,
    MotionPathStartedEvent,
)
from automataii.core.performance_monitor import time_operation

from .base_mode import IInteractionMode

logger = logging.getLogger(__name__)


class MotionPathMode(IInteractionMode):
    """
    Interaction mode for drawing motion paths.
    Allows users to click points to define a motion path for a selected part.
    """

    def __init__(self, state_manager, view_ref: Optional = None):
        super().__init__(state_manager, view_ref)

        # Event bus for event-driven architecture
        self.event_bus = get_global_event_bus()

        # Visual elements for path drawing
        self.path_item: QGraphicsPathItem | None = None
        self.point_items: list[QGraphicsEllipseItem] = []
        self.preview_line: QGraphicsItem | None = None

        # Path styling
        self.drawing_path_pen = QPen(QColor(255, 60, 60), 3)  # Red during drawing
        self.completed_path_pen = QPen(QColor(0, 200, 80), 3)  # Green when completed
        self.point_pen = QPen(QColor(255, 165, 0), 2)  # Orange points
        self.point_brush = QColor(255, 165, 0, 100)  # Semi-transparent orange
        self.point_radius = 6

        # Track current part name for event publishing
        self.current_part_name = None

        # Track whether path should be closed
        self.closed_path = False

        # Track smoothness level (0-100%)
        self.smoothness = 50
        
        # Track drag state for continuous drawing
        self.is_dragging = False
        self.last_drag_pos = None
        self.drag_threshold = 5.0  # Minimum distance before adding new point
        self.show_points_during_drag = False  # Hide individual points while dragging

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press for starting drag-based path drawing."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.last_drag_pos = scene_pos
            self._add_path_point(scene_pos)
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self._complete_path()
            return True

        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for drag-based drawing and preview line."""
        if self.is_dragging and self.last_drag_pos:
            # Calculate distance from last point
            from PyQt6.QtCore import QPointF
            dx = scene_pos.x() - self.last_drag_pos.x()
            dy = scene_pos.y() - self.last_drag_pos.y()
            distance = (dx * dx + dy * dy) ** 0.5
            
            # Add point if we've moved far enough
            if distance >= self.drag_threshold:
                self._add_path_point(scene_pos)
                self.last_drag_pos = scene_pos
                return True
        elif self.state.motion_path_points:
            # Show preview line when not dragging
            self._update_preview_line(scene_pos)
        
        return False

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release - complete path automatically."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.last_drag_pos = None
            # Add final point if we haven't added one recently
            if self.state.motion_path_points:
                last_point = self.state.motion_path_points[-1]
                dx = scene_pos.x() - last_point.x()
                dy = scene_pos.y() - last_point.y()
                distance = (dx * dx + dy * dy) ** 0.5
                if distance >= self.drag_threshold:
                    self._add_path_point(scene_pos)
            
            # Auto-complete path on mouse release
            if len(self.state.motion_path_points) >= 2:
                self._complete_path()
            
            return True
        return False

    def handle_mouse_double_click(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle double click to complete path."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._complete_path()
            return True
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key presses for motion path shortcuts."""
        key = event.key()

        # Escape to cancel path drawing
        if key == Qt.Key.Key_Escape:
            self._cancel_path()
            return True

        # Enter to complete path
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._complete_path()
            return True

        # Backspace to remove last point
        elif key == Qt.Key.Key_Backspace:
            self._remove_last_point()
            return True

        # Delete to clear all points
        elif key == Qt.Key.Key_Delete:
            self._clear_all_points()
            return True

        return False

    def _add_path_point(self, scene_pos: QPointF) -> None:
        """Add a point to the motion path."""
        with time_operation("motion_path_add_point"):
            if not self.view_ref or not self.view_ref.scene():
                return

            # Add point to state
            self.state.motion_path_points.append(scene_pos)

            # Publish event for point addition
            if self.current_part_name:
                self.event_bus.publish(
                    MotionPathPointAddedEvent(
                        part_name=self.current_part_name,
                        point=scene_pos,
                        point_index=len(self.state.motion_path_points) - 1,
                    )
                )

            # Create visual point
            point_item = QGraphicsEllipseItem(
                scene_pos.x() - self.point_radius,
                scene_pos.y() - self.point_radius,
                self.point_radius * 2,
                self.point_radius * 2,
            )
            point_item.setPen(self.point_pen)
            point_item.setBrush(self.point_brush)
            point_item.setZValue(1000)  # High Z-value to ensure visibility
            
            # Always hide individual points - we only show the path
            point_item.setVisible(False)

            self.view_ref.scene().addItem(point_item)
            self.point_items.append(point_item)
            
            logger.debug(f"Added visual point item to scene. Point items count: {len(self.point_items)}")
            logger.debug(f"Scene items count: {len(self.view_ref.scene().items())}")

            # Update path visualization
            self._update_path_visualization()

            logger.debug(f"Added motion path point at {scene_pos}")

    def _update_path_visualization(self) -> None:
        """Update the visual representation of the motion path."""
        with time_operation("motion_path_update_visualization"):
            if not self.view_ref or not self.view_ref.scene():
                logger.debug("No view_ref or scene available for path visualization")
                return

            points = self.state.motion_path_points
            logger.debug(f"Updating path visualization with {len(points)} points")
            
            if len(points) < 2:
                logger.debug("Less than 2 points, skipping path visualization")
                return

            # Remove existing path item
            if self.path_item:
                self.view_ref.scene().removeItem(self.path_item)
                logger.debug("Removed existing path item")

            # During drawing: show raw lines, After completion: apply smoothing
            if self.is_dragging:
                # Raw drawing during drag - no smoothing
                path = self._create_smoothed_path(points, 0, self.closed_path)  # smoothness=0 for raw lines
            else:
                # Apply spline smoothing after drawing is completed
                path = self._create_smoothed_path(points, self.smoothness, self.closed_path)

            # Create path item
            self.path_item = QGraphicsPathItem(path)
            
            # Use dotted line during drag, solid line when completed
            if self.is_dragging:
                dotted_pen = QPen(self.drawing_path_pen)
                dotted_pen.setStyle(Qt.PenStyle.DashLine)
                dotted_pen.setWidth(2)
                self.path_item.setPen(dotted_pen)
            else:
                self.path_item.setPen(self.drawing_path_pen)
                
            self.path_item.setZValue(999)  # High Z-value to ensure visibility

            self.view_ref.scene().addItem(self.path_item)
            logger.debug(f"Added path item to scene. Scene items count: {len(self.view_ref.scene().items())}")

    def _update_preview_line(self, current_pos: QPointF) -> None:
        """Update preview line from last point to current cursor position."""
        if not self.view_ref or not self.view_ref.scene() or not self.state.motion_path_points:
            return

        # Remove existing preview line
        if self.preview_line:
            self.view_ref.scene().removeItem(self.preview_line)
            self.preview_line = None

        # Create new preview line
        last_point = self.state.motion_path_points[-1]
        path = QPainterPath()
        path.moveTo(last_point)
        path.lineTo(current_pos)

        preview_pen = QPen(self.drawing_path_pen)
        preview_pen.setStyle(Qt.PenStyle.DashLine)
        preview_pen.setColor(QColor(0, 120, 215, 128))  # Semi-transparent

        self.preview_line = QGraphicsPathItem(path)
        self.preview_line.setPen(preview_pen)
        self.preview_line.setZValue(998)  # High Z-value to ensure visibility

        self.view_ref.scene().addItem(self.preview_line)

    def _remove_last_point(self) -> None:
        """Remove the last point from the motion path."""
        if not self.state.motion_path_points:
            return

        # Remove from state
        self.state.motion_path_points.pop()

        # Remove visual point
        if self.point_items:
            point_item = self.point_items.pop()
            if self.view_ref and self.view_ref.scene():
                self.view_ref.scene().removeItem(point_item)

        # Update path visualization
        self._update_path_visualization()

        logger.debug("Removed last motion path point")

    def _clear_all_points(self) -> None:
        """Clear all points from the motion path."""
        # Clear state
        self.state.motion_path_points.clear()

        # Remove all visual elements
        self._clear_visual_elements()

        logger.debug("Cleared all motion path points")

    def _complete_path(self) -> None:
        """Complete the motion path and return to pan/zoom mode."""
        if len(self.state.motion_path_points) < 2:
            logger.warning("Motion path needs at least 2 points")
            return

        logger.info(f"COMPLETE_PATH: Motion path completed with {len(self.state.motion_path_points)} points")
        
        # Keep points hidden - we only show the completed path

        # Convert motion path points to QPainterPath with smoothing
        motion_path = self._create_smoothed_path(
            self.state.motion_path_points, self.smoothness, self.closed_path
        )

        # Ensure is_dragging is False to trigger spline smoothing
        self.is_dragging = False
        
        # Update path visualization to show smoothed spline
        self._update_path_visualization()
        
        # Update path color to green and make it solid when completed
        if self.path_item:
            logger.info(f"COMPLETE_PATH: Updating existing path item to green solid line")
            solid_pen = QPen(self.completed_path_pen)
            solid_pen.setStyle(Qt.PenStyle.SolidLine)  # Ensure solid line
            self.path_item.setPen(solid_pen)
            logger.info(f"COMPLETE_PATH: Path item in scene: {self.path_item.scene() is not None}")
            logger.info(f"COMPLETE_PATH: Path item visible: {self.path_item.isVisible()}")
            logger.info(f"COMPLETE_PATH: Path item Z-value: {self.path_item.zValue()}")
            logger.info(f"COMPLETE_PATH: Path item bounding rect: {self.path_item.boundingRect()}")
        else:
            logger.warning("COMPLETE_PATH: No path item to update for completion!")

        # Publish event for motion path completion - EVENT BUS INTEGRATION!
        if self.current_part_name:
            self.event_bus.publish(
                MotionPathCompletedEvent(
                    part_name=self.current_part_name,
                    path_points=self.state.motion_path_points.copy(),
                    path_data=motion_path,
                )
            )
            logger.info(f"Published MotionPathCompletedEvent for part {self.current_part_name}")

        # Keep legacy signal for backward compatibility during transition
        if self.view_ref and hasattr(self.view_ref, "freehandPathCompleted"):
            self.view_ref.freehandPathCompleted.emit(self.state.motion_path_points)
            logger.info("Emitted legacy freehandPathCompleted signal")

        # Clean up state but keep the completed path visible
        logger.info("COMPLETE_PATH: Calling _cleanup_path_drawing_state_only to preserve completed path")
        self._cleanup_path_drawing_state_only()
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def _cancel_path(self) -> None:
        """Cancel motion path drawing and return to pan/zoom mode."""
        logger.info("Motion path drawing cancelled")

        # Publish event for motion path cancellation
        if self.current_part_name:
            self.event_bus.publish(MotionPathCancelledEvent(part_name=self.current_part_name))

        # Clear all points and return to pan/zoom mode
        self._clear_all_points()
        self._cleanup_path_drawing()
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def _cleanup_path_drawing(self) -> None:
        """Clean up all path drawing state and visuals."""
        self._clear_visual_elements()
        self.state.motion_path_points.clear()
        self.state.motion_path_target_item = None
        self.state.is_drawing_motion_path = False

    def _cleanup_path_drawing_state_only(self) -> None:
        """Clean up path drawing state but keep completed path visible."""
        logger.info("CLEANUP_STATE_ONLY: Starting cleanup while preserving completed path")
        
        # Only clear the hidden points, keep the completed path
        if not self.view_ref or not self.view_ref.scene():
            logger.warning("CLEANUP_STATE_ONLY: No view_ref or scene available")
            return

        # Remove only the hidden point items
        logger.info(f"CLEANUP_STATE_ONLY: Removing {len(self.point_items)} hidden point items")
        for point_item in self.point_items:
            self.view_ref.scene().removeItem(point_item)
        self.point_items.clear()

        # Keep the path_item visible as the completed path
        if self.path_item:
            logger.info(f"CLEANUP_STATE_ONLY: Preserving path_item. Still in scene: {self.path_item.scene() is not None}")
            logger.info(f"CLEANUP_STATE_ONLY: Path item still visible: {self.path_item.isVisible()}")
        else:
            logger.warning("CLEANUP_STATE_ONLY: No path_item to preserve!")
            
        # Clear state but keep motion_path_points for the completed path
        self.state.motion_path_target_item = None
        self.state.is_drawing_motion_path = False
        logger.info("CLEANUP_STATE_ONLY: State cleanup completed, path should remain visible")

    def _clear_visual_elements(self) -> None:
        """Remove all visual elements from the scene."""
        if not self.view_ref or not self.view_ref.scene():
            return

        # Remove path item
        if self.path_item:
            self.view_ref.scene().removeItem(self.path_item)
            self.path_item = None

        # Remove preview line
        if self.preview_line:
            self.view_ref.scene().removeItem(self.preview_line)
            self.preview_line = None

        # Remove all point items
        for point_item in self.point_items:
            self.view_ref.scene().removeItem(point_item)
        self.point_items.clear()

    def get_cursor(self):
        """Return cursor for motion path mode."""
        return Qt.CursorShape.CrossCursor

    def enter_mode(self) -> None:
        """Setup when entering motion path mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())

        # Get current part name from multiple sources
        logger.info("ENTER_MODE: Attempting to find selected part name from multiple sources")
        
        # First try: view state's selected_part_name
        if hasattr(self.state, "selected_part_name") and self.state.selected_part_name:
            self.current_part_name = self.state.selected_part_name
            logger.info(f"ENTER_MODE: Found current_part_name from view state: {self.current_part_name}")
        # Second try: get from parent tab's state via view_ref
        elif (self.view_ref and hasattr(self.view_ref, 'parent') and 
              hasattr(self.view_ref.parent(), 'state') and 
              hasattr(self.view_ref.parent().state, 'selected_part_name') and
              self.view_ref.parent().state.selected_part_name):
            self.current_part_name = self.view_ref.parent().state.selected_part_name
            logger.info(f"ENTER_MODE: Found current_part_name from tab state: {self.current_part_name}")
        # Third try: motion_path_target_item
        elif hasattr(self.state, "motion_path_target_item") and self.state.motion_path_target_item:
            target_item = self.state.motion_path_target_item
            if hasattr(target_item, "part_info") and target_item.part_info and hasattr(target_item.part_info, "name"):
                self.current_part_name = target_item.part_info.name
                logger.info(f"ENTER_MODE: Found current_part_name from target_item: {self.current_part_name}")
            else:
                logger.warning(f"ENTER_MODE: Target item has no valid part_info: {target_item}")
                self.current_part_name = None
        else:
            logger.warning("ENTER_MODE: No selected part name found from any source")
            self.current_part_name = None

        # Publish event for motion path started
        if self.current_part_name:
            self.event_bus.publish(
                MotionPathStartedEvent(
                    part_name=self.current_part_name,
                    target_item=getattr(self.state, "motion_path_target_item", None),
                )
            )

        logger.info(f"Entered motion path mode for part: {self.current_part_name}")

    def exit_mode(self) -> None:
        """Cleanup when exiting motion path mode."""
        logger.info("EXIT_MODE: Starting mode exit")
        
        # If we have a completed path (path_item exists and has green pen), preserve it
        if self.path_item and hasattr(self.path_item, 'pen') and self.path_item.pen().color() == self.completed_path_pen.color():
            logger.info("EXIT_MODE: Preserving completed path, only clearing points and preview")
            # Only clear points and preview, keep the completed path
            if self.preview_line and self.view_ref and self.view_ref.scene():
                self.view_ref.scene().removeItem(self.preview_line)
                self.preview_line = None
                
            # Remove all point items but keep the completed path
            for point_item in self.point_items:
                if self.view_ref and self.view_ref.scene():
                    self.view_ref.scene().removeItem(point_item)
            self.point_items.clear()
            
            logger.info(f"EXIT_MODE: Preserved completed path. Still in scene: {self.path_item.scene() is not None}")
        else:
            logger.info("EXIT_MODE: No completed path to preserve, clearing all visual elements")
            self._clear_visual_elements()
            
        # Reset drag state
        self.is_dragging = False
        self.last_drag_pos = None
        logger.info("Exited motion path mode")

    def set_closed_path(self, closed: bool) -> None:
        """Set whether the motion path should be closed."""
        self.closed_path = closed
        # Update visualization if we have points
        if self.state.motion_path_points:
            self._update_path_visualization()
        logger.debug(f"Motion path closed setting: {closed}")

    def set_smoothness(self, smoothness: int) -> None:
        """Set the smoothness level for motion paths."""
        self.smoothness = smoothness
        # Update visualization if we have points
        if self.state.motion_path_points:
            self._update_path_visualization()
        logger.debug(f"Motion path smoothness setting: {smoothness}%")

    def _create_smoothed_path(self, points: list, smoothness: int, closed: bool) -> QPainterPath:
        """Create a smoothed QPainterPath from points using spline interpolation."""
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPainterPath

        path = QPainterPath()
        if not points:
            return path

        if len(points) < 3 or smoothness == 0:
            # No smoothing - use original points
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if closed and len(points) >= 3:
                path.lineTo(points[0])
            return path

        try:
            import numpy as np
            from scipy.interpolate import UnivariateSpline

            # Convert smoothness percentage to spline smoothing factor
            # 0% = high smoothing factor (more faithful to original)
            # 100% = low smoothing factor (more smoothed)
            smoothing_factor = max(0.01, (100 - smoothness) / 100.0 * len(points))

            # Create parameter t for spline
            t = np.linspace(0, 1, len(points))
            x_coords = [p.x() for p in points]
            y_coords = [p.y() for p in points]

            # If closed path, duplicate the first point at the end for continuity
            if closed:
                t = np.concatenate([t, [1.1]])  # Slightly beyond 1 to avoid duplicate parameter
                x_coords.append(x_coords[0])
                y_coords.append(y_coords[0])

            # For small number of points, use lower degree spline
            # k = degree of spline, must be < number of points
            k = min(3, len(x_coords) - 1) if len(x_coords) < 4 else 3

            # Create splines with appropriate degree
            spline_x = UnivariateSpline(t, x_coords, s=smoothing_factor, k=k)
            spline_y = UnivariateSpline(t, y_coords, s=smoothing_factor, k=k)

            # Sample 16 points evenly along the spline
            t_end = 1.0 if not closed else 1.1
            t_new = np.linspace(0, t_end, 16)
            x_new = spline_x(t_new)
            y_new = spline_y(t_new)

            # Create smoothed path
            path.moveTo(QPointF(x_new[0], y_new[0]))
            for i in range(1, len(x_new)):
                path.lineTo(QPointF(x_new[i], y_new[i]))

            return path

        except Exception as e:
            logger.warning(f"Failed to create smoothed path: {e}")
            # Fall back to original path
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if closed and len(points) >= 3:
                path.lineTo(points[0])
            return path
