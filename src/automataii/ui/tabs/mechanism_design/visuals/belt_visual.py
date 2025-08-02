# src/automataii/gui/tabs/mechanism_design/visuals/belt_visual.py
import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem


def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a belt/pulley mechanism."""
    items = []
    debug_items = []

    # Colors for belt/pulley system
    pulley_color = QColor("#3498db")  # Blue for pulleys
    belt_color = QColor("#8e44ad")  # Purple for belt

    line_width = 3 if is_preview else 4

    # Create first pulley
    pulley1 = QGraphicsEllipseItem()
    pulley1.setPen(QPen(pulley_color, line_width))
    pulley1.setBrush(QBrush(pulley_color.lighter(160)))
    scene_manager.scene.addItem(pulley1)
    items.append(pulley1)

    # Create second pulley
    pulley2 = QGraphicsEllipseItem()
    pulley2.setPen(QPen(pulley_color, line_width))
    pulley2.setBrush(QBrush(pulley_color.lighter(160)))
    scene_manager.scene.addItem(pulley2)
    items.append(pulley2)

    # Create belt path
    belt_path = QGraphicsPathItem()
    belt_path.setPen(QPen(belt_color, line_width - 1))
    belt_path.setBrush(QBrush(belt_color.lighter(180)))
    scene_manager.scene.addItem(belt_path)
    items.append(belt_path)

    # Create belt marker (moving point on belt)
    belt_marker = QGraphicsEllipseItem()
    belt_marker.setPen(QPen(QColor("#e74c3c"), 2))
    belt_marker.setBrush(QBrush(QColor("#e74c3c")))
    scene_manager.scene.addItem(belt_marker)
    items.append(belt_marker)

    return items, debug_items


def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a belt/pulley mechanism."""
    if len(visual_items) != 4:
        return None

    pulley1, pulley2, belt_path, belt_marker = visual_items

    # Get parameters from layer data
    params = layer_data.get("params", {})
    key_points = layer_data.get("key_points", {})

    # Pulley parameters
    r1 = params.get("pulley_1_radius", 40.0)
    r2 = params.get("pulley_2_radius", 25.0)

    # Pulley centers
    center1_orig = np.array(key_points.get("pulley_1_center", [0, 0]))
    center2_orig = np.array(key_points.get("pulley_2_center", [100, 0]))

    center1 = transform(center1_orig)
    center2 = transform(center2_orig)

    # Position pulleys
    pulley1.setRect(center1.x() - r1, center1.y() - r1, 2 * r1, 2 * r1)
    pulley2.setRect(center2.x() - r2, center2.y() - r2, 2 * r2, 2 * r2)

    # Calculate belt geometry
    dx = center2.x() - center1.x()
    dy = center2.y() - center1.y()
    distance = np.sqrt(dx**2 + dy**2)

    if distance > (r1 + r2):  # Valid belt configuration
        # Calculate external tangent points
        angle_centers = np.arctan2(dy, dx)

        if r1 != r2:
            beta = np.arcsin((r1 - r2) / distance)
        else:
            beta = 0

        # Tangent angles
        t1_angle = angle_centers + beta + np.pi / 2
        t2_angle = angle_centers + beta - np.pi / 2

        # Tangent points on first pulley
        t1_top = QPointF(center1.x() + r1 * np.cos(t1_angle), center1.y() + r1 * np.sin(t1_angle))
        t1_bottom = QPointF(
            center1.x() + r1 * np.cos(t2_angle), center1.y() + r1 * np.sin(t2_angle)
        )

        # Tangent points on second pulley
        t2_top = QPointF(center2.x() + r2 * np.cos(t1_angle), center2.y() + r2 * np.sin(t1_angle))
        t2_bottom = QPointF(
            center2.x() + r2 * np.cos(t2_angle), center2.y() + r2 * np.sin(t2_angle)
        )

        # Create belt path
        belt_path_shape = QPainterPath()

        # Top arc on pulley 1
        belt_path_shape.moveTo(t1_top)
        belt_path_shape.arcTo(
            center1.x() - r1,
            center1.y() - r1,
            2 * r1,
            2 * r1,
            np.degrees(t1_angle),
            np.degrees(t2_angle - t1_angle),
        )

        # Bottom straight line
        belt_path_shape.lineTo(t2_bottom)

        # Bottom arc on pulley 2
        belt_path_shape.arcTo(
            center2.x() - r2,
            center2.y() - r2,
            2 * r2,
            2 * r2,
            np.degrees(t2_angle),
            np.degrees(t1_angle - t2_angle),
        )

        # Top straight line
        belt_path_shape.lineTo(t1_top)
        belt_path_shape.closeSubpath()

        belt_path.setPath(belt_path_shape)

        # Animate belt marker
        omega1 = params.get("angular_velocity_1", 1.0)
        slip_coeff = params.get("slip_coefficient", 0.0)

        # Calculate belt position
        belt_speed = r1 * omega1 * (1 - slip_coeff)
        belt_circumference = 2 * np.pi * (r1 + r2) + 2 * distance
        belt_position = (belt_speed * time) % belt_circumference

        # Determine marker position on belt
        circumference1 = np.pi * r1
        straight_section = distance

        if belt_position < circumference1:
            # Marker is on pulley 1
            angle = belt_position / r1 + t1_angle
            marker_pos = QPointF(center1.x() + r1 * np.cos(angle), center1.y() + r1 * np.sin(angle))
        elif belt_position < circumference1 + straight_section:
            # Marker is on top straight section
            ratio = (belt_position - circumference1) / straight_section
            marker_pos = QPointF(
                t1_top.x() + ratio * (t2_top.x() - t1_top.x()),
                t1_top.y() + ratio * (t2_top.y() - t1_top.y()),
            )
        else:
            # Marker is on pulley 2 or bottom straight section
            remaining = belt_position - circumference1 - straight_section
            circumference2 = np.pi * r2

            if remaining < circumference2:
                # Marker is on pulley 2
                angle = remaining / r2 + t2_angle
                marker_pos = QPointF(
                    center2.x() + r2 * np.cos(angle), center2.y() + r2 * np.sin(angle)
                )
            else:
                # Marker is on bottom straight section
                ratio = (remaining - circumference2) / straight_section
                marker_pos = QPointF(
                    t2_bottom.x() + ratio * (t1_bottom.x() - t2_bottom.x()),
                    t2_bottom.y() + ratio * (t1_bottom.y() - t2_bottom.y()),
                )

        # Position belt marker
        marker_size = 6
        belt_marker.setRect(
            marker_pos.x() - marker_size / 2,
            marker_pos.y() - marker_size / 2,
            marker_size,
            marker_size,
        )

        return marker_pos

    return QPointF(center1.x(), center1.y())


def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a belt mechanism."""
    key_points = layer_data.get("key_points", {})
    center1 = transform(key_points.get("pulley_1_center", [0, 0]))

    # Return the center of the first pulley as initial output
    return QPointF(center1.x(), center1.y())
