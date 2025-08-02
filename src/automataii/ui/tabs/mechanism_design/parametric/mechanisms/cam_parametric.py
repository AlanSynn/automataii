"""
Parametric editor for cam mechanisms.

Provides interactive editing of cam center, follower position, and cam parameters
for cam-follower systems.
"""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from ..base.parametric_interface import ParametricHandleFactory, ParametricMechanismInterface
from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class CamParametricEditor(ParametricMechanismInterface):
    """
    Parametric editor for cam mechanisms.

    Provides interactive editing capabilities for:
    - Cam center position
    - Follower position
    - Base radius adjustment
    - Rise parameter modification
    - Motion law selection
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        super().__init__(mechanism_id, layer_data, scene_manager)

        # Cam-specific constraints
        self.min_base_radius = 10.0  # Minimum base radius
        self.max_base_radius = 200.0  # Maximum base radius
        self.min_rise = 5.0  # Minimum rise
        self.max_rise = 100.0  # Maximum rise
        self.min_center_distance = 50.0  # Minimum distance between cam and follower

        # Store original parameters for validation
        self.original_params = layer_data.get("params", {}).copy()

    def create_handles(self) -> list[BaseHandle]:
        """
        Create handles for cam mechanism parameters.

        Returns:
            List of handles for cam center, follower position, and radius
        """
        handles = []
        key_points = self.layer_data.get("key_points", {})

        if not key_points:
            logger.warning(f"No key_points found for cam {self.mechanism_id}")
            return handles

        # Get scene transform function
        transform = self.scene_manager.visuals.visual_factory.get_scene_transform_function(
            self.layer_data
        )

        # Create handle for cam center
        cam_center_data = key_points.get("cam_center")
        if cam_center_data:
            scene_pos = transform(cam_center_data)
            handle = ParametricHandleFactory.create_anchor_handle(
                mechanism_id=self.mechanism_id,
                anchor_name="cam_center",
                position=scene_pos,
                mechanism_data=self.layer_data,
                callback=self._on_anchor_moved,
            )
            if handle:
                handles.append(handle)
                logger.debug(f"Created cam center handle at {scene_pos}")

        # Create handle for follower position
        follower_data = key_points.get("follower_position")
        if follower_data:
            scene_pos = transform(follower_data)
            handle = ParametricHandleFactory.create_anchor_handle(
                mechanism_id=self.mechanism_id,
                anchor_name="follower_position",
                position=scene_pos,
                mechanism_data=self.layer_data,
                callback=self._on_anchor_moved,
            )
            if handle:
                handles.append(handle)
                logger.debug(f"Created follower position handle at {scene_pos}")

        # Create handle for base radius adjustment
        cam_center_data = key_points.get("cam_center", [0, 0])
        base_radius = self.layer_data.get("params", {}).get("base_radius", 50.0)

        if cam_center_data:
            scene_center = transform(cam_center_data)
            radius_pos = QPointF(scene_center.x() + base_radius, scene_center.y())

            handle = ParametricHandleFactory.create_radius_handle(
                mechanism_id=self.mechanism_id,
                parameter_name="base_radius",
                center_position=scene_center,
                radius_position=radius_pos,
                mechanism_data=self.layer_data,
                callback=self._on_radius_changed,
            )
            if handle:
                handles.append(handle)
                logger.debug(f"Created base radius handle at {radius_pos}")

        return handles

    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update cam mechanism parameters based on handle changes.

        Args:
            changed_handles: Dictionary mapping handle names to new positions

        Returns:
            Updated mechanism parameters
        """
        updated_params = self.layer_data.get("params", {}).copy()
        key_points = self.layer_data.get("key_points", {}).copy()

        # Handle cam center changes
        if "cam_center" in changed_handles:
            new_pos = changed_handles["cam_center"]
            if isinstance(new_pos, QPointF):
                key_points["cam_center"] = [new_pos.x(), new_pos.y()]
                logger.debug(f"Updated cam center to {new_pos}")

        # Handle follower position changes
        if "follower_position" in changed_handles:
            new_pos = changed_handles["follower_position"]
            if isinstance(new_pos, QPointF):
                key_points["follower_position"] = [new_pos.x(), new_pos.y()]
                logger.debug(f"Updated follower position to {new_pos}")

        # Handle base radius changes
        if "base_radius" in changed_handles:
            new_radius = changed_handles["base_radius"]
            if isinstance(new_radius, (int, float)):
                updated_params["base_radius"] = max(
                    self.min_base_radius, min(self.max_base_radius, new_radius)
                )
                logger.debug(f"Updated base radius to {updated_params['base_radius']}")

        # Update layer data
        self.layer_data["params"] = updated_params
        self.layer_data["key_points"] = key_points

        return updated_params

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate cam mechanism parameters.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check base radius
        base_radius = params.get("base_radius", 0)
        if base_radius < self.min_base_radius or base_radius > self.max_base_radius:
            return (
                False,
                f"Base radius must be between {self.min_base_radius} and {self.max_base_radius}",
            )

        # Check rise
        rise = params.get("rise", 0)
        if rise < self.min_rise or rise > self.max_rise:
            return False, f"Rise must be between {self.min_rise} and {self.max_rise}"

        # Check cam center and follower position
        key_points = self.layer_data.get("key_points", {})
        cam_center = key_points.get("cam_center", [0, 0])
        follower_pos = key_points.get("follower_position", [0, 0])

        distance = math.sqrt(
            (cam_center[0] - follower_pos[0]) ** 2 + (cam_center[1] - follower_pos[1]) ** 2
        )

        if distance < self.min_center_distance:
            return (
                False,
                f"Cam center and follower must be at least {self.min_center_distance} units apart",
            )

        # Check motion law
        motion_law = params.get("motion_law", "harmonic")
        if motion_law not in ["harmonic", "cycloidal", "polynomial"]:
            return False, "Motion law must be one of: harmonic, cycloidal, polynomial"

        return True, ""

    def get_parameter_constraints(self) -> dict[str, tuple[float, float]]:
        """
        Get parameter constraints for the cam mechanism.

        Returns:
            Dictionary mapping parameter names to (min, max) tuples
        """
        return {
            "base_radius": (self.min_base_radius, self.max_base_radius),
            "rise": (self.min_rise, self.max_rise),
            "offset": (-100.0, 100.0),
            "angular_velocity": (0.1, 10.0),
            "dwell_start": (0.0, 2 * math.pi),
            "dwell_end": (0.0, 2 * math.pi),
        }

    def _on_anchor_moved(self, anchor_name: str, new_position: QPointF):
        """Handle anchor point movement."""
        logger.debug(f"Cam anchor {anchor_name} moved to {new_position}")
        # This will be handled by the parameter controller
        pass

    def _on_radius_changed(self, parameter_name: str, new_radius: float):
        """Handle radius parameter changes."""
        logger.debug(f"Cam radius {parameter_name} changed to {new_radius}")
        # This will be handled by the parameter controller
        pass

    def get_mechanism_type(self) -> str:
        """Return the mechanism type."""
        return "cam"

    def get_editable_parameters(self) -> list[str]:
        """Get list of parameter names that can be edited."""
        return [
            "base_radius",
            "rise",
            "offset",
            "angular_velocity",
            "dwell_start",
            "dwell_end",
            "motion_law",
        ]

    def calculate_motion_profile(self, time_points: list[float]) -> list[float]:
        """
        Calculate the motion profile of the cam follower.

        Args:
            time_points: List of time points to evaluate

        Returns:
            List of follower positions at each time point
        """
        params = self.layer_data.get("params", {})
        base_radius = params.get("base_radius", 50.0)
        rise = params.get("rise", 20.0)
        motion_law = params.get("motion_law", "harmonic")

        positions = []
        for t in time_points:
            if motion_law == "harmonic":
                position = base_radius + rise * (1 - math.cos(math.pi * t)) / 2
            elif motion_law == "cycloidal":
                position = base_radius + rise * (t - math.sin(2 * math.pi * t) / (2 * math.pi))
            elif motion_law == "polynomial":
                position = base_radius + rise * (10 * t**3 - 15 * t**4 + 6 * t**5)
            else:
                position = base_radius + rise * (1 + math.sin(t)) / 2

            positions.append(position)

        return positions
