"""
Cached computation functions for mechanism calculations.

Uses functools.lru_cache for memoization of expensive pure computations.
All functions in this module must be pure (no side effects, deterministic output).
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# Type alias for cached tuple results
Point2D = tuple[float, float]


@lru_cache(maxsize=512)
def compute_fourbar_geometry(
    ground: float,
    input_l: float,
    coupler: float,
    output: float,
    input_angle_deg: float,
) -> tuple[Point2D, Point2D, Point2D, Point2D, float] | None:
    """
    Compute four-bar linkage geometry for a given input angle.

    Returns:
        Tuple of (O1, O4, A, B, output_angle_rad) or None if invalid.

    Time Complexity: O(1)
    Space Complexity: O(1)

    Note: Uses open-loop kinematics without assembly mode tracking.
    For animation, use FourBarMechanism.compute_state() which tracks state.
    """
    input_angle = math.radians(input_angle_deg)

    O1: Point2D = (-ground / 2, 0.0)
    O4: Point2D = (ground / 2, 0.0)

    A: Point2D = (
        O1[0] + input_l * math.cos(input_angle),
        O1[1] + input_l * math.sin(input_angle),
    )

    # Solve for output angle using law of cosines
    Ax, Ay = A
    O4x, O4y = O4
    L = math.sqrt((O4x - Ax) ** 2 + (O4y - Ay) ** 2)

    # Check reachability
    if L > (coupler + output) or L < abs(coupler - output):
        return None

    # Compute output angle
    alpha = math.atan2(Ay - O4y, Ax - O4x)

    try:
        cos_beta = (output * output + L * L - coupler * coupler) / (2 * output * L)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
    except (ValueError, ZeroDivisionError):
        return None

    # Choose assembly mode (default to positive beta)
    output_angle = alpha + beta

    B: Point2D = (
        O4[0] + output * math.cos(output_angle),
        O4[1] + output * math.sin(output_angle),
    )

    return (O1, O4, A, B, output_angle)


@lru_cache(maxsize=128)
def compute_grashof_condition(
    ground: float, input_l: float, coupler: float, output: float
) -> tuple[bool, float, str]:
    """
    Check Grashof condition for a four-bar linkage.

    Returns:
        Tuple of (is_grashof, ratio, classification)

    Time Complexity: O(1)
    """
    links = sorted([ground, input_l, coupler, output])
    s, p, q, l = links

    grashof_sum = s + l
    middle_sum = p + q
    is_grashof = grashof_sum <= middle_sum
    ratio = grashof_sum / middle_sum if middle_sum > 0 else float("inf")

    if is_grashof:
        # Find which link is shortest
        link_names = ["ground", "input", "coupler", "output"]
        lengths = [ground, input_l, coupler, output]
        shortest_idx = lengths.index(min(lengths))
        shortest_name = link_names[shortest_idx]

        if shortest_name == "ground":
            classification = "Double-Crank"
        elif shortest_name in ["input", "output"]:
            classification = "Crank-Rocker"
        else:
            classification = "Double-Rocker"
    else:
        classification = "Triple-Rocker"

    return (is_grashof, ratio, classification)


@lru_cache(maxsize=256)
def compute_cam_profile_points(
    cam_radius: float,
    cam_offset: float,
    cam_lobes: int,
    profile_harmonic: float,
    num_points: int = 72,
) -> tuple[tuple[float, float], ...]:
    """
    Compute cam profile points (unrotated).

    Returns:
        Tuple of (x, y) points for the cam profile at angle=0.

    Time Complexity: O(n) where n = num_points
    """
    points = []
    for i in range(num_points):
        theta = (i * 2 * math.pi) / num_points

        base_radius = cam_radius
        primary_variation = cam_offset * math.cos(cam_lobes * theta)
        secondary_variation = (cam_offset * profile_harmonic) * math.cos(
            2 * cam_lobes * theta
        )

        radius = base_radius + primary_variation + secondary_variation
        x = radius * math.cos(theta)
        y = radius * math.sin(theta)
        points.append((x, y))

    return tuple(points)


@lru_cache(maxsize=512)
def compute_cam_contact_radius(
    cam_radius: float,
    cam_offset: float,
    cam_lobes: int,
    profile_harmonic: float,
    cam_angle_deg: float,
) -> float:
    """
    Compute the contact radius at the follower position.

    Time Complexity: O(1)
    """
    cam_angle = math.radians(cam_angle_deg)
    follower_contact_theta = -math.pi / 2
    theta_normalized = (follower_contact_theta - cam_angle) % (2 * math.pi)

    base_radius = cam_radius
    primary_variation = cam_offset * math.cos(cam_lobes * theta_normalized)
    secondary_variation = (cam_offset * profile_harmonic) * math.cos(
        2 * cam_lobes * theta_normalized
    )

    return base_radius + primary_variation + secondary_variation


@lru_cache(maxsize=360)
def compute_transmission_angle(
    ground: float,
    input_l: float,
    coupler: float,
    output: float,
    input_angle_deg: float,
) -> float | None:
    """
    Compute transmission angle for a four-bar linkage.

    Returns:
        Transmission angle in degrees, or None if position is unreachable.

    Time Complexity: O(1)
    """
    input_angle = math.radians(input_angle_deg)

    O1 = (-ground / 2, 0)
    O4 = (ground / 2, 0)
    A = (O1[0] + input_l * math.cos(input_angle), O1[1] + input_l * math.sin(input_angle))

    distance_AO4 = math.sqrt((A[0] - O4[0]) ** 2 + (A[1] - O4[1]) ** 2)

    max_reach = coupler + output
    min_reach = abs(coupler - output)

    if distance_AO4 > max_reach or distance_AO4 < min_reach:
        return None

    try:
        cos_gamma = (coupler * coupler + output * output - distance_AO4 * distance_AO4) / (
            2 * coupler * output
        )
        cos_gamma = max(-1.0, min(1.0, cos_gamma))
        return math.degrees(math.acos(abs(cos_gamma)))
    except (ValueError, ZeroDivisionError):
        return None


def get_cache_stats() -> dict[str, dict]:
    """Return cache statistics for all cached functions."""
    from typing import Any, cast

    cached_funcs: list[tuple[str, Any]] = [
        ("fourbar_geometry", compute_fourbar_geometry),
        ("grashof_condition", compute_grashof_condition),
        ("cam_profile_points", compute_cam_profile_points),
        ("cam_contact_radius", compute_cam_contact_radius),
        ("transmission_angle", compute_transmission_angle),
    ]

    stats = {}
    for name, func in cached_funcs:
        info = cast(Any, func).cache_info()
        stats[name] = {
            "hits": info.hits,
            "misses": info.misses,
            "maxsize": info.maxsize,
            "currsize": info.currsize,
            "hit_rate": info.hits / (info.hits + info.misses) if (info.hits + info.misses) > 0 else 0,
        }

    return stats


def clear_all_caches() -> None:
    """Clear all mechanism computation caches."""
    compute_fourbar_geometry.cache_clear()
    compute_grashof_condition.cache_clear()
    compute_cam_profile_points.cache_clear()
    compute_cam_contact_radius.cache_clear()
    compute_transmission_angle.cache_clear()
