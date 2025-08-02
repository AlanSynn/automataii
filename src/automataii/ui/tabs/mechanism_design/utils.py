# src/automataii/gui/tabs/mechanism_design/utils.py
import logging

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath

from automataii.ui.dialogs.recommendation_dialog import (
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

    logger.info(f"Creating transform function. Has transform_params: {transform_params is not None}, Has target_path: {target_path is not None}")
    
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
        # Check if we have aligned paths - this is the most accurate way
        user_path_aligned = layer_data.get("user_path_aligned_np")
        mech_path_aligned = layer_data.get("mech_path_aligned_np")
        
        if user_path_aligned is not None and transform_params:
            # Use the same transformation as in the recommendation dialog
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
            
            # Use aligned user path center as the target
            user_center = np.mean(user_path_aligned, axis=0)
            user_bbox = np.max(user_path_aligned, axis=0) - np.min(user_path_aligned, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 1.0
            
            logger.info(f"Using aligned paths transform - user_center: {user_center}, user_scale: {user_scale}")
        else:
            # Fallback to target path analysis
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
            
            logger.info(f"Using target path transform - user_center: {user_center}, user_scale: {user_scale}")

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
