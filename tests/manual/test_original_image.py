#!/usr/bin/env python

import cv2
import numpy as np
import pytest

# Load original image
img = cv2.imread("image_123650291.JPG", cv2.IMREAD_UNCHANGED)
if img is None:
    pytest.skip("image_123650291.JPG not found; skipping manual image test.", allow_module_level=True)

print(f"Original image shape: {img.shape}")

if len(img.shape) == 3:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std_dev = np.std(gray)
    unique_colors = len(np.unique(gray))

    print(f"Standard deviation: {std_dev}")
    print(f"Unique colors: {unique_colors}")

    is_line_art = unique_colors < 50 or std_dev < 30
    print(f"Is line art: {is_line_art}")

    # Check the dominant color
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    most_common = np.argmax(hist)
    print(f"Most common gray value: {most_common}")

    # Check percentage of white/near-white pixels
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    white_percentage = (white_pixels / total_pixels) * 100
    print(f"White pixels: {white_percentage:.1f}%")
