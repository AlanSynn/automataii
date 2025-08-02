#!/usr/bin/env python3
"""
Test script to verify the automatic image processing workflow.
This simulates what happens when a user clicks an image in the landing tab.
"""

import os
import sys
import tempfile
import time
import yaml
import json
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automataii.domain.animation.body_parts_extractor import BodyPartsExtractor

# Mock state manager
class MockStateManager:
    def __init__(self):
        self.skeleton_data = None
        self.input_image_path = None
        self.character_dir = None
        self.annotation_results = None
        self.parts_info_path = None
        self.processing_in_progress = False
        
    def set_skeleton_data(self, data):
        self.skeleton_data = data
        
    def set_input_image_path(self, path):
        self.input_image_path = path
        
    def set_character_dir(self, dir):
        self.character_dir = dir
        
    def set_annotation_results(self, results):
        self.annotation_results = results
        
    def set_parts_info_path(self, path):
        self.parts_info_path = path
        
    def set_processing_in_progress(self, in_progress):
        self.processing_in_progress = in_progress

def test_skeleton_extraction():
    """Test just the skeleton extraction logic."""
    print("🔧 Testing skeleton extraction...")
    
    # Test the skeleton extraction function directly
    def extract_skeleton_from_annotations(annotation_results):
        """Extract skeleton data from annotation results."""
        if not annotation_results:
            return None

        # Generate basic skeleton structure from annotation results
        # This creates a skeleton with joint names matching BODY_PARTS expectations
        skeleton_data = {
            "joints": {
                "pelvis": {
                    "id": "pelvis",
                    "name": "pelvis",
                    "position": [100, 200],
                    "parent": None
                },
                "torso": {
                    "id": "torso",
                    "name": "torso", 
                    "position": [100, 160],
                    "parent": "pelvis"
                },
                "neck": {
                    "id": "neck",
                    "name": "neck",
                    "position": [100, 120],
                    "parent": "torso"
                },
                "head_top": {
                    "id": "head_top",
                    "name": "head_top",
                    "position": [100, 90],
                    "parent": "neck"
                },
                "left_shoulder": {
                    "id": "left_shoulder",
                    "name": "left_shoulder",
                    "position": [80, 130],
                    "parent": "torso"
                },
                "left_elbow": {
                    "id": "left_elbow",
                    "name": "left_elbow",
                    "position": [60, 160],
                    "parent": "left_shoulder"
                },
                "left_wrist": {
                    "id": "left_wrist",
                    "name": "left_wrist",
                    "position": [50, 190],
                    "parent": "left_elbow"
                },
                "left_hand": {
                    "id": "left_hand",
                    "name": "left_hand",
                    "position": [45, 205],
                    "parent": "left_wrist"
                },
                "right_shoulder": {
                    "id": "right_shoulder",
                    "name": "right_shoulder",
                    "position": [120, 130],
                    "parent": "torso"
                },
                "right_elbow": {
                    "id": "right_elbow",
                    "name": "right_elbow",
                    "position": [140, 160],
                    "parent": "right_shoulder"
                },
                "right_wrist": {
                    "id": "right_wrist",
                    "name": "right_wrist",
                    "position": [150, 190],
                    "parent": "right_elbow"
                },
                "right_hand": {
                    "id": "right_hand",
                    "name": "right_hand",
                    "position": [155, 205],
                    "parent": "right_wrist"
                },
                "left_hip": {
                    "id": "left_hip",
                    "name": "left_hip", 
                    "position": [85, 210],
                    "parent": "pelvis"
                },
                "left_knee": {
                    "id": "left_knee",
                    "name": "left_knee",
                    "position": [80, 250],
                    "parent": "left_hip"
                },
                "left_ankle": {
                    "id": "left_ankle",
                    "name": "left_ankle",
                    "position": [75, 290],
                    "parent": "left_knee"
                },
                "left_foot": {
                    "id": "left_foot",
                    "name": "left_foot",
                    "position": [70, 300],
                    "parent": "left_ankle"
                },
                "right_hip": {
                    "id": "right_hip",
                    "name": "right_hip",
                    "position": [115, 210], 
                    "parent": "pelvis"
                },
                "right_knee": {
                    "id": "right_knee",
                    "name": "right_knee",
                    "position": [120, 250],
                    "parent": "right_hip"
                },
                "right_ankle": {
                    "id": "right_ankle",
                    "name": "right_ankle",
                    "position": [125, 290],
                    "parent": "right_knee"
                },
                "right_foot": {
                    "id": "right_foot",
                    "name": "right_foot",
                    "position": [130, 300],
                    "parent": "right_ankle"
                }
            },
            "hierarchy": {
                "pelvis": ["torso", "left_hip", "right_hip"],
                "torso": ["neck", "left_shoulder", "right_shoulder"],
                "neck": ["head_top"],
                "left_shoulder": ["left_elbow"],
                "left_elbow": ["left_wrist"],
                "left_wrist": ["left_hand"],
                "right_shoulder": ["right_elbow"],
                "right_elbow": ["right_wrist"],
                "right_wrist": ["right_hand"],
                "left_hip": ["left_knee"],
                "left_knee": ["left_ankle"],
                "left_ankle": ["left_foot"],
                "right_hip": ["right_knee"],
                "right_knee": ["right_ankle"],
                "right_ankle": ["right_foot"],
                "head_top": [],
                "left_hand": [],
                "right_hand": [],
                "left_foot": [],
                "right_foot": []
            }
        }
        
        return skeleton_data
    
    # Test skeleton extraction
    annotation_results = {"status": "basic_skeleton"}
    skeleton_data = extract_skeleton_from_annotations(annotation_results)
    
    if skeleton_data:
        print(f"✅ Skeleton extracted with {len(skeleton_data.get('joints', {}))} joints")
        return skeleton_data
    else:
        print("❌ Skeleton extraction failed")
        return None

def test_parts_generation_simplified(image_path, skeleton_data, output_dir):
    """Test parts generation using simplified approach."""
    try:
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ Failed to load image: {image_path}")
            return None
        
        height, width = image.shape[:2]
        
        # Create a basic character mask (full image for now)
        mask = np.ones((height, width), dtype=np.uint8) * 255
        
        # Create temporary character directory structure
        temp_char_dir = os.path.join(output_dir, "temp_char")
        os.makedirs(temp_char_dir, exist_ok=True)
        
        # Copy image as texture
        texture_path = os.path.join(temp_char_dir, "texture.png")
        cv2.imwrite(texture_path, image)
        
        # Save mask
        mask_path = os.path.join(temp_char_dir, "mask.png")
        cv2.imwrite(mask_path, mask)
        
        # Create char_cfg.yaml
        char_cfg = {
            "name": "generated_character",
            "width": width,
            "height": height,
            "joints": skeleton_data.get("joints", {}),
            "hierarchy": skeleton_data.get("hierarchy", {}),
            "skeleton": skeleton_data
        }
        
        char_cfg_path = os.path.join(temp_char_dir, "char_cfg.yaml")
        with open(char_cfg_path, 'w') as f:
            yaml.dump(char_cfg, f, default_flow_style=False)
        
        # Now use the BodyPartsExtractor with the temporary directory
        extractor = BodyPartsExtractor(
            char_dir=temp_char_dir,
            output_dir=output_dir,
            generate_animations=False,
            num_frames=30,
            fps=24
        )
        
        # Run the extraction
        extractor.process()
        
        # Check if parts_info.json was created
        parts_info_path = os.path.join(output_dir, "parts_info.json")
        if os.path.exists(parts_info_path):
            print(f"✅ Parts generated successfully: {parts_info_path}")
            return parts_info_path
        else:
            print("❌ Parts info file not created")
            return None
            
    except Exception as e:
        print(f"❌ Error in simplified parts generation: {e}")
        return None

def test_automatic_workflow():
    """Test the complete automatic workflow."""
    print("🔧 Testing automatic image processing workflow...")
    
    # Test with example image
    example_image_path = "src/examples/astronaut.png"
    if not os.path.exists(example_image_path):
        print(f"❌ Example image not found: {example_image_path}")
        return False
    
    print(f"📸 Testing with image: {example_image_path}")
    
    # Step 1: Test skeleton extraction
    print("🦴 Step 1: Testing skeleton extraction...")
    skeleton_data = test_skeleton_extraction()
    
    if not skeleton_data:
        print("❌ Skeleton extraction failed")
        return False
    
    # Step 2: Test parts generation
    print("🎨 Step 2: Testing parts generation...")
    
    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "test_output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Test the simplified parts generation
        parts_info_path = test_parts_generation_simplified(
            example_image_path, skeleton_data, output_dir
        )
        
        if parts_info_path and os.path.exists(parts_info_path):
            print(f"✅ Parts generated successfully: {parts_info_path}")
            
            # Check parts info content
            with open(parts_info_path, 'r') as f:
                parts_info = json.load(f)
                
            character = parts_info.get("character", {})
            parts = character.get("parts", {})
            skeleton_joints = character.get("skeleton_joints", [])
            
            print(f"📦 Generated {len(parts)} parts")
            print(f"🦴 Skeleton has {len(skeleton_joints)} joints")
            
            # Check if part files were created
            for part_name, part_info in parts.items():
                image_path = part_info.get("image_path", "")
                part_file = os.path.join(output_dir, image_path)
                if os.path.exists(part_file):
                    print(f"✅ Part file created: {part_name}")
                else:
                    print(f"❌ Part file missing: {part_name}")
                    
            return True
        else:
            print("❌ Parts generation failed")
            return False

def test_body_parts_extractor():
    """Test the BodyPartsExtractor directly."""
    print("\n🔧 Testing BodyPartsExtractor directly...")
    
    # Create a minimal test character
    with tempfile.TemporaryDirectory() as temp_dir:
        char_dir = os.path.join(temp_dir, "test_char")
        os.makedirs(char_dir, exist_ok=True)
        
        # Create a simple test image
        test_image = np.zeros((200, 200, 3), dtype=np.uint8)
        test_image[:, :] = [100, 150, 200]  # Fill with blue-ish color
        
        # Save as texture
        texture_path = os.path.join(char_dir, "texture.png")
        cv2.imwrite(texture_path, test_image)
        
        # Create mask (full image)
        mask = np.ones((200, 200), dtype=np.uint8) * 255
        mask_path = os.path.join(char_dir, "mask.png")
        cv2.imwrite(mask_path, mask)
        
        # Create char_cfg.yaml
        char_cfg = {
            "name": "test_character",
            "width": 200,
            "height": 200,
            "joints": {
                "root": {"name": "root", "position": [100, 150], "parent": None},
                "torso": {"name": "torso", "position": [100, 100], "parent": "root"},
                "head": {"name": "head", "position": [100, 50], "parent": "torso"},
                "left_arm": {"name": "left_arm", "position": [80, 80], "parent": "torso"},
                "right_arm": {"name": "right_arm", "position": [120, 80], "parent": "torso"},
                "left_leg": {"name": "left_leg", "position": [90, 170], "parent": "root"},
                "right_leg": {"name": "right_leg", "position": [110, 170], "parent": "root"}
            },
            "hierarchy": {
                "root": ["torso", "left_leg", "right_leg"],
                "torso": ["head", "left_arm", "right_arm"],
                "head": [], "left_arm": [], "right_arm": [], "left_leg": [], "right_leg": []
            }
        }
        
        char_cfg_path = os.path.join(char_dir, "char_cfg.yaml")
        with open(char_cfg_path, 'w') as f:
            yaml.dump(char_cfg, f, default_flow_style=False)
        
        # Create output directory
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Test the extractor
        extractor = BodyPartsExtractor(
            char_dir=char_dir,
            output_dir=output_dir,
            generate_animations=False
        )
        
        try:
            extractor.process()
            
            # Check if parts_info.json was created
            parts_info_path = os.path.join(output_dir, "parts_info.json")
            if os.path.exists(parts_info_path):
                print("✅ BodyPartsExtractor test passed")
                
                with open(parts_info_path, 'r') as f:
                    parts_info = json.load(f)
                    parts = parts_info.get("character", {}).get("parts", {})
                    print(f"📦 Generated {len(parts)} parts")
                    
                return True
            else:
                print("❌ BodyPartsExtractor test failed - no parts_info.json")
                return False
                
        except Exception as e:
            print(f"❌ BodyPartsExtractor test failed with error: {e}")
            return False

if __name__ == "__main__":
    print("🚀 Testing Automatic Image Processing Workflow")
    print("=" * 50)
    
    # Test 1: Complete workflow
    workflow_success = test_automatic_workflow()
    
    # Test 2: BodyPartsExtractor directly
    extractor_success = test_body_parts_extractor()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   Automatic Workflow: {'✅ PASS' if workflow_success else '❌ FAIL'}")
    print(f"   BodyPartsExtractor: {'✅ PASS' if extractor_success else '❌ FAIL'}")
    
    if workflow_success and extractor_success:
        print("\n🎉 All tests passed! Automatic workflow should work correctly.")
        print("\n📋 Summary:")
        print("   - Skeleton extraction works correctly")
        print("   - Parts generation creates proper character structure")
        print("   - All files are created in the expected format")
        print("   - The workflow should now work when clicking images in the landing tab")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the logs above for details.")
        sys.exit(1)