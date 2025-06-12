import numpy as np
import math
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath
from automataii.gui.dialogs.recommendation_dialog import qpainterpath_to_numpy_array

def get_scene_transform_function(layer_data: dict) -> Optional[callable]:
    """
    Creates a function to transform points from mechanism's original space to scene space.
    """
    target_path = layer_data.get("generated_path")
    transform_params = layer_data.get("transform_params")
    vis_params = layer_data.get("visualization_params")

    if not all([target_path, transform_params, vis_params]):
        return None

    user_path_np = qpainterpath_to_numpy_array(target_path)
    if user_path_np is None:
        return None

    # Get transformation parameters from alignment
    center = np.array(vis_params["center"])
    scale = vis_params["scale"]
    angle = transform_params["rotation"]

    if np.isclose(scale, 0):
        return None

    rotation_matrix = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])

    # Determine the scale and position of the user's original path in the scene
    user_path_center = np.mean(user_path_np, axis=0)
    user_path_size = np.max(np.ptp(user_path_np, axis=0))

    # The mechanism's normalized path has a size of 2.0 (from -1 to 1)
    # We need to find the size of the mechanism's path in its original coordinates
    full_sim_data = layer_data.get("full_simulation_data", {})
    if "coupler_path" not in full_sim_data:
        return None

    coupler_path_orig = np.array(full_sim_data["coupler_path"])
    mech_path_size_orig = np.max(np.ptp(coupler_path_orig, axis=0))

    if np.isclose(mech_path_size_orig, 0):
        final_scale_factor = 1.0
    else:
        # The scale from vis_params normalizes the entire mechanism, not just the path.
        # We use it to get the normalized size of the path.
        mech_path_norm_size = mech_path_size_orig / scale
        final_scale_factor = user_path_size / mech_path_norm_size

    def to_scene_coords(p_orig: np.ndarray) -> QPointF:
        # 1. Normalize the original mechanism point using the whole mechanism's vis_params
        p_norm = (p_orig - center) / scale

        # 2. Rotate it by the alignment angle
        p_rotated = p_norm @ rotation_matrix.T

        # 3. Scale it to match the user's path size
        p_rescaled = p_rotated * final_scale_factor

        # 4. Translate it to the user's path center
        coupler_path_norm = (coupler_path_orig - center) / scale
        coupler_path_rotated_norm = coupler_path_norm @ rotation_matrix.T
        norm_path_center = np.mean(coupler_path_rotated_norm, axis=0)

        p_final = p_rescaled - (norm_path_center * final_scale_factor) + user_path_center

        return QPointF(p_final[0], p_final[1])

    return to_scene_coords
