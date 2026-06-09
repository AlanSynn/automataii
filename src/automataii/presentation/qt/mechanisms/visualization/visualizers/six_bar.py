"""
Six-bar linkage visualizer implementation.

Structure (from domain layer):
- G1, G2: Ground pivots (fixed, from 5-bar base)
- C1: Left crank end (driven)
- C2: Right crank end (driven)
- P: Floating coupler point (from 5-bar)
- G3: Third ground pivot (fixed, center above ground)
- Q: Rocker end point (OUTPUT - connected to P and G3)

Links (all 5-bar links plus):
- G3→Q: Rocker link
- P→Q: Connection link
"""

import logging
import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
)

from ..base import MechanismVisualizer


class SixBarVisualizer(MechanismVisualizer):
    """Visualizer for 6-bar linkage mechanisms."""

    # Color scheme for 6-bar components
    LEFT_CRANK_COLOR = QColor("#e74c3c")  # Red
    RIGHT_CRANK_COLOR = QColor("#3498db")  # Blue
    COUPLER_COLOR = QColor("#2ecc71")  # Green
    GROUND_COLOR = QColor("#9b59b6")  # Purple
    ROCKER_COLOR = QColor("#e67e22")  # Orange (G3→Q)
    CONNECTOR_COLOR = QColor("#1abc9c")  # Teal (P→Q)
    OUTPUT_COLOR = QColor("#f1c40f")  # Yellow (Q point - output)
    P_COLOR = QColor("#f39c12")  # Orange (P point)

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of 6-bar linkage.

        Visual items order:
        - Item 0: Left crank (G1→C1)
        - Item 1: Left coupler (C1→P)
        - Item 2: Right coupler (P→C2)
        - Item 3: Right crank (C2→G2)
        - Item 4: Ground link (G1→G2)
        - Item 5: Rocker (G3→Q)
        - Item 6: Connector (P→Q)
        - Item 7-8: G1 pivot
        - Item 9-10: G2 pivot
        - Item 11-12: G3 pivot
        - Item 13-14: C1 joint
        - Item 15-16: C2 joint
        - Item 17-18: P joint
        - Item 19-20: Q output

        Returns:
            List of QGraphicsItem objects representing the 6-bar linkage
        """
        visual_items: list[QGraphicsItem] = []

        params = self.extract_params(mechanism_data)
        if not params:
            logging.warning("No parameters found in mechanism data")
            return visual_items

        # Get joint positions from simulation data or calculate defaults
        joint_positions = self._get_joint_positions(mechanism_data, params)
        if not joint_positions:
            return visual_items

        g1, g2, c1, c2, p, g3, q = joint_positions

        # Transform to scene coordinates
        g1_t = self.transform_point(g1)
        g2_t = self.transform_point(g2)
        c1_t = self.transform_point(c1)
        c2_t = self.transform_point(c2)
        p_t = self.transform_point(p)
        g3_t = self.transform_point(g3)
        q_t = self.transform_point(q)

        # Create links
        visual_items.extend(self._create_links(g1_t, g2_t, c1_t, c2_t, p_t, g3_t, q_t))

        # Create pivots and joints
        visual_items.extend(self._create_pivots_and_joints(g1_t, g2_t, c1_t, c2_t, p_t, g3_t, q_t))

        return visual_items

    def update_visuals(
        self, visual_items: list[QGraphicsItem], mechanism_data: dict[str, Any]
    ) -> None:
        """Update existing 6-bar visuals with new mechanism state."""
        if len(visual_items) < 7:
            return

        params = self.extract_params(mechanism_data)
        joint_positions = self._get_joint_positions(mechanism_data, params)
        if not joint_positions:
            return

        g1, g2, c1, c2, p, g3, q = joint_positions

        # Transform to scene coordinates
        g1_t = self.transform_point(g1)
        g2_t = self.transform_point(g2)
        c1_t = self.transform_point(c1)
        c2_t = self.transform_point(c2)
        p_t = self.transform_point(p)
        g3_t = self.transform_point(g3)
        q_t = self.transform_point(q)

        # Update links (items 0-6)
        if isinstance(visual_items[0], QGraphicsLineItem):
            visual_items[0].setLine(QLineF(g1_t, c1_t))  # Left crank
        if isinstance(visual_items[1], QGraphicsLineItem):
            visual_items[1].setLine(QLineF(c1_t, p_t))  # Left coupler
        if isinstance(visual_items[2], QGraphicsLineItem):
            visual_items[2].setLine(QLineF(p_t, c2_t))  # Right coupler
        if isinstance(visual_items[3], QGraphicsLineItem):
            visual_items[3].setLine(QLineF(c2_t, g2_t))  # Right crank
        if isinstance(visual_items[4], QGraphicsLineItem):
            visual_items[4].setLine(QLineF(g1_t, g2_t))  # Ground
        if isinstance(visual_items[5], QGraphicsLineItem):
            visual_items[5].setLine(QLineF(g3_t, q_t))  # Rocker
        if isinstance(visual_items[6], QGraphicsLineItem):
            visual_items[6].setLine(QLineF(p_t, q_t))  # Connector

        # Update pivots and joints (items 7+)
        pivot_positions = [g1_t, g2_t, g3_t, c1_t, c2_t, p_t, q_t]
        item_idx = 7
        for pos in pivot_positions:
            if item_idx < len(visual_items) and isinstance(
                visual_items[item_idx], QGraphicsEllipseItem
            ):
                visual_items[item_idx].setRect(pos.x() - 8, pos.y() - 8, 16, 16)
            item_idx += 1
            if item_idx < len(visual_items) and isinstance(
                visual_items[item_idx], QGraphicsEllipseItem
            ):
                visual_items[item_idx].setRect(pos.x() - 4, pos.y() - 4, 8, 8)
            item_idx += 1

    def _get_joint_positions(
        self, mechanism_data: dict[str, Any], params: dict[str, Any]
    ) -> tuple[np.ndarray, ...] | None:
        """
        Get joint positions from simulation data or calculate defaults.

        Returns:
            Tuple of (G1, G2, C1, C2, P, G3, Q) as numpy arrays, or None
        """
        # Try to get from simulation data first
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]

            # Map position keys (both naming conventions)
            g1_key = "g1_positions" if "g1_positions" in joint_positions else "p1_positions"
            g2_key = "g2_positions" if "g2_positions" in joint_positions else "p2_positions"
            c1_key = "c1_positions" if "c1_positions" in joint_positions else "p3_positions"
            c2_key = "c2_positions" if "c2_positions" in joint_positions else "p4_positions"
            p_key = "p_positions" if "p_positions" in joint_positions else "p5_positions"
            g3_key = "g3_positions"
            q_key = "q_positions" if "q_positions" in joint_positions else "p6_positions"

            if g1_key in joint_positions and len(joint_positions[g1_key]) > 0:
                g1 = np.array(joint_positions[g1_key][0])
                g2 = np.array(joint_positions[g2_key][0])
                c1 = np.array(joint_positions[c1_key][0])
                c2 = np.array(joint_positions[c2_key][0])
                p = np.array(joint_positions[p_key][0])

                # G3 and Q may use different keys
                if g3_key in joint_positions:
                    g3 = np.array(joint_positions[g3_key][0])
                else:
                    # Calculate default G3 position
                    ground = params.get("ground_link", params.get("l1", 210.0))
                    pivot_height = params.get("pivot_height", 0.6 * ground)
                    g3 = np.array([0.0, pivot_height])

                if q_key in joint_positions:
                    q = np.array(joint_positions[q_key][0])
                else:
                    # Calculate Q from P and G3
                    rocker_length = params.get("rocker_link", params.get("l5", 95.0))
                    q = self._solve_rocker_point(p, g3, rocker_length)

                return g1, g2, c1, c2, p, g3, q

        # Try key_points
        key_points = mechanism_data.get("key_points", {})
        if "G1" in key_points or "ground_pivot_1" in key_points:
            g1 = np.array(key_points.get("G1", key_points.get("ground_pivot_1", [0, 0])))
            g2 = np.array(key_points.get("G2", key_points.get("ground_pivot_2", [0, 0])))
            c1 = np.array(key_points.get("C1", key_points.get("crank_end_1", [0, 0])))
            c2 = np.array(key_points.get("C2", key_points.get("crank_end_2", [0, 0])))
            p = np.array(key_points.get("P", key_points.get("coupler_point", [0, 0])))
            g3 = np.array(key_points.get("G3", key_points.get("ground_pivot_3", [0, 0])))
            q = np.array(key_points.get("Q", key_points.get("output_point", [0, 0])))
            return g1, g2, c1, c2, p, g3, q

        # Fallback to calculated positions
        return self._calculate_default_positions(params)

    def _calculate_default_positions(self, params: dict[str, Any]) -> tuple[np.ndarray, ...] | None:
        """Calculate default joint positions based on link lengths."""
        # Extract parameters (support both naming conventions)
        ground = params.get("ground_link", params.get("l1", 210.0))
        left_crank = params.get("input_link", params.get("l2", 55.0))
        right_crank = params.get("output_link", params.get("l4", 75.0))
        floating = params.get("coupler_link", params.get("l3", 160.0))
        rocker_length = params.get("rocker_link", params.get("l5", 95.0))
        input_angle = params.get("input_angle", 18.0)
        pivot_height = params.get("pivot_height", 0.6 * ground)

        # Ground pivots centered at origin
        g1 = np.array([-ground / 2.0, 0.0])
        g2 = np.array([ground / 2.0, 0.0])

        # Third ground pivot (center, above ground)
        g3 = np.array([0.0, pivot_height])

        # Left crank end (driven by input angle)
        theta = math.radians(input_angle)
        c1 = g1 + np.array([left_crank * math.cos(theta), left_crank * math.sin(theta)])

        # Right crank (mirror angle)
        phi = math.pi - theta
        c2 = g2 + np.array([right_crank * math.cos(phi), right_crank * math.sin(phi)])

        # Floating coupler point (circle-circle intersection)
        p = self._circle_intersection(c1, floating, c2, floating)
        if p is None:
            p = (c1 + c2) / 2.0

        # Rocker end point Q
        q = self._solve_rocker_point(p, g3, rocker_length)

        return g1, g2, c1, c2, p, g3, q

    @staticmethod
    def _circle_intersection(
        center_a: np.ndarray,
        radius_a: float,
        center_b: np.ndarray,
        radius_b: float,
    ) -> np.ndarray | None:
        """Find intersection of two circles, returning the upper point."""
        dx = center_b[0] - center_a[0]
        dy = center_b[1] - center_a[1]
        d = math.hypot(dx, dy)

        if d < 1e-6:
            return None
        if d > radius_a + radius_b or d < abs(radius_a - radius_b):
            return None

        a = (radius_a**2 - radius_b**2 + d**2) / (2 * d)
        h_sq = radius_a**2 - a**2
        h = math.sqrt(max(h_sq, 0.0))

        xm = center_a[0] + a * dx / d
        ym = center_a[1] + a * dy / d

        rx = -dy * (h / d)
        ry = dx * (h / d)

        p1 = np.array([xm + rx, ym + ry])
        p2 = np.array([xm - rx, ym - ry])

        return p1 if p1[1] >= p2[1] else p2

    @staticmethod
    def _solve_rocker_point(
        floating_point: np.ndarray,
        pivot: np.ndarray,
        rocker_length: float,
    ) -> np.ndarray:
        """
        Solve for rocker end point Q.

        Q is on the line from G3 (pivot) towards P (floating_point),
        at distance rocker_length from G3.
        """
        dx = floating_point[0] - pivot[0]
        dy = floating_point[1] - pivot[1]
        dist = math.hypot(dx, dy)

        if dist < 1e-6:
            return pivot.copy()

        scale = min(rocker_length, dist) / dist
        return np.array([pivot[0] + dx * scale, pivot[1] + dy * scale])

    def _create_links(
        self,
        g1_t: QPointF,
        g2_t: QPointF,
        c1_t: QPointF,
        c2_t: QPointF,
        p_t: QPointF,
        g3_t: QPointF,
        q_t: QPointF,
    ) -> list[QGraphicsItem]:
        """Create link visual items."""
        links: list[QGraphicsItem] = []

        # Left crank (G1→C1)
        left_crank = QGraphicsLineItem(QLineF(g1_t, c1_t))
        left_crank.setPen(
            QPen(self.LEFT_CRANK_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        left_crank.setZValue(self.config.z_index_base + 5)
        links.append(left_crank)

        # Left coupler (C1→P)
        left_coupler = QGraphicsLineItem(QLineF(c1_t, p_t))
        left_coupler.setPen(
            QPen(self.COUPLER_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        left_coupler.setZValue(self.config.z_index_base + 6)
        links.append(left_coupler)

        # Right coupler (P→C2)
        right_coupler = QGraphicsLineItem(QLineF(p_t, c2_t))
        right_coupler.setPen(
            QPen(self.COUPLER_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        right_coupler.setZValue(self.config.z_index_base + 6)
        links.append(right_coupler)

        # Right crank (C2→G2)
        right_crank = QGraphicsLineItem(QLineF(c2_t, g2_t))
        right_crank.setPen(
            QPen(self.RIGHT_CRANK_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        right_crank.setZValue(self.config.z_index_base + 5)
        links.append(right_crank)

        # Ground link (G1→G2)
        ground_link = QGraphicsLineItem(QLineF(g1_t, g2_t))
        ground_link.setPen(
            QPen(self.GROUND_COLOR, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        ground_link.setZValue(self.config.z_index_base + 4)
        links.append(ground_link)

        # Rocker (G3→Q)
        rocker = QGraphicsLineItem(QLineF(g3_t, q_t))
        rocker.setPen(QPen(self.ROCKER_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        rocker.setZValue(self.config.z_index_base + 7)
        links.append(rocker)

        # Connector (P→Q)
        connector = QGraphicsLineItem(QLineF(p_t, q_t))
        connector.setPen(
            QPen(self.CONNECTOR_COLOR, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        connector.setZValue(self.config.z_index_base + 7)
        links.append(connector)

        return links

    def _create_pivots_and_joints(
        self,
        g1_t: QPointF,
        g2_t: QPointF,
        c1_t: QPointF,
        c2_t: QPointF,
        p_t: QPointF,
        g3_t: QPointF,
        q_t: QPointF,
    ) -> list[QGraphicsItem]:
        """Create pivot and joint visual items."""
        items: list[QGraphicsItem] = []

        pivot_data = [
            (g1_t, self.GROUND_COLOR, "Ground Pivot G1"),
            (g2_t, self.GROUND_COLOR, "Ground Pivot G2"),
            (g3_t, self.GROUND_COLOR, "Ground Pivot G3"),
            (c1_t, self.LEFT_CRANK_COLOR, "Left Crank End C1"),
            (c2_t, self.RIGHT_CRANK_COLOR, "Right Crank End C2"),
            (p_t, self.P_COLOR, "Floating Point P"),
            (q_t, self.OUTPUT_COLOR, "Output Point Q"),
        ]

        for pos, color, name in pivot_data:
            # Outer circle
            outer = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
            outer.setPen(QPen(color.darker(150), 2))
            outer.setBrush(QBrush(color))
            outer.setZValue(self.config.z_index_pivot)
            outer.setToolTip(name)
            items.append(outer)

            # Inner highlight
            inner = QGraphicsEllipseItem(pos.x() - 4, pos.y() - 4, 8, 8)
            inner.setPen(QPen(Qt.PenStyle.NoPen))
            inner.setBrush(QBrush(color.lighter(150)))
            inner.setZValue(self.config.z_index_pivot + 1)
            items.append(inner)

        return items
