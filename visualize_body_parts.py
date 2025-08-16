#!/usr/bin/env python

import cv2
import numpy as np
from pathlib import Path

def create_composite_view(parts_dir):
    """Create a composite view of all body parts"""
    parts_dir = Path(parts_dir)
    
    # Load all part images
    part_files = sorted(parts_dir.glob("*.png"))
    part_files = [f for f in part_files if "segmentation_vis" not in f.name and "viewer" not in f.name]
    
    if not part_files:
        print("No body part files found")
        return
    
    # Create a grid layout
    cols = 3
    rows = (len(part_files) + cols - 1) // cols
    
    # Fixed size for each cell
    cell_size = 200
    padding = 10
    
    # Create output image with checkerboard background
    output_width = cols * (cell_size + padding) + padding
    output_height = rows * (cell_size + padding) + padding
    output = np.ones((output_height, output_width, 4), dtype=np.uint8) * 255
    
    # Create checkerboard pattern for transparency visualization
    checker_size = 10
    for y in range(0, output_height, checker_size):
        for x in range(0, output_width, checker_size):
            if (x // checker_size + y // checker_size) % 2 == 0:
                output[y:y+checker_size, x:x+checker_size] = [240, 240, 240, 255]
    
    # Place each part
    for idx, part_file in enumerate(part_files):
        row = idx // cols
        col = idx % cols
        
        # Load part image
        part_img = cv2.imread(str(part_file), cv2.IMREAD_UNCHANGED)
        if part_img is None:
            continue
            
        # Ensure 4 channels
        if part_img.shape[2] == 3:
            part_img = cv2.cvtColor(part_img, cv2.COLOR_BGR2BGRA)
        
        # Resize to fit cell while maintaining aspect ratio
        h, w = part_img.shape[:2]
        scale = min(cell_size / w, cell_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        part_img = cv2.resize(part_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Calculate position (center in cell)
        x_start = col * (cell_size + padding) + padding + (cell_size - new_w) // 2
        y_start = row * (cell_size + padding) + padding + (cell_size - new_h) // 2
        
        # Composite the part onto output
        for c in range(3):
            output[y_start:y_start+new_h, x_start:x_start+new_w, c] = \
                part_img[:, :, c] * (part_img[:, :, 3] / 255.0) + \
                output[y_start:y_start+new_h, x_start:x_start+new_w, c] * (1 - part_img[:, :, 3] / 255.0)
        output[y_start:y_start+new_h, x_start:x_start+new_w, 3] = 255
        
        # Add label
        label = part_file.stem.replace("_", " ").title()
        cv2.putText(output, label, (x_start, y_start - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0, 255), 1)
    
    # Save composite
    output_path = parts_dir / "body_parts_composite.png"
    cv2.imwrite(str(output_path), output)
    print(f"Composite saved to: {output_path}")
    
    return output_path

# Test with the elephant
parts_dir = "/private/var/folders/qf/8vynx0hj5q55zj3rcrqw1myw0000gn/T/automataii/image_123650291/body_parts"
if Path(parts_dir).exists():
    create_composite_view(parts_dir)
else:
    print(f"Directory not found: {parts_dir}")