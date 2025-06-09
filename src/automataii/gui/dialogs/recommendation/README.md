# Mechanism Recommendation Dialog Module

This module implements a dialog for recommending and selecting mechanisms based on user-drawn motion paths.

## Structure

The module is organized into the following components:

### Core Components

- **`dialog.py`** (108 lines) - Main dialog class that coordinates the UI
- **`preview_container.py`** (93 lines) - Container widget for individual mechanism previews
- **`preview_widget.py`** (104 lines) - Widget that renders mechanism visualizations
- **`preview_renderer.py`** (297 lines) - Rendering logic for different mechanism types (cam, gear, linkage)

### Services and Logic

- **`recommendation_service.py`** (145 lines) - Business logic for finding best mechanism matches
- **`path_analysis.py`** (67 lines) - Utilities for path comparison using Hausdorff distance
- **`data_loader.py`** (50 lines) - Handles loading mechanism data from JSON files

### Configuration

- **`constants.py`** (40 lines) - Constants, color definitions, and type mappings
- **`styles.py`** (97 lines) - Centralized stylesheet definitions

## Key Features

1. **Path Matching**: Uses Hausdorff distance to compare user-drawn paths with pre-generated mechanism paths
2. **Visual Preview**: Shows schematic visualizations of different mechanism types
3. **Type Diversity**: Ensures recommendations include different mechanism types when possible
4. **Interactive Selection**: Click to preview, button to select

## Usage

```python
from automataii.gui.dialogs.recommendation import MechanismRecommendationDialog

# Show dialog and get selected mechanism
selected = MechanismRecommendationDialog.get_recommendation(
    user_motion_path,  # QPainterPath drawn by user
    generated_paths_filepath,  # Path to JSON file with mechanisms
    parent=parent_widget
)

if selected:
    # Use selected mechanism data
    print(f"Selected: {selected['name']}")
```

## Design Principles

- **Single Responsibility**: Each file has a focused purpose
- **Separation of Concerns**: Business logic separated from UI code
- **Modularity**: Components can be tested and modified independently
- **Type Safety**: Uses type hints throughout
- **Clean Architecture**: Services don't depend on UI components