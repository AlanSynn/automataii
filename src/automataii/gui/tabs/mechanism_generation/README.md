# Mechanism Generation Module

This module contains the refactored mechanism generation tab components, following a modular architecture with clear separation of concerns.

## Structure

### Core Components

- **`mechanism_generation_tab.py`** (168 lines)
  - Main coordinator that orchestrates all components
  - Handles external signals and tab lifecycle
  - Manages communication between components

- **`state_manager.py`** (135 lines)
  - Centralized state management using dataclass
  - Emits signals for state changes
  - Provides query methods for UI state decisions

- **`control_panels.py`** (247 lines)
  - Reusable UI panels for different controls:
    - `PartSelectionPanel`: Part selection list
    - `MechanismTypePanel`: Mechanism type and parameters
    - `SimulationControlPanel`: Play/stop/reset controls
    - `MechanismListPanel`: Generated mechanisms list

- **`visualization.py`** (191 lines)
  - Mechanism visualization with zoom controls
  - Scene management and visual markers
  - Character part and skeleton visualization

- **`generation_service.py`** (128 lines)
  - Business logic for mechanism generation
  - Parameter validation
  - Mechanism complexity estimation

- **`export_handler.py`** (150 lines)
  - Blueprint export to SVG
  - Data export to JSON/CSV
  - File dialog handling

## Design Patterns

1. **Coordinator Pattern**: The main tab acts as a coordinator, delegating responsibilities to specialized components

2. **State Management**: Centralized state with signals for reactive UI updates

3. **Service Layer**: Business logic separated from UI in service classes

4. **Component Composition**: UI built from reusable, focused components

## Benefits of This Structure

1. **Maintainability**: Each file has a single responsibility and is under 300 lines
2. **Testability**: Components can be tested in isolation
3. **Reusability**: Control panels and services can be reused elsewhere
4. **Scalability**: Easy to add new mechanism types or export formats
5. **Clarity**: Clear separation between UI, business logic, and state

## Adding New Features

### Adding a New Mechanism Type
1. Update `MechanismTypePanel` to include new type in combo box
2. Add parameter controls for the new type
3. Update `MechanismGenerationService` validation and generation logic
4. Add visualization logic in `visualization.py`

### Adding a New Export Format
1. Add new method in `ExportHandler` (e.g., `_export_as_dxf`)
2. Update export UI in main tab if needed
3. Handle format-specific conversions

### Adding New Controls
1. Create new panel class in `control_panels.py`
2. Add to main tab layout in `_create_control_panel`
3. Connect signals in `_connect_signals`