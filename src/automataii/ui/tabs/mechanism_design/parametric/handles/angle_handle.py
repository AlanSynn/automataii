"""
Angle Handle for Angular Parameter Manipulation

Specialized handle for manipulating angular parameters in mechanism systems.
Allows direct manipulation of angles like initial positions, orientation, and rotation.

Author: AI Engineering Assistant
Architecture: Jeff Dean Performance + Kent Beck Simplicity + Rob Pike Clarity
"""

import logging
import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen

from .base_handle import BaseHandle

logger = logging.getLogger(__name__)


class AngleHandle(BaseHandle):
    """
    Handle for manipulating angular parameters in mechanism systems.

    This handle appears as a small circle at a fixed distance from a pivot point
    and allows dragging to adjust angles. The handle moves along a circular arc
    centered at the pivot point.

    Features:
    - Circular arc drag interaction for intuitive angle adjustment
    - Automatic angle constraint validation
    - Visual feedback with arc indicators
    - Support for full 360° range or constrained ranges
    - Real-time angle calculations and updates
    """

    # Angle-specific appearance - BRIGHT GREEN for angle handles
    COLOR_ANGLE = QColor(0, 200, 0)  # BRIGHT GREEN
    COLOR_ANGLE_HOVER = QColor(100, 255, 100)  # Light green
    COLOR_ANGLE_ACTIVE = QColor(150, 255, 150)  # Very light green

    def __init__(
        self,
        mechanism_id: str,
        angle_name: str,  # 'initial_angle', 'orientation', etc.
        pivot_point: QPointF,
        initial_angle: float,  # In radians
        radius: float,  # Distance from pivot to handle
        mechanism_data: dict,
        update_callback: Callable[[str, float], None],
        constraint_validator: Callable | None = None,
        angle_range: tuple[float, float] | None = None,  # (min_angle, max_angle) in radians
        parent=None,
    ):
        """
        Initialize angle handle for angular parameter manipulation.

        Args:
            mechanism_id: Unique mechanism identifier
            angle_name: Name of angle parameter
            pivot_point: Center point for angle rotation
            initial_angle: Initial angle in radians
            radius: Distance from pivot to handle
            mechanism_data: Reference to mechanism layer data
            update_callback: Function to call when angle changes
            constraint_validator: Optional constraint validation function
            angle_range: Optional (min_angle, max_angle) constraint in radians
            parent: Qt parent object
        """
        # Calculate initial handle position based on angle
        handle_pos = QPointF(
            pivot_point.x() + radius * math.cos(initial_angle),
            pivot_point.y() + radius * math.sin(initial_angle),
        )

        super().__init__(mechanism_id, angle_name, handle_pos, constraint_validator, None, parent)

        self.angle_name = angle_name
        self.pivot_point = pivot_point
        self.radius = radius
        self.current_angle = initial_angle
        self.mechanism_data = mechanism_data
        self.update_callback = update_callback

        # Angle constraints
        self.angle_range = angle_range  # (min_angle, max_angle) or None for full range
        self.angle_tolerance = 0.01  # Small tolerance for angle comparisons

        # Visual properties
        self.show_arc = True  # Whether to show the circular arc
        self.arc_span = math.pi / 3  # Span of arc to show (60 degrees)

        # Setup angle-specific appearance
        self._setup_angle_appearance()

        logger.debug(
            f"Created AngleHandle for {self.angle_name} at pivot {pivot_point} with angle {math.degrees(initial_angle):.1f}°"
        )

    def _setup_angle_appearance(self):
        """Setup angle-specific visual appearance."""
        # Override base colors with angle-specific colors
        self.COLOR_NORMAL = self.COLOR_ANGLE
        self.COLOR_HOVER = self.COLOR_ANGLE_HOVER
        self.COLOR_ACTIVE = self.COLOR_ANGLE_ACTIVE

        # Small handles for precise angle control
        self.HANDLE_RADIUS = 10.0
        self.HOVER_RADIUS = 14.0
        self.ACTIVE_RADIUS = 18.0

        # Update appearance
        self._update_visual_state()

        # FORCE visibility and interaction
        self.setVisible(True)
        self.setOpacity(1.0)
        self.show()

        logger.info(f"[ANGLE] Created BRIGHT GREEN angle handle: {self.angle_name}")

    def paint(self, painter: QPainter, option, widget):
        """
        Custom paint method to draw angle handle with arc indicator.
        """
        # Call parent paint for basic handle
        super().paint(painter, option, widget)

        if self.show_arc:
            # Draw arc indicator
            painter.setPen(QPen(self.COLOR_NORMAL, 1.5, Qt.PenStyle.DashLine))

            # Draw partial arc around pivot point
            pivot_local = self.mapFromScene(self.pivot_point)
            arc_start_angle = self.current_angle - self.arc_span / 2
            arc_end_angle = self.current_angle + self.arc_span / 2

            # Draw arc using multiple line segments
            num_segments = 20
            for i in range(num_segments):
                t1 = i / num_segments
                t2 = (i + 1) / num_segments

                angle1 = arc_start_angle + t1 * self.arc_span
                angle2 = arc_start_angle + t2 * self.arc_span

                p1 = QPointF(
                    pivot_local.x() + self.radius * math.cos(angle1),
                    pivot_local.y() + self.radius * math.sin(angle1),
                )
                p2 = QPointF(
                    pivot_local.x() + self.radius * math.cos(angle2),
                    pivot_local.y() + self.radius * math.sin(angle2),
                )

                painter.drawLine(p1, p2)

        # Draw line from pivot to handle
        painter.setPen(QPen(self.COLOR_NORMAL, 2.0))
        painter.drawLine(
            self.mapFromScene(self.pivot_point),
            QPointF(0, 0),  # Handle center in local coordinates
        )

        # Draw small circle at pivot point for reference
        pivot_local = self.mapFromScene(self.pivot_point)
        painter.setBrush(QBrush(self.COLOR_NORMAL))
        painter.drawEllipse(pivot_local, 2, 2)

    def _calculate_parameter_from_position(self, scene_pos: QPointF) -> float:
        """
        Calculate angle from handle position.

        Args:
            scene_pos: Current handle position in scene coordinates

        Returns:
            New angle value in radians
        """
        # Calculate angle from pivot to handle position
        dx = scene_pos.x() - self.pivot_point.x()
        dy = scene_pos.y() - self.pivot_point.y()
        angle = math.atan2(dy, dx)

        # Normalize angle to [0, 2π) range
        angle = angle % (2 * math.pi)

        # Apply angle constraints if specified
        if self.angle_range:
            min_angle, max_angle = self.angle_range

            # Normalize constraint range
            min_angle = min_angle % (2 * math.pi)
            max_angle = max_angle % (2 * math.pi)

            # Clamp angle to valid range
            if min_angle <= max_angle:
                # Normal case: range doesn't cross 0
                angle = max(min_angle, min(max_angle, angle))
            else:
                # Range crosses 0 (e.g., -π/4 to π/4)
                if angle <= max_angle or angle >= min_angle:
                    # Angle is in valid range
                    pass
                else:
                    # Clamp to nearest boundary
                    dist_to_min = min(
                        abs(angle - min_angle), abs(angle - (min_angle - 2 * math.pi))
                    )
                    dist_to_max = min(
                        abs(angle - max_angle), abs(angle - (max_angle + 2 * math.pi))
                    )

                    if dist_to_min < dist_to_max:
                        angle = min_angle
                    else:
                        angle = max_angle

        return angle

    def _apply_parameter_change(self, new_angle: float):
        """
        Apply angle change to mechanism.

        Args:
            new_angle: New angle in radians
        """
        try:
            # Update angle in mechanism data
            params = self.mechanism_data.get("params", {})
            if not params:
                params = {}
                self.mechanism_data["params"] = params

            # Update the angle parameter
            params[self.angle_name] = new_angle

            # Update current angle
            self.current_angle = new_angle

            # Update handle position to stay on circle
            new_handle_pos = QPointF(
                self.pivot_point.x() + self.radius * math.cos(new_angle),
                self.pivot_point.y() + self.radius * math.sin(new_angle),
            )
            self.setPos(new_handle_pos)

            # Trigger mechanism recalculation via callback
            self.update_callback(self.angle_name, new_angle)

            logger.debug(f"Updated {self.angle_name} to {math.degrees(new_angle):.1f}°")

        except Exception as e:
            logger.error(f"Failed to apply angle change: {e}")

    def get_current_parameter_value(self) -> float:
        """
        Get current angle from mechanism data.

        Returns:
            Current angle in radians
        """
        try:
            params = self.mechanism_data.get("params", {})

            if self.angle_name in params:
                return params[self.angle_name]
            else:
                return self.current_angle

        except Exception as e:
            logger.warning(f"Could not get current angle: {e}")
            return self.current_angle

    def _validate_angle_constraints(self, new_angle: float) -> tuple[bool, str]:
        """
        Validate angle against constraints.

        Args:
            new_angle: Proposed new angle in radians

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check angle range constraints
            if self.angle_range:
                min_angle, max_angle = self.angle_range

                # Normalize angles
                new_angle_norm = new_angle % (2 * math.pi)
                min_angle_norm = min_angle % (2 * math.pi)
                max_angle_norm = max_angle % (2 * math.pi)

                if min_angle_norm <= max_angle_norm:
                    # Normal case: range doesn't cross 0
                    if not (min_angle_norm <= new_angle_norm <= max_angle_norm):
                        return (
                            False,
                            f"Angle {math.degrees(new_angle):.1f}° outside range [{math.degrees(min_angle):.1f}°, {math.degrees(max_angle):.1f}°]",
                        )
                else:
                    # Range crosses 0
                    if not (new_angle_norm <= max_angle_norm or new_angle_norm >= min_angle_norm):
                        return (
                            False,
                            f"Angle {math.degrees(new_angle):.1f}° outside range [{math.degrees(min_angle):.1f}°, {math.degrees(max_angle):.1f}°]",
                        )

            # Additional mechanism-specific angle validation can be added here
            return self._validate_mechanism_angle(new_angle)

        except Exception as e:
            logger.warning(f"Angle constraint validation failed: {e}")
            return True, ""  # Allow movement if validation fails

    def _validate_mechanism_angle(self, new_angle: float) -> tuple[bool, str]:
        """
        Validate angle against mechanism-specific constraints.

        Args:
            new_angle: Proposed new angle in radians

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # This can be extended with mechanism-specific validation
            # For example, checking if the angle causes link intersections
            # or violates mechanical constraints

            return True, ""

        except Exception as e:
            logger.warning(f"Mechanism angle validation failed: {e}")
            return True, ""

    def mouseMoveEvent(self, event):
        """
        Override mouse move to include angle-specific constraint validation.
        """
        if not self._is_dragging or not self._is_enabled:
            return

        new_position = event.scenePos()
        new_angle = self._calculate_parameter_from_position(new_position)

        # Validate angle-specific constraints
        is_valid, error_msg = self._validate_angle_constraints(new_angle)

        if not is_valid:
            # Show constraint violation feedback
            self._show_constraint_feedback()
            logger.debug(f"Angle constraint violation: {error_msg}")
            return  # Don't move if constraints violated

        # Constrain handle to move along circle (angular only)
        constrained_pos = QPointF(
            self.pivot_point.x() + self.radius * math.cos(new_angle),
            self.pivot_point.y() + self.radius * math.sin(new_angle),
        )

        # Update position immediately for visual feedback
        self.setPos(constrained_pos)

        # Apply parameter change
        self._apply_parameter_change(new_angle)

        # Call parent implementation for standard handling
        super().mouseMoveEvent(event)

    def get_angle_name(self) -> str:
        """Get the angle parameter name."""
        return self.angle_name

    def get_pivot_point(self) -> QPointF:
        """Get the pivot point position."""
        return self.pivot_point

    def get_current_angle(self) -> float:
        """Get the current angle in radians."""
        return self.current_angle

    def get_current_angle_degrees(self) -> float:
        """Get the current angle in degrees."""
        return math.degrees(self.current_angle)

    def set_pivot_point(self, new_pivot: QPointF):
        """
        Update pivot point position (called when mechanism moves).

        Args:
            new_pivot: New pivot position
        """
        self.pivot_point = new_pivot

        # Update handle position to maintain angle and radius
        new_handle_pos = QPointF(
            new_pivot.x() + self.radius * math.cos(self.current_angle),
            new_pivot.y() + self.radius * math.sin(self.current_angle),
        )
        self.setPos(new_handle_pos)

        logger.debug(f"Updated {self.angle_name} pivot to {new_pivot}")

    def set_angle_range(self, min_angle: float, max_angle: float):
        """
        Set angle constraint range.

        Args:
            min_angle: Minimum angle in radians
            max_angle: Maximum angle in radians
        """
        self.angle_range = (min_angle, max_angle)

        # Validate current angle against new range
        if not self._validate_angle_constraints(self.current_angle)[0]:
            # Current angle is outside new range, clamp it
            new_angle = self._calculate_parameter_from_position(self.pos())
            self._apply_parameter_change(new_angle)

        logger.debug(
            f"Set angle range for {self.angle_name}: [{math.degrees(min_angle):.1f}°, {math.degrees(max_angle):.1f}°]"
        )

    def set_show_arc(self, show: bool):
        """
        Set whether to show the circular arc indicator.

        Args:
            show: True to show arc, False to hide
        """
        self.show_arc = show
        self.update()  # Trigger repaint

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AngleHandle({self.mechanism_id}:{self.angle_name} "
            f"pivot={self.pivot_point.x():.1f},{self.pivot_point.y():.1f} "
            f"angle={math.degrees(self.current_angle):.1f}° "
            f"radius={self.radius:.1f})"
        )
