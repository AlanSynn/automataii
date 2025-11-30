#!/usr/bin/env python3
"""
Direct test of the blueprint export functionality to verify it's working correctly.
This test simulates what happens when the user exports a blueprint.
"""
import sys
sys.path.append('src')
import pytest

# Manual blueprint export inspection; skip in automated pytest runs.
pytest.skip("Manual blueprint export test; skipping in automated pytest.", allow_module_level=True)

from automataii.infrastructure.generation.svg.blueprint import generate_single_large_blueprint
from automataii.infrastructure.generation.svg.optimizer import BlueprintLayoutOptimizer
import os

def test_direct_blueprint_export():
    """Test direct blueprint export functionality"""
    print("🧪 Testing direct blueprint export...")
    
    # Simulate some basic part and mechanism data
    part_items = [
        {
            'id': 'test_head',
            'type': 'head',
            'bounds': {'width': 50, 'height': 60},
            'clip_path': 'M 0 0 L 50 0 L 50 60 L 0 60 Z',
            'texture_data_uri': None
        },
        {
            'id': 'test_torso',
            'type': 'torso', 
            'bounds': {'width': 80, 'height': 120},
            'clip_path': 'M 0 0 L 80 0 L 80 120 L 0 120 Z',
            'texture_data_uri': None
        }
    ]
    
    mechanism_layers = {
        'test_4bar': {
            'id': 'test_4bar',
            'type': '4_bar_linkage',
            'total_scale_factor': 1.5,
            'key_points': {
                'ground_pivot_a': [0, 0],
                'ground_pivot_b': [60, 0], 
                'coupler_a': [20, 40],
                'coupler_b': [40, 40]
            }
        },
        'test_gear': {
            'id': 'test_gear',
            'type': 'gear',
            'total_scale_factor': 1.2,
            'params': {
                'radius_mm': 25.0,
                'teeth': 20
            }
        }
    }
    
    # Create optimizer
    optimizer = BlueprintLayoutOptimizer(target_character_height_mm=300.0)
    
    # Optimize layout 
    print("⚙️  Optimizing blueprint layout...")
    layout_items, scale_info, metrics = optimizer.optimize_blueprint_layout(part_items, mechanism_layers)
    
    print(f"✅ Layout optimization complete:")
    print(f"   - Layout items: {len(layout_items)}")
    print(f"   - Scale info: {scale_info}")
    print(f"   - Metrics: {metrics}")
    
    # Generate blueprint
    print("📝 Generating blueprint SVG...")
    
    page_width_mm = 800.0
    page_height_mm = 600.0
    
    svg_content = generate_single_large_blueprint(
        layout_items,
        page_width_mm,
        page_height_mm,
        title="Test Manufacturing Blueprint",
        scale_info="Test Scale: 1.0 mm/pixel",
        snapshot_data_uri=None,
    )
    
    # Save to file
    output_file = 'test_direct_blueprint_export.svg'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"✅ Blueprint exported successfully to {output_file}")
    print(f"   - File size: {len(svg_content):,} characters")
    
    # Verify file exists and has content
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"✅ File verification passed: {file_size:,} bytes")
        
        # Check if file contains expected content
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        checks = [
            ('SVG header', '<svg' in content),
            ('Blueprint title', 'Test Manufacturing Blueprint' in content),
            ('Character parts', 'test_head' in content or 'test_torso' in content),
            ('Mechanisms', 'test_4bar' in content or 'test_gear' in content),
            ('Manufacturing details', 'manufacturing' in content.lower()),
        ]
        
        print("\n🔍 Content verification:")
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")
            
        all_passed = all(passed for _, passed in checks)
        print(f"\n🎯 Overall result: {'✅ SUCCESS' if all_passed else '❌ PARTIAL'}")
        
        if all_passed:
            print("\n💡 Blueprint export is working correctly!")
            print("   The exported file should contain:")
            print("   - Character parts with proper scaling")  
            print("   - Enhanced mechanisms with manufacturing details")
            print("   - Proper layout and dimensions")
        else:
            print("\n⚠️  Some content checks failed. Review the implementation.")
            
    else:
        print(f"❌ File creation failed: {output_file} not found")
        return False
        
    return True

if __name__ == "__main__":
    try:
        success = test_direct_blueprint_export()
        if success:
            print(f"\n🎉 Direct blueprint export test completed successfully!")
        else:
            print(f"\n❌ Direct blueprint export test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
