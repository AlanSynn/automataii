#!/usr/bin/env python3
"""
Debug script to understand why only some parts are being generated.
"""

import os
import sys
import tempfile
import yaml
import json
import cv2
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor
from automataii.domain.animation.part_definitions import BODY_PARTS

def debug_parts_generation():
    """Debug the parts generation process."""
    print("🐛 Debugging Parts Generation")
    print("=" * 50)
    
    # Create test skeleton with comprehensive joint names
    skeleton_data = {
        "joints": {
            "pelvis": {"name": "pelvis", "position": [100, 200], "parent": None},
            "torso": {"name": "torso", "position": [100, 160], "parent": "pelvis"},
            "neck": {"name": "neck", "position": [100, 120], "parent": "torso"},
            "head_top": {"name": "head_top", "position": [100, 90], "parent": "neck"},
            "left_shoulder": {"name": "left_shoulder", "position": [80, 130], "parent": "torso"},
            "left_elbow": {"name": "left_elbow", "position": [60, 160], "parent": "left_shoulder"},
            "left_wrist": {"name": "left_wrist", "position": [50, 190], "parent": "left_elbow"},
            "left_hand": {"name": "left_hand", "position": [45, 205], "parent": "left_wrist"},
            "right_shoulder": {"name": "right_shoulder", "position": [120, 130], "parent": "torso"},
            "right_elbow": {"name": "right_elbow", "position": [140, 160], "parent": "right_shoulder"},
            "right_wrist": {"name": "right_wrist", "position": [150, 190], "parent": "right_elbow"},
            "right_hand": {"name": "right_hand", "position": [155, 205], "parent": "right_wrist"},
            "left_hip": {"name": "left_hip", "position": [85, 210], "parent": "pelvis"},
            "left_knee": {"name": "left_knee", "position": [80, 250], "parent": "left_hip"},
            "left_ankle": {"name": "left_ankle", "position": [75, 290], "parent": "left_knee"},
            "left_foot": {"name": "left_foot", "position": [70, 300], "parent": "left_ankle"},
            "right_hip": {"name": "right_hip", "position": [115, 210], "parent": "pelvis"},
            "right_knee": {"name": "right_knee", "position": [120, 250], "parent": "right_hip"},
            "right_ankle": {"name": "right_ankle", "position": [125, 290], "parent": "right_knee"},
            "right_foot": {"name": "right_foot", "position": [130, 300], "parent": "right_ankle"}
        }
    }
    
    print(f"📊 Skeleton has {len(skeleton_data['joints'])} joints:")
    for joint_name in skeleton_data['joints'].keys():
        print(f"   - {joint_name}")
    
    print(f"\n📦 BODY_PARTS expects these parts:")
    for part_name, part_def in BODY_PARTS.items():
        joints = part_def.get('joints', [])
        print(f"   - {part_name}: {joints}")
    
    # Create a temporary character directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        char_dir = os.path.join(temp_dir, "test_char")
        os.makedirs(char_dir, exist_ok=True)
        
        # Create a simple test image
        test_image = np.zeros((300, 200, 3), dtype=np.uint8)
        test_image[:, :] = [100, 150, 200]  # Fill with blue-ish color
        
        # Save as texture
        texture_path = os.path.join(char_dir, "texture.png")
        cv2.imwrite(texture_path, test_image)
        
        # Create mask (full image)
        mask = np.ones((300, 200), dtype=np.uint8) * 255
        mask_path = os.path.join(char_dir, "mask.png")
        cv2.imwrite(mask_path, mask)
        
        # Create char_cfg.yaml
        char_cfg = {
            "name": "test_character",
            "width": 200,
            "height": 300,
            "joints": skeleton_data["joints"],
            "skeleton": skeleton_data
        }
        
        char_cfg_path = os.path.join(char_dir, "char_cfg.yaml")
        with open(char_cfg_path, 'w') as f:
            yaml.dump(char_cfg, f, default_flow_style=False)
        
        # Create output directory
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n🔧 Testing with BodyPartsExtractor...")
        
        # Test the extractor
        extractor = BodyPartsExtractor(
            char_dir=char_dir,
            output_dir=output_dir,
            generate_animations=False
        )
        
        # Debug the joint map creation
        print(f"\n🗺️ Testing joint map creation...")
        joint_map = extractor._create_joint_map(skeleton_data)
        print(f"Created joint_map with {len(joint_map)} joints:")
        for joint_name, pos in joint_map.items():
            print(f"   - {joint_name}: {pos}")
        
        # Test each part individually
        print(f"\n🧩 Testing individual parts...")
        for part_name, part_def in BODY_PARTS.items():
            joints = part_def.get('joints', [])
            print(f"\n{part_name}:")
            print(f"   Expected joints: {joints}")
            
            mapped_joints = []
            for joint in joints:
                if joint in joint_map:
                    mapped_joints.append(joint)
                    print(f"   ✅ Found: {joint}")
                else:
                    # Try prefix matching
                    found = False
                    for jname in joint_map:
                        if jname.startswith(joint):
                            mapped_joints.append(jname)
                            print(f"   ✅ Found by prefix: {jname} (for {joint})")
                            found = True
                            break
                    if not found:
                        print(f"   ❌ Missing: {joint}")
            
            if mapped_joints:
                print(f"   ✅ Part {part_name} will be generated with joints: {mapped_joints}")
            else:
                print(f"   ❌ Part {part_name} will NOT be generated (no matching joints)")
        
        # Run the extraction
        print(f"\n🎨 Running full extraction...")
        try:
            extractor.process()
            
            # Check results
            parts_info_path = os.path.join(output_dir, "parts_info.json")
            if os.path.exists(parts_info_path):
                with open(parts_info_path, 'r') as f:
                    parts_info = json.load(f)
                    parts = parts_info.get("character", {}).get("parts", {})
                    print(f"\n📊 Generated {len(parts)} parts:")
                    for part_name in parts.keys():
                        print(f"   ✅ {part_name}")
                        
                    missing_parts = set(BODY_PARTS.keys()) - set(parts.keys())
                    if missing_parts:
                        print(f"\n❌ Missing parts: {', '.join(missing_parts)}")
                    else:
                        print(f"\n🎉 All expected parts generated!")
                        
                return True
            else:
                print("❌ No parts_info.json created")
                return False
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    debug_parts_generation()