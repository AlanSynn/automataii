#!/usr/bin/env python

import cv2
import numpy as np
from pathlib import Path

parts_dir = Path("/private/var/folders/qf/8vynx0hj5q55zj3rcrqw1myw0000gn/T/automataii/image_123650291/body_parts")

print("Body Parts Analysis:")
print("-" * 50)

for part_file in sorted(parts_dir.glob("*.png")):
    if "segmentation" in part_file.name or "composite" in part_file.name:
        continue
        
    img = cv2.imread(str(part_file), cv2.IMREAD_UNCHANGED)
    if img is not None and img.shape[2] == 4:
        h, w = img.shape[:2]
        alpha = img[:, :, 3]
        
        # Check alpha coverage
        non_zero = np.count_nonzero(alpha)
        total = alpha.size
        coverage = (non_zero / total) * 100
        
        # Check if content is visible
        rgb = img[:, :, :3]
        # Get mean color where alpha > 0
        if non_zero > 0:
            mask = alpha > 0
            mean_color = np.mean(rgb[mask])
        else:
            mean_color = 0
            
        print(f"{part_file.stem:20} | Size: {w:3}x{h:3} | Coverage: {coverage:5.1f}% | Mean RGB: {mean_color:.1f}")