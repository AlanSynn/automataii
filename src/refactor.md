# Automataii Refactoring Plan

## Overview

This document outlines a comprehensive refactoring plan for the Automataii codebase to address:
- Single Responsibility Principle (SRP) violations
- Deep nesting (>4 levels)
- Code readability and maintainability
- Testability improvements
- Modular design for research reusability

## Current Architecture Issues

### 1. SRP Violations

#### MainWindow (main_window.py)
- **Current Issues**:
  - Handles UI initialization, tab management, project management, IK management, mechanism generation
  - Contains business logic that should be in separate services
  - Direct manipulation of multiple managers
- **Responsibilities Mixed**:
  - UI orchestration
  - Business logic coordination
  - Data persistence
  - Animation control
  - File I/O operations

#### EditorTab (editor_tab.py)
- **Current Issues**:
  - ~3000 lines of code
  - Handles UI, animation, simulation, drawing, part management
  - Contains mechanism simulation logic
  - Direct scene manipulation
- **Responsibilities Mixed**:
  - UI management
  - Animation control
  - Path drawing
  - Part manipulation
  - Simulation logic

### 2. Deep Nesting Issues

#### Common Patterns
```python
# Current deep nesting example
if condition1:
    if condition2:
        for item in items:
            if condition3:
                if condition4:
                    # actual logic
```

#### Files with Deep Nesting
- `editor_tab.py`: Multiple 5-6 level deep sections
- `image_processing_tab.py`: Nested callbacks and conditions
- `ik_solver.py`: Complex mathematical calculations with deep conditionals

### 3. Tight Coupling Issues

- Tabs directly access MainWindow attributes
- Circular dependencies between managers
- UI components containing business logic
- Direct scene manipulation from multiple sources

## Refactoring Strategy

### Phase 1: Extract Services and Controllers

#### 1.1 Create Service Layer
```
services/
├── project_service.py       # Project management logic
├── animation_service.py     # Animation control
├── mechanism_service.py     # Mechanism generation
├── skeleton_service.py      # Skeleton operations
├── path_service.py         # Path drawing logic
└── export_service.py       # Blueprint/SVG export
```

#### 1.2 Create Controllers
```
controllers/
├── editor_controller.py     # Coordinates editor operations
├── mechanism_controller.py  # Coordinates mechanism operations
└── project_controller.py    # Coordinates project operations
```

#### 1.3 Extract UI Components
```
gui/components/
├── path_drawing/
│   ├── path_canvas.py
│   ├── path_toolbar.py
│   └── path_controls.py
├── mechanism/
│   ├── mechanism_selector.py
│   ├── mechanism_params.py
│   └── mechanism_preview.py
└── common/
    ├── zoom_toolbar.py
    ├── part_list.py
    └── property_panel.py
```

### Phase 2: Reduce Nesting

#### 2.1 Early Returns Pattern
```python
# Before
def process_item(item):
    if item is not None:
        if item.is_valid():
            if item.has_data():
                # process
                
# After
def process_item(item):
    if item is None:
        return
    if not item.is_valid():
        return
    if not item.has_data():
        return
    # process
```

#### 2.2 Extract Methods
```python
# Before
def complex_operation():
    # 50 lines of nested code
    
# After
def complex_operation():
    data = self._prepare_data()
    result = self._process_data(data)
    self._handle_result(result)
```

#### 2.3 Strategy Pattern for Conditionals
```python
# Before
if mechanism_type == "cam":
    # 20 lines of cam logic
elif mechanism_type == "linkage":
    # 20 lines of linkage logic
    
# After
strategy = MechanismStrategyFactory.create(mechanism_type)
strategy.execute(params)
```

### Phase 3: Improve Testability

#### 3.1 Dependency Injection
```python
# Before
class EditorTab:
    def __init__(self):
        self.ik_manager = IKManager()  # Hard dependency
        
# After
class EditorTab:
    def __init__(self, ik_manager: IKManagerInterface):
        self.ik_manager = ik_manager  # Injected dependency
```

#### 3.2 Extract Pure Functions
```python
# Move pure calculations to separate modules
kinematics/calculations/
├── linkage_math.py      # Pure mathematical functions
├── cam_profile.py       # Cam profile calculations
└── path_analysis.py     # Path analysis algorithms
```

#### 3.3 Create Interfaces
```python
# interfaces/
├── ik_manager_interface.py
├── mechanism_generator_interface.py
└── project_manager_interface.py
```

### Phase 4: Modularize for Research

#### 4.1 Core Modules
```
automataii_core/           # Standalone package
├── kinematics/           # Pure kinematics library
├── mechanisms/           # Mechanism definitions
├── skeleton/            # Skeleton analysis
└── animation/           # Animation algorithms

automataii_gui/           # GUI-specific code
├── widgets/
├── views/
└── controllers/
```

#### 4.2 Plugin Architecture
```python
# plugins/
├── mechanism_plugins/
│   ├── base_mechanism.py
│   ├── cam_mechanism.py
│   └── linkage_mechanism.py
└── export_plugins/
    ├── svg_exporter.py
    └── dxf_exporter.py
```

## Detailed Refactoring Tasks

### Task 1: Extract PathDrawingService
**File**: `services/path_drawing_service.py`
```python
class PathDrawingService:
    """Handles all path drawing operations"""
    
    def start_path(self, start_point: QPointF) -> PathDrawing:
        """Start a new path drawing"""
        
    def add_point(self, path_id: str, point: QPointF) -> None:
        """Add point to existing path"""
        
    def complete_path(self, path_id: str) -> QPainterPath:
        """Complete and return the path"""
```

### Task 2: Simplify EditorTab
**Current**: ~3000 lines
**Target**: <500 lines

1. Extract PathDrawingWidget
2. Extract AnimationControlWidget
3. Extract PartManagementWidget
4. Keep only coordination logic

### Task 3: Create MechanismFactory
```python
class MechanismFactory:
    """Factory for creating mechanisms"""
    
    @staticmethod
    def create_mechanism(
        type: MechanismType,
        params: MechanismParams
    ) -> BaseMechanism:
        """Create mechanism instance"""
```

### Task 4: Extract Animation Pipeline
```python
# animation/pipeline.py
class AnimationPipeline:
    """Manages the animation pipeline"""
    
    def __init__(self):
        self.stages = [
            SkeletonExtractionStage(),
            PartSeparationStage(),
            MotionAnalysisStage(),
            MechanismGenerationStage()
        ]
    
    def process(self, input_data: ImageData) -> AnimationResult:
        """Process through all stages"""
```

### Task 5: Implement Event Bus
```python
# events/event_bus.py
class EventBus:
    """Central event management"""
    
    def publish(self, event: Event) -> None:
        """Publish event to subscribers"""
        
    def subscribe(self, event_type: Type[Event], handler: Callable) -> None:
        """Subscribe to event type"""
```

## Testing Strategy

### Unit Tests Structure
```
tests/
├── unit/
│   ├── services/
│   ├── controllers/
│   └── core/
├── integration/
│   ├── test_animation_pipeline.py
│   └── test_mechanism_generation.py
└── fixtures/
    ├── sample_images/
    └── mock_data/
```

### Test Examples
```python
# tests/unit/services/test_path_drawing_service.py
class TestPathDrawingService:
    def test_start_path_creates_new_drawing(self):
        service = PathDrawingService()
        path = service.start_path(QPointF(0, 0))
        assert path.id is not None
        assert path.points == [QPointF(0, 0)]
```

## Migration Plan

### Phase 1: Preparation (Week 1)
1. Create service layer structure
2. Write interfaces for existing managers
3. Add comprehensive logging
4. Create test harness

### Phase 2: Service Extraction (Week 2-3)
1. Extract PathDrawingService
2. Extract AnimationService
3. Extract MechanismService
4. Update dependencies

### Phase 3: UI Refactoring (Week 4-5)
1. Break down EditorTab
2. Create reusable widgets
3. Implement event bus
4. Remove circular dependencies

### Phase 4: Core Module Extraction (Week 6)
1. Create automataii_core package
2. Move pure logic to core
3. Create plugin interfaces
4. Documentation

## Success Metrics

### Code Quality
- No method >50 lines
- No class >500 lines
- Maximum nesting depth: 3
- Test coverage >80%

### Architecture
- Clear separation of concerns
- No circular dependencies
- Pluggable components
- Research-ready modules

### Maintainability
- Clear naming conventions
- Comprehensive documentation
- Type hints throughout
- Minimal coupling

## Risk Mitigation

### Maintaining Functionality
1. Feature flags for gradual rollout
2. Parallel implementation
3. Comprehensive integration tests
4. A/B testing approach

### Performance Considerations
1. Profile before/after changes
2. Optimize critical paths
3. Lazy loading for heavy operations
4. Caching strategies

## Phase 2: Aggressive Refactoring Plan

### Current State Analysis (Files > 300 lines)

1. **editor_tab.py (2021 lines)** - CRITICAL
2. **ik_manager.py (1691 lines)** - CRITICAL  
3. **mechanism.py (1252 lines)** - HIGH
4. **pose_config.py (1148 lines)** - HIGH
5. **editor_view.py (1047 lines)** - HIGH
6. **main_window.py (1034 lines)** - HIGH

### Detailed Refactoring Tasks

#### Task 1: Refactor editor_tab.py (2021 → <500 lines)

**Current Issues:**
- Mixed UI and business logic
- Multiple responsibilities
- Deep nesting
- Direct scene manipulation

**Refactoring Strategy:**
```
editor_tab.py → 
├── EditorTabCoordinator (main file, <200 lines)
├── components/
│   ├── PartManagementPanel
│   ├── MotionControlPanel
│   ├── MechanismControlPanel
│   └── SimulationControlPanel
├── handlers/
│   ├── PartSelectionHandler
│   ├── PathDrawingHandler
│   └── SimulationHandler
└── state/
    └── EditorState
```

#### Task 2: Refactor ik_manager.py (2192 → <300 lines) ✓ COMPLETED

**Current Issues:**
- Monolithic solver handling all IK operations
- Mixed animation and IK logic
- Complex state management
- Direct UI coupling

**Refactoring Strategy:**
```
kinematics/
├── core/
│   ├── __init__.py
│   ├── ik_state.py (~150 lines) - IK state management
│   ├── joint_config.py (~180 lines) - Joint configuration
│   └── limb_config.py (~120 lines) - Limb configuration
├── solvers/
│   ├── __init__.py
│   ├── base_solver.py (~80 lines) - Abstract base class
│   ├── single_bone_solver.py (~150 lines) - Single bone IK
│   ├── two_bone_solver.py (~200 lines) - Two bone IK
│   └── solver_factory.py (~60 lines) - Factory pattern
├── animation/
│   ├── __init__.py
│   ├── animation_manager.py (~180 lines) - Animation control
│   ├── path_sampler.py (~120 lines) - Path sampling
│   └── interpolator.py (~100 lines) - Animation interpolation
├── visualization/
│   ├── __init__.py
│   ├── skeleton_visualizer.py (~150 lines) - Debug visualization
│   └── joint_visualizer.py (~100 lines) - Joint rendering
├── ik_coordinator.py (~200 lines) - Main coordinator
└── ik_service.py (~180 lines) - High-level service API
```

#### Task 3: Refactor mechanism.py (1252 → <300 lines)

**Current Issues:**
- Multiple mechanism types in one file
- Complex calculations mixed with data structures

**Refactoring Strategy:**
```
mechanism.py →
├── base/
│   ├── BaseMechanism (abstract)
│   └── MechanismRegistry
├── implementations/
│   ├── FourBarMechanism
│   ├── CamMechanism
│   ├── GearMechanism
│   └── LinkageMechanism
└── analysis/
    ├── KinematicAnalyzer
    └── DynamicAnalyzer
```

### New Architecture Patterns

#### 1. Command Pattern for Actions
```python
class Command(ABC):
    @abstractmethod
    def execute(self) -> None:
        pass
    
    @abstractmethod
    def undo(self) -> None:
        pass

class DrawPathCommand(Command):
    def __init__(self, path_service, part_name, points):
        self.path_service = path_service
        self.part_name = part_name
        self.points = points
```

#### 2. Strategy Pattern for Solvers
```python
class IKSolverStrategy(ABC):
    @abstractmethod
    def solve(self, target, constraints) -> Solution:
        pass

class AnalyticalIKSolver(IKSolverStrategy):
    def solve(self, target, constraints):
        # Analytical solution
        pass

class NumericalIKSolver(IKSolverStrategy):
    def solve(self, target, constraints):
        # Numerical solution
        pass
```

#### 3. Observer Pattern with Type Safety
```python
from typing import Generic, TypeVar

T = TypeVar('T')

class TypedObservable(Generic[T]):
    def __init__(self):
        self._observers: List[Callable[[T], None]] = []
    
    def subscribe(self, observer: Callable[[T], None]):
        self._observers.append(observer)
    
    def notify(self, data: T):
        for observer in self._observers:
            observer(data)
```

### Refactoring Principles

1. **Maximum File Size**: 300 lines (hard limit: 500)
2. **Maximum Method Size**: 30 lines (hard limit: 50)
3. **Maximum Class Size**: 150 lines (hard limit: 200)
4. **Maximum Nesting**: 2 levels (hard limit: 3)
5. **Cyclomatic Complexity**: <10 per method

### Implementation Order

1. **Week 1**: editor_tab.py decomposition
2. **Week 2**: ik_manager.py refactoring
3. **Week 3**: mechanism.py modularization
4. **Week 4**: view components extraction
5. **Week 5**: main_window.py simplification
6. **Week 6**: Integration and testing

### Success Metrics

- No file > 500 lines
- Average file size < 200 lines
- Test coverage > 85%
- Cyclomatic complexity < 10
- No circular dependencies

## Next Steps

1. Start with editor_tab.py decomposition
2. Create base classes and interfaces
3. Implement command pattern
4. Extract state management
5. Add comprehensive tests

## Code Examples

### Before: Deep Nesting in EditorTab
```python
def _handle_part_selection_change(self, current, previous):
    if current:
        part_name = current.data(Qt.ItemDataRole.UserRole)
        if part_name:
            self.selected_part_name = part_name
            for name, item in self.current_editor_items.items():
                if name == part_name:
                    item.setSelected(True)
                    if hasattr(item, 'motion_path'):
                        if item.motion_path:
                            if not item.motion_path.isEmpty():
                                self._update_motion_controls(True)
```

### After: Simplified with Service
```python
def _handle_part_selection_change(self, current, previous):
    if not current:
        return
        
    part_name = current.data(Qt.ItemDataRole.UserRole)
    if not part_name:
        return
        
    self.part_service.select_part(part_name)
    self._update_ui_state()
```

### Before: Mixed Responsibilities
```python
class EditorTab(QWidget):
    def generate_mechanism(self):
        # UI logic
        # Business logic
        # Scene manipulation
        # File I/O
        # Animation control
```

### After: Separated Concerns
```python
class EditorTab(QWidget):
    def __init__(self, controller: EditorController):
        self.controller = controller
        
    def generate_mechanism(self):
        params = self._gather_ui_params()
        self.controller.generate_mechanism(params)
```

## Conclusion

This refactoring plan provides a roadmap to transform the Automataii codebase into a maintainable, testable, and modular system. The focus on human readability, proper separation of concerns, and research reusability will make the codebase more valuable for both immediate use and future research applications.