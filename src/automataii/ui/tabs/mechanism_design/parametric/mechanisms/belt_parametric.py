"""
Parametric editor for belt/pulley mechanisms.

Provides interactive editing of pulley positions, radii, and belt parameters
for belt-pulley systems.
"""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from ..base.parametric_interface import ParametricHandleFactory, ParametricMechanismInterface
from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class BeltParametricEditor(ParametricMechanismInterface):
    """
    Parametric editor for belt/pulley mechanisms.

    Provides interactive editing capabilities for:
    - Pulley center positions
    - Pulley radii
    - Belt tension parameters
    - Angular velocity settings
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        super().__init__(mechanism_id, layer_data, scene_manager)

        # Belt-specific constraints
        self.min_pulley_radius = 5.0  # Minimum pulley radius
        self.max_pulley_radius = 150.0  # Maximum pulley radius
        self.min_pulley_distance = 50.0  # Minimum distance between pulleys
        self.max_pulley_distance = 800.0  # Maximum distance between pulleys
        self.min_belt_tension = 1.0  # Minimum belt tension
        self.max_belt_tension = 1000.0  # Maximum belt tension

        # Store original parameters for validation
        self.original_params = layer_data.get("params", {}).copy()

    def create_handles(self) -> list[BaseHandle]:
        """
        Create handles for belt/pulley mechanism parameters.

        Returns:
            List of handles for pulley centers and radii
        """
        handles = []
        key_points = self.layer_data.get("key_points", {})

        if not key_points:
            logger.warning(f"No key_points found for belt {self.mechanism_id}")
            return handles

        # Get scene transform function
        transform = self.scene_manager.visuals.visual_factory.get_scene_transform_function(
            self.layer_data
        )

        # Create handles for pulley centers
        pulley_centers = ["pulley_1_center", "pulley_2_center"]

        for center_name in pulley_centers:
            center_data = key_points.get(center_name)
            if center_data:
                scene_pos = transform(center_data)
                handle = ParametricHandleFactory.create_anchor_handle(
                    mechanism_id=self.mechanism_id,
                    anchor_name=center_name,
                    position=scene_pos,
                    mechanism_data=self.layer_data,
                    callback=self._on_anchor_moved,
                )
                if handle:
                    handles.append(handle)
                    logger.debug(f"Created pulley center handle for {center_name} at {scene_pos}")

        # Create handles for pulley radii
        params = self.layer_data.get("params", {})

        # Pulley 1 radius handle
        pulley1_center_data = key_points.get("pulley_1_center", [0, 0])
        pulley1_radius = params.get("pulley_1_radius", 40.0)

        if pulley1_center_data:
            scene_center = transform(pulley1_center_data)
            radius_pos = QPointF(scene_center.x() + pulley1_radius, scene_center.y())

            handle = ParametricHandleFactory.create_radius_handle(
                mechanism_id=self.mechanism_id,
                parameter_name="pulley_1_radius",
                center_position=scene_center,
                radius_position=radius_pos,
                mechanism_data=self.layer_data,
                callback=self._on_radius_changed,
            )
            if handle:
                handles.append(handle)
                logger.debug(f"Created pulley 1 radius handle at {radius_pos}")

        # Pulley 2 radius handle
        pulley2_center_data = key_points.get("pulley_2_center", [100, 0])
        pulley2_radius = params.get("pulley_2_radius", 25.0)

        if pulley2_center_data:
            scene_center = transform(pulley2_center_data)
            radius_pos = QPointF(scene_center.x() + pulley2_radius, scene_center.y())

            handle = ParametricHandleFactory.create_radius_handle(
                mechanism_id=self.mechanism_id,
                parameter_name="pulley_2_radius",
                center_position=scene_center,
                radius_position=radius_pos,
                mechanism_data=self.layer_data,
                callback=self._on_radius_changed,
            )
            if handle:
                handles.append(handle)
                logger.debug(f"Created pulley 2 radius handle at {radius_pos}")

        return handles

    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update belt/pulley mechanism parameters based on handle changes.

        Args:
            changed_handles: Dictionary mapping handle names to new positions

        Returns:
            Updated mechanism parameters
        """
        updated_params = self.layer_data.get("params", {}).copy()
        key_points = self.layer_data.get("key_points", {}).copy()

        # Handle pulley center changes
        for center_name in ["pulley_1_center", "pulley_2_center"]:
            if center_name in changed_handles:
                new_pos = changed_handles[center_name]
                if isinstance(new_pos, QPointF):
                    key_points[center_name] = [new_pos.x(), new_pos.y()]
                    logger.debug(f"Updated {center_name} to {new_pos}")

        # Handle pulley radius changes
        for radius_name in ["pulley_1_radius", "pulley_2_radius"]:
            if radius_name in changed_handles:
                new_radius = changed_handles[radius_name]
                if isinstance(new_radius, (int, float)):
                    updated_params[radius_name] = max(
                        self.min_pulley_radius, min(self.max_pulley_radius, new_radius)
                    )
                    logger.debug(f"Updated {radius_name} to {updated_params[radius_name]}")

        # Update layer data
        self.layer_data["params"] = updated_params
        self.layer_data["key_points"] = key_points

        return updated_params

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate belt/pulley mechanism parameters.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check pulley radii
        pulley1_radius = params.get("pulley_1_radius", 0)
        pulley2_radius = params.get("pulley_2_radius", 0)

        if pulley1_radius < self.min_pulley_radius or pulley1_radius > self.max_pulley_radius:
            return (
                False,
                f"Pulley 1 radius must be between {self.min_pulley_radius} and {self.max_pulley_radius}",
            )

        if pulley2_radius < self.min_pulley_radius or pulley2_radius > self.max_pulley_radius:
            return (
                False,
                f"Pulley 2 radius must be between {self.min_pulley_radius} and {self.max_pulley_radius}",
            )

        # Check pulley positions
        key_points = self.layer_data.get("key_points", {})
        pulley1_center = key_points.get("pulley_1_center", [0, 0])
        pulley2_center = key_points.get("pulley_2_center", [100, 0])

        distance = math.sqrt(
            (pulley1_center[0] - pulley2_center[0]) ** 2
            + (pulley1_center[1] - pulley2_center[1]) ** 2
        )

        min_distance = pulley1_radius + pulley2_radius
        if distance < min_distance:
            return False, f"Pulleys are too close together. Minimum distance: {min_distance:.1f}"

        if distance > self.max_pulley_distance:
            return False, f"Pulleys are too far apart. Maximum distance: {self.max_pulley_distance}"

        # Check belt tension
        belt_tension = params.get("belt_tension", 10.0)
        if belt_tension < self.min_belt_tension or belt_tension > self.max_belt_tension:
            return (
                False,
                f"Belt tension must be between {self.min_belt_tension} and {self.max_belt_tension}",
            )

        # Check slip coefficient
        slip_coeff = params.get("slip_coefficient", 0.0)
        if slip_coeff < 0.0 or slip_coeff > 1.0:
            return False, "Slip coefficient must be between 0.0 and 1.0"

        return True, ""

    def get_parameter_constraints(self) -> dict[str, tuple[float, float]]:
        """
        Get parameter constraints for the belt/pulley mechanism.

        Returns:
            Dictionary mapping parameter names to (min, max) tuples
        """
        return {
            "pulley_1_radius": (self.min_pulley_radius, self.max_pulley_radius),
            "pulley_2_radius": (self.min_pulley_radius, self.max_pulley_radius),
            "belt_tension": (self.min_belt_tension, self.max_belt_tension),
            "angular_velocity_1": (0.1, 20.0),
            "slip_coefficient": (0.0, 1.0),
            "belt_width": (1.0, 50.0),
            "belt_thickness": (0.5, 10.0),
        }

    def _on_anchor_moved(self, anchor_name: str, new_position: QPointF):
        """Handle anchor point movement."""
        logger.debug(f"Belt anchor {anchor_name} moved to {new_position}")
        # This will be handled by the parameter controller
        pass

    def _on_radius_changed(self, parameter_name: str, new_radius: float):
        """Handle radius parameter changes."""
        logger.debug(f"Belt radius {parameter_name} changed to {new_radius}")
        # This will be handled by the parameter controller
        pass

    def get_mechanism_type(self) -> str:
        """Return the mechanism type."""
        return "belt"

    def get_editable_parameters(self) -> list[str]:
        """Get list of parameter names that can be edited."""
        return [
            "pulley_1_radius",
            "pulley_2_radius",
            "belt_tension",
            "angular_velocity_1",
            "slip_coefficient",
            "belt_width",
            "belt_thickness",
        ]

    def calculate_gear_ratio(self) -> float:
        """
        Calculate the gear ratio between pulleys.

        Returns:
            Gear ratio (pulley1_radius / pulley2_radius)
        """
        params = self.layer_data.get("params", {})
        r1 = params.get("pulley_1_radius", 40.0)
        r2 = params.get("pulley_2_radius", 25.0)

        if r2 == 0:
            return 1.0

        return r1 / r2

    def calculate_belt_length(self) -> float:
        """
        Calculate the total belt length.

        Returns:
            Total belt length
        """
        params = self.layer_data.get("params", {})
        key_points = self.layer_data.get("key_points", {})

        r1 = params.get("pulley_1_radius", 40.0)
        r2 = params.get("pulley_2_radius", 25.0)

        center1 = key_points.get("pulley_1_center", [0, 0])
        center2 = key_points.get("pulley_2_center", [100, 0])

        # Distance between centers
        distance = math.sqrt((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2)

        # Belt length calculation for external belt
        if distance > abs(r1 - r2):
            # Arc lengths
            arc1 = math.pi * r1
            arc2 = math.pi * r2

            # Straight sections
            if r1 != r2:
                beta = math.asin(abs(r1 - r2) / distance)
                straight_length = 2 * distance * math.cos(beta)
            else:
                straight_length = 2 * distance

            total_length = arc1 + arc2 + straight_length
        else:
            # Internal belt configuration
            total_length = 2 * math.pi * (r1 + r2)

        return total_length

    def get_belt_speed(self) -> float:
        """
        Calculate the belt speed.

        Returns:
            Belt speed in units per second
        """
        params = self.layer_data.get("params", {})
        r1 = params.get("pulley_1_radius", 40.0)
        omega1 = params.get("angular_velocity_1", 1.0)
        slip_coeff = params.get("slip_coefficient", 0.0)

        return r1 * omega1 * (1 - slip_coeff)
