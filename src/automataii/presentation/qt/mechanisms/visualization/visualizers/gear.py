"""
Gear mechanism visualizer implementation.

Structure:
- Gear 1: Driver gear (input)
- Gear 2: Driven gear (output)
- Teeth on each gear
- Tracking point on gear surface (output)
"""

import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPolygonItem,
)

from automataii.shared.physical_kit import (
    gear_center_distance,
    gear_clearance_from_params,
    physical_profile_from_params,
)

from ..base import MechanismVisualizer


class GearVisualizer(MechanismVisualizer):
    """Visualizer for gear mechanisms (simple gear pair)."""

    # Color scheme for gears
    GEAR1_COLOR = QColor("#3498db")  # Blue (driver)
    GEAR2_COLOR = QColor("#e74c3c")  # Red (driven)
    TOOTH_COLOR = QColor("#2c3e50")  # Dark (tooth outline)
    CENTER_COLOR = QColor("#f39c12")  # Orange (center)
    TRACKING_COLOR = QColor("#2ecc71")  # Green (tracking point)
    MESH_COLOR = QColor("#9b59b6")  # Purple (mesh point)

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of gear mechanism.

        Optimized: Uses QGraphicsItem rotation instead of regenerating geometry.
        """
        visual_items: list[QGraphicsItem] = []

        params = self.extract_params(mechanism_data)
        if not params:
            return visual_items
        profile = physical_profile_from_params(params)

        # Get gear parameters
        gear_data = self._get_gear_data(mechanism_data, params, profile=profile)
        if not gear_data:
            return visual_items

        g1_center, g2_center, r1, r2, teeth1, teeth2, input_angle = gear_data

        # Transform centers to scene coordinates
        g1_center_t = self.transform_point(g1_center)
        g2_center_t = self.transform_point(g2_center)

        # Create gear 1 (driver)
        # Create at (0,0) then move and rotate
        gear1_polygon = self._create_gear_polygon(QPointF(0, 0), r1, teeth1, 0, self.GEAR1_COLOR)
        gear1_polygon.setPos(g1_center_t)
        gear1_polygon.setRotation(math.degrees(input_angle))
        gear1_polygon.setZValue(self.config.z_index_base)
        visual_items.append(gear1_polygon)

        # Create gear 2 (driven)
        gear2_angle = -input_angle * (r1 / r2) if r2 > 0 else 0
        phase_offset = math.pi / teeth2 if teeth2 > 0 else 0

        gear2_polygon = self._create_gear_polygon(
            QPointF(0, 0), r2, teeth2, phase_offset, self.GEAR2_COLOR
        )
        gear2_polygon.setPos(g2_center_t)
        gear2_polygon.setRotation(math.degrees(gear2_angle))
        gear2_polygon.setZValue(self.config.z_index_base)
        visual_items.append(gear2_polygon)

        # Create center pivots
        for center, color in [(g1_center_t, self.CENTER_COLOR), (g2_center_t, self.CENTER_COLOR)]:
            pivot = QGraphicsEllipseItem(-6, -6, 12, 12)
            pivot.setPos(center)
            pivot.setPen(QPen(color.darker(150), 2))
            pivot.setBrush(QBrush(color))
            pivot.setZValue(self.config.z_index_pivot)
            visual_items.append(pivot)

        # Create tracking point on gear 1 surface
        # Parent it to gear 1 or calculate manually?
        # Current architecture returns flat list, so calculate position.
        # To optimize, we could make it a child item, but sticking to flat list for compatibility.
        tracking_pos = self._calculate_tracking_point(g1_center, r1, input_angle)
        tracking_t = self.transform_point(tracking_pos)
        tracking = QGraphicsEllipseItem(-5, -5, 10, 10)
        tracking.setPos(tracking_t)
        tracking.setPen(QPen(self.TRACKING_COLOR.darker(150), 2))
        tracking.setBrush(QBrush(self.TRACKING_COLOR))
        tracking.setZValue(self.config.z_index_pivot + 1)
        tracking.setToolTip("Tracking Point (Output)")
        visual_items.append(tracking)

        # Create mesh point indicator
        mesh_pos = self._calculate_mesh_point(g1_center, g2_center, r1, r2)
        mesh_t = self.transform_point(mesh_pos)
        mesh = QGraphicsEllipseItem(-4, -4, 8, 8)
        mesh.setPos(mesh_t)
        mesh.setPen(QPen(self.MESH_COLOR.darker(150), 2))
        mesh.setBrush(QBrush(self.MESH_COLOR))
        mesh.setZValue(self.config.z_index_pivot + 2)
        mesh.setToolTip("Mesh Point")
        visual_items.append(mesh)

        return visual_items

    def update_visuals(
        self, visual_items: list[QGraphicsItem], mechanism_data: dict[str, Any]
    ) -> None:
        """Update existing gear visuals with new mechanism state.

        Optimized: Updates rotation/position instead of regenerating geometry.
        """
        if len(visual_items) < 6:
            return

        params = self.extract_params(mechanism_data)
        profile = physical_profile_from_params(params)
        gear_data = self._get_gear_data(mechanism_data, params, profile=profile)
        if not gear_data:
            return

        g1_center, g2_center, r1, r2, teeth1, teeth2, input_angle = gear_data

        # Transform centers
        g1_center_t = self.transform_point(g1_center)
        g2_center_t = self.transform_point(g2_center)

        # Update gear 1 polygon (Item 0)
        if isinstance(visual_items[0], QGraphicsPolygonItem):
            visual_items[0].setPos(g1_center_t)
            visual_items[0].setRotation(math.degrees(input_angle))

        # Update gear 2 polygon (Item 1)
        if isinstance(visual_items[1], QGraphicsPolygonItem):
            gear2_angle = -input_angle * (r1 / r2) if r2 > 0 else 0
            visual_items[1].setPos(g2_center_t)
            # Note: Initial phase offset was baked into the polygon geometry or rotation base
            # If we baked it into geometry (in create_visuals), we just add delta rotation.
            # But here we construct absolute rotation.
            # In create_visuals, we passed phase_offset as initial angle to _create_gear_polygon.
            # So the polygon geometry is "at phase offset".
            # We just need to rotate by the motion angle.
            visual_items[1].setRotation(math.degrees(gear2_angle))

        # Update center pivots (Item 2, 3)
        if isinstance(visual_items[2], QGraphicsEllipseItem):
            visual_items[2].setPos(g1_center_t)
        if isinstance(visual_items[3], QGraphicsEllipseItem):
            visual_items[3].setPos(g2_center_t)

        # Update tracking point (Item 4)
        if isinstance(visual_items[4], QGraphicsEllipseItem):
            tracking_pos = self._calculate_tracking_point(g1_center, r1, input_angle)
            tracking_t = self.transform_point(tracking_pos)
            visual_items[4].setPos(tracking_t)

        # Update mesh point (Item 5)
        if isinstance(visual_items[5], QGraphicsEllipseItem):
            mesh_pos = self._calculate_mesh_point(g1_center, g2_center, r1, r2)
            mesh_t = self.transform_point(mesh_pos)
            visual_items[5].setPos(mesh_t)

    def _get_gear_data(
        self,
        mechanism_data: dict[str, Any],
        params: dict[str, Any],
        *,
        profile: Any | None = None,
    ) -> tuple | None:
        """Extract gear data from mechanism_data."""
        if profile is None:
            profile = physical_profile_from_params(params)

        # Get centers
        key_points = mechanism_data.get("key_points", {})

        if "gear1_center" in key_points:
            g1_center = np.array(key_points["gear1_center"])
        elif "center_x" in params:
            g1_center = np.array([params.get("center_x", 0), params.get("center_y", 0)])
        else:
            g1_center = np.array([0.0, 0.0])

        if "gear2_center" in key_points:
            g2_center = np.array(key_points["gear2_center"])
        else:
            # Calculate gear 2 center based on gear 1 and radii
            r1 = params.get("r1", params.get("gear1_radius", 50.0))
            r2 = params.get("r2", params.get("gear2_radius", 75.0))
            # Default: gear 2 to the right of gear 1
            clearance = gear_clearance_from_params(params, profile=profile)
            distance = gear_center_distance(r1, r2, clearance, profile=profile)
            g2_center = np.array([g1_center[0] + distance, g1_center[1]])

        # Get radii
        r1 = params.get("r1", params.get("gear1_radius", 50.0))
        r2 = params.get("r2", params.get("gear2_radius", 75.0))

        # Get teeth count
        teeth1 = int(params.get("gear1_teeth", 12))
        teeth2 = int(params.get("gear2_teeth", 18))

        # Get input angle (in radians)
        input_angle = params.get("input_angle", 0.0)
        if abs(input_angle) > 2 * math.pi:
            # Assume degrees if > 2π
            input_angle = math.radians(input_angle)

        return g1_center, g2_center, r1, r2, teeth1, teeth2, input_angle

    def _create_gear_polygon(
        self,
        center: QPointF,
        radius: float,
        num_teeth: int,
        angle: float,
        color: QColor,
    ) -> QGraphicsPolygonItem:
        """Create a gear polygon with teeth."""
        points = self._generate_gear_points(center, radius, num_teeth, angle)
        polygon = QGraphicsPolygonItem(QPolygonF(points))
        polygon.setPen(QPen(self.TOOTH_COLOR, 2))
        polygon.setBrush(QBrush(color.lighter(120)))
        return polygon

    def _generate_gear_points(
        self,
        center: QPointF,
        radius: float,
        num_teeth: int,
        angle: float,
    ) -> list[QPointF]:
        """Generate points for gear polygon with teeth."""
        points: list[QPointF] = []

        if num_teeth < 3:
            num_teeth = 12  # Minimum teeth

        # Tooth dimensions
        tooth_height = radius * 0.15
        outer_radius = radius + tooth_height / 2
        inner_radius = radius - tooth_height / 2

        # Angle per tooth
        tooth_angle = 2 * math.pi / num_teeth

        for i in range(num_teeth):
            base_angle = angle + i * tooth_angle

            # Each tooth has 4 points: inner-start, outer-start, outer-end, inner-end
            angles = [
                base_angle,  # Inner start
                base_angle + tooth_angle * 0.2,  # Outer start
                base_angle + tooth_angle * 0.5,  # Outer end
                base_angle + tooth_angle * 0.7,  # Inner end
            ]
            radii = [inner_radius, outer_radius, outer_radius, inner_radius]

            for a, r in zip(angles, radii, strict=False):
                x = center.x() + r * math.cos(a)
                y = center.y() + r * math.sin(a)
                points.append(QPointF(x, y))

        return points

    @staticmethod
    def _calculate_tracking_point(center: np.ndarray, radius: float, angle: float) -> np.ndarray:
        """Calculate tracking point position on gear surface."""
        return np.array(
            [
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle),
            ]
        )

    @staticmethod
    def _calculate_mesh_point(
        g1_center: np.ndarray,
        g2_center: np.ndarray,
        r1: float,
        r2: float,
    ) -> np.ndarray:
        """Calculate the mesh point where gears meet."""
        # Vector from g1 to g2
        dx = g2_center[0] - g1_center[0]
        dy = g2_center[1] - g1_center[1]
        dist = math.hypot(dx, dy)

        if dist < 1e-6:
            return g1_center.copy()

        # Mesh point is at r1 distance from g1 center towards g2
        ratio = r1 / dist
        return np.array(
            [
                g1_center[0] + dx * ratio,
                g1_center[1] + dy * ratio,
            ]
        )
