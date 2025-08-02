"""
Parametric editor for spring/damper mechanisms.

Provides interactive editing of attachment points, spring parameters, and dynamics
for spring-mass-damper systems.
"""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from ..base.parametric_interface import ParametricHandleFactory, ParametricMechanismInterface
from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class SpringParametricEditor(ParametricMechanismInterface):
    """
    Parametric editor for spring/damper mechanisms.

    Provides interactive editing capabilities for:
    - Attachment point positions
    - Spring constant adjustment
    - Damping coefficient tuning
    - Rest length modification
    - Mass parameter changes
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        super().__init__(mechanism_id, layer_data, scene_manager)

        # Spring-specific constraints
        self.min_spring_constant = 0.1  # Minimum spring constant
        self.max_spring_constant = 10000.0  # Maximum spring constant
        self.min_damping = 0.0  # Minimum damping coefficient
        self.max_damping = 1000.0  # Maximum damping coefficient
        self.min_rest_length = 5.0  # Minimum rest length
        self.max_rest_length = 500.0  # Maximum rest length
        self.min_mass = 0.01  # Minimum mass
        self.max_mass = 100.0  # Maximum mass

        # Store original parameters for validation
        self.original_params = layer_data.get("params", {}).copy()

    def create_handles(self) -> list[BaseHandle]:
        """
        Create handles for spring/damper mechanism parameters.

        Returns:
            List of handles for attachment points and spring length
        """
        handles = []
        key_points = self.layer_data.get("key_points", {})

        if not key_points:
            logger.warning(f"No key_points found for spring {self.mechanism_id}")
            return handles

        # Get scene transform function
        transform = self.scene_manager.visuals.visual_factory.get_scene_transform_function(
            self.layer_data
        )

        # Create handles for attachment points
        attachment_points = ["attachment_1", "attachment_2"]

        for attachment_name in attachment_points:
            attachment_data = key_points.get(attachment_name)
            if attachment_data:
                scene_pos = transform(attachment_data)
                handle = ParametricHandleFactory.create_anchor_handle(
                    mechanism_id=self.mechanism_id,
                    anchor_name=attachment_name,
                    position=scene_pos,
                    mechanism_data=self.layer_data,
                    callback=self._on_anchor_moved,
                )
                if handle:
                    handles.append(handle)
                    logger.debug(f"Created attachment handle for {attachment_name} at {scene_pos}")

        # Create handle for rest length adjustment
        attach1_data = key_points.get("attachment_1", [0, 0])
        attach2_data = key_points.get("attachment_2", [0, 100])
        params = self.layer_data.get("params", {})
        rest_length = params.get("rest_length", 100.0)

        if attach1_data and attach2_data:
            scene_pos1 = transform(attach1_data)
            scene_pos2 = transform(attach2_data)

            # Calculate current direction
            dx = scene_pos2.x() - scene_pos1.x()
            dy = scene_pos2.y() - scene_pos1.y()
            current_length = math.sqrt(dx**2 + dy**2)

            if current_length > 0:
                # Position rest length handle between attachment points
                ratio = rest_length / current_length
                rest_pos = QPointF(scene_pos1.x() + dx * ratio, scene_pos1.y() + dy * ratio)

                handle = ParametricHandleFactory.create_anchor_handle(
                    mechanism_id=self.mechanism_id,
                    anchor_name="rest_length_marker",
                    position=rest_pos,
                    mechanism_data=self.layer_data,
                    callback=self._on_rest_length_changed,
                )
                if handle:
                    handles.append(handle)
                    logger.debug(f"Created rest length handle at {rest_pos}")

        return handles

    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update spring/damper mechanism parameters based on handle changes.

        Args:
            changed_handles: Dictionary mapping handle names to new positions

        Returns:
            Updated mechanism parameters
        """
        updated_params = self.layer_data.get("params", {}).copy()
        key_points = self.layer_data.get("key_points", {}).copy()

        # Handle attachment point changes
        for attachment_name in ["attachment_1", "attachment_2"]:
            if attachment_name in changed_handles:
                new_pos = changed_handles[attachment_name]
                if isinstance(new_pos, QPointF):
                    key_points[attachment_name] = [new_pos.x(), new_pos.y()]
                    logger.debug(f"Updated {attachment_name} to {new_pos}")

        # Handle rest length changes
        if "rest_length_marker" in changed_handles:
            new_pos = changed_handles["rest_length_marker"]
            if isinstance(new_pos, QPointF):
                # Calculate new rest length based on position
                attach1 = key_points.get("attachment_1", [0, 0])
                attach2 = key_points.get("attachment_2", [0, 100])

                # Distance from first attachment to rest length marker
                new_rest_length = math.sqrt(
                    (new_pos.x() - attach1[0]) ** 2 + (new_pos.y() - attach1[1]) ** 2
                )

                updated_params["rest_length"] = max(
                    self.min_rest_length, min(self.max_rest_length, new_rest_length)
                )
                logger.debug(f"Updated rest length to {updated_params['rest_length']}")

        # Update layer data
        self.layer_data["params"] = updated_params
        self.layer_data["key_points"] = key_points

        return updated_params

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate spring/damper mechanism parameters.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check spring constant
        spring_constant = params.get("spring_constant", 0)
        if spring_constant < self.min_spring_constant or spring_constant > self.max_spring_constant:
            return (
                False,
                f"Spring constant must be between {self.min_spring_constant} and {self.max_spring_constant}",
            )

        # Check damping coefficient
        damping = params.get("damping_coefficient", 0)
        if damping < self.min_damping or damping > self.max_damping:
            return (
                False,
                f"Damping coefficient must be between {self.min_damping} and {self.max_damping}",
            )

        # Check rest length
        rest_length = params.get("rest_length", 0)
        if rest_length < self.min_rest_length or rest_length > self.max_rest_length:
            return (
                False,
                f"Rest length must be between {self.min_rest_length} and {self.max_rest_length}",
            )

        # Check mass
        mass = params.get("mass", 0)
        if mass < self.min_mass or mass > self.max_mass:
            return False, f"Mass must be between {self.min_mass} and {self.max_mass}"

        # Check compression/extension ratios
        max_compression = params.get("max_compression", 0.8)
        if max_compression <= 0 or max_compression >= 1:
            return False, "Maximum compression must be between 0 and 1"

        max_extension = params.get("max_extension", 2.0)
        if max_extension <= 1:
            return False, "Maximum extension must be greater than 1"

        # Check attachment points
        key_points = self.layer_data.get("key_points", {})
        attach1 = key_points.get("attachment_1", [0, 0])
        attach2 = key_points.get("attachment_2", [0, 100])

        if attach1 == attach2:
            return False, "Attachment points cannot be at the same location"

        return True, ""

    def get_parameter_constraints(self) -> dict[str, tuple[float, float]]:
        """
        Get parameter constraints for the spring/damper mechanism.

        Returns:
            Dictionary mapping parameter names to (min, max) tuples
        """
        return {
            "spring_constant": (self.min_spring_constant, self.max_spring_constant),
            "damping_coefficient": (self.min_damping, self.max_damping),
            "rest_length": (self.min_rest_length, self.max_rest_length),
            "mass": (self.min_mass, self.max_mass),
            "max_compression": (0.1, 0.9),
            "max_extension": (1.1, 5.0),
            "coil_diameter": (1.0, 50.0),
            "wire_diameter": (0.1, 10.0),
            "number_of_coils": (3, 50),
        }

    def _on_anchor_moved(self, anchor_name: str, new_position: QPointF):
        """Handle anchor point movement."""
        logger.debug(f"Spring anchor {anchor_name} moved to {new_position}")
        # This will be handled by the parameter controller
        pass

    def _on_rest_length_changed(self, anchor_name: str, new_position: QPointF):
        """Handle rest length marker movement."""
        logger.debug(f"Spring rest length marker moved to {new_position}")
        # This will be handled by the parameter controller
        pass

    def get_mechanism_type(self) -> str:
        """Return the mechanism type."""
        return "spring"

    def get_editable_parameters(self) -> list[str]:
        """Get list of parameter names that can be edited."""
        return [
            "spring_constant",
            "damping_coefficient",
            "rest_length",
            "mass",
            "max_compression",
            "max_extension",
            "coil_diameter",
            "wire_diameter",
            "number_of_coils",
        ]

    def calculate_natural_frequency(self) -> float:
        """
        Calculate the natural frequency of the spring-mass system.

        Returns:
            Natural frequency in Hz
        """
        params = self.layer_data.get("params", {})
        k = params.get("spring_constant", 100.0)
        m = params.get("mass", 1.0)

        if m <= 0:
            return 0.0

        omega_n = math.sqrt(k / m)
        return omega_n / (2 * math.pi)

    def calculate_damping_ratio(self) -> float:
        """
        Calculate the damping ratio of the system.

        Returns:
            Damping ratio (dimensionless)
        """
        params = self.layer_data.get("params", {})
        c = params.get("damping_coefficient", 10.0)
        k = params.get("spring_constant", 100.0)
        m = params.get("mass", 1.0)

        if k <= 0 or m <= 0:
            return 0.0

        critical_damping = 2 * math.sqrt(k * m)
        return c / critical_damping

    def get_system_type(self) -> str:
        """
        Determine the system type based on damping ratio.

        Returns:
            System type: "underdamped", "critically_damped", or "overdamped"
        """
        zeta = self.calculate_damping_ratio()

        if zeta < 1.0:
            return "underdamped"
        elif zeta == 1.0:
            return "critically_damped"
        else:
            return "overdamped"

    def calculate_current_length(self) -> float:
        """
        Calculate the current distance between attachment points.

        Returns:
            Current length
        """
        key_points = self.layer_data.get("key_points", {})
        attach1 = key_points.get("attachment_1", [0, 0])
        attach2 = key_points.get("attachment_2", [0, 100])

        return math.sqrt((attach1[0] - attach2[0]) ** 2 + (attach1[1] - attach2[1]) ** 2)

    def calculate_spring_force(self, displacement: float = None) -> float:
        """
        Calculate the spring force for a given displacement.

        Args:
            displacement: Displacement from rest position (if None, uses current position)

        Returns:
            Spring force
        """
        params = self.layer_data.get("params", {})
        k = params.get("spring_constant", 100.0)
        rest_length = params.get("rest_length", 100.0)

        if displacement is None:
            current_length = self.calculate_current_length()
            displacement = current_length - rest_length

        return k * displacement
