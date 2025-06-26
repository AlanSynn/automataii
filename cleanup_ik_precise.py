#!/usr/bin/env python3
"""
Precise cleanup of IK Manager logging by removing complete logging statement blocks.
"""

import sys
from pathlib import Path

def remove_logging_blocks(file_path: str):
    """Remove specific debug logging blocks while preserving code structure."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original_debug_count = sum(1 for line in lines if 'logging.debug' in line)
    original_total_count = sum(1 for line in lines if 'logging.' in line)
    
    print(f"Original: {original_debug_count} debug logs, {original_total_count} total logs")
    
    cleaned_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this is start of a debug logging statement we want to remove
        if 'logging.debug(' in line:
            # Check for specific patterns we want to remove
            should_remove = False
            debug_content = line
            
            # For multiline statements, collect the full statement
            if not line.strip().endswith(')'):
                j = i + 1
                while j < len(lines) and not lines[j-1].strip().endswith(')'):
                    debug_content += lines[j]
                    j += 1
                
            # Patterns to remove
            remove_patterns = [
                'set_skeleton_manager called',
                'Disconnected from old SkeletonManager', 
                'Connected to new SkeletonManager',
                'TypeError while disconnecting',
                'RuntimeError while disconnecting',
                'SkeletonManager instance was set to None',
                'set_project_parts_data called. Received',
                'head\' part IS IN incoming parts_data',
                'head\' part IS NOT in incoming parts_data', 
                'head\' (incoming) motion_path_data IS',
                'head\' part exists in self.project_parts_data after copy',
                'head\' part DOES NOT exist in self.project_parts_data',
                'Applying pending motion path for part',
                'Applied PENDING motion path for \'head\'',
                'project_parts_data[\'head\'].motion_path_data IS NOW',
                'Could not apply pending motion path for',
                'AFTER pending paths, project_parts_data[\'head\']',
                'AFTER pending paths, \'head\' part still not',
                '_try_initialize_solver attempt',
                'Still waiting for valid skeleton data',
                'Still waiting for project parts data',
                'Prerequisites met (skeleton & parts data)',
                'IK Solver initialized successfully',
                '(Placeholder) IK solver marked as initialized',
                'About to iterate self._current_skeleton_data',
                'Processing joint_id:',
                'pos_list for',
                'Added .* to _sim_dynamic_joints_data',
                'NOT added to _sim_dynamic_joints_data',
                'Could not populate sim_joints_config',
                'Calculated initial angle for',
                'num_sim_config_joints =',
                'num_dynamic_joints =',
                'num_snapshot_items =',
                'Set limb length for',
                'Part .* for length measurement not found',
                'Populated sim_limb_lengths:',
                'Using sim_joint_rest_angles:',
                'nearly straight, using default direction',
                'naturally bends',
                'Received skeleton update',
                'Received empty skeleton dict',
                'Missing project_parts_data',
                'Missing sim_joints_config',
                'No sim_selectable_components defined',
                'update_part_motion_path ENTRY for',
                'update_part_motion_path CALLED FOR \'head\'',
                'pre-workaround) for',
                'Cannot update motion path for',
                'head\'s path stored as PENDING',
                'project_parts_data not set, pending',
                'Updated motion path for part',
                'head\' motion_path_data directly updated',
                'not found in project_parts_data',
                'before _try_initialize_solver',
                'dynamic_joints setter called with',
                'Cannot recalculate bone angles',
                'Updated standalone joint',
                'Recalculated angles for .* bones after IK'
            ]
            
            for pattern in remove_patterns:
                if pattern in debug_content:
                    should_remove = True
                    break
            
            if should_remove:
                # Skip this logging block
                if not line.strip().endswith(')'):
                    # Multi-line statement, skip until closing )
                    while i < len(lines) and not lines[i].strip().endswith(')'):
                        i += 1
                    i += 1  # Skip the closing ) line
                else:
                    # Single line statement
                    i += 1
                continue
        
        # Keep this line
        cleaned_lines.append(line)
        i += 1
    
    # Count final logs
    final_debug_count = sum(1 for line in cleaned_lines if 'logging.debug' in line)
    final_total_count = sum(1 for line in cleaned_lines if 'logging.' in line)
    
    print(f"After cleanup: {final_debug_count} debug logs, {final_total_count} total logs")
    print(f"Removed: {original_debug_count - final_debug_count} debug logs")
    
    # Write back
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
        remove_logging_blocks(ik_manager_path)
        print("🎉 IK Manager logging cleanup completed!")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)