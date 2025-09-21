#!/usr/bin/env python3
"""
Mechanism Debug System for Blueprint Visualization
Implements debug visualization for mechanism placement issues

Author: Legendary CS Research Collective  
Inspired by: Carmack's performance engineering and debug systems
"""

import logging
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class BoundingBox:
    """Represents a 2D bounding box"""
    x: float
    y: float
    width: float
    height: float

    def is_valid(self) -> bool:
        """Check if bounding box is valid (positive dimensions)"""
        return self.width > 0 and self.height > 0

    def area(self) -> float:
        """Calculate bounding box area"""
        return self.width * self.height

    def center(self) -> tuple[float, float]:
        """Get center point of bounding box"""
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass
class DebugInfo:
    """Debug information for mechanism rendering"""
    mechanism_id: str
    mechanism_type: str
    data_completeness: dict[str, bool]
    transform_valid: bool
    svg_generated: bool
    svg_length: int
    bounding_box: BoundingBox | None
    errors: list[str]
    warnings: list[str]


class MechanismDebugRenderer:
    """Debug visualization for mechanism placement issues"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.debug_reports: list[DebugInfo] = []

    

    def _debug_single_mechanism(self, mech_id: str, data: dict[str, Any]) -> DebugInfo:
        """Debug a single mechanism"""

        errors = []
        warnings = []

        # Initialize debug info
        debug_info = DebugInfo(
            mechanism_id=mech_id,
            mechanism_type=data.get('mechanism_type', 'unknown'),
            data_completeness={},
            transform_valid=False,
            svg_generated=False,
            svg_length=0,
            bounding_box=None,
            errors=errors,
            warnings=warnings
        )

        # Check data completeness
        required_fields = ['mechanism_type', 'position', 'rotation', 'scale']
        for field in required_fields:
            debug_info.data_completeness[field] = field in data
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Check mechanism type validity
        valid_types = ['gear', 'linkage', 'cam']
        if debug_info.mechanism_type not in valid_types:
            errors.append(f"Invalid mechanism type: {debug_info.mechanism_type}")

        # Check position data
        position = data.get('position')
        if position:
            if not isinstance(position, (list, tuple)) or len(position) < 2:
                errors.append("Position must be a list/tuple with at least 2 coordinates")
            else:
                try:
                    x, y = float(position[0]), float(position[1])
                    if not (-10000 <= x <= 10000) or not (-10000 <= y <= 10000):
                        warnings.append(f"Position coordinates seem extreme: ({x}, {y})")
                except (ValueError, TypeError):
                    errors.append("Position coordinates must be numeric")

        # Check rotation data
        rotation = data.get('rotation')
        if rotation is not None:
            try:
                rot_val = float(rotation)
                if not (0 <= rot_val <= 360):
                    warnings.append(f"Rotation value outside normal range: {rot_val}")
            except (ValueError, TypeError):
                errors.append("Rotation must be numeric")

        # Check scale data
        scale = data.get('scale')
        if scale is not None:
            try:
                scale_val = float(scale)
                if scale_val <= 0:
                    errors.append("Scale must be positive")
                elif scale_val > 10:
                    warnings.append(f"Large scale value may cause positioning issues: {scale_val}")
            except (ValueError, TypeError):
                errors.append("Scale must be numeric")

        # Validate transform matrix if present
        debug_info.transform_valid = self._validate_transform_matrix(data)

        # Test SVG generation
        try:
            svg_content = self._generate_test_svg(debug_info.mechanism_type, data)
            debug_info.svg_generated = bool(svg_content)
            debug_info.svg_length = len(svg_content) if svg_content else 0

            if svg_content:
                debug_info.bounding_box = self.parse_svg_bounds(svg_content)
            else:
                errors.append("SVG generation failed - no content produced")

        except Exception as e:
            errors.append(f"SVG generation error: {str(e)}")

        return debug_info

    def _validate_transform_matrix(self, data: dict[str, Any]) -> bool:
        """Validate transform matrix calculations"""
        try:
            position = data.get('position', [0, 0])
            rotation = data.get('rotation', 0)
            scale = data.get('scale', 1)

            # Basic validation
            x, y = float(position[0]), float(position[1])
            rot = float(rotation)
            sc = float(scale)

            # Check for reasonable values
            if abs(x) > 50000 or abs(y) > 50000:
                return False
            if sc <= 0 or sc > 100:
                return False

            return True

        except (ValueError, TypeError, IndexError):
            return False

    def _generate_test_svg(self, mechanism_type: str, data: dict[str, Any]) -> str:
        """Generate test SVG to verify mechanism generation"""

        # Import mechanism generators
        try:
            if mechanism_type == 'gear':
                from automataii.generation.gear import GearGenerator
                generator = GearGenerator()
                return generator.generate_svg(data)
            elif mechanism_type == 'linkage':
                from automataii.generation.linkage import LinkageGenerator
                generator = LinkageGenerator()
                return generator.generate_svg(data)
            elif mechanism_type == 'cam':
                from automataii.generation.cam import CamGenerator
                generator = CamGenerator()
                return generator.generate_svg(data)
            else:
                return ""
        except ImportError as e:
            self.logger.error(f"Failed to import mechanism generator: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Mechanism generator error: {e}")
            return ""

    def parse_svg_bounds(self, svg_content: str) -> BoundingBox | None:
        """
        Parse SVG content and calculate actual rendering bounds
        
        Args:
            svg_content: SVG content string
            
        Returns:
            BoundingBox object or None if parsing fails
        """
        if not svg_content:
            return None

        try:
            # Extract viewBox or width/height from SVG root
            viewbox_match = re.search(r'viewBox=["\']([\d\.\-\s]+)["\']', svg_content)
            if viewbox_match:
                coords = viewbox_match.group(1).strip().split()
                if len(coords) >= 4:
                    x, y, w, h = map(float, coords[:4])
                    return BoundingBox(x, y, w, h)

            # Try to extract width and height attributes
            width_match = re.search(r'width=["\']([\d\.]+)["\']', svg_content)
            height_match = re.search(r'height=["\']([\d\.]+)["\']', svg_content)

            if width_match and height_match:
                w = float(width_match.group(1))
                h = float(height_match.group(1))
                return BoundingBox(0, 0, w, h)

            # Fallback: analyze path coordinates
            return self._estimate_bounds_from_paths(svg_content)

        except Exception as e:
            self.logger.error(f"Error parsing SVG bounds: {e}")
            return None

    def _estimate_bounds_from_paths(self, svg_content: str) -> BoundingBox | None:
        """Estimate bounds by analyzing path coordinates"""

        try:
            # Find all numeric coordinates in path data
            coords = []

            # Match path d attributes
            path_matches = re.findall(r'd=["\']([\d\.\-\sMLCZ]+)["\']', svg_content)
            for path_data in path_matches:
                # Extract coordinates (simple regex for basic paths)
                numbers = re.findall(r'[\d\.\-]+', path_data)
                coords.extend([float(n) for n in numbers])

            # Match circle/rect coordinates
            circle_matches = re.findall(r'c[xy]=["\']([\d\.\-]+)["\']', svg_content)
            coords.extend([float(m) for m in circle_matches])

            rect_matches = re.findall(r'[xy]=["\']([\d\.\-]+)["\']', svg_content)
            coords.extend([float(m) for m in rect_matches])

            if coords:
                min_coord = min(coords)
                max_coord = max(coords)
                size = max_coord - min_coord
                return BoundingBox(min_coord, min_coord, size, size)

            return None

        except Exception as e:
            self.logger.error(f"Error estimating bounds from paths: {e}")
            return None

    

    

    
