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

from ..base import MechanismVisualizer


class GearVisualizer(MechanismVisualizer):
    """Visualizer for gear mechanisms (simple gear pair)."""

    # Color scheme for gears
    GEAR1_COLOR = QColor("#3498db")       # Blue (driver)
    GEAR2_COLOR = QColor("#e74c3c")       # Red (driven)
    TOOTH_COLOR = QColor("#2c3e50")       # Dark (tooth outline)
    CENTER_COLOR = QColor("#f39c12")      # Orange (center)
    TRACKING_COLOR = QColor("#2ecc71")    # Green (tracking point)
    MESH_COLOR = QColor("#9b59b6")        # Purple (mesh point)

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of gear mechanism.

        Visual items order:
        - Item 0: Gear 1 body (polygon with teeth)
        - Item 1: Gear 2 body (polygon with teeth)
        - Item 2: Gear 1 center pivot
        - Item 3: Gear 2 center pivot
        - Item 4: Tracking point on gear 1
        - Item 5: Mesh point indicator

        Returns:
            List of QGraphicsItem objects representing the gear mechanism
        """
        visual_items: list[QGraphicsItem] = []

        params = self.extract_params(mechanism_data)
        if not params:
            return visual_items

        # Get gear parameters
        gear_data = self._get_gear_data(mechanism_data, params)
        if not gear_data:
            return visual_items

        g1_center, g2_center, r1, r2, teeth1, teeth2, input_angle = gear_data

        # Transform centers to scene coordinates
        g1_center_t = self.transform_point(g1_center)
        g2_center_t = self.transform_point(g2_center)

        # Create gear 1 (driver)
        gear1_polygon = self._create_gear_polygon(
            g1_center_t, r1, teeth1, input_angle, self.GEAR1_COLOR
        )
        gear1_polygon.setZValue(self.config.z_index_base)
        visual_items.append(gear1_polygon)

        # Create gear 2 (driven)
        # Gear 2 rotates opposite direction with ratio r1/r2
        gear2_angle = -input_angle * (r1 / r2) if r2 > 0 else 0
        # Add phase offset so teeth mesh
        phase_offset = math.pi / teeth2 if teeth2 > 0 else 0
        gear2_polygon = self._create_gear_polygon(
            g2_center_t, r2, teeth2, gear2_angle + phase_offset, self.GEAR2_COLOR
        )
        gear2_polygon.setZValue(self.config.z_index_base)
        visual_items.append(gear2_polygon)

        # Create center pivots
        for center, color in [(g1_center_t, self.CENTER_COLOR), (g2_center_t, self.CENTER_COLOR)]:
            pivot = QGraphicsEllipseItem(center.x() - 6, center.y() - 6, 12, 12)
            pivot.setPen(QPen(color.darker(150), 2))
            pivot.setBrush(QBrush(color))
            pivot.setZValue(self.config.z_index_pivot)
            visual_items.append(pivot)

        # Create tracking point on gear 1 surface
        tracking_pos = self._calculate_tracking_point(g1_center, r1, input_angle)
        tracking_t = self.transform_point(tracking_pos)
        tracking = QGraphicsEllipseItem(tracking_t.x() - 5, tracking_t.y() - 5, 10, 10)
        tracking.setPen(QPen(self.TRACKING_COLOR.darker(150), 2))
        tracking.setBrush(QBrush(self.TRACKING_COLOR))
        tracking.setZValue(self.config.z_index_pivot + 1)
        tracking.setToolTip("Tracking Point (Output)")
        visual_items.append(tracking)

        # Create mesh point indicator (where gears meet)
        mesh_pos = self._calculate_mesh_point(g1_center, g2_center, r1, r2)
        mesh_t = self.transform_point(mesh_pos)
        mesh = QGraphicsEllipseItem(mesh_t.x() - 4, mesh_t.y() - 4, 8, 8)
        mesh.setPen(QPen(self.MESH_COLOR.darker(150), 2))
        mesh.setBrush(QBrush(self.MESH_COLOR))
        mesh.setZValue(self.config.z_index_pivot + 2)
        mesh.setToolTip("Mesh Point")
        visual_items.append(mesh)

        return visual_items

    def update_visuals(
        self, visual_items: list[QGraphicsItem], mechanism_data: dict[str, Any]
    ) -> None:
        """Update existing gear visuals with new mechanism state."""
        if len(visual_items) < 6:
            return

        params = self.extract_params(mechanism_data)
        gear_data = self._get_gear_data(mechanism_data, params)
        if not gear_data:
            return

        g1_center, g2_center, r1, r2, teeth1, teeth2, input_angle = gear_data

        # Transform centers
        g1_center_t = self.transform_point(g1_center)
        g2_center_t = self.transform_point(g2_center)

        # Update gear 1 polygon
        if isinstance(visual_items[0], QGraphicsPolygonItem):
            gear1_points = self._generate_gear_points(g1_center_t, r1, teeth1, input_angle)
            visual_items[0].setPolygon(QPolygonF(gear1_points))

        # Update gear 2 polygon
        if isinstance(visual_items[1], QGraphicsPolygonItem):
            gear2_angle = -input_angle * (r1 / r2) if r2 > 0 else 0
            phase_offset = math.pi / teeth2 if teeth2 > 0 else 0
            gear2_points = self._generate_gear_points(
                g2_center_t, r2, teeth2, gear2_angle + phase_offset
            )
            visual_items[1].setPolygon(QPolygonF(gear2_points))

        # Update center pivots
        if isinstance(visual_items[2], QGraphicsEllipseItem):
            visual_items[2].setRect(g1_center_t.x() - 6, g1_center_t.y() - 6, 12, 12)
        if isinstance(visual_items[3], QGraphicsEllipseItem):
            visual_items[3].setRect(g2_center_t.x() - 6, g2_center_t.y() - 6, 12, 12)

        # Update tracking point
        if isinstance(visual_items[4], QGraphicsEllipseItem):
            tracking_pos = self._calculate_tracking_point(g1_center, r1, input_angle)
            tracking_t = self.transform_point(tracking_pos)
            visual_items[4].setRect(tracking_t.x() - 5, tracking_t.y() - 5, 10, 10)

        # Update mesh point
        if isinstance(visual_items[5], QGraphicsEllipseItem):
            mesh_pos = self._calculate_mesh_point(g1_center, g2_center, r1, r2)
            mesh_t = self.transform_point(mesh_pos)
            visual_items[5].setRect(mesh_t.x() - 4, mesh_t.y() - 4, 8, 8)

    def _get_gear_data(
        self, mechanism_data: dict[str, Any], params: dict[str, Any]
    ) -> tuple | None:
        """Extract gear data from mechanism_data."""
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
            g2_center = np.array([g1_center[0] + r1 + r2, g1_center[1]])

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
                base_angle,                          # Inner start
                base_angle + tooth_angle * 0.2,      # Outer start
                base_angle + tooth_angle * 0.5,      # Outer end
                base_angle + tooth_angle * 0.7,      # Inner end
            ]
            radii = [inner_radius, outer_radius, outer_radius, inner_radius]

            for a, r in zip(angles, radii, strict=False):
                x = center.x() + r * math.cos(a)
                y = center.y() + r * math.sin(a)
                points.append(QPointF(x, y))

        return points

    @staticmethod
    def _calculate_tracking_point(
        center: np.ndarray, radius: float, angle: float
    ) -> np.ndarray:
        """Calculate tracking point position on gear surface."""
        return np.array([
            center[0] + radius * math.cos(angle),
            center[1] + radius * math.sin(angle),
        ])

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
        return np.array([
            g1_center[0] + dx * ratio,
            g1_center[1] + dy * ratio,
        ])
