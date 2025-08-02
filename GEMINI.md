# GEMINI.md: Automataii Technical Specification & Engineering Guide

**Author:** Gemini (Principal Software Engineer)
**Version:** 2.0 (Post-Refactoring)
**Date:** 2025-07-06

## 1. Project Vision & Philosophy

This document outlines the technical architecture, standards, and future direction for the Automataii project. Our core philosophy is to build a **robust, modular, and maintainable application** by adhering to modern software engineering principles.

The primary goal of the planned refactoring is to **decouple the core application logic from the graphical user interface (GUI)**. This will enable independent development and testing of business logic, improve scalability, and allow for future technological evolutions, such as the integration of an OpenGL rendering backend.

## 2. Core Architecture: A Decoupled, Layered System

We are adopting a **Layered Architecture** to enforce a strict separation of concerns. Each layer communicates with adjacent layers through well-defined interfaces, primarily using an **Event-Driven Architecture (EDA)** and **Dependency Injection (DI)**.

### Architectural Layers

1.  **App (`app/`):** The main entry point. Its sole responsibility is to initialize the DI container, compose the application layers, and start the UI.
2.  **UI (`ui/`):** The presentation layer (PyQt/PySide). This layer is "dumb" and contains no business logic. It emits events in response to user actions and updates itself based on data received from services.
3.  **Graphics (`graphics/`):** An abstraction layer for rendering. It defines a `BaseRenderer` interface, with concrete implementations like `QtRenderer`. This decouples the UI from specific drawing technologies.
4.  **Services (`services/`):** The application layer. Services orchestrate business logic by interacting with domain modules. They are stateless and handle application-specific use cases (e.g., `ProjectService`, `AnimationService`).
5.  **Domain (`domain/`):** The heart of the application. Contains the core business logic and rules, completely independent of any other layer. This includes modules for `kinematics`, `animation`, `fabrication`, and `segmentation`.
6.  **Core (`core/`):** Foundational, cross-cutting concerns like the DI container, event bus, and state management primitives.
7.  **Models (`models/`):** Pydantic-based data models ensuring data integrity and clear structure throughout the application.

### Key Design Patterns

-   **Dependency Injection (DI):** Managed by the `core.di` container. Components (especially in the UI and service layers) declare their dependencies in their constructors and receive them from the container. This promotes loose coupling and testability.
-   **Event-Driven Architecture (EDA):** The `core.events` EventBus is the central nervous system. Components communicate by publishing and subscribing to events, eliminating direct dependencies.
-   **Observer Pattern:** UI components observe state changes (managed by services or a state store) and update themselves accordingly, often triggered by events.
-   **Strategy Pattern:** Used in areas like rendering (`graphics/`) and mechanism simulation (`kinematics/`) to allow algorithms and behaviors to be swapped out easily.
-   **Facade Pattern:** The `KinematicsSystem` acts as a facade, simplifying the interface to a complex subsystem of IK solvers, animators, and managers.

## 3. Directory Structure

The refactored directory structure is as follows:

```
src/automataii/
├── app/
├── core/
├── domain/
│   ├── animation/
│   ├── fabrication/
│   ├── kinematics/
│   └── segmentation/
├── models/
├── services/
├── graphics/
├── ui/
│   ├── dialogs/
│   ├── tabs/
│   └── widgets/
├── config/
└── utils/
```

## 4. Package & Environment Management (`uv`)

This project uses **`uv`** for high-performance package management and virtual environment creation. **Do not use `pip` or `venv` directly.**

-   **Install all dependencies:** `uv sync --group dev`
-   **Add a new dependency:** `uv add <package-name>`
-   **Run the application:** `uv run automataii`
-   **Run tests:** `uv run pytest`

Refer to the `Makefile` for a convenient set of commands abstracting `uv` usage.

## 5. Git Workflow & Large File Storage (`git lfs`)

-   **Branching:** Follow a standard feature-branching workflow (e.g., GitFlow).
-   **Commits:** Write clear, concise commit messages explaining the *why*, not just the *what*.
-   **Git LFS:** This project uses Git Large File Storage (LFS) to manage large binary files, primarily machine learning models.
    -   **Tracked Files:** `*.onnx`, `*.pth`
    -   **Setup:** Before cloning or pulling, ensure you have Git LFS installed (`git lfs install`).
    -   **Cloning:** `git clone` will automatically download LFS files.
    -   **Adding New Large Files:** If you add a new large file type, track it with `git lfs track "*.new_extension"`.

## 6. Code Quality & Development Standards

Maintaining high code quality is paramount. We enforce these standards through automated checks in our CI pipeline.

-   **Type Safety:** The entire codebase is strictly typed. All new code must include type annotations. We use **`mypy`** for static type checking.
    -   Run check: `make type-check` or `uv run mypy src/automataii`
-   **Linting & Formatting:** We use **`Ruff`** for both linting and code formatting to ensure a consistent style.
    -   Run checks: `make quality`
    -   Run linter: `make lint` or `uv run ruff check src/`
    -   Format code: `make format` or `uv run ruff format src/`
-   **Testing:** **`pytest`** is our testing framework. All new features should be accompanied by unit tests, and critical logic must have coverage.
    -   Run tests: `make test` or `uv run pytest`

## 7. Key Technologies

-   **GUI:** PyQt6 (with a PySide6 compatibility layer)
-   **Scientific Computing:** NumPy, SciPy
-   **Computer Vision / ML:** OpenCV, ONNX Runtime
-   **Data Validation:** Pydantic
-   **Package Management:** uv

## 8. Future Direction

The primary driver for this refactoring is to prepare the application for future growth. The decoupled architecture will allow us to:

-   **Implement an OpenGL Renderer:** By creating a new `OpenGLRenderer` that implements the `BaseRenderer` interface, we can switch the rendering backend with minimal changes to the UI or domain logic.
-   **Develop a Web-Based Viewer:** The decoupled services and domain logic can be exposed via a REST API (e.g., using FastAPI) to power a web-based version of the application.
-   **Improve Test Coverage:** With logic isolated from the UI, we can significantly increase our unit and integration test coverage, leading to a more stable and reliable application.
