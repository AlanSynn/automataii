#!/usr/bin/env python3
"""Test and fix bend direction calculation."""

import math
from PyQt6.QtCore import QPointF


def calculate_bend_direction_original(p0, p1, p2):
    """Original bend direction calculation from IK manager."""
    signed_area = (p1.x() - p0.x()) * (p2.y() - p0.y()) - (p1.y() - p0.y()) * (p2.x() - p0.x())
    
    if abs(signed_area) < 1e-6:  # Collinear
        return 0
    elif signed_area > 0:  # CCW
        return 1
    else:  # CW
        return -1


def calculate_bend_direction_anatomical(p0, p1, p2, joint_name):
    """Improved bend direction based on anatomical constraints."""
    # For arms: elbows typically bend towards the body (inward)
    # For legs: knees typically bend forward
    
    signed_area = (p1.x() - p0.x()) * (p2.y() - p0.y()) - (p1.y() - p0.y()) * (p2.x() - p0.x())
    
    # Get base direction from geometry
    if abs(signed_area) < 1e-6:  # Collinear
        base_dir = 0
    elif signed_area > 0:  # CCW
        base_dir = 1
    else:  # CW
        base_dir = -1
    
    # Apply anatomical corrections
    if "elbow" in joint_name.lower():
        # Elbows should bend inward (towards body center)
        # For left elbow: if arm is extended left, elbow bends right (CW = -1)
        # For right elbow: if arm is extended right, elbow bends left (CCW = 1)
        
        # Check arm extension direction
        arm_vec = p2 - p0
        arm_angle = math.atan2(arm_vec.y(), arm_vec.x())
        arm_angle_deg = math.degrees(arm_angle)
        
        # Determine if arm is pointing outward from body
        if "left" in joint_name.lower():
            # Left arm extended outward is roughly -180 to -90 degrees
            if -180 <= arm_angle_deg <= -90:
                # Arm pointing left, elbow should bend right (CW)
                return -1
            else:
                # Use geometric calculation
                return base_dir
        elif "right" in joint_name.lower():
            # Right arm extended outward is roughly -90 to 0 degrees  
            if -90 <= arm_angle_deg <= 0:
                # Arm pointing right, elbow should bend left (CCW)
                return 1
            else:
                # Use geometric calculation
                return base_dir
                
    elif "knee" in joint_name.lower():
        # Knees typically bend forward (away from body back)
        # This usually means bending in the direction that moves p1 forward relative to p0-p2 line
        
        # For typical standing pose, knees bend forward
        # Check if leg is roughly vertical
        leg_vec = p2 - p0
        leg_angle = math.atan2(leg_vec.y(), leg_vec.x())
        leg_angle_deg = math.degrees(leg_angle)
        
        # Legs pointing down are around -90 degrees
        if -120 <= leg_angle_deg <= -60:
            # Leg is roughly vertical, knee should bend forward
            # Forward typically means positive x direction
            if p1.x() < (p0.x() + p2.x()) / 2:
                # Knee is behind the leg line, should bend forward (positive x)
                return 1 if "left" in joint_name.lower() else -1
            else:
                # Knee is already forward
                return base_dir
        else:
            return base_dir
            
    return base_dir


def test_bend_directions():
    """Test bend direction calculations with typical joint configurations."""
    
    test_cases = [
        # Left arm bent at elbow (more pronounced bend)
        {
            "name": "left_elbow",
            "p0": QPointF(0, 0),      # Shoulder
            "p1": QPointF(-40, 30),   # Elbow (bent down significantly)
            "p2": QPointF(-80, 10),   # Wrist
            "expected": -1,  # Should bend inward (CW)
        },
        # Right arm bent at elbow
        {
            "name": "right_elbow", 
            "p0": QPointF(0, 0),      # Shoulder
            "p1": QPointF(40, 30),    # Elbow (bent down significantly)
            "p2": QPointF(80, 10),    # Wrist
            "expected": 1,   # Should bend inward (CCW)
        },
        # Left knee bent forward
        {
            "name": "left_knee",
            "p0": QPointF(-10, 0),    # Hip
            "p1": QPointF(-5, -40),   # Knee (bent forward)
            "p2": QPointF(-15, -80),  # Ankle
            "expected": 1,   # Should bend forward (CCW)
        },
        # Right knee bent forward
        {
            "name": "right_knee",
            "p0": QPointF(10, 0),     # Hip
            "p1": QPointF(5, -40),    # Knee (bent forward) 
            "p2": QPointF(15, -80),   # Ankle
            "expected": -1,  # Should bend forward (CW)
        },
    ]
    
    print("Testing bend directions:\n")
    
    for case in test_cases:
        name = case["name"]
        p0, p1, p2 = case["p0"], case["p1"], case["p2"]
        expected = case["expected"]
        
        # Original calculation
        original_dir = calculate_bend_direction_original(p0, p1, p2)
        
        # Improved calculation
        improved_dir = calculate_bend_direction_anatomical(p0, p1, p2, name)
        
        print(f"{name}:")
        print(f"  Points: p0={p0}, p1={p1}, p2={p2}")
        print(f"  Original direction: {original_dir}")
        print(f"  Improved direction: {improved_dir}")
        print(f"  Expected direction: {expected}")
        print(f"  Status: {'✓ PASS' if improved_dir == expected else '✗ FAIL'}")
        print()


if __name__ == "__main__":
    test_bend_directions()