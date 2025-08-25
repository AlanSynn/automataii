#!/usr/bin/env python3
"""
Verify unused methods by actually searching for their usage
"""

import re
from pathlib import Path
from typing import List, Tuple

def search_method_usage(method_name: str, file_path: str) -> List[Tuple[int, str]]:
    """Search for actual usage of a method in the file"""
    usage_patterns = [
        rf'\.{method_name}\s*\(',           # obj.method_name(
        rf'self\.{method_name}\s*\(',       # self.method_name(
        rf'{method_name}\s*\(',             # method_name( (direct call)
        rf'connect\s*\(\s*.*{method_name}',  # signal.connect(method_name)
        rf'\.connect\s*\(.*{method_name}',   # .connect(method_name)
    ]
    
    usage_lines = []
    
    try:
        content = Path(file_path).read_text(encoding='utf-8')
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Skip the method definition itself
            if f'def {method_name}(' in line:
                continue
                
            for pattern in usage_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    usage_lines.append((line_num, line.strip()))
                    break
    
    except Exception as e:
        print(f"Error reading file: {e}")
    
    return usage_lines

def verify_orphan_methods():
    """Verify which methods are actually orphaned"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    # Methods identified as potentially orphaned
    candidates = [
        "_add_test_path_for_debugging",
        "_create_mechanism_visuals_unified", 
        "_check_4bar_validity",
        "_check_multibar_validity",
        "_check_gear_validity",
        "_calculate_4bar_rocker_position",
        "_validate_anchor_constraints",
        "_regenerate_cam_mechanism_realtime",
        "_regenerate_cam_visuals_with_params",
        "_create_gear_handles",
        "_remove_parametric_handles_for_mechanism",
        "_show_current_mechanism_dimensions",
        "_export_current_mechanism_blueprint",
        "_rotate_mechanism",
        "_create_rotation_handle",
        "_show_free_edit_feedback"
    ]
    
    truly_unused = []
    used_methods = []
    
    for method in candidates:
        print(f"\nChecking: {method}")
        usage = search_method_usage(method, file_path)
        
        if not usage:
            print(f"  ✓ No usage found - SAFE TO REMOVE")
            truly_unused.append(method)
        else:
            print(f"  ✗ Found {len(usage)} usages:")
            for line_num, line in usage[:3]:  # Show first 3 usages
                print(f"    Line {line_num}: {line}")
            used_methods.append((method, usage))
    
    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"{'='*60}")
    print(f"Truly unused methods ({len(truly_unused)}):")
    for method in truly_unused:
        print(f"  - {method}")
    
    print(f"\nMethods with usage found ({len(used_methods)}):")
    for method, usage in used_methods:
        print(f"  - {method} ({len(usage)} usages)")
    
    return truly_unused, used_methods

if __name__ == "__main__":
    verify_orphan_methods()