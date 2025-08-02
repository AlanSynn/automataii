"""
Radius Handle for Gear Radius Manipulation

Specialized handle for manipulating gear radii in mechanism systems.
Allows direct manipulation of gear sizes while maintaining proper meshing constraints.

Author: AI Engineering Assistant
Architecture: Jeff Dean Performance + Kent Beck Simplicity + Rob Pike Clarity
"""

import logging
import math
from collections.abc import Callable

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen

from .base_handle import BaseHandle

logger = logging.getLogger(__name__)


class RadiusHandle(BaseHandle):
    """
    Handle for manipulating gear radius in mechanism systems.

    This handle appears as a circle on the gear perimeter and allows
    dragging to adjust the gear radius while maintaining proper meshing
    constraints with adjacent gears.

    Features:
    - Radial drag interaction for intuitive radius adjustment
    - Automatic gear meshing validation
    - Real-time gear ratio calculations
    - Visual feedback for valid/invalid configurations
    - Constraint enforcement for minimum/maximum radii
    """

    # Radius-specific appearance - BRIGHT BLUE for gear handles
    COLOR_RADIUS = QColor(0, 100, 255)  # BRIGHT BLUE
    COLOR_RADIUS_HOVER = QColor(100, 150, 255)  # Light blue
    COLOR_RADIUS_ACTIVE = QColor(150, 200, 255)  # Very light blue

    def __init__(
        self,
        mechanism_id: str,
        gear_name: str,  # 'gear_1', 'gear_2', etc.
        gear_center: QPointF,
        initial_radius: float,
        mechanism_data: dict,
        update_callback: Callable[[str, float], None],
        constraint_validator: Callable | None = None,
        parent=None,
    ):
        """
        Initialize radius handle for gear manipulation.

        Args:
            mechanism_id: Unique mechanism identifier
            gear_name: Name of gear ('gear_1', 'gear_2', etc.)
            gear_center: Center position of gear in scene coordinates
            initial_radius: Initial gear radius
            mechanism_data: Reference to mechanism layer data
            update_callback: Function to call when radius changes
            constraint_validator: Optional constraint validation function
            parent: Qt parent object
        """
        # Calculate initial handle position on gear perimeter
        handle_pos = QPointF(gear_center.x() + initial_radius, gear_center.y())

        super().__init__(
            mechanism_id, f"{gear_name}_radius", handle_pos, constraint_validator, None, parent
        )

        self.gear_name = gear_name
        self.gear_center = gear_center
        self.current_radius = initial_radius
        self.mechanism_data = mechanism_data
        self.update_callback = update_callback

        # Radius-specific constraints
        self.min_radius = 10.0  # Minimum gear radius
        self.max_radius = 200.0  # Maximum gear radius
        self.min_tooth_count = 12  # Minimum number of teeth for valid gear
        self.max_tooth_count = 200  # Maximum number of teeth

        # Setup radius-specific appearance
        self._setup_radius_appearance()

        logger.debug(
            f"Created RadiusHandle for {self.gear_name} at center {gear_center} with radius {initial_radius}"
        )

    def _setup_radius_appearance(self):
        """Setup radius-specific visual appearance."""
        # Override base colors with radius-specific colors
        self.COLOR_NORMAL = self.COLOR_RADIUS
        self.COLOR_HOVER = self.COLOR_RADIUS_HOVER
        self.COLOR_ACTIVE = self.COLOR_RADIUS_ACTIVE

        # Medium-sized handles for precise control
        self.HANDLE_RADIUS = 12.0
        self.HOVER_RADIUS = 16.0
        self.ACTIVE_RADIUS = 20.0

        # Update appearance
        self._update_visual_state()

        # FORCE visibility and interaction
        self.setVisible(True)
        self.setOpacity(1.0)
        self.show()

        logger.info(f"[RADIUS] Created BRIGHT BLUE radius handle: {self.gear_name}")

    def paint(self, painter: QPainter, option, widget):
        """
        Custom paint method to draw radius handle with radial indicator.
        """
        # Call parent paint for basic handle
        super().paint(painter, option, widget)

        # Draw radial line from center to handle
        painter.setPen(QPen(self.COLOR_NORMAL, 2.0))
        painter.drawLine(
            self.mapFromScene(self.gear_center),
            QPointF(0, 0),  # Handle center in local coordinates
        )

        # Draw small circle at gear center for reference
        center_local = self.mapFromScene(self.gear_center)
        painter.setBrush(QBrush(self.COLOR_NORMAL))
        painter.drawEllipse(center_local, 3, 3)

    def _calculate_parameter_from_position(self, scene_pos: QPointF) -> float:
        """
        Calculate radius from handle position.

        Args:
            scene_pos: Current handle position in scene coordinates

        Returns:
            New radius value
        """
        # Calculate distance from gear center to handle position
        dx = scene_pos.x() - self.gear_center.x()
        dy = scene_pos.y() - self.gear_center.y()
        radius = math.sqrt(dx * dx + dy * dy)

        # Clamp to valid range
        radius = max(self.min_radius, min(self.max_radius, radius))

        return radius

    def _apply_parameter_change(self, new_radius: float):
        """
        Apply radius change to gear mechanism.

        Args:
            new_radius: New gear radius
        """
        try:
            # Update radius in mechanism data
            params = self.mechanism_data.get("params", {})
            if not params:
                params = {}
                self.mechanism_data["params"] = params

            # Update the gear radius parameter
            radius_param = f"{self.gear_name}_radius"
            params[radius_param] = new_radius

            # Update current radius
            self.current_radius = new_radius

            # Update handle position to stay on gear perimeter
            new_handle_pos = QPointF(self.gear_center.x() + new_radius, self.gear_center.y())
            self.setPos(new_handle_pos)

            # Trigger mechanism recalculation via callback
            self.update_callback(self.gear_name, new_radius)

            logger.debug(f"Updated {self.gear_name} radius to {new_radius}")

        except Exception as e:
            logger.error(f"Failed to apply radius change: {e}")

    def get_current_parameter_value(self) -> float:
        """
        Get current gear radius from mechanism data.

        Returns:
            Current gear radius
        """
        try:
            params = self.mechanism_data.get("params", {})
            radius_param = f"{self.gear_name}_radius"

            if radius_param in params:
                return params[radius_param]
            else:
                return self.current_radius

        except Exception as e:
            logger.warning(f"Could not get current radius: {e}")
            return self.current_radius

    def _validate_radius_constraints(self, new_radius: float) -> tuple[bool, str]:
        """
        Validate radius against gear constraints.

        Args:
            new_radius: Proposed new radius

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check basic radius limits
            if new_radius < self.min_radius:
                return False, f"Radius too small: {new_radius:.1f} < {self.min_radius}"

            if new_radius > self.max_radius:
                return False, f"Radius too large: {new_radius:.1f} > {self.max_radius}"

            # Check tooth count constraints (assuming module = 1.0)
            module = 1.0  # Standard gear module
            tooth_count = int(2 * new_radius / module)

            if tooth_count < self.min_tooth_count:
                return False, f"Too few teeth: {tooth_count} < {self.min_tooth_count}"

            if tooth_count > self.max_tooth_count:
                return False, f"Too many teeth: {tooth_count} > {self.max_tooth_count}"

            # Validate gear meshing constraints
            return self._validate_gear_meshing(new_radius)

        except Exception as e:
            logger.warning(f"Radius constraint validation failed: {e}")
            return True, ""  # Allow movement if validation fails

    def _validate_gear_meshing(self, new_radius: float) -> tuple[bool, str]:
        """
        Validate gear meshing constraints with other gears.

        Args:
            new_radius: Proposed new radius

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            params = self.mechanism_data.get("params", {})

            # Find other gears in the mechanism
            other_gears = []
            for key, value in params.items():
                if key.endswith("_radius") and key != f"{self.gear_name}_radius":
                    gear_name = key.replace("_radius", "")
                    other_gears.append((gear_name, value))

            # Check meshing constraints with each other gear
            for other_gear_name, other_radius in other_gears:
                # Get gear centers from key_points
                key_points = self.mechanism_data.get("key_points", {})

                if f"{other_gear_name}_center" in key_points:
                    other_center_data = key_points[f"{other_gear_name}_center"]
                    other_center = QPointF(other_center_data[0], other_center_data[1])

                    # Calculate center distance
                    dx = other_center.x() - self.gear_center.x()
                    dy = other_center.y() - self.gear_center.y()
                    center_distance = math.sqrt(dx * dx + dy * dy)

                    # Check if gears can mesh (external meshing)
                    expected_distance = new_radius + other_radius
                    tolerance = 5.0  # Allow some tolerance

                    if abs(center_distance - expected_distance) > tolerance:
                        return False, f"Gear meshing constraint violated with {other_gear_name}"

            return True, ""

        except Exception as e:
            logger.warning(f"Gear meshing validation failed: {e}")
            return True, ""

    def mouseMoveEvent(self, event):
        """
        Override mouse move to include radius-specific constraint validation.
        """
        if not self._is_dragging or not self._is_enabled:
            return

        new_position = event.scenePos()
        new_radius = self._calculate_parameter_from_position(new_position)

        # Validate radius-specific constraints
        is_valid, error_msg = self._validate_radius_constraints(new_radius)

        if not is_valid:
            # Show constraint violation feedback
            self._show_constraint_feedback()
            logger.debug(f"Radius constraint violation: {error_msg}")
            return  # Don't move if constraints violated

        # Constrain handle to move along circle (radial only)
        angle = math.atan2(
            new_position.y() - self.gear_center.y(), new_position.x() - self.gear_center.x()
        )

        constrained_pos = QPointF(
            self.gear_center.x() + new_radius * math.cos(angle),
            self.gear_center.y() + new_radius * math.sin(angle),
        )

        # Update position immediately for visual feedback
        self.setPos(constrained_pos)

        # Apply parameter change
        self._apply_parameter_change(new_radius)

        # Call parent implementation for standard handling
        super().mouseMoveEvent(event)

    def get_gear_name(self) -> str:
        """Get the gear name."""
        return self.gear_name

    def get_gear_center(self) -> QPointF:
        """Get the gear center position."""
        return self.gear_center

    def get_current_radius(self) -> float:
        """Get the current gear radius."""
        return self.current_radius

    def set_gear_center(self, new_center: QPointF):
        """
        Update gear center position (called when gear position changes).

        Args:
            new_center: New center position
        """
        self.gear_center = new_center

        # Update handle position to maintain radius
        new_handle_pos = QPointF(new_center.x() + self.current_radius, new_center.y())
        self.setPos(new_handle_pos)

        logger.debug(f"Updated {self.gear_name} center to {new_center}")

    def get_gear_ratio(self, other_gear_name: str) -> float:
        """
        Calculate gear ratio with another gear.

        Args:
            other_gear_name: Name of other gear

        Returns:
            Gear ratio (this_radius / other_radius), or -1 if not found
        """
        try:
            params = self.mechanism_data.get("params", {})
            other_radius_param = f"{other_gear_name}_radius"

            if other_radius_param in params:
                other_radius = params[other_radius_param]
                if other_radius > 0:
                    return self.current_radius / other_radius

            return -1

        except Exception as e:
            logger.warning(f"Could not calculate gear ratio: {e}")
            return -1

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"RadiusHandle({self.mechanism_id}:{self.gear_name} "
            f"center={self.gear_center.x():.1f},{self.gear_center.y():.1f} "
            f"radius={self.current_radius:.1f})"
        )
