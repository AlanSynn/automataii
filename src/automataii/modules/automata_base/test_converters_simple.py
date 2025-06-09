#!/usr/bin/env python3
"""Direct test of converter issues"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Import converters directly
import importlib.util
spec = importlib.util.spec_from_file_location("converters", "utils/converters.py")
converters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converters)

# Test the functions
print("Testing converter parameter issue...")

# The issue is likely that the functions expect certain object types
# Let's check what happens with a mock object

class MockConfig:
    def __init__(self):
        self.base_type = type('obj', (object,), {'value': 'flat_rectangular'})
        self.dimensions = type('obj', (object,), {
            'width': 200,
            'height': 150,
            'to_2d': lambda exclude_axis=None: type('obj', (object,), {
                'width': 200,
                'height': 150,
                'unit': type('obj', (object,), {'value': 'mm'})
            })()
        })()
        self.mounting_points = []
        self.material_thickness = 6.0

config = MockConfig()

try:
    # This should reveal the actual error
    result = converters.base_to_svg(config)
    print(f"✅ SVG conversion worked: {len(result)} chars")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    
    # Let's trace where the error occurs
    import traceback
    traceback.print_exc()
    
print("\nChecking what might be wrong...")
print(f"Config type: {type(config)}")
print(f"Dimensions type: {type(config.dimensions)}")
print(f"Width: {config.dimensions.width}")

# Check if it's a multiplication issue
try:
    test_mult = config.dimensions.width * 1.0
    print(f"✅ Multiplication works: {test_mult}")
except Exception as e:
    print(f"❌ Multiplication error: {e}")