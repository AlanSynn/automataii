"""
PNG Blueprint Processor.

Processes character part PNG files for blueprint generation.
Integrates with existing body parts extractor workflow.
"""

import logging
import math
import os
from html import escape as escape_xml
from pathlib import Path
from typing import Any

from automataii.domain.generation.contour import (
    AdvancedContourExtractor,
    ManufacturingContour,
)

__all__ = [
    "PNGBlueprintProcessor",
]


class PNGBlueprintProcessor:
    """
    Processes character part PNG files for blueprint generation.
    Integrates with existing body parts extractor workflow.
    """

    def __init__(self, tolerance: float = 1.5):
        self.extractor = AdvancedContourExtractor(tolerance=tolerance)

    @staticmethod
    def _nonnegative_finite_float(value: object, default: float = 0.0) -> float:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return number if math.isfinite(number) and number >= 0.0 else default

    @staticmethod
    def _safe_svg_text(value: object) -> str:
        return escape_xml(str(value or ""), quote=True)

    def process_part_png(self, part_item: Any) -> ManufacturingContour | None:
        """
        Process a single part item to extract manufacturing contours.

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

            # Discover project_dir if available on the item
            project_dir = None
            try:
                if hasattr(part_item, "project_dir") and part_item.project_dir:
                    project_dir = Path(part_item.project_dir)
            except Exception:
                project_dir = None

            # Resolve image path robustly (mirror CharacterPartItem logic)
            png_path_str: str | None = None
            if hasattr(part_item.part_info, "image_path"):
                raw_path = part_item.part_info.image_path
            elif isinstance(part_item.part_info, dict):
                raw_path = part_item.part_info.get("image_path")
            else:
                logging.warning(f"Unknown part_info format: {type(part_item.part_info)}")
                raw_path = None

            # 1) Absolute path if valid
            if raw_path and Path(raw_path).is_absolute() and Path(raw_path).exists():
                png_path_str = raw_path
            # 2) Relative to project_dir
            elif raw_path and project_dir and (project_dir / raw_path).exists():
                png_path_str = str(project_dir / raw_path)
            # 3) Fallback: project_dir/name.png
            elif project_dir and hasattr(part_item.part_info, "name"):
                fallback = project_dir / f"{part_item.part_info.name}.png"
                if fallback.exists():
                    png_path_str = str(fallback)

            if not png_path_str or not os.path.exists(png_path_str):
                logging.warning(
                    f"PNG file not found for part "
                    f"'{getattr(part_item.part_info, 'name', 'unknown')}': {png_path_str}"
                )
                return None

            # Extract contours from PNG
            contours = self.extractor.extract_manufacturing_contours(png_path_str)

            if not contours:
                logging.warning(f"No contours extracted from {png_path_str}")
                return None

            # Return the largest contour (main part shape) and attach source image path
            largest_contour = max(contours, key=lambda c: c.area)
            # Attach source image path for downstream texture embedding
            try:
                largest_contour.source_image_path = png_path_str
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)
            return largest_contour

        except Exception as e:
            logging.error(f"Error processing part PNG: {e}")
            return None

    def generate_parts_blueprint_svg(self, part_items: list[Any], padding: float = 20.0) -> str:
        """
        Generate complete parts blueprint using PNG contour extraction.

        Args:
            part_items: List of character part items
            padding: Spacing between parts

        Returns:
            Complete SVG blueprint with real contours
        """
        if not part_items:
            logging.warning("No part items provided for blueprint generation")
            return ""
        padding = self._nonnegative_finite_float(padding, 20.0)

        svg_parts = []
        current_x = padding
        current_y = padding
        max_row_height = 0.0
        total_width = 0.0
        total_height = 0.0

        for item in part_items:
            # Extract manufacturing contour from PNG
            manufacturing_contour = self.process_part_png(item)

            if not manufacturing_contour:
                logging.warning("Skipping item: No manufacturing contour extracted")
                continue

            # Get part name
            part_name = "Unknown Part"
            if hasattr(item, "part_info") and item.part_info:
                if isinstance(item.part_info, dict):
                    part_name = item.part_info.get("name", "Unknown Part")
                else:
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
                    max_row_height = 0.0

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
        """Create detailed manufacturing SVG for a single part."""
        x_offset = self._nonnegative_finite_float(x_offset)
        y_offset = self._nonnegative_finite_float(y_offset)

        # Get contour dimensions
        cx, cy, raw_width, raw_height = manufacturing_contour.bounding_rect
        width = self._nonnegative_finite_float(raw_width)
        height = self._nonnegative_finite_float(raw_height)
        area = self._nonnegative_finite_float(manufacturing_contour.area)
        perimeter = self._nonnegative_finite_float(manufacturing_contour.perimeter)
        part_name_text = self._safe_svg_text(part_name)

        # Apply offset to SVG path
        offset_path = self.extractor._apply_offset_to_path(
            manufacturing_contour.svg_path, x_offset - cx, y_offset - cy
        )
        offset_path = escape_xml(offset_path, quote=True)

        # Create detailed manufacturing part SVG
        part_svg = f'''
    <g class="manufacturing-part" data-name="{part_name_text}">
        <!-- PNG-extracted contour outline -->
        <path d="{offset_path}" class="part-outline"/>

        <!-- Cutting path for manufacturing -->
        <path d="{offset_path}" class="cutting-path"/>

        <!-- Part label -->
        <text x="{x_offset + width / 2:.2f}" y="{y_offset - 5:.2f}"
              class="part-label" text-anchor="middle">{part_name_text}</text>

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
              Area: {area:.0f}mm² | Perimeter: {perimeter:.1f}mm
        </text>
    </g>
'''

        return part_svg
