"""
Motion Path Generator - Domain Layer

Generates motion paths for skeleton joints based on mechanism calculations.
Pure domain logic with no Qt dependencies except QPainterPath for path representation.

Design Pattern: Domain Service (DDD)
Architecture: Hexagonal - Domain Core
"""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QPainterPath


class MotionPathGenerator:
    """
    Generates motion paths for joint animation from mechanism calculations.

    This is pure domain logic that computes the path a joint will follow
    based on mechanism kinematics.
    """

    DEFAULT_RESOLUTION = 180  # Points per full rotation

    def __init__(self, resolution: int = DEFAULT_RESOLUTION) -> None:
        """
        Initialize generator.

        Args:
            resolution: Number of points for path generation (default 180)
        """
        self._resolution = resolution

    def generate_joint_motion_path(
        self,
        layer_data: dict[str, Any],
        joint_id: str,
        calculate_output_fn: Callable[[str, dict, float, dict], Any],
    ) -> "QPainterPath | None":
        """
        Generate a motion path for a skeleton joint using mechanism calculations.

        Args:
            layer_data: Mechanism layer data containing type, params
            joint_id: ID of the joint to generate path for (for logging/debugging)
            calculate_output_fn: Function to calculate mechanism output position
                Signature: (mech_type, params, time, layer_data) -> QPointF | None

        Returns:
            QPainterPath representing the joint's motion, or None if generation fails
        """
        from PyQt6.QtGui import QPainterPath

        motion_path = QPainterPath()
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})

        try:
            for i in range(self._resolution + 1):
                # Calculate angle for this point (full rotation)
                angle = (i / self._resolution) * 2 * math.pi

                # Calculate mechanism output position
                joint_pos = calculate_output_fn(mech_type, params, angle, layer_data)

                if joint_pos:
                    if i == 0:
                        motion_path.moveTo(joint_pos)
                    else:
                        motion_path.lineTo(joint_pos)
                else:
                    # Failed to calculate position - invalid path
                    return None

            return motion_path

        except Exception:
            return None

    def generate_sampled_positions(
        self,
        layer_data: dict[str, Any],
        calculate_output_fn: Callable[[str, dict, float, dict], Any],
        num_samples: int | None = None,
    ) -> list[tuple[float, float]]:
        """
        Generate sampled positions for mechanism output.

        Args:
            layer_data: Mechanism layer data
            calculate_output_fn: Function to calculate output
            num_samples: Number of samples (defaults to resolution)

        Returns:
            List of (x, y) tuples representing sampled positions
        """
        samples = num_samples or self._resolution
        positions: list[tuple[float, float]] = []
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})

        try:
            for i in range(samples):
                angle = (i / samples) * 2 * math.pi
                pos = calculate_output_fn(mech_type, params, angle, layer_data)
                if pos:
                    positions.append((pos.x(), pos.y()))
        except Exception:
            pass

        return positions


# Singleton instance
_default_generator: MotionPathGenerator | None = None


def get_motion_path_generator() -> MotionPathGenerator:
    """Get or create the default motion path generator."""
    global _default_generator
    if _default_generator is None:
        _default_generator = MotionPathGenerator()
    return _default_generator
