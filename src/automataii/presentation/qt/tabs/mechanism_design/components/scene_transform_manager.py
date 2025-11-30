"""
Scene Transform Manager - Coordinate transformations between mechanism and scene space.

Extracted from MechanismDesignTab. Handles all coordinate transformations
for mapping mechanism coordinates to Qt scene coordinates and back.

Design Pattern: Adapter (coordinate space adaptation)
"""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QPointF

if TYPE_CHECKING:
    pass


class SceneTransformManager:
    """
    Manages coordinate transformations between mechanism and scene space.

    Responsibilities:
    - Create transform functions from mechanism to scene coordinates
    - Create inverse transform functions from scene to mechanism coordinates
    - Handle various mechanism anchor configurations

    Time Complexity: O(1) per transformation
    """

    def __init__(self) -> None:
        """Initialize transform manager."""
        pass

    def get_scene_transform_function(
        self,
        layer_data: dict,
    ) -> Callable[[np.ndarray], QPointF] | None:
        """
        Create a transform function from mechanism to scene coordinates.

        Args:
            layer_data: Layer data with mechanism configuration

        Returns:
            Transform function (mechanism coords -> scene coords) or None

        Time Complexity: O(1) per call
        """
        try:
            # Get mechanism key points
            key_points = layer_data.get("key_points", {})

            # Ground pivot 1 in mechanism space (typically origin)
            p1_mech = np.array(key_points.get("ground_pivot_1", [0, 0]))

            # Anchor position in scene space
            anchor_scene_x = layer_data.get("anchor_scene_x")
            anchor_scene_y = layer_data.get("anchor_scene_y")

            if anchor_scene_x is None or anchor_scene_y is None:
                # Try to get from anchor_position
                anchor_pos = layer_data.get("anchor_position")
                if anchor_pos:
                    if isinstance(anchor_pos, QPointF):
                        anchor_scene_x = anchor_pos.x()
                        anchor_scene_y = anchor_pos.y()
                    elif isinstance(anchor_pos, list | tuple) and len(anchor_pos) >= 2:
                        anchor_scene_x = anchor_pos[0]
                        anchor_scene_y = anchor_pos[1]

            if anchor_scene_x is None or anchor_scene_y is None:
                return None

            # Get scale and rotation parameters
            scale = layer_data.get("scale", 1.0)
            rotation = layer_data.get("rotation", 0.0)

            # Calculate transformation matrix components
            cos_r = math.cos(rotation)
            sin_r = math.sin(rotation)

            # Translation offset (anchor scene position - scaled/rotated mechanism origin)
            offset_x = anchor_scene_x - scale * (p1_mech[0] * cos_r - p1_mech[1] * sin_r)
            offset_y = anchor_scene_y - scale * (p1_mech[0] * sin_r + p1_mech[1] * cos_r)

            def to_scene_coords(p_orig: np.ndarray) -> QPointF:
                """Transform mechanism coordinates to scene coordinates."""
                try:
                    # Apply scale and rotation
                    x_rot = scale * (p_orig[0] * cos_r - p_orig[1] * sin_r)
                    y_rot = scale * (p_orig[0] * sin_r + p_orig[1] * cos_r)

                    # Apply translation
                    scene_x = x_rot + offset_x
                    scene_y = y_rot + offset_y

                    return QPointF(float(scene_x), float(scene_y))
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    return QPointF(float(offset_x), float(offset_y))

            return to_scene_coords

        except (KeyError, ValueError, TypeError):
            return None

    def get_inverse_scene_transform_function(
        self,
        layer_data: dict,
    ) -> Callable[[QPointF], np.ndarray] | None:
        """
        Create an inverse transform function from scene to mechanism coordinates.

        Args:
            layer_data: Layer data with mechanism configuration

        Returns:
            Inverse transform function (scene coords -> mechanism coords) or None

        Time Complexity: O(1) per call
        """
        try:
            # Get mechanism key points
            key_points = layer_data.get("key_points", {})

            # Ground pivot 1 in mechanism space
            p1_mech = np.array(key_points.get("ground_pivot_1", [0, 0]))

            # Anchor position in scene space
            anchor_scene_x = layer_data.get("anchor_scene_x")
            anchor_scene_y = layer_data.get("anchor_scene_y")

            if anchor_scene_x is None or anchor_scene_y is None:
                anchor_pos = layer_data.get("anchor_position")
                if anchor_pos:
                    if isinstance(anchor_pos, QPointF):
                        anchor_scene_x = anchor_pos.x()
                        anchor_scene_y = anchor_pos.y()
                    elif isinstance(anchor_pos, list | tuple) and len(anchor_pos) >= 2:
                        anchor_scene_x = anchor_pos[0]
                        anchor_scene_y = anchor_pos[1]

            if anchor_scene_x is None or anchor_scene_y is None:
                return None

            # Get scale and rotation parameters
            scale = layer_data.get("scale", 1.0)
            rotation = layer_data.get("rotation", 0.0)

            if abs(scale) < 1e-10:
                return None

            # Inverse transformation components
            cos_r = math.cos(-rotation)
            sin_r = math.sin(-rotation)
            inv_scale = 1.0 / scale

            # Center point in scene coordinates
            center = np.array([anchor_scene_x, anchor_scene_y])

            def to_mechanism_coords(scene_point: QPointF) -> np.ndarray:
                """Transform scene coordinates to mechanism coordinates."""
                try:
                    # Translate to origin
                    dx = scene_point.x() - center[0]
                    dy = scene_point.y() - center[1]

                    # Apply inverse rotation
                    x_rot = dx * cos_r - dy * sin_r
                    y_rot = dx * sin_r + dy * cos_r

                    # Apply inverse scale and add mechanism origin offset
                    mech_x = x_rot * inv_scale + p1_mech[0]
                    mech_y = y_rot * inv_scale + p1_mech[1]

                    return np.array([mech_x, mech_y])
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    return center

            return to_mechanism_coords

        except (KeyError, ValueError, TypeError):
            return None

    def create_transform_from_anchors(
        self,
        mech_anchor1: np.ndarray,
        mech_anchor2: np.ndarray,
        scene_anchor1: QPointF,
        scene_anchor2: QPointF,
    ) -> Callable[[np.ndarray], QPointF] | None:
        """
        Create transform function from two corresponding anchor pairs.

        This allows arbitrary scaling and rotation based on how anchors
        are positioned in both coordinate systems.

        Args:
            mech_anchor1: First anchor in mechanism space
            mech_anchor2: Second anchor in mechanism space
            scene_anchor1: First anchor in scene space
            scene_anchor2: Second anchor in scene space

        Returns:
            Transform function or None if anchors are degenerate

        Time Complexity: O(1) per call
        """
        try:
            # Calculate vectors in both spaces
            mech_vec = mech_anchor2 - mech_anchor1
            mech_len = np.linalg.norm(mech_vec)

            scene_vec = np.array([
                scene_anchor2.x() - scene_anchor1.x(),
                scene_anchor2.y() - scene_anchor1.y()
            ])
            scene_len = np.linalg.norm(scene_vec)

            if mech_len < 1e-10 or scene_len < 1e-10:
                return None

            # Calculate scale
            scale = scene_len / mech_len

            # Calculate rotation angle
            mech_angle = math.atan2(mech_vec[1], mech_vec[0])
            scene_angle = math.atan2(scene_vec[1], scene_vec[0])
            rotation = scene_angle - mech_angle

            cos_r = math.cos(rotation)
            sin_r = math.sin(rotation)

            # Calculate translation
            offset_x = scene_anchor1.x() - scale * (mech_anchor1[0] * cos_r - mech_anchor1[1] * sin_r)
            offset_y = scene_anchor1.y() - scale * (mech_anchor1[0] * sin_r + mech_anchor1[1] * cos_r)

            def to_scene_coords(p_orig: np.ndarray) -> QPointF:
                """Transform mechanism coordinates to scene coordinates."""
                try:
                    x_rot = scale * (p_orig[0] * cos_r - p_orig[1] * sin_r)
                    y_rot = scale * (p_orig[0] * sin_r + p_orig[1] * cos_r)

                    scene_x = x_rot + offset_x
                    scene_y = y_rot + offset_y

                    return QPointF(float(scene_x), float(scene_y))
                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    return scene_anchor1

            return to_scene_coords

        except (ValueError, TypeError):
            return None

    def calculate_scale_from_key_points(
        self,
        layer_data: dict,
    ) -> float:
        """
        Calculate the effective scale factor from layer data.

        Args:
            layer_data: Layer data with mechanism configuration

        Returns:
            Scale factor (default 1.0)

        Time Complexity: O(1)
        """
        return layer_data.get("scale", 1.0)

    def calculate_rotation_from_key_points(
        self,
        layer_data: dict,
    ) -> float:
        """
        Calculate the effective rotation angle from layer data.

        Args:
            layer_data: Layer data with mechanism configuration

        Returns:
            Rotation angle in radians (default 0.0)

        Time Complexity: O(1)
        """
        return layer_data.get("rotation", 0.0)

    def transform_point(
        self,
        point: np.ndarray,
        layer_data: dict,
    ) -> QPointF | None:
        """
        Transform a single point from mechanism to scene coordinates.

        Args:
            point: Point in mechanism coordinates
            layer_data: Layer data with mechanism configuration

        Returns:
            Point in scene coordinates or None

        Time Complexity: O(1)
        """
        transform_func = self.get_scene_transform_function(layer_data)
        if transform_func:
            return transform_func(point)
        return None

    def inverse_transform_point(
        self,
        point: QPointF,
        layer_data: dict,
    ) -> np.ndarray | None:
        """
        Transform a single point from scene to mechanism coordinates.

        Args:
            point: Point in scene coordinates
            layer_data: Layer data with mechanism configuration

        Returns:
            Point in mechanism coordinates or None

        Time Complexity: O(1)
        """
        inverse_func = self.get_inverse_scene_transform_function(layer_data)
        if inverse_func:
            return inverse_func(point)
        return None
