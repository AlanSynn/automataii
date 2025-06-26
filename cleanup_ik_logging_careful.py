#!/usr/bin/env python3
"""
Careful cleanup of excessive logging in IK Manager.
Removes verbose debug logs while preserving critical functionality and code structure.
"""

import re
import sys
from pathlib import Path

def clean_ik_logging_careful(file_path: str):
    """Carefully clean up excessive logging in IK Manager file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_debug_count = len(re.findall(r'logging\.debug', content))
    original_total_count = len(re.findall(r'logging\.', content))
    
    print(f"Original: {original_debug_count} debug logs, {original_total_count} total logs")
    
    # Patterns to remove - being very careful about line boundaries and indentation
    patterns_to_remove = [
        # Connection/disconnection debug logs - complete statements only
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): set_skeleton_manager called\. Old ref_id:.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Disconnected from old SkeletonManager.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): TypeError while disconnecting.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): RuntimeError while disconnecting.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Connected to new SkeletonManager.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): SkeletonManager instance was set to None.*?\"\s*\)\n',
        
        # Parts data verbose debug logs
        r'        logging\.debug\(\s*f"IKManager: set_project_parts_data called\. Received.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part IS IN incoming parts_data for set_project_parts_data\."\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: \'head\' \(incoming\) motion_path_data IS.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part IS NOT in incoming parts_data for set_project_parts_data\."\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part exists in self\.project_parts_data after copy\."\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' part DOES NOT exist in self\.project_parts_data after copy\."\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Applying pending motion path for part.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Applied PENDING motion path for \'head\'.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: project_parts_data\[\'head\'\]\.motion_path_data IS NOW.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Could not apply pending motion path for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: AFTER pending paths, project_parts_data\[\'head\'\].*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: AFTER pending paths, \'head\' part still not.*?\"\s*\)\n',
        
        # Initialization debug logs
        r'        logging\.debug\(\s*f"IKManager: _try_initialize_solver attempt.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Still waiting for valid skeleton data.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Still waiting for project parts data\."\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: _try_initialize_solver: Prerequisites met.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: IK Solver initialized successfully\."\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \(Placeholder\) IK solver marked as initialized\."\s*\)\n',
        
        # Joint processing debug logs
        r'        logging\.debug\(\s*f"IKManager DEBUG: About to iterate.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: Processing joint_id:.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:   pos_list for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:     Added.*?to _sim_dynamic_joints_data\."\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG:     .*?NOT added to _sim_dynamic_joints_data.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager WARNING: Could not populate sim_joints_config.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Calculated initial angle for.*?\"\s*\)\n',
        
        # Excessive numeric debug logs
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_sim_config_joints = \{num_sim_config_joints\}"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_dynamic_joints = \{num_dynamic_joints\}"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager DEBUG: num_snapshot_items = \{num_snapshot_items\}"\s*\)\n',
        
        # Limb configuration debug logs
        r'        logging\.debug\(\s*f"IKManager: Set limb length for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Part.*?for length measurement not found.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Populated sim_limb_lengths.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: Using sim_joint_rest_angles.*?\"\s*\)\n',
        
        # Some bend direction debug logs (keep the critical ones)
        r'        logging\.debug\(\s*f"IKManager: \'.*?\' nearly straight, using default direction"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: \'.*?\' naturally bends.*?\"\s*\)\n',
        
        # Skeleton update debug logs
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Received skeleton update.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Received empty skeleton dict.*?\"\s*\)\n',
        
        # Animation step debug logs (keep some, remove excessive ones)
        r'        logging\.debug\(\s*"IKManager\._run_ik_animation_step: Missing project_parts_data\."\s*\)\n',
        r'        logging\.debug\(\s*"IKManager\._run_ik_animation_step: Missing sim_joints_config.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager\._run_ik_animation_step: No sim_selectable_components defined\."\s*\)\n',
        
        # Motion path debug logs
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\)\.update_part_motion_path ENTRY for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager: update_part_motion_path CALLED FOR \'head\'.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\)\.update_part_motion_path \(pre-workaround\) for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Cannot update motion path for.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\'s path stored as PENDING.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager\.update_part_motion_path \(project_parts_data not set.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Updated motion path for part.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\' motion_path_data directly updated.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager \(id:\{id\(self\)\}\): Part.*?not found in project_parts_data.*?\"\s*\)\n',
        r'        logging\.debug\(\s*"IKManager: \'head\'s path stored as PENDING because.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKManager\.update_part_motion_path \(before _try_initialize_solver\).*?\"\s*\)\n',
        
        # Dynamic joints debug logs
        r'        logging\.debug\(\s*f"IKManager: dynamic_joints setter called with.*?\"\s*\)\n',
        
        # Angle recalculation debug logs (keep critical ones, remove verbose ones)
        r'        logging\.debug\(\s*"IKM: Cannot recalculate bone angles - missing sim_joints_config or initial_snapshot"\s*\)\n',
        r'        logging\.debug\(\s*f"IKM: Updated standalone joint.*?\"\s*\)\n',
        r'        logging\.debug\(\s*f"IKM: Recalculated angles for.*?\"\s*\)\n',
        
        # Remove multi-line debug comment blocks but preserve the debug log sections
        r'        # ---- ADD DEBUG LOGS ----\n.*?        # ---- END DEBUG LOGS ----\n',
        
        # Remove standalone comment lines for debugging
        r'        # Getter will be used\n',
        r'        # Setter will log this\n', 
        r'        # Setter logs details\n',
        r'        # Will use setter\n',
    ]
    
    # Apply all removals
    for pattern in patterns_to_remove:
        old_content = content
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
        if content != old_content:
            print(f"Applied pattern removal")
    
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
        clean_ik_logging_careful(ik_manager_path)
        print("🎉 IK Manager logging cleanup completed successfully!")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        sys.exit(1)