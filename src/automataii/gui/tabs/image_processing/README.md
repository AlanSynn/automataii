# Image Processing Tab Refactored Structure

This directory contains the refactored image processing tab with a modular architecture following the Single Responsibility Principle.

## Directory Structure

```
image_processing/
├── __init__.py              # Module entry point
├── tab_coordinator.py       # Main tab coordinator that brings all components together
├── state_manager.py         # Centralized state management for the tab
├── control_panels.py        # UI control panels (left side)
├── view_manager.py          # View and zoom control management
└── services/               # Business logic services
    ├── __init__.py
    ├── image_service.py     # Image loading and capture operations
    ├── processing_service.py # Image processing operations
    ├── skeleton_service.py  # Skeleton management operations
    └── parts_service.py     # Body parts generation
```

## Component Responsibilities

### Tab Coordinator (`tab_coordinator.py`)
- Main widget that coordinates all components
- Handles signal routing between components
- Maintains backward compatibility with existing code
- ~180 lines

### State Manager (`state_manager.py`) 
- Centralized state management
- Provides state queries for UI updates
- Manages file paths and processing results
- ~90 lines

### Control Panels (`control_panels.py`)
- Left side UI controls
- Button groups and checkboxes
- Processing steps group integration
- ~90 lines

### View Manager (`view_manager.py`)
- Manages the image processing view
- Handles zoom controls and toolbar
- View state management
- ~200 lines

### Services

#### Image Service (`image_service.py`)
- File dialog operations
- Camera capture
- Image loading logic
- ~85 lines

#### Processing Service (`processing_service.py`)
- Image annotation processing
- Progress dialog management
- Error handling
- ~70 lines

#### Skeleton Service (`skeleton_service.py`)
- Skeleton loading/saving
- Skeleton editing operations
- Joint locking dialog
- ~190 lines

#### Parts Service (`parts_service.py`)
- Body parts generation
- Progress tracking
- Output validation
- ~110 lines

## Key Improvements

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Testability**: Services can be tested independently from UI
3. **Maintainability**: Smaller files are easier to understand and modify
4. **Reusability**: Services can be reused by other components
5. **Clear Dependencies**: Import structure shows component relationships

## Usage

The refactored tab maintains full backward compatibility. Import and use it exactly as before:

```python
from automataii.gui.tabs import ImageProcessingTab

# In MainWindow
self.image_processing_tab = ImageProcessingTab(self)
```

## Migration Notes

- The original file (`image_processing_tab.py`) has been renamed to `image_processing_tab_old.py` as a backup
- All functionality remains the same from the user's perspective
- Internal structure is now modular and easier to maintain