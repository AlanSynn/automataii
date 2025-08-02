# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Management

**This project uses `uv` for package management** - always use `uv` commands instead of pip:

```bash
# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev

# Add new dependencies
uv add package-name

# Run the application
uv run automataii

# Run tests
uv run pytest

# Run linting and formatting
uv run ruff check src/
uv run ruff format src/

# Run type checking
uv run mypy src/automataii
```

## Common Development Commands

Use the provided Makefile for common tasks:

```bash
# Development setup
make dev              # Install development dependencies
make run              # Run the application
make test             # Run tests with pytest
make quality          # Run linting, formatting, and type checking
make build            # Build for current platform

# Individual quality checks
make lint             # Run ruff linter
make format           # Format code with ruff
make type-check       # Run mypy type checking

# Testing variants
make test-verbose     # Run tests with verbose output
make test-coverage    # Run tests with coverage report

# Build for specific platforms
make build-macos      # Build macOS app bundle
make build-windows    # Build Windows executable
make build-linux      # Build Linux executable
```

## Application Architecture

**Automataii** is a sophisticated PyQt6-based desktop application for interactive mechanism design and character animation. Key architectural components:

### Core Architecture

- **Dependency Injection**: Uses `src/automataii/core/container.py` for component lifecycle management
- **Event System**: Event-driven architecture in `src/automataii/core/events/`
- **State Management**: Redux-like state management in `src/automataii/core/state/`
- **Project Format**: ZIP-based `.atii` project files with versioning

### Main Components

- **GUI Layer** (`src/automataii/gui/`): Main window with tabbed interface

  - **Landing Tab**: Project management and welcome screen
  - **Editor Tab**: Character animation and pose editing
  - **Image Processing Tab**: Computer vision and pose estimation
  - **Mechanism Design Tab**: Interactive mechanism design and parametric editing
  - **Options Tab**: Application settings and preferences

- **Core Systems** (`src/automataii/core/`):

  - **Project Manager**: `.atii` project file handling
  - **Skeleton Manager**: Character animation data management
  - **Mechanism Manager**: Mechanical system data management

- **Kinematics Engine** (`src/automataii/kinematics/`):

  - **IK Solver**: Inverse kinematics for character animation
  - **Mechanism Simulator**: Physics-based mechanism simulation
  - **Motion Database**: Pre-computed motion patterns

- **Animation System** (`src/automataii/animate/`):
  - **Pose Estimation**: ONNX-based body pose detection
  - **Character Animation**: From static images to animated characters
  - **Body Parts Extraction**: Automated character segmentation

### Key Features

- **Parametric Editing**: Real-time mechanism parameter manipulation via drag handles
- **4-Bar Linkage Design**: Fully functional parametric editing for 4-bar mechanisms
- **Multi-Platform**: Cross-platform Qt application with native builds
- **Modern Python**: Uses Python 3.13+ with full type annotations

## Development Standards

### Code Quality

- **Type Safety**: Full type annotations required (`mypy` enforced)
- **Code Style**: Ruff for linting and formatting (line length: 100 chars)
- **Testing**: pytest with coverage reporting
- **Documentation**: Comprehensive docstrings for public APIs

### File Organization

- Source code in `src/automataii/`
- Tests in `tests/`
- Build scripts in `scripts/`
- Configuration in `pyproject.toml`

### Key Dependencies

- **GUI**: PyQt6 (with PySide6 compatibility layer)
- **Scientific**: NumPy, SciPy, scikit-learn, scikit-image
- **Computer Vision**: OpenCV, ONNX Runtime
- **Data**: Pydantic, PyYAML, Pillow
- **Visualization**: Matplotlib
