"""
CAM mechanism visualizer implementation.
"""

from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
)

from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float,
    positive_finite_float,
)
from automataii.presentation.qt.tabs.cam_geometry import (
    cam_contact_local_from_profile,
    cam_follower_base_scene,
    cam_scene_unit_scale,
)

from ..base import MechanismVisualizer


class CamVisualizer(MechanismVisualizer):
    """Visualizer for CAM and follower mechanisms.

    The profile remains Foundry-compatible, while contact/follower placement uses
    the shared Mechanism Design Tab scene-vertical convention.
    """

    # Colors matching Mechanism Foundry
    CAM_COLOR = QColor(70, 130, 180)  # Steel Blue (Foundry)
    CAM_CENTER_COLOR = QColor(255, 0, 0)  # Red
    CONTACT_COLOR = QColor(220, 20, 60)  # Crimson
    FOLLOWER_COLOR = QColor(120, 120, 120)  # Gray
    ROD_COLOR = QColor(80, 80, 80)  # Dark Gray
    FOLLOWER_BASE_COLOR = QColor(100, 100, 100)  # Gray

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """Create visual representation of CAM mechanism."""
        visual_items: list[QGraphicsItem] = []
        params = self.extract_params(mechanism_data)

        if not params:
            return visual_items

        # Extract CAM parameters (matching Foundry defaults) with finite guards.
        base_radius = positive_finite_float(
            params.get("base_radius", params.get("cam_radius")),
            60.0,
        )
        cam_offset = max(
            0.0,
            finite_float(params.get("eccentricity", params.get("cam_offset")), 20.0),
        )
        follower_rod_length = positive_finite_float(
            params.get("follower_rod_length", params.get("follower_length")),
            100.0,
        )

        # Harmonic parameters (Foundry-compatible)
        cam_lobes = max(1, int(positive_finite_float(params.get("cam_lobes"), 1.0)))
        profile_harmonic = finite_float(params.get("profile_harmonic"), 0.3)

        # Apply scaling factors if available
        cam_scale_factor = positive_finite_float(mechanism_data.get("cam_scale_factor"), 1.0)
        rod_length_multiplier = positive_finite_float(
            mechanism_data.get("rod_length_multiplier"), 1.0
        )

        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_cam_offset = cam_offset * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Get CAM position - prioritize params over cam_position
        if "center_x" in params and "center_y" in params:
            cam_center = np.array(
                [
                    finite_float(params.get("center_x"), 0.0),
                    finite_float(params.get("center_y"), 0.0),
                ],
                dtype=float,
            )
        elif "cam_position" in mechanism_data and len(mechanism_data["cam_position"]) >= 2:
            cam_center = np.array(
                [
                    finite_float(mechanism_data["cam_position"][0], 0.0),
                    finite_float(mechanism_data["cam_position"][1], 0.0),
                ],
                dtype=float,
            )
        else:
            cam_center = np.array([0.0, 0.0])  # Default at origin (like Foundry)

        # Create CAM profile using harmonic formula (matches Foundry)
        cam_profile = self._create_cam_profile(
            scaled_base_radius, scaled_cam_offset, cam_lobes, profile_harmonic
        )
        cam_profile_array = np.asarray(cam_profile, dtype=float)

        # Transform to scene coordinates if transform function provided
        if self.config.transform_function:
            cam_center_scene = self.config.transform_function(cam_center)
        else:
            cam_center_scene = QPointF(cam_center[0], cam_center[1])

        # Create CAM polygon
        cam_polygon_points = []
        for point in cam_profile:
            point_offset = np.array(point) + cam_center
            if self.config.transform_function:
                scene_point = self.config.transform_function(point_offset)
            else:
                scene_point = QPointF(point_offset[0], point_offset[1])
            cam_polygon_points.append(scene_point)

        # Create CAM visual (item 0)
        cam_polygon = QPolygonF(cam_polygon_points)
        cam_item = QGraphicsPolygonItem(cam_polygon)
        cam_item.setPen(QPen(self.CAM_COLOR.darker(150), 3))
        cam_item.setBrush(QBrush(self.CAM_COLOR))
        cam_item.setZValue(self.config.z_index_base)
        visual_items.append(cam_item)

        # Contact point follows the shared Mechanism Design Tab convention:
        # local +Y support height with a scene-vertical follower rod.
        contact_local = cam_contact_local_from_profile(cam_profile_array)
        contact_pos = cam_center + contact_local
        if self.config.transform_function:
            contact_scene = self.config.transform_function(contact_pos)
        else:
            contact_scene = QPointF(contact_pos[0], contact_pos[1])

        # Create contact point visual (item 1) - Crimson
        contact_item = QGraphicsEllipseItem(contact_scene.x() - 5, contact_scene.y() - 5, 10, 10)
        contact_item.setPen(QPen(self.CONTACT_COLOR, 3))
        contact_item.setBrush(QBrush(self.CONTACT_COLOR))
        contact_item.setZValue(self.config.z_index_base + 3)
        visual_items.append(contact_item)

        # Follower end position (at contact point)
        follower_end = contact_pos.copy()

        if self.config.transform_function:
            follower_end_scene = self.config.transform_function(follower_end)
            unit_scale = cam_scene_unit_scale(self.config.transform_function)
        else:
            follower_end_scene = QPointF(follower_end[0], follower_end[1])
            unit_scale = 1.0
        follower_base_scene = cam_follower_base_scene(
            follower_end_scene,
            scaled_rod_length,
            unit_scale,
        )

        # Follower rod (item 2) - from contact to base
        rod = QGraphicsLineItem(QLineF(follower_end_scene, follower_base_scene))
        rod.setPen(QPen(self.ROD_COLOR, 6))
        rod.setZValue(self.config.z_index_base + 1)
        visual_items.append(rod)

        # Follower head (item 3) - at base position (Foundry style)
        follower_head = QGraphicsRectItem(
            follower_base_scene.x() - 15, follower_base_scene.y() - 8, 30, 15
        )
        follower_head.setPen(QPen(QColor(50, 50, 50), 2))
        follower_head.setBrush(QBrush(self.FOLLOWER_COLOR))
        follower_head.setZValue(self.config.z_index_base + 2)
        visual_items.append(follower_head)

        # Follower base anchor (item 4) - fixed guide
        follower_anchor = QGraphicsRectItem(
            follower_base_scene.x() - 30, follower_base_scene.y() - 45, 60, 30
        )
        follower_anchor.setPen(QPen(self.ROD_COLOR, 3))
        follower_anchor.setBrush(QBrush(self.FOLLOWER_BASE_COLOR))
        follower_anchor.setZValue(self.config.z_index_base)
        visual_items.append(follower_anchor)

        # CAM center pivot (item 5)
        pivot = QGraphicsEllipseItem(cam_center_scene.x() - 8, cam_center_scene.y() - 8, 16, 16)
        pivot.setPen(QPen(self.CAM_CENTER_COLOR, 2))
        pivot.setBrush(QBrush(QColor(255, 100, 100)))
        pivot.setZValue(self.config.z_index_pivot)
        visual_items.append(pivot)

        # Store cam parameters for animation updates
        mechanism_data["_cam_profile_params"] = {
            "base_radius": scaled_base_radius,
            "cam_offset": scaled_cam_offset,
            "cam_lobes": cam_lobes,
            "profile_harmonic": profile_harmonic,
            "rod_length": scaled_rod_length,
        }

        return visual_items

    def update_visuals(
        self, visual_items: list[QGraphicsItem], mechanism_data: dict[str, Any]
    ) -> None:
        """
        Update existing CAM visuals with new position and parameters.

        Visual items order (must match create_visuals):
        - Item 0: cam polygon (QGraphicsPolygonItem)
        - Item 1: contact point (QGraphicsEllipseItem)
        - Item 2: follower rod (QGraphicsLineItem)
        - Item 3: follower head (QGraphicsRectItem)
        - Item 4: follower anchor (QGraphicsRectItem)
        - Item 5: cam center pivot (QGraphicsEllipseItem)
        """
        if len(visual_items) < 4:
            return  # Not enough items to update

        params = self.extract_params(mechanism_data)
        if not params:
            return

        # Extract CAM parameters (Foundry-compatible)
        base_radius = positive_finite_float(
            params.get("base_radius", params.get("cam_radius")),
            60.0,
        )
        cam_offset = max(
            0.0,
            finite_float(params.get("eccentricity", params.get("cam_offset")), 20.0),
        )
        follower_rod_length = positive_finite_float(
            params.get("follower_rod_length", params.get("follower_length")),
            100.0,
        )
        cam_lobes = max(1, int(positive_finite_float(params.get("cam_lobes"), 1.0)))
        profile_harmonic = finite_float(params.get("profile_harmonic"), 0.3)

        # Apply scaling factors
        cam_scale_factor = positive_finite_float(mechanism_data.get("cam_scale_factor"), 1.0)
        rod_length_multiplier = positive_finite_float(
            mechanism_data.get("rod_length_multiplier"), 1.0
        )

        scaled_base_radius = base_radius * cam_scale_factor
        scaled_cam_offset = cam_offset * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Get CAM position
        if "center_x" in params and "center_y" in params:
            cam_center = np.array(
                [
                    finite_float(params.get("center_x"), 0.0),
                    finite_float(params.get("center_y"), 0.0),
                ],
                dtype=float,
            )
        elif "cam_position" in mechanism_data and len(mechanism_data["cam_position"]) >= 2:
            cam_center = np.array(
                [
                    finite_float(mechanism_data["cam_position"][0], 0.0),
                    finite_float(mechanism_data["cam_position"][1], 0.0),
                ],
                dtype=float,
            )
        else:
            cam_center = np.array([0.0, 0.0])

        # Transform center to scene coordinates
        if self.config.transform_function:
            cam_center_scene = self.config.transform_function(cam_center)
        else:
            cam_center_scene = QPointF(cam_center[0], cam_center[1])

        # Update CAM polygon (item 0)
        if isinstance(visual_items[0], QGraphicsPolygonItem):
            cam_profile = self._create_cam_profile(
                scaled_base_radius, scaled_cam_offset, cam_lobes, profile_harmonic
            )
            cam_polygon_points = []
            for point in cam_profile:
                point_offset = np.array(point) + cam_center
                if self.config.transform_function:
                    scene_point = self.config.transform_function(point_offset)
                else:
                    scene_point = QPointF(point_offset[0], point_offset[1])
                cam_polygon_points.append(scene_point)
            visual_items[0].setPolygon(QPolygonF(cam_polygon_points))
        else:
            cam_profile = self._create_cam_profile(
                scaled_base_radius, scaled_cam_offset, cam_lobes, profile_harmonic
            )

        contact_local = cam_contact_local_from_profile(np.asarray(cam_profile, dtype=float))
        contact_pos = cam_center + contact_local
        if self.config.transform_function:
            contact_scene = self.config.transform_function(contact_pos)
        else:
            contact_scene = QPointF(contact_pos[0], contact_pos[1])

        # Follower base position
        if self.config.transform_function:
            unit_scale = cam_scene_unit_scale(self.config.transform_function)
        else:
            unit_scale = 1.0
        follower_base_scene = cam_follower_base_scene(
            contact_scene,
            scaled_rod_length,
            unit_scale,
        )

        # Update contact point (item 1)
        if len(visual_items) > 1 and isinstance(visual_items[1], QGraphicsEllipseItem):
            visual_items[1].setRect(contact_scene.x() - 5, contact_scene.y() - 5, 10, 10)

        # Update follower rod (item 2)
        if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
            visual_items[2].setLine(QLineF(contact_scene, follower_base_scene))

        # Update follower head (item 3)
        if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsRectItem):
            visual_items[3].setRect(
                follower_base_scene.x() - 15,
                follower_base_scene.y() - 8,
                30,
                15,
            )

        # Update follower anchor (item 4)
        if len(visual_items) > 4 and isinstance(visual_items[4], QGraphicsRectItem):
            visual_items[4].setRect(
                follower_base_scene.x() - 30,
                follower_base_scene.y() - 45,
                60,
                30,
            )

        # Update cam center pivot (item 5)
        if len(visual_items) > 5 and isinstance(visual_items[5], QGraphicsEllipseItem):
            visual_items[5].setRect(cam_center_scene.x() - 8, cam_center_scene.y() - 8, 16, 16)

    def _create_cam_profile(
        self,
        base_radius: float,
        cam_offset: float,
        cam_lobes: int = 1,
        profile_harmonic: float = 0.3,
    ) -> list[list[float]]:
        """
        Create cam profile using harmonic formula (matches Mechanism Foundry).

        Formula: radius = base_radius + cam_offset * cos(lobes * theta)
                       + (cam_offset * profile_harmonic) * cos(2 * lobes * theta)

        Args:
            base_radius: Base circle radius
            cam_offset: Maximum radial offset (eccentricity)
            cam_lobes: Number of lobes (1-4)
            profile_harmonic: Secondary harmonic amplitude (0.0-0.8)

        Returns:
            List of [x, y] points forming cam profile
        """
        base_radius = positive_finite_float(base_radius, 60.0)
        cam_offset = max(0.0, finite_float(cam_offset, 20.0))
        cam_lobes = max(1, int(positive_finite_float(cam_lobes, 1.0)))
        profile_harmonic = finite_float(profile_harmonic, 0.3)
        min_radius = max(1e-6, base_radius * 0.05)

        points = []
        num_points = 72  # Match Foundry's resolution

        for i in range(num_points):
            theta = (i / num_points) * 2 * np.pi

            # Harmonic profile formula (same as Foundry)
            primary_variation = cam_offset * np.cos(cam_lobes * theta)
            secondary_variation = (cam_offset * profile_harmonic) * np.cos(2 * cam_lobes * theta)
            r = max(min_radius, base_radius + primary_variation + secondary_variation)

            # Convert to Cartesian
            x = r * np.cos(theta)
            y = r * np.sin(theta)

            points.append([x, y])

        return points

    def _create_egg_shape_profile(
        self,
        base_radius: float,
        eccentricity: float,
    ) -> list[list[float]]:
        """Legacy egg-shape profile. Use _create_cam_profile for Foundry compatibility."""
        # Delegate to harmonic formula with 1 lobe, 0 secondary harmonic
        return self._create_cam_profile(
            base_radius,
            eccentricity,
            cam_lobes=1,
            profile_harmonic=0.0,
        )
