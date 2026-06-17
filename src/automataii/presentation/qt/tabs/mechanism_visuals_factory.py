"""
Factory class for creating visual representations of mechanisms.

This class encapsulates all mechanism visual creation logic, providing a clean
separation between the main tab logic and visual rendering concerns.
"""

import logging
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import TypeVar

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
)

from automataii.config.z_indices import (
    Z_MECHANISM_PIVOT,
    Z_SELECTION_MARKER,
)
from automataii.presentation.qt.gear_rendering import (
    annulus_path,
    gear_attachment_hole_centers,
    gear_hole_radius,
    gear_outline_polygon,
    radial_tick_lines,
)
from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float,
    finite_param,
    gear_linkage_arm_length,
    gear_linkage_pin_radius,
    positive_finite_float,
    truthy_param,
)
from automataii.presentation.qt.tabs.cam_geometry import (
    build_pear_cam_profile,
    build_pear_cam_profile_from_params,
    cam_contact_local_from_profile,
    cam_follower_base_scene,
    cam_scene_unit_scale,
)
from automataii.shared.physical_kit import (
    gear_center_distance,
    gear_clearance_from_params,
    physical_profile_from_params,
)

_GraphicsItemT = TypeVar("_GraphicsItemT", bound=QGraphicsItem)
_SceneTransform = Callable[[object], QPointF]


def _require_graphics_item(item: _GraphicsItemT | None) -> _GraphicsItemT:
    """Narrow PyQt scene factory return types; Qt returns an item at runtime."""
    assert item is not None
    return item


def _cosmetic_pen(
    color: QColor | Qt.GlobalColor | str,
    width: float = 3.0,
    style: Qt.PenStyle = Qt.PenStyle.SolidLine,
    cap: Qt.PenCapStyle = Qt.PenCapStyle.RoundCap,
) -> QPen:
    """
    Create a cosmetic pen that maintains constant screen width regardless of zoom.

    Args:
        color: Pen color (QColor or hex string)
        width: Pen width in pixels (screen units)
        style: Pen line style
        cap: Pen cap style

    Returns:
        QPen with cosmetic flag set
    """
    if isinstance(color, str):
        color = QColor(color)
    pen = QPen(color, width, style, cap)
    pen.setCosmetic(True)  # Width doesn't scale with view transform
    return pen


def _finite_point_array(raw: object) -> np.ndarray | None:
    try:
        point = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return None
    if point.ndim != 1 or len(point) < 2:
        return None
    point = point[:2]
    if not bool(np.isfinite(point).all()):
        return None
    return point


def _first_position_point(raw: object) -> np.ndarray | None:
    if isinstance(raw, np.ndarray):
        if raw.ndim == 1:
            return _finite_point_array(raw[:2])
        if raw.ndim == 2 and raw.shape[0] > 0:
            return _finite_point_array(raw[0, :2])
        return None

    if isinstance(raw, list | tuple):
        if not raw:
            return None
        first_point = _finite_point_array(raw[0])
        if first_point is not None:
            return first_point
        return _finite_point_array(raw)

    return _finite_point_array(raw)


def _point_from_params(params: dict, x_key: str, y_key: str) -> np.ndarray | None:
    if x_key not in params or y_key not in params:
        return None
    x_value = finite_float(params.get(x_key), math.nan)
    y_value = finite_float(params.get(y_key), math.nan)
    if not math.isfinite(x_value) or not math.isfinite(y_value):
        return None
    return np.array([x_value, y_value], dtype=float)


def _first_point(*points: np.ndarray | None) -> np.ndarray | None:
    for point in points:
        if point is not None:
            return point
    return None


class MechanismVisualsFactory:
    """Factory for creating visual representations of mechanisms."""

    def __init__(self, scene: QGraphicsScene, *, show_diagnostics: bool = False):
        """Initialize the factory with a graphics scene.

        Args:
            scene: The QGraphicsScene where visual items will be added
            show_diagnostics: Whether to render engineering diagnostic overlays.
        """
        self.scene = scene
        self.show_diagnostics = show_diagnostics

    def create_4bar_linkage_visuals(
        self, mechanism_data: dict, transform_function: _SceneTransform | None = None
    ) -> list[QGraphicsItem]:
        """Create visual representation of 4-bar linkage with triangular coupler (like dataset generator)."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        if not all([l1 is not None, l2 is not None, l3 is not None, l4 is not None]):
            return []

        # Use initial positions from simulation data if available.
        # If a Foundry/Design layer is already scene-aligned and only has
        # key_points, those key_points are the authoritative geometry.  Falling
        # back directly to [0, l1] would render a second, detached linkage in
        # the corner while handles/blueprint still point to the imported layer.
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        p1: np.ndarray | None = None
        p2: np.ndarray | None = None
        p3: np.ndarray | None = None
        p4: np.ndarray | None = None
        p_coupler: np.ndarray | None = None
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            has_initial_frame = isinstance(joint_positions, dict) and all(
                name in joint_positions
                and hasattr(joint_positions[name], "__len__")
                and len(joint_positions[name]) > 0
                for name in (
                    "p1_positions",
                    "p2_positions",
                    "p3_positions",
                    "p4_positions",
                )
            )
            if has_initial_frame:
                # Use first frame from simulation
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

                # Calculate initial coupler point position (same as dataset)
                # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
                coupler_point_x = finite_param(params, "coupler_point_x", "p_x", default=0.0)
                coupler_point_y = finite_param(params, "coupler_point_y", "p_y", default=0.0)

                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = (
                        p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                    )
                else:
                    p_coupler = p3
            else:
                key_points = mechanism_data.get("key_points", {})
                p1 = _finite_point_array(key_points.get("ground_pivot_1"))
                p2 = _finite_point_array(key_points.get("ground_pivot_2"))
                p3 = _finite_point_array(key_points.get("crank_end"))
                p4 = _finite_point_array(key_points.get("rocker_end"))
                p_coupler = _finite_point_array(key_points.get("coupler_point"))
                if p1 is None or p2 is None or p3 is None or p4 is None:
                    return []
                if p_coupler is None:
                    default_coupler_x = finite_float(l3, 0.0) / 2.0
                    coupler_point_x = finite_param(
                        params, "coupler_point_x", "p_x", default=default_coupler_x
                    )
                    coupler_point_y = finite_param(params, "coupler_point_y", "p_y", default=0.0)
                    coupler_vec = p4 - p3
                    coupler_length = np.linalg.norm(coupler_vec)
                    if coupler_length > 0:
                        coupler_unit = coupler_vec / coupler_length
                        coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                        p_coupler = (
                            p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                        )
                    else:
                        p_coupler = p3
        else:
            key_points = mechanism_data.get("key_points", {})
            p1 = _finite_point_array(key_points.get("ground_pivot_1"))
            p2 = _finite_point_array(key_points.get("ground_pivot_2"))
            p3 = _finite_point_array(key_points.get("crank_end"))
            p4 = _finite_point_array(key_points.get("rocker_end"))
            p_coupler = _finite_point_array(key_points.get("coupler_point"))

            if p1 is None or p2 is None or p3 is None or p4 is None:
                # Fallback - use default ground pivot positions based on l1
                p1 = np.array([0, 0])
                p2 = np.array([l1, 0])
                p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])
                d = np.linalg.norm(p2 - p3)
                if not (abs(l3 - l4) <= d <= l3 + l4):
                    return []

                a = (l3**2 - l4**2 + d**2) / (2 * d)
                h = math.sqrt(max(0, l3**2 - a**2))
                p3_p2_unit = (p2 - p3) / d
                midpoint = p3 + a * p3_p2_unit
                p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

            if p_coupler is None:
                # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
                default_coupler_x = finite_float(l3, 0.0) / 2.0
                coupler_point_x = finite_param(
                    params, "coupler_point_x", "p_x", default=default_coupler_x
                )
                coupler_point_y = finite_param(params, "coupler_point_y", "p_y", default=0.0)

                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = (
                        p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                    )
                else:
                    p_coupler = p3

        if p1 is None or p2 is None or p3 is None or p4 is None or p_coupler is None:
            return []

        # Transform all points to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)

        visual_items: list[QGraphicsItem] = []

        # Draw basic links (driver and follower) with cosmetic pens
        driver_link = QGraphicsLineItem(QLineF(p1_t, p3_t))
        driver_link.setPen(_cosmetic_pen("#e74c3c", 5))
        driver_link.setZValue(15)  # Above parts (Z_PART_DEFAULT = 10)
        self.scene.addItem(driver_link)
        visual_items.append(driver_link)

        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_link.setPen(_cosmetic_pen("#f39c12", 5))
        follower_link.setZValue(15)  # Above parts
        self.scene.addItem(follower_link)
        visual_items.append(follower_link)

        # Check if coupler forms a triangle or is collinear (same as dataset generator)
        area = (
            abs(
                p3[0] * (p4[1] - p_coupler[1])
                + p4[0] * (p_coupler[1] - p3[1])
                + p_coupler[0] * (p3[1] - p4[1])
            )
            / 2
        )

        if area < 1e-3:  # Collinear - show as line
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_line.setPen(_cosmetic_pen("#2ecc71", 4))
            coupler_line.setZValue(16)  # Above other links
            self.scene.addItem(coupler_line)
            visual_items.append(coupler_line)
        else:  # Non-collinear - show as triangle
            # Create triangular coupler plate (p3, p4, coupler_point)
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)

            coupler_triangle = QGraphicsPolygonItem(triangle_polygon)
            coupler_triangle.setPen(_cosmetic_pen("#2ecc71", 2))
            triangle_brush = QBrush(QColor("#2ecc71").lighter(160))
            triangle_brush.setStyle(Qt.BrushStyle.SolidPattern)
            coupler_triangle.setBrush(triangle_brush)
            coupler_triangle.setZValue(16)  # Above other links
            coupler_triangle.setOpacity(0.8)
            self.scene.addItem(coupler_triangle)
            visual_items.append(coupler_triangle)

        # Add ground link (p1 to p2) with colorful style like dataset generator
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_link.setPen(_cosmetic_pen("#9b59b6", 6))  # Purple
        ground_link.setZValue(14)  # Base mechanism level, above parts
        self.scene.addItem(ground_link)
        visual_items.append(ground_link)

        # Add pivot points with colorful style (like dataset generator)
        pivot_colors = [
            QColor("#f39c12"),
            QColor("#f39c12"),
            QColor("#e74c3c"),
            QColor("#3498db"),
        ]  # Orange, Orange, Red, Blue
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Outer circle
            outer_pivot = _require_graphics_item(
                self.scene.addEllipse(
                    pos.x() - 8,
                    pos.y() - 8,
                    16,
                    16,
                    _cosmetic_pen(color.darker(150), 2),
                    QBrush(color),
                )
            )
            outer_pivot.setZValue(Z_MECHANISM_PIVOT)
            outer_pivot.setToolTip(name)  # Add tooltip for identification
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = _require_graphics_item(
                self.scene.addEllipse(
                    pos.x() - 4,
                    pos.y() - 4,
                    8,
                    8,
                    QPen(Qt.PenStyle.NoPen),
                    QBrush(color.lighter(150)),
                )
            )
            inner_pivot.setZValue(Z_MECHANISM_PIVOT + 1)
            visual_items.append(inner_pivot)

        # Add coupler point marker (red dot)
        coupler_marker = _require_graphics_item(
            self.scene.addEllipse(
                p_coupler_t.x() - 4,
                p_coupler_t.y() - 4,
                8,
                8,
                _cosmetic_pen("#ff0000", 2),
                QBrush(QColor("#ff0000")),
            )
        )
        coupler_marker.setZValue(Z_SELECTION_MARKER)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)
        if self.show_diagnostics:
            self._add_transmission_angle_overlay(visual_items, mechanism_data, p2_t)

        return visual_items

    def _add_transmission_angle_overlay(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict,
        p2_t: QPointF,
    ) -> None:
        """Add transmission-angle diagnostics for debug builds only."""
        try:
            jp = mechanism_data.get("full_simulation_data", {}).get("joint_positions", {})
            if not (
                jp
                and all(
                    k in jp and len(jp[k]) > 0
                    for k in ("p1_positions", "p2_positions", "p3_positions", "p4_positions")
                )
            ):
                return
            mu_min = 180.0
            for i in range(min(len(jp["p3_positions"]), len(jp["p4_positions"]))):
                p3_i = np.array(jp["p3_positions"][i], dtype=float)
                p4_i = np.array(jp["p4_positions"][i], dtype=float)
                p2_i = np.array(jp["p2_positions"][i], dtype=float)
                v_c = p4_i - p3_i  # coupler
                v_r = p4_i - p2_i  # rocker
                n_c = np.linalg.norm(v_c)
                n_r = np.linalg.norm(v_r)
                if n_c < 1e-6 or n_r < 1e-6:
                    continue
                cos_mu = float(np.clip(np.dot(v_c, v_r) / (n_c * n_r), -1.0, 1.0))
                mu = math.degrees(math.acos(cos_mu))
                if mu > 180:
                    mu = 180.0
                if mu < mu_min:
                    mu_min = mu
            color = QColor("#2ecc71")
            status = "SAFE"
            if mu_min < 20.0 or mu_min > 160.0:
                color = QColor("#e74c3c")
                status = "CRITICAL"
            elif mu_min < 40.0 or mu_min > 140.0:
                color = QColor("#f1c40f")
                status = "CAUTION"
            halo_center = p2_t
            radius = 24.0
            halo = _require_graphics_item(
                self.scene.addEllipse(
                    halo_center.x() - radius,
                    halo_center.y() - radius,
                    radius * 2,
                    radius * 2,
                    _cosmetic_pen(color, 5),
                    QBrush(Qt.BrushStyle.NoBrush),
                )
            )
            halo.setZValue(30)
            visual_items.append(halo)
            label = _require_graphics_item(self.scene.addText(f"μ_min={mu_min:.0f}° {status}"))
            label.setDefaultTextColor(color)
            label.setPos(halo_center.x() + radius + 6, halo_center.y() - 8)
            label.setZValue(31)
            visual_items.append(label)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def create_5bar_linkage_visuals(
        self, mechanism_data: dict, transform_function: _SceneTransform | None = None
    ) -> list[QGraphicsItem]:
        """Create visual representation for 5-bar linkage mechanism."""
        visual_items: list[QGraphicsItem] = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(
                mechanism_data
            )

            if not to_scene_coords:
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                L3 = params.get("L3", 50)
                params.get("L4", 45)
                L5 = params.get("L5", 55)

                p3 = p1 + np.array([L2, 0])
                p4 = p3 + np.array([L3 * 0.7, L3 * 0.7])
                p5 = p2 + np.array([-L5 * 0.5, L5 * 0.866])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)

            # Create links with cosmetic pens
            pen = _cosmetic_pen(QColor(100, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler 1 (p3 to p4)
            coupler1 = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler1.setPen(pen)
            self.scene.addItem(coupler1)
            visual_items.append(coupler1)

            # Coupler 2 (p4 to p5)
            coupler2 = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            coupler2.setPen(pen)
            self.scene.addItem(coupler2)
            visual_items.append(coupler2)

            # Output link (p5 to p2)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p2_scene))
            output_link.setPen(pen)
            self.scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground link
            ground_link = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground_link.setPen(_cosmetic_pen(QColor(50, 50, 50), 4))
            self.scene.addItem(ground_link)
            visual_items.append(ground_link)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(_cosmetic_pen(Qt.GlobalColor.black, 2))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(_cosmetic_pen(Qt.GlobalColor.black, 1))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def create_6bar_linkage_visuals(
        self, mechanism_data: dict, transform_function: _SceneTransform | None = None
    ) -> list[QGraphicsItem]:
        """Create visual representation for 6-bar linkage mechanism (Stephenson Type I)."""
        visual_items: list[QGraphicsItem] = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(
                mechanism_data
            )

            if not to_scene_coords:
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))
            p6 = np.array(params.get("ground_pivot_3", [50, -30]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                params.get("L3", 60)
                L4 = params.get("L4", 50)
                L5 = params.get("L5", 45)

                p3 = p1 + np.array([L2, 0])
                p4 = p2 + np.array([-L4 * 0.5, L4 * 0.866])
                p5 = p6 + np.array([L5 * 0.7, L5 * 0.7])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)
            p6_scene = to_scene_coords(p6)

            # Create links with cosmetic pens
            pen = _cosmetic_pen(QColor(150, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler (p3 to p4)
            coupler = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler.setPen(pen)
            self.scene.addItem(coupler)
            visual_items.append(coupler)

            # Rocker (p4 to p2)
            rocker = QGraphicsLineItem(QLineF(p4_scene, p2_scene))
            rocker.setPen(pen)
            self.scene.addItem(rocker)
            visual_items.append(rocker)

            # Ternary link (p4 to p5)
            ternary = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            ternary.setPen(_cosmetic_pen(QColor(200, 150, 100), 3))
            self.scene.addItem(ternary)
            visual_items.append(ternary)

            # Output link (p5 to p6)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p6_scene))
            output_link.setPen(pen)
            self.scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground links
            ground1 = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground1.setPen(_cosmetic_pen(QColor(50, 50, 50), 4))
            self.scene.addItem(ground1)
            visual_items.append(ground1)

            ground2 = QGraphicsLineItem(QLineF(p2_scene, p6_scene))
            ground2.setPen(_cosmetic_pen(QColor(50, 50, 50), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(ground2)
            visual_items.append(ground2)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene, p6_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(_cosmetic_pen(Qt.GlobalColor.black, 2))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(_cosmetic_pen(Qt.GlobalColor.black, 1))
                self.scene.addItem(pivot)
                visual_items.append(pivot)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def create_cam_visuals(
        self,
        mechanism_data: dict,
        transform_function: _SceneTransform | None = None,
        character_position: object | None = None,
    ) -> list[QGraphicsItem]:
        """Create visual representation of cam and follower mechanism using analytic pear-cam profile.

        - No dataset/template dependency: profile is built from base_radius and eccentricity (total lift).
        - Pear-cam lobe: single-sided rise/return with dwells; shape preserved under rotation.
        """
        # Note: transform_function is used later at line 542 via base_map assignment
        params = mechanism_data.get("params", {})

        if not params:
            return []

        # Adjusted parameters for more realistic CAM size
        # CAM should be smaller, rod should be longer for realistic appearance
        follower_rod_length = positive_finite_float(params.get("follower_rod_length"), 40.0)

        # Scale CAM appropriately for character interaction
        # Use stored scaling factors if available, otherwise use defaults
        cam_scale_factor = positive_finite_float(
            mechanism_data.get("cam_scale_factor", 1.0), 1.0
        )  # Normal CAM size
        rod_length_multiplier = positive_finite_float(
            mechanism_data.get("rod_length_multiplier", 1.0), 1.0
        )  # Direct rod length control

        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Build profile from the same contract as domain/Foundry exports.
        # When cam_lobes/profile_harmonic are present, this preserves the
        # harmonic Foundry profile; otherwise it keeps the pear timing model.
        cam_points_local = build_pear_cam_profile_from_params(
            params,
            scale=cam_scale_factor,
            num_samples=360,
        )
        mechanism_data["cam_points_local"] = cam_points_local

        key_points = mechanism_data.get("key_points", {})
        if not isinstance(key_points, dict):
            key_points = {}
        is_foundry_scene_cam = (
            str(mechanism_data.get("source", "")).lower() == "foundry"
            and str(mechanism_data.get("coordinate_space", "")).lower() == "scene"
        )

        def scene_key_point(name: str) -> QPointF | None:
            if not is_foundry_scene_cam:
                return None
            point = _finite_point_array(key_points.get(name))
            if point is None:
                return None
            return QPointF(float(point[0]), float(point[1]))

        snapshot_contact_scene = scene_key_point("contact_point")
        snapshot_follower_base_scene = (
            scene_key_point("follower_base")
            or scene_key_point("follower_end")
            or scene_key_point("follower_position")
        )

        # Placement priority:
        # 1) Explicit edited center in mechanism-space (m_center_*)
        # 2) Explicit edited center in scene-space (center_*)
        # 3) Auto-alignment from generated_path (legacy behavior)
        gen_path = mechanism_data.get("generated_path")
        explicit_center_mech = None
        explicit_center_scene = None

        try:
            if "m_center_x" in params and "m_center_y" in params:
                candidate_center = np.array(
                    [
                        finite_float(params.get("m_center_x"), math.nan),
                        finite_float(params.get("m_center_y"), math.nan),
                    ],
                    dtype=float,
                )
                if bool(np.isfinite(candidate_center).all()):
                    explicit_center_mech = candidate_center
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
            explicit_center_mech = None

        try:
            if "center_x" in params and "center_y" in params:
                center_x = finite_float(params.get("center_x"), math.nan)
                center_y = finite_float(params.get("center_y"), math.nan)
                if math.isfinite(center_x) and math.isfinite(center_y):
                    explicit_center_scene = QPointF(center_x, center_y)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
            explicit_center_scene = None

        if explicit_center_scene is not None:
            mechanism_data["cam_position"] = [explicit_center_scene.x(), explicit_center_scene.y()]
        elif explicit_center_mech is None:
            try:
                if gen_path is not None:
                    brect = gen_path.boundingRect()
                    path_x_center = float(brect.center().x())
                    path_y_bottom = float(brect.bottom())
                    contact_local = cam_contact_local_from_profile(cam_points_local)
                    mechanism_data["cam_position"] = [
                        path_x_center,
                        path_y_bottom - float(contact_local[1]),
                    ]
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        base_map = transform_function or self._get_scene_transform_function(mechanism_data)
        if base_map is None and explicit_center_scene is None:
            return []

        try:
            if explicit_center_mech is not None and base_map is not None:

                def cam_to_scene_coords(p: object) -> QPointF:
                    point = _finite_point_array(p)
                    if point is None:
                        mapped = base_map(explicit_center_mech)
                    else:
                        mapped = base_map(point + explicit_center_mech)
                    return QPointF(mapped.x(), mapped.y())

                mechanism_data["cam_transform_function"] = cam_to_scene_coords

            elif explicit_center_scene is not None:
                center_scene = QPointF(explicit_center_scene.x(), explicit_center_scene.y())

                def cam_to_scene_coords(p: object) -> QPointF:
                    point = _finite_point_array(p)
                    if point is None:
                        return QPointF(center_scene.x(), center_scene.y())
                    return QPointF(
                        center_scene.x() + float(point[0]), center_scene.y() + float(point[1])
                    )

                mechanism_data["cam_transform_function"] = cam_to_scene_coords

            elif gen_path is not None and base_map is not None:
                brect = gen_path.boundingRect()
                path_x_center = float(brect.center().x())
                path_y_bottom = float(brect.bottom())
                follower_local = cam_contact_local_from_profile(cam_points_local)
                follower_scene_raw = base_map(follower_local)
                dx = path_x_center - follower_scene_raw.x()
                dy = path_y_bottom - follower_scene_raw.y()

                def cam_to_scene_coords(p: object) -> QPointF:
                    point = _finite_point_array(p)
                    if point is None:
                        return QPointF(follower_scene_raw.x() + dx, follower_scene_raw.y() + dy)
                    mapped = base_map(point)
                    return QPointF(mapped.x() + dx, mapped.y() + dy)

                mechanism_data["cam_transform_function"] = cam_to_scene_coords
                center_scene_raw = base_map(np.array([0.0, 0.0], dtype=float))
                mechanism_data["cam_position"] = [
                    float(center_scene_raw.x() + dx),
                    float(center_scene_raw.y() + dy),
                ]
            else:
                mechanism_data["cam_transform_function"] = base_map
        except Exception:
            if explicit_center_scene is not None:
                center_scene = QPointF(explicit_center_scene.x(), explicit_center_scene.y())

                def cam_to_scene_coords(p: object) -> QPointF:
                    point = _finite_point_array(p)
                    if point is None:
                        return QPointF(center_scene.x(), center_scene.y())
                    return QPointF(
                        center_scene.x() + float(point[0]), center_scene.y() + float(point[1])
                    )

                mechanism_data["cam_transform_function"] = cam_to_scene_coords
            else:
                mechanism_data["cam_transform_function"] = base_map
        # Bind local mapper for convenience
        cam_to_scene_coords = mechanism_data["cam_transform_function"]
        # Initial follower contact at local +Y max using the shared scene-vertical convention.
        follower_pos_orig = cam_contact_local_from_profile(cam_points_local)
        cam_center_orig = np.array([0.0, 0.0], dtype=float)

        # Store scaling factors for consistency in animation and parametric editing
        mechanism_data["cam_scale_factor"] = cam_scale_factor
        mechanism_data["rod_length_multiplier"] = rod_length_multiplier

        # Transform key points to scene coordinates
        cam_center_scene = cam_to_scene_coords(cam_center_orig)
        follower_scene = cam_to_scene_coords(follower_pos_orig)
        if snapshot_contact_scene is not None:
            follower_scene = snapshot_contact_scene

        unit_scale = cam_scene_unit_scale(cam_to_scene_coords)
        if snapshot_follower_base_scene is not None:
            follower_base_scene = snapshot_follower_base_scene
        else:
            follower_base_scene = cam_follower_base_scene(
                follower_scene, scaled_rod_length, unit_scale
            )

        # Build cam polygon
        cam_polygon_points: list[QPointF] = []
        pts = cam_points_local
        for p in pts:
            scene_point = cam_to_scene_coords(p)
            cam_polygon_points.append(scene_point)

        # Create QPolygonF from points
        cam_polygon = QPolygonF(cam_polygon_points)

        visual_items: list[QGraphicsItem] = []

        # Create cam body
        # Fill with blue like gear visuals (not green outline)
        cam_color = QColor("#3498db")  # Gear blue
        cam_body = QGraphicsPolygonItem(cam_polygon)
        cam_body.setPen(_cosmetic_pen(cam_color, 4))
        cam_body.setBrush(QBrush(cam_color.lighter(170)))
        cam_body.setZValue(15)  # Above parts
        cam_body.setOpacity(1.0)
        cam_body.setToolTip("Cam Profile")
        self.scene.addItem(cam_body)
        visual_items.append(cam_body)

        # Build items in the order expected by animator updates:
        # [cam body, contact point, follower rod, follower head, follower anchor, cam center]
        # Contact point marker at local +Y max.
        contact_color = QColor("#e53935")
        contact_marker = QGraphicsEllipseItem(
            follower_scene.x() - 5, follower_scene.y() - 5, 10, 10
        )
        contact_marker.setPen(_cosmetic_pen(contact_color.darker(130), 2))
        contact_marker.setBrush(QBrush(contact_color))
        contact_marker.setZValue(18)
        contact_marker.setToolTip("Cam Contact Point")
        self.scene.addItem(contact_marker)
        visual_items.append(contact_marker)

        # Create follower rod line from cam top (contact point) to follower.
        rod_pen = _cosmetic_pen("#9e9e9e", 3, Qt.PenStyle.DashLine)
        cam_top_scene = follower_scene
        follower_rod = QGraphicsLineItem(
            cam_top_scene.x(), cam_top_scene.y(), follower_base_scene.x(), follower_base_scene.y()
        )
        follower_rod.setPen(rod_pen)
        follower_rod.setZValue(14)  # Below cam but above parts
        follower_rod.setToolTip("Connecting Rod")
        self.scene.addItem(follower_rod)
        visual_items.append(follower_rod)

        # Follower head (animated in-place by visual animator).
        follower_color = QColor("#ff9800")
        follower_body = QGraphicsRectItem(
            follower_base_scene.x() - 15,
            follower_base_scene.y() - 8,
            30,
            15,
        )
        follower_body.setPen(_cosmetic_pen(follower_color.darker(120), 2))
        follower_body.setBrush(QBrush(follower_color))
        follower_body.setZValue(16)
        follower_body.setToolTip("Follower Head")
        self.scene.addItem(follower_body)
        visual_items.append(follower_body)

        # Follower anchor/guide block.
        follower_anchor = QGraphicsRectItem(
            follower_base_scene.x() - 30,
            follower_base_scene.y() - 45,
            60,
            30,
        )
        follower_anchor.setPen(_cosmetic_pen("#616161", 2))
        follower_anchor.setBrush(QBrush(QColor("#bdbdbd")))
        follower_anchor.setZValue(13)
        follower_anchor.setToolTip("Follower Guide")
        self.scene.addItem(follower_anchor)
        visual_items.append(follower_anchor)

        # Cam center marker (rotation point).
        cam_center_color = QColor("#f44336")
        cam_center_marker = QGraphicsEllipseItem(
            cam_center_scene.x() - 8, cam_center_scene.y() - 8, 16, 16
        )
        cam_center_marker.setPen(_cosmetic_pen(cam_center_color.darker(150), 2))
        cam_center_marker.setBrush(QBrush(cam_center_color))
        cam_center_marker.setZValue(20)
        cam_center_marker.setToolTip("Cam Center - Rotation axis")
        self.scene.addItem(cam_center_marker)
        visual_items.append(cam_center_marker)

        # Store follower's fixed X position in scene coordinates for vertical motion constraint
        try:
            mechanism_data["follower_fixed_x_scene"] = float(follower_base_scene.x())
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        if self.show_diagnostics:
            # --- Diagnostics overlay: High-curvature highlight on cam profile ---
            try:
                pts = cam_points_local
                if pts is not None and len(pts) >= 5 and "cam_transform_function" in mechanism_data:
                    k_values = []
                    for i in range(1, len(pts) - 2):
                        x1, y1 = pts[i - 1]
                        x2, y2 = pts[i]
                        x3, y3 = pts[i + 1]
                        dx1, dy1 = x2 - x1, y2 - y1
                        dx2, dy2 = x3 - x2, y3 - y2
                        num = abs(dx1 * dy2 - dy1 * dx2)
                        den = (dx1 * dx1 + dy1 * dy1) ** 1.5 + 1e-6
                        k = num / den
                        k_values.append(k)
                    if k_values:
                        import numpy as _np

                        k_arr = _np.array(k_values)
                        thr = float(_np.percentile(k_arr, 90))
                        highlight = QPainterPath()
                        tf = mechanism_data["cam_transform_function"]
                        for i, kval in enumerate(k_values, start=1):
                            if kval >= thr:
                                p = pts[i]
                                sp = tf(p)
                                if highlight.isEmpty():
                                    highlight.moveTo(sp)
                                else:
                                    highlight.lineTo(sp)
                        if not highlight.isEmpty():
                            hp = QGraphicsPathItem(highlight)
                            hp.setPen(QPen(QColor("#e74c3c"), 3, Qt.PenStyle.SolidLine))
                            hp.setZValue(25)
                            self.scene.addItem(hp)
                            visual_items.append(hp)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def _load_cam_profile_svg(self, svg_path: str) -> tuple[np.ndarray, np.ndarray]:
        """Parse a simple SVG cam profile and return (axis, polygon_points).

        Assumptions:
        - Uses a <path> composed of M/L commands for the cam outline
        - A <circle> in construction layer gives axis (cx, cy)
        - Ignores group transforms as both elements share the same space
        """
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # Namespaces handling (strip if present)
        def strip(tag: str) -> str:
            return tag.split("}", 1)[-1]

        axis = None
        poly_pts: list[tuple[float, float]] = []

        for elem in root.iter():
            tag = strip(elem.tag)
            if tag == "circle" and axis is None:
                cx = float(elem.attrib.get("cx", "0"))
                cy = float(elem.attrib.get("cy", "0"))
                axis = np.array([cx, cy], dtype=float)
            elif tag == "path" and ("layer-cam" in (elem.get("id") or "") or True):
                d = elem.attrib.get("d", "")
                if not d:
                    continue
                # Very simple M/L tokenizer
                tokens = d.replace(",", " ").split()
                i = 0
                while i < len(tokens):
                    cmd = tokens[i]
                    if cmd in ("M", "L") and i + 2 < len(tokens):
                        try:
                            x = float(tokens[i + 1])
                            y = float(tokens[i + 2])
                            poly_pts.append((x, y))
                            i += 3
                        except ValueError:
                            i += 1
                    else:
                        # Skip numbers after implicit L
                        try:
                            x = float(cmd)
                            y = float(tokens[i + 1])
                            poly_pts.append((x, y))
                            i += 2
                        except Exception:
                            i += 1

        if axis is None:
            # Fallback: center of bbox of points
            arr = np.array(poly_pts, dtype=float)
            center = (np.min(arr, axis=0) + np.max(arr, axis=0)) / 2.0
            axis = center

        arr = np.array(poly_pts, dtype=float)
        return axis, arr

    def _build_cam_from_template(
        self,
        template_points: np.ndarray,
        base_radius: float,
        eccentricity: float,
        num_samples: int = 180,
    ) -> np.ndarray:
        """Build a cam polygon from a template profile using normalized radial mapping.

        - Compute support function r_templ(θ) = max(dot(p, uθ)) over template points (convex envelope)
        - Normalize: s(θ) = (r_templ(θ) - min(r_templ)) / (max(r_templ) - min(r_templ) + eps)
        - New radius: r(θ) = base_radius + eccentricity * s(θ)
        - Return polygon points: r(θ) * [cosθ, sinθ]
        """
        if template_points is None or len(template_points) < 3:
            # Fallback circular cam
            fallback_points: list[list[float]] = []
            for i in range(num_samples + 1):
                theta = 2 * np.pi * i / num_samples
                fallback_points.append(
                    [base_radius * np.cos(theta), base_radius * np.sin(theta)]
                )
            return np.array(fallback_points, dtype=float)

        thetas = np.linspace(0, 2 * np.pi, num_samples + 1)
        u = np.stack([np.cos(thetas), np.sin(thetas)], axis=1)  # (N,2)
        # Compute support: for each θ, max over points dot(p, uθ)
        # template_points shape (M,2)
        # dots shape (N,M) = u @ p^T
        dots = u @ template_points.T
        r_templ = np.max(dots, axis=1)
        r_min = float(np.min(r_templ))
        r_max = float(np.max(r_templ))
        denom = max(1e-9, r_max - r_min)
        s = (r_templ - r_min) / denom
        r_new = base_radius + eccentricity * s
        points = np.stack([r_new * np.cos(thetas), r_new * np.sin(thetas)], axis=1)
        return points.astype(float)

    def _build_pear_cam_profile(
        self,
        base_radius: float,
        eccentricity: float,
        rise_deg: float = 90.0,
        high_dwell_deg: float = 60.0,
        return_deg: float | None = None,
        dwell_low_deg: float = 180.0,
        align_max_to_deg: float = 90.0,
        num_samples: int = 360,
    ) -> np.ndarray:
        """Analytic pear-cam (single-lobe) profile with sinusoidal rise/return and dwells.

        Matches blueprint script defaults (green outline):
        - rise=90°, high dwell=60°, low dwell=180°, fall inferred
        - align_max_to_deg: angle where radius is maximum (default 90° => +Y)
        - r(θ) = base_radius + eccentricity * s(θ)
        """
        return np.asarray(
            build_pear_cam_profile(
                base_radius=base_radius,
                eccentricity=eccentricity,
                rise_deg=rise_deg,
                high_dwell_deg=high_dwell_deg,
                return_deg=return_deg,
                dwell_low_deg=dwell_low_deg,
                align_max_to_deg=align_max_to_deg,
                num_samples=num_samples,
            ),
            dtype=float,
        )

    def create_gear_visuals(
        self, mechanism_data: dict, transform_function: _SceneTransform | None = None
    ) -> list[QGraphicsItem]:
        """Create visual representation of gear train mechanism."""
        params = mechanism_data.get("params", {})
        if not params:
            return []
        profile = physical_profile_from_params(params)

        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)

        r1 = float(params.get("gear1_radius", params.get("r1", 30)))
        r2 = float(params.get("gear2_radius", params.get("r2", 50)))
        if r1 <= 0:
            r1 = 1.0
        if r2 <= 0:
            r2 = 1.0

        use_scene_geometry = all(
            key in params for key in ("gear1_x", "gear1_y", "gear2_x", "gear2_y")
        )

        if use_scene_geometry:
            gear1_center_scene = QPointF(float(params["gear1_x"]), float(params["gear1_y"]))
            gear2_center_scene = QPointF(float(params["gear2_x"]), float(params["gear2_y"]))
            r1_screen = float(params.get("gear1_radius", r1))
            r2_screen = float(params.get("gear2_radius", r2))
            if r1_screen <= 0:
                r1_screen = r1
            if r2_screen <= 0:
                r2_screen = r2

            # Keep names for diagnostics logic below.
            gear1_center_orig = np.array([0.0, 0.0], dtype=float)
            gear2_center_orig = np.array(
                [float(QLineF(gear1_center_scene, gear2_center_scene).length()), 0.0], dtype=float
            )
        else:
            if not to_scene_coords:
                return []

            key_points = mechanism_data.get("key_points", {})
            if "gear1_center" in key_points and "gear2_center" in key_points:
                gear1_center_orig = np.array(key_points["gear1_center"], dtype=float)
                gear2_center_orig = np.array(key_points["gear2_center"], dtype=float)
            else:
                clearance = gear_clearance_from_params(params, profile=profile)
                distance = gear_center_distance(r1, r2, clearance, profile=profile)
                gear1_center_orig = np.array([0.0, 0.0], dtype=float)
                gear2_center_orig = np.array([distance, 0.0], dtype=float)

            # Transform to scene coordinates
            gear1_center_scene = to_scene_coords(gear1_center_orig)
            gear2_center_scene = to_scene_coords(gear2_center_orig)

            # Calculate screen radii from transform scale.
            gear1_edge_orig = gear1_center_orig + np.array([r1, 0.0], dtype=float)
            gear1_edge_scene = to_scene_coords(gear1_edge_orig)
            r1_screen = QLineF(gear1_center_scene, gear1_edge_scene).length()

            gear2_edge_orig = gear2_center_orig + np.array([r2, 0.0], dtype=float)
            gear2_edge_scene = to_scene_coords(gear2_edge_orig)
            r2_screen = QLineF(gear2_center_scene, gear2_edge_scene).length()

        visual_items: list[QGraphicsItem] = []
        gear1_teeth = int(round(finite_float(params.get("gear1_teeth"), 12.0)))
        gear2_teeth = int(round(finite_float(params.get("gear2_teeth"), 16.0)))

        # Create gear 1 (driver) with visible tooth geometry.
        gear1_color = QColor("#3498db")  # Blue

        gear1_body = _require_graphics_item(
            self.scene.addPolygon(
                gear_outline_polygon(gear1_center_scene, r1_screen, gear1_teeth, 0.0),
                _cosmetic_pen(gear1_color, 4),
                QBrush(gear1_color.lighter(170)),
            )
        )
        gear1_body.setZValue(15)  # Above parts
        visual_items.append(gear1_body)

        # Create gear 2 (driven) with visible tooth geometry.
        gear2_color = QColor("#2ecc71")  # Green

        gear2_body = _require_graphics_item(
            self.scene.addPolygon(
                gear_outline_polygon(gear2_center_scene, r2_screen, gear2_teeth, 0.0),
                _cosmetic_pen(gear2_color, 4),
                QBrush(gear2_color.lighter(170)),
            )
        )
        gear2_body.setZValue(15)  # Above parts
        visual_items.append(gear2_body)

        # Create rotation indicators (lines that will rotate)
        indicator_color = QColor("#ffffff")  # White lines

        # Gear 1 indicator (initially horizontal) - use screen-space radius
        gear1_indicator = _require_graphics_item(
            self.scene.addLine(
                gear1_center_scene.x(),
                gear1_center_scene.y(),
                gear1_center_scene.x() + r1_screen,
                gear1_center_scene.y(),
                _cosmetic_pen(indicator_color, 3),
            )
        )
        gear1_indicator.setZValue(15)
        visual_items.append(gear1_indicator)

        # Gear 2 indicator (initially horizontal) - use screen-space radius
        gear2_indicator = _require_graphics_item(
            self.scene.addLine(
                gear2_center_scene.x(),
                gear2_center_scene.y(),
                gear2_center_scene.x() + r2_screen,
                gear2_center_scene.y(),
                _cosmetic_pen(indicator_color, 3),
            )
        )
        gear2_indicator.setZValue(15)
        visual_items.append(gear2_indicator)

        for center_scene, radius_screen, prefix in (
            (gear1_center_scene, r1_screen, "gear1_attachment_hole"),
            (gear2_center_scene, r2_screen, "gear2_attachment_hole"),
        ):
            hole_radius = gear_hole_radius(radius_screen)
            for index, hole_center in enumerate(
                gear_attachment_hole_centers(center_scene, radius_screen, count=4)
            ):
                hole = _require_graphics_item(
                    self.scene.addEllipse(
                        hole_center.x() - hole_radius,
                        hole_center.y() - hole_radius,
                        hole_radius * 2,
                        hole_radius * 2,
                        _cosmetic_pen("#5c4033", 1.5),
                        QBrush(QColor(255, 255, 255, 225)),
                    )
                )
                hole.setData(0, f"{prefix}_{index}")
                hole.setZValue(16)
                visual_items.append(hole)

        # Create center pivots
        pivot_color = QColor("#f39c12")  # Orange

        # Gear 1 center
        gear1_pivot = _require_graphics_item(
            self.scene.addEllipse(
                gear1_center_scene.x() - 8,
                gear1_center_scene.y() - 8,
                16,
                16,
                _cosmetic_pen(pivot_color.darker(150), 3),
                QBrush(pivot_color),
            )
        )
        gear1_pivot.setZValue(20)
        visual_items.append(gear1_pivot)

        # Gear 2 center
        gear2_pivot = _require_graphics_item(
            self.scene.addEllipse(
                gear2_center_scene.x() - 8,
                gear2_center_scene.y() - 8,
                16,
                16,
                _cosmetic_pen(pivot_color.darker(150), 3),
                QBrush(pivot_color),
            )
        )
        gear2_pivot.setZValue(20)
        visual_items.append(gear2_pivot)

        if truthy_param(params.get("gear_linkage_enabled", False)):
            pin_radius = gear_linkage_pin_radius(params, r2)
            arm_length = gear_linkage_arm_length(params)
            theta1 = math.radians(finite_param(params, "input_angle", default=0.0))
            theta2 = -theta1 * (r1 / r2 if abs(r2) > 1e-9 else 1.0)

            if use_scene_geometry:
                scene_scale = r2_screen / max(r2, 1e-9)
                pin_scene = gear2_center_scene + QPointF(
                    pin_radius * scene_scale * math.cos(theta2),
                    pin_radius * scene_scale * math.sin(theta2),
                )
                end_scene = pin_scene + QPointF(
                    arm_length * scene_scale * math.cos(theta2),
                    arm_length * scene_scale * math.sin(theta2),
                )
            else:
                assert to_scene_coords is not None
                pin_orig = gear2_center_orig + np.array(
                    [pin_radius * math.cos(theta2), pin_radius * math.sin(theta2)],
                    dtype=float,
                )
                end_orig = pin_orig + np.array(
                    [arm_length * math.cos(theta2), arm_length * math.sin(theta2)],
                    dtype=float,
                )
                pin_scene = to_scene_coords(pin_orig)
                end_scene = to_scene_coords(end_orig)

            linkage_arm = _require_graphics_item(
                self.scene.addLine(
                    QLineF(pin_scene, end_scene),
                    _cosmetic_pen("#d62728", 5),
                )
            )
            linkage_arm.setData(0, "gear_linkage_arm")
            linkage_arm.setZValue(22)
            visual_items.append(linkage_arm)

            for key, point, color in (
                ("gear_linkage_pin", pin_scene, QColor("#ff9896")),
                ("gear_linkage_end", end_scene, QColor("#d62728")),
            ):
                marker = _require_graphics_item(
                    self.scene.addEllipse(
                        point.x() - 5.0,
                        point.y() - 5.0,
                        10.0,
                        10.0,
                        _cosmetic_pen("#7f1d1d", 2),
                        QBrush(color),
                    )
                )
                marker.setData(0, key)
                marker.setZValue(23)
                visual_items.append(marker)

        if self.show_diagnostics:
            # --- Diagnostics overlay: pitch circles and center distance check ---
            try:
                dashed = _cosmetic_pen("#7f8c8d", 1, Qt.PenStyle.DashLine)
                pc1 = _require_graphics_item(
                    self.scene.addEllipse(
                        gear1_center_scene.x() - r1_screen,
                        gear1_center_scene.y() - r1_screen,
                        r1_screen * 2,
                        r1_screen * 2,
                        dashed,
                    )
                )
                pc1.setZValue(12)
                visual_items.append(pc1)
                pc2 = _require_graphics_item(
                    self.scene.addEllipse(
                        gear2_center_scene.x() - r2_screen,
                        gear2_center_scene.y() - r2_screen,
                        r2_screen * 2,
                        r2_screen * 2,
                        dashed,
                    )
                )
                pc2.setZValue(12)
                visual_items.append(pc2)
                if use_scene_geometry:
                    d_orig = float(QLineF(gear1_center_scene, gear2_center_scene).length())
                    desired = gear_center_distance(
                        r1_screen,
                        r2_screen,
                        gear_clearance_from_params(params, profile=profile),
                        profile=profile,
                    )
                else:
                    d_orig = float(np.linalg.norm(gear2_center_orig - gear1_center_orig))
                    desired = gear_center_distance(
                        r1,
                        r2,
                        gear_clearance_from_params(params, profile=profile),
                        profile=profile,
                    )
                mismatch = abs(d_orig - desired)
                if mismatch > 0.5:
                    warn = _require_graphics_item(
                        self.scene.addText(f"Center distance off by {mismatch:.1f}")
                    )
                    warn.setDefaultTextColor(QColor("#e74c3c"))
                    warn.setPos(
                        (gear1_center_scene.x() + gear2_center_scene.x()) / 2.0,
                        gear1_center_scene.y() - 20,
                    )
                    warn.setZValue(30)
                    visual_items.append(warn)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def create_planetary_gear_visuals(
        self, mechanism_data: dict, transform_function: _SceneTransform | None = None
    ) -> list[QGraphicsItem]:
        """Create visual representation of planetary gear mechanism."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r_sun = positive_finite_float(params.get("r_sun", 20), 20.0)
        r_planet = positive_finite_float(params.get("r_planet", 30), 30.0)
        arm_length = positive_finite_float(params.get("arm_length", 15), 15.0)

        visual_items: list[QGraphicsItem] = []

        # Try to get initial positions from simulation data
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        gear_positions = (
            full_sim_data.get("gear_positions", {}) if isinstance(full_sim_data, dict) else {}
        )
        if not isinstance(gear_positions, dict):
            gear_positions = {}

        sim_sun_center = _first_position_point(gear_positions.get("sun_centers"))
        sim_planet_center = _first_position_point(gear_positions.get("planet_centers"))
        sim_tracking_point = _first_position_point(gear_positions.get("tracking_points"))

        if (
            sim_sun_center is not None
            and sim_planet_center is not None
            and sim_tracking_point is not None
        ):
            # Use simulation data for accurate positioning
            sun_center_orig = sim_sun_center
            planet_center_orig = sim_planet_center
            tracking_point_orig = sim_tracking_point
        else:
            key_points = mechanism_data.get("key_points", {})
            if not isinstance(key_points, dict):
                key_points = {}

            sun_center = _first_point(
                _finite_point_array(key_points.get("sun_center")),
                _point_from_params(params, "m_sun_x", "m_sun_y"),
                _point_from_params(params, "sun_x", "sun_y"),
                _point_from_params(params, "gear1_x", "gear1_y"),
            )
            if sun_center is None:
                sun_center_orig = np.array([0.0, 0.0], dtype=float)
            else:
                sun_center_orig = sun_center

            planet_center = _first_point(
                _finite_point_array(key_points.get("planet_center")),
                _point_from_params(params, "planet_x", "planet_y"),
                _point_from_params(params, "gear2_x", "gear2_y"),
            )
            if planet_center is None:
                planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1.0, 0.0])
            else:
                planet_center_orig = planet_center

            tracking_point = _finite_point_array(key_points.get("tracking_point"))
            if tracking_point is None:
                tracking_point_orig = planet_center_orig + arm_length * np.array([1.0, 0.0])
            else:
                tracking_point_orig = tracking_point

        planet_count = min(max(int(round(finite_float(params.get("planet_count"), 1.0))), 1), 4)
        orbit_vector = planet_center_orig - sun_center_orig
        orbit_radius = float(np.linalg.norm(orbit_vector))
        if not math.isfinite(orbit_radius) or orbit_radius <= 1e-6:
            orbit_radius = r_sun + r_planet
            orbit_vector = np.array([orbit_radius, 0.0], dtype=float)
        base_angle = math.atan2(float(orbit_vector[1]), float(orbit_vector[0]))
        planet_centers_orig = [
            planet_center_orig
            if index == 0
            else sun_center_orig
            + orbit_radius
            * np.array(
                [
                    math.cos(base_angle + (2.0 * math.pi * index / planet_count)),
                    math.sin(base_angle + (2.0 * math.pi * index / planet_count)),
                ],
                dtype=float,
            )
            for index in range(planet_count)
        ]

        # Transform to scene coordinates
        sun_center_scene = to_scene_coords(sun_center_orig)
        planet_centers_scene = [to_scene_coords(center) for center in planet_centers_orig]
        planet_center_scene = planet_centers_scene[0]
        tracking_point_scene = to_scene_coords(tracking_point_orig)

        # Calculate screen radii for proper scaling
        sun_edge_orig = sun_center_orig + np.array([r_sun, 0])
        planet_edge_orig = planet_center_orig + np.array([r_planet, 0])

        sun_edge_scene = to_scene_coords(sun_edge_orig)
        planet_edge_scene = to_scene_coords(planet_edge_orig)

        r_sun_screen = QLineF(sun_center_scene, sun_edge_scene).length()
        r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

        sun_teeth = int(round(finite_float(params.get("sun_teeth"), 12.0)))
        planet_teeth = int(round(finite_float(params.get("planet_teeth"), 12.0)))
        ring_inner = QLineF(sun_center_scene, planet_center_scene).length() + r_planet_screen * 0.55
        ring_outer = ring_inner + max(7.0, min(16.0, r_planet_screen * 0.45))
        decorative_items: list[QGraphicsItem] = []
        ring_path = _require_graphics_item(
            self.scene.addPath(
                annulus_path(sun_center_scene, ring_outer, ring_inner),
                _cosmetic_pen("#5d6d7e", 3),
                QBrush(QColor(180, 185, 190, 80)),
            )
        )
        ring_path.setZValue(10)
        decorative_items.append(ring_path)

        for start, end in radial_tick_lines(sun_center_scene, ring_inner - 2, ring_inner + 4, 36):
            tick = _require_graphics_item(
                self.scene.addLine(QLineF(start, end), _cosmetic_pen("#5d6d7e", 1))
            )
            tick.setZValue(11)
            decorative_items.append(tick)

        # Create sun gear (stationary)
        sun_color = QColor("#7f8c8d")  # Gray
        sun_gear = _require_graphics_item(
            self.scene.addPolygon(
                gear_outline_polygon(sun_center_scene, r_sun_screen, sun_teeth, 0.0),
                _cosmetic_pen(sun_color, 4),
                QBrush(sun_color.lighter(150)),
            )
        )
        sun_gear.setData(0, "planetary_sun_body")
        sun_gear.setZValue(14)  # Base level, above parts
        visual_items.append(sun_gear)

        # Create primary planet gear (orbiting)
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = _require_graphics_item(
            self.scene.addPolygon(
                gear_outline_polygon(planet_center_scene, r_planet_screen, planet_teeth, 0.0),
                _cosmetic_pen(planet_color, 4),
                QBrush(planet_color.lighter(150)),
            )
        )
        planet_gear.setData(0, "planetary_planet_1_body")
        planet_gear.setZValue(15)  # Above base level
        visual_items.append(planet_gear)

        # Create arm connecting planet center to tracking point
        arm_color = QColor("#f39c12")  # Golden
        arm_line = _require_graphics_item(
            self.scene.addLine(
                QLineF(planet_center_scene, tracking_point_scene), _cosmetic_pen(arm_color, 3)
            )
        )
        arm_line.setData(0, "planetary_output_arm")
        arm_line.setZValue(15)
        visual_items.append(arm_line)

        # Create tracking point marker
        tracking_color = QColor("#e74c3c")  # Red
        tracking_marker = _require_graphics_item(
            self.scene.addEllipse(
                tracking_point_scene.x() - 8,
                tracking_point_scene.y() - 8,
                16,
                16,
                _cosmetic_pen(tracking_color, 2),
                QBrush(tracking_color),
            )
        )
        tracking_marker.setData(0, "planetary_output_pin")
        tracking_marker.setZValue(20)
        visual_items.append(tracking_marker)

        # Create center markers for pivots
        center_color = QColor("#3498db")  # Blue

        # Sun center marker
        sun_center_marker = _require_graphics_item(
            self.scene.addEllipse(
                sun_center_scene.x() - 6,
                sun_center_scene.y() - 6,
                12,
                12,
                _cosmetic_pen(center_color.darker(150), 2),
                QBrush(center_color),
            )
        )
        sun_center_marker.setData(0, "planetary_sun_center")
        sun_center_marker.setZValue(25)
        visual_items.append(sun_center_marker)

        # Planet center marker
        planet_center_marker = _require_graphics_item(
            self.scene.addEllipse(
                planet_center_scene.x() - 4,
                planet_center_scene.y() - 4,
                8,
                8,
                _cosmetic_pen(center_color.darker(150), 1),
                QBrush(center_color.lighter(130)),
            )
        )
        planet_center_marker.setData(0, "planetary_planet_1_center")
        planet_center_marker.setZValue(25)
        visual_items.append(planet_center_marker)

        carrier_color = QColor("#d4a017")
        for index, center_scene in enumerate(planet_centers_scene, start=1):
            carrier_line = _require_graphics_item(
                self.scene.addLine(
                    QLineF(sun_center_scene, center_scene),
                    _cosmetic_pen(carrier_color, 2),
                )
            )
            carrier_line.setData(0, f"planetary_carrier_{index}")
            carrier_line.setZValue(13)
            visual_items.append(carrier_line)

        for index, center_scene in enumerate(planet_centers_scene[1:], start=2):
            extra_planet = _require_graphics_item(
                self.scene.addPolygon(
                    gear_outline_polygon(center_scene, r_planet_screen, planet_teeth, 0.0),
                    _cosmetic_pen(planet_color, 4),
                    QBrush(planet_color.lighter(150)),
                )
            )
            extra_planet.setData(0, f"planetary_planet_{index}_body")
            extra_planet.setZValue(15)
            visual_items.append(extra_planet)

            extra_marker = _require_graphics_item(
                self.scene.addEllipse(
                    center_scene.x() - 4,
                    center_scene.y() - 4,
                    8,
                    8,
                    _cosmetic_pen(center_color.darker(150), 1),
                    QBrush(center_color.lighter(130)),
                )
            )
            extra_marker.setData(0, f"planetary_planet_{index}_center")
            extra_marker.setZValue(25)
            visual_items.append(extra_marker)

        hole_specs: list[tuple[QPointF, float, str]] = [
            (sun_center_scene, r_sun_screen, "planetary_sun_hole"),
        ]
        hole_specs.extend(
            (center_scene, r_planet_screen, f"planetary_planet_{index}_hole")
            for index, center_scene in enumerate(planet_centers_scene, start=1)
        )
        for center_scene, radius_screen, prefix in hole_specs:
            hole_radius = gear_hole_radius(radius_screen)
            for index, hole_center in enumerate(
                gear_attachment_hole_centers(center_scene, radius_screen, count=4)
            ):
                hole = _require_graphics_item(
                    self.scene.addEllipse(
                        hole_center.x() - hole_radius,
                        hole_center.y() - hole_radius,
                        hole_radius * 2,
                        hole_radius * 2,
                        _cosmetic_pen("#5c4033", 1.3),
                        QBrush(QColor(255, 255, 255, 225)),
                    )
                )
                hole.setData(0, f"{prefix}_{index}")
                hole.setZValue(18)
                visual_items.append(hole)

        visual_items.extend(decorative_items)

        return visual_items

    def _get_scene_transform_function(self, layer_data: dict) -> _SceneTransform | None:
        """
        Returns None - transform function is provided by caller via layer_data.

        The scene transform is injected through layer_data["transform_function"]
        by the parent tab, maintaining proper dependency inversion.
        """
        return None
