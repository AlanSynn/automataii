# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automataii is a PyQt6-based desktop application for creating animated mechanical automata from static images. It combines computer vision, mechanical engineering, and interactive design to transform character images into functioning mechanical designs.

## Development Setup and Commands

```bash
# Setup virtual environment
uv venv
source .venv/bin/activate

# Install package in development mode
uv pip install -e ".[dev]"

# Run the application
python -m automataii

# Run with debug mode
python -m automataii --debug

# Run tests
pytest

# Run tests with coverage
pytest --cov=automataii

# Run single test
pytest tests/test_specific_file.py::test_function_name

# Type checking
mypy automataii

# Linting/formatting
ruff check automataii
ruff format automataii
```

## Architecture Overview

The application follows a modular PyQt6 architecture with these key components:

1. **Core Models & Managers** (`core/`):
   - Pydantic v1 models for data validation (`models_pydantic.py`)
   - Skeleton management system with hierarchy support
   - Project data management with file I/O
   - Mechanism manager for kinematic systems

2. **GUI System** (`gui/`):
   - Main window with tabbed interface (`main_window/`)
   - Five main tabs: Landing, Image Processing, Editor, Mechanism Generation, Options
   - Custom graphics items for skeleton/part rendering
   - Modular view system with specialized views for different tasks

3. **Image Processing Pipeline** (`processing/`):
   - Neural network-based character segmentation
   - Skeleton extraction and body part separation
   - Animation system with ARAP deformation
   - Template-based part definitions

4. **Kinematics Engine** (`kinematics/`):
   - IK solver with multiple solver implementations
   - Animation manager for smooth motion interpolation
   - Mechanism simulation and path analysis

5. **Mechanism Generation** (`generation/`):
   - Factory pattern for creating mechanism types (4-bar linkage, cam, gear)
   - Blueprint generation for manufacturing
   - Integration with external mechanism analysis library

## Code Quality Standards

- Use Python 3.9+ features and type hints
- Follow Google-style docstrings
- Prefer f-strings for string formatting
- Use dataclasses and Pydantic v1 for data structures
- Implement robust error handling for external dependencies
- Use logging instead of print statements
- Keep files under 500 lines
- Maintain hierarchical subdirectories
- Use ruff for linting and formatting

## Key Workflows

### Adding New Mechanism Types
1. Create new class in `generation/` inheriting from `BaseMechanism`
2. Implement required methods: `generate()`, `simulate()`, `to_blueprint()`
3. Register in `MechanismManager`
4. Add UI controls in mechanism generation tab

### Working with PyQt6 Components
- All UI components use PyQt6 (with PyQt5 fallback in some areas)
- Main window uses tab-based architecture with coordinator pattern
- Custom graphics items inherit from QGraphicsItem
- Signal/slot connections for UI updates
- High DPI support enabled by default

### Modifying Animation System
1. Body part extraction logic in `processing/animation/`
2. Skeleton management in `core/skeleton/` with new modular system
3. Animation coordination through `gui/main_window/animation_coordinator.py`
4. Template definitions in `processing/animation/part_definitions.py`

### Working with Project Data
- Projects use `ProjectFileModel` (Pydantic) for validation
- File I/O handled by `project_data_manager.py`
- Support for project loading/saving with proper error handling
- Image and skeleton data persistence

## Testing Strategy

- Use pytest for all tests with minimum 80% coverage target
- Test mechanism generation with known inputs/outputs
- Verify IK solver convergence for standard mechanisms
- UI tests focus on state management and signal handling
- Integration tests for end-to-end workflows

## Current Development Status

Currently on `mech_tab` branch focusing on:
- Mechanism generation tab implementation
- Enhanced mechanism preview and simulation
- Integration of kinematic analysis tools
- Path generation and optimization features

## Important Notes

- The application supports both PyQt6 and PySide6 with automatic fallback
- Uses `uv` for package management instead of pip
- Embedded `macanism` library provides additional mechanism analysis
- Debug mode available via `--debug` flag for development
- Project follows Korean documentation with English code (per developer preferences)

## Branching Workflow

When developing new features, we use git worktree to work on branches:
git worktree add .worktree/branch-name -b feat/branch-name # Create a new branch and set up the worktree
cd .worktree/branch-name # Move to the worktree and start working