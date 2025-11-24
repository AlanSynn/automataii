"""Protocol for mechanism visual rendering.

Defines Strategy Pattern interface for rendering different mechanism types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from PyQt6.QtWidgets import QGraphicsItem

__all__ = ["RenderConfig", "MechanismVisualRendererProtocol"]


@dataclass(frozen=True)
class RenderConfig:
    """Configuration for mechanism visual rendering.

    Attributes:
        show_pivots: Whether to render pivot points
        show_joints: Whether to render joint markers
        show_paths: Whether to render motion paths
        pivot_color: Color for pivot markers (Qt color name)
        joint_color: Color for joint markers (Qt color name)
        path_color: Color for path lines (Qt color name)
        line_width: Width of rendered lines
        scale_factor: Scaling factor for rendering
    """

    show_pivots: bool = True
    show_joints: bool = True
    show_paths: bool = True
    pivot_color: str = "#FF0000"
    joint_color: str = "#00FF00"
    path_color: str = "#0000FF"
    line_width: float = 2.0
    scale_factor: float = 1.0


class MechanismVisualRendererProtocol(Protocol):
    """Protocol for mechanism-specific visual rendering.

    Strategy Pattern interface enabling extensible mechanism type support.
    Each mechanism type (fourbar, cam, gear, etc.) implements this protocol.
    """

    def render(
        self,
        graphics_data: dict[str, Any],
        config: RenderConfig,
    ) -> list[QGraphicsItem]:
        """Render mechanism graphics items.

        Args:
            graphics_data: Mechanism-specific graphics data containing:
                - key_points: dict of named points (pivots, joints, etc.)
                - full_simulation_data: frame-by-frame position data
                - transform_params: coordinate transformation parameters
                - mechanism_type: type identifier
            config: Rendering configuration

        Returns:
            List of QGraphicsItem objects ready to add to scene

        Raises:
            ValueError: If graphics_data is malformed

        Complexity: O(N) where N = number of path points
        """
        ...
