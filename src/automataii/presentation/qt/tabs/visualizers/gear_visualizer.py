"""
Gear Visualizer - Visual representation for gear and planetary gear mechanisms.

Extracted from MechanismVisualsFactory to support polymorphic dispatch.
Handles creation and update of gear mechanism visuals.

Design Pattern: Strategy (implements MechanismVisualizerProtocol)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QLineF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
)

from automataii.shared.physical_kit import (
    gear_center_distance,
    gear_clearance_from_params,
    physical_profile_from_params,
)

from .protocol import BaseMechanismVisualizer

if TYPE_CHECKING:
    from PyQt6.QtCore import QPointF


class GearVisualizer(BaseMechanismVisualizer):
    """Visualizer for gear train mechanisms.

    Creates visual representation of two meshing gears:
    - Driver gear (blue)
    - Driven gear (green)
    - Rotation indicators
    - Center pivots
    """

    @property
    def mechanism_type(self) -> str:
        return "gear"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation of gear train mechanism.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state
            transform_function: Optional coordinate transform function
            **kwargs: Additional arguments

        Returns:
            List of QGraphicsItem objects representing the gear mechanism
        """
        to_scene_coords = self._get_transform_function(mechanism_data, transform_function)
        params = mechanism_data.get("params", {})
        profile = physical_profile_from_params(params)

        if not to_scene_coords or not params:
            return []

        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        # Gear centers in original coordinates - gears touching with the shared
        # physical-kit clearance contract.
        clearance = gear_clearance_from_params(params, profile=profile)
        distance = gear_center_distance(r1, r2, clearance, profile=profile)
        gear1_center_orig = np.array([0, 0])
        gear2_center_orig = np.array([distance, 0])

        # Transform to scene coordinates
        gear1_center_scene = to_scene_coords(gear1_center_orig)
        gear2_center_scene = to_scene_coords(gear2_center_orig)

        # Calculate screen radii for proper scaling
        gear1_edge_orig = gear1_center_orig + np.array([r1, 0])
        gear2_edge_orig = gear2_center_orig + np.array([r2, 0])
        gear1_edge_scene = to_scene_coords(gear1_edge_orig)
        gear2_edge_scene = to_scene_coords(gear2_edge_orig)

        r1_screen = QLineF(gear1_center_scene, gear1_edge_scene).length()
        r2_screen = QLineF(gear2_center_scene, gear2_edge_scene).length()

        visual_items: list[QGraphicsItem] = []

        # Create gear bodies
        self._create_gear_body(
            visual_items,
            gear1_center_scene,
            r1_screen,
            QColor("#3498db"),  # Blue - driver
            "Driver Gear",
        )
        self._create_gear_body(
            visual_items,
            gear2_center_scene,
            r2_screen,
            QColor("#2ecc71"),  # Green - driven
            "Driven Gear",
        )

        # Create rotation indicators
        self._create_rotation_indicator(visual_items, gear1_center_scene, r1_screen)
        self._create_rotation_indicator(visual_items, gear2_center_scene, r2_screen)

        # Create center pivots
        self._create_center_pivot(visual_items, gear1_center_scene)
        self._create_center_pivot(visual_items, gear2_center_scene)

        # Add diagnostics overlay
        self._add_gear_diagnostics(
            visual_items,
            gear1_center_scene,
            gear2_center_scene,
            r1_screen,
            r2_screen,
            gear1_center_orig,
            gear2_center_orig,
            r1,
            r2,
            params,
        )

        return visual_items

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update gear mechanism visuals for animation frame.

        Args:
            time: Animation time in radians (0 to 2π for one cycle)
            layer_data: Layer data containing mechanism state
            visual_items: List of visual items to update
            **kwargs: Additional arguments
        """
        # Gear animation is handled by MechanismVisualAnimator
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data for gear mechanism.

        Args:
            params: Gear mechanism parameters
            **kwargs: Additional options

        Returns:
            Dictionary containing simulation results
        """
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)
        num_frames = kwargs.get("num_frames", 360)

        # Generate gear angles for full rotation
        gear1_angles = np.linspace(0, 2 * np.pi, num_frames)
        # Gear 2 rotates opposite direction with gear ratio
        gear_ratio = r1 / r2
        gear2_angles = -gear1_angles * gear_ratio

        return {
            "gear_angles": {
                "gear1_angles": gear1_angles.tolist(),
                "gear2_angles": gear2_angles.tolist(),
            },
            "r1": r1,
            "r2": r2,
        }

    def _create_gear_body(
        self,
        visual_items: list[QGraphicsItem],
        center_scene: QPointF,
        radius_screen: float,
        color: QColor,
        tooltip: str,
    ) -> None:
        """Create a gear body ellipse.

        Args:
            visual_items: List to append created items
            center_scene: Center position in scene coordinates
            radius_screen: Radius in screen units
            color: Gear color
            tooltip: Tooltip text
        """
        gear_body = self.scene.addEllipse(
            center_scene.x() - radius_screen,
            center_scene.y() - radius_screen,
            radius_screen * 2,
            radius_screen * 2,
            QPen(color, 4),
            QBrush(color.lighter(170)),
        )
        gear_body.setZValue(15)
        gear_body.setToolTip(tooltip)
        visual_items.append(gear_body)

    def _create_rotation_indicator(
        self,
        visual_items: list[QGraphicsItem],
        center_scene: QPointF,
        radius_screen: float,
    ) -> None:
        """Create rotation indicator line for a gear.

        Args:
            visual_items: List to append created items
            center_scene: Gear center in scene coordinates
            radius_screen: Gear radius in screen units
        """
        indicator_color = QColor("#ffffff")  # White
        indicator = self.scene.addLine(
            center_scene.x(),
            center_scene.y(),
            center_scene.x() + radius_screen,
            center_scene.y(),
            QPen(indicator_color, 3),
        )
        indicator.setZValue(15)
        visual_items.append(indicator)

    def _create_center_pivot(
        self,
        visual_items: list[QGraphicsItem],
        center_scene: QPointF,
    ) -> None:
        """Create center pivot marker for a gear.

        Args:
            visual_items: List to append created items
            center_scene: Gear center in scene coordinates
        """
        pivot_color = QColor("#f39c12")  # Orange
        pivot = self.scene.addEllipse(
            center_scene.x() - 8,
            center_scene.y() - 8,
            16,
            16,
            QPen(pivot_color.darker(150), 3),
            QBrush(pivot_color),
        )
        pivot.setZValue(20)
        visual_items.append(pivot)

    def _add_gear_diagnostics(
        self,
        visual_items: list[QGraphicsItem],
        gear1_center_scene: QPointF,
        gear2_center_scene: QPointF,
        r1_screen: float,
        r2_screen: float,
        gear1_center_orig: np.ndarray,
        gear2_center_orig: np.ndarray,
        r1: float,
        r2: float,
        params: dict[str, Any],
    ) -> None:
        """Add diagnostic overlays for gear mechanism.

        Includes pitch circles and center distance check.

        Args:
            visual_items: List to append created items
            gear1_center_scene: Gear 1 center in scene coordinates
            gear2_center_scene: Gear 2 center in scene coordinates
            r1_screen: Gear 1 radius in screen units
            r2_screen: Gear 2 radius in screen units
            gear1_center_orig: Gear 1 center in original coordinates
            gear2_center_orig: Gear 2 center in original coordinates
            r1: Gear 1 radius in original units
            r2: Gear 2 radius in original units
        """
        try:
            profile = physical_profile_from_params(params)
            dashed = QPen(QColor("#7f8c8d"), 1, Qt.PenStyle.DashLine)

            # Pitch circles
            pc1 = self.scene.addEllipse(
                gear1_center_scene.x() - r1_screen,
                gear1_center_scene.y() - r1_screen,
                r1_screen * 2,
                r1_screen * 2,
                dashed,
            )
            pc1.setZValue(12)
            visual_items.append(pc1)

            pc2 = self.scene.addEllipse(
                gear2_center_scene.x() - r2_screen,
                gear2_center_scene.y() - r2_screen,
                r2_screen * 2,
                r2_screen * 2,
                dashed,
            )
            pc2.setZValue(12)
            visual_items.append(pc2)

            # Center distance check
            d_orig = float(np.linalg.norm(gear2_center_orig - gear1_center_orig))
            desired = gear_center_distance(
                r1,
                r2,
                gear_clearance_from_params(params, profile=profile),
                profile=profile,
            )
            mismatch = abs(d_orig - desired)

            if mismatch > 0.5:
                warn = self.scene.addText(f"Center distance off by {mismatch:.1f}")
                warn.setDefaultTextColor(QColor("#e74c3c"))
                warn.setPos(
                    (gear1_center_scene.x() + gear2_center_scene.x()) / 2.0,
                    gear1_center_scene.y() - 20,
                )
                warn.setZValue(30)
                visual_items.append(warn)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)


class PlanetaryGearVisualizer(BaseMechanismVisualizer):
    """Visualizer for planetary gear mechanisms.

    Creates visual representation of:
    - Sun gear (stationary, gray)
    - Planet gear (orbiting, orange)
    - Carrier arm with tracking point
    - Center markers
    """

    @property
    def mechanism_type(self) -> str:
        return "planetary_gear"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation of planetary gear mechanism.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state
            transform_function: Optional coordinate transform function
            **kwargs: Additional arguments

        Returns:
            List of QGraphicsItem objects representing the planetary gear
        """
        to_scene_coords = self._get_transform_function(mechanism_data, transform_function)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        # Get initial positions from simulation or calculate fallback
        sun_center_orig, planet_center_orig, tracking_point_orig = self._get_initial_positions(
            mechanism_data,
            r_sun,
            r_planet,
            arm_length,
        )

        # Transform to scene coordinates
        sun_center_scene = to_scene_coords(sun_center_orig)
        planet_center_scene = to_scene_coords(planet_center_orig)
        tracking_point_scene = to_scene_coords(tracking_point_orig)

        # Calculate screen radii for proper scaling
        sun_edge_orig = sun_center_orig + np.array([r_sun, 0])
        planet_edge_orig = planet_center_orig + np.array([r_planet, 0])
        sun_edge_scene = to_scene_coords(sun_edge_orig)
        planet_edge_scene = to_scene_coords(planet_edge_orig)

        r_sun_screen = QLineF(sun_center_scene, sun_edge_scene).length()
        r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

        visual_items: list[QGraphicsItem] = []

        # Create sun gear (stationary)
        self._create_sun_gear(visual_items, sun_center_scene, r_sun_screen)

        # Create planet gear (orbiting)
        self._create_planet_gear(visual_items, planet_center_scene, r_planet_screen)

        # Create carrier arm and tracking point
        self._create_carrier_arm(visual_items, planet_center_scene, tracking_point_scene)

        # Create center markers
        self._create_center_markers(visual_items, sun_center_scene, planet_center_scene)

        return visual_items

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update planetary gear visuals for animation frame.

        Args:
            time: Animation time in radians (0 to 2π for one cycle)
            layer_data: Layer data containing mechanism state
            visual_items: List of visual items to update
            **kwargs: Additional arguments
        """
        # Animation is handled by MechanismVisualAnimator
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data for planetary gear mechanism.

        Args:
            params: Planetary gear mechanism parameters
            **kwargs: Additional options

        Returns:
            Dictionary containing simulation results
        """
        r_sun = float(params.get("r_sun", params.get("gear1_radius", 20.0)))
        r_planet = float(params.get("r_planet", params.get("gear2_radius", 30.0)))
        arm_length = float(params.get("arm_length", 15.0))
        num_frames = kwargs.get("num_frames", 360)
        if r_planet <= 0:
            r_planet = 1.0

        if "sun_center" in params and isinstance(params["sun_center"], list | tuple):
            sun_center = np.array(params["sun_center"], dtype=float)
        elif "m_sun_x" in params and "m_sun_y" in params:
            sun_center = np.array(
                [float(params.get("m_sun_x", 0.0)), float(params.get("m_sun_y", 0.0))],
                dtype=float,
            )
        elif "sun_x" in params and "sun_y" in params:
            sun_center = np.array([float(params["sun_x"]), float(params["sun_y"])], dtype=float)
        elif "gear1_x" in params and "gear1_y" in params:
            sun_center = np.array([float(params["gear1_x"]), float(params["gear1_y"])], dtype=float)
        else:
            sun_center = np.array([0.0, 0.0], dtype=float)
        orbit_radius = r_sun + r_planet

        # Generate positions for each frame
        planet_centers = []
        tracking_points = []
        sun_angles = np.linspace(0, 2 * np.pi, num_frames)

        for angle in sun_angles:
            # Planet center orbits around sun
            planet_center = sun_center + orbit_radius * np.array([np.cos(angle), np.sin(angle)])
            planet_centers.append(planet_center.tolist())

            # Planet rotates in opposite direction
            planet_angle = -angle * (r_sun / r_planet)
            tracking_offset = arm_length * np.array([np.cos(planet_angle), np.sin(planet_angle)])
            tracking_point = planet_center + tracking_offset
            tracking_points.append(tracking_point.tolist())

        return {
            "gear_positions": {
                "sun_centers": [sun_center.tolist()] * num_frames,
                "planet_centers": planet_centers,
                "tracking_points": tracking_points,
            },
            "r_sun": r_sun,
            "r_planet": r_planet,
            "arm_length": arm_length,
        }

    def _get_initial_positions(
        self,
        mechanism_data: dict[str, Any],
        r_sun: float,
        r_planet: float,
        arm_length: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get initial positions from simulation data or calculate fallback.

        Args:
            mechanism_data: Mechanism data dictionary
            r_sun: Sun gear radius
            r_planet: Planet gear radius
            arm_length: Carrier arm length

        Returns:
            Tuple of (sun_center, planet_center, tracking_point) arrays
        """
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        gear_positions = full_sim_data.get("gear_positions", {})

        if (
            gear_positions
            and "sun_centers" in gear_positions
            and len(gear_positions["sun_centers"]) > 0
        ):
            # Use simulation data for accurate positioning
            frame_idx = 0
            sun_center = np.array(gear_positions["sun_centers"][frame_idx])
            planet_center = np.array(gear_positions["planet_centers"][frame_idx])
            tracking_point = np.array(gear_positions["tracking_points"][frame_idx])
        else:
            params = mechanism_data.get("params", {})
            key_points = mechanism_data.get("key_points", {})

            if "sun_center" in key_points:
                sun_center = np.array(key_points["sun_center"], dtype=float)
            elif "m_sun_x" in params and "m_sun_y" in params:
                sun_center = np.array(
                    [float(params.get("m_sun_x", 0.0)), float(params.get("m_sun_y", 0.0))],
                    dtype=float,
                )
            elif "sun_x" in params and "sun_y" in params:
                sun_center = np.array(
                    [float(params.get("sun_x", 0.0)), float(params.get("sun_y", 0.0))],
                    dtype=float,
                )
            elif "gear1_x" in params and "gear1_y" in params:
                sun_center = np.array(
                    [float(params.get("gear1_x", 0.0)), float(params.get("gear1_y", 0.0))],
                    dtype=float,
                )
            else:
                sun_center = np.array([0.0, 0.0], dtype=float)

            if "planet_center" in key_points:
                planet_center = np.array(key_points["planet_center"], dtype=float)
            elif "planet_x" in params and "planet_y" in params:
                planet_center = np.array(
                    [float(params.get("planet_x", 0.0)), float(params.get("planet_y", 0.0))],
                    dtype=float,
                )
            elif "gear2_x" in params and "gear2_y" in params:
                planet_center = np.array(
                    [float(params.get("gear2_x", 0.0)), float(params.get("gear2_y", 0.0))],
                    dtype=float,
                )
            else:
                planet_center = sun_center + (r_sun + r_planet) * np.array([1.0, 0.0])

            if "tracking_point" in key_points:
                tracking_point = np.array(key_points["tracking_point"], dtype=float)
            else:
                tracking_point = planet_center + arm_length * np.array([1.0, 0.0])

        return sun_center, planet_center, tracking_point

    def _create_sun_gear(
        self,
        visual_items: list[QGraphicsItem],
        sun_center_scene: QPointF,
        r_sun_screen: float,
    ) -> None:
        """Create sun gear visual (stationary).

        Args:
            visual_items: List to append created items
            sun_center_scene: Sun center in scene coordinates
            r_sun_screen: Sun radius in screen units
        """
        sun_color = QColor("#7f8c8d")  # Gray
        sun_gear = self.scene.addEllipse(
            sun_center_scene.x() - r_sun_screen,
            sun_center_scene.y() - r_sun_screen,
            r_sun_screen * 2,
            r_sun_screen * 2,
            QPen(sun_color, 4),
            QBrush(sun_color.lighter(150)),
        )
        sun_gear.setZValue(14)
        sun_gear.setToolTip("Sun Gear (Stationary)")
        visual_items.append(sun_gear)

    def _create_planet_gear(
        self,
        visual_items: list[QGraphicsItem],
        planet_center_scene: QPointF,
        r_planet_screen: float,
    ) -> None:
        """Create planet gear visual (orbiting).

        Args:
            visual_items: List to append created items
            planet_center_scene: Planet center in scene coordinates
            r_planet_screen: Planet radius in screen units
        """
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = self.scene.addEllipse(
            planet_center_scene.x() - r_planet_screen,
            planet_center_scene.y() - r_planet_screen,
            r_planet_screen * 2,
            r_planet_screen * 2,
            QPen(planet_color, 4),
            QBrush(planet_color.lighter(150)),
        )
        planet_gear.setZValue(15)
        planet_gear.setToolTip("Planet Gear (Orbiting)")
        visual_items.append(planet_gear)

    def _create_carrier_arm(
        self,
        visual_items: list[QGraphicsItem],
        planet_center_scene: QPointF,
        tracking_point_scene: QPointF,
    ) -> None:
        """Create carrier arm and tracking point visuals.

        Args:
            visual_items: List to append created items
            planet_center_scene: Planet center in scene coordinates
            tracking_point_scene: Tracking point in scene coordinates
        """
        # Carrier arm line
        arm_color = QColor("#f39c12")  # Golden
        arm_line = self.scene.addLine(
            QLineF(planet_center_scene, tracking_point_scene),
            QPen(arm_color, 3),
        )
        arm_line.setZValue(15)
        arm_line.setToolTip("Carrier Arm")
        visual_items.append(arm_line)

        # Tracking point marker
        tracking_color = QColor("#e74c3c")  # Red
        tracking_marker = self.scene.addEllipse(
            tracking_point_scene.x() - 8,
            tracking_point_scene.y() - 8,
            16,
            16,
            QPen(tracking_color, 2),
            QBrush(tracking_color),
        )
        tracking_marker.setZValue(20)
        tracking_marker.setToolTip("Tracking Point - Traces output path")
        visual_items.append(tracking_marker)

    def _create_center_markers(
        self,
        visual_items: list[QGraphicsItem],
        sun_center_scene: QPointF,
        planet_center_scene: QPointF,
    ) -> None:
        """Create center markers for sun and planet gears.

        Args:
            visual_items: List to append created items
            sun_center_scene: Sun center in scene coordinates
            planet_center_scene: Planet center in scene coordinates
        """
        center_color = QColor("#3498db")  # Blue

        # Sun center marker (larger)
        sun_marker = self.scene.addEllipse(
            sun_center_scene.x() - 6,
            sun_center_scene.y() - 6,
            12,
            12,
            QPen(center_color.darker(150), 2),
            QBrush(center_color),
        )
        sun_marker.setZValue(25)
        sun_marker.setToolTip("Sun Center - Fixed pivot")
        visual_items.append(sun_marker)

        # Planet center marker (smaller)
        planet_marker = self.scene.addEllipse(
            planet_center_scene.x() - 4,
            planet_center_scene.y() - 4,
            8,
            8,
            QPen(center_color.darker(150), 1),
            QBrush(center_color.lighter(130)),
        )
        planet_marker.setZValue(25)
        planet_marker.setToolTip("Planet Center - Orbiting pivot")
        visual_items.append(planet_marker)
