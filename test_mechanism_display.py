#!/usr/bin/env python3
"""Test script to verify mechanism dataset loading and display."""

import json
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainterPath
from automataii.gui.dialogs.recommendation_dialog import MechanismRecommendationDialog

def test_mechanism_display():
    """Test if mechanisms are loaded and displayed correctly."""
    
    # Create a dummy user path
    user_path = QPainterPath()
    user_path.moveTo(0, 0)
    user_path.lineTo(50, 30)
    user_path.lineTo(100, 20)
    user_path.lineTo(150, 40)
    user_path.lineTo(200, 10)
    
    # Path to dataset
    dataset_path = "src/automataii/kinematics/generated_mechanism_paths.json"
    
    # Load and check dataset
    print("Loading dataset from:", dataset_path)
    try:
        with open(dataset_path, 'r') as f:
            data = json.load(f)
        print(f"✓ Loaded {len(data)} mechanisms from dataset")
        
        # Check first mechanism structure
        if data:
            first = data[0]
            print(f"\nFirst mechanism:")
            print(f"  Type: {first.get('type')}")
            print(f"  Name: {first.get('name')}")
            
            full_sim = first.get('full_simulation_data', {})
            print(f"  Full simulation data keys: {list(full_sim.keys())}")
            
            if 'joint_positions' in full_sim:
                joint_pos = full_sim['joint_positions']
                print(f"  Joint positions keys: {list(joint_pos.keys())}")
                if 'p1_positions' in joint_pos:
                    print(f"  Number of frames: {len(joint_pos['p1_positions'])}")
            else:
                print("  ⚠ No joint_positions found in full_simulation_data")
                
    except Exception as e:
        print(f"✗ Error loading dataset: {e}")
        return 1
    
    # Create application and test dialog
    app = QApplication(sys.argv)
    
    print("\nOpening mechanism recommendation dialog...")
    dialog = MechanismRecommendationDialog(user_path, dataset_path)
    
    print(f"✓ Dialog created with {len(dialog.generated_paths_data)} mechanisms loaded")
    
    # Check if mechanisms have proper structure
    for i, mech in enumerate(dialog.generated_paths_data[:3]):  # Check first 3
        print(f"\nMechanism {i+1}:")
        print(f"  Type: {mech.get('type')}")
        print(f"  Has path_coordinates_np: {'path_coordinates_np' in mech}")
        full_sim = mech.get('full_simulation_data', {})
        print(f"  Has full_simulation_data: {bool(full_sim)}")
        if full_sim:
            print(f"  Full sim keys: {list(full_sim.keys())}")
    
    # Show dialog
    result = dialog.exec()
    
    if result:
        selected = dialog.selected_mechanism_data
        if selected:
            print(f"\n✓ Selected mechanism: {selected.get('name')} ({selected.get('type')})")
            print(f"  Has transform_params: {'transform_params' in selected}")
            print(f"  Has full_simulation_data: {'full_simulation_data' in selected}")
        else:
            print("\n⚠ No mechanism selected")
    else:
        print("\n✗ Dialog cancelled")
    
    return 0

if __name__ == "__main__":
    sys.exit(test_mechanism_display())