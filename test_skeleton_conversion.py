#!/usr/bin/env python3

import logging
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automataii.services.skeleton_manager import SkeletonManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

def test_char_cfg_conversion():
    # Simulate char_cfg.yaml data
    char_cfg_data = {
        "skeleton": [
            {"name": "root", "parent": None, "loc": [379, 431]},
            {"name": "hip", "parent": "root", "loc": [379, 431]},
            {"name": "torso", "parent": "hip", "loc": [371, 260]},
            {"name": "left_shoulder", "parent": "torso", "loc": [501, 266]},
            {"name": "left_elbow", "parent": "left_shoulder", "loc": [582, 241]},
            {"name": "left_hand", "parent": "left_elbow", "loc": [646, 190]},
        ]
    }
    
    # Test SkeletonManager
    manager = SkeletonManager()
    
    print("Testing char_cfg conversion...")
    success = manager.load_skeleton_from_dict(char_cfg_data, source_format="animated_drawings")
    
    if success and manager.standardized_model:
        print(f"✅ Successfully loaded {len(manager.standardized_model.joints)} joints")
        
        # Check if parent relationships are preserved
        left_hand = manager.get_joint_by_name("left_hand")
        if left_hand and left_hand.parent_id:
            print(f"✅ left_hand has parent: {left_hand.parent_id}")
            
            # Check the full chain
            chain = []
            current = left_hand
            while current:
                chain.append(current.name)
                current = manager.get_parent_joint(current.id)
            
            print(f"✅ Full chain: {' -> '.join(chain)}")
        else:
            print("❌ left_hand has no parent")
            
        # Check hierarchy
        print(f"✅ Hierarchy: {manager.standardized_model.hierarchy}")
        print(f"✅ Root joints: {manager.standardized_model.root_joint_ids}")
    else:
        print("❌ Failed to load skeleton")

if __name__ == "__main__":
    test_char_cfg_conversion()