# Skeleton Management Module

This module provides a modular architecture for managing skeleton data in Automataii. The previous monolithic `skeleton_manager.py` (824 lines) has been refactored into smaller, focused components following the Single Responsibility Principle.

## Architecture

### Components

1. **models.py** (~85 lines)
   - Data models: `StandardizedJointModel` and `StandardizedSkeletonModel`
   - Pure data structures with validation via Pydantic

2. **format_converter.py** (~295 lines)
   - Format detection and conversion logic
   - Handles conversion from Animated Drawings format to standardized format
   - Supports multiple input formats with auto-detection

3. **joint_manager.py** (~120 lines)
   - Joint access and query operations
   - Methods for finding joints by ID, name, or original name
   - Position queries and relationship lookups

4. **hierarchy_manager.py** (~185 lines)
   - Parent-child relationship management
   - Tree traversal operations (ancestors, descendants, siblings)
   - Hierarchy validation and consistency checks

5. **operations.py** (~280 lines)
   - Skeleton transformation operations (translate, rotate, scale, mirror)
   - Joint locking/unlocking for IK
   - Bone length extension

6. **serializer.py** (~130 lines)
   - Save/load skeleton data to/from files
   - JSON serialization and deserialization
   - Export simplified representations

7. **manager.py** (~195 lines)
   - Main orchestrator that coordinates all components
   - Qt signal integration for UI updates
   - Public API that delegates to specialized components

## Usage

The public API remains the same as the original `SkeletonManager`:

```python
from automataii.core.skeleton import SkeletonManager

# Create manager
manager = SkeletonManager()

# Load skeleton data
manager.load_skeleton_from_dict(skeleton_data)

# Access joints
joint = manager.get_joint_by_name("hip")
children = manager.get_child_joints("hip")

# Perform operations
manager.extend_skeleton_lengths(1.1)  # 10% extension
manager.lock_joint("head", True)

# Save/load
manager.save_skeleton_to_file(Path("skeleton.json"))
```

## Benefits of Refactoring

1. **Maintainability**: Each component has a clear, single responsibility
2. **Testability**: Components can be tested in isolation
3. **Reusability**: Components can be used independently if needed
4. **Readability**: Smaller files are easier to understand and navigate
5. **Extensibility**: New features can be added to specific components without affecting others

## Migration Notes

- The original `skeleton_manager.py` has been renamed to `skeleton_manager_old.py`
- All imports from `core.managers.skeleton_manager` should continue to work via the re-export in `core.managers.__init__.py`
- The public API is unchanged, ensuring backward compatibility