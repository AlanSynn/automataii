"""
Mechanism Preview Renderer - Preview rendering for mechanism recommendations.

Extracted from MechanismPreviewWidget. Handles rendering mechanism
structures and path comparisons for recommendation dialogs.

Design Pattern: Renderer (preview generation)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QColor, QPen

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene


class MechanismPreviewRenderer:
    """
    Renders mechanism previews for recommendation dialogs.

    Responsibilities:
    - Render path comparisons (target vs mechanism path)
    - Render 4-bar linkage structure
    - Render cam-follower mechanism
    - Render gear mechanisms

    Time Complexity: O(p) where p = number of path points
    """

    # Visual settings
    TARGET_PATH_COLOR = QColor(100, 149, 237)  # Cornflower blue
    MECHANISM_PATH_COLOR = QColor(50, 205, 50)  # Lime green
    STRUCTURE_COLOR = QColor(70, 70, 70)
    JOINT_COLOR = QColor(255, 100, 100)

    PATH_WIDTH = 2.0
    LINK_WIDTH = 3.0
    JOINT_RADIUS = 5.0

    def __init__(self) -> None:
        """Initialize renderer."""
        self._scene: QGraphicsScene | None = None

    def configure(self, scene: QGraphicsScene) -> None:
        """Configure renderer with graphics scene."""
        self._scene = scene

    def render_path_comparison(
        self,
        bounds: QRectF,
        target_path: list[tuple[float, float]] | None,
        mechanism_path: list[tuple[float, float]] | None,
    ) -> None:
        """
        Render target path vs mechanism path comparison.

        Args:
            bounds: Bounding rectangle for scaling
            target_path: Target path points
            mechanism_path: Generated mechanism path points
        """
        if not self._scene:
            return

        # Clear existing items
        self._scene.clear()

        if target_path:
            self._draw_path(
                target_path,
                self.TARGET_PATH_COLOR,
                self.PATH_WIDTH,
                bounds,
            )

        if mechanism_path:
            self._draw_path(
                mechanism_path,
                self.MECHANISM_PATH_COLOR,
                self.PATH_WIDTH,
                bounds,
            )

    def render_4bar_structure(
        self,
        positions: dict[str, tuple[float, float]],
        transform: Callable[[float, float], tuple[float, float]] | None = None,
    ) -> None:
        """
        Render 4-bar linkage structure.

        Args:
            positions: Joint positions (O0, O1, A, B)
            transform: Optional coordinate transform function
        """
        if not self._scene:
            return

        # Get positions
        O0 = positions.get("O0", (0, 0))
        O1 = positions.get("O1", (100, 0))
        A = positions.get("A", (30, -50))
        B = positions.get("B", (70, -50))

        if transform:
            O0 = transform(*O0)
            O1 = transform(*O1)
            A = transform(*A)
            B = transform(*B)

        pen = QPen(self.STRUCTURE_COLOR, self.LINK_WIDTH)

        # Draw links
        self._scene.addLine(O0[0], O0[1], A[0], A[1], pen)  # Crank
        self._scene.addLine(A[0], A[1], B[0], B[1], pen)  # Coupler
        self._scene.addLine(B[0], B[1], O1[0], O1[1], pen)  # Rocker
        self._scene.addLine(O0[0], O0[1], O1[0], O1[1], QPen(QColor(100, 100, 100), 1))  # Ground

        # Draw joints
        joint_pen = QPen(self.JOINT_COLOR, 1)
        joint_brush = QBrush(self.JOINT_COLOR)
        r = self.JOINT_RADIUS

        for pos in [O0, O1, A, B]:
            self._scene.addEllipse(pos[0] - r, pos[1] - r, r * 2, r * 2, joint_pen, joint_brush)

    def render_cam_follower(
        self,
        center: tuple[float, float],
        base_radius: float,
        follower_pos: tuple[float, float],
        cam_profile: list[tuple[float, float]] | None = None,
        transform: Callable[[float, float], tuple[float, float]] | None = None,
    ) -> None:
        """
        Render cam-follower mechanism.

        Args:
            center: Cam center position
            base_radius: Base circle radius
            follower_pos: Follower position
            cam_profile: Optional cam profile points
            transform: Optional coordinate transform function
        """
        if not self._scene:
            return

        if transform:
            original_center = center
            center = transform(*center)
            follower_pos = transform(*follower_pos)
            radius_basis = transform(original_center[0] + base_radius, original_center[1])
            transformed_radius = math.hypot(
                radius_basis[0] - center[0], radius_basis[1] - center[1]
            )
            if math.isfinite(transformed_radius) and transformed_radius > 0.0:
                base_radius = transformed_radius

        # Draw cam base circle
        cam_pen = QPen(QColor(70, 130, 180), 2)
        self._scene.addEllipse(
            center[0] - base_radius,
            center[1] - base_radius,
            base_radius * 2,
            base_radius * 2,
            cam_pen,
        )

        # Draw cam profile if provided
        if cam_profile and len(cam_profile) > 2:
            profile_pen = QPen(QColor(70, 130, 180), 2)
            for i in range(len(cam_profile) - 1):
                p1 = cam_profile[i]
                p2 = cam_profile[i + 1]
                if transform:
                    p1 = transform(*p1)
                    p2 = transform(*p2)
                self._scene.addLine(p1[0], p1[1], p2[0], p2[1], profile_pen)

        # Draw follower
        follower_pen = QPen(QColor(220, 20, 60), 2)
        follower_r = 8
        self._scene.addEllipse(
            follower_pos[0] - follower_r,
            follower_pos[1] - follower_r,
            follower_r * 2,
            follower_r * 2,
            follower_pen,
            QBrush(QColor(220, 20, 60, 100)),
        )

        # Draw follower rod
        self._scene.addLine(
            follower_pos[0],
            follower_pos[1] + follower_r,
            follower_pos[0],
            follower_pos[1] + 50,
            QPen(QColor(80, 80, 80), 3),
        )

    def render_gear_pair(
        self,
        center1: tuple[float, float],
        radius1: float,
        center2: tuple[float, float],
        radius2: float,
        transform: Callable[[float, float], tuple[float, float]] | None = None,
    ) -> None:
        """
        Render gear pair.

        Args:
            center1: First gear center
            radius1: First gear radius
            center2: Second gear center
            radius2: Second gear radius
            transform: Optional coordinate transform function
        """
        if not self._scene:
            return

        if transform:
            center1 = transform(*center1)
            center2 = transform(*center2)

        # Draw gear 1
        gear1_pen = QPen(QColor(70, 130, 180), 2)
        self._scene.addEllipse(
            center1[0] - radius1,
            center1[1] - radius1,
            radius1 * 2,
            radius1 * 2,
            gear1_pen,
            QBrush(QColor(70, 130, 180, 50)),
        )

        # Draw gear 2
        gear2_pen = QPen(QColor(180, 130, 70), 2)
        self._scene.addEllipse(
            center2[0] - radius2,
            center2[1] - radius2,
            radius2 * 2,
            radius2 * 2,
            gear2_pen,
            QBrush(QColor(180, 130, 70, 50)),
        )

        # Draw center points
        center_pen = QPen(QColor(50, 50, 50), 1)
        center_brush = QBrush(QColor(50, 50, 50))
        r = 3

        self._scene.addEllipse(
            center1[0] - r, center1[1] - r, r * 2, r * 2, center_pen, center_brush
        )
        self._scene.addEllipse(
            center2[0] - r, center2[1] - r, r * 2, r * 2, center_pen, center_brush
        )

    def _draw_path(
        self,
        points: list[tuple[float, float]],
        color: QColor,
        width: float,
        bounds: QRectF,
    ) -> None:
        """Draw a path as connected line segments."""
        if not self._scene or len(points) < 2:
            return

        # Calculate scale to fit bounds
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width_p = max_x - min_x
        height_p = max_y - min_y

        if width_p < 1 or height_p < 1:
            return

        scale = min(
            bounds.width() * 0.9 / width_p,
            bounds.height() * 0.9 / height_p,
        )

        offset_x = bounds.center().x() - (min_x + max_x) / 2 * scale
        offset_y = bounds.center().y() - (min_y + max_y) / 2 * scale

        pen = QPen(color, width)

        for i in range(len(points) - 1):
            x1 = points[i][0] * scale + offset_x
            y1 = points[i][1] * scale + offset_y
            x2 = points[i + 1][0] * scale + offset_x
            y2 = points[i + 1][1] * scale + offset_y
            self._scene.addLine(x1, y1, x2, y2, pen)

    def clear(self) -> None:
        """Clear all rendered items."""
        if self._scene:
            self._scene.clear()
