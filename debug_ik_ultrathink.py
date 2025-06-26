#!/usr/bin/env python3
"""
ULTRATHINK Root Cause Analysis for IK Issues

This script analyzes the fundamental problems:
1. Arms moving in wrong directions despite correct bend directions
2. Skeleton joint distances changing during animation

Focus Areas:
- Initial pose analysis (astronaut with raised arms)
- Bend direction calculation vs. actual movement
- Bone length preservation during FABRIK
- Coordinate system transformations
"""

import logging
import math
from PyQt6.QtCore import QPointF, QLineF

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def analyze_astronaut_initial_pose():
    """Analyze the initial astronaut pose to understand the arm configuration."""
    print("=" * 80)
    print("ULTRATHINK ANALYSIS: ASTRONAUT INITIAL POSE")
    print("=" * 80)
    
    # From the logs, the astronaut's initial joint positions are:
    joints = {
        'left_shoulder': QPointF(501.0, 266.0),
        'left_elbow': QPointF(582.0, 241.0),  # ELBOW ABOVE SHOULDER!
        'right_shoulder': QPointF(242.0, 253.0),
        'right_elbow': QPointF(177.0, 304.0), # ELBOW BELOW SHOULDER
    }
    
    print("Initial Joint Positions:")
    for name, pos in joints.items():
        print(f"  {name}: ({pos.x():.1f}, {pos.y():.1f})")
    
    print("\nArm Configuration Analysis:")
    
    # Left arm analysis
    left_shoulder_to_elbow = joints['left_elbow'] - joints['left_shoulder']
    left_arm_angle = math.degrees(math.atan2(left_shoulder_to_elbow.y(), left_shoulder_to_elbow.x()))
    print(f"  Left arm: shoulder->elbow angle = {left_arm_angle:.1f}°")
    if joints['left_elbow'].y() < joints['left_shoulder'].y():
        print("    ✅ LEFT ARM IS RAISED (elbow above shoulder)")
    else:
        print("    ❌ LEFT ARM IS LOWERED (elbow below shoulder)")
    
    # Right arm analysis  
    right_shoulder_to_elbow = joints['right_elbow'] - joints['right_shoulder']
    right_arm_angle = math.degrees(math.atan2(right_shoulder_to_elbow.y(), right_shoulder_to_elbow.x()))
    print(f"  Right arm: shoulder->elbow angle = {right_arm_angle:.1f}°")
    if joints['right_elbow'].y() < joints['right_shoulder'].y():
        print("    ❌ RIGHT ARM IS RAISED (elbow above shoulder)")
    else:
        print("    ✅ RIGHT ARM IS LOWERED (elbow below shoulder)")
    
    print("\nCRITICAL INSIGHT:")
    print("The astronaut has ASYMMETRIC arm poses:")
    print("- Left arm is RAISED (pointing upward)")
    print("- Right arm is LOWERED (pointing downward)")
    print("This could cause IK to behave differently for each arm!")
    
    return joints

def analyze_bend_direction_logic(joints):
    """Analyze the bend direction calculation logic."""
    print("\n" + "=" * 80)
    print("ULTRATHINK ANALYSIS: BEND DIRECTION CALCULATION")
    print("=" * 80)
    
    # Simulate the bend direction calculation from IK manager
    def calculate_joint_bend_direction(p0_pos, p1_pos, p2_pos, joint_name):
        """Replicate the IK manager bend direction calculation."""
        
        # Calculate vectors from P1 (middle joint) to P0 (root) and P2 (end)
        vec_to_root = QPointF(p0_pos.x() - p1_pos.x(), p0_pos.y() - p1_pos.y())
        vec_to_end = QPointF(p2_pos.x() - p1_pos.x(), p2_pos.y() - p1_pos.y())
        
        # Calculate angles of both vectors
        angle_to_root = math.atan2(vec_to_root.y(), vec_to_root.x())
        angle_to_end = math.atan2(vec_to_end.y(), vec_to_end.x())
        
        # Calculate the current angle between the vectors
        angle_diff = angle_to_end - angle_to_root
        
        # Normalize angle difference to [-π, π]
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        print(f"\n{joint_name} Bend Direction Analysis:")
        print(f"  P0 (root): {p0_pos}")
        print(f"  P1 (middle): {p1_pos}")  
        print(f"  P2 (end): {p2_pos}")
        print(f"  Angle difference: {math.degrees(angle_diff):.1f}°")
        
        # Apply the actual logic from IK manager
        if "elbow" in joint_name:
            if "left" in joint_name:
                calculated_direction = 1  # CCW
                print(f"  ✅ HARDCODED: Left elbow bends CCW (downward)")
            else:
                calculated_direction = -1  # CW  
                print(f"  ✅ HARDCODED: Right elbow bends CW (downward)")
        else:
            # For other joints, use angle-based calculation
            if angle_diff > 0:
                calculated_direction = 1
                print(f"  📐 CALCULATED: Bends CCW based on angle")
            else:
                calculated_direction = -1
                print(f"  📐 CALCULATED: Bends CW based on angle")
                
        return calculated_direction
    
    # Calculate for left elbow (need hand position)
    # Approximating hand positions based on arm direction
    left_hand_approx = joints['left_elbow'] + (joints['left_elbow'] - joints['left_shoulder'])
    right_hand_approx = joints['right_elbow'] + (joints['right_elbow'] - joints['right_shoulder'])
    
    left_bend_dir = calculate_joint_bend_direction(
        joints['left_shoulder'], joints['left_elbow'], left_hand_approx, "left_elbow"
    )
    
    right_bend_dir = calculate_joint_bend_direction(
        joints['right_shoulder'], joints['right_elbow'], right_hand_approx, "right_elbow"
    )
    
    print(f"\nFINAL BEND DIRECTIONS:")
    print(f"  Left elbow: {left_bend_dir} ({'CCW' if left_bend_dir > 0 else 'CW'})")
    print(f"  Right elbow: {right_bend_dir} ({'CCW' if right_bend_dir > 0 else 'CW'})")
    
    return {'left_elbow': left_bend_dir, 'right_elbow': right_bend_dir}

def analyze_potential_issues():
    """Identify potential root causes."""
    print("\n" + "=" * 80)
    print("ULTRATHINK ANALYSIS: POTENTIAL ROOT CAUSES")
    print("=" * 80)
    
    issues = [
        {
            "issue": "Asymmetric Initial Pose",
            "description": "Left arm raised, right arm lowered creates different IK behavior",
            "impact": "Different starting angles may cause opposite bend directions",
            "likelihood": "HIGH"
        },
        {
            "issue": "Coordinate System Confusion", 
            "description": "Screen coordinates (Y+ down) vs. mathematical coordinates (Y+ up)",
            "impact": "Bend direction calculations may be inverted",
            "likelihood": "MEDIUM"
        },
        {
            "issue": "Part Name vs Joint Name Mapping",
            "description": "Bend directions use joint names, but solver receives part names",
            "impact": "Bend hints may not be applied to correct joints",
            "likelihood": "MEDIUM"
        },
        {
            "issue": "FABRIK Length Enforcement",
            "description": "FABRIK may violate length constraints during iteration",
            "impact": "Skeleton stretching during animation",
            "likelihood": "HIGH"
        },
        {
            "issue": "Scene Transform Application",
            "description": "Coordinate transformations between IK space and scene space",
            "impact": "Visual positioning doesn't match IK calculations",
            "likelihood": "MEDIUM"
        }
    ]
    
    print("Identified Issues (by likelihood):")
    for i, issue in enumerate(sorted(issues, key=lambda x: x["likelihood"], reverse=True), 1):
        print(f"\n{i}. {issue['issue']} ({issue['likelihood']} likelihood)")
        print(f"   Description: {issue['description']}")
        print(f"   Impact: {issue['impact']}")
    
    return issues

def recommend_solutions():
    """Provide specific solutions for identified issues."""
    print("\n" + "=" * 80)
    print("ULTRATHINK SOLUTIONS: RECOMMENDED FIXES")
    print("=" * 80)
    
    solutions = [
        {
            "issue": "Skeleton Length Preservation",
            "solution": "Add strict bone length enforcement after each FABRIK iteration",
            "implementation": [
                "1. Store original bone lengths before IK",
                "2. After each FABRIK iteration, normalize bone lengths",
                "3. Add post-application verification with detailed logging",
                "4. Set MAX_BONE_LENGTH_DEVIATION to 0.0 for rigid preservation"
            ]
        },
        {
            "issue": "Asymmetric Initial Pose Handling",
            "solution": "Analyze actual initial pose and adapt bend directions accordingly",
            "implementation": [
                "1. Calculate initial elbow angle relative to shoulder-hand line",
                "2. Determine if arm is in 'raised' or 'lowered' configuration",
                "3. Set bend direction to maintain natural pose",
                "4. Override hardcoded directions for specific poses"
            ]
        },
        {
            "issue": "Coordinate System Validation",
            "solution": "Add comprehensive coordinate system debugging",
            "implementation": [
                "1. Log all coordinate transformations",
                "2. Verify screen vs. mathematical coordinate assumptions",
                "3. Add visual debug markers for bend hint directions",
                "4. Test with known simple poses"
            ]
        }
    ]
    
    for i, solution in enumerate(solutions, 1):
        print(f"\n{i}. FIX: {solution['issue']}")
        print(f"   Solution: {solution['solution']}")
        print("   Implementation Steps:")
        for step in solution['implementation']:
            print(f"     {step}")
    
    return solutions

def main():
    """Run the complete ULTRATHINK analysis."""
    print("🧠 ULTRATHINK ROOT CAUSE ANALYSIS STARTING...")
    print("Analyzing IK bend direction and skeleton length issues...")
    
    # Step 1: Analyze initial pose
    joints = analyze_astronaut_initial_pose()
    
    # Step 2: Analyze bend direction logic
    bend_directions = analyze_bend_direction_logic(joints)
    
    # Step 3: Identify potential issues
    issues = analyze_potential_issues()
    
    # Step 4: Recommend solutions
    solutions = recommend_solutions()
    
    print("\n" + "=" * 80)
    print("🎯 ULTRATHINK CONCLUSION")
    print("=" * 80)
    
    print("\nMOST LIKELY ROOT CAUSE:")
    print("1. ASYMMETRIC INITIAL POSE: Astronaut has one arm up, one arm down")
    print("2. RIGID LENGTH CONSTRAINT VIOLATION: FABRIK algorithm stretches bones")
    print("3. The system assumes symmetric arm poses but gets asymmetric input")
    
    print("\nIMMEDIATE ACTION REQUIRED:")
    print("1. Set MAX_BONE_LENGTH_DEVIATION = 0.0 for strict preservation")
    print("2. Add detailed bone length logging during FABRIK iterations")
    print("3. Test with symmetric poses to isolate the bend direction issue")
    print("4. Verify that part-to-joint mapping is working correctly")
    
    print("\n🚀 Ready to implement fixes...")

if __name__ == "__main__":
    main()