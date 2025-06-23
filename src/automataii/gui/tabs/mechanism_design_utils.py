"""
Utility functions for mechanism design operations.
This module contains standalone utility functions that don't depend on class state.
"""


import numpy as np
from PyQt6.QtGui import QPainterPath


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
    points = np.array([[path.elementAt(i).x, path.elementAt(i).y] for i in range(path.elementCount())])
    return points


def convert_json_params_to_internal(mechanism_type: str, json_params: dict) -> dict:
    """Convert parameters from JSON format to internal format.
    
    Args:
        mechanism_type: Type of mechanism (e.g., "4-Bar", "Cam", "Gear", "Planetary Gear")
        json_params: Parameters in JSON format
        
    Returns:
        Parameters converted to internal format
    """
    if "4-Bar" in mechanism_type:
        params = {
            "l1": json_params.get('l1'),
            "l2": json_params.get('l2'),
            "l3": json_params.get('l3'),
            "l4": json_params.get('l4'),
        }
        # Handle both formats: nested coupler_point and direct p_x/p_y
        coupler_point = json_params.get("coupler_point", {})
        if coupler_point:
            params["coupler_point_x"] = coupler_point.get("x", 0.0)
            params["coupler_point_y"] = coupler_point.get("y", 0.0)
        else:
            # Fallback to p_x/p_y format used in dataset generator
            params["coupler_point_x"] = json_params.get('p_x', 0.0)
            params["coupler_point_y"] = json_params.get('p_y', 0.0)
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
