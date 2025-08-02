#!/usr/bin/env python3
"""
Advanced PNG Contour Extraction System for Manufacturing Blueprints
Implements computer vision-based contour extraction from PNG files

Author: Legendary CS Research Collective
Inspired by: Kass, Catmull, Carmack, Sutherland
"""

import logging
import os
from typing import Any

import cv2
import numpy as np


class ManufacturingContour:
    """Represents a manufacturing-precision contour with SVG path data"""

    def __init__(self, contour: np.ndarray, simplified_contour: np.ndarray, svg_path: str):
        self.contour = contour
        self.simplified_contour = simplified_contour
        self.svg_path = svg_path
        self.area = cv2.contourArea(contour)
        self.perimeter = cv2.arcLength(contour, True)
        self.bounding_rect = cv2.boundingRect(contour)

    def get_cutting_path(self, kerf_compensation: float = 0.1) -> str:
        """Generate optimized cutting path for CNC/laser with kerf compensation"""
        # TODO: Implement kerf compensation for laser cutting
        return self.svg_path


class AdvancedContourExtractor:
    """Computer vision-based contour extraction from PNG files"""

    def __init__(self, tolerance: float = 2.0, min_area: float = 100.0):
        """
        Initialize the contour extractor

        Args:
            tolerance: Douglas-Peucker simplification tolerance
            min_area: Minimum contour area to consider (filters noise)
        """
        self.tolerance = tolerance
        self.min_area = min_area

    def extract_manufacturing_contours(self, png_path: str) -> list[ManufacturingContour]:
        """
        Extract manufacturing-precision contours from PNG file

        Args:
            png_path: Path to PNG file with alpha channel

        Returns:
            List of ManufacturingContour objects
        """
        if not os.path.exists(png_path):
            logging.error(f"PNG file not found: {png_path}")
            return []

        try:
            # 1. Load PNG with alpha channel
            image = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                logging.error(f"Failed to load image: {png_path}")
                return []

            # Handle different image formats
            if len(image.shape) == 2:
                # Grayscale image
                alpha_mask = image
            elif image.shape[2] == 3:
                # RGB image - create mask from non-background pixels
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                # Use adaptive thresholding for better edge detection
                alpha_mask = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )

                # Alternative: use Otsu's method for automatic threshold
                _, otsu_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                # Combine both methods for robust segmentation
                alpha_mask = cv2.bitwise_or(alpha_mask, otsu_mask)

                # Remove potential background noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_OPEN, kernel)
                alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel)
            elif image.shape[2] == 4:
                # RGBA image - use alpha channel
                alpha_mask = image[:, :, 3]
            else:
                logging.error(f"Unsupported image format: {image.shape}")
                return []

            # 2. Apply edge detection and preprocessing
            processed_mask = self._preprocess_mask(alpha_mask)

            # 3. Find contours using cv2.findContours with RETR_EXTERNAL
            contours, _ = cv2.findContours(
                processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # 4. Process and simplify contours
            manufacturing_contours = []
            for contour in contours:
                # Filter by area
                area = cv2.contourArea(contour)
                if area < self.min_area:
                    continue

                # 5. Simplify contours using Douglas-Peucker algorithm
                epsilon = self.tolerance
                simplified_contour = cv2.approxPolyDP(contour, epsilon, True)

                # 6. Convert to manufacturing-precision SVG paths
                svg_path = self._contour_to_svg_path(simplified_contour)

                manufacturing_contour = ManufacturingContour(contour, simplified_contour, svg_path)
                manufacturing_contours.append(manufacturing_contour)

            logging.info(f"Extracted {len(manufacturing_contours)} contours from {png_path}")
            return manufacturing_contours

        except Exception as e:
            logging.error(f"Error extracting contours from {png_path}: {e}")
            return []

    def _preprocess_mask(self, alpha_mask: np.ndarray) -> np.ndarray:
        """
        Preprocess alpha mask for optimal contour detection
        Applies Canny edge detection and adaptive thresholding
        """
        # Ensure binary mask
        if alpha_mask.dtype != np.uint8:
            alpha_mask = alpha_mask.astype(np.uint8)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(alpha_mask, (5, 5), 0)

        # Apply adaptive thresholding for better edge detection
        _, binary_mask = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY)

        # Apply morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        cleaned = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # For better contour detection, use the cleaned binary mask directly
        # instead of edge detection for filled shapes
        edges = cleaned

        # Optional: Apply Canny edge detection for outline-based detection
        canny_edges = cv2.Canny(cleaned, 50, 150)

        # Combine both approaches
        edges = cv2.bitwise_or(edges, canny_edges)

        # Dilate edges slightly to ensure connected contours
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, dilate_kernel, iterations=1)

        return edges

    def _contour_to_svg_path(self, contour: np.ndarray) -> str:
        """
        Convert OpenCV contour to SVG path data string

        Args:
            contour: OpenCV contour array

        Returns:
            SVG path data string
        """
        if len(contour) == 0:
            return ""

        path_data = ""

        # Start with MoveTo command
        first_point = contour[0][0]
        path_data += f"M {first_point[0]:.2f} {first_point[1]:.2f} "

        # Add LineTo commands for each subsequent point
        for i in range(1, len(contour)):
            point = contour[i][0]
            path_data += f"L {point[0]:.2f} {point[1]:.2f} "

        # Close the path
        path_data += "Z"

        return path_data

    def generate_cutting_paths(self, contours: list[ManufacturingContour]) -> str:
        """
        Generate optimized cutting paths for CNC/laser fabrication

        Args:
            contours: List of manufacturing contours

        Returns:
            Complete SVG with optimized cutting paths
        """
        if not contours:
            return ""

        # Calculate total bounding box
        all_rects = [contour.bounding_rect for contour in contours]
        min_x = min(rect[0] for rect in all_rects)
        min_y = min(rect[1] for rect in all_rects)
        max_x = max(rect[0] + rect[2] for rect in all_rects)
        max_y = max(rect[1] + rect[3] for rect in all_rects)

        width = max_x - min_x + 20  # Add padding
        height = max_y - min_y + 20

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width:.2f}" height="{height:.2f}" xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .cutting-path {{ fill: none; stroke: red; stroke-width: 0.1; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.25; stroke-dasharray: 1,1; }}
      .part-outline {{ fill: none; stroke: black; stroke-width: 0.5; }}
    </style>
  </defs>
  
  <!-- Manufacturing contour paths -->
  <g class="manufacturing-contours">
'''

        # Add each contour as a cutting path
        for i, contour in enumerate(contours):
            # Translate contour to account for bounding box offset
            offset_x = 10 - min_x
            offset_y = 10 - min_y

            # Create path with offset
            path_data = self._apply_offset_to_path(contour.svg_path, offset_x, offset_y)

            svg_content += f'''    <path d="{path_data}" class="cutting-path" id="contour-{i}"/>
    <path d="{path_data}" class="part-outline" id="outline-{i}"/>
'''

        svg_content += """  </g>
</svg>"""

        return svg_content

    def _apply_offset_to_path(self, svg_path: str, offset_x: float, offset_y: float) -> str:
        """Apply offset to SVG path coordinates"""
        if not svg_path:
            return ""

        # Simple offset implementation
        # For production, would need more robust SVG path parsing
        import re

        def offset_coords(match):
            command = match.group(1)
            x = float(match.group(2)) + offset_x
            y = float(match.group(3)) + offset_y
            return f"{command} {x:.2f} {y:.2f}"

        # Match coordinate patterns like "M 123.45 67.89" or "L 123.45 67.89"
        pattern = r"([ML]) ([\d\.-]+) ([\d\.-]+)"
        offset_path = re.sub(pattern, offset_coords, svg_path)

        return offset_path


class PNGBlueprintProcessor:
    """
    Processes character part PNG files for blueprint generation
    Integrates with existing body parts extractor workflow
    """

    def __init__(self, tolerance: float = 1.5):
        self.extractor = AdvancedContourExtractor(tolerance=tolerance)

    def process_part_png(self, part_item) -> ManufacturingContour | None:
        """
        Process a single part item to extract manufacturing contours

        Args:
            part_item: Character part item with part_info containing image_path

        Returns:
            ManufacturingContour object or None if processing fails
        """
        try:
            # Get PNG path from part_info
            if not hasattr(part_item, "part_info") or not part_item.part_info:
                logging.warning("Part item has no part_info")
                return None

            # Handle different part_info formats
            if hasattr(part_item.part_info, "image_path"):
                png_path = part_item.part_info.image_path
            elif isinstance(part_item.part_info, dict):
                png_path = part_item.part_info.get("image_path")
            else:
                logging.warning(f"Unknown part_info format: {type(part_item.part_info)}")
                return None

            if not png_path or not os.path.exists(png_path):
                logging.warning(f"PNG file not found: {png_path}")
                return None

            # Extract contours from PNG
            contours = self.extractor.extract_manufacturing_contours(png_path)

            if not contours:
                logging.warning(f"No contours extracted from {png_path}")
                return None

            # Return the largest contour (main part shape)
            largest_contour = max(contours, key=lambda c: c.area)
            return largest_contour

        except Exception as e:
            logging.error(f"Error processing part PNG: {e}")
            return None

    def generate_parts_blueprint_svg(self, part_items: list[Any], padding: float = 20.0) -> str:
        """
        Generate complete parts blueprint using PNG contour extraction

        Args:
            part_items: List of character part items
            padding: Spacing between parts

        Returns:
            Complete SVG blueprint with real contours
        """
        if not part_items:
            logging.warning("No part items provided for blueprint generation")
            return ""

        svg_parts = []
        current_x = padding
        current_y = padding
        max_row_height = 0
        total_width = 0
        total_height = 0

        for item in part_items:
            # Extract manufacturing contour from PNG
            manufacturing_contour = self.process_part_png(item)

            if not manufacturing_contour:
                logging.warning("Skipping item: No manufacturing contour extracted")
                continue

            # Get part name
            part_name = "Unknown Part"
            if hasattr(item, "part_info") and item.part_info:
                part_name = getattr(item.part_info, "name", "Unknown Part")

            # Get contour bounding box
            x, y, w, h = manufacturing_contour.bounding_rect

            # Create part SVG with manufacturing details
            part_svg = self._create_manufacturing_part_svg(
                manufacturing_contour, current_x, current_y, part_name
            )

            if part_svg:
                svg_parts.append(part_svg)

                # Update layout position
                current_x += w + padding
                max_row_height = max(max_row_height, h)
                total_width = max(total_width, current_x)

                # Wrap to next row if needed
                if current_x > 600:
                    current_x = padding
                    current_y += max_row_height + padding
                    max_row_height = 0

        total_height = current_y + max_row_height + padding
        total_width = max(600, total_width + padding)

        if not svg_parts:
            return '<svg><text x="20" y="20">No parts could be processed</text></svg>'

        # Create complete manufacturing blueprint
        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{total_width:.2f}" height="{total_height:.2f}" xmlns="http://www.w3.org/2000/svg" version="1.1">
  <defs>
    <style>
      .part-outline {{ fill: none; stroke: black; stroke-width: 1.5; }}
      .part-label {{ font-family: Arial, sans-serif; font-size: 10px; font-weight: bold; }}
      .dimension-line {{ stroke: #666; stroke-width: 0.5; stroke-dasharray: 2,2; }}
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 8px; fill: #333; }}
      .cutting-path {{ stroke: red; stroke-width: 0.25; stroke-dasharray: 1,1; fill: none; }}
      .manufacturing-note {{ font-family: Arial, sans-serif; font-size: 7px; fill: #555; }}
    </style>
  </defs>
  
  <!-- Blueprint Title -->
  <rect x="5" y="5" width="{total_width - 10}" height="40" fill="none" stroke="black" stroke-width="2"/>
  <text x="20" y="25" class="part-label" font-size="14">Character Parts Manufacturing Blueprint</text>
  <text x="20" y="35" class="manufacturing-note">Scale: 1:1 | Units: mm | Material: 3mm Plywood/Acrylic | Extracted from PNG Contours</text>
  
  <!-- Parts Content -->
  <g transform="translate(0,50)">
{chr(10).join(svg_parts)}
  </g>
  
  <!-- Border -->
  <rect x="2" y="2" width="{total_width - 4}" height="{total_height - 4}" fill="none" stroke="black" stroke-width="1"/>
</svg>'''

        return svg_content

    def _create_manufacturing_part_svg(
        self,
        manufacturing_contour: ManufacturingContour,
        x_offset: float,
        y_offset: float,
        part_name: str,
    ) -> str:
        """Create detailed manufacturing SVG for a single part"""

        # Get contour dimensions
        cx, cy, width, height = manufacturing_contour.bounding_rect

        # Apply offset to SVG path
        offset_path = self.extractor._apply_offset_to_path(
            manufacturing_contour.svg_path, x_offset - cx, y_offset - cy
        )

        # Create detailed manufacturing part SVG
        part_svg = f'''
    <g class="manufacturing-part" data-name="{part_name}">
        <!-- PNG-extracted contour outline -->
        <path d="{offset_path}" class="part-outline"/>
        
        <!-- Cutting path for manufacturing -->
        <path d="{offset_path}" class="cutting-path"/>
        
        <!-- Part label -->
        <text x="{x_offset + width / 2:.2f}" y="{y_offset - 5:.2f}" 
              class="part-label" text-anchor="middle">{part_name}</text>
        
        <!-- Dimensions -->
        <g class="dimensions">
            <!-- Width dimension -->
            <line x1="{x_offset:.2f}" y1="{y_offset + height + 10:.2f}" 
                  x2="{x_offset + width:.2f}" y2="{y_offset + height + 10:.2f}" 
                  class="dimension-line"/>
            <text x="{x_offset + width / 2:.2f}" y="{y_offset + height + 20:.2f}" 
                  class="dimension-text" text-anchor="middle">{width:.1f}mm</text>
            
            <!-- Height dimension -->
            <line x1="{x_offset - 10:.2f}" y1="{y_offset:.2f}" 
                  x2="{x_offset - 10:.2f}" y2="{y_offset + height:.2f}" 
                  class="dimension-line"/>
            <text x="{x_offset - 15:.2f}" y="{y_offset + height / 2:.2f}" 
                  class="dimension-text" text-anchor="middle" 
                  transform="rotate(-90, {x_offset - 15:.2f}, {y_offset + height / 2:.2f})">
                  {height:.1f}mm</text>
        </g>
        
        <!-- Manufacturing notes -->
        <text x="{x_offset:.2f}" y="{y_offset + height + 35:.2f}" 
              class="manufacturing-note">
              Area: {manufacturing_contour.area:.0f}mm² | Perimeter: {manufacturing_contour.perimeter:.1f}mm
        </text>
    </g>
'''

        return part_svg
