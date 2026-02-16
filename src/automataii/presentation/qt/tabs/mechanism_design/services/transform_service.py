"""
Transform Service for coordinate transformations between mechanism and scene space.

Extracted from MechanismDesignTab as part of god class decomposition.
Cohesion score: 0.340 (highest in the codebase).
"""

from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF

from automataii.presentation.qt.utils import qpainterpath_to_numpy_array


class TransformService:
    """
    Handles coordinate transformations between mechanism space and scene space.

    This service provides pure functions for transforming coordinates using
    the recommendation system's transform parameters. It ensures mechanism
    animations match the recommended mechanism orientation and scale.
    """

    def get_scene_transform(
        self, layer_data: dict[str, Any]
    ) -> Callable[[np.ndarray], QPointF] | None:
        """
        Creates coordinate transformation from mechanism space to scene space.

        Uses the recommendation system's transform_params to ensure mechanism
        animations match the recommended mechanism orientation and scale.

        Args:
            layer_data: Layer data containing transform_params and generated_path

        Returns:
            Transform function or None if transform cannot be created
        """
        transform_params = layer_data.get("transform_params")
        target_path = layer_data.get("generated_path")

        if not transform_params or not target_path:
            # Fallback: simple centering
            scene_center = QPointF(400, 300)
            return (
                lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                if len(p) == 2
                else scene_center
            )

        try:
            # Extract transformation parameters
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            # Validate scale
            if np.isclose(scale, 0) or scale < 1e-6 or scale > 1e6:
                scene_center = QPointF(400, 300)
                return (
                    lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                    if len(p) == 2
                    else scene_center
                )

            # Validate center
            if np.any(np.abs(center) > 1e6):
                scene_center = QPointF(400, 300)
                return (
                    lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                    if len(p) == 2
                    else scene_center
                )

            # Create rotation matrix
            rotation_matrix = np.array(
                [
                    [np.cos(rotation_angle), -np.sin(rotation_angle)],
                    [np.sin(rotation_angle), np.cos(rotation_angle)],
                ]
            )

            # Get user path bounds for mapping to scene space
            try:
                user_path_np = qpainterpath_to_numpy_array(target_path)
            except Exception:
                user_path_np = None

            if user_path_np is None or len(user_path_np) == 0:
                scene_center = QPointF(400, 300)
                return (
                    lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                    if len(p) == 2
                    else scene_center
                )

            # Calculate user path properties for mapping
            user_center = np.mean(user_path_np, axis=0)
            user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 100.0

            # Validate user_scale
            if user_scale < 10 or user_scale > 10000:
                user_scale = np.clip(user_scale, 50, 1000)

            def to_scene_coords(p_orig: np.ndarray) -> QPointF:
                """
                Apply transformation: mechanism space -> scene space.

                Steps:
                1. Center the point (subtract mechanism center)
                2. Scale down to normalized space
                3. Apply rotation
                4. Map to user path space
                """
                if p_orig is None or len(p_orig) != 2:
                    return QPointF(user_center[0], user_center[1])

                try:
                    # Validate input point
                    if np.any(np.abs(p_orig) > 1e6):
                        return QPointF(user_center[0], user_center[1])

                    # Apply transformation
                    p_centered = p_orig - center

                    if np.any(np.abs(p_centered) > 1e6):
                        p_centered = np.clip(p_centered, -1e4, 1e4)

                    p_scaled = p_centered / scale

                    if np.any(np.abs(p_scaled) > 1e4):
                        p_scaled = np.clip(p_scaled, -1e3, 1e3)

                    p_rotated = p_scaled @ rotation_matrix.T

                    # Transform to user path space
                    final_point = p_rotated * user_scale + user_center

                    if np.any(np.abs(final_point) > 1e5):
                        return QPointF(user_center[0], user_center[1])

                    return QPointF(float(final_point[0]), float(final_point[1]))

                except (ValueError, TypeError, IndexError, ZeroDivisionError, OverflowError):
                    return QPointF(user_center[0], user_center[1])

            return to_scene_coords

        except (KeyError, ValueError, TypeError):
            scene_center = QPointF(400, 300)
            return (
                lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                if len(p) == 2
                else scene_center
            )

    def get_batch_scene_transform(
        self, layer_data: dict[str, Any]
    ) -> Callable[[np.ndarray], list[QPointF]] | None:
        """
        Creates a vectorized coordinate transformation function.

        Args:
            layer_data: Layer data containing transform_params

        Returns:
            Function taking (N, 2) numpy array and returning list[QPointF]
        """
        transform_params = layer_data.get("transform_params")
        target_path = layer_data.get("generated_path")

        if not transform_params or not target_path:
            scene_center = QPointF(400, 300)
            return lambda points: [
                QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y())
                for p in points
            ]

        try:
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            # Safe defaults
            if np.isclose(scale, 0) or scale < 1e-6 or scale > 1e6:
                scale = 1.0
            if np.any(np.abs(center) > 1e6):
                center = np.zeros(2)

            rotation_matrix = np.array(
                [
                    [np.cos(rotation_angle), -np.sin(rotation_angle)],
                    [np.sin(rotation_angle), np.cos(rotation_angle)],
                ]
            )

            # Get user path properties
            try:
                user_path_np = qpainterpath_to_numpy_array(target_path)
            except Exception:
                user_path_np = None

            if user_path_np is None or len(user_path_np) == 0:
                user_center = np.array([400.0, 300.0])
                user_scale = 100.0
            else:
                user_center = np.mean(user_path_np, axis=0)
                user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
                user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 100.0
                user_scale = np.clip(user_scale, 50, 1000)

            def to_scene_coords_batch(points: np.ndarray) -> list[QPointF]:
                """Vectorized transform for N points."""
                if points is None or len(points) == 0:
                    return []

                # Numpy vectorization
                # 1. Center
                p_centered = points - center

                # 2. Scale
                p_scaled = p_centered / scale

                # 3. Rotate (N,2) @ (2,2).T -> (N,2)
                p_rotated = p_scaled @ rotation_matrix.T

                # 4. Map to user space
                final_points = p_rotated * user_scale + user_center

                # Convert to QPointF list (loop is unavoidable but faster than full python math logic per point)
                # Using list comp is standard for Qt conversion
                return [QPointF(float(x), float(y)) for x, y in final_points]

            return to_scene_coords_batch

        except Exception:
            return None

    def get_inverse_scene_transform(
        self, layer_data: dict[str, Any]
    ) -> Callable[[QPointF], np.ndarray] | None:
        """
        Creates coordinate transformation from scene space to mechanism space.

        This is the exact inverse of get_scene_transform.

        Args:
            layer_data: Layer data containing transform_params and generated_path

        Returns:
            Inverse transform function or None if transform cannot be created
        """
        transform_params = layer_data.get("transform_params")
        target_path = layer_data.get("generated_path")

        if not transform_params or not target_path:
            return None

        try:
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            # Validate parameters
            if np.isclose(scale, 0) or scale < 1e-6 or scale > 1e6:
                return None

            if np.any(np.abs(center) > 1e6):
                return None

            # Rotation matrix (inverse is transpose for orthonormal)
            rotation_matrix = np.array(
                [
                    [np.cos(rotation_angle), -np.sin(rotation_angle)],
                    [np.sin(rotation_angle), np.cos(rotation_angle)],
                ]
            )

            user_path_np = qpainterpath_to_numpy_array(target_path)
            if user_path_np is None or len(user_path_np) == 0:
                return None

            user_center = np.mean(user_path_np, axis=0)
            user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 100.0

            if user_scale < 10 or user_scale > 10000:
                user_scale = np.clip(user_scale, 50, 1000)

            def to_mechanism_coords(scene_point: QPointF) -> np.ndarray:
                """
                Apply inverse transformation: scene space -> mechanism space.
                """
                try:
                    # Validate input
                    if abs(scene_point.x()) > 1e5 or abs(scene_point.y()) > 1e5:
                        scene_point = QPointF(
                            np.clip(scene_point.x(), -1e4, 1e4), np.clip(scene_point.y(), -1e4, 1e4)
                        )

                    # Inverse: g = (scene - user_center) / user_scale
                    g = np.array([scene_point.x(), scene_point.y()])
                    g = (g - user_center) / user_scale

                    if np.any(np.abs(g) > 1e3):
                        g = np.clip(g, -1e3, 1e3)

                    # Inverse rotation and scale
                    p_scaled = g @ rotation_matrix
                    p_orig = center + scale * p_scaled

                    if np.any(np.abs(p_orig) > 1e5):
                        p_orig = np.clip(p_orig, -1e4, 1e4)

                    return p_orig

                except (ValueError, TypeError, ZeroDivisionError, OverflowError):
                    return center

            return to_mechanism_coords

        except (KeyError, ValueError, TypeError):
            return None
