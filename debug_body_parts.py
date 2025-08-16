#!/usr/bin/env python

import sys
from pathlib import Path
import cv2
import numpy as np
import yaml

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def debug_body_segmentation():
    """Debug body parts segmentation"""
    
    temp_dir = Path("/private/var/folders/qf/8vynx0hj5q55zj3rcrqw1myw0000gn/T/automataii/image_123650291")
    parts_dir = temp_dir / "body_parts"
    
    # Load character config
    with open(temp_dir / "char_cfg.yaml") as f:
        char_cfg = yaml.safe_load(f)
    
    print("Skeleton joints:")
    for joint in char_cfg['skeleton']:
        print(f"  {joint['name']}: {joint['loc']}")
    
    # Check what body parts were extracted
    print("\nBody parts found:")
    for part_file in parts_dir.glob("*.png"):
        if "segmentation" not in part_file.name and "composite" not in part_file.name:
            img = cv2.imread(str(part_file), cv2.IMREAD_UNCHANGED)
            if img is not None:
                print(f"  {part_file.stem}: shape={img.shape}")
                
                # Check if the image has actual content
                if img.shape[2] == 4:
                    alpha = img[:, :, 3]
                    non_zero = np.count_nonzero(alpha)
                    total = alpha.size
                    percent = (non_zero / total) * 100
                    print(f"    Alpha coverage: {percent:.1f}%")
                    
                    # Check RGB content where alpha > 0
                    mask_3d = np.stack([alpha > 0] * 3, axis=2)
                    rgb_masked = img[:, :, :3][mask_3d].reshape(-1, 3)
                    if len(rgb_masked) > 0:
                        mean_color = np.mean(rgb_masked, axis=0)
                        print(f"    Mean color (BGR): {mean_color}")

if __name__ == "__main__":
    debug_body_segmentation()