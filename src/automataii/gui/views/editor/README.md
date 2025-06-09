# EditorView Refactoring

This directory contains the refactored EditorView implementation, broken down into smaller, focused modules following the Single Responsibility Principle.

## Module Structure

### Core View
- **editor_view.py** (451 lines): Main coordinator class that integrates all components
- **constants.py** (56 lines): Shared constants and enumerations

### Feature Handlers
- **grid_drawer.py** (128 lines): Grid background rendering
- **zoom_controller.py** (206 lines): Zoom and pan control with gesture support
- **mode_manager.py** (112 lines): Editor mode state management
- **joint_handler.py** (132 lines): Joint definition operations
- **motion_path_handler.py** (294 lines): Motion path drawing and management
- **selection_handler.py** (164 lines): Various selection operations
- **simulation_controller.py** (193 lines): Simulation state and animation
- **context_menu_handler.py** (60 lines): Context menu creation

## Benefits of Refactoring

1. **Maintainability**: Each module has a single, clear responsibility
2. **Testability**: Components can be tested in isolation
3. **Readability**: Smaller files are easier to understand and navigate
4. **Extensibility**: New features can be added as new handlers
5. **Reusability**: Components can be reused in other views if needed

## Usage

The main `EditorView` class maintains the same public API as before:

```python
from automataii.gui.views.editor import EditorView

# Create view
view = EditorView(scene, parent_window)

# Use as before
view.set_mode("select")
view.start_define_joint()
view.zoom_to_fit()
```

## Backward Compatibility

A compatibility shim is provided at the old location (`gui/views/editor_view.py`) that imports from the new location and shows a deprecation warning.

## Adding New Features

To add a new feature:

1. Create a new handler class in its own file
2. Initialize it in `EditorView.__init__()`
3. Connect any signals in `EditorView._connect_signals()`
4. Add public methods to `EditorView` that delegate to the handler
5. Update constants.py if needed

## Handler Communication

Handlers communicate through:
- Direct method calls on the view
- Qt signals and slots
- Shared state through the view's properties
- Mode manager for state coordination