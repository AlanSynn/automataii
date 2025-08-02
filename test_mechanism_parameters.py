#!/usr/bin/env python3
"""
Test script to verify that all mechanism parameters work correctly
with the new parameter name mapping system.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from automataii.services.mechanism_service import MechanismService

def test_mechanism_parameters():
    """Test parameter operations for all mechanism types"""
    
    # List of all mechanism types supported
    mechanism_types = [
        "four_bar_linkage",
        "slider_crank", 
        "gear_train",
        "cam_follower",
        "spring_system"
    ]
    
    service = MechanismService()
    
    for mechanism_type in mechanism_types:
        print(f"\n=== Testing {mechanism_type} ===")
        
        # Create mechanism
        success = service.create_mechanism(
            mechanism_type=mechanism_type,
            mechanism_id=f"test_{mechanism_type}"
        )
        
        if not success:
            print(f"❌ Failed to create {mechanism_type}")
            continue
            
        print(f"✅ Created {mechanism_type}")
        
        # Get parameter info
        param_info = service.get_parameter_info()
        if not param_info:
            print(f"❌ No parameter info for {mechanism_type}")
            continue
            
        print(f"📊 Found {len(param_info)} parameters:")
        
        # Test each parameter
        for param_name, info in param_info.items():
            print(f"  - {param_name}: {info.get('current_value', 'N/A')} "
                  f"[{info.get('min_value', 0)}-{info.get('max_value', 100)}]")
            
            # Test parameter update
            current_value = info.get('current_value', 50.0)
            min_value = info.get('min_value', 0.0)
            max_value = info.get('max_value', 100.0)
            
            # Test with a safe middle value
            test_value = min_value + (max_value - min_value) * 0.6
            
            update_success = service.update_parameter(param_name, test_value)
            if update_success:
                print(f"    ✅ Updated {param_name} = {test_value}")
            else:
                print(f"    ❌ Failed to update {param_name} = {test_value}")
        
        # Clean up
        service.remove_mechanism(f"test_{mechanism_type}")
        print(f"🧹 Cleaned up {mechanism_type}")

if __name__ == "__main__":
    test_mechanism_parameters()