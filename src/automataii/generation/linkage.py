"""Module for generating n-bar linkage mechanisms."""
import logging
import math
from typing import Optional, Dict, List, Any, Tuple
from PyQt6.QtCore import QPointF, QLineF
from PyQt6.QtGui import QPainterPath
import numpy as np # For more complex geometry if needed in future

# Placeholder for more sophisticated data structures if needed
# from ...core.models import Link, Pivot Point, etc.

# Default color palettes for visualization consistency if needed here
# (though usually colors are decided by the visualizer)
LINK_COLORS_FRONT = ['skyblue', 'lightcoral', 'lightgreen', 'silver']
LINK_COLORS_BACK = ['steelblue', 'indianred', 'seagreen', 'darkgray']
PIN_COLORS_FRONT = ['blue', 'red', 'green', 'black']
PIN_COLORS_BACK = ['darkblue', 'darkred', 'darkgreen', 'dimgray']

def generate_3bar_linkage(
    base_pos: QPointF = QPointF(0,0),
    scale: float = 1.0,
    link_lengths: Optional[Dict[str, float]] = None,
    input_angle_deg: float = 30.0
) -> Optional[Dict[str, Any]]:
    """
    Generates data for a representative 3-bar linkage (crank-rocker type often).
    For now, this creates a fixed geometry 3-bar linkage, not synthesized from a path.
    The "3-bar" here refers to a grounded crank, a coupler, and a rocker/slider.
    This example will be a crank, coupler, and a coupler extension point.
    The ground is implicit.

    Args:
        base_pos: QPointF, the position of the first pivot (p0, crank pivot).
        scale: float, a scaling factor for default link lengths.
        link_lengths: Optional dictionary like {"l1": 50, "l2": 70, "l3_coupler_ext": 40}.
                      l1: crank, l2: coupler.
                      l3_coupler_ext: length from coupler joint (p1) to coupler point (p_coupler_end).
        input_angle_deg: float, the angle of the crank (l1) in degrees.

    Returns:
        A dictionary containing the linkage data, or None if generation fails.
        Points are relative to the scene (base_pos is the origin for the linkage).
    """
    if link_lengths is None:
        l1 = 50 * scale  # Crank
        l2 = 70 * scale  # Coupler
        l3_ext = 40 * scale # Coupler extension from p1 towards a coupler point
    else:
        l1 = link_lengths.get("l1", 50 * scale)
        l2 = link_lengths.get("l2", 70 * scale)
        l3_ext = link_lengths.get("l3_coupler_ext", 40 * scale)

    if not all(l > 0 for l in [l1, l2, l3_ext]):
        # print("Warning: 3-bar linkage lengths must be positive.")
        return None

    theta1_rad = math.radians(input_angle_deg)

    p0 = QPointF(base_pos.x(), base_pos.y())
    p1 = p0 + QPointF(l1 * math.cos(theta1_rad), l1 * math.sin(theta1_rad))

    # For a simple 3-bar, p2 (end of coupler) could be a fixed pivot or slider guide.
    # Here, we are defining a coupler point based on an extension from p1.
    # Let's assume the coupler (l2) connects p1 to an imaginary p2 for calculation,
    # and the actual "output" is p_coupler_end.
    # For a simple 3-bar display (crank + coupler + point on coupler):
    # We define p1. The link l2 starts at p1. We need a direction for l2.
    # Let coupler make an angle, say, -30 deg relative to crank for visual separation
    coupler_angle_rel_rad = math.radians(-45) # Angle of coupler relative to crank
    theta_coupler_rad = theta1_rad + coupler_angle_rel_rad
    p2_imaginary = p1 + QPointF(l2 * math.cos(theta_coupler_rad), l2 * math.sin(theta_coupler_rad))

    # The coupler extension point (p_coupler_end) extends from p1 along the coupler l2 direction by l3_ext
    # Or, for more general look, let l3_ext be a point on the coupler body (triangle p0-p1-p_coupler_end).
    # For this example, let's make the "coupler" link from p1 to p2_imaginary, and p_coupler_end an extension.
    # Or simplify: l1 is crank, l2 is a link attached to p1, and p_coupler_end is its end.
    # Let's redefine: l1=crank, l2=coupler link from p1. p_coupler_end is not used directly from l3_ext.
    # Instead, l2 is the main coupler arm. This makes it a 2-link open chain for visualization.
    p2 = p1 + QPointF(l2 * math.cos(theta_coupler_rad), l2 * math.sin(theta_coupler_rad))

    points = {
        "p0": [p0.x(), p0.y()],
        "p1": [p1.x(), p1.y()],
        "p2": [p2.x(), p2.y()], # This is effectively the end of the second link.
                                # For a true 3-bar with a third grounded pivot, IK is needed for p2.
                                # For now, this is an open chain: ground-p0-p1-p2.
    }
    final_link_lengths = {"l1": l1, "l2": l2} # l1=p0-p1, l2=p1-p2

    return {
        "type": "linkage",
        "bar_type": "3-bar (Open Chain)", # Clarify that this is an open chain for visualization
        "name": "Generated 3-Bar Linkage",
        "points": points,
        "link_lengths": final_link_lengths,
        "thickness": 10 * scale * 0.2, # Example thickness
        "input_angle_deg": input_angle_deg
    }


def generate_4bar_linkage(
    base_pos: QPointF = QPointF(0,0),
    scale: float = 1.0,
    link_lengths: Optional[Dict[str, float]] = None, # l1, l2, l3, l4 (ground)
    input_angle_deg: float = 60.0 # Angle of crank l1
) -> Optional[Dict[str, Any]]:
    """
    Generates data for a representative 4-bar linkage.
    Calculates positions of p1 and p2 based on input angle theta1 for crank l1.
    Args:
        base_pos: QPointF, position of the first fixed pivot (p0).
        scale: float, scaling factor for default lengths.
        link_lengths: Optional dict like {"l1":50, "l2":70, "l3":60, "l4":80}.
                      l1=crank, l2=coupler, l3=rocker, l4=ground link length.
        input_angle_deg: float, angle of the input crank (l1) in degrees.
    Returns:
        A dictionary containing linkage data, or None if not constructible.
    """
    if link_lengths is None:
        # Default Grashofian crank-rocker proportions
        l1 = 50 * scale  # Crank (shortest)
        l4 = 80 * scale  # Ground (longest or one of longer ones)
        l2 = 70 * scale
        l3 = 60 * scale
    else:
        l1 = link_lengths.get("l1", 50 * scale)
        l2 = link_lengths.get("l2", 70 * scale)
        l3 = link_lengths.get("l3", 60 * scale)
        l4 = link_lengths.get("l4", 80 * scale)

    if not all(l > 0 for l in [l1, l2, l3, l4]):
        # print("Warning: 4-bar linkage lengths must be positive.")
        return None

    theta1_rad = math.radians(input_angle_deg)

    p0 = QPointF(base_pos.x(), base_pos.y())
    p3_fixed = QPointF(base_pos.x() + l4, base_pos.y()) # Second fixed pivot along x-axis from p0

    p1 = p0 + QPointF(l1 * math.cos(theta1_rad), l1 * math.sin(theta1_rad))

    # Solve for p2 (intersection of two circles)
    # Circle 1: center p1, radius l2
    # Circle 2: center p3_fixed, radius l3
    d_sq = (p1.x() - p3_fixed.x())**2 + (p1.y() - p3_fixed.y())**2
    d = math.sqrt(d_sq)

    # Check for constructibility
    if d > (l2 + l3) or d < abs(l2 - l3) or d == 0: # Links cannot reach or collinear issue
        # print(f"4-bar linkage not constructible with l1={l1}, l2={l2}, l3={l3}, l4={l4}, d={d:.2f}, theta1={input_angle_deg:.1f}")
        # Return a "broken" or default state if not constructible, or None
        # For previews, might want to show something still.
        # Let's return None, MainWindow can handle this by not offering it or showing a message.
        return None

    # Parameter a for Freudenstein's equation or geometric solution
    # (d^2 - l3^2 + l2^2) / (2d)
    # Check for d being zero already done
    a = (d_sq - l3**2 + l2**2) / (2 * d)

    # h = sqrt(l2^2 - a^2)
    # Ensure l2^2 - a^2 is not negative due to float precision
    h_sq = l2**2 - a**2
    if h_sq < -1e-9: # Allow small negative due to precision, but treat as non-constructible if significant
        # print(f"4-bar linkage: h_sq negative ({h_sq:.2f}), non-constructible.")
        return None
    h = math.sqrt(max(0, h_sq)) # max(0, ..) to handle tiny negatives from precision

    # Midpoint between p1 and intersection of line p1-p3_fixed and line perpendicular to p2
    p_mid_x = p3_fixed.x() + a * (p1.x() - p3_fixed.x()) / d
    p_mid_y = p3_fixed.y() + a * (p1.y() - p3_fixed.y()) / d

    # Two possible solutions for p2. Choose one (e.g., based on cross product sign for elbow up/down)
    # For consistency, let's pick one solution. This choice affects the "elbow" direction.
    # (p1.y - p3_fixed.y) / d determines sin of angle of line p3_fixed-p1
    # (p1.x - p3_fixed.x) / d determines cos of angle of line p3_fixed-p1

    # Solution 1 for p2:
    p2_x1 = p_mid_x + h * (p1.y() - p3_fixed.y()) / d
    p2_y1 = p_mid_y - h * (p1.x() - p3_fixed.x()) / d
    # Solution 2 for p2:
    # p2_x2 = p_mid_x - h * (p1.y() - p3_fixed.y()) / d
    # p2_y2 = p_mid_y + h * (p1.x() - p3_fixed.x()) / d

    # We'll use solution 1 (p2_x1, p2_y1)
    p2 = QPointF(p2_x1, p2_y1)

    points = {
        "p0": [p0.x(), p0.y()],
        "p1": [p1.x(), p1.y()],
        "p2": [p2.x(), p2.y()],
        "p3_fixed": [p3_fixed.x(), p3_fixed.y()]
    }
    final_link_lengths = {"l1": l1, "l2": l2, "l3": l3, "l4": l4}

    return {
        "type": "linkage",
        "bar_type": "4-bar",
        "name": "Generated 4-Bar Linkage",
        "points": points,
        "link_lengths": final_link_lengths,
        "thickness": 10 * scale * 0.2, # Example thickness
        "input_angle_deg": input_angle_deg,
        # Could add Grashof condition info here if needed
    }

if __name__ == '__main__':
    # Example Usage (mainly for illustration, QT objects might need app context)
    logging.basicConfig(level=logging.INFO)

    # Mock data for testing
    path = QPainterPath()
    path.moveTo(10, 10)
    path.lineTo(50, 50)
    path.lineTo(10, 90)

    pivot_a = QPointF(0, 0)
    pivot_d = QPointF(100, 0)

    print("--- Testing 3-Bar Linkage --- (Now an open chain: Ground-Crank-Coupler)")
    linkage_3bar_data = generate_3bar_linkage(base_pos=QPointF(10,10), scale=1.0, input_angle_deg=45)
    if linkage_3bar_data:
        print("3-Bar Data:")
        for key, value in linkage_3bar_data.items():
            print(f"  {key}: {value}")
    else:
        print("Failed to generate 3-bar linkage data.")

    print("\n--- Testing 4-Bar Linkage --- (Grashof crank-rocker by default)")
    linkage_4bar_data = generate_4bar_linkage(base_pos=QPointF(0,0), scale=1.0, input_angle_deg=30)
    if linkage_4bar_data:
        print("4-Bar Data (Default, 30 deg):")
        for key, value in linkage_4bar_data.items():
            print(f"  {key}: {value}")
    else:
        print("Failed to generate 4-bar linkage data (Default, 30 deg).")

    custom_lengths_4bar = {"l1": 30, "l2": 80, "l3": 70, "l4": 60} # Another Grashof
    linkage_4bar_custom = generate_4bar_linkage(base_pos=QPointF(50,50), link_lengths=custom_lengths_4bar, input_angle_deg=90)
    if linkage_4bar_custom:
        print("\n4-Bar Data (Custom, 90 deg):")
        for key, value in linkage_4bar_custom.items():
            print(f"  {key}: {value}")
    else:
        print("\nFailed to generate 4-bar linkage data (Custom, 90 deg).")

    # Test non-constructible 4-bar
    non_constructible_lengths = {"l1": 20, "l2": 20, "l3": 20, "l4": 100} # l1+l2+l3 < l4
    linkage_4bar_fail = generate_4bar_linkage(link_lengths=non_constructible_lengths)
    if linkage_4bar_fail is None:
        print("\nSuccessfully identified non-constructible 4-bar linkage as None.")
    else:
        print("\nError: Non-constructible 4-bar linkage did not return None.")
        print(linkage_4bar_fail)

    # Test another non-constructible 4-bar (links too short to span d)
    # Here p0=(0,0), p3_fixed=(100,0). If l1=30, theta1=0, p1=(30,0). d = p1 to p3_fixed = 70.
    # If l2=20, l3=20, then l2+l3=40 < 70. Not constructible.
    non_constructible_lengths_2 = {"l1": 30, "l2": 20, "l3": 20, "l4": 100}
    linkage_4bar_fail_2 = generate_4bar_linkage(link_lengths=non_constructible_lengths_2, input_angle_deg=0)
    if linkage_4bar_fail_2 is None:
        print("\nSuccessfully identified non-constructible 4-bar linkage (case 2) as None.")
    else:
        print("\nError: Non-constructible 4-bar linkage (case 2) did not return None.")
        print(linkage_4bar_fail_2)