# Automataii Project Structure

## Current Architecture (Post-Refactoring Stage 2)

The project has undergone a major refactoring to achieve better separation of concerns:

```
src/automataii/
├── app/                    # Application entry points
│   ├── __init__.py
│   └── main.py            # Main entry point with DI setup
│
├── core/                   # Core infrastructure
│   ├── base.py            # Base classes (Event, Action, State)
│   ├── decorators.py      # Event decorators
│   ├── event_bus.py       # Event system
│   ├── middleware.py      # Redux middleware
│   ├── selectors.py       # State selectors
│   ├── store.py           # Redux store
│   └── types.py           # Core type definitions
│
├── domain/                 # Business logic (UI-independent)
│   ├── animation/         # Animation logic (from animate/)
│   ├── fabrication/       # Blueprint/mechanism generation (from generation/)
│   ├── kinematics/        # Kinematics simulation (from kinematics/)
│   └── segmentation/      # Image segmentation (from carsegnet/)
│
├── models/                 # Data models
│   ├── pydantic.py        # Pydantic validation models
│   ├── runtime.py         # Runtime data models
│   └── skeleton.py        # Skeleton-specific models
│
├── services/              # Application services
│   ├── blueprint_manager.py
│   ├── di.py             # Dependency injection container
│   ├── inference_service.py
│   ├── mechanism_manager.py
│   ├── project_data_manager.py
│   └── skeleton_manager.py
│
├── ui/                    # User interface (PyQt6)
│   ├── actions/          # UI action management
│   ├── dialogs/          # Dialog windows
│   ├── fonts/            # UI fonts
│   ├── graphics_items/   # Qt graphics items
│   ├── main_window.py    # Main application window
│   ├── tabs/             # Tab implementations
│   │   ├── base/        # Base tab classes
│   │   ├── editor/      # Character editor tab
│   │   ├── mechanism_design/  # Mechanism design tab
│   │   └── ...          # Other tabs
│   ├── views/           # Qt view components
│   └── widgets/         # Reusable widgets
│
├── graphics/             # Graphics abstraction layer
├── config/              # Configuration files
├── utils/               # Utility functions
└── __init__.py
```

## Key Architectural Points

1. **Separation of Concerns**: Domain logic is completely separated from UI
2. **Dependency Injection**: Services are managed through DI container
3. **Event-Driven**: Communication between components via event bus
4. **State Management**: Redux-like pattern for application state
5. **Layered Architecture**: Clear separation between layers

## Migration Status
The project is currently on the `refactor-stage2` branch, which represents a significant architectural refactoring from the original structure.