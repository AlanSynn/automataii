#!/usr/bin/env python3
"""
Conservative cleanup of excessive logging in IK Manager.
Only removes complete debug logging statements, preserves all code structure.
"""

import re
import sys
from pathlib import Path

def clean_ik_logging_conservative(file_path: str):
    """Conservatively clean up excessive logging in IK Manager file."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_debug_count = sum(1 for line in lines if 'logging.debug' in line)
    original_total_count = sum(1 for line in lines if 'logging.' in line)
    
    print(f"Original: {original_debug_count} debug logs, {original_total_count} total logs")
    
    # Lines to remove (exact matches) - being very specific about what to remove
    lines_to_remove = [
        # Connection debug logs
        '        logging.debug(\n',
        '            f"IKManager (id:{id(self)}): set_skeleton_manager called. Old ref_id: {old_ref_id}, New ref_id: {new_ref_id}. New instance type: {type(skeleton_manager_instance)}"\n',
        '        )\n',
        
        # More specific removals - looking for exact line patterns
    ]
    
    # Instead of removing by exact lines, let's remove by patterns that we're sure about
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip verbose debug logging blocks while preserving structure
        if ('logging.debug(' in line and 
            any(pattern in line for pattern in [
                'set_skeleton_manager called',
                'Disconnected from old SkeletonManager',
                'Connected to new SkeletonManager', 
                'TypeError while disconnecting',
                'RuntimeError while disconnecting',
                'SkeletonManager instance was set to None',
                'set_project_parts_data called',
                'head\' part IS IN incoming',
                'head\' part IS NOT in incoming',
                'head\' (incoming) motion_path_data IS',
                'head\' part exists in self.project_parts_data',
                'head\' part DOES NOT exist',
                'Applying pending motion path',
                'Applied PENDING motion path',
                'project_parts_data[\'head\'].motion_path_data IS NOW',
                'Could not apply pending motion path',
                'AFTER pending paths',
                '_try_initialize_solver attempt',
                'Still waiting for valid skeleton data',
                'Still waiting for project parts data',
                'Prerequisites met',
                'IK Solver initialized successfully',
                '(Placeholder) IK solver marked as initialized',
                'About to iterate self._current_skeleton_data',
                'Processing joint_id:',
                'pos_list for',
                'Added.*to _sim_dynamic_joints_data',
                'NOT added to _sim_dynamic_joints_data',
                'Could not populate sim_joints_config',
                'Calculated initial angle for',
                'num_sim_config_joints =',
                'num_dynamic_joints =', 
                'num_snapshot_items =',
                'Set limb length for',
                'Part.*for length measurement not found',
                'Populated sim_limb_lengths',
                'Using sim_joint_rest_angles',
                'nearly straight, using default direction',
                'naturally bends',
                'Received skeleton update',
                'Received empty skeleton dict',
                'Missing project_parts_data',
                'Missing sim_joints_config',
                'No sim_selectable_components defined',
                'update_part_motion_path ENTRY',
                'update_part_motion_path CALLED FOR',
                'pre-workaround',
                'Cannot update motion path for',
                'head\'s path stored as PENDING',
                'project_parts_data not set',
                'Updated motion path for part',
                'head\' motion_path_data directly updated',
                'not found in project_parts_data',
                'before _try_initialize_solver',
                'dynamic_joints setter called',
                'Cannot recalculate bone angles',
                'Updated standalone joint',
                'Recalculated angles for'
            ])):
            # Skip this debug line and any continuation lines
            if line.strip().endswith('('):
                # Multi-line debug statement, skip until we find the closing )
                while i < len(lines) and not lines[i].strip().endswith(')'):
                    i += 1
                i += 1  # Skip the closing ) line too
                continue
            else:
                # Single line debug statement
                i += 1
                continue
        
        # Keep the line
        cleaned_lines.append(line)
        i += 1
    
    # Count remaining logs
    final_debug_count = sum(1 for line in cleaned_lines if 'logging.debug' in line)
    final_total_count = sum(1 for line in cleaned_lines if 'logging.' in line)
    
    print(f"After cleanup: {final_debug_count} debug logs, {final_total_count} total logs")
    print(f"Removed: {original_debug_count - final_debug_count} debug logs, {original_total_count - final_total_count} total logs")
    
    # Write cleaned content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)
    
    print(f"✅ Cleaned up {file_path}")
    
    return True

if __name__ == "__main__":
    ik_manager_path = "/Users/alansynn/Workspace/src/Research/automataii/src/automataii/kinematics/ik_manager.py"
    
    if not Path(ik_manager_path).exists():
        print(f"❌ File not found: {ik_manager_path}")
        sys.exit(1)
    
    try:
        clean_ik_logging_conservative(ik_manager_path)
        print("🎉 IK Manager logging cleanup completed successfully!")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        sys.exit(1)