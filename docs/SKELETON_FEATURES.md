# Skeleton Features Implementation

This document describes the implementation of two new skeleton features:
1. Skeleton length extension by 10%
2. Joint locking/unlocking for IK solving

## Implementation Overview

### 1. Skeleton Length Extension

The skeleton extension feature allows users to scale all bone lengths by a factor (default 10% increase).

**Key Components:**
- `SkeletonManager.extend_skeleton_lengths(scale_factor=1.1)` - Main method that scales skeleton
- Preserves root joint positions while scaling child positions
- Updates limb lengths in the skeleton model
- Emits `skeleton_updated` signal to notify UI

**Usage:**
```python
# Extend skeleton by 10%
skeleton_manager.extend_skeleton_lengths(1.1)
```

### 2. Joint Locking

Joint locking prevents specific joints from being rotated during IK solving.

**Key Components:**
- `StandardizedJointModel.is_locked` - New field in skeleton model
- `SkeletonManager.lock_joint(joint_id_or_name, locked=True)` - Lock/unlock specific joint
- `SkeletonManager.get_locked_joints()` - Get list of locked joint IDs
- `SkeletonManager.unlock_all_joints()` - Unlock all joints
- `CharacterPartItem.is_joint_locked` - Property to check if part's joint is locked
- IK solver respects locked joints and skips rotating them

**Usage:**
```python
# Lock a joint
skeleton_manager.lock_joint("neck", True)

# Get locked joints
locked = skeleton_manager.get_locked_joints()

# Unlock all
skeleton_manager.unlock_all_joints()
```

## UI Integration

### Image Processing Tab

Two new buttons added to the `ProcessingStepsGroup`:
1. **"Extend Skeleton 10%"** - Applies 10% extension to skeleton
2. **"Lock/Unlock Joints"** - Opens dialog to select joints to lock

### Implementation Details

1. **Skeleton Extension UI:**
   - Confirms action with user (irreversible)
   - Updates skeleton in skeleton manager
   - Refreshes view with new skeleton positions

2. **Joint Lock Dialog:**
   - Shows list of all joints with checkboxes
   - Checked = locked, unchecked = unlocked
   - Updates skeleton manager and refreshes view

### Editor Tab Integration

The editor tab automatically:
- Sets joint lock status on CharacterPartItems when loading parts
- Updates lock status when skeleton is updated
- IK solver skips locked joints during solving

## Technical Details

### Modified Files:

1. **Core:**
   - `core/models_skeleton.py` - Added `is_locked` field to `StandardizedJointModel`
   - `core/skeleton_manager.py` - Added extension and locking methods

2. **UI:**
   - `gui/widgets/processing_steps_group.py` - Added new buttons and signals
   - `gui/tabs/image_processing_tab.py` - Added handlers for new features
   - `gui/tabs/editor_tab.py` - Updates part items with lock status
   - `gui/graphics_items/part_item.py` - Added `is_joint_locked` property

3. **Kinematics:**
   - `kinematics/ik_solver.py` - Modified to skip locked joints

### Signals:

- `ProcessingStepsGroup.extendSkeletonClicked` - Emitted when extend button clicked
- `ProcessingStepsGroup.lockJointsClicked` - Emitted when lock/unlock button clicked
- `SkeletonManager.skeleton_updated` - Emitted when skeleton is modified

## Testing

Run the test script to verify functionality:
```bash
cd /Users/alansynn/Workspace/src/Research/automataii/src
python -m automataii.test_skeleton_features
```

The test verifies:
- Skeleton loading
- Extension by 10% with correct position updates
- Root joints remain fixed during extension
- Joint locking/unlocking
- Lock state persistence