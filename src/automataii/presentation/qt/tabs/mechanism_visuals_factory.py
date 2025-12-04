"""
Factory class for creating visual representations of mechanisms.

This class encapsulates all mechanism visual creation logic, providing a clean
separation between the main tab logic and visual rendering concerns.
"""

import logging
import math
import xml.etree.ElementTree as ET

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


def _cosmetic_pen(
    color: QColor | str,
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


class MechanismVisualsFactory:
    """Factory for creating visual representations of mechanisms."""

    def __init__(self, scene: QGraphicsScene):
        """Initialize the factory with a graphics scene.

        Args:
            scene: The QGraphicsScene where visual items will be added
        """
        self.scene = scene

    def create_4bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
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

        # Use initial positions from simulation data if available
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0:
                # Use first frame from simulation
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

                # Calculate initial coupler point position (same as dataset)
                # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
                coupler_point_x = params.get("coupler_point_x") or params.get("p_x", 0.0)
                coupler_point_y = params.get("coupler_point_y") or params.get("p_y", 0.0)

                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                else:
                    p_coupler = p3
            else:
                return []
        else:
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

            # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
            coupler_point_x = params.get("coupler_point_x") or params.get("p_x", l3/2)
            coupler_point_y = params.get("coupler_point_y") or params.get("p_y", 0.0)

            coupler_vec = p4 - p3
            coupler_length = np.linalg.norm(coupler_vec)
            if coupler_length > 0:
                coupler_unit = coupler_vec / coupler_length
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
            else:
                p_coupler = p3

        # Transform all points to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)

        visual_items = []

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
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2

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
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]  # Orange, Orange, Red, Blue
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Outer circle
            outer_pivot = self.scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                _cosmetic_pen(color.darker(150), 2),
                QBrush(color)
            )
            outer_pivot.setZValue(Z_MECHANISM_PIVOT)
            outer_pivot.setToolTip(name)  # Add tooltip for identification
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = self.scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )
            inner_pivot.setZValue(Z_MECHANISM_PIVOT + 1)
            visual_items.append(inner_pivot)

        # Add coupler point marker (red dot)
        coupler_marker = self.scene.addEllipse(
            p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8,
            _cosmetic_pen("#ff0000", 2),
            QBrush(QColor("#ff0000"))
        )
        coupler_marker.setZValue(Z_SELECTION_MARKER)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)
        # --- Diagnostics overlay: Transmission angle (guardrail) ---
        try:
            jp = mechanism_data.get("full_simulation_data", {}).get("joint_positions", {})
            if jp and all(k in jp and len(jp[k]) > 0 for k in ("p1_positions", "p2_positions", "p3_positions", "p4_positions")):
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
                halo = self.scene.addEllipse(halo_center.x() - radius, halo_center.y() - radius, radius*2, radius*2, _cosmetic_pen(color, 5), QBrush(Qt.BrushStyle.NoBrush))
                halo.setZValue(30)
                visual_items.append(halo)
                label = self.scene.addText(f"μ_min={mu_min:.0f}° {status}")
                label.setDefaultTextColor(color)
                label.setPos(halo_center.x() + radius + 6, halo_center.y() - 8)
                label.setZValue(31)
                visual_items.append(label)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)


        return visual_items

    def create_5bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation for 5-bar linkage mechanism."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)

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

    def create_6bar_linkage_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation for 6-bar linkage mechanism (Stephenson Type I)."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)

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

    def create_cam_visuals(self, mechanism_data: dict, transform_function=None, character_position=None) -> list[QGraphicsItem]:
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
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        follower_rod_length = params.get("follower_rod_length", 40.0)

        # Scale CAM appropriately for character interaction
        # Use stored scaling factors if available, otherwise use defaults
        cam_scale_factor = mechanism_data.get('cam_scale_factor', 1.0)  # Normal CAM size
        rod_length_multiplier = mechanism_data.get('rod_length_multiplier', 1.0)  # Direct rod length control

        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Build analytic pear-cam profile from parameters (fallback to sensible defaults)
        rise_deg = float(params.get("rise_deg", 90.0))
        high_dwell_deg = float(params.get("high_dwell_deg", 60.0))
        # Accept either explicit low_dwell or return; compute the missing one to satisfy 360°
        if "low_dwell_deg" in params:
            low_dwell_deg = float(params.get("low_dwell_deg", 180.0))
            # Clamp to valid range
            low_dwell_deg = max(0.0, min(360.0, low_dwell_deg))
        else:
            # If return provided, derive low_dwell; else use default 180°
            return_deg = float(params.get("return_deg", 30.0))
            low_dwell_deg = max(0.0, 360.0 - (rise_deg + high_dwell_deg + return_deg))

        align_max_deg = float(params.get("align_max_deg", 90.0))

        # Guard against invalid sums
        total = rise_deg + high_dwell_deg + low_dwell_deg
        if total > 360.0:
            # Scale dwells proportionally to fit
            scale = 360.0 / max(1e-6, total)
            rise_deg *= scale
            high_dwell_deg *= scale
            low_dwell_deg *= scale

        cam_points_local = self._build_pear_cam_profile(
            base_radius=scaled_base_radius,
            eccentricity=scaled_eccentricity,
            rise_deg=rise_deg,
            high_dwell_deg=high_dwell_deg,
            dwell_low_deg=low_dwell_deg,
            align_max_to_deg=align_max_deg,
            num_samples=360,
        )
        mechanism_data['cam_points_local'] = cam_points_local

        # Determine placement: align follower center with bottom of user's path
        cam_pos = mechanism_data.get('cam_position')
        try:
            gen_path = mechanism_data.get('generated_path')
            if gen_path is not None:
                brect = gen_path.boundingRect()
                path_x_center = float(brect.center().x())
                path_y_bottom = float(brect.bottom())
                local_y_max = float(np.max(cam_points_local[:, 1]))
                follower_local_y = local_y_max + scaled_rod_length
                cam_pos = [path_x_center, path_y_bottom - follower_local_y]
                mechanism_data['cam_position'] = cam_pos
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        # Define mapping as base transform + offset so scale is preserved
        base_map = transform_function or self._get_scene_transform_function(mechanism_data)
        if base_map is None:
            return []
        try:
            if gen_path is not None:
                brect = gen_path.boundingRect()
                path_x_center = float(brect.center().x())
                path_y_bottom = float(brect.bottom())
                local_y_max = float(np.max(cam_points_local[:, 1]))
                # Place cam such that its top (local_y_max) touches path bottom; ignore rod length for placement
                follower_local = np.array([0.0, local_y_max])
                follower_scene_raw = base_map(follower_local)
                dx = path_x_center - follower_scene_raw.x()
                dy = path_y_bottom - follower_scene_raw.y()
                def cam_to_scene_coords(p):
                    if p is None or len(p) != 2:
                        return QPointF(follower_scene_raw.x() + dx, follower_scene_raw.y() + dy)
                    mapped = base_map(p)
                    return QPointF(mapped.x() + dx, mapped.y() + dy)
                mechanism_data['cam_transform_function'] = cam_to_scene_coords
            else:
                mechanism_data['cam_transform_function'] = base_map
        except Exception:
            mechanism_data['cam_transform_function'] = base_map
        # Bind local mapper for convenience
        cam_to_scene_coords = mechanism_data['cam_transform_function']
        # Initial follower position at topmost y of unrotated cam (ignore rod length for default placement)
        y_max = float(np.max(cam_points_local[:, 1]))
        follower_pos_orig = np.array([0.0, y_max], dtype=float)
        cam_center_orig = np.array([0.0, 0.0], dtype=float)

        # Store scaling factors for consistency in animation and parametric editing
        mechanism_data['cam_scale_factor'] = cam_scale_factor
        mechanism_data['rod_length_multiplier'] = rod_length_multiplier

        # Transform key points to scene coordinates
        cam_center_scene = cam_to_scene_coords(cam_center_orig)
        follower_scene = cam_to_scene_coords(follower_pos_orig)

        # Build cam polygon
        cam_polygon_points = []
        pts = mechanism_data.get('cam_points_local')
        for p in pts:
            scene_point = cam_to_scene_coords(p)
            cam_polygon_points.append(scene_point)

        # Create QPolygonF from points
        cam_polygon = QPolygonF(cam_polygon_points)

        visual_items = []

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

        # Create follower with appropriate size
        follower_color = QColor("#ff9800")  # Orange
        follower_width, follower_height = 20, 15  # Larger for visibility
        follower_body = QGraphicsRectItem(
            follower_scene.x() - follower_width/2,
            follower_scene.y() - follower_height/2,
            follower_width,
            follower_height
        )
        follower_body.setPen(_cosmetic_pen(follower_color.darker(120), 2))
        follower_body.setBrush(QBrush(follower_color))
        follower_body.setZValue(16)  # Above cam
        follower_body.setToolTip("Follower - Moves up/down as cam rotates")
        self.scene.addItem(follower_body)
        visual_items.append(follower_body)

        # Create cam center marker (rotation point)
        cam_center_color = QColor("#f44336")  # Red for rotation center
        cam_center_marker = QGraphicsEllipseItem(
            cam_center_scene.x() - 5, cam_center_scene.y() - 5, 10, 10
        )
        cam_center_marker.setPen(_cosmetic_pen(cam_center_color.darker(150), 2))
        cam_center_marker.setBrush(QBrush(cam_center_color))
        cam_center_marker.setZValue(20)  # Top level
        cam_center_marker.setToolTip("Cam Center - Rotation axis")
        self.scene.addItem(cam_center_marker)
        visual_items.append(cam_center_marker)

        # Create follower rod line from cam top (support point) to follower
        rod_pen = _cosmetic_pen("#9e9e9e", 3, Qt.PenStyle.DashLine)
        pts = mechanism_data.get('cam_points_local')
        y_max = float(np.max(pts[:, 1]))
        cam_top_scene = cam_to_scene_coords(np.array([0.0, y_max]))
        follower_rod = QGraphicsLineItem(
            cam_top_scene.x(), cam_top_scene.y(),
            follower_scene.x(), follower_scene.y()
        )
        follower_rod.setPen(rod_pen)
        follower_rod.setZValue(14)  # Below cam but above parts
        follower_rod.setToolTip("Connecting Rod")
        self.scene.addItem(follower_rod)
        visual_items.append(follower_rod)

        # Store follower's fixed X position in scene coordinates for vertical motion constraint
        try:
            mechanism_data['follower_fixed_x_scene'] = float(follower_scene.x())
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        # Return visual items
        # --- Diagnostics overlay: High-curvature highlight on cam profile ---
        try:
            pts = cam_points_local
            if pts is not None and len(pts) >= 5 and 'cam_transform_function' in mechanism_data:
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
                    tf = mechanism_data['cam_transform_function']
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
            return tag.split('}', 1)[-1]

        axis = None
        poly_pts: list[tuple[float, float]] = []

        for elem in root.iter():
            tag = strip(elem.tag)
            if tag == 'circle' and axis is None:
                cx = float(elem.attrib.get('cx', '0'))
                cy = float(elem.attrib.get('cy', '0'))
                axis = np.array([cx, cy], dtype=float)
            elif tag == 'path' and ('layer-cam' in (elem.get('id') or '') or True):
                d = elem.attrib.get('d', '')
                if not d:
                    continue
                # Very simple M/L tokenizer
                tokens = d.replace(',', ' ').split()
                i = 0
                while i < len(tokens):
                    cmd = tokens[i]
                    if cmd in ('M', 'L') and i + 2 < len(tokens):
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

    def _build_cam_from_template(self, template_points: np.ndarray, base_radius: float, eccentricity: float, num_samples: int = 180) -> np.ndarray:
        """Build a cam polygon from a template profile using normalized radial mapping.

        - Compute support function r_templ(θ) = max(dot(p, uθ)) over template points (convex envelope)
        - Normalize: s(θ) = (r_templ(θ) - min(r_templ)) / (max(r_templ) - min(r_templ) + eps)
        - New radius: r(θ) = base_radius + eccentricity * s(θ)
        - Return polygon points: r(θ) * [cosθ, sinθ]
        """
        if template_points is None or len(template_points) < 3:
            # Fallback circular cam
            pts = []
            for i in range(num_samples + 1):
                theta = 2 * np.pi * i / num_samples
                pts.append([base_radius * np.cos(theta), base_radius * np.sin(theta)])
            return np.array(pts, dtype=float)

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
        pts = np.stack([r_new * np.cos(thetas), r_new * np.sin(thetas)], axis=1)
        return pts.astype(float)

    def _build_pear_cam_profile(
        self,
        base_radius: float,
        eccentricity: float,
        rise_deg: float = 90.0,
        high_dwell_deg: float = 60.0,
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
        rise = np.deg2rad(rise_deg)
        dwell_high = np.deg2rad(high_dwell_deg)
        dwell_low = np.deg2rad(dwell_low_deg)
        total = 2 * np.pi
        fall = max(0.0, total - (rise + dwell_high + dwell_low))

        # Phase reference: ensure max radius at align_max_to_deg
        theta0 = np.deg2rad(align_max_to_deg)
        seg1_end = theta0 + rise
        seg2_end = seg1_end + dwell_high
        seg3_end = seg2_end + fall

        thetas = np.linspace(0, 2 * np.pi, num_samples, endpoint=False)
        s = np.zeros_like(thetas)
        for i, t in enumerate(thetas):
            rel = (t - theta0) % (2 * np.pi) + theta0
            if rel < seg1_end:  # rise 0->1
                u = (rel - theta0) / rise if rise > 0 else 1.0
                s[i] = 0.5 * (1 - np.cos(np.pi * u))
            elif rel < seg2_end:  # high dwell at 1
                s[i] = 1.0
            elif rel < seg3_end:  # fall 1->0
                u = (rel - seg2_end) / fall if fall > 0 else 1.0
                s[i] = 0.5 * (1 + np.cos(np.pi * u))
            else:  # low dwell at 0
                s[i] = 0.0

        r = base_radius + eccentricity * s
        pts = np.stack([r * np.cos(thetas), r * np.sin(thetas)], axis=1)
        return pts.astype(float)

    def create_gear_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation of gear train mechanism."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        # Gear centers in original coordinates - match dataset generator
        distance = r1 + r2  # Gears touching
        gear1_center_orig = np.array([0, 0])
        gear2_center_orig = np.array([distance, 0])

        # Transform to scene coordinates
        gear1_center_scene = to_scene_coords(gear1_center_orig)
        gear2_center_scene = to_scene_coords(gear2_center_orig)

        visual_items = []

        # Create gear 1 (driver) with proper screen coordinates
        gear1_color = QColor("#3498db")  # Blue

        # Calculate screen radius for gear1
        gear1_edge_orig = gear1_center_orig + np.array([r1, 0])
        gear1_edge_scene = to_scene_coords(gear1_edge_orig)
        r1_screen = QLineF(gear1_center_scene, gear1_edge_scene).length()

        gear1_body = self.scene.addEllipse(
            gear1_center_scene.x() - r1_screen, gear1_center_scene.y() - r1_screen,
            r1_screen * 2, r1_screen * 2,
            _cosmetic_pen(gear1_color, 4),
            QBrush(gear1_color.lighter(170))
        )
        gear1_body.setZValue(15)  # Above parts
        visual_items.append(gear1_body)

        # Create gear 2 (driven) with proper screen coordinates
        gear2_color = QColor("#2ecc71")  # Green

        # Calculate screen radius for gear2
        gear2_edge_orig = gear2_center_orig + np.array([r2, 0])
        gear2_edge_scene = to_scene_coords(gear2_edge_orig)
        r2_screen = QLineF(gear2_center_scene, gear2_edge_scene).length()

        gear2_body = self.scene.addEllipse(
            gear2_center_scene.x() - r2_screen, gear2_center_scene.y() - r2_screen,
            r2_screen * 2, r2_screen * 2,
            _cosmetic_pen(gear2_color, 4),
            QBrush(gear2_color.lighter(170))
        )
        gear2_body.setZValue(15)  # Above parts
        visual_items.append(gear2_body)

        # Create rotation indicators (lines that will rotate)
        indicator_color = QColor("#ffffff")  # White lines

        # Gear 1 indicator (initially horizontal) - use screen-space radius
        gear1_indicator = self.scene.addLine(
            gear1_center_scene.x(), gear1_center_scene.y(),
            gear1_center_scene.x() + r1_screen, gear1_center_scene.y(),
            _cosmetic_pen(indicator_color, 3)
        )
        gear1_indicator.setZValue(15)
        visual_items.append(gear1_indicator)

        # Gear 2 indicator (initially horizontal) - use screen-space radius
        gear2_indicator = self.scene.addLine(
            gear2_center_scene.x(), gear2_center_scene.y(),
            gear2_center_scene.x() + r2_screen, gear2_center_scene.y(),
            _cosmetic_pen(indicator_color, 3)
        )
        gear2_indicator.setZValue(15)
        visual_items.append(gear2_indicator)

        # Create center pivots
        pivot_color = QColor("#f39c12")  # Orange

        # Gear 1 center
        gear1_pivot = self.scene.addEllipse(
            gear1_center_scene.x() - 8, gear1_center_scene.y() - 8, 16, 16,
            _cosmetic_pen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear1_pivot.setZValue(20)
        visual_items.append(gear1_pivot)

        # Gear 2 center
        gear2_pivot = self.scene.addEllipse(
            gear2_center_scene.x() - 8, gear2_center_scene.y() - 8, 16, 16,
            _cosmetic_pen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear2_pivot.setZValue(20)
        visual_items.append(gear2_pivot)
        # --- Diagnostics overlay: pitch circles and center distance check ---
        try:
            dashed = _cosmetic_pen("#7f8c8d", 1, Qt.PenStyle.DashLine)
            pc1 = self.scene.addEllipse(gear1_center_scene.x() - r1_screen, gear1_center_scene.y() - r1_screen, r1_screen*2, r1_screen*2, dashed)
            pc1.setZValue(12)
            visual_items.append(pc1)
            pc2 = self.scene.addEllipse(gear2_center_scene.x() - r2_screen, gear2_center_scene.y() - r2_screen, r2_screen*2, r2_screen*2, dashed)
            pc2.setZValue(12)
            visual_items.append(pc2)
            d_orig = float(np.linalg.norm(gear2_center_orig - gear1_center_orig))
            desired = float(r1 + r2)
            mismatch = abs(d_orig - desired)
            if mismatch > 0.5:
                warn = self.scene.addText(f"Center distance off by {mismatch:.1f}")
                warn.setDefaultTextColor(QColor("#e74c3c"))
                warn.setPos((gear1_center_scene.x()+gear2_center_scene.x())/2.0, gear1_center_scene.y()-20)
                warn.setZValue(30)
                visual_items.append(warn)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)


        return visual_items

    def create_planetary_gear_visuals(self, mechanism_data: dict, transform_function=None) -> list[QGraphicsItem]:
        """Create visual representation of planetary gear mechanism."""
        to_scene_coords = transform_function or self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        visual_items = []

        # Try to get initial positions from simulation data
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        gear_positions = full_sim_data.get("gear_positions", {})

        if gear_positions and "sun_centers" in gear_positions and len(gear_positions["sun_centers"]) > 0:
            # Use simulation data for accurate positioning
            frame_idx = 0
            sun_center_orig = np.array(gear_positions["sun_centers"][frame_idx])
            planet_center_orig = np.array(gear_positions["planet_centers"][frame_idx])
            tracking_point_orig = np.array(gear_positions["tracking_points"][frame_idx])
        else:
            # Fallback to calculated initial positions
            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1, 0])  # Initial position
            tracking_point_orig = planet_center_orig + arm_length * np.array([1, 0])  # Initial tracking point

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

        # Create sun gear (stationary)
        sun_color = QColor("#7f8c8d")  # Gray
        sun_gear = self.scene.addEllipse(
            sun_center_scene.x() - r_sun_screen, sun_center_scene.y() - r_sun_screen,
            r_sun_screen * 2, r_sun_screen * 2,
            _cosmetic_pen(sun_color, 4),
            QBrush(sun_color.lighter(150))
        )
        sun_gear.setZValue(14)  # Base level, above parts
        visual_items.append(sun_gear)

        # Create planet gear (orbiting)
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = self.scene.addEllipse(
            planet_center_scene.x() - r_planet_screen, planet_center_scene.y() - r_planet_screen,
            r_planet_screen * 2, r_planet_screen * 2,
            _cosmetic_pen(planet_color, 4),
            QBrush(planet_color.lighter(150))
        )
        planet_gear.setZValue(15)  # Above base level
        visual_items.append(planet_gear)

        # Create arm connecting planet center to tracking point
        arm_color = QColor("#f39c12")  # Golden
        arm_line = self.scene.addLine(
            QLineF(planet_center_scene, tracking_point_scene),
            _cosmetic_pen(arm_color, 3)
        )
        arm_line.setZValue(15)
        visual_items.append(arm_line)

        # Create tracking point marker
        tracking_color = QColor("#e74c3c")  # Red
        tracking_marker = self.scene.addEllipse(
            tracking_point_scene.x() - 8, tracking_point_scene.y() - 8, 16, 16,
            _cosmetic_pen(tracking_color, 2),
            QBrush(tracking_color)
        )
        tracking_marker.setZValue(20)
        visual_items.append(tracking_marker)

        # Create center markers for pivots
        center_color = QColor("#3498db")  # Blue

        # Sun center marker
        sun_center_marker = self.scene.addEllipse(
            sun_center_scene.x() - 6, sun_center_scene.y() - 6, 12, 12,
            _cosmetic_pen(center_color.darker(150), 2),
            QBrush(center_color)
        )
        sun_center_marker.setZValue(25)
        visual_items.append(sun_center_marker)

        # Planet center marker
        planet_center_marker = self.scene.addEllipse(
            planet_center_scene.x() - 4, planet_center_scene.y() - 4, 8, 8,
            _cosmetic_pen(center_color.darker(150), 1),
            QBrush(center_color.lighter(130))
        )
        planet_center_marker.setZValue(25)
        visual_items.append(planet_center_marker)

        return visual_items

    def _get_scene_transform_function(self, layer_data: dict):
        """
        Returns None - transform function is provided by caller via layer_data.

        The scene transform is injected through layer_data["transform_function"]
        by the parent tab, maintaining proper dependency inversion.
        """
        return None
