# src/automataii/gui/tabs/mechanism_design/utils.py
import logging
import numpy as np
from PyQt6.QtCore import QPointF
from automataii.gui.dialogs.recommendation_dialog import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)

logger = logging.getLogger(__name__)

def get_scene_transform_function(layer_data):
    """
    Creates a function to transform mechanism coordinates to scene coordinates,
    using the transformation parameters from the recommendation system.
    """
    transform_params = layer_data.get("transform_params")
    target_path = layer_data.get("generated_path")

    if not transform_params or not target_path:
        return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

    try:
        center = np.array(transform_params["center"])
        scale = transform_params["scale"]
        rotation_angle = transform_params["rotation"]

        if np.isclose(scale, 0):
            scale = 1.0

        rotation_matrix = np.array([
            [np.cos(rotation_angle), -np.sin(rotation_angle)],
            [np.sin(rotation_angle), np.cos(rotation_angle)]
        ])

        user_path_np = utils_qpainterpath_to_numpy_array(target_path)
        if user_path_np is None or len(user_path_np) == 0:
            return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

        user_center = np.mean(user_path_np, axis=0)
        user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
        user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 1.0

        def to_scene_coords(p_orig):
            if p_orig is None or len(p_orig) != 2:
                return QPointF(user_center[0], user_center[1])
            
            p_centered = np.array(p_orig) - center
            p_scaled = p_centered / scale
            p_rotated = p_scaled @ rotation_matrix.T
            final_point = p_rotated * user_scale + user_center
            return QPointF(float(final_point[0]), float(final_point[1]))

        return to_scene_coords

    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Error creating transform function: {e}. Using identity transform.")
        return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

def extract_key_points_from_simulation(full_sim_data, mechanism_type):
    """Extracts key points from full simulation data for initial visualization."""
    key_points = {}
    if not full_sim_data:
        return key_points

    try:
        if mechanism_type == "4_bar_linkage" and "joint_positions" in full_sim_data:
            joint_pos = full_sim_data["joint_positions"]
            if "p1_positions" in joint_pos and joint_pos["p1_positions"]:
                key_points["ground_pivot_1"] = joint_pos["p1_positions"][0]
            if "p2_positions" in joint_pos and joint_pos["p2_positions"]:
                key_points["ground_pivot_2"] = joint_pos["p2_positions"][0]
            if "p3_positions" in joint_pos and joint_pos["p3_positions"]:
                key_points["crank_end"] = joint_pos["p3_positions"][0]
            if "p4_positions" in joint_pos and joint_pos["p4_positions"]:
                key_points["rocker_end"] = joint_pos["p4_positions"][0]
            if "coupler_path" in full_sim_data and full_sim_data["coupler_path"]:
                 key_points["coupler"] = full_sim_data["coupler_path"][0]

    except (KeyError, IndexError) as e:
        logger.warning(f"Could not extract key points from simulation data: {e}")

    return key_points
