# Automataii `src/automataii` Refactoring Plan

**Author:** Gemini (Principal Software Engineer)
**Date:** 2025-07-06

## 1. Current Architecture Analysis

The current structure of the `src/automataii` directory exhibits a tight coupling between the application's core logic and its GUI implementation (PyQt/PySide). This leads to several challenges:

-   **Strong GUI Dependency:** Core logic, such as in `__main__.py`, directly imports and instantiates Qt components, making it difficult to run or test the logic independently of the GUI.
-   **Mixed Domain Logic:** Key domains like animation, kinematics, and blueprint generation are located at the top level, lacking clear structural separation and encapsulation.
-   **Limited Extensibility & Testability:** The intermingling of UI and logic makes unit testing difficult and increases the risk of unintended side effects when adding new features or modifying the UI.

## 2. Proposed Architecture: Decoupled & Layered

To address these issues, a **Layered Architecture** is proposed. This will separate concerns, improve modularity, and facilitate future maintenance and expansion (e.g., migrating to an OpenGL renderer).

The new structure will be organized into the following distinct layers:

1.  **Core:** Foundational components like the DI container, event bus, state management, and project file handling.
2.  **Domain:** The core business logic, completely independent of the UI. This includes kinematics, animation, segmentation, and fabrication logic.
3.  **Models:** Pydantic-based data models for clear, validated data structures.
4.  **Services:** An application layer that orchestrates domain logic.
5.  **Graphics:** An abstraction layer for rendering, decoupling the logic from specific rendering backends like Qt or OpenGL.
6.  **UI:** The user interface layer (PyQt/PySide), responsible only for presentation and user interaction.
7.  **App:** The main application entry point, responsible for initializing the DI container and starting the application.

### New Directory Structure

```
src/automataii/
├── app/                  # 1. Application Entrypoints
│   ├── __init__.py
│   └── main.py             # New __main__.py: DI setup, UI startup.
│
├── core/                 # 2. Core Infrastructure
│   ├── __init__.py
│   ├── di.py               # Dependency Injection (from container.py)
│   ├── events.py           # EventBus and base events
│   ├── project.py          # Project file management
│   └── state.py            # State management
│
├── domain/               # 3. Domain Logic (Business Logic)
│   ├── __init__.py
│   ├── animation/          # (from animate/)
│   ├── fabrication/        # (from generation/)
│   ├── kinematics/         # (from kinematics/)
│   └── segmentation/       # (from carsegnet/)
│
├── models/               # 4. Data Models
│   ├── __init__.py
│   ├── pydantic.py         # (from models_pydantic.py)
│   ├── project.py          # Project-related data classes
│   └── skeleton.py         # (from models_skeleton.py)
│
├── services/             # 5. Application Services
│   ├── __init__.py
│   ├── animation_service.py
│   ├── inference_service.py
│   └── project_service.py
│
├── graphics/             # 6. Graphics Abstraction Layer
│   ├── __init__.py
│   ├── base_renderer.py    # Abstract renderer interface
│   ├── qt_renderer.py      # QGraphicsItem-based implementation
│   └── opengl_renderer.py  # (Future) OpenGL implementation
│
├── ui/                   # 7. User Interface (PyQt/PySide)
│   ├── __init__.py
│   ├── main_window.py      # (from gui/main_window.py)
│   ├── dialogs/
│   ├── tabs/
│   └── widgets/
│
├── config/               # 8. Configuration
│   └── z_indices.py
│
└── utils/                # 9. Utilities
    ├── __init__.py
    └── ...
```

## 3. Phased Refactoring Plan

### Phase 1: Foundational Restructuring

1.  **Create New Directories:** Establish the new directory structure as outlined above.
2.  **Move Files:** Relocate existing files and folders to their new locations.
    -   `animate/` -> `domain/animation/`
    -   `carsegnet/` -> `domain/segmentation/`
    -   `generation/` -> `domain/fabrication/`
    -   `kinematics/` -> `domain/kinematics/`
    -   `core/` files -> `core/` and `models/`
    -   `gui/` -> `ui/`
    -   `__main__.py` -> `app/main.py`
3.  **Fix Imports:** Update all `import` statements across the codebase to reflect the new file locations. The application should run identically to its pre-refactoring state after this step.

### Phase 2: Decoupling Logic from UI

This is the most critical phase.

1.  **Introduce Service Layer:**
    -   Create service classes (e.g., `ProjectService`, `AnimationService`) in the `services/` directory.
    -   These services will encapsulate the application's business logic, using the `domain` modules.
2.  **Apply Dependency Injection (DI):**
    -   Configure the DI container in `app/main.py` to manage service instances (mostly as singletons).
    -   Modify the constructors of UI components (`MainWindow`, tabs, dialogs) to receive services as dependencies instead of creating them.
3.  **Strengthen Event-Driven Communication:**
    -   UI components will emit events via the `EventBus` in response to user actions.
    -   Services will subscribe to these events, execute the necessary logic, and publish result events.
    -   UI components will subscribe to the result events to update the display.
    -   **Outcome:** The UI becomes a thin layer focused purely on presentation, decoupled from the application's state and business rules.

### Phase 3: Graphics Abstraction

This phase prepares the application for future UI technology changes, such as adopting OpenGL.

1.  **Define Renderer Interface:** Create an abstract `BaseRenderer` class in `graphics/base_renderer.py` with methods like `draw_part()`, `draw_skeleton()`, etc.
2.  **Implement QtRenderer:** Create a concrete `QtRenderer` in `graphics/qt_renderer.py` that implements the `BaseRenderer` interface using `QGraphicsItem`s.
3.  **Inject Renderer into UI:** Modify UI components that perform rendering (e.g., `EditorView`) to depend on the `BaseRenderer` interface. The DI container will inject the `QtRenderer` instance.
    -   **Outcome:** UI components will call `self.renderer.draw_part()` instead of `self.scene.addItem(...)`, making the rendering backend swappable.

### Phase 4: Tab-Specific Refactoring Strategy

The core principle for refactoring the UI tabs is to transform them into pure **View** components that are driven by state and services, rather than containing complex logic themselves.

#### Core Principles for Tab Refactoring

1.  **Dumb Views, Smart Services:** Tabs will be made "dumb." They will not contain business logic. Their sole responsibilities are to display data provided by services and to capture user input, which is then relayed to services via method calls or events.
2.  **Dependency Injection:** Each tab will receive its necessary dependencies (e.g., `ProjectService`, `AnimationService`, `BaseRenderer`) through its constructor. Tabs will no longer instantiate their own dependencies.
3.  **Event-Driven Communication:** Direct communication between tabs will be eliminated. Instead, tabs will use a central `EventBus` to announce user actions or state changes. Other components (services or other tabs) will subscribe to these events to react accordingly.

#### Role Transformation of Each Tab

-   **`LandingTab` (Welcome):**
    -   **Current:** Directly communicates with `MainWindow` to switch tabs and pass image paths.
    -   **New Role:** When a user selects an example image, it will emit an `ImageSelectedEvent(path)` to the `EventBus`. A dedicated service or `MainWindow` will listen for this event and orchestrate the subsequent actions (switching tabs, loading data), completely decoupling `LandingTab` from other UI components.

-   **`ImageProcessingTab` (Character Selection):**
    -   **Current:** Handles heavy tasks like image loading, ONNX model inference, and part extraction directly.
    -   **New Role:** Becomes a UI for the image processing workflow. Clicking "Process Image" will call a method on an `InferenceService`. The service will run the process asynchronously, preventing the UI from freezing. Upon completion, the service will emit a `ProcessingFinishedEvent` with the results, which the tab will then use to update its display.

-   **`EditorTab` (Path Editor):**
    -   **Current:** Manages part items, motion path data, and IK simulation logic.
    -   **New Role:** Becomes a pure visual editor.
        -   When a user draws a motion path, the tab emits a `MotionPathDefinedEvent`.
        -   When the user clicks "Play," it calls `AnimationService.play()`.
        -   It subscribes to `PoseUpdatedEvent` from the `AnimationService` and uses the injected `Renderer` to update the positions of parts and skeleton visuals. It will no longer contain any IK logic or animation timers.

-   **`MechanismDesignTab` (Mechanism Design):**
    -   **Current:** Contains logic for mechanism recommendation, simulation, and visualization.
    -   **New Role:** Similar to `EditorTab`, it becomes a visual editor for mechanisms.
        -   "Get Mechanism" button will call `MechanismService.get_recommendations()`.
        -   It will subscribe to `PoseUpdatedEvent` to animate the character and the selected mechanism together, using the injected `Renderer`. All complex mathematical models and simulations will reside in the `domain/kinematics` and `services` layers.

-   **`OptionsTab` (Options):**
    -   **Current:** Directly calls methods on `MainWindow` to change settings.
    -   **New Role:** Will emit events for setting changes, such as `ThemeChangedEvent("dark")` or `AnimationSpeedChangedEvent(2.5)`. `MainWindow` and other relevant services will subscribe to these events to apply the changes. The `OptionsTab` will have no knowledge of which components consume its settings.

### Phase 5: Finalization and Verification

1.  **Finalize Entry Point:** Refine `app/main.py` to cleanly orchestrate the application startup: DI container setup, service registration, `MainWindow` instantiation, and service injection.
2.  **Add Unit Tests:** With the logic now decoupled, write unit tests for the `services` and `domain` layers to ensure correctness and stability.
3.  **Update Documentation:** Add a brief overview of the new architecture to the project's documentation.
