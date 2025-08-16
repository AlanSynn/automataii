#!/usr/bin/env python

import sys
from pathlib import Path
import cv2
import numpy as np

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def visualize_masks():
    """Debug the segmentation masks"""
    
    temp_dir = Path("/private/var/folders/qf/8vynx0hj5q55zj3rcrqw1myw0000gn/T/automataii/image_123650291")
    
    # Load the original texture and mask
    texture = cv2.imread(str(temp_dir / "texture.png"), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(temp_dir / "mask.png"), cv2.IMREAD_GRAYSCALE)
    
    print(f"Texture shape: {texture.shape}")
    print(f"Mask shape: {mask.shape}")
    print(f"Mask unique values: {np.unique(mask)}")
    print(f"Mask mean: {np.mean(mask)}")
    
    # Visualize the mask
    cv2.imwrite("debug_mask_original.png", mask)
    
    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Found {len(contours)} contours")
    
    # Create a filled version
    filled_mask = np.zeros_like(mask)
    cv2.drawContours(filled_mask, contours, -1, 255, -1)
    cv2.imwrite("debug_mask_filled.png", filled_mask)
    
    # Check texture content
    if texture.shape[2] == 4:
        alpha = texture[:, :, 3]
        print(f"Alpha channel mean: {np.mean(alpha)}")
        print(f"Alpha unique values: {np.unique(alpha)}")
        cv2.imwrite("debug_alpha.png", alpha)
        
        # Check RGB content
        rgb = texture[:, :, :3]
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        print(f"Gray mean: {np.mean(gray)}")
        print(f"Gray std: {np.std(gray)}")
        
        # Try to extract the actual drawing
        # For line art, the drawing is usually darker than background
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        cv2.imwrite("debug_binary.png", binary)
        
        # Find contours in the binary image
        contours2, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"Found {len(contours2)} contours in binary")
        
        # Create filled version from binary
        filled_from_binary = np.zeros_like(binary)
        cv2.drawContours(filled_from_binary, contours2, -1, 255, -1)
        cv2.imwrite("debug_filled_from_binary.png", filled_from_binary)

if __name__ == "__main__":
    visualize_masks()