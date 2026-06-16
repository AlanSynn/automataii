"""
Linkage Visualizer - Visual representation for 4-bar, 5-bar, and 6-bar linkages.

Extracted from MechanismVisualsFactory to support polymorphic dispatch.
Handles creation and update of linkage mechanism visuals.

Design Pattern: Strategy (implements MechanismVisualizerProtocol)
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QLineF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
)

from automataii.config.z_indices import Z_MECHANISM_PIVOT, Z_SELECTION_MARKER
from automataii.presentation.qt.mechanism_parameter_utils import finite_float, finite_param

from .protocol import BaseMechanismVisualizer

if TYPE_CHECKING:
    from PyQt6.QtCore import QPointF


class FourBarVisualizer(BaseMechanismVisualizer):
    """Visualizer for 4-bar linkage mechanisms."""

    @property
    def mechanism_type(self) -> str:
        return "4_bar_linkage"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation of 4-bar linkage with triangular coupler."""
        to_scene_coords = self._get_transform_function(mechanism_data, transform_function)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        if not all([l1 is not None, l2 is not None, l3 is not None, l4 is not None]):
            return []

        # Get joint positions
        p1, p2, p3, p4, p_coupler = self._get_joint_positions(params, mechanism_data)
        if p1 is None:
            return []

        # Transform to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)

        visual_items: list[QGraphicsItem] = []

        # Create links
        self._create_links(visual_items, p1_t, p2_t, p3_t, p4_t, p_coupler_t, p3, p4, p_coupler)

        # Create pivots
        self._create_pivots(visual_items, p1_t, p2_t, p3_t, p4_t, p_coupler_t)

        if bool(kwargs.get("show_diagnostics", False)):
            self._add_transmission_angle_overlay(visual_items, mechanism_data, p2_t)

        return visual_items

    def _get_joint_positions(
        self,
        params: dict[str, Any],
        mechanism_data: dict[str, Any],
    ) -> tuple[Any, ...]:
        """Extract joint positions from simulation data or calculate fallback."""
        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0:
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

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

                return p1, p2, p3, p4, p_coupler

        # Fallback calculation
        p1 = np.array([0, 0])
        p2 = np.array([l1, 0])
        p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])
        d = np.linalg.norm(p2 - p3)
        # Guard against division by zero and check linkage feasibility
        if d < 1e-10 or not (abs(l3 - l4) <= d <= l3 + l4):
            return None, None, None, None, None

        a = (l3**2 - l4**2 + d**2) / (2 * d)
        h = math.sqrt(max(0, l3**2 - a**2))
        p3_p2_unit = (p2 - p3) / d
        midpoint = p3 + a * p3_p2_unit
        p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
        default_coupler_x = finite_float(l3, 0.0) / 2.0
        coupler_point_x = finite_param(params, "coupler_point_x", "p_x", default=default_coupler_x)
        coupler_point_y = finite_param(params, "coupler_point_y", "p_y", default=0.0)

        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)
        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
        else:
            p_coupler = p3

        return p1, p2, p3, p4, p_coupler

    def _create_links(
        self,
        visual_items: list[QGraphicsItem],
        p1_t: QPointF,
        p2_t: QPointF,
        p3_t: QPointF,
        p4_t: QPointF,
        p_coupler_t: QPointF,
        p3: np.ndarray,
        p4: np.ndarray,
        p_coupler: np.ndarray,
    ) -> None:
        """Create link visual items."""
        # Driver link
        driver_link = QGraphicsLineItem(QLineF(p1_t, p3_t))
        driver_pen = QPen(QColor("#e74c3c"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        driver_link.setPen(driver_pen)
        driver_link.setZValue(15)
        self.scene.addItem(driver_link)
        visual_items.append(driver_link)

        # Follower link
        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_pen = QPen(QColor("#f39c12"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        follower_link.setPen(follower_pen)
        follower_link.setZValue(15)
        self.scene.addItem(follower_link)
        visual_items.append(follower_link)

        # Coupler (triangle or line)
        area = (
            abs(
                p3[0] * (p4[1] - p_coupler[1])
                + p4[0] * (p_coupler[1] - p3[1])
                + p_coupler[0] * (p3[1] - p4[1])
            )
            / 2
        )

        if area < 1e-3:  # Collinear
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_pen = QPen(QColor("#2ecc71"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            coupler_line.setPen(coupler_pen)
            coupler_line.setZValue(16)
            self.scene.addItem(coupler_line)
            visual_items.append(coupler_line)
        else:  # Triangle
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)
            coupler_triangle = QGraphicsPolygonItem(triangle_polygon)
            triangle_pen = QPen(QColor("#2ecc71"), 2, Qt.PenStyle.SolidLine)
            triangle_brush = QBrush(QColor("#2ecc71").lighter(160))
            triangle_brush.setStyle(Qt.BrushStyle.SolidPattern)
            coupler_triangle.setPen(triangle_pen)
            coupler_triangle.setBrush(triangle_brush)
            coupler_triangle.setZValue(16)
            coupler_triangle.setOpacity(0.8)
            self.scene.addItem(coupler_triangle)
            visual_items.append(coupler_triangle)

        # Ground link
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_pen = QPen(QColor("#9b59b6"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        ground_link.setPen(ground_pen)
        ground_link.setZValue(14)
        self.scene.addItem(ground_link)
        visual_items.append(ground_link)

    def _create_pivots(
        self,
        visual_items: list[QGraphicsItem],
        p1_t: QPointF,
        p2_t: QPointF,
        p3_t: QPointF,
        p4_t: QPointF,
        p_coupler_t: QPointF,
    ) -> None:
        """Create pivot visual items."""
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Outer circle
            outer_pivot = self.scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16, QPen(color.darker(150), 2), QBrush(color)
            )
            outer_pivot.setZValue(Z_MECHANISM_PIVOT)
            outer_pivot.setToolTip(name)
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = self.scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8, QPen(Qt.PenStyle.NoPen), QBrush(color.lighter(150))
            )
            inner_pivot.setZValue(Z_MECHANISM_PIVOT + 1)
            visual_items.append(inner_pivot)

        # Coupler marker
        coupler_marker = self.scene.addEllipse(
            p_coupler_t.x() - 4,
            p_coupler_t.y() - 4,
            8,
            8,
            QPen(QColor("#ff0000"), 2),
            QBrush(QColor("#ff0000")),
        )
        coupler_marker.setZValue(Z_SELECTION_MARKER)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)

    def _add_transmission_angle_overlay(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict[str, Any],
        p2_t: QPointF,
    ) -> None:
        """Add transmission angle diagnostic overlay."""
        try:
            jp = mechanism_data.get("full_simulation_data", {}).get("joint_positions", {})
            if not jp:
                return
            if not all(
                k in jp and len(jp[k]) > 0
                for k in ("p1_positions", "p2_positions", "p3_positions", "p4_positions")
            ):
                return

            mu_min = 180.0
            for i in range(min(len(jp["p3_positions"]), len(jp["p4_positions"]))):
                p3_i = np.array(jp["p3_positions"][i], dtype=float)
                p4_i = np.array(jp["p4_positions"][i], dtype=float)
                p2_i = np.array(jp["p2_positions"][i], dtype=float)
                v_c = p4_i - p3_i
                v_r = p4_i - p2_i
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

            radius = 24.0
            halo = self.scene.addEllipse(
                p2_t.x() - radius,
                p2_t.y() - radius,
                radius * 2,
                radius * 2,
                QPen(color, 5, Qt.PenStyle.SolidLine),
                QBrush(Qt.BrushStyle.NoBrush),
            )
            halo.setZValue(30)
            visual_items.append(halo)

            label = self.scene.addText(f"μ_min={mu_min:.0f}° {status}")
            label.setDefaultTextColor(color)
            label.setPos(p2_t.x() + radius + 6, p2_t.y() - 8)
            label.setZValue(31)
            visual_items.append(label)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update 4-bar visuals for animation. Delegates to MechanismVisualAnimator."""
        # Animation updates are handled by MechanismVisualAnimator
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data from parameters."""
        # Simulation generation is handled by domain layer
        from automataii.domain.mechanisms.linkages.fourbar.compute import compute_4bar_positions

        return compute_4bar_positions(params)


class FiveBarVisualizer(BaseMechanismVisualizer):
    """Visualizer for 5-bar linkage mechanisms."""

    @property
    def mechanism_type(self) -> str:
        return "5_bar_linkage"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation for 5-bar linkage mechanism."""
        visual_items: list[QGraphicsItem] = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = self._get_transform_function(mechanism_data, transform_function)

            if not to_scene_coords:
                return visual_items

            # Get joint positions
            p1, p2, p3, p4, p5 = self._get_joint_positions(params, mechanism_data)

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)

            # Create links
            pen = QPen(QColor(100, 100, 200), 3)

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
            ground_pen = QPen(QColor(50, 50, 50), 4)
            ground_link = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground_link.setPen(ground_pen)
            self.scene.addItem(ground_link)
            visual_items.append(ground_link)

            # Add pivots
            self._create_pivots(visual_items, [p1_scene, p2_scene], [p3_scene, p4_scene, p5_scene])

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def _get_joint_positions(
        self,
        params: dict[str, Any],
        mechanism_data: dict[str, Any],
    ) -> tuple[np.ndarray, ...]:
        """Get joint positions from simulation or calculate defaults."""
        p1 = np.array(params.get("ground_pivot_1", [0, 0]))
        p2 = np.array(params.get("ground_pivot_2", [100, 0]))

        full_sim_data = mechanism_data.get("full_simulation_data", {})
        joint_positions = full_sim_data.get("joint_positions", {})

        if joint_positions and "p3_positions" in joint_positions:
            p3 = np.array(joint_positions["p3_positions"][0])
            p4 = np.array(joint_positions["p4_positions"][0])
            p5 = np.array(joint_positions["p5_positions"][0])
        else:
            L2 = params.get("L2", 40)
            L3 = params.get("L3", 50)
            L5 = params.get("L5", 55)

            p3 = p1 + np.array([L2, 0])
            p4 = p3 + np.array([L3 * 0.7, L3 * 0.7])
            p5 = p2 + np.array([-L5 * 0.5, L5 * 0.866])

        return p1, p2, p3, p4, p5

    def _create_pivots(
        self,
        visual_items: list[QGraphicsItem],
        ground_positions: list[QPointF],
        moving_positions: list[QPointF],
    ) -> None:
        """Create pivot markers."""
        pivot_brush = QBrush(QColor(150, 150, 255))
        ground_pivot_brush = QBrush(QColor(80, 80, 80))

        for pos in ground_positions:
            pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
            pivot.setBrush(ground_pivot_brush)
            pivot.setPen(QPen(Qt.GlobalColor.black, 2))
            self.scene.addItem(pivot)
            visual_items.append(pivot)

        for pos in moving_positions:
            pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
            pivot.setBrush(pivot_brush)
            pivot.setPen(QPen(Qt.GlobalColor.black, 1))
            self.scene.addItem(pivot)
            visual_items.append(pivot)

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update 5-bar visuals for animation."""
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data from parameters."""
        from automataii.domain.mechanisms.linkages.fivebar.compute import compute_5bar_positions

        return compute_5bar_positions(params)


class SixBarVisualizer(BaseMechanismVisualizer):
    """Visualizer for 6-bar linkage mechanisms (Stephenson Type I)."""

    @property
    def mechanism_type(self) -> str:
        return "6_bar_linkage"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation for 6-bar linkage mechanism."""
        visual_items: list[QGraphicsItem] = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = self._get_transform_function(mechanism_data, transform_function)

            if not to_scene_coords:
                return visual_items

            # Get joint positions
            p1, p2, p3, p4, p5, p6 = self._get_joint_positions(params, mechanism_data)

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)
            p6_scene = to_scene_coords(p6)

            # Create links
            pen = QPen(QColor(150, 100, 200), 3)

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
            ternary.setPen(QPen(QColor(200, 150, 100), 3))
            self.scene.addItem(ternary)
            visual_items.append(ternary)

            # Output link (p5 to p6)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p6_scene))
            output_link.setPen(pen)
            self.scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground links
            ground_pen = QPen(QColor(50, 50, 50), 4)

            ground1 = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground1.setPen(ground_pen)
            self.scene.addItem(ground1)
            visual_items.append(ground1)

            ground2 = QGraphicsLineItem(QLineF(p2_scene, p6_scene))
            ground2.setPen(QPen(QColor(50, 50, 50), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(ground2)
            visual_items.append(ground2)

            # Add pivots
            self._create_pivots(
                visual_items, [p1_scene, p2_scene, p6_scene], [p3_scene, p4_scene, p5_scene]
            )

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return visual_items

    def _get_joint_positions(
        self,
        params: dict[str, Any],
        mechanism_data: dict[str, Any],
    ) -> tuple[np.ndarray, ...]:
        """Get joint positions from simulation or calculate defaults."""
        p1 = np.array(params.get("ground_pivot_1", [0, 0]))
        p2 = np.array(params.get("ground_pivot_2", [100, 0]))
        p6 = np.array(params.get("ground_pivot_3", [50, -30]))

        full_sim_data = mechanism_data.get("full_simulation_data", {})
        joint_positions = full_sim_data.get("joint_positions", {})

        if joint_positions and "p3_positions" in joint_positions:
            p3 = np.array(joint_positions["p3_positions"][0])
            p4 = np.array(joint_positions["p4_positions"][0])
            p5 = np.array(joint_positions["p5_positions"][0])
        else:
            L2 = params.get("L2", 40)
            L4 = params.get("L4", 50)
            L5 = params.get("L5", 45)

            p3 = p1 + np.array([L2, 0])
            p4 = p2 + np.array([-L4 * 0.5, L4 * 0.866])
            p5 = p6 + np.array([L5 * 0.7, L5 * 0.7])

        return p1, p2, p3, p4, p5, p6

    def _create_pivots(
        self,
        visual_items: list[QGraphicsItem],
        ground_positions: list[QPointF],
        moving_positions: list[QPointF],
    ) -> None:
        """Create pivot markers."""
        pivot_brush = QBrush(QColor(150, 150, 255))
        ground_pivot_brush = QBrush(QColor(80, 80, 80))

        for pos in ground_positions:
            pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
            pivot.setBrush(ground_pivot_brush)
            pivot.setPen(QPen(Qt.GlobalColor.black, 2))
            self.scene.addItem(pivot)
            visual_items.append(pivot)

        for pos in moving_positions:
            pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
            pivot.setBrush(pivot_brush)
            pivot.setPen(QPen(Qt.GlobalColor.black, 1))
            self.scene.addItem(pivot)
            visual_items.append(pivot)

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update 6-bar visuals for animation."""
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data from parameters."""
        from automataii.domain.mechanisms.linkages.sixbar.compute import compute_6bar_positions

        return compute_6bar_positions(params)
