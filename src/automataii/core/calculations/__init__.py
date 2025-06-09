"""Pure calculation functions for testability."""

from .geometry import (
    calculate_distance,
    calculate_angle,
    calculate_midpoint,
    normalize_vector,
    rotate_point,
    calculate_bounds,
    point_on_line_closest_to_point
)

from .path_analysis import (
    calculate_path_length,
    sample_path_points,
    simplify_path,
    calculate_path_curvature,
    find_path_intersections,
    calculate_path_bounds
)

from .mechanism_math import (
    calculate_linkage_angles,
    check_grashof_condition,
    calculate_cam_profile,
    calculate_gear_ratio,
    solve_four_bar_position
)

__all__ = [
    # Geometry
    'calculate_distance',
    'calculate_angle',
    'calculate_midpoint',
    'normalize_vector',
    'rotate_point',
    'calculate_bounds',
    'point_on_line_closest_to_point',
    
    # Path analysis
    'calculate_path_length',
    'sample_path_points',
    'simplify_path',
    'calculate_path_curvature',
    'find_path_intersections',
    'calculate_path_bounds',
    
    # Mechanism math
    'calculate_linkage_angles',
    'check_grashof_condition',
    'calculate_cam_profile',
    'calculate_gear_ratio',
    'solve_four_bar_position'
]