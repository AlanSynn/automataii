"""
Planetary gear mechanism visualizer implementation.

Structure:
- Sun gear: Central gear (driver)
- Planet gear(s): Orbiting gears around sun
- Carrier arm: Connects sun center to planet centers
- Ring gear (optional): Outer fixed ring
- Tracking point: On planet surface (output)

Motion:
- Sun rotation drives planet orbit and spin
- Planet spins in opposite direction: ω_planet = -ω_sun * (r_sun / r_planet)
- Carrier arm rotates with sun (simplified model)
"""

import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
)

from ..base import MechanismVisualizer


class PlanetaryGearVisualizer(MechanismVisualizer):
    """Visualizer for planetary gear mechanisms."""

    # Color scheme
    SUN_COLOR = QColor("#f1c40f")          # Yellow (sun)
    PLANET_COLOR = QColor("#3498db")       # Blue (planet)
    RING_COLOR = QColor("#7f8c8d")         # Gray (ring)
    CARRIER_COLOR = QColor("#e74c3c")      # Red (carrier arm)
    CENTER_COLOR = QColor("#f39c12")       # Orange (centers)
    TRACKING_COLOR = QColor("#2ecc71")     # Green (tracking point)
    TOOTH_COLOR = QColor("#2c3e50")        # Dark (tooth outline)

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of planetary gear mechanism.

        Visual items order:
        - Item 0: Ring gear (outer circle)
        - Item 1: Carrier arm (line from sun to planet)
        - Item 2: Sun gear (polygon with teeth)
        - Item 3: Planet gear (polygon with teeth)
        - Item 4: Sun center pivot
        - Item 5: Planet center pivot
        - Item 6: Tracking point on planet

        Returns:
            List of QGraphicsItem objects representing the planetary gear
        """
        visual_items: list[QGraphicsItem] = []

        params = self.extract_params(mechanism_data)
        if not params:
            return visual_items

        # Get planetary gear data
        gear_data = self._get_gear_data(mechanism_data, params)
        if not gear_data:
            return visual_items

        (
            sun_center,
            r_sun,
            r_planet,
            sun_teeth,
            planet_teeth,
            carrier_angle,
            sun_angle,
        ) = gear_data

        # Calculate planet center position (orbits around sun)
        planet_center = self._calculate_planet_center(sun_center, r_sun, r_planet, carrier_angle)

        # Transform to scene coordinates
        sun_center_t = self.transform_point(sun_center)
        planet_center_t = self.transform_point(planet_center)

        # Ring gear (outer boundary)
        ring_radius = r_sun + 2 * r_planet + r_planet * 0.2  # Approximate ring
        ring = QGraphicsEllipseItem(
            sun_center_t.x() - ring_radius,
            sun_center_t.y() - ring_radius,
            ring_radius * 2,
            ring_radius * 2,
        )
        ring.setPen(QPen(self.RING_COLOR.darker(120), 4))
        ring.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        ring.setZValue(self.config.z_index_base - 1)
        visual_items.append(ring)

        # Carrier arm (from sun center to planet center)
        carrier = QGraphicsLineItem(QLineF(sun_center_t, planet_center_t))
        carrier.setPen(
            QPen(self.CARRIER_COLOR, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        carrier.setZValue(self.config.z_index_base)
        visual_items.append(carrier)

        # Sun gear
        sun_polygon = self._create_gear_polygon(
            sun_center_t, r_sun, sun_teeth, sun_angle, self.SUN_COLOR
        )
        sun_polygon.setZValue(self.config.z_index_base + 1)
        visual_items.append(sun_polygon)

        # Planet gear (spins opposite to sun)
        planet_spin = -sun_angle * (r_sun / r_planet) if r_planet > 0 else 0
        planet_polygon = self._create_gear_polygon(
            planet_center_t, r_planet, planet_teeth, planet_spin, self.PLANET_COLOR
        )
        planet_polygon.setZValue(self.config.z_index_base + 2)
        visual_items.append(planet_polygon)

        # Sun center pivot
        sun_pivot = QGraphicsEllipseItem(sun_center_t.x() - 6, sun_center_t.y() - 6, 12, 12)
        sun_pivot.setPen(QPen(self.CENTER_COLOR.darker(150), 2))
        sun_pivot.setBrush(QBrush(self.CENTER_COLOR))
        sun_pivot.setZValue(self.config.z_index_pivot)
        sun_pivot.setToolTip("Sun Center")
        visual_items.append(sun_pivot)

        # Planet center pivot
        planet_pivot = QGraphicsEllipseItem(
            planet_center_t.x() - 5, planet_center_t.y() - 5, 10, 10
        )
        planet_pivot.setPen(QPen(self.PLANET_COLOR.darker(150), 2))
        planet_pivot.setBrush(QBrush(self.PLANET_COLOR.lighter(120)))
        planet_pivot.setZValue(self.config.z_index_pivot)
        planet_pivot.setToolTip("Planet Center")
        visual_items.append(planet_pivot)

        # Tracking point on planet surface (output)
        tracking_pos = self._calculate_tracking_point(
            planet_center, r_planet, planet_spin
        )
        tracking_t = self.transform_point(tracking_pos)
        tracking = QGraphicsEllipseItem(tracking_t.x() - 5, tracking_t.y() - 5, 10, 10)
        tracking.setPen(QPen(self.TRACKING_COLOR.darker(150), 2))
        tracking.setBrush(QBrush(self.TRACKING_COLOR))
        tracking.setZValue(self.config.z_index_pivot + 1)
        tracking.setToolTip("Tracking Point (Output)")
        visual_items.append(tracking)

        return visual_items

    def update_visuals(
        self, visual_items: list[QGraphicsItem], mechanism_data: dict[str, Any]
    ) -> None:
        """Update existing planetary gear visuals with new mechanism state."""
        if len(visual_items) < 7:
            return

        params = self.extract_params(mechanism_data)
        gear_data = self._get_gear_data(mechanism_data, params)
        if not gear_data:
            return

        (
            sun_center,
            r_sun,
            r_planet,
            sun_teeth,
            planet_teeth,
            carrier_angle,
            sun_angle,
        ) = gear_data

        # Calculate planet center
        planet_center = self._calculate_planet_center(sun_center, r_sun, r_planet, carrier_angle)

        # Transform to scene coordinates
        sun_center_t = self.transform_point(sun_center)
        planet_center_t = self.transform_point(planet_center)

        # Update ring gear (item 0)
        if isinstance(visual_items[0], QGraphicsEllipseItem):
            ring_radius = r_sun + 2 * r_planet + r_planet * 0.2
            visual_items[0].setRect(
                sun_center_t.x() - ring_radius,
                sun_center_t.y() - ring_radius,
                ring_radius * 2,
                ring_radius * 2,
            )

        # Update carrier arm (item 1)
        if isinstance(visual_items[1], QGraphicsLineItem):
            visual_items[1].setLine(QLineF(sun_center_t, planet_center_t))

        # Update sun gear (item 2)
        if isinstance(visual_items[2], QGraphicsPolygonItem):
            sun_points = self._generate_gear_points(sun_center_t, r_sun, sun_teeth, sun_angle)
            visual_items[2].setPolygon(QPolygonF(sun_points))

        # Update planet gear (item 3)
        if isinstance(visual_items[3], QGraphicsPolygonItem):
            planet_spin = -sun_angle * (r_sun / r_planet) if r_planet > 0 else 0
            planet_points = self._generate_gear_points(
                planet_center_t, r_planet, planet_teeth, planet_spin
            )
            visual_items[3].setPolygon(QPolygonF(planet_points))

        # Update sun center (item 4)
        if isinstance(visual_items[4], QGraphicsEllipseItem):
            visual_items[4].setRect(sun_center_t.x() - 6, sun_center_t.y() - 6, 12, 12)

        # Update planet center (item 5)
        if isinstance(visual_items[5], QGraphicsEllipseItem):
            visual_items[5].setRect(planet_center_t.x() - 5, planet_center_t.y() - 5, 10, 10)

        # Update tracking point (item 6)
        if isinstance(visual_items[6], QGraphicsEllipseItem):
            planet_spin = -sun_angle * (r_sun / r_planet) if r_planet > 0 else 0
            tracking_pos = self._calculate_tracking_point(planet_center, r_planet, planet_spin)
            tracking_t = self.transform_point(tracking_pos)
            visual_items[6].setRect(tracking_t.x() - 5, tracking_t.y() - 5, 10, 10)

    def _get_gear_data(
        self, mechanism_data: dict[str, Any], params: dict[str, Any]
    ) -> tuple | None:
        """Extract planetary gear data from mechanism_data."""
        # Get sun center
        key_points = mechanism_data.get("key_points", {})

        if "sun_center" in key_points:
            sun_center = np.array(key_points["sun_center"])
        elif "center_x" in params:
            sun_center = np.array([params.get("center_x", 0), params.get("center_y", 0)])
        else:
            sun_center = np.array([0.0, 0.0])

        # Get radii
        r_sun = params.get("r_sun", params.get("sun_radius", 40.0))
        r_planet = params.get("r_planet", params.get("planet_radius", 25.0))

        # Get teeth count
        sun_teeth = int(params.get("sun_teeth", 16))
        planet_teeth = int(params.get("planet_teeth", 10))

        # Get angles
        carrier_angle = params.get("carrier_angle", params.get("input_angle", 0.0))
        sun_angle = params.get("sun_angle", carrier_angle)  # Default: sun rotates with carrier

        # Convert to radians if needed
        if abs(carrier_angle) > 2 * math.pi:
            carrier_angle = math.radians(carrier_angle)
        if abs(sun_angle) > 2 * math.pi:
            sun_angle = math.radians(sun_angle)

        return sun_center, r_sun, r_planet, sun_teeth, planet_teeth, carrier_angle, sun_angle

    @staticmethod
    def _calculate_planet_center(
        sun_center: np.ndarray,
        r_sun: float,
        r_planet: float,
        carrier_angle: float,
    ) -> np.ndarray:
        """Calculate planet center position based on carrier angle."""
        # Planet orbits at distance r_sun + r_planet from sun center
        orbit_radius = r_sun + r_planet
        return np.array([
            sun_center[0] + orbit_radius * math.cos(carrier_angle),
            sun_center[1] + orbit_radius * math.sin(carrier_angle),
        ])

    @staticmethod
    def _calculate_tracking_point(
        planet_center: np.ndarray, r_planet: float, planet_spin: float
    ) -> np.ndarray:
        """Calculate tracking point on planet surface."""
        return np.array([
            planet_center[0] + r_planet * math.cos(planet_spin),
            planet_center[1] + r_planet * math.sin(planet_spin),
        ])

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
            num_teeth = 10

        # Tooth dimensions
        tooth_height = radius * 0.15
        outer_radius = radius + tooth_height / 2
        inner_radius = radius - tooth_height / 2

        tooth_angle = 2 * math.pi / num_teeth

        for i in range(num_teeth):
            base_angle = angle + i * tooth_angle

            angles = [
                base_angle,
                base_angle + tooth_angle * 0.2,
                base_angle + tooth_angle * 0.5,
                base_angle + tooth_angle * 0.7,
            ]
            radii = [inner_radius, outer_radius, outer_radius, inner_radius]

            for a, r in zip(angles, radii, strict=False):
                x = center.x() + r * math.cos(a)
                y = center.y() + r * math.sin(a)
                points.append(QPointF(x, y))

        return points
