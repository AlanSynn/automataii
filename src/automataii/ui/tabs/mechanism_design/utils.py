# src/automataii/gui/tabs/mechanism_design/utils.py
import logging

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.ui.dialogs.recommendation_dialog import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)

logger = logging.getLogger(__name__)


def get_dialog_transform_for_sim_data(layer_data, path_key: str):
    """
    EXACT copy of the recommendation dialog's _get_transform_for_sim_data method.
    This ensures perfect visual consistency by using the SAME transformation logic.
    """
    full_sim_data = layer_data.get("full_simulation_data", {})
    mech_path = np.array(full_sim_data.get(path_key, []))
    user_path_aligned = layer_data.get("user_path_aligned_np")

    if mech_path.size == 0 or user_path_aligned is None:
        return None

    # EXACT same logic as dialog
    mech_center = np.mean(mech_path, axis=0)
    user_center = np.mean(user_path_aligned, axis=0)

    mech_bbox = np.max(mech_path, axis=0) - np.min(mech_path, axis=0)
    user_bbox = np.max(user_path_aligned, axis=0) - np.min(user_path_aligned, axis=0)

    mech_size = np.max(mech_bbox)
    user_size = np.max(user_bbox)
    scale_factor = user_size / mech_size if mech_size > 0 else 1.0

    def to_scene_coords_exact_dialog(p_orig):
        """EXACT same logic as dialog's to_screen_coords function with QTransform equivalent"""
        if p_orig is None or len(p_orig) != 2:
            return QPointF(user_center[0], user_center[1])

        p_orig_array = np.array(p_orig)
        p_centered = p_orig_array - mech_center
        p_scaled = p_centered * scale_factor
        p_final = p_scaled + user_center

        # Apply the dialog's EXACT QTransform logic for scene mapping
        target_path = layer_data.get("generated_path")
        if target_path:
            user_path_np = utils_qpainterpath_to_numpy_array(target_path)
            if user_path_np is not None:
                # Calculate scene bounds - this is our "draw_area" equivalent
                scene_center = np.mean(user_path_np, axis=0)
                scene_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
                scene_size = np.max(scene_bbox)

                # EXACT same QTransform logic as dialog:
                # source_rect_size = 2.2 (normalized space [-1.1, 1.1] x [-1.1, 1.1])
                # scale = draw_area.size / source_rect_size * 0.9
                source_rect_size = 2.2
                dialog_scale = scene_size / source_rect_size * 0.9  # Same 90% margin as dialog

                # Apply QTransform equivalent:
                # 1. Translate to center
                # 2. Scale (dialog uses positive y-scale)
                p_point = QPointF(p_final[0], p_final[1])

                # This mimics: transform.map(QPointF(p_final[0], p_final[1]))
                # where transform has translate(center) and scale(dialog_scale)
                transformed_x = scene_center[0] + p_point.x() * dialog_scale
                transformed_y = scene_center[1] + p_point.y() * dialog_scale

                return QPointF(float(transformed_x), float(transformed_y))

        # Fallback: use scene scaling approximation
        return QPointF(float(p_final[0] * 100), float(p_final[1] * 100))

    return to_scene_coords_exact_dialog


def get_scene_transform_function(layer_data):
    """
    Creates a function to transform mechanism coordinates to scene coordinates,
    using the EXACT same transformation as the recommendation dialog preview.
    This ensures perfect visual consistency between dialog and main scene.
    """
    transform_params = layer_data.get("transform_params")
    target_path = layer_data.get("generated_path")
    full_sim_data = layer_data.get("full_simulation_data", {})

    logger.info(f"Creating transform function. Has transform_params: {transform_params is not None}, Has target_path: {target_path is not None}")

    # First priority: Use dialog's exact sim data transform if available
    mech_type = layer_data.get("original_json_type", layer_data.get("type"))

    # Try to get the dialog's exact transform for different mechanism types
    dialog_transform = None
    if mech_type == "4-bar Coupler" and "joint_positions" in full_sim_data:
        dialog_transform = get_dialog_transform_for_sim_data(layer_data, "coupler_path")
    elif mech_type in ["Cam-Follower", "Cam Follower"] and "cam_data" in full_sim_data:
        dialog_transform = get_dialog_transform_for_sim_data(layer_data, "follower_path")
    elif mech_type in ["Simple Gear", "Gear Contact"] and "gear_data" in full_sim_data:
        dialog_transform = get_dialog_transform_for_sim_data(layer_data, "tracking_points")
    elif mech_type == "Planetary Gear" and "gear_positions" in full_sim_data:
        dialog_transform = get_dialog_transform_for_sim_data(layer_data, "tracking_points")

    if dialog_transform:
        logger.info(f"Using EXACT dialog simulation transform for {mech_type}")
        return dialog_transform

    # If no transform params or target path, use the mechanism as-is but with some scaling
    if not transform_params:
        logger.warning("No transform_params found, using default scaling transform")
        def default_transform(p_orig):
            if p_orig is None or len(p_orig) != 2:
                return QPointF()
            # Just scale to scene units
            return QPointF(p_orig[0] * 2.0, p_orig[1] * 2.0)
        return default_transform

    if not target_path:
        logger.warning("No target_path found, using identity transform")
        return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

    try:
        # Use the EXACT same transformation logic as the recommendation dialog preview
        user_path_aligned = layer_data.get("user_path_aligned_np")
        mech_path_aligned = layer_data.get("mech_path_aligned_np")

        if user_path_aligned is not None and mech_path_aligned is not None:
            # This is the key: use the EXACT aligned coordinates from the dialog
            # Map from the dialog's normalized space to the scene's user path space

            # Get the target path center and size in scene coordinates
            user_path_np = utils_qpainterpath_to_numpy_array(target_path)
            if user_path_np is None or len(user_path_np) == 0:
                return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

            scene_center = np.mean(user_path_np, axis=0)
            scene_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            scene_scale = np.max(scene_bbox) / 2.2  # Same normalization as dialog (2.2 is the dialog's normalized space size)

            logger.info(f"Using EXACT dialog alignment - scene_center: {scene_center}, scene_scale: {scene_scale}")

            def to_scene_coords_aligned(p_orig):
                if p_orig is None or len(p_orig) != 2:
                    return QPointF(scene_center[0], scene_center[1])

                # p_orig is already in the dialog's aligned coordinate system
                # Just scale it to match the scene's target path size
                p_array = np.array(p_orig)
                final_point = p_array * scene_scale + scene_center
                return QPointF(float(final_point[0]), float(final_point[1]))

            return to_scene_coords_aligned

        else:
            # Fallback to original transform logic when aligned data not available
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            if np.isclose(scale, 0):
                scale = 1.0

            rotation_matrix = np.array(
                [
                    [np.cos(rotation_angle), -np.sin(rotation_angle)],
                    [np.sin(rotation_angle), np.cos(rotation_angle)],
                ]
            )

            user_path_np = utils_qpainterpath_to_numpy_array(target_path)
            if user_path_np is None or len(user_path_np) == 0:
                return lambda p: QPointF(p[0], p[1]) if p is not None and len(p) == 2 else QPointF()

            user_center = np.mean(user_path_np, axis=0)
            user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 1.0

            logger.info(f"Using fallback transform - user_center: {user_center}, user_scale: {user_scale}")

            def to_scene_coords_fallback(p_orig):
                if p_orig is None or len(p_orig) != 2:
                    return QPointF(user_center[0], user_center[1])

                p_centered = np.array(p_orig) - center
                p_scaled = p_centered / scale
                p_rotated = p_scaled @ rotation_matrix.T
                final_point = p_rotated * user_scale + user_center
                return QPointF(float(final_point[0]), float(final_point[1]))

            return to_scene_coords_fallback

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


"""
Utility functions for mechanism design operations.
This module contains standalone utility functions that don't depend on class state.
"""


def qpainterpath_to_numpy_array(path: QPainterPath, num_points: int = 100) -> np.ndarray | None:
    """Convert QPainterPath to numpy array of points.

    Args:
        path: QPainterPath to convert
        num_points: Number of points to extract (not used in current implementation)

    Returns:
        numpy array of shape (n, 2) containing x, y coordinates, or None if path is empty
    """
    if path.isEmpty():
        return None
    points = np.array(
        [[path.elementAt(i).x, path.elementAt(i).y] for i in range(path.elementCount())]
    )
    return points


def convert_json_params_to_internal(mechanism_type: str, json_params: dict) -> dict:
    """Convert parameters from JSON format to internal format.

    Args:
        mechanism_type: Type of mechanism (e.g., "4-Bar", "Cam", "Gear", "Planetary Gear")
        json_params: Parameters in JSON format

    Returns:
        Parameters converted to internal format
    """
    logger.info(f"Converting params for type: {mechanism_type}, input params: {json_params}")

    if "4-Bar" in mechanism_type or "4-bar" in mechanism_type:
        params = {
            "l1": json_params.get("l1"),
            "l2": json_params.get("l2"),
            "l3": json_params.get("l3"),
            "l4": json_params.get("l4"),
        }
        # Handle both formats: nested coupler_point and direct p_x/p_y
        coupler_point = json_params.get("coupler_point", {})
        if coupler_point:
            params["coupler_point_x"] = coupler_point.get("x", 0.0)
            params["coupler_point_y"] = coupler_point.get("y", 0.0)
        else:
            # Fallback to p_x/p_y format used in dataset generator
            params["coupler_point_x"] = json_params.get("p_x", 0.0)
            params["coupler_point_y"] = json_params.get("p_y", 0.0)

        # Also keep p_x, p_y for compatibility with visuals
        params["p_x"] = params["coupler_point_x"]
        params["p_y"] = params["coupler_point_y"]

        logger.info(f"Converted 4-bar params: {params}")
        return params

    elif "Cam" in mechanism_type:
        params = {
            "base_radius": json_params.get("base_radius", 25.0),
            "eccentricity": json_params.get("eccentricity", 10.0),
        }
        return params

    elif "Gear" in mechanism_type:
        params = {
            "r1": json_params.get("r1", 30),
            "r2": json_params.get("r2", 50),
        }
        return params

    elif "Planetary Gear" in mechanism_type:
        params = {
            "r_sun": json_params.get("r_sun", 20),
            "r_planet": json_params.get("r_planet", 30),
            "arm_length": json_params.get("arm_length", 15),
        }
        return params

    return json_params
