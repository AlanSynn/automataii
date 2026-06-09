"""
Service class for mechanism-related business logic.

This service handles mechanism calculations, positioning, and adjustments
that were previously embedded in the MechanismDesignTab class.

Architecture Note:
- This is an APPLICATION layer service
- It must NOT depend on presentation layer (Qt types)
- Path conversion is injected via callable to maintain layer separation
"""

from collections.abc import Callable
from typing import Any

import numpy as np


class MechanismService:
    """Service for handling mechanism business logic."""

    def __init__(self):
        """Initialize the mechanism service."""
        pass

    def verify_coupler_joint_connection(
        self,
        layer_data: dict,
        parts_data: dict,
        initial_skeleton_data_cache: dict,
        scene_transform_function_getter,
        mechanism_output_calculator,
    ) -> bool:
        """
        Verify that the mechanism attachment point is properly connected to the target skeleton joint.

        Args:
            layer_data: Mechanism layer data
            parts_data: Parts data dictionary
            initial_skeleton_data_cache: Cached skeleton data
            scene_transform_function_getter: Function to get scene transform
            mechanism_output_calculator: Function to calculate mechanism output

        Returns:
            True if connection is verified, False otherwise
        """
        part_name = layer_data.get("part_name")
        if not part_name or part_name not in parts_data:
            return False

        part_info = parts_data[part_name]
        anchor_joint_id = part_info.anchor_joint_id

        # Get the target joint position from cached skeleton data
        if initial_skeleton_data_cache and anchor_joint_id in initial_skeleton_data_cache.get(
            "joints", {}
        ):
            joint_data = initial_skeleton_data_cache["joints"][anchor_joint_id]
            target_joint_pos = np.array(joint_data.get("position", [0, 0]))

            # Get mechanism attachment info from dataset
            skeleton_attachment = layer_data.get("skeleton_attachment", {})
            attachment_coords = skeleton_attachment.get("attachment_coordinates")

            if attachment_coords:
                # Use the specified attachment coordinates from dataset
                to_scene_coords = scene_transform_function_getter(layer_data)
                if to_scene_coords:
                    attachment_scene_pos = to_scene_coords(np.array(attachment_coords))
                    initial_pos_np = np.array([attachment_scene_pos.x(), attachment_scene_pos.y()])
                    distance = np.linalg.norm(initial_pos_np - target_joint_pos)

                    return distance <= 50  # Threshold for "close enough" in scene coordinates
            else:
                # Fallback to calculating mechanism output
                initial_coupler_pos = mechanism_output_calculator(
                    layer_data["type"], layer_data["params"], 0.0, layer_data
                )

                if initial_coupler_pos:
                    initial_pos_np = np.array([initial_coupler_pos.x(), initial_coupler_pos.y()])
                    distance = np.linalg.norm(initial_pos_np - target_joint_pos)

                    return distance <= 50  # Threshold for "close enough" in scene coordinates

        return False

    def adjust_mechanism_to_target_joint(
        self,
        layer_data: dict,
        parts_data: dict,
        initial_skeleton_data_cache: dict,
        mechanism_output_calculator: Callable,
        path_to_numpy_converter: Callable[[Any], np.ndarray | None] | None = None,
    ) -> bool:
        """
        Adjust mechanism positioning so coupler point aligns with target skeleton joint.

        Args:
            layer_data: Mechanism layer data (modified in-place)
            parts_data: Parts data dictionary
            initial_skeleton_data_cache: Cached skeleton data
            mechanism_output_calculator: Function to calculate mechanism output
            path_to_numpy_converter: Function to convert path object to numpy array
                                     (injected from presentation layer)

        Returns:
            True if adjustment was made, False otherwise
        """
        part_name = layer_data.get("part_name")
        if not part_name or part_name not in parts_data:
            return False

        part_info = parts_data[part_name]
        anchor_joint_id = part_info.anchor_joint_id

        # Get the target joint position from cached skeleton data
        if initial_skeleton_data_cache and anchor_joint_id in initial_skeleton_data_cache.get(
            "joints", {}
        ):
            joint_data = initial_skeleton_data_cache["joints"][anchor_joint_id]
            target_joint_pos = np.array(joint_data.get("position", [0, 0]))

            # Calculate the current mechanism coupler point position
            current_coupler_pos = mechanism_output_calculator(
                layer_data["type"], layer_data["params"], 0.0, layer_data
            )

            if current_coupler_pos:
                current_pos_np = np.array([current_coupler_pos.x(), current_coupler_pos.y()])
                offset = target_joint_pos - current_pos_np

                # Simple offset adjustment - modify the target center directly
                full_sim_data = layer_data.get("full_simulation_data", {})
                if "coupler_path" in full_sim_data:
                    # Calculate required adjustment in mechanism space
                    target_path = layer_data.get("generated_path")
                    if target_path and path_to_numpy_converter:
                        user_path_np = path_to_numpy_converter(target_path)
                        if user_path_np is not None:
                            target_center_np = np.mean(user_path_np, axis=0)

                            # Adjust target center to align with skeleton joint
                            new_target_center = target_center_np + offset

                            # Store the adjustment for the transform function
                            layer_data["_target_center_adjustment"] = new_target_center.tolist()
                            return True

        return False
