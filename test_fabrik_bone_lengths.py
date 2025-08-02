#!/usr/bin/env python3
"""
Test FABRIK implementation to ensure bone lengths remain constant.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtCore import QPointF
from automataii.domain.kinematics.ik_solver_improved import FABRIKSolver, IKChain
from automataii.models.skeleton import StandardizedJointModel

def create_test_chain():
    """Create a simple test chain (like an arm)"""
    joints = [
        StandardizedJointModel(id="shoulder", name="shoulder", position=(100, 100)),
        StandardizedJointModel(id="elbow", name="elbow", position=(150, 150)),
        StandardizedJointModel(id="wrist", name="wrist", position=(200, 200))
    ]
    return IKChain(joints)

def test_bone_length_preservation():
    """Test that bone lengths are preserved during IK solving"""
    print("🔬 Testing FABRIK bone length preservation...\n")
    
    # Create test chain
    chain = create_test_chain()
    solver = FABRIKSolver(iterations=20, tolerance=0.5)
    
    # Get original bone lengths
    original_lengths = chain.bone_lengths.copy()
    print(f"Original bone lengths: {[f'{l:.2f}' for l in original_lengths]}")
    print(f"Total chain length: {sum(original_lengths):.2f}\n")
    
    # Test cases
    test_targets = [
        ("Reachable target", QPointF(220, 180)),
        ("Barely reachable", QPointF(100 + sum(original_lengths) - 1, 100)),
        ("Unreachable (too far)", QPointF(400, 300)),
        ("Unreachable (behind)", QPointF(0, 0)),
    ]
    
    for test_name, target in test_targets:
        print(f"📍 {test_name}: ({target.x():.1f}, {target.y():.1f})")
        
        # Solve IK
        new_positions = solver.solve(chain, target)
        
        # Check bone lengths
        length_preserved = True
        for i in range(len(original_lengths)):
            p1, p2 = new_positions[i], new_positions[i+1]
            actual_length = ((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)**0.5
            expected_length = original_lengths[i]
            diff = abs(actual_length - expected_length)
            
            status = "✅" if diff < 1e-6 else "❌"
            print(f"   Bone {i}: expected={expected_length:.2f}, actual={actual_length:.2f}, diff={diff:.6f} {status}")
            
            if diff >= 1e-6:
                length_preserved = False
        
        # Check if target was reached (for reachable targets)
        end_effector = new_positions[-1]
        distance_to_target = ((end_effector.x() - target.x())**2 + (end_effector.y() - target.y())**2)**0.5
        
        if "Unreachable" in test_name:
            # For unreachable targets, check if chain is stretched towards target
            direction_to_target = QPointF(target.x() - new_positions[0].x(), 
                                        target.y() - new_positions[0].y())
            dir_length = (direction_to_target.x()**2 + direction_to_target.y()**2)**0.5
            if dir_length > 0:
                normalized_dir = QPointF(direction_to_target.x() / dir_length,
                                       direction_to_target.y() / dir_length)
                
                # Check if chain is aligned with target direction
                chain_dir = QPointF(new_positions[-1].x() - new_positions[0].x(),
                                  new_positions[-1].y() - new_positions[0].y())
                chain_length = (chain_dir.x()**2 + chain_dir.y()**2)**0.5
                if chain_length > 0:
                    chain_normalized = QPointF(chain_dir.x() / chain_length,
                                             chain_dir.y() / chain_length)
                    dot_product = (normalized_dir.x() * chain_normalized.x() + 
                                 normalized_dir.y() * chain_normalized.y())
                    print(f"   Chain alignment with target direction: {dot_product:.3f} (1.0 = perfect)")
        else:
            print(f"   Distance to target: {distance_to_target:.2f}")
        
        print(f"   Overall: {'✅ Lengths preserved' if length_preserved else '❌ Length violation detected!'}\n")

if __name__ == "__main__":
    test_bone_length_preservation()