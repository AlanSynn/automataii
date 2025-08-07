# src/automataii/gui/tabs/mechanism_design/visuals/cam_visual.py
import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPolygonItem


def create(layer_data, scene_manager, transform, is_preview=False):
    """(Strategy) Creates visuals for a cam mechanism with enhanced graphics."""
    items = []
    debug_items = []

    # Colors exactly matching recommendation dialog
    cam_color = QColor("#e74c3c")  # Red for cam
    follower_color = QColor("#2ecc71")  # Green for follower

    line_width = 4  # Same as dialog

    # Create cam profile as egg-shaped path - same as dialog
    cam_profile = QGraphicsPathItem()
    cam_profile.setPen(QPen(cam_color, 4))  # Same as dialog
    cam_profile.setBrush(QBrush(cam_color.lighter(160)))  # Same as dialog
    scene_manager.scene.addItem(cam_profile)
    items.append(cam_profile)

    # Create follower as rectangular polygon
    follower = QGraphicsPolygonItem()
    follower.setPen(QPen(follower_color, 3))
    follower.setBrush(QBrush(follower_color.lighter(160)))
    scene_manager.scene.addItem(follower)
    items.append(follower)

    return items, debug_items


def update(layer_data, time, visual_items, transform):
    """(Strategy) Updates visuals for a cam mechanism with enhanced egg-shaped cam using EXACT dialog alignment."""
    if len(visual_items) != 2:
        return None

    cam_profile, follower = visual_items

    # Get simulation data or use defaults
    sim_data = layer_data.get("full_simulation_data", {})
    params = layer_data.get("parameters", {})
    base_radius = params.get("base_radius", 50)

    # Use dialog-aligned data for exact consistency if available
    is_dialog_aligned = layer_data.get("dialog_aligned", False)
    user_path_aligned = layer_data.get("user_path_aligned_np")
    mech_path_aligned = layer_data.get("mech_path_aligned_np")

    if is_dialog_aligned and "cam_data" in sim_data:
        # Use EXACT simulation data from the dialog for perfect consistency
        cam_data = sim_data["cam_data"]
        frame_idx = int((time % (2 * np.pi)) / (2 * np.pi) * len(cam_data.get("cam_centers", [1]))) % max(1, len(cam_data.get("cam_centers", [1])))

        cam_center_orig = np.array(cam_data["cam_centers"][frame_idx] if cam_data.get("cam_centers") else [0, 0])
        follower_y = cam_data["follower_y_positions"][frame_idx] if cam_data.get("follower_y_positions") else cam_center_orig[1] + base_radius
    else:
        # Fallback to key points and simulation data
        key_points = layer_data.get("key_points", {})
        cam_center_orig = np.array(key_points.get("cam_center", [0, 0]))

        # Calculate follower position from simulation data or time-based animation
        if sim_data and "follower_y_positions" in sim_data:
            num_frames = len(sim_data["follower_y_positions"])
            if num_frames > 0:
                frame_index = int((time % (2 * np.pi)) / (2 * np.pi) * num_frames) % num_frames
                follower_y = sim_data["follower_y_positions"][frame_index]
            else:
                follower_y = cam_center_orig[1] + base_radius
        else:
            # Fallback to simple oscillation
            follower_y = cam_center_orig[1] + base_radius + 20 * np.sin(time)

    cam_center = transform(cam_center_orig)

    # Create egg-shaped cam profile - EXACT same as dialog
    cam_path = QPainterPath()
    for i in range(101):
        theta = 2 * np.pi * i / 100

        # Egg shape: vary radius based on angle for realistic cam profile - SAME AS DIALOG
        if theta <= np.pi:
            # Top half: smaller radius (narrow part of egg)
            radius_factor = 0.7 + 0.3 * (1 - np.cos(theta))
        else:
            # Bottom half: larger radius (wide part of egg)
            radius_factor = 1.0 + 0.4 * (1 + np.cos(theta))

        effective_radius = base_radius * radius_factor * 0.6  # SAME scaling as dialog

        # Calculate point on cam profile
        p_orig = cam_center_orig + effective_radius * np.array([np.cos(theta), np.sin(theta)])
        p_screen = transform(p_orig)

        if i == 0:
            cam_path.moveTo(p_screen.x(), p_screen.y())
        else:
            cam_path.lineTo(p_screen.x(), p_screen.y())

    cam_path.closeSubpath()
    cam_profile.setPath(cam_path)

    # Transform follower position - EXACT same as dialog
    follower_pos_orig = np.array([0, follower_y])
    follower_pos = transform(follower_pos_orig)

    # Create rectangular follower - EXACT same size and logic as dialog
    w, h = 20, 10  # SAME size as dialog
    tl = QPointF(follower_pos.x() - w / 2, follower_pos.y() + h / 2)
    tr = QPointF(follower_pos.x() + w / 2, follower_pos.y() + h / 2)
    br = QPointF(follower_pos.x() + w / 2, follower_pos.y() - h / 2)
    bl = QPointF(follower_pos.x() - w / 2, follower_pos.y() - h / 2)

    follower_polygon = QPolygonF([tl, tr, br, bl])
    follower.setPolygon(follower_polygon)

    return follower_pos


def get_initial_output(layer_data, transform):
    """(Strategy) Calculates the initial output position for a cam mechanism."""
    key_points = layer_data.get("key_points", {})
    cam_center = transform(key_points.get("cam_center", [0, 0]))

    # This should match the initial state in the update function
    radius = 50
    angle = 0
    pos_x = cam_center.x() + radius * 0.5 * (1 + np.cos(angle))
    pos_y = cam_center.y()

    return QPointF(pos_x, pos_y)
