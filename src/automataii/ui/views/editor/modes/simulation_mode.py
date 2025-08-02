# src/automataii/ui/views/editor/modes/simulation_mode.py

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PyQt6.QtWidgets import QGraphicsItem

from .base_mode import IInteractionMode

logger = logging.getLogger(__name__)


class SimulationMode(IInteractionMode):
    """
    Interaction mode for running mechanism simulations.
    Handles simulation controls and provides limited interaction during simulation.
    """

    def __init__(self, state_manager, view_ref: Optional = None):
        super().__init__(state_manager, view_ref)

        # Simulation state
        self.is_simulation_running = False
        self.simulation_paused = False
        self.simulation_timer: QTimer | None = None

        # Simulation settings
        self.simulation_speed = 1.0  # Speed multiplier
        self.frame_rate = 60  # Target FPS

        # Interactive elements during simulation
        self.dragging_item = None
        self.drag_start_pos = None
        self.is_dragging = False

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press during simulation."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Allow dragging of certain items during simulation
            item = self._find_draggable_item(scene_pos)
            if item:
                self._start_dragging(item, scene_pos)
                return True
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click to pause/resume simulation
            self._toggle_simulation_pause()
            return True

        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move during simulation."""
        if self.is_dragging and self.dragging_item:
            self._update_drag(scene_pos)
            return True

        return False

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release during simulation."""
        if self.is_dragging:
            self._end_dragging()
            return True

        return False

    def handle_wheel_event(self, event: QWheelEvent) -> bool:
        """Handle wheel events for simulation speed control."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + wheel to adjust simulation speed
            if event.angleDelta().y() > 0:
                self._increase_simulation_speed()
            else:
                self._decrease_simulation_speed()
            return True

        # Allow normal zooming with wheel (delegate to pan/zoom behavior)
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key presses for simulation controls."""
        key = event.key()

        # Space to pause/resume simulation
        if key == Qt.Key.Key_Space:
            self._toggle_simulation_pause()
            return True

        # Escape to stop simulation and exit mode
        elif key == Qt.Key.Key_Escape:
            self._stop_simulation()
            return True

        # R to restart simulation
        elif key == Qt.Key.Key_R:
            self._restart_simulation()
            return True

        # Arrow keys for manual stepping when paused
        elif self.simulation_paused:
            if key == Qt.Key.Key_Right:
                self._step_simulation_forward()
                return True
            elif key == Qt.Key.Key_Left:
                self._step_simulation_backward()
                return True

        # Number keys for speed presets
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            speed = (key - Qt.Key.Key_1 + 1) * 0.5  # 0.5x to 4.5x speed
            self._set_simulation_speed(speed)
            return True

        return False

    def _find_draggable_item(self, scene_pos: QPointF) -> QGraphicsItem | None:
        """Find an item that can be dragged during simulation."""
        if not self.view_ref or not self.view_ref.scene():
            return None

        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        # Check if item is draggable during simulation
        # This would depend on your specific item types and simulation constraints
        if item and hasattr(item, "is_simulation_draggable"):
            return item if item.is_simulation_draggable() else None

        return item  # For now, allow dragging any item

    def _start_dragging(self, item: QGraphicsItem, scene_pos: QPointF) -> None:
        """Start dragging an item during simulation."""
        self.is_dragging = True
        self.dragging_item = item
        self.drag_start_pos = scene_pos

        # Highlight the dragged item
        if hasattr(item, "setHighlighted"):
            item.setHighlighted(True)

        logger.debug(f"Started dragging item during simulation: {item}")

    def _update_drag(self, scene_pos: QPointF) -> None:
        """Update dragging position during simulation."""
        if not self.dragging_item or not self.drag_start_pos:
            return

        # Calculate drag delta
        delta = scene_pos - self.drag_start_pos

        # Update item position (this would integrate with your simulation system)
        if hasattr(self.dragging_item, "setPos"):
            current_pos = self.dragging_item.pos()
            self.dragging_item.setPos(current_pos + delta)

        self.drag_start_pos = scene_pos

    def _end_dragging(self) -> None:
        """End dragging during simulation."""
        if self.dragging_item:
            # Remove highlight
            if hasattr(self.dragging_item, "setHighlighted"):
                self.dragging_item.setHighlighted(False)

            logger.debug(f"Ended dragging item: {self.dragging_item}")

        self.is_dragging = False
        self.dragging_item = None
        self.drag_start_pos = None

    def _toggle_simulation_pause(self) -> None:
        """Toggle simulation pause state."""
        if self.is_simulation_running:
            self.simulation_paused = not self.simulation_paused

            if self.simulation_paused:
                logger.info("Simulation paused")
                if self.simulation_timer:
                    self.simulation_timer.stop()
            else:
                logger.info("Simulation resumed")
                if self.simulation_timer:
                    self.simulation_timer.start()

    def _stop_simulation(self) -> None:
        """Stop simulation and exit mode."""
        self.is_simulation_running = False
        self.simulation_paused = False

        if self.simulation_timer:
            self.simulation_timer.stop()
            self.simulation_timer = None

        logger.info("Simulation stopped")

        # Return to pan/zoom mode
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def _restart_simulation(self) -> None:
        """Restart the simulation from the beginning."""
        logger.info("Simulation restarted")

        # TODO: Reset simulation state
        # This would involve resetting mechanism positions, clearing trajectories, etc.

        self.simulation_paused = False
        if self.simulation_timer:
            self.simulation_timer.start()

    def _step_simulation_forward(self) -> None:
        """Step simulation forward by one frame (when paused)."""
        if self.simulation_paused:
            logger.debug("Stepping simulation forward")
            # TODO: Advance simulation by one frame

    def _step_simulation_backward(self) -> None:
        """Step simulation backward by one frame (when paused)."""
        if self.simulation_paused:
            logger.debug("Stepping simulation backward")
            # TODO: Move simulation back by one frame

    def _increase_simulation_speed(self) -> None:
        """Increase simulation speed."""
        self.simulation_speed = min(self.simulation_speed * 1.2, 5.0)
        self._update_simulation_timer()
        logger.info(f"Simulation speed increased to {self.simulation_speed:.1f}x")

    def _decrease_simulation_speed(self) -> None:
        """Decrease simulation speed."""
        self.simulation_speed = max(self.simulation_speed / 1.2, 0.1)
        self._update_simulation_timer()
        logger.info(f"Simulation speed decreased to {self.simulation_speed:.1f}x")

    def _set_simulation_speed(self, speed: float) -> None:
        """Set simulation speed to a specific value."""
        self.simulation_speed = max(0.1, min(speed, 5.0))
        self._update_simulation_timer()
        logger.info(f"Simulation speed set to {self.simulation_speed:.1f}x")

    def _update_simulation_timer(self) -> None:
        """Update simulation timer interval based on current speed."""
        if self.simulation_timer:
            interval = int(1000 / (self.frame_rate * self.simulation_speed))
            self.simulation_timer.setInterval(interval)

    def _start_simulation_timer(self) -> None:
        """Start the simulation timer."""
        if not self.simulation_timer:
            self.simulation_timer = QTimer()
            # TODO: Connect to simulation update method
            # self.simulation_timer.timeout.connect(self._update_simulation)

        interval = int(1000 / (self.frame_rate * self.simulation_speed))
        self.simulation_timer.setInterval(interval)
        self.simulation_timer.start()

    def get_cursor(self):
        """Return cursor for simulation mode."""
        if self.is_dragging:
            return Qt.CursorShape.ClosedHandCursor
        return Qt.CursorShape.ArrowCursor

    def enter_mode(self) -> None:
        """Setup when entering simulation mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())

        self.is_simulation_running = True
        self.simulation_paused = False
        self._start_simulation_timer()

        logger.info("Entered simulation mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting simulation mode."""
        # Stop simulation
        self.is_simulation_running = False
        self.simulation_paused = False

        if self.simulation_timer:
            self.simulation_timer.stop()
            self.simulation_timer = None

        # End any ongoing drag
        if self.is_dragging:
            self._end_dragging()

        logger.info("Exited simulation mode")
