#!/usr/bin/env python3
"""
Test script for enhanced segmentation with robot image
"""

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from automataii.domain.animation.body_parts_extractor import (
        BodyPartsExtractor,
        TextureAwareSkeletonSegmenter,
        TorsoFirstSkeletonSegmenter,
    )
except ImportError:
    pytest.skip(
        "Segmentation components not available (TorsoFirstSkeletonSegmenter missing); skipping manual test.",
        allow_module_level=True,
    )
from automataii.domain.animation.part_definitions import BODY_PARTS


def create_structure_preserving_mask(
    gray: np.ndarray, alpha_mask: np.ndarray, rgb_data: np.ndarray
) -> np.ndarray:
    """Create an advanced mask that preserves all structural information from the robot image"""
    height, width = gray.shape

    print("Creating structure-preserving mask with multiple techniques...")

    # Method 1: Multi-scale edge detection for different detail levels
    edges_fine = cv2.Canny(gray, 20, 60)  # Fine details (joint lines, small features)
    edges_medium = cv2.Canny(gray, 50, 100)  # Medium details (part boundaries)
    edges_coarse = cv2.Canny(gray, 100, 200)  # Coarse details (major outlines)

    # Method 2: Gradient-based edge detection
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
    sobel_edges = (sobel_magnitude > 30).astype(np.uint8) * 255

    # Method 3: Laplacian for internal structure
    laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
    laplacian_edges = (np.abs(laplacian) > 20).astype(np.uint8) * 255

    # Method 4: Morphological gradient for shape boundaries
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    morph_grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    morph_edges = (morph_grad > 25).astype(np.uint8) * 255

    # Method 5: Color-based segmentation for RGB information
    if len(rgb_data.shape) == 3:
        # Convert to different color spaces for better segmentation
        hsv = cv2.cvtColor(rgb_data, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(rgb_data, cv2.COLOR_BGR2LAB)

        # Extract intensity variations in different color channels
        hsv_edges = cv2.Canny(hsv[:, :, 2], 30, 80)  # Value channel
        lab_edges = cv2.Canny(lab[:, :, 0], 25, 75)  # L channel

        # Combine color-based edges
        color_edges = cv2.bitwise_or(hsv_edges, lab_edges)
    else:
        color_edges = np.zeros_like(edges_fine)

    # Method 6: Texture analysis using Local Binary Patterns concept
    texture_mask = create_texture_aware_mask(gray)

    # Combine all edge information with weighted importance
    print("Combining multi-scale edge information...")
    combined_edges = np.zeros_like(alpha_mask, dtype=np.float32)

    # Weight different edge types by importance
    combined_edges += edges_fine.astype(np.float32) * 0.8  # High weight for fine details
    combined_edges += edges_medium.astype(np.float32) * 1.0  # Highest weight for medium details
    combined_edges += edges_coarse.astype(np.float32) * 0.6  # Medium weight for coarse details
    combined_edges += sobel_edges.astype(np.float32) * 0.7  # Good weight for gradients
    combined_edges += (
        laplacian_edges.astype(np.float32) * 0.5
    )  # Medium weight for internal structure
    combined_edges += morph_edges.astype(np.float32) * 0.6  # Good weight for boundaries
    combined_edges += color_edges.astype(np.float32) * 0.4  # Lower weight for color edges
    combined_edges += texture_mask.astype(np.float32) * 0.3  # Lower weight for texture

    # Normalize combined edges
    if np.max(combined_edges) > 0:
        combined_edges = (combined_edges / np.max(combined_edges) * 255).astype(np.uint8)
    else:
        combined_edges = combined_edges.astype(np.uint8)

    # Create multi-intensity mask instead of binary
    print("Creating multi-intensity structural mask...")
    structural_mask = alpha_mask.astype(np.float32)

    # Add edge information as intensity variations
    edge_intensity = combined_edges.astype(np.float32) / 255.0

    # Where we have alpha, add edge intensity
    mask_regions = (alpha_mask > 0).astype(np.float32)
    structural_mask = structural_mask + (edge_intensity * 100 * mask_regions)  # Add edge details

    # Create distance-based internal structure
    print("Adding distance-based internal structure...")
    if np.sum(alpha_mask > 0) > 0:
        # Distance transform from edges
        dist_transform = cv2.distanceTransform(alpha_mask, cv2.DIST_L2, 5)

        # Normalize distance transform
        if np.max(dist_transform) > 0:
            dist_normalized = dist_transform / np.max(dist_transform)

            # Add distance-based intensity variation
            structural_mask += dist_normalized * 50  # Add internal gradient

    # Apply smoothing to avoid noise while preserving edges
    print("Smoothing while preserving edges...")
    # Use bilateral filter to smooth noise while keeping edges sharp
    if np.max(structural_mask) > 255:
        structural_mask = np.clip(structural_mask, 0, 255)

    structural_mask_uint8 = structural_mask.astype(np.uint8)
    smoothed_mask = cv2.bilateralFilter(structural_mask_uint8, 9, 75, 75)

    # Enhance contrast to make internal structure more visible
    print("Enhancing contrast for better structure visibility...")
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced_mask = clahe.apply(smoothed_mask)

    # Ensure we maintain the original alpha boundary
    final_mask = np.where(alpha_mask > 0, enhanced_mask, 0).astype(np.uint8)

    # Final morphological operations to clean up
    print("Final morphological cleanup...")
    kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, kernel_small)

    # Add back strong edges to ensure they're not lost
    strong_edges = (combined_edges > 150).astype(np.uint8) * 255
    final_mask = cv2.bitwise_or(final_mask, cv2.bitwise_and(strong_edges, alpha_mask))

    print(
        f"Structure-preserving mask created with intensity range: {np.min(final_mask)}-{np.max(final_mask)}"
    )

    # Save intermediate results for debugging
    cv2.imwrite("debug_alpha_mask.png", alpha_mask)
    cv2.imwrite("debug_combined_edges.png", combined_edges)
    cv2.imwrite("debug_structural_mask.png", structural_mask.astype(np.uint8))
    cv2.imwrite("debug_final_mask.png", final_mask)

    return final_mask


def create_texture_aware_mask(gray: np.ndarray) -> np.ndarray:
    """Create texture-based mask using local texture analysis"""
    height, width = gray.shape

    # Simple texture detection using standard deviation in local windows
    kernel_size = 5
    texture_response = np.zeros_like(gray, dtype=np.float32)

    # Pad image for convolution
    padded = cv2.copyMakeBorder(
        gray,
        kernel_size // 2,
        kernel_size // 2,
        kernel_size // 2,
        kernel_size // 2,
        cv2.BORDER_REFLECT,
    )

    for i in range(height):
        for j in range(width):
            window = padded[i : i + kernel_size, j : j + kernel_size].astype(np.float32)
            texture_response[i, j] = np.std(window)

    # Threshold texture response
    texture_mask = (texture_response > 10).astype(np.uint8) * 255

    return texture_mask


def create_test_robot_data():
    """Create test data structure for robot image"""
    # Create temporary directory for test
    test_dir = Path("test_robot_data")
    test_dir.mkdir(exist_ok=True)

    # Load the robot image
    robot_img_path = "Robot.png"
    if not os.path.exists(robot_img_path):
        print("Robot.png not found in current directory")
        return None

    robot_image = cv2.imread(robot_img_path, cv2.IMREAD_UNCHANGED)
    if robot_image is None:
        print(f"Could not load robot image from {robot_img_path}")
        return None

    height, width = robot_image.shape[:2]

    # Create structure-preserving mask that maintains all robot details
    if robot_image.shape[2] == 4:  # RGBA
        alpha_mask = robot_image[:, :, 3]
        rgb_data = robot_image[:, :, :3]
        gray = cv2.cvtColor(rgb_data, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv2.cvtColor(robot_image, cv2.COLOR_BGR2GRAY)
        _, alpha_mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
        rgb_data = robot_image

    # Advanced multi-layer mask creation
    mask = create_structure_preserving_mask(gray, alpha_mask, rgb_data)

    # Create texture (RGB version)
    if robot_image.shape[2] == 4:
        texture = cv2.cvtColor(robot_image, cv2.COLOR_BGRA2BGR)
    else:
        texture = robot_image

    # Define robot skeleton joints based on robot structure
    # These positions are estimated based on typical robot proportions
    joint_map = {
        # Head
        "head_top": (width // 2, int(height * 0.05)),
        "neck": (width // 2, int(height * 0.12)),
        # Torso
        "torso": (width // 2, int(height * 0.25)),
        "pelvis": (width // 2, int(height * 0.45)),
        # Shoulders
        "left_shoulder": (int(width * 0.35), int(height * 0.18)),
        "right_shoulder": (int(width * 0.65), int(height * 0.18)),
        # Arms
        "left_elbow": (int(width * 0.25), int(height * 0.35)),
        "left_wrist": (int(width * 0.20), int(height * 0.50)),
        "left_hand": (int(width * 0.15), int(height * 0.55)),
        "right_elbow": (int(width * 0.75), int(height * 0.35)),
        "right_wrist": (int(width * 0.80), int(height * 0.50)),
        "right_hand": (int(width * 0.85), int(height * 0.55)),
        # Hips
        "left_hip": (int(width * 0.42), int(height * 0.45)),
        "right_hip": (int(width * 0.58), int(height * 0.45)),
        # Legs
        "left_knee": (int(width * 0.40), int(height * 0.65)),
        "left_ankle": (int(width * 0.38), int(height * 0.85)),
        "left_foot": (int(width * 0.35), int(height * 0.95)),
        "right_knee": (int(width * 0.60), int(height * 0.65)),
        "right_ankle": (int(width * 0.62), int(height * 0.85)),
        "right_foot": (int(width * 0.65), int(height * 0.95)),
    }

    # Create character config
    char_config = {
        "name": "test_robot",
        "width": width,
        "height": height,
        "skeleton": {
            "joints": {
                f"{joint_name}_0": {
                    "position": [float(pos[0]), float(pos[1])],
                    "parent": None,  # Simplified - no hierarchy for this test
                }
                for joint_name, pos in joint_map.items()
            }
        },
    }

    # Save test data
    cv2.imwrite(str(test_dir / "texture.png"), texture)
    cv2.imwrite(str(test_dir / "mask.png"), mask)

    with open(test_dir / "char_cfg.yaml", "w") as f:
        yaml.safe_dump(char_config, f)

    print(f"Created test data in {test_dir}")
    print(f"Image dimensions: {width}x{height}")
    print(f"Joint positions: {len(joint_map)} joints defined")

    return str(test_dir)


def test_enhanced_segmentation():
    """Test the enhanced segmentation on robot image"""

    # Create test data
    test_dir = create_test_robot_data()
    if not test_dir:
        return

    # Create output directory
    output_dir = Path("test_enhanced_output")
    output_dir.mkdir(exist_ok=True)

    print("Running enhanced segmentation...")

    # Run body parts extraction with enhanced segmentation
    extractor = BodyPartsExtractor(
        char_dir=test_dir,
        output_dir=str(output_dir),
        generate_animations=False,  # Skip animations for this test
        num_frames=10,
        fps=12,
    )

    try:
        extractor.process()
        print("Enhanced segmentation completed successfully!")

        # Check results
        results_file = output_dir / "parts_info.json"
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)

            print("\nSegmentation Results:")
            parts = results.get("character", {}).get("parts", {})
            print(f"Total parts extracted: {len(parts)}")

            for part_name, part_info in parts.items():
                roi = part_info.get("roi", [0, 0, 0, 0])
                print(
                    f"  {part_name}: ROI {roi[2]:.0f}x{roi[3]:.0f} at ({roi[0]:.0f}, {roi[1]:.0f})"
                )

        # Check for debug visualization
        debug_file = output_dir / "enhanced_segmentation_debug.png"
        if debug_file.exists():
            print(f"\nDebug visualization saved to: {debug_file}")

        # Check for segmentation visualization
        seg_vis_file = output_dir / "segmentation_vis.png"
        if seg_vis_file.exists():
            print(f"Segmentation visualization saved to: {seg_vis_file}")

        print(f"\nAll results saved to: {output_dir}")

    except Exception as e:
        print(f"Error during segmentation: {e}")
        import traceback

        traceback.print_exc()


def test_direct_torso_first_segmenter():
    """Test TorsoFirstSkeletonSegmenter directly"""
    print("Testing TorsoFirstSkeletonSegmenter directly...")

    # Load robot image
    robot_img_path = "Robot.png"
    if not os.path.exists(robot_img_path):
        print("Robot.png not found")
        return

    robot_image = cv2.imread(robot_img_path, cv2.IMREAD_UNCHANGED)
    height, width = robot_image.shape[:2]

    # Create mask
    if robot_image.shape[2] == 4:
        mask = robot_image[:, :, 3]
    else:
        gray = cv2.cvtColor(robot_image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)

    # Simple joint map for testing
    joint_map = {
        "neck": (width // 2, int(height * 0.12)),
        "left_shoulder": (int(width * 0.35), int(height * 0.18)),
        "left_elbow": (int(width * 0.25), int(height * 0.35)),
        "right_shoulder": (int(width * 0.65), int(height * 0.18)),
        "right_elbow": (int(width * 0.75), int(height * 0.35)),
        "left_hip": (int(width * 0.42), int(height * 0.45)),
        "left_knee": (int(width * 0.40), int(height * 0.65)),
        "right_hip": (int(width * 0.58), int(height * 0.45)),
        "right_knee": (int(width * 0.60), int(height * 0.65)),
    }

    # Create torso-first segmenter
    segmenter = TorsoFirstSkeletonSegmenter(
        mask=mask, joint_map=joint_map, part_definitions=BODY_PARTS, scale_factor=0.5
    )

    try:
        # Run segmentation
        results = segmenter.segment_torso_first()
        print(f"Direct segmentation completed. Parts: {list(results.keys())}")

        # Save debug visualization
        debug_path = "direct_segmentation_debug.png"
        segmenter.visualize_debug(debug_path)
        print(f"Debug visualization saved to: {debug_path}")

        # Save individual results
        for part_name, mask_result in results.items():
            if np.sum(mask_result) > 0:  # Only save non-empty masks
                cv2.imwrite(f"direct_{part_name}_mask.png", mask_result)

        print("Direct segmentation test completed successfully!")

    except Exception as e:
        print(f"Error in direct segmentation: {e}")
        import traceback

        traceback.print_exc()


def test_direct_texture_aware_segmenter():
    """Test TextureAwareSkeletonSegmenter directly"""
    print("Testing TextureAwareSkeletonSegmenter directly...")

    # Load robot image
    robot_img_path = "Robot.png"
    if not os.path.exists(robot_img_path):
        print(f"Robot image not found: {robot_img_path}")
        return

    robot_image = cv2.imread(robot_img_path, cv2.IMREAD_UNCHANGED)
    if robot_image is None:
        print(f"Could not load robot image from {robot_img_path}")
        return

    height, width = robot_image.shape[:2]

    # Create structure-preserving mask (same as create_test_robot_data function)
    if robot_image.shape[2] == 4:  # RGBA
        alpha_mask = robot_image[:, :, 3]
        rgb_data = robot_image[:, :, :3]
        gray = cv2.cvtColor(rgb_data, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv2.cvtColor(robot_image, cv2.COLOR_BGR2GRAY)
        _, alpha_mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
        rgb_data = robot_image

    # Advanced multi-layer mask creation
    mask = create_structure_preserving_mask(gray, alpha_mask, rgb_data)

    # Create texture (RGB version)
    if robot_image.shape[2] == 4:
        texture = cv2.cvtColor(robot_image, cv2.COLOR_BGRA2BGR)
    else:
        texture = robot_image

    # Define joint positions (same as in create_test_robot_data)
    joint_map = {
        "head_top": (width // 2, int(height * 0.05)),
        "neck": (width // 2, int(height * 0.12)),
        "torso": (width // 2, int(height * 0.25)),
        "pelvis": (width // 2, int(height * 0.45)),
        "left_shoulder": (int(width * 0.35), int(height * 0.18)),
        "right_shoulder": (int(width * 0.65), int(height * 0.18)),
        "left_elbow": (int(width * 0.20), int(height * 0.30)),
        "right_elbow": (int(width * 0.80), int(height * 0.30)),
        "left_wrist": (int(width * 0.15), int(height * 0.42)),
        "right_wrist": (int(width * 0.85), int(height * 0.42)),
        "left_hip": (int(width * 0.42), int(height * 0.45)),
        "right_hip": (int(width * 0.58), int(height * 0.45)),
        "left_knee": (int(width * 0.40), int(height * 0.65)),
        "right_knee": (int(width * 0.60), int(height * 0.65)),
    }

    # Create texture-aware segmenter
    segmenter = TextureAwareSkeletonSegmenter(
        mask=mask,
        texture=texture,
        joint_map=joint_map,
        part_definitions=BODY_PARTS,
        scale_factor=0.5,
    )

    try:
        # Run segmentation
        results = segmenter.segment_with_texture()
        print(f"Texture-aware segmentation completed. Parts: {list(results.keys())}")

        # Save debug visualization
        debug_path = "texture_aware_segmentation_debug.png"
        segmenter.visualize_debug(debug_path)
        print(f"Debug visualization saved to: {debug_path}")

        # Save individual results
        for part_name, mask_result in results.items():
            if np.sum(mask_result) > 0:  # Only save non-empty masks
                cv2.imwrite(f"texture_aware_{part_name}_mask.png", mask_result)

        print("Texture-aware segmentation test completed successfully!")

    except Exception as e:
        print(f"Error in texture-aware segmentation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("Enhanced Robot Segmentation Test")
    print("=" * 40)

    # Test 1: Direct texture-aware segmenter test
    print("\n1. Testing TextureAwareSkeletonSegmenter directly...")
    test_direct_texture_aware_segmenter()

    print("\n" + "=" * 40)

    # Test 2: Full pipeline test
    print("\n2. Testing full BodyPartsExtractor pipeline...")
    test_enhanced_segmentation()

    print("\n" + "=" * 40)
    print("Test completed! Check the output files for results.")
