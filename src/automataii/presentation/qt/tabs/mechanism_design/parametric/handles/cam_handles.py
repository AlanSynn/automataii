"""
CAM Follower Mechanism Handles

This module implements specialized handles for CAM follower mechanisms with gravity physics constraints:
- CAM must be below (due to gravity)
- Follower rod extends upward from CAM
- Egg-shaped CAM profile for proper motion
- Real-time drag-to-edit capabilities

Author: Automataii Enhanced CAM System
"""

import logging
import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QGraphicsItem

from .draggable_handle import DraggableHandle


class CamRodLengthHandle(DraggableHandle):
    """
    Handle for adjusting CAM follower rod length.

    Features:
    - Drag vertically to adjust rod length
    - Gravity constraint: follower always above cam
    - Real-time visual feedback
    - Minimum/maximum rod length validation
    """

    # Visual constants for rod handle
    COLOR_NORMAL = QColor(255, 165, 0)  # Orange for rod
    COLOR_HOVER = QColor(255, 200, 100)  # Light orange
    COLOR_DRAG = QColor(255, 220, 150)  # Very light orange

    def __init__(
        self,
        mechanism_id: str,
        initial_position: QPointF,
        cam_center: QPointF,
        base_radius: float,
        initial_rod_length: float,
        mechanism_data: dict[str, Any],
        update_callback: Callable[[str, str, float], None] | None = None,
        parent=None,
    ):
        """
        Initialize CAM rod length handle.

        Args:
            mechanism_id: Unique mechanism identifier
            initial_position: Handle starting position (follower location)
            cam_center: Center point of CAM (fixed)
            base_radius: CAM base radius
            initial_rod_length: Initial rod length
            mechanism_data: Reference to mechanism data
            update_callback: Function to call when rod length changes
            parent: Qt parent object
        """

        # Create wrapper callback for rod length parameter
        def rod_update_callback(handle_id: str, new_pos: QPointF):
            new_rod_length = self._calculate_rod_length_from_position(new_pos)
            if update_callback:
                update_callback(mechanism_id, "follower_rod_length", new_rod_length)

        super().__init__(
            handle_id=f"{mechanism_id}_cam_rod",
            initial_pos=initial_position,
            update_callback=rod_update_callback,
            parent=parent,
        )

        self.mechanism_id = mechanism_id
        self.cam_center = cam_center
        self.base_radius = base_radius
        self.current_rod_length = initial_rod_length
        self.mechanism_data = mechanism_data

        # Rod length constraints
        self.min_rod_length = 15.0  # Minimum rod length
        self.max_rod_length = 150.0  # Maximum rod length

        # Override colors for rod-specific appearance
        self._setup_rod_appearance()

        logging.info(
            f"Created CamRodLengthHandle for {mechanism_id} with initial length {initial_rod_length}"
        )

    def _setup_rod_appearance(self):
        """Setup rod-specific visual appearance."""
        self.COLOR_NORMAL = QColor(255, 165, 0)  # Orange
        self.COLOR_HOVER = QColor(255, 200, 100)
        self.COLOR_DRAG = QColor(255, 220, 150)

        # Update visual state
        self._update_visual_state()

        # Set rod-specific cursor
        self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))  # Vertical resize cursor

        logging.info("[CAM_ROD] Setup rod handle appearance")

    def _calculate_rod_length_from_position(self, handle_pos: QPointF) -> float:
        """
        Calculate rod length from handle position.

        With gravity physics, the follower is above the cam, so:
        rod_length = (cam_top_y - follower_y)

        Args:
            handle_pos: Current handle position (follower location)

        Returns:
            New rod length
        """
        # CAM top point (highest point of cam edge)
        cam_top_y = self.cam_center.y() - self.base_radius

        # Follower is above cam, so rod length is distance from cam top to follower
        follower_y = handle_pos.y()

        # Rod length is the vertical distance from cam top to follower
        rod_length = cam_top_y - follower_y  # Positive when follower is above cam

        return max(self.min_rod_length, min(self.max_rod_length, rod_length))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Override to allow free dragging without real-time physics constraints.
        Physics validation will be deferred to when exiting parametric editing mode.
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value  # Proposed new position

            # Allow free dragging without physics constraints for smoother UX
            # Just calculate the new rod length for display purposes
            new_rod_length = self._calculate_rod_length_from_position(new_pos)

            # Update rod length if changed
            if new_rod_length != self.current_rod_length:
                self.current_rod_length = new_rod_length
                logging.debug(f"[CAM_ROD] Rod length changed to {new_rod_length:.1f}")

            # Return the proposed position without constraints
            return super().itemChange(change, value)

        return super().itemChange(change, value)

    def _apply_gravity_constraints(self, proposed_pos: QPointF) -> QPointF:
        """
        Apply gravity physics constraints to handle position.

        Constraints:
        1. Follower must be above cam (gravity)
        2. Follower moves only vertically (rod constraint)
        3. Rod length within valid range

        Args:
            proposed_pos: Proposed new handle position

        Returns:
            Constrained valid position
        """
        # Keep X position fixed (rod moves only vertically)
        constrained_x = self.cam_center.x()

        # Calculate proposed rod length
        proposed_rod_length = self._calculate_rod_length_from_position(proposed_pos)

        # Clamp rod length to valid range
        clamped_rod_length = max(self.min_rod_length, min(self.max_rod_length, proposed_rod_length))

        # Calculate constrained Y position based on clamped rod length
        cam_top_y = self.cam_center.y() - self.base_radius
        constrained_y = cam_top_y - clamped_rod_length  # Follower above cam top

        return QPointF(constrained_x, constrained_y)


class CamSizeHandle(DraggableHandle):
    """
    Handle for adjusting CAM size (base radius and eccentricity).

    Features:
    - Drag to adjust cam size
    - Maintains egg shape proportions
    - Real-time cam profile update
    - Minimum/maximum size validation
    """

    # Visual constants for cam size handle
    COLOR_NORMAL = QColor(70, 130, 180)  # Steel blue for cam
    COLOR_HOVER = QColor(100, 149, 237)  # Cornflower blue
    COLOR_DRAG = QColor(135, 206, 250)  # Light sky blue

    def __init__(
        self,
        mechanism_id: str,
        initial_position: QPointF,
        cam_center: QPointF,
        initial_base_radius: float,
        initial_eccentricity: float,
        mechanism_data: dict[str, Any],
        update_callback: Callable[[str, str, float], None] | None = None,
        parent=None,
    ):
        """
        Initialize CAM size handle.

        Args:
            mechanism_id: Unique mechanism identifier
            initial_position: Handle starting position (on cam edge)
            cam_center: Center point of CAM
            initial_base_radius: Initial CAM base radius
            initial_eccentricity: Initial CAM eccentricity
            mechanism_data: Reference to mechanism data
            update_callback: Function to call when cam size changes
            parent: Qt parent object
        """

        # Create wrapper callback for cam size parameters
        def size_update_callback(handle_id: str, new_pos: QPointF):
            new_base_radius, new_eccentricity = self._calculate_cam_params_from_position(new_pos)
            if update_callback:
                update_callback(mechanism_id, "base_radius", new_base_radius)
                update_callback(mechanism_id, "eccentricity", new_eccentricity)

        super().__init__(
            handle_id=f"{mechanism_id}_cam_size",
            initial_pos=initial_position,
            update_callback=size_update_callback,
            parent=parent,
        )

        self.mechanism_id = mechanism_id
        self.cam_center = cam_center
        self.current_base_radius = initial_base_radius
        self.current_eccentricity = initial_eccentricity
        self.mechanism_data = mechanism_data

        # Size constraints
        self.min_base_radius = 10.0
        self.max_base_radius = 80.0
        self.min_eccentricity = 2.0
        self.max_eccentricity = 30.0

        # Override colors for cam-specific appearance
        self._setup_cam_appearance()

        logging.info(f"Created CamSizeHandle for {mechanism_id}")

    def _setup_cam_appearance(self):
        """Setup cam-specific visual appearance."""
        self.COLOR_NORMAL = QColor(70, 130, 180)  # Steel blue
        self.COLOR_HOVER = QColor(100, 149, 237)
        self.COLOR_DRAG = QColor(135, 206, 250)

        # Update visual state
        self._update_visual_state()

        # Set cam-specific cursor
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))  # Multi-directional resize

        logging.info("[CAM_SIZE] Setup cam size handle appearance")

    def _calculate_cam_params_from_position(self, handle_pos: QPointF) -> tuple[float, float]:
        """
        Calculate cam parameters from handle position.

        The handle position determines the cam size. Distance from center
        determines base radius, and offset determines eccentricity.

        Args:
            handle_pos: Current handle position

        Returns:
            Tuple of (base_radius, eccentricity)
        """
        # Distance from cam center to handle
        dx = handle_pos.x() - self.cam_center.x()
        dy = handle_pos.y() - self.cam_center.y()
        distance = math.sqrt(dx * dx + dy * dy)

        # Base radius is proportional to distance
        base_radius = max(self.min_base_radius, min(self.max_base_radius, distance * 0.8))

        # Eccentricity based on horizontal offset (egg asymmetry)
        eccentricity = max(self.min_eccentricity, min(self.max_eccentricity, abs(dx) * 0.6))

        return base_radius, eccentricity

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Override to enforce cam size constraints.
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value  # Proposed new position

            # Calculate new parameters
            new_base_radius, new_eccentricity = self._calculate_cam_params_from_position(new_pos)

            # Update internal state
            if (
                new_base_radius != self.current_base_radius
                or new_eccentricity != self.current_eccentricity
            ):
                self.current_base_radius = new_base_radius
                self.current_eccentricity = new_eccentricity
                logging.debug(
                    f"[CAM_SIZE] Size changed to radius={new_base_radius:.1f}, ecc={new_eccentricity:.1f}"
                )

            # Continue with standard processing
            return super().itemChange(change, value)

        return super().itemChange(change, value)


def create_cam_handles(
    mechanism_id: str,
    cam_center: QPointF,
    base_radius: float,
    eccentricity: float,
    rod_length: float,
    mechanism_data: dict[str, Any],
    update_callback: Callable[[str, str, float], None] | None = None,
) -> list[DraggableHandle]:
    """
    Create all CAM handles for parametric editing.

    Args:
        mechanism_id: Unique mechanism identifier
        cam_center: CAM center position
        base_radius: CAM base radius
        eccentricity: CAM eccentricity
        rod_length: Follower rod length
        mechanism_data: Reference to mechanism data
        update_callback: Function to call when parameters change

    Returns:
        List of created handles
    """
    handles = []

    # Calculate initial positions based on gravity physics
    # Follower is above cam by rod_length
    follower_y = cam_center.y() - base_radius - rod_length
    rod_handle_pos = QPointF(cam_center.x(), follower_y)

    # Cam size handle on the edge of the cam (right side)
    size_handle_pos = QPointF(cam_center.x() + base_radius + eccentricity, cam_center.y())

    # Create rod length handle
    rod_handle = CamRodLengthHandle(
        mechanism_id=mechanism_id,
        initial_position=rod_handle_pos,
        cam_center=cam_center,
        base_radius=base_radius,
        initial_rod_length=rod_length,
        mechanism_data=mechanism_data,
        update_callback=update_callback,
    )
    handles.append(rod_handle)

    # Create cam size handle
    size_handle = CamSizeHandle(
        mechanism_id=mechanism_id,
        initial_position=size_handle_pos,
        cam_center=cam_center,
        initial_base_radius=base_radius,
        initial_eccentricity=eccentricity,
        mechanism_data=mechanism_data,
        update_callback=update_callback,
    )
    handles.append(size_handle)

    logging.info(f"Created {len(handles)} CAM handles for {mechanism_id}")
    return handles
