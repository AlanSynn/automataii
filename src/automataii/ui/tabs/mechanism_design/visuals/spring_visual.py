# src/automataii/gui/tabs/mechanism_design/visuals/spring_visual.py
import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem


def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a spring/damper mechanism."""
    items = []
    debug_items = []

    # Colors for spring system
    spring_color = QColor("#f39c12")  # Orange for spring
    mass_color = QColor("#e74c3c")  # Red for mass
    anchor_color = QColor("#2c3e50")  # Dark blue for anchors

    line_width = 3 if is_preview else 4

    # Create first anchor point
    anchor1 = QGraphicsEllipseItem()
    anchor1.setPen(QPen(anchor_color, line_width))
    anchor1.setBrush(QBrush(anchor_color))
    scene_manager.scene.addItem(anchor1)
    items.append(anchor1)

    # Create spring path
    spring_path = QGraphicsPathItem()
    spring_path.setPen(QPen(spring_color, line_width - 1))
    scene_manager.scene.addItem(spring_path)
    items.append(spring_path)

    # Create mass (attached to spring)
    mass = QGraphicsEllipseItem()
    mass.setPen(QPen(mass_color, line_width))
    mass.setBrush(QBrush(mass_color.lighter(160)))
    scene_manager.scene.addItem(mass)
    items.append(mass)

    # Create second anchor point (if fixed-fixed spring)
    anchor2 = QGraphicsEllipseItem()
    anchor2.setPen(QPen(anchor_color, line_width))
    anchor2.setBrush(QBrush(anchor_color))
    scene_manager.scene.addItem(anchor2)
    items.append(anchor2)

    return items, debug_items


def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a spring/damper mechanism."""
    if len(visual_items) != 4:
        return None

    anchor1, spring_path, mass, anchor2 = visual_items

    # Get parameters from layer data
    params = layer_data.get("params", {})
    key_points = layer_data.get("key_points", {})

    # Spring parameters
    k = params.get("spring_constant", 100.0)  # N/m
    c = params.get("damping_coefficient", 10.0)  # N·s/m
    m = params.get("mass", 1.0)  # kg
    rest_length = params.get("rest_length", 100.0)  # mm

    # Attachment points
    attach1_orig = np.array(key_points.get("attachment_1", [0, 0]))
    attach2_orig = np.array(key_points.get("attachment_2", [0, 100]))

    attach1 = transform(attach1_orig)
    attach2 = transform(attach2_orig)

    # Position anchor points
    anchor_size = 8
    anchor1.setRect(
        attach1.x() - anchor_size / 2, attach1.y() - anchor_size / 2, anchor_size, anchor_size
    )
    anchor2.setRect(
        attach2.x() - anchor_size / 2, attach2.y() - anchor_size / 2, anchor_size, anchor_size
    )

    # Calculate spring dynamics
    omega_n = np.sqrt(k / m)  # Natural frequency
    zeta = c / (2 * np.sqrt(k * m))  # Damping ratio

    # Initial conditions
    current_length = np.sqrt((attach2.x() - attach1.x()) ** 2 + (attach2.y() - attach1.y()) ** 2)
    x0 = current_length - rest_length  # Initial displacement
    v0 = params.get("initial_velocity", 0.0)  # Initial velocity

    # Calculate displacement at current time
    if zeta < 1:  # Underdamped
        omega_d = omega_n * np.sqrt(1 - zeta**2)
        displacement = np.exp(-zeta * omega_n * time) * (
            x0 * np.cos(omega_d * time)
            + ((v0 + zeta * omega_n * x0) / omega_d) * np.sin(omega_d * time)
        )
    elif zeta == 1:  # Critically damped
        displacement = np.exp(-omega_n * time) * (x0 + (v0 + omega_n * x0) * time)
    else:  # Overdamped
        r1 = -omega_n * (zeta + np.sqrt(zeta**2 - 1))
        r2 = -omega_n * (zeta - np.sqrt(zeta**2 - 1))
        A = (v0 - r2 * x0) / (r1 - r2)
        B = (r1 * x0 - v0) / (r1 - r2)
        displacement = A * np.exp(r1 * time) + B * np.exp(r2 * time)

    # Calculate current spring length
    spring_length = rest_length + displacement

    # Direction vector
    dx = attach2.x() - attach1.x()
    dy = attach2.y() - attach1.y()
    direction_length = np.sqrt(dx**2 + dy**2)

    if direction_length > 0:
        unit_x = dx / direction_length
        unit_y = dy / direction_length
    else:
        unit_x, unit_y = 1, 0

    # Calculate mass position
    mass_pos = QPointF(
        attach1.x() + unit_x * spring_length * 0.8,  # Position mass 80% along spring
        attach1.y() + unit_y * spring_length * 0.8,
    )

    # Position mass
    mass_size = 12
    mass.setRect(mass_pos.x() - mass_size / 2, mass_pos.y() - mass_size / 2, mass_size, mass_size)

    # Create spring coil visualization
    spring_path_shape = QPainterPath()

    # Number of coils
    num_coils = int(params.get("number_of_coils", 8))
    coil_amplitude = params.get("coil_diameter", 10.0) / 2

    # Calculate spring path
    steps = num_coils * 8  # 8 points per coil
    for i in range(steps + 1):
        t = i / steps

        # Position along spring length
        along_spring = t * spring_length

        # Perpendicular offset for coil shape
        coil_angle = t * num_coils * 2 * np.pi
        perpendicular_offset = coil_amplitude * np.sin(coil_angle)

        # Calculate perpendicular direction
        perp_x = -unit_y
        perp_y = unit_x

        # Spring point position
        spring_x = attach1.x() + unit_x * along_spring + perp_x * perpendicular_offset
        spring_y = attach1.y() + unit_y * along_spring + perp_y * perpendicular_offset

        if i == 0:
            spring_path_shape.moveTo(spring_x, spring_y)
        else:
            spring_path_shape.lineTo(spring_x, spring_y)

    spring_path.setPath(spring_path_shape)

    # Color coding based on spring state
    if abs(displacement) < 0.1:
        # Spring at rest - normal color
        spring_color = QColor("#f39c12")
    elif displacement > 0:
        # Spring extended - red
        spring_color = QColor("#e74c3c")
    else:
        # Spring compressed - blue
        spring_color = QColor("#3498db")

    spring_path.setPen(QPen(spring_color, 3))

    return mass_pos


def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a spring mechanism."""
    key_points = layer_data.get("key_points", {})
    params = layer_data.get("params", {})

    attach1 = transform(key_points.get("attachment_1", [0, 0]))
    attach2 = transform(key_points.get("attachment_2", [0, 100]))

    # Calculate initial mass position (at rest length)
    rest_length = params.get("rest_length", 100.0)
    dx = attach2.x() - attach1.x()
    dy = attach2.y() - attach1.y()
    direction_length = np.sqrt(dx**2 + dy**2)

    if direction_length > 0:
        unit_x = dx / direction_length
        unit_y = dy / direction_length

        # Position mass at 80% of rest length
        mass_pos = QPointF(
            attach1.x() + unit_x * rest_length * 0.8, attach1.y() + unit_y * rest_length * 0.8
        )
        return mass_pos

    return QPointF(attach1.x(), attach1.y())
