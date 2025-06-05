# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automataii is a PyQt5-based desktop application for creating animated mechanical automata from static images. It combines computer vision, mechanical engineering, and interactive design to transform character images into functioning mechanical designs.

## Development Setup and Commands

```bash
# Setup virtual environment
uv venv
source .venv/bin/activate

# Install package in development mode
uv pip install -e ".[dev]"

# Run the application
python -m automataii

# Run tests
pytest

# Run tests with coverage
pytest --cov=automataii

# Type checking (if needed)
mypy automataii

# Linting/formatting
ruff check automataii
ruff format automataii
```

## Architecture Overview

The application follows a modular architecture with these key components:

1. **Image Processing Pipeline** (`animate/`): Handles character segmentation, skeleton extraction, and body part separation using neural networks
2. **Core Models** (`core/`): Data structures and managers for skeletons, mechanisms, and project data
3. **Mechanism Generation** (`generation/`): Creates mechanical linkages (4-bar, cam, gear) from motion paths
4. **Kinematics Engine** (`kinematics/`): IK solver for real-time mechanism simulation
5. **GUI** (`gui/`): PyQt5 interface with tabs for image processing, editing, and design
6. **External Library** (`macanism/`): Embedded mechanism analysis library for kinematic calculations

## Key Workflows

### Adding New Mechanism Types
1. Create new class in `generation/` inheriting from `BaseMechanism`
2. Implement required methods: `generate()`, `simulate()`, `to_blueprint()`
3. Register in `MechanismManager`
4. Add UI controls in `editor_tab.py`

### Modifying Animation Pipeline
1. Animation logic is in `animate/body_parts_animation.py`
2. Body part extraction in `animate/body_parts_extractor.py`
3. Skeleton management in `core/skeleton_manager.py`
4. UI updates in `tabs/image_processing_tab.py`

### Working with IK System
1. Core solver in `kinematics/ik_solver.py`
2. Manager handles multiple mechanisms in `kinematics/ik_manager.py`
3. Custom solvers go in `kinematics/solvers/`

## Important Design Patterns

- **Model-View Pattern**: Core models separate from GUI components
- **Manager Pattern**: Centralized managers for skeletons, mechanisms, and projects
- **Factory Pattern**: Mechanism generation through base class interface
- **Observer Pattern**: Qt signals/slots for UI updates

## Testing Considerations

- Test mechanism generation with known inputs/outputs
- Verify IK solver convergence for standard mechanisms
- Check blueprint SVG output validity
- UI tests focus on state management and signal handling

## Current Development Focus

The project is on the `anim` branch working on:
- Animation system improvements
- Joint repositioning logic
- 2D mechanism simulation
- 4-bar mechanism kinematics
- Mechanism recommendation using Hausdorff distance