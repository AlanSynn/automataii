"""
Influence Map Generator - Vectorized influence map generation.

Extracted from FastSkeletonSegmenter. Handles efficient
influence map creation for body part segmentation.

Design Pattern: Generator (vectorized computation)
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


class InfluenceMapGenerator:
    """
    Generates influence maps for body part segmentation.

    Uses vectorized numpy operations for efficient computation.

    Responsibilities:
    - Create part influence maps based on joint positions
    - Create bone influence maps for connected joints
    - Apply part modulation to influence maps

    Time Complexity: O(w * h) where w, h = image dimensions
    """

    def __init__(
        self,
        image_shape: tuple[int, int],
        joint_map: dict[str, tuple[int, int]],
    ) -> None:
        """
        Initialize influence map generator.

        Args:
            image_shape: (height, width) of target image
            joint_map: Mapping of joint names to (x, y) positions
        """
        self._height, self._width = image_shape
        self._joint_map = joint_map

        # Pre-compute coordinate grids
        self._y_grid, self._x_grid = np.mgrid[0:self._height, 0:self._width]

    def create_part_influence(
        self,
        joint_name: str,
        base_radius: float = 50.0,
        falloff_type: str = "gaussian",
    ) -> np.ndarray:
        """
        Create influence map centered on a joint.

        Args:
            joint_name: Name of the joint
            base_radius: Base influence radius
            falloff_type: "gaussian" or "linear"

        Returns:
            Influence map as float array [0, 1]

        Time Complexity: O(w * h)
        """
        if joint_name not in self._joint_map:
            return np.zeros((self._height, self._width), dtype=np.float32)

        cx, cy = self._joint_map[joint_name]

        # Calculate distances from joint
        dx = self._x_grid - cx
        dy = self._y_grid - cy
        distances = np.sqrt(dx * dx + dy * dy)

        # Apply falloff
        if falloff_type == "gaussian":
            sigma = base_radius / 2.0
            influence = np.exp(-(distances ** 2) / (2 * sigma ** 2))
        else:  # linear
            influence = np.clip(1.0 - distances / base_radius, 0, 1)

        return influence.astype(np.float32)

    def create_bone_influence(
        self,
        joint1_name: str,
        joint2_name: str,
        width: float = 30.0,
    ) -> np.ndarray:
        """
        Create influence map along a bone (line between joints).

        Args:
            joint1_name: Start joint name
            joint2_name: End joint name
            width: Influence width perpendicular to bone

        Returns:
            Influence map as float array [0, 1]

        Time Complexity: O(w * h)
        """
        if joint1_name not in self._joint_map or joint2_name not in self._joint_map:
            return np.zeros((self._height, self._width), dtype=np.float32)

        x1, y1 = self._joint_map[joint1_name]
        x2, y2 = self._joint_map[joint2_name]

        # Bone vector
        dx = x2 - x1
        dy = y2 - y1
        bone_length = math.sqrt(dx * dx + dy * dy)

        if bone_length < 1e-6:
            return self.create_part_influence(joint1_name, width)

        # Normalized bone direction
        ux = dx / bone_length
        uy = dy / bone_length

        # Project points onto bone axis
        px = self._x_grid - x1
        py = self._y_grid - y1

        # Parallel component (along bone)
        t = px * ux + py * uy
        t = np.clip(t, 0, bone_length)

        # Perpendicular component (distance from bone)
        nearest_x = x1 + t * ux
        nearest_y = y1 + t * uy
        perp_dist = np.sqrt(
            (self._x_grid - nearest_x) ** 2 + (self._y_grid - nearest_y) ** 2
        )

        # Gaussian falloff from bone
        sigma = width / 2.0
        influence = np.exp(-(perp_dist ** 2) / (2 * sigma ** 2))

        return influence.astype(np.float32)

    def create_all_influence_maps(
        self,
        part_definitions: dict[str, dict[str, Any]],
    ) -> dict[str, np.ndarray]:
        """
        Create influence maps for all defined parts.

        Args:
            part_definitions: Dictionary of part definitions with:
                - joints: list of joint names
                - bones: list of (joint1, joint2) tuples
                - radius: influence radius (optional)

        Returns:
            Dictionary mapping part names to influence maps

        Time Complexity: O(p * w * h) where p = number of parts
        """
        influence_maps = {}

        for part_name, definition in part_definitions.items():
            # Start with zeros
            combined = np.zeros((self._height, self._width), dtype=np.float32)

            # Add joint influences
            joints = definition.get("joints", [])
            radius = definition.get("radius", 50.0)

            for joint in joints:
                influence = self.create_part_influence(joint, radius)
                combined = np.maximum(combined, influence)

            # Add bone influences
            bones = definition.get("bones", [])
            bone_width = definition.get("bone_width", 30.0)

            for j1, j2 in bones:
                influence = self.create_bone_influence(j1, j2, bone_width)
                combined = np.maximum(combined, influence)

            influence_maps[part_name] = combined

        return influence_maps

    def apply_modulation(
        self,
        influence_map: np.ndarray,
        modulation_mask: np.ndarray | None,
        strength: float = 1.0,
    ) -> np.ndarray:
        """
        Apply modulation mask to influence map.

        Args:
            influence_map: Base influence map
            modulation_mask: Optional modulation mask [0, 1]
            strength: Modulation strength

        Returns:
            Modulated influence map

        Time Complexity: O(w * h)
        """
        if modulation_mask is None:
            return influence_map

        modulated = influence_map * (
            1.0 - strength + strength * modulation_mask
        )
        return np.clip(modulated, 0, 1).astype(np.float32)

    def get_joint_position(self, joint_name: str) -> tuple[int, int] | None:
        """Get position of a joint."""
        return self._joint_map.get(joint_name)

    def update_joint_position(
        self,
        joint_name: str,
        position: tuple[int, int],
    ) -> None:
        """Update position of a joint."""
        self._joint_map[joint_name] = position
