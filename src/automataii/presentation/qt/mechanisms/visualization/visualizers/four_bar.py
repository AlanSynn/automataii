"""
Four-bar linkage visualizer implementation.
"""

import logging
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

from automataii.presentation.qt.mechanism_parameter_utils import finite_param

from ..base import MechanismVisualizer


class FourBarVisualizer(MechanismVisualizer):
    """Visualizer for 4-bar linkage mechanisms."""

    # Color scheme for 4-bar components
    DRIVER_COLOR = QColor("#e74c3c")  # Red
    FOLLOWER_COLOR = QColor("#f39c12")  # Orange
    COUPLER_COLOR = QColor("#2ecc71")  # Green
    GROUND_COLOR = QColor("#9b59b6")  # Purple

    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of 4-bar linkage.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state

        Returns:
            List of QGraphicsItem objects representing the 4-bar linkage
        """
        visual_items = []

        # Extract parameters
        params = self.extract_params(mechanism_data)
        if not params:
            logging.warning("No parameters found in mechanism data")
            return visual_items

        # Get link lengths
        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        if not all([l1 is not None, l2 is not None, l3 is not None, l4 is not None]):
            logging.warning(f"Incomplete 4-bar parameters: l1={l1}, l2={l2}, l3={l3}, l4={l4}")
            return visual_items

        # Get joint positions from simulation data or calculate defaults
        joint_positions = self._get_joint_positions(mechanism_data, params)
        if not joint_positions:
            return visual_items

        p1, p2, p3, p4, p_coupler = joint_positions

        # Transform to scene coordinates
        p1_t = self.transform_point(p1)
        p2_t = self.transform_point(p2)
        p3_t = self.transform_point(p3)
        p4_t = self.transform_point(p4)
        p_coupler_t = self.transform_point(p_coupler)

        # Create visual elements
        visual_items.extend(self._create_links(p1_t, p2_t, p3_t, p4_t))
        visual_items.extend(self._create_coupler(p3_t, p4_t, p_coupler_t, p3, p4, p_coupler))
        visual_items.extend(self._create_pivots(p1_t, p2_t, p3_t, p4_t))

        # Add coupler point indicator
        visual_items.append(self._create_coupler_point(p_coupler_t))

        return visual_items

    def update_visuals(self, visual_items: list[QGraphicsItem],
                      mechanism_data: dict[str, Any]) -> None:
        """
        Update existing visual items with new mechanism state.

        Args:
            visual_items: Existing visual items to update
            mechanism_data: Updated mechanism parameters and state
        """
        # Get updated joint positions
        joint_positions = self._get_joint_positions(mechanism_data, self.extract_params(mechanism_data))
        if not joint_positions:
            return

        p1, p2, p3, p4, p_coupler = joint_positions

        # Transform to scene coordinates
        p1_t = self.transform_point(p1)
        p2_t = self.transform_point(p2)
        p3_t = self.transform_point(p3)
        p4_t = self.transform_point(p4)
        p_coupler_t = self.transform_point(p_coupler)

        # Update visual items (assuming standard order)
        item_index = 0

        # Update links
        if item_index < len(visual_items) and isinstance(visual_items[item_index], QGraphicsLineItem):
            visual_items[item_index].setLine(QLineF(p1_t, p3_t))  # Driver link
            item_index += 1

        if item_index < len(visual_items) and isinstance(visual_items[item_index], QGraphicsLineItem):
            visual_items[item_index].setLine(QLineF(p2_t, p4_t))  # Follower link
            item_index += 1

        # Update coupler (triangle or line)
        if item_index < len(visual_items):
            if isinstance(visual_items[item_index], QGraphicsPolygonItem):
                # Update triangle
                triangle_points = [p3_t, p4_t, p_coupler_t]
                visual_items[item_index].setPolygon(QPolygonF(triangle_points))
            elif isinstance(visual_items[item_index], QGraphicsLineItem):
                # Update line
                visual_items[item_index].setLine(QLineF(p3_t, p4_t))

    def _get_joint_positions(self, mechanism_data: dict[str, Any],
                            params: dict[str, Any]) -> tuple | None:
        """
        Get joint positions from simulation data or calculate defaults.

        Returns:
            Tuple of (p1, p2, p3, p4, p_coupler) as numpy arrays, or None
        """
        # Try to get from simulation data first
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0:
                # Use first frame from simulation
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

                # Calculate coupler point
                p_coupler = self._calculate_coupler_point(p3, p4, params)

                return p1, p2, p3, p4, p_coupler

        # Fallback to calculated positions
        return self._calculate_default_positions(params)

    def _calculate_default_positions(self, params: dict[str, Any]) -> tuple | None:
        """Calculate default joint positions based on link lengths."""
        l1 = params.get("l1", 100)
        l2 = params.get("l2", 40)
        l3 = params.get("l3", 60)
        l4 = params.get("l4", 50)

        # Default ground pivots
        p1 = np.array([0, 0])
        p2 = np.array([l1, 0])

        # Calculate crank position (at angle 0)
        p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])

        # Calculate rocker position using circle-circle intersection
        d = np.linalg.norm(p2 - p3)
        if not (abs(l3 - l4) <= d <= l3 + l4):
            logging.warning("Invalid 4-bar configuration")
            return None

        a = (l3**2 - l4**2 + d**2) / (2 * d)
        h = math.sqrt(max(0, l3**2 - a**2))
        p3_p2_unit = (p2 - p3) / d
        midpoint = p3 + a * p3_p2_unit
        p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        # Calculate coupler point
        p_coupler = self._calculate_coupler_point(p3, p4, params)

        return p1, p2, p3, p4, p_coupler

    def _calculate_coupler_point(self, p3: np.ndarray, p4: np.ndarray,
                                 params: dict[str, Any]) -> np.ndarray:
        """Calculate coupler point position."""
        # Support both param name conventions: coupler_point_x/y (internal) and p_x/p_y (JSON/dataset)
        coupler_point_x = finite_param(params, "coupler_point_x", "p_x", default=0.0)
        coupler_point_y = finite_param(params, "coupler_point_y", "p_y", default=0.0)

        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)

        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            return p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal

        return p3

    def _create_links(self, p1_t: QPointF, p2_t: QPointF,
                     p3_t: QPointF, p4_t: QPointF) -> list[QGraphicsItem]:
        """Create link visual items."""
        links = []

        # Driver link (p1 to p3)
        driver_link = QGraphicsLineItem(QLineF(p1_t, p3_t))
        driver_pen = QPen(self.DRIVER_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        driver_link.setPen(driver_pen)
        driver_link.setZValue(self.config.z_index_base + 5)
        links.append(driver_link)

        # Follower link (p2 to p4)
        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_pen = QPen(self.FOLLOWER_COLOR, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        follower_link.setPen(follower_pen)
        follower_link.setZValue(self.config.z_index_base + 5)
        links.append(follower_link)

        # Ground link (p1 to p2)
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_pen = QPen(self.GROUND_COLOR, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        ground_link.setPen(ground_pen)
        ground_link.setZValue(self.config.z_index_base + 4)
        links.append(ground_link)

        return links

    def _create_coupler(self, p3_t: QPointF, p4_t: QPointF, p_coupler_t: QPointF,
                       p3: np.ndarray, p4: np.ndarray, p_coupler: np.ndarray) -> list[QGraphicsItem]:
        """Create coupler visual (triangle or line)."""
        coupler_items = []

        # Check if coupler forms a triangle or is collinear
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) +
                  p_coupler[0]*(p3[1]-p4[1])) / 2

        if area < 1e-3:  # Collinear - show as line
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_pen = QPen(self.COUPLER_COLOR, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            coupler_line.setPen(coupler_pen)
            coupler_line.setZValue(self.config.z_index_base + 6)
            coupler_items.append(coupler_line)
        else:  # Non-collinear - show as triangle
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)

            coupler_triangle = QGraphicsPolygonItem(triangle_polygon)
            triangle_pen = QPen(self.COUPLER_COLOR, 2, Qt.PenStyle.SolidLine)
            triangle_brush = QBrush(self.COUPLER_COLOR.lighter(160))
            triangle_brush.setStyle(Qt.BrushStyle.SolidPattern)
            coupler_triangle.setPen(triangle_pen)
            coupler_triangle.setBrush(triangle_brush)
            coupler_triangle.setZValue(self.config.z_index_base + 6)
            coupler_triangle.setOpacity(0.8)
            coupler_items.append(coupler_triangle)

        return coupler_items

    def _create_pivots(self, p1_t: QPointF, p2_t: QPointF,
                      p3_t: QPointF, p4_t: QPointF) -> list[QGraphicsItem]:
        """Create pivot point visual items."""
        pivots = []

        pivot_colors = [
            QColor("#f39c12"),  # Orange for ground pivot 1
            QColor("#f39c12"),  # Orange for ground pivot 2
            QColor("#e74c3c"),  # Red for moving joint 1
            QColor("#3498db")   # Blue for moving joint 2
        ]
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Create compound pivot visual

            # Outer circle
            outer_pivot = QGraphicsEllipseItem(
                pos.x() - 8, pos.y() - 8, 16, 16
            )
            outer_pivot.setPen(QPen(color.darker(150), 2))
            outer_pivot.setBrush(QBrush(color))
            outer_pivot.setZValue(self.config.z_index_pivot)
            outer_pivot.setToolTip(name)
            pivots.append(outer_pivot)

            # Inner highlight
            inner_pivot = QGraphicsEllipseItem(
                pos.x() - 4, pos.y() - 4, 8, 8
            )
            inner_pivot.setPen(QPen(Qt.PenStyle.NoPen))
            inner_pivot.setBrush(QBrush(color.lighter(150)))
            inner_pivot.setZValue(self.config.z_index_pivot + 1)
            pivots.append(inner_pivot)

        return pivots

    def _create_coupler_point(self, p_coupler_t: QPointF) -> QGraphicsItem:
        """Create coupler point indicator."""
        coupler_point = QGraphicsEllipseItem(
            p_coupler_t.x() - 5, p_coupler_t.y() - 5, 10, 10
        )
        coupler_point.setPen(QPen(QColor("#27ae60"), 2))
        coupler_point.setBrush(QBrush(QColor("#27ae60")))
        coupler_point.setZValue(self.config.z_index_pivot + 2)
        coupler_point.setToolTip("Coupler Point")

        return coupler_point
