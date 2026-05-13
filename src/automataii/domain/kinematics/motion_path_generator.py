"""
Motion Path Generator - Domain Layer

Generates motion paths for skeleton joints based on mechanism calculations.
Pure domain logic with no Qt dependencies except QPainterPath for path representation.

Design Pattern: Domain Service (DDD)
Architecture: Hexagonal - Domain Core
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtGui import QPainterPath


class MotionPathGenerator:
    """
    Generates motion paths for joint animation from mechanism calculations.

    This is pure domain logic that computes the path a joint will follow
    based on mechanism kinematics.
    """

    DEFAULT_RESOLUTION = 180  # Points per full rotation

    @staticmethod
    def _positive_int_or_default(value: Any, default: int, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            logging.warning("Invalid %s %r, using default %s", label, value, default)
            return default
        return int(value)

    @staticmethod
    def _finite_position_tuple(pos: Any) -> tuple[float, float] | None:
        try:
            x = float(pos.x())
            y = float(pos.y())
        except (AttributeError, TypeError, ValueError):
            return None
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        return x, y

    def __init__(self, resolution: int = DEFAULT_RESOLUTION) -> None:
        """
        Initialize generator.

        Args:
            resolution: Number of points for path generation (default 180)

        Raises:
            ValueError: If resolution is less than 1
        """
        self._resolution = self._positive_int_or_default(
            resolution,
            self.DEFAULT_RESOLUTION,
            "resolution",
        )

    def generate_joint_motion_path(
        self,
        layer_data: dict[str, Any],
        joint_id: str,
        calculate_output_fn: Callable[[str, dict, float, dict], Any],
    ) -> QPainterPath | None:
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
        if not isinstance(mech_type, str):
            return None
        if not isinstance(params, dict):
            params = {}

        try:
            for i in range(self._resolution + 1):
                # Calculate angle for this point (full rotation)
                angle = (i / self._resolution) * 2 * math.pi

                # Calculate mechanism output position
                joint_pos = calculate_output_fn(mech_type, params, angle, layer_data)

                if joint_pos is not None and self._finite_position_tuple(joint_pos) is not None:
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
        samples = (
            self._positive_int_or_default(num_samples, self._resolution, "num_samples")
            if num_samples is not None
            else self._resolution
        )
        positions: list[tuple[float, float]] = []
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})
        if not isinstance(mech_type, str):
            return positions
        if not isinstance(params, dict):
            params = {}

        try:
            for i in range(samples):
                angle = (i / samples) * 2 * math.pi
                pos = calculate_output_fn(mech_type, params, angle, layer_data)
                point = self._finite_position_tuple(pos) if pos is not None else None
                if point is not None:
                    positions.append(point)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return positions


# Singleton instance
_default_generator: MotionPathGenerator | None = None


def get_motion_path_generator() -> MotionPathGenerator:
    """Get or create the default motion path generator."""
    global _default_generator
    if _default_generator is None:
        _default_generator = MotionPathGenerator()
    return _default_generator
