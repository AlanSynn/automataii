#!/usr/bin/env python3
"""Test and fix converter issues"""

import sys
from pathlib import Path

# Use local imports
sys.path.insert(0, str(Path(__file__).parent))

from models.base_config import BaseConfiguration
from enums.base_types import BaseType, MaterialType  
from models.dimensions import Dimensions2D, Point2D, MountingPoint
from utils.converters import base_to_svg, base_to_dxf

print("Testing converters...")

# Create a simple configuration
config = BaseConfiguration(
    name="Test Base",
    base_type=BaseType.FLAT_RECTANGULAR,
    dimensions=Dimensions2D(200, 150),
    primary_material=MaterialType.PLYWOOD,
    material_thickness=6.0
)

# Add mounting points
config.add_mounting_point(MountingPoint(
    position=Point2D(50, 50),
    hole_diameter=4.0,
    thread_type="M4"
))

print("Configuration created successfully")

# Test SVG export
try:
    svg_output = base_to_svg(config)
    print(f"✅ SVG export successful: {len(svg_output)} characters")
except Exception as e:
    print(f"❌ SVG export error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test DXF export
try:
    dxf_output = base_to_dxf(config)
    print(f"✅ DXF export successful: {len(dxf_output)} characters")
except Exception as e:
    print(f"❌ DXF export error: {type(e).__name__}: {e}")