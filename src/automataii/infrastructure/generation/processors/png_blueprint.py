"""
PNG Blueprint Processor.

Processes character part PNG files for blueprint generation.
Integrates with existing body parts extractor workflow.
"""

import base64
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
from automataii.utils.paths import resolve_path

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

    @staticmethod
    def _part_name(part_item: Any) -> str:
        part_info = getattr(part_item, "part_info", None)
        if isinstance(part_info, dict):
            return str(part_info.get("name", "unknown"))
        return str(getattr(part_info, "name", "unknown"))

    @staticmethod
    def _pixmap_from_item(part_item: Any) -> Any | None:
        pixmap = getattr(part_item, "part_pixmap", None)
        if pixmap is None:
            pixmap_getter = getattr(part_item, "pixmap", None)
            if callable(pixmap_getter):
                try:
                    pixmap = pixmap_getter()
                except Exception:
                    pixmap = None
        try:
            if pixmap is None or pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
                return None
        except Exception:
            return None
        return pixmap

    @staticmethod
    def _pixmap_to_rgba_array(pixmap: Any) -> Any | None:
        """Return the current editor pixmap as an RGBA NumPy array via duck typing."""
        try:
            image = pixmap.toImage().convertToFormat(pixmap.toImage().Format.Format_RGBA8888)
            width = int(image.width())
            height = int(image.height())
            if width <= 0 or height <= 0:
                return None
            ptr = image.bits()
            ptr.setsize(int(image.sizeInBytes()))
            import numpy as np

            raw = np.frombuffer(ptr, dtype=np.uint8).reshape((height, int(image.bytesPerLine())))
            rgba = raw[:, : width * 4].reshape((height, width, 4)).copy()
            return rgba
        except Exception:
            return None

    @staticmethod
    def _rgba_array_to_data_uri(rgba: Any) -> str | None:
        try:
            import cv2

            bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
            ok, encoded = cv2.imencode(".png", bgra)
            if not ok:
                return None
            return f"data:image/png;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}"
        except Exception:
            return None

    def _process_editor_pixmap(self, part_item: Any) -> ManufacturingContour | None:
        """Extract the contour from the pixmap currently shown in the editor.

        This is the highest-fidelity source for cut sheets because it includes
        ROI scaling and anti-aliased alpha exactly as the user sees it.
        """
        pixmap = self._pixmap_from_item(part_item)
        if pixmap is None:
            return None
        rgba = self._pixmap_to_rgba_array(pixmap)
        if rgba is None:
            return None
        try:
            alpha = rgba[:, :, 3]
        except Exception:
            return None
        contours = self.extractor.extract_manufacturing_contours_from_alpha_mask(alpha)
        if not contours:
            return None
        largest_contour = max(contours, key=lambda c: c.area)
        try:
            largest_contour.coordinate_space = "displayed_roi"
            largest_contour.source_image_size_px = (float(rgba.shape[1]), float(rgba.shape[0]))
            largest_contour.source_image_data_uri = self._rgba_array_to_data_uri(rgba)
            # Keep the original file path as a fallback texture source.
            fallback_path = self._resolve_part_png_path(part_item)
            if fallback_path:
                largest_contour.source_image_path = fallback_path
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
        logging.debug(
            "Extracted editor-visible contour for part '%s' from current pixmap",
            self._part_name(part_item),
        )
        return largest_contour

    def _resolve_part_png_path(self, part_item: Any) -> str | None:
        """Resolve a part texture path, mirroring CharacterPartItem lookup."""
        if not hasattr(part_item, "part_info") or not part_item.part_info:
            return None

        project_dir = None
        try:
            if hasattr(part_item, "project_dir") and part_item.project_dir:
                project_dir = Path(part_item.project_dir)
        except Exception:
            project_dir = None

        if hasattr(part_item.part_info, "image_path"):
            raw_path = part_item.part_info.image_path
        elif isinstance(part_item.part_info, dict):
            raw_path = part_item.part_info.get("image_path")
        else:
            raw_path = None

        png_path_str: str | None = None
        if raw_path and Path(raw_path).is_absolute() and Path(raw_path).exists():
            png_path_str = str(raw_path)
        elif raw_path and project_dir and (project_dir / raw_path).exists():
            png_path_str = str(project_dir / raw_path)
        elif raw_path:
            resolved = resolve_path(str(raw_path))
            if resolved.exists():
                png_path_str = str(resolved)
        if not png_path_str and project_dir and hasattr(part_item.part_info, "name"):
            fallback = project_dir / f"{part_item.part_info.name}.png"
            if fallback.exists():
                png_path_str = str(fallback)
        return png_path_str if png_path_str and os.path.exists(png_path_str) else None

    def process_part_png(self, part_item: Any) -> ManufacturingContour | None:
        """
        Process a single part item to extract manufacturing contours.

        Args:
            part_item: Character part item with part_info containing image_path

        Returns:
            ManufacturingContour object or None if processing fails
        """
        try:
            editor_contour = self._process_editor_pixmap(part_item)
            if editor_contour is not None:
                return editor_contour

            # Get PNG path from part_info
            if not hasattr(part_item, "part_info") or not part_item.part_info:
                logging.warning("Part item has no part_info")
                return None

            png_path_str = self._resolve_part_png_path(part_item)

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
                image = None
                try:
                    import cv2

                    image = cv2.imread(str(png_path_str), cv2.IMREAD_UNCHANGED)
                except Exception:
                    image = None
                if image is not None and len(getattr(image, "shape", ())) >= 2:
                    source_h, source_w = image.shape[:2]
                    largest_contour.source_image_size_px = (float(source_w), float(source_h))
                    largest_contour.coordinate_space = "source_png"
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
  <text x="20" y="35" class="manufacturing-note">Cut/drill character body parts; board placement and fastener stacks are in the assembly guide</text>

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
