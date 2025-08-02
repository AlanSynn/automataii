# src/automataii/gui/tabs/mechanism_design/visuals/gear_visual.py
import numpy as np
from PyQt6.QtCore import QLineF, QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem


def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a gear mechanism with enhanced graphics."""
    items = []
    debug_items = []

    # Colors exactly matching recommendation dialog
    # For simple gears:
    gear1_color = QColor("#3498db")  # Blue for first gear
    gear2_color = QColor("#2ecc71")  # Green for second gear
    # For planetary gears (from dialog):
    sun_gear_color = QColor("#7f8c8d")  # Gray for sun gear
    planet_gear_color = QColor("#e67e22")  # Orange for planet gear
    tracking_line_color = QColor("#f39c12")  # Orange for tracking line
    tracking_point_color = QColor("#e74c3c")  # Red for tracking point
    spoke_color = QColor("#ffffff")  # White for spokes

    line_width = 4  # Same as dialog

    # Determine mechanism type for color selection
    mech_type = layer_data.get("original_json_type", "Simple Gear")
    
    if "Planetary" in mech_type:
        # Planetary gear colors
        gear1_final_color = sun_gear_color
        gear2_final_color = planet_gear_color
    else:
        # Simple gear colors
        gear1_final_color = gear1_color
        gear2_final_color = gear2_color
    
    # First gear - same as dialog
    gear1 = QGraphicsEllipseItem()
    gear1.setPen(QPen(gear1_final_color, 4))  # Same width as dialog
    gear1.setBrush(QBrush(gear1_final_color.lighter(170)))  # Same brush as dialog
    scene_manager.scene.addItem(gear1)
    items.append(gear1)

    # Second gear - same as dialog
    gear2 = QGraphicsEllipseItem()
    gear2.setPen(QPen(gear2_final_color, 4))  # Same width as dialog
    gear2.setBrush(QBrush(gear2_final_color.lighter(170)))  # Same brush as dialog
    scene_manager.scene.addItem(gear2)
    items.append(gear2)

    # Spokes for gear1
    gear1_spoke = QGraphicsLineItem()
    gear1_spoke.setPen(QPen(spoke_color, 2))
    scene_manager.scene.addItem(gear1_spoke)
    items.append(gear1_spoke)

    # Spokes for gear2
    gear2_spoke = QGraphicsLineItem()
    gear2_spoke.setPen(QPen(spoke_color, 2))
    scene_manager.scene.addItem(gear2_spoke)
    items.append(gear2_spoke)

    return items, debug_items


def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a gear mechanism with enhanced graphics."""
    if len(visual_items) != 4:
        return None

    gear1, gear2, gear1_spoke, gear2_spoke = visual_items

    # Get simulation data or use defaults
    sim_data = layer_data.get("full_simulation_data", {})
    params = layer_data.get("parameters", {})

    # Handle different gear types
    mech_type = layer_data.get("original_json_type", "Simple Gear")

    if mech_type == "Planetary Gear" and "gear_positions" in sim_data:
        # Planetary gear system
        gear_pos = sim_data["gear_positions"]
        num_frames = len(gear_pos.get("sun_centers", []))
        if num_frames > 0:
            frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames

            sun_center_orig = np.array(gear_pos["sun_centers"][frame_index])
            planet_center_orig = np.array(gear_pos["planet_centers"][frame_index])
            tracking_point_orig = np.array(gear_pos["tracking_points"][frame_index])

            r_sun = params.get("r_sun", 30)
            r_planet = params.get("r_planet", 20)

            sun_center = transform(sun_center_orig)
            planet_center = transform(planet_center_orig)
            tracking_point = transform(tracking_point_orig)

            # Update gear positions
            gear1.setRect(
                QRectF(sun_center.x() - r_sun, sun_center.y() - r_sun, 2 * r_sun, 2 * r_sun)
            )
            gear2.setRect(
                QRectF(
                    planet_center.x() - r_planet,
                    planet_center.y() - r_planet,
                    2 * r_planet,
                    2 * r_planet,
                )
            )

            # Update spokes (radial lines)
            gear1_spoke.setLine(QLineF(sun_center, QPointF(sun_center.x() + r_sun, sun_center.y())))
            gear2_spoke.setLine(QLineF(planet_center, tracking_point))

            return tracking_point

    elif "gear_data" in sim_data:
        # Simple gear pair
        gear_data = sim_data["gear_data"]
        num_frames = len(gear_data.get("gear1_centers", []))
        if num_frames > 0:
            frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames

            g1_center_orig = np.array(gear_data["gear1_centers"][frame_index])
            g2_center_orig = np.array(gear_data["gear2_centers"][frame_index])
            theta1 = gear_data["gear1_angles"][frame_index]
            theta2 = gear_data["gear2_angles"][frame_index]

            r1 = params.get("r1", 40)
            r2 = params.get("r2", 30)

            g1_center = transform(g1_center_orig)
            g2_center = transform(g2_center_orig)

            # Update gear positions
            gear1.setRect(QRectF(g1_center.x() - r1, g1_center.y() - r1, 2 * r1, 2 * r1))
            gear2.setRect(QRectF(g2_center.x() - r2, g2_center.y() - r2, 2 * r2, 2 * r2))

            # Update spokes showing rotation
            spoke1_end = QPointF(
                g1_center.x() + r1 * np.cos(theta1), g1_center.y() + r1 * np.sin(theta1)
            )
            spoke2_end = QPointF(
                g2_center.x() + r2 * np.cos(theta2), g2_center.y() + r2 * np.sin(theta2)
            )

            gear1_spoke.setLine(QLineF(g1_center, spoke1_end))
            gear2_spoke.setLine(QLineF(g2_center, spoke2_end))

            # Return tracking point if available
            tracking_points = gear_data.get("tracking_points", [])
            if tracking_points and frame_index < len(tracking_points):
                return transform(tracking_points[frame_index])
            else:
                return spoke2_end

    # Fallback to simple animation
    key_points = layer_data.get("key_points", {})
    center1 = transform(key_points.get("gear1_center", [0, 0]))
    center2 = transform(key_points.get("gear2_center", [70, 0]))

    r1, r2 = 30, 25
    angle1 = time
    angle2 = -time * (r1 / r2)  # Counter-rotation based on radius ratio

    gear1.setRect(QRectF(center1.x() - r1, center1.y() - r1, 2 * r1, 2 * r1))
    gear2.setRect(QRectF(center2.x() - r2, center2.y() - r2, 2 * r2, 2 * r2))

    spoke1_end = QPointF(center1.x() + r1 * np.cos(angle1), center1.y() + r1 * np.sin(angle1))
    spoke2_end = QPointF(center2.x() + r2 * np.cos(angle2), center2.y() + r2 * np.sin(angle2))

    gear1_spoke.setLine(QLineF(center1, spoke1_end))
    gear2_spoke.setLine(QLineF(center2, spoke2_end))

    return spoke2_end


def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a gear mechanism."""
    params = layer_data.get("params", {})
    sun_radius = params.get("sun_radius", 50)
    planet_radius = params.get("planet_radius", 25)

    sun_center = transform(layer_data.get("key_points", {}).get("sun_center", [0, 0]))

    # This should match the initial state in the update function
    orbit_radius = sun_radius + planet_radius
    angle = 0
    planet_x = sun_center.x() + orbit_radius * np.cos(angle)
    planet_y = sun_center.y() + orbit_radius * np.sin(angle)

    return QPointF(planet_x, planet_y)
