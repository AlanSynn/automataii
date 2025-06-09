"""Pure functions for mechanism calculations."""

import math
from typing import Tuple, List, Optional, Dict
import cmath


def check_grashof_condition(
    link_lengths: Tuple[float, float, float, float]
) -> Tuple[bool, str]:
    """Check if four-bar linkage satisfies Grashof condition.
    
    Args:
        link_lengths: Tuple of (a, b, c, d) link lengths
        
    Returns:
        Tuple of (is_grashof, mechanism_type)
        mechanism_type: "crank-rocker", "double-crank", "double-rocker", "non-grashof"
    """
    a, b, c, d = link_lengths
    
    # Find shortest and longest links
    lengths = sorted(link_lengths)
    s = lengths[0]  # shortest
    l = lengths[3]  # longest
    p = lengths[1]
    q = lengths[2]
    
    # Grashof condition: s + l <= p + q
    is_grashof = (s + l) <= (p + q)
    
    if not is_grashof:
        return False, "non-grashof"
    
    # Determine mechanism type based on which link is shortest
    if link_lengths[0] == s:  # Frame is shortest
        mechanism_type = "double-crank"
    elif link_lengths[1] == s:  # Crank is shortest
        mechanism_type = "crank-rocker"
    elif link_lengths[2] == s:  # Coupler is shortest
        mechanism_type = "double-rocker"
    else:  # Output is shortest
        mechanism_type = "crank-rocker"
    
    return True, mechanism_type


def solve_four_bar_position(
    a: float, b: float, c: float, d: float,
    theta2: float, 
    theta1: float = 0.0
) -> List[Tuple[float, float]]:
    """Solve four-bar linkage position analysis.
    
    Args:
        a: Ground link length
        b: Input link length
        c: Coupler link length
        d: Output link length
        theta2: Input angle (radians)
        theta1: Ground angle (radians, usually 0)
        
    Returns:
        List of solutions [(theta3, theta4), ...] or empty if no solution
    """
    # Convert to complex notation
    r1 = a * cmath.exp(1j * theta1)
    r2 = b * cmath.exp(1j * theta2)
    
    # Loop closure equation: r2 + r3 = r1 + r4
    # Rearranging: r3 - r4 = r1 - r2
    
    # Let R = r1 - r2
    R = r1 - r2
    R_mag = abs(R)
    R_angle = cmath.phase(R)
    
    # Check triangle inequality
    if R_mag > c + d or R_mag < abs(c - d):
        return []  # No solution
    
    # Use law of cosines to find angle between r3 and R
    cos_beta = (c**2 + R_mag**2 - d**2) / (2 * c * R_mag)
    
    # Check for valid cosine value
    if abs(cos_beta) > 1:
        return []
    
    beta = math.acos(cos_beta)
    
    # Two possible solutions
    solutions = []
    
    # Solution 1
    theta3_1 = R_angle + beta
    r3_1 = c * cmath.exp(1j * theta3_1)
    r4_1 = r1 + r3_1 - r2
    theta4_1 = cmath.phase(r4_1)
    solutions.append((theta3_1, theta4_1))
    
    # Solution 2 (if beta != 0)
    if abs(beta) > 1e-10:
        theta3_2 = R_angle - beta
        r3_2 = c * cmath.exp(1j * theta3_2)
        r4_2 = r1 + r3_2 - r2
        theta4_2 = cmath.phase(r4_2)
        solutions.append((theta3_2, theta4_2))
    
    return solutions


def calculate_linkage_angles(
    pivot_a: Tuple[float, float],
    pivot_b: Tuple[float, float],
    target: Tuple[float, float],
    link_a_length: float,
    link_b_length: float
) -> Optional[Tuple[float, float]]:
    """Calculate angles for two-link system to reach target.
    
    Args:
        pivot_a: Fixed pivot point A
        pivot_b: Fixed pivot point B
        target: Target point to reach
        link_a_length: Length of link from pivot A
        link_b_length: Length of link from pivot B
        
    Returns:
        Tuple of (angle_a, angle_b) in radians, or None if unreachable
    """
    # Distance from pivots to target
    dist_a = math.sqrt((target[0] - pivot_a[0])**2 + (target[1] - pivot_a[1])**2)
    dist_b = math.sqrt((target[0] - pivot_b[0])**2 + (target[1] - pivot_b[1])**2)
    
    # Check if target is reachable
    if dist_a > link_a_length or dist_b > link_b_length:
        return None
    
    # Calculate angles
    angle_a = math.atan2(target[1] - pivot_a[1], target[0] - pivot_a[0])
    angle_b = math.atan2(target[1] - pivot_b[1], target[0] - pivot_b[0])
    
    return (angle_a, angle_b)


def calculate_cam_profile(
    motion_curve: List[float],
    base_radius: float,
    roller_radius: float = 0.0
) -> List[Tuple[float, float]]:
    """Calculate cam profile from follower motion.
    
    Args:
        motion_curve: List of follower displacements
        base_radius: Base circle radius
        roller_radius: Roller follower radius (0 for knife edge)
        
    Returns:
        List of cam profile points (x, y)
    """
    num_points = len(motion_curve)
    if num_points < 3:
        return []
    
    profile_points = []
    
    for i, displacement in enumerate(motion_curve):
        # Angle for this point
        theta = 2 * math.pi * i / num_points
        
        # Radius at this angle
        r = base_radius + displacement + roller_radius
        
        # Convert to Cartesian
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        
        profile_points.append((x, y))
    
    return profile_points


def calculate_gear_ratio(
    teeth_driver: int,
    teeth_driven: int
) -> float:
    """Calculate gear ratio.
    
    Args:
        teeth_driver: Number of teeth on driver gear
        teeth_driven: Number of teeth on driven gear
        
    Returns:
        Gear ratio (driven/driver)
    """
    if teeth_driver <= 0:
        return 0.0
    
    return teeth_driven / teeth_driver


def calculate_gear_centers_distance(
    module: float,
    teeth1: int,
    teeth2: int
) -> float:
    """Calculate center distance between two gears.
    
    Args:
        module: Gear module
        teeth1: Teeth on first gear
        teeth2: Teeth on second gear
        
    Returns:
        Center distance
    """
    # Pitch diameters
    d1 = module * teeth1
    d2 = module * teeth2
    
    # Center distance
    return (d1 + d2) / 2


def calculate_instant_center(
    vel_a: Tuple[float, float],
    pos_a: Tuple[float, float],
    vel_b: Tuple[float, float],
    pos_b: Tuple[float, float]
) -> Optional[Tuple[float, float]]:
    """Calculate instant center of rotation for two points.
    
    Args:
        vel_a: Velocity of point A
        pos_a: Position of point A
        vel_b: Velocity of point B
        pos_b: Position of point B
        
    Returns:
        Instant center position or None if not found
    """
    # Velocity vectors must be perpendicular to lines from IC
    # This gives us two lines; their intersection is the IC
    
    # If velocities are parallel, IC is at infinity
    cross = vel_a[0] * vel_b[1] - vel_a[1] * vel_b[0]
    if abs(cross) < 1e-10:
        return None
    
    # Lines perpendicular to velocities through points
    # Line A: vel_a[0] * (x - pos_a[0]) + vel_a[1] * (y - pos_a[1]) = 0
    # Line B: vel_b[0] * (x - pos_b[0]) + vel_b[1] * (y - pos_b[1]) = 0
    
    # Solve for intersection
    det = vel_a[0] * vel_b[1] - vel_a[1] * vel_b[0]
    if abs(det) < 1e-10:
        return None
    
    c_a = vel_a[0] * pos_a[0] + vel_a[1] * pos_a[1]
    c_b = vel_b[0] * pos_b[0] + vel_b[1] * pos_b[1]
    
    x = (c_a * vel_b[1] - c_b * vel_a[1]) / det
    y = (vel_a[0] * c_b - vel_b[0] * c_a) / det
    
    return (x, y)


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-π, π] range.
    
    Args:
        angle: Angle in radians
        
    Returns:
        Normalized angle
    """
    # Normalize to [0, 2π]
    angle = angle % (2 * math.pi)
    
    # Convert to [-π, π]
    if angle > math.pi:
        angle -= 2 * math.pi
    
    return angle