"""
Parametric editor for gear mechanisms.

Provides interactive editing of gear positions, radii, and gear ratios
for simple gear pairs and planetary gear systems.
"""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from ..base.parametric_interface import ParametricHandleFactory, ParametricMechanismInterface
from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class GearParametricEditor(ParametricMechanismInterface):
    """
    Parametric editor for gear mechanisms.

    Provides interactive editing capabilities for:
    - Gear center positions
    - Gear radii (and derived gear ratios)
    - Meshing distance constraints
    - Gear ratio validation
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        super().__init__(mechanism_id, layer_data, scene_manager)

        # Gear-specific constraints
        self.min_gear_radius = 10.0  # Minimum gear radius
        self.max_gear_radius = 200.0  # Maximum gear radius
        self.min_center_distance = 25.0  # Minimum distance between gear centers
        self.max_center_distance = 500.0  # Maximum distance between gear centers
        self.meshing_tolerance = (
            2.0  # Tolerance for gear meshing (radius1 + radius2 ≈ center_distance)
        )

        # Store original parameters
        self.original_params = layer_data.get("params", {}).copy()

    def create_handles(self) -> list[BaseHandle]:
        """
        Create handles for gear center positions and radii.

        Returns:
            List of handles for gear centers and radius adjustment
        """
        handles = []
        key_points = self.layer_data.get("key_points", {})
        params = self.layer_data.get("params", {})

        if not key_points:
            logger.warning(f"No key_points found for gear {self.mechanism_id}")
            return handles

        # Get scene transform function
        transform = self.scene_manager.visuals.visual_factory.get_scene_transform_function(
            self.layer_data
        )

        # Create handles for gear centers
        gear_centers = ["gear1_center", "gear2_center"]

        for center_name in gear_centers:
            center_data = key_points.get(center_name)
            if not center_data:
                logger.warning(f"Missing {center_name} in key_points for gear {self.mechanism_id}")
                continue

            # Transform to scene coordinates
            scene_pos = transform(center_data)

            # Create center position handle (using anchor handle for position)
            handle = ParametricHandleFactory.create_anchor_handle(
                mechanism_id=self.mechanism_id,
                anchor_name=center_name,
                position=scene_pos,
                mechanism_data=self.layer_data,
                callback=self._on_gear_center_moved,
            )

            if handle:
                handles.append(handle)
                logger.debug(f"Created gear center handle for {center_name} at {scene_pos}")

        # Create radius handles for gear sizing
        # TODO: Implement RadiusHandle for gear radius adjustment
        # For now, radius adjustment will be done through parameter input

        return handles

    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update gear parameters based on handle changes.

        Args:
            changed_handles: Dictionary mapping handle names to new positions

        Returns:
            Updated mechanism parameters
        """
        updated_params = self.layer_data.get("params", {}).copy()
        key_points = self.layer_data.get("key_points", {}).copy()

        # Update key points with new gear center positions
        for handle_name, new_position in changed_handles.items():
            if handle_name in ["gear1_center", "gear2_center"]:
                if isinstance(new_position, QPointF):
                    key_points[handle_name] = [new_position.x(), new_position.y()]
                else:
                    key_points[handle_name] = new_position

        # Recalculate gear meshing parameters
        if "gear1_center" in key_points and "gear2_center" in key_points:
            g1_center = key_points["gear1_center"]
            g2_center = key_points["gear2_center"]

            # Calculate center distance
            dx = g2_center[0] - g1_center[0]
            dy = g2_center[1] - g1_center[1]
            center_distance = math.sqrt(dx * dx + dy * dy)

            # Update center distance parameter
            updated_params["center_distance"] = center_distance

            # Adjust gear radii to maintain meshing if needed
            r1 = updated_params.get("radius1", 20.0)
            r2 = updated_params.get("radius2", 20.0)

            # Check if gears can mesh at current distance
            ideal_distance = r1 + r2
            distance_error = abs(center_distance - ideal_distance)

            if distance_error > self.meshing_tolerance:
                # Adjust radii proportionally to maintain meshing
                ratio = r1 / (r1 + r2)  # Preserve gear ratio
                new_r1 = center_distance * ratio
                new_r2 = center_distance * (1 - ratio)

                # Ensure radii are within bounds
                if (
                    self.min_gear_radius <= new_r1 <= self.max_gear_radius
                    and self.min_gear_radius <= new_r2 <= self.max_gear_radius
                ):
                    updated_params["radius1"] = new_r1
                    updated_params["radius2"] = new_r2
                    logger.debug(
                        f"Adjusted gear radii to maintain meshing: r1={new_r1:.2f}, r2={new_r2:.2f}"
                    )

            logger.debug(f"Updated gear center distance to {center_distance:.2f}")

        # Update the layer data
        self.layer_data["params"] = updated_params
        self.layer_data["key_points"] = key_points

        return updated_params

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate gear parameters for mechanical feasibility.

        Args:
            params: Mechanism parameters including gear radii and positions

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Extract gear parameters
            r1 = params.get("radius1", 0)
            r2 = params.get("radius2", 0)
            center_distance = params.get("center_distance", 0)

            if not all([r1 > 0, r2 > 0, center_distance > 0]):
                return False, "All gear radii and center distance must be positive"

            # Check radius constraints
            if r1 < self.min_gear_radius or r1 > self.max_gear_radius:
                return (
                    False,
                    f"Gear 1 radius out of range: {r1:.1f} (valid: {self.min_gear_radius}-{self.max_gear_radius})",
                )

            if r2 < self.min_gear_radius or r2 > self.max_gear_radius:
                return (
                    False,
                    f"Gear 2 radius out of range: {r2:.1f} (valid: {self.min_gear_radius}-{self.max_gear_radius})",
                )

            # Check center distance constraints
            if (
                center_distance < self.min_center_distance
                or center_distance > self.max_center_distance
            ):
                return (
                    False,
                    f"Center distance out of range: {center_distance:.1f} (valid: {self.min_center_distance}-{self.max_center_distance})",
                )

            # Check gear meshing constraint
            ideal_distance = r1 + r2
            distance_error = abs(center_distance - ideal_distance)

            if distance_error > self.meshing_tolerance:
                return (
                    False,
                    f"Gears don't mesh properly: center distance {center_distance:.1f} ≠ radius sum {ideal_distance:.1f} (tolerance: {self.meshing_tolerance})",
                )

            # Check gear ratio feasibility
            gear_ratio = r2 / r1
            if gear_ratio < 0.1 or gear_ratio > 10.0:
                return False, f"Gear ratio extreme: {gear_ratio:.2f} (recommended: 0.1-10.0)"

            # Check for gear interference (minimum spacing)
            min_spacing = 2.0  # Minimum clearance between gear teeth
            if center_distance < r1 + r2 + min_spacing:
                return (
                    False,
                    f"Gears too close: insufficient clearance (need {min_spacing}mm minimum)",
                )

            return True, ""

        except Exception as e:
            logger.error(f"Gear parameter validation failed: {e}")
            return False, f"Validation error: {str(e)}"

    def get_editable_parameters(self) -> list[str]:
        """
        Get list of parameters that can be edited for gear mechanisms.

        Returns:
            List of editable parameter names
        """
        return [
            "gear1_center",  # Gear 1 center position
            "gear2_center",  # Gear 2 center position
            "radius1",  # Gear 1 radius
            "radius2",  # Gear 2 radius
            "center_distance",  # Distance between gear centers (derived)
            "gear_ratio",  # Gear ratio (derived from radii)
            "rotation_speed1",  # Gear 1 rotation speed
            "rotation_speed2",  # Gear 2 rotation speed (derived)
        ]

    def _on_gear_center_moved(self, center_name: str, new_position: QPointF) -> None:
        """
        Callback function when a gear center handle is moved.

        Args:
            center_name: Name of the moved center (gear1_center or gear2_center)
            new_position: New position of the center in scene coordinates
        """
        try:
            # Update mechanism with new center position
            changed_handles = {center_name: new_position}
            updated_params = self.update_mechanism_from_handles(changed_handles)

            # Validate the new parameters
            is_valid, error_msg = self.validate_parameters(updated_params)

            if not is_valid:
                logger.warning(
                    f"Invalid gear configuration after moving {center_name}: {error_msg}"
                )
                # Could implement visual feedback here (red coloring, warning icons, etc.)
                return

            # Trigger mechanism recalculation
            logger.debug(f"Successfully moved {center_name} to {new_position}")

        except Exception as e:
            logger.error(f"Error handling gear center movement for {center_name}: {e}")

    def get_gear_ratio(self) -> float:
        """
        Calculate current gear ratio (output/input).

        Returns:
            Gear ratio as float
        """
        params = self.layer_data.get("params", {})
        r1 = params.get("radius1", 1.0)
        r2 = params.get("radius2", 1.0)
        return r2 / r1 if r1 != 0 else 1.0

    def set_gear_ratio(self, target_ratio: float) -> bool:
        """
        Set gear ratio by adjusting radii while maintaining center distance.

        Args:
            target_ratio: Desired gear ratio (r2/r1)

        Returns:
            True if successfully set, False otherwise
        """
        try:
            params = self.layer_data.get("params", {})
            center_distance = params.get("center_distance", 100.0)

            # Calculate new radii based on target ratio
            # r1 + r2 = center_distance (for meshing)
            # r2 / r1 = target_ratio
            # Solving: r1 = center_distance / (1 + target_ratio)

            new_r1 = center_distance / (1 + target_ratio)
            new_r2 = center_distance - new_r1

            # Validate new radii
            if (
                self.min_gear_radius <= new_r1 <= self.max_gear_radius
                and self.min_gear_radius <= new_r2 <= self.max_gear_radius
            ):
                params["radius1"] = new_r1
                params["radius2"] = new_r2
                self.layer_data["params"] = params

                logger.debug(
                    f"Set gear ratio to {target_ratio:.2f}: r1={new_r1:.2f}, r2={new_r2:.2f}"
                )
                return True
            else:
                logger.warning(f"Cannot set gear ratio {target_ratio:.2f}: radii out of bounds")
                return False

        except Exception as e:
            logger.error(f"Error setting gear ratio: {e}")
            return False

    def get_constraint_info(self) -> dict[str, Any]:
        """
        Get constraint information for UI display.

        Returns:
            Dictionary containing constraint information
        """
        return {
            "min_gear_radius": self.min_gear_radius,
            "max_gear_radius": self.max_gear_radius,
            "min_center_distance": self.min_center_distance,
            "max_center_distance": self.max_center_distance,
            "meshing_tolerance": self.meshing_tolerance,
            "recommended_gear_ratio_range": "0.1 - 10.0",
        }
