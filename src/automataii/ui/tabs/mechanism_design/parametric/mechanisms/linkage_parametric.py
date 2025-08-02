"""
Parametric editor for 4-bar linkage mechanisms.

Provides interactive editing of anchor points, link lengths, and geometric constraints
for 4-bar linkage systems.
"""

import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF

from ..base.parametric_interface import ParametricHandleFactory, ParametricMechanismInterface
from ..handles.base_handle import BaseHandle

logger = logging.getLogger(__name__)


class LinkageParametricEditor(ParametricMechanismInterface):
    """
    Parametric editor for 4-bar linkage mechanisms.

    Provides interactive editing capabilities for:
    - Ground pivot positions (anchor points)
    - Link lengths (through anchor manipulation)
    - Geometric constraints validation
    - Real-time mechanism recalculation
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        super().__init__(mechanism_id, layer_data, scene_manager)

        # 4-bar linkage specific constraints
        self.min_anchor_distance = 20.0  # Minimum distance between ground pivots
        self.max_anchor_distance = 500.0  # Maximum distance between ground pivots
        self.min_link_length = 10.0  # Minimum link length
        self.max_link_length = 1000.0  # Maximum link length

        # Store original parameters for validation
        self.original_params = layer_data.get("params", {}).copy()

    def create_handles(self) -> list[BaseHandle]:
        """
        Create anchor handles for ground pivots of the 4-bar linkage.

        Returns:
            List of AnchorHandle objects for ground_pivot_1 and ground_pivot_2
        """
        handles = []
        key_points = self.layer_data.get("key_points", {})

        if not key_points:
            logger.warning(f"No key_points found for linkage {self.mechanism_id}")
            return handles

        # Get scene transform function
        transform = self.scene_manager.visuals.visual_factory.get_scene_transform_function(
            self.layer_data
        )

        # Create handles for ground pivots
        pivot_names = ["ground_pivot_1", "ground_pivot_2"]

        for pivot_name in pivot_names:
            pivot_data = key_points.get(pivot_name)
            if not pivot_data:
                logger.warning(
                    f"Missing {pivot_name} in key_points for linkage {self.mechanism_id}"
                )
                continue

            # Transform to scene coordinates
            scene_pos = transform(pivot_data)

            # Create anchor handle
            handle = ParametricHandleFactory.create_anchor_handle(
                mechanism_id=self.mechanism_id,
                anchor_name=pivot_name,
                position=scene_pos,
                mechanism_data=self.layer_data,
                callback=self._on_anchor_moved,
            )

            if handle:
                handles.append(handle)
                logger.debug(f"Created anchor handle for {pivot_name} at {scene_pos}")

        return handles

    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update 4-bar linkage parameters based on anchor handle changes.

        Args:
            changed_handles: Dictionary mapping handle names to new positions

        Returns:
            Updated mechanism parameters
        """
        updated_params = self.layer_data.get("params", {}).copy()
        key_points = self.layer_data.get("key_points", {}).copy()

        # Update key points with new anchor positions
        for handle_name, new_position in changed_handles.items():
            if handle_name in ["ground_pivot_1", "ground_pivot_2"]:
                if isinstance(new_position, QPointF):
                    key_points[handle_name] = [new_position.x(), new_position.y()]
                else:
                    key_points[handle_name] = new_position

        # Recalculate link lengths based on new anchor positions
        if "ground_pivot_1" in key_points and "ground_pivot_2" in key_points:
            p1 = key_points["ground_pivot_1"]
            p2 = key_points["ground_pivot_2"]

            # Calculate ground link length (l1)
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            ground_length = math.sqrt(dx * dx + dy * dy)

            # Update l1 parameter (ground link)
            updated_params["l1"] = ground_length

            logger.debug(f"Updated ground link length to {ground_length:.2f}")

        # Update the layer data
        self.layer_data["params"] = updated_params
        self.layer_data["key_points"] = key_points

        return updated_params

    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate 4-bar linkage parameters for mechanical feasibility.

        Args:
            params: Mechanism parameters including link lengths

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Extract link lengths
            l1 = params.get("l1", 0)  # Ground link
            l2 = params.get("l2", 0)  # Driver link
            l3 = params.get("l3", 0)  # Coupler link
            l4 = params.get("l4", 0)  # Rocker link

            if not all([l1 > 0, l2 > 0, l3 > 0, l4 > 0]):
                return False, "All link lengths must be positive"

            # Check minimum and maximum link length constraints
            for i, length in enumerate([l1, l2, l3, l4], 1):
                if length < self.min_link_length:
                    return False, f"Link l{i} too short: {length:.1f} < {self.min_link_length}"
                if length > self.max_link_length:
                    return False, f"Link l{i} too long: {length:.1f} > {self.max_link_length}"

            # Grashof's criterion for linkage mobility
            lengths = [l1, l2, l3, l4]
            lengths.sort()
            s, p, q, l = lengths  # s=shortest, l=longest, p,q=intermediate

            # Check basic assembly condition (triangle inequality for each link triangle)
            # For a 4-bar linkage to be assemblable, certain triangle inequalities must hold

            # Assembly condition: |li - lj| <= lk + ll for all combinations
            assembly_conditions = [
                abs(l1 - l3) <= l2 + l4,  # Opposite links condition
                abs(l2 - l4) <= l1 + l3,  # Opposite links condition
                l1 <= l2 + l3 + l4,  # Triangle inequality
                l2 <= l1 + l3 + l4,  # Triangle inequality
                l3 <= l1 + l2 + l4,  # Triangle inequality
                l4 <= l1 + l2 + l3,  # Triangle inequality
            ]

            if not all(assembly_conditions):
                return False, "Linkage geometry not assemblable - triangle inequality violated"

            # Grashof condition for continuous rotation capability
            grashof_satisfied = s + l <= p + q + 1e-6  # Small tolerance for floating point

            if not grashof_satisfied:
                # Still valid, but warn about limited mobility
                logger.info(
                    f"Linkage {self.mechanism_id}: Grashof condition not satisfied - limited rotation"
                )

            # Check anchor distance constraints
            key_points = self.layer_data.get("key_points", {})
            if "ground_pivot_1" in key_points and "ground_pivot_2" in key_points:
                p1 = key_points["ground_pivot_1"]
                p2 = key_points["ground_pivot_2"]
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]
                anchor_distance = math.sqrt(dx * dx + dy * dy)

                if anchor_distance < self.min_anchor_distance:
                    return (
                        False,
                        f"Anchors too close: {anchor_distance:.1f} < {self.min_anchor_distance}",
                    )
                if anchor_distance > self.max_anchor_distance:
                    return (
                        False,
                        f"Anchors too far: {anchor_distance:.1f} > {self.max_anchor_distance}",
                    )

            return True, ""

        except Exception as e:
            logger.error(f"Parameter validation failed: {e}")
            return False, f"Validation error: {str(e)}"

    def get_editable_parameters(self) -> list[str]:
        """
        Get list of parameters that can be edited for 4-bar linkage.

        Returns:
            List of editable parameter names
        """
        return [
            "ground_pivot_1",  # Ground pivot 1 position
            "ground_pivot_2",  # Ground pivot 2 position
            "l1",  # Ground link length (derived from anchors)
            "l2",  # Driver link length
            "l3",  # Coupler link length
            "l4",  # Rocker link length
        ]

    def _on_anchor_moved(self, anchor_name: str, new_position: QPointF) -> None:
        """
        Callback function when an anchor handle is moved.

        Args:
            anchor_name: Name of the moved anchor (ground_pivot_1 or ground_pivot_2)
            new_position: New position of the anchor in scene coordinates
        """
        try:
            # Update mechanism with new anchor position
            changed_handles = {anchor_name: new_position}
            updated_params = self.update_mechanism_from_handles(changed_handles)

            # Validate the new parameters
            is_valid, error_msg = self.validate_parameters(updated_params)

            if not is_valid:
                logger.warning(
                    f"Invalid linkage configuration after moving {anchor_name}: {error_msg}"
                )
                # Could implement visual feedback here (red coloring, etc.)
                return

            # Trigger mechanism recalculation
            # This should be handled by the ParametricHandler's callback system
            logger.debug(f"Successfully moved {anchor_name} to {new_position}")

        except Exception as e:
            logger.error(f"Error handling anchor movement for {anchor_name}: {e}")

    def get_constraint_info(self) -> dict[str, Any]:
        """
        Get constraint information for UI display.

        Returns:
            Dictionary containing constraint information
        """
        return {
            "min_anchor_distance": self.min_anchor_distance,
            "max_anchor_distance": self.max_anchor_distance,
            "min_link_length": self.min_link_length,
            "max_link_length": self.max_link_length,
            "grashof_condition": "s + l <= p + q for continuous rotation",
        }
