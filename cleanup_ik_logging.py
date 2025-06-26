#!/usr/bin/env python3
"""
Script to clean up excessive logging in IK Manager.
Removes verbose debug logs while preserving critical functionality.
"""

import re
import sys
from pathlib import Path

def clean_ik_logging(file_path: str):
    """Clean up excessive logging in IK Manager file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_debug_count = len(re.findall(r'logging\.debug', content))
    original_total_count = len(re.findall(r'logging\.', content))
    
    print(f"Original: {original_debug_count} debug logs, {original_total_count} total logs")
    
    # Remove specific debug logging patterns
    removals = [
        # Connection/disconnection debug logs
        r'        logging\.debug\(\s*f"IKManager.*?(?:Connected|Disconnected) to.*?SkeletonManager.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager.*?TypeError while disconnecting.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager.*?RuntimeError while disconnecting.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager.*?SkeletonManager instance was set to None.*?"\s*\)\n',
        
        # Parts data debug logs
        r'        logging\.debug\(\s*f"IKManager: set_project_parts_data called.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part IS IN incoming parts_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part IS NOT in incoming parts_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: \'head\' \(incoming\) motion_path_data IS.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part exists in self\.project_parts_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part DOES NOT exist in self\.project_parts_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Applied PENDING motion path for \'head\'.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: project_parts_data\[\'head\'\]\.motion_path_data IS NOW.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Applying pending motion path for part.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Could not apply pending motion path for.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: AFTER pending paths, project_parts_data\[\'head\'\].*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: AFTER pending paths, \'head\' part still not.*?"\s*\)\n',
        
        # Initialization debug logs
        r'        logging\.debug\(\s*f"IKManager: _try_initialize_solver attempt.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Still waiting for valid skeleton data.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Still waiting for project parts data.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Prerequisites met.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: IK Solver initialized successfully.*?"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \(Placeholder\) IK solver marked as initialized.*?"\s*\)\n',
        
        # Joint processing debug logs
        r'        logging\.debug\(\s*f"IKManager DEBUG: About to iterate.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: Processing joint_id.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:   pos_list for.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:     Added.*?to _sim_dynamic_joints_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:     .*?NOT added to _sim_dynamic_joints_data.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager WARNING: Could not populate sim_joints_config.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Calculated initial angle for.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_sim_config_joints.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_dynamic_joints.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_snapshot_items.*?"\s*\)\n',
        
        # Limb configuration debug logs
        r'        logging\.debug\(\s*f"IKManager: Set limb length for.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Part.*?for length measurement not found.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Populated sim_limb_lengths.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Using sim_joint_rest_angles.*?"\s*\)\n',
        
        # Bend direction debug logs (keep the critical ones)
        r'        logging\.debug\(\s*f"IKManager: \'.*?\' nearly straight, using default direction"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: \'.*?\' naturally bends.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"{joint_name}: {direction}"\s*\)\n',
        
        # Skeleton update debug logs
        r'        logging\.debug\(\s*f"IKManager.*?Received skeleton update.*?from SkeletonManager.*?"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager.*?Received empty skeleton dict.*?"\s*\)\n',
        
        # Animation debug logs
        r'        logging\.debug\(\s*f"IKManager.*?Animation step.*?"\s*\)\n',
        r'        logging\.debug\(\s*f".*?_run_ik_animation_step.*?"\s*\)\n',
        r'        logging\.debug\(\s*f".*?Progress:.*?ms elapsed.*?"\s*\)\n',
        r'        logging\.debug\(\s*f".*?Target position for.*?"\s*\)\n',
        r'        logging\.debug\(\s*f".*?Current position.*?Target.*?"\s*\)\n',
        r'        logging\.debug\(\s*f".*?solving two-bone IK for.*?"\s*\)\n',
        
        # Verbose multiline debug statements
        r'        logging\.debug\(\s*f"IKManager.*?set_skeleton_manager called.*?New instance type.*?"\s*\)\n',
        
        # Remove excessive comment blocks
        r'        # ---- ADD DEBUG LOGS ----\n.*?        # ---- END DEBUG LOGS ----\n',
        
        # Remove excessive inline comments for debug logs
        r'        # Getter will be used\n',
        r'        # Setter will log this\n',
        r'        # Setter logs details\n',
        r'        # Will use setter\n',
        
        # Remove commented out debug statements
        r'            # logging\.debug.*?\n',
    ]
    
    # Apply all removals
    for pattern in removals:
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
    
    # Clean up excessive empty lines (max 2 consecutive empty lines)
    content = re.sub(r'\n\n\n+', '\n\n', content)
    
    # Remove trailing whitespace
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    content = '\n'.join(lines)
    
    # Count remaining logs
    final_debug_count = len(re.findall(r'logging\.debug', content))
    final_total_count = len(re.findall(r'logging\.', content))
    
    print(f"After cleanup: {final_debug_count} debug logs, {final_total_count} total logs")
    print(f"Removed: {original_debug_count - final_debug_count} debug logs, {original_total_count - final_total_count} total logs")
    
    # Write cleaned content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Cleaned up {file_path}")
    
    return True

if __name__ == "__main__":
    ik_manager_path = "/Users/alansynn/Workspace/src/Research/automataii/src/automataii/kinematics/ik_manager.py"
    
    if not Path(ik_manager_path).exists():
        print(f"❌ File not found: {ik_manager_path}")
        sys.exit(1)
    
    try:
        clean_ik_logging(ik_manager_path)
        print("🎉 IK Manager logging cleanup completed successfully!")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        sys.exit(1)