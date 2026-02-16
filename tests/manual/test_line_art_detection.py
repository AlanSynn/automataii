#!/usr/bin/env python

import sys
from pathlib import Path

import cv2
import numpy as np

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_line_art_detection():
    """Test if line art detection is working"""

    temp_dir = Path("/private/var/folders/qf/8vynx0hj5q55zj3rcrqw1myw0000gn/T/automataii/image_123650291")

    # Load texture
    texture_path = temp_dir / "texture.png"
    if not texture_path.exists():
        print(f"Texture not found at {texture_path}")
        return

    texture = cv2.imread(str(texture_path), cv2.IMREAD_UNCHANGED)
    print(f"Texture shape: {texture.shape}")

    # Check if it's line art
    if texture.shape[2] >= 3:
        gray = cv2.cvtColor(texture[:, :, :3], cv2.COLOR_BGR2GRAY)
        std_dev = np.std(gray)
        unique_colors = len(np.unique(gray))

        print(f"Standard deviation: {std_dev}")
        print(f"Unique colors: {unique_colors}")

        is_line_art = unique_colors < 50 or std_dev < 30
        print(f"Is line art: {is_line_art}")

        # Show first 10 unique values
        unique_vals = np.unique(gray)[:10]
        print(f"First 10 unique gray values: {unique_vals}")

if __name__ == "__main__":
    test_line_art_detection()
