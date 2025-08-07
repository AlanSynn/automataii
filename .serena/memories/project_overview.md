# Project Overview - Automataii

## Purpose
Automataii is an advanced interactive mechanism design, simulation, and animation platform. It enables engineers and researchers to design, simulate, and animate mechanical systems with real-time parametric editing capabilities.

## Key Features
- **Mechanism Design**: Interactive design of 4-bar linkages, cam systems, and gear trains
- **Parametric Playground**: Real-time manipulation of mechanism parameters through drag-and-drop handles
- **Kinematic Simulation**: Advanced forward/inverse kinematics with collision detection
- **Animation Pipeline**: Character animation from static drawings with mechanism-driven motion
- **Modular Architecture**: Event-driven, dependency-injected architecture for extensibility

## Tech Stack
- **Language**: Python 3.13+
- **GUI Framework**: PyQt6/PySide6 (with compatibility layer)
- **Scientific Computing**: NumPy, SciPy, scikit-learn, scikit-image
- **Computer Vision**: OpenCV, ONNX Runtime
- **Build System**: PyInstaller for executable generation
- **Dependency Management**: uv (modern Python package manager)

## Current Status
- 4-Bar Linkage parametric editing is **functional** with anchor point manipulation
- Cam systems and gear trains have design capabilities but limited parametric editing
- Animation and simulation systems are complete
- Project uses compressed .atii format for project files