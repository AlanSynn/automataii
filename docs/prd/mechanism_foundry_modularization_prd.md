# Mechanism Foundry Modularization PRD

**Author:** Alan Synn · [alan@alansynn.com](mailto:alan@alansynn.com)  
**Status:** Proposed (2025-10-20)  
**Related:** `docs/prd/god_class_refactor_prd.md`, `docs/adr/000-architecture-intent.md`

---

## 1. Problem / Goal

**Problem:**
- `enhanced_macanism_tab.py` is **3771 LOC** (violates 500 LOC policy by 7.5x)
- Mechanism rendering logic embedded in UI layer (no reusability)
- Four mechanism types (four_bar, slider_crank, cam_follower, gear_train) duplicated across codebase
- Physics calculations, force visualization, and safety zones mixed with UI event handling
- Cannot swap rendering backends (QPainter → OpenGL/shaders)
- Impossible to unit test mechanism logic without Qt
- No shared rendering between Foundry tab and Design tab

**Goal:**
Create modular `automataii/mechanisms/` architecture extracting mechanism domain logic, rendering, and catalog into reusable, testable modules.

**Quantitative Targets:**
- Reduce `enhanced_macanism_tab.py` from 3771 → ≤800 LOC (79% reduction)
- Each mechanism module ≤300 LOC
- Rendering abstraction ≤200 LOC per implementation
- 100% visual parity (pixel-perfect comparison)
- Zero performance regression (maintain 60fps)
- ≥85% test coverage for extracted modules
- Mechanism computation ≤5ms per frame

---

## 2. In-Scope / Out-of-Scope

### In-Scope
1. **Module Structure:**
   - Create `src/automataii/mechanisms/` directory with submodules
   - Extract 4 mechanism types: `linkages/`, `cams/`, `cranks/`, `gears/`
   
2. **Domain Layer:**
   - Pure kinematics computation (joint positions, velocities, forces)
   - Physics validation (Grashof criterion, collision detection)
   - Safety evaluation logic
   - Parameter validation

3. **Rendering Layer:**
   - Abstract `MechanismRenderer` protocol
   - QPainter implementation (current)
   - Interface for future OpenGL/shader renderers

4. **Catalog Layer:**
   - Central mechanism registry
   - Metadata management
   - Factory pattern for instantiation

5. **Integration:**
   - Update Foundry tab to use new modules
   - Prepare Design tab for shared rendering
   - Maintain all existing features (forces, trails, handles, safety zones)

### Out-of-Scope
- Actual OpenGL/shader implementation (prepare interface only)
- New mechanism types beyond existing four
- Blueprint export changes
- IK/kinematics service modifications
- UI layout/styling changes
- Performance optimizations beyond current baseline

---

## 3. Success Metrics & Validation

### Structural Metrics
- `enhanced_macanism_tab.py`: 3771 → ≤800 LOC
- New mechanism modules: ≤300 LOC each
- Cyclomatic complexity: ≤10 per method
- Module coupling: Low (only through protocols)
- Test coverage: ≥85% for mechanisms, ≥90% for core protocols

### Quality Metrics
- **Visual Regression:** Zero pixel diff for all 4 mechanism types
- **Performance:** Maintain 60fps animation (≤16.67ms per frame)
- **Computation Latency:** 
  - Mechanism state compute: ≤5ms
  - Rendering: ≤10ms
  - Total frame budget: ≤16ms
- **Memory:** ≤1MB per mechanism instance

### Validation Methods
1. Snapshot tests: SVG output comparison before/after
2. Screenshot diffing: Pixel-perfect visual regression
3. Telemetry comparison: Latency p50/p95/p99 validation
4. Property-based tests: Kinematic constraints preserved
5. Integration tests: Full pipeline from UI → compute → render

---

## 4. Architecture Overview

### Directory Structure
```
src/automataii/mechanisms/
├── __init__.py                    # Public exports
├── catalog/
│   ├── __init__.py
│   ├── registry.py               # MechanismRegistry singleton
│   └── metadata.py               # MechanismMetadata dataclass
├── core/
│   ├── __init__.py
│   ├── protocols.py              # Mechanism, MechanismRenderer protocols
│   ├── state.py                  # MechanismState, ForceVector dataclasses
│   └── validation.py             # Parameter validation utilities
├── linkages/
│   ├── __init__.py
│   ├── four_bar.py               # FourBarMechanism (kinematics + physics)
│   ├── slider_crank.py           # SliderCrankMechanism
│   └── renderer.py               # LinkageRenderer (QPainter impl)
├── cams/
│   ├── __init__.py
│   ├── cam_follower.py           # CamFollowerMechanism
│   └── renderer.py               # CamRenderer (QPainter impl)
├── gears/
│   ├── __init__.py
│   ├── gear_train.py             # GearTrainMechanism
│   └── renderer.py               # GearRenderer (QPainter impl)
└── utils/
    ├── __init__.py
    ├── geometry.py               # Shared geometry utilities
    └── safety.py                 # Safety zone rendering helpers
```

### Layering & Dependencies
```
UI Layer (enhanced_macanism_tab.py)
    ↓
mechanisms/catalog/registry.py (discovery)
    ↓
mechanisms/{type}/*.py (domain logic)
    ↓
mechanisms/core/protocols.py (abstractions)

Rendering Path:
UI → Mechanism.compute_state() → MechanismState → Renderer.render(state, scene)
```

### Key Abstractions

#### 1. Core Protocols (`mechanisms/core/protocols.py`)
```python
@dataclass(frozen=True)
class MechanismState:
    """Computed mechanism state at a point in time"""
    positions: dict[str, tuple[float, float]]  # joint positions
    velocities: dict[str, tuple[float, float]] | None
    forces: dict[str, ForceVector] | None
    safety_status: SafetyStatus
    metadata: dict[str, Any]

class Mechanism(Protocol):
    """Base protocol for all mechanisms"""
    @property
    def mechanism_type(self) -> str: ...
    
    @property
    def required_parameters(self) -> frozenset[str]: ...
    
    def compute_state(
        self, 
        parameters: Mapping[str, float],
        input_angle: float,
    ) -> MechanismState: ...
    
    def validate_parameters(self, parameters: Mapping[str, float]) -> None: ...

class MechanismRenderer(Protocol):
    """Protocol for rendering backends"""
    def render(
        self,
        state: MechanismState,
        scene: QGraphicsScene,
        config: RenderConfig,
    ) -> list[QGraphicsItem]: ...
```

#### 2. Registry (`mechanisms/catalog/registry.py`)
```python
class MechanismRegistry:
    """Central registry for mechanism types"""
    _instance: MechanismRegistry | None = None
    _mechanisms: dict[str, type[Mechanism]]
    
    @classmethod
    def get_instance(cls) -> MechanismRegistry: ...
    
    def register(self, mechanism_type: str, cls: type[Mechanism]) -> None: ...
    def get(self, mechanism_type: str) -> Mechanism: ...
    def list_types(self) -> list[str]: ...
```

### Data/Control Flow
1. **Initialization:** `MechanismRegistry` loads all mechanism types
2. **Selection:** UI queries registry for mechanism by type
3. **Computation:** `mechanism.compute_state(params, angle)` → `MechanismState`
4. **Rendering:** `renderer.render(state, scene, config)` → visual output
5. **Interaction:** UI events update parameters → recompute → re-render

---

## 5. Migration Strategy (Phased Approach)

### Phase 1: Foundation (Week 1)
**Goal:** Set up architecture, no UI changes

**Tasks:**
1. Create directory structure
2. Define core protocols (`Mechanism`, `MechanismRenderer`)
3. Define `MechanismState`, `ForceVector`, `SafetyStatus` dataclasses
4. Create `MechanismRegistry` with empty implementations
5. Add comprehensive unit tests for protocols

**DoD:**
- All tests green
- Zero UI changes
- Documentation complete
- Code review approved

---

### Phase 2: Four-Bar Extraction (Week 2)
**Goal:** Extract first mechanism as pilot

**Tasks:**
1. Extract four-bar kinematics from lines 379-717
   - `_solve_four_bar_output_angle_fast()` → `FourBarMechanism.compute_state()`
   - `_evaluate_four_bar_safety()` → `FourBarMechanism._evaluate_safety()`
2. Extract four-bar rendering from lines 379-456
   - `_draw_four_bar_mechanism_optimized()` → `LinkageRenderer.render_four_bar()`
   - `_draw_link_optimized()`, `_draw_joint_optimized()` → renderer helpers
3. Extract force calculation from lines 449
   - `_calculate_four_bar_forces_optimized()` → physics module
4. Create `FourBarMechanism` class implementing `Mechanism` protocol
5. Create `LinkageRenderer` implementing `MechanismRenderer` protocol
6. Register four-bar in registry
7. Add comprehensive tests:
   - Unit: kinematics accuracy, Grashof validation
   - Integration: compute → render pipeline
   - Regression: snapshot tests for visual output

**Feature Flag:** `MECHANISM_MODULAR_FOUR_BAR` (default: off)

**DoD:**
- Four-bar extractedfrom UI file
- Tests passing (≥85% coverage)
- Visual regression tests passing (pixel-perfect)
- Performance baseline captured
- Feature flag allows toggle

---

### Phase 3: Foundry Tab Integration (Week 3)
**Goal:** Wire new modules into UI

**Tasks:**
1. Update `InteractiveMechanismWidget` to use registry:
   ```python
   mechanism = registry.get(self.mechanism_type)
   state = mechanism.compute_state(self.mechanism_params, self.animation_angle)
   renderer = LinkageRenderer()
   renderer.render(state, self.scene, self.render_config)
   ```
2. Add telemetry spans:
   - `mechanisms.compute` (type, duration_ms, param_count)
   - `mechanisms.render` (type, duration_ms, item_count)
3. Run dual-path validation:
   - Old path: existing inline code
   - New path: registry + renderer
   - Compare outputs, log discrepancies
4. Update parameter change handlers to use new API
5. Update safety zone rendering to use `state.safety_status`

**Validation:**
- Side-by-side comparison: old vs new rendering
- Telemetry confirms zero performance regression
- All interactive features work (handles, animation, trails)

**DoD:**
- Foundry tab uses registry for four-bar
- Old code path still available via flag
- Telemetry integrated
- Zero visual/behavioral changes observed
- Performance metrics within 5% of baseline

---

### Phase 4: Remaining Mechanisms (Week 4-5)
**Goal:** Extract slider_crank, cam_follower, gear_train

**Tasks (per mechanism):**
1. Extract kinematics computation
2. Extract rendering logic
3. Extract force calculations
4. Extract safety evaluation
5. Create mechanism class
6. Create/update renderer
7. Register in catalog
8. Add tests (unit + integration + regression)

**Mechanism-Specific Extraction:**

- **Slider-Crank** (lines 1324-1426):
  - Kinematics: crank motion + connecting rod + slider position
  - Forces: gas pressure, rod tension, crank torque
  - Safety: dead center detection, rod length validation

- **Cam-Follower** (lines 1427-1613):
  - Kinematics: egg-shaped cam profile + follower displacement
  - Forces: spring force, contact force, inertia
  - Rendering: cam profile path, follower guide rails

- **Gear-Train** (lines 1800-1884):
  - Kinematics: pitch circle rotation, gear ratio
  - Rendering: gear teeth, mesh point, rotation arrows
  - Handles: gear center dragging (parametric editing)

**DoD (per mechanism):**
- Mechanism extracted and registered
- Tests passing (≥85% coverage)
- Visual regression tests passing
- Performance within budget

---

### Phase 5: Shared Utilities & Cleanup (Week 6)
**Goal:** Extract common code, remove duplication

**Tasks:**
1. Extract shared geometry utilities:
   - `_draw_link_optimized()` → `utils/geometry.py`
   - `_draw_joint_optimized()` → `utils/geometry.py`
2. Extract safety zone rendering:
   - `_draw_safety_zones()` → `utils/safety.py`
   - `_add_safety_zone_labels()` → `utils/safety.py`
3. Extract force visualization:
   - `_draw_force_vectors_optimized()` → `utils/forces.py`
4. Update all renderers to use shared utilities
5. Remove legacy code from `enhanced_macanism_tab.py`
6. Final LOC verification: ≤800 LOC remaining

**DoD:**
- Shared utilities extracted
- Zero code duplication across mechanism modules
- `enhanced_macanism_tab.py` ≤800 LOC
- All tests passing
- Documentation updated

---

### Phase 6: Design Tab Integration (Week 7)
**Goal:** Enable shared rendering in Design tab

**Tasks:**
1. Update `mechanism_design_tab.py` to use registry
2. Share renderers between Foundry and Design tabs
3. Add telemetry for Design tab usage
4. Validate consistency across tabs

**DoD:**
- Design tab uses shared mechanism modules
- Consistent rendering across tabs
- No visual regressions

---

### Phase 7: Final Validation & Cleanup (Week 8)
**Goal:** Remove feature flags, finalize migration

**Tasks:**
1. Run full regression suite (all mechanism types)
2. Performance validation across all mechanisms
3. Remove feature flags (default new path)
4. Archive legacy code
5. Update documentation:
   - ADR documenting migration
   - Module READMEs
   - API documentation
6. Team knowledge share session

**DoD:**
- All feature flags removed
- Legacy code archived
- Documentation complete
- Team trained on new architecture

---

## 6. Public API

### Registry API
```python
from automataii.mechanisms import get_mechanism, list_mechanism_types

# Get mechanism
mechanism = get_mechanism("four_bar")

# List available types
types = list_mechanism_types()  # ["four_bar", "slider_crank", ...]
```

### Mechanism API
```python
# Compute state
state = mechanism.compute_state(
    parameters={"ground_link": 150.0, "input_link": 40.0, ...},
    input_angle=45.0  # degrees
)

# Access computed data
positions = state.positions  # {"O1": (x, y), "A": (x, y), ...}
forces = state.forces        # {"reaction_O1": ForceVector(...), ...}
safety = state.safety_status # SafetyStatus(level="safe", message="...")
```

### Renderer API
```python
from automataii.mechanisms.linkages import LinkageRenderer

renderer = LinkageRenderer()
items = renderer.render(
    state=mechanism_state,
    scene=qgraphics_scene,
    config=RenderConfig(
        show_forces=True,
        show_safety_zones=True,
        show_labels=True,
        color_scheme="default"
    )
)
```

---

## 7. Dependencies

### Internal
- `application/mechanism_foundry/` → becomes thin wrapper over `mechanisms/`
- `generation/linkage.py` (572 LOC) → deprecated by `mechanisms/linkages/`
- `generation/cam.py` (378 LOC) → deprecated by `mechanisms/cams/`
- `generation/gear.py` (348 LOC) → deprecated by `mechanisms/gears/`
- `ui/tabs/mechanism_foundry/` → consumes `mechanisms/` API

### External
- PyQt6 (QGraphicsScene, QPainter) - isolated in renderer layer only
- NumPy - for matrix operations in kinematics
- Dataclasses/Pydantic - for state management
- Math - for trigonometry and geometry

### Dependency Direction
```
UI → mechanisms/catalog → mechanisms/{type} → mechanisms/core
                                     ↓
                          mechanisms/{type}/renderer → mechanisms/core/protocols
```

---

## 8. Test Strategy

### Unit Tests
**Target: ≥85% coverage**

1. **Mechanism Computation:**
   - Four-bar: Grashof validation, output angle accuracy, branch switching
   - Slider-crank: Dead center handling, rod length validation
   - Cam-follower: Profile generation, follower displacement
   - Gear-train: Gear ratio, pitch circle tangency

2. **Parameter Validation:**
   - Missing required parameters
   - Invalid ranges (negative lengths, etc.)
   - Edge cases (zero lengths, extreme ratios)

3. **Safety Evaluation:**
   - Grashof criterion violations
   - Reach limit violations
   - Transmission angle thresholds
   - Dead center detection

### Integration Tests
**Target: 100% for critical paths**

1. **Compute → Render Pipeline:**
   - Mechanism.compute_state() → Renderer.render()
   - Verify graphics items created correctly
   - Verify Z-ordering, colors, labels

2. **Registry Operations:**
   - Registration and retrieval
   - Error handling for unknown types
   - Factory instantiation

### Regression Tests
**Target: Pixel-perfect parity**

1. **Snapshot Tests:**
   - SVG export comparison before/after
   - Capture mechanism state at keyframes (0°, 45°, 90°, 180°, 270°)
   - Compare joint positions, forces, safety status

2. **Visual Regression:**
   - Screenshot comparison using Qt offscreen rendering
   - Pixel diff threshold: 0.1% (allow minor anti-aliasing differences)

3. **Performance Regression:**
   - Telemetry comparison: p50/p95/p99 latencies
   - Frame rate monitoring during animation
   - Memory footprint validation

### Property-Based Tests
**Target: Validate invariants**

1. **Kinematic Constraints:**
   - Four-bar: Coupler length = distance(A, B) within tolerance
   - Slider-crank: Slider Y-position = 0 (horizontal motion only)
   - Gear-train: Angular velocity ratio = teeth ratio

2. **Energy Conservation:**
   - Total force sum = zero (equilibrium)
   - Torque balance at joints

---

## 9. Observability / Telemetry

### Telemetry Spans
```python
# Mechanism computation
telemetry_span(
    "mechanisms.compute",
    mechanism_type="four_bar",
    param_count=5,
    duration_ms=2.3,
    status="success"
)

# Rendering
telemetry_span(
    "mechanisms.render",
    mechanism_type="four_bar",
    renderer="qpainter",
    item_count=24,
    duration_ms=8.1,
    status="success"
)

# Safety evaluation
telemetry_span(
    "mechanisms.safety.evaluate",
    mechanism_type="four_bar",
    safety_level="warning",
    duration_ms=0.5
)
```

### Logging
- **INFO:** Mechanism registration, safety status changes
- **WARNING:** Parameter validation failures, near-limit conditions
- **ERROR:** Computation failures, rendering errors

### Metrics Dashboard
- Computation latency by mechanism type (p50/p95/p99)
- Render latency by renderer type
- Safety violation frequency
- Frame rate distribution (target: 100% frames ≥60fps)

---

## 10. Performance / Resource Constraints

### Hard Constraints
- **Frame Budget:** ≤16.67ms per frame (60fps)
  - Compute: ≤5ms
  - Render: ≤10ms
  - Overhead: ≤1.67ms
- **Memory:** ≤1MB per mechanism instance
- **Startup:** Mechanism registration ≤100ms

### Optimization Strategies
1. **Caching:**
   - Cache computed states for unchanged parameters
   - Reuse QGraphicsItems when possible (avoid recreating)

2. **Lazy Initialization:**
   - Registry loads mechanisms on-demand
   - Renderer resources allocated lazily

3. **Frame Skipping:**
   - Skip expensive operations (labels, safety zones) on alternate frames
   - Already implemented in current code (line 306)

4. **Profiling:**
   - Profile each mechanism's compute and render
   - Identify and optimize hot paths
   - Use Qt's built-in profiling tools

---

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| **Visual regression during extraction** | High | Medium | Pixel-perfect snapshot tests, side-by-side comparison UI, feature flags for rollback |
| **Performance degradation from abstraction** | High | Low | Profiling at each phase, inline critical paths, keep zero-cost abstractions |
| **Breaking parametric handles** | High | Medium | Dedicated integration tests for interactive features, manual QA per phase |
| **Kinematics computation drift** | High | Low | Property-based tests, cross-validation against existing implementation |
| **Renderer protocol too rigid** | Medium | Medium | Design for extension, allow escape hatches, version protocol |
| **Team unfamiliarity with new architecture** | Medium | High | Comprehensive docs, knowledge share sessions, pair programming during integration |
| **Incomplete migration leaves mixed patterns** | High | Medium | Phase-by-phase DoD enforcement, no merges without full mechanism coverage |

---

## 12. Rollout / Rollback Plan

### Feature Flags
```python
# Per-mechanism flags
MECHANISM_MODULAR_FOUR_BAR = os.getenv("MECHANISM_MODULAR_FOUR_BAR", "false") == "true"
MECHANISM_MODULAR_SLIDER_CRANK = ...
MECHANISM_MODULAR_CAM_FOLLOWER = ...
MECHANISM_MODULAR_GEAR_TRAIN = ...

# Global flag (overrides individual flags when enabled)
MECHANISM_MODULAR_ENABLED = os.getenv("MECHANISM_MODULAR_ENABLED", "false") == "true"
```

### Dual-Path Validation
During Phases 2-5, run both old and new code paths:
```python
if MECHANISM_MODULAR_FOUR_BAR:
    state = registry.get("four_bar").compute_state(params, angle)
    renderer.render(state, scene, config)
else:
    self._draw_four_bar_mechanism_optimized()  # Legacy

# Log comparison
if VALIDATE_MIGRATION:
    compare_outputs(old_scene, new_scene)
```

### Rollback Procedure
1. **Immediate:** Flip feature flag to `false`
2. **Quick:** Revert PR if issues discovered within 24h
3. **Gradual:** Archive legacy code after 2 weeks of stable new path

### Timeline
- **Week 1-2:** Foundation + Four-bar (feature flagged off)
- **Week 3:** Integration testing, feature flag on for dev environment
- **Week 4-5:** Remaining mechanisms (feature flagged off initially)
- **Week 6:** Cleanup, feature flags on for all mechanisms in dev
- **Week 7:** Production rollout (staged: 10% → 50% → 100% users)
- **Week 8:** Remove feature flags, archive legacy code

---

## 13. Definition of Done (DoD)

### Per-Phase DoD
- [ ] Code changes complete
- [ ] All tests passing (unit + integration + regression)
- [ ] Test coverage ≥85% for new code
- [ ] Performance metrics within 5% of baseline
- [ ] Telemetry integrated
- [ ] Documentation updated (code comments, docstrings)
- [ ] Code review approved
- [ ] Feature flag functional (if applicable)

### Final Project DoD
- [ ] All 4 mechanism types extracted
- [ ] `enhanced_macanism_tab.py` reduced to ≤800 LOC
- [ ] Zero visual regressions (pixel-perfect comparison)
- [ ] Zero performance regressions (60fps maintained)
- [ ] Test coverage ≥85% for `mechanisms/` modules
- [ ] Telemetry spans emitting for all operations
- [ ] Feature flags removed (new path is default)
- [ ] Legacy code archived
- [ ] Documentation complete:
  - [ ] ADR documenting migration decisions
  - [ ] Module READMEs with examples
  - [ ] API documentation
  - [ ] Migration guide for future mechanism types
- [ ] Team knowledge share completed
- [ ] Design tab integration validated

---

## 14. Success Criteria

### Must-Have (P0)
1. ✅ `enhanced_macanism_tab.py` ≤800 LOC
2. ✅ 100% visual parity (zero pixel diff)
3. ✅ Zero performance regression (60fps maintained)
4. ✅ All existing features functional (forces, trails, handles, safety zones)

### Should-Have (P1)
1. ✅ Test coverage ≥85%
2. ✅ Telemetry integrated
3. ✅ Design tab can share renderers
4. ✅ Mechanism modules ≤300 LOC each

### Nice-to-Have (P2)
1. OpenGL renderer interface defined (not implemented)
2. Performance improvements (faster than baseline)
3. Additional property-based tests

---

## 15. Open Questions

1. **Should we extract handles (DraggablePointHandle) to a separate interaction module?**
   - Current: Handles are in UI file
   - Proposal: `mechanisms/interaction/handles.py`
   - Decision: TBD (can be separate PR after main migration)

2. **How to handle mechanism-specific parameters in Design tab?**
   - Current: Design tab has its own parameter system
   - Proposal: Shared parameter metadata from mechanisms
   - Decision: TBD (address in Phase 6)

3. **Should force calculation be in mechanism or separate physics module?**
   - Option A: `FourBarMechanism.compute_forces()` (domain logic)
   - Option B: `PhysicsEngine.compute_forces(state)` (separate concern)
   - Decision: Option A (forces are inherent to mechanism kinematics)

---

## 16. Next Steps

**Immediate Actions:**
1. **Get approval** on this PRD from team
2. **Create Phase 1 implementation plan** (detailed task breakdown)
3. **Set up telemetry baseline** (capture current performance metrics)
4. **Create snapshot test harness** (for visual regression testing)

**First Implementation Task:**
Create directory structure and core protocols (Phase 1, Week 1)

---

## Appendix A: Line-by-Line Extraction Map

### Four-Bar Mechanism
- **Kinematics** (→ `mechanisms/linkages/four_bar.py`):
  - Lines 574-717: `_solve_four_bar_output_angle_fast()` → `FourBarMechanism.compute_output_angle()`
  - Lines 719-885: `_evaluate_four_bar_safety()` → `FourBarMechanism.evaluate_safety()`
  - Lines 1615-1672: `_find_safe_four_bar_position()`, `_is_four_bar_position_valid()`

- **Rendering** (→ `mechanisms/linkages/renderer.py`):
  - Lines 379-456: `_draw_four_bar_mechanism_optimized()` → `LinkageRenderer.render_four_bar()`
  - Lines 457-511: `_draw_link_optimized()` → `LinkageRenderer._draw_link()`
  - Lines 513-572: `_draw_joint_optimized()` → `LinkageRenderer._draw_joint()`
  - Lines 921-1077: `_draw_four_bar_safety_zones()` → `SafetyZoneRenderer.render_four_bar_zones()`

- **Forces** (→ `mechanisms/linkages/four_bar.py`):
  - Line 449: `_calculate_four_bar_forces_optimized()` → `FourBarMechanism._compute_forces()`

### Slider-Crank Mechanism
- **Kinematics** (→ `mechanisms/cranks/slider_crank.py`):
  - Lines 1324-1426: `_draw_slider_crank_mechanism_optimized()` → extract kinematics

- **Forces** (→ `mechanisms/cranks/slider_crank.py`):
  - Lines 1685-1735: `_calculate_slider_crank_forces_accurate()`

- **Safety** (→ `mechanisms/cranks/slider_crank.py`):
  - Lines 887-902: `_evaluate_slider_crank_safety()`
  - Lines 1079-1131: `_draw_slider_crank_safety_zones()`

### Cam-Follower Mechanism
- **Kinematics** (→ `mechanisms/cams/cam_follower.py`):
  - Lines 1427-1613: `_draw_cam_follower_mechanism_optimized()` → extract kinematics

- **Forces** (→ `mechanisms/cams/cam_follower.py`):
  - Lines 1737-1798: `_calculate_cam_follower_forces_accurate()`

### Gear-Train Mechanism
- **Kinematics** (→ `mechanisms/gears/gear_train.py`):
  - Lines 1800-1884: `_draw_gear_train_mechanism_optimized()` → extract kinematics

### Shared Utilities
- **Geometry** (→ `mechanisms/utils/geometry.py`):
  - Lines 457-511: Link drawing
  - Lines 513-572: Joint drawing

- **Safety Zones** (→ `mechanisms/utils/safety.py`):
  - Lines 904-1131: Safety zone rendering
  - Lines 1133-1178: Zone labels

- **Forces** (→ `mechanisms/utils/forces.py`):
  - Force vector rendering (scattered throughout)

---

## Appendix B: Test Plan Template

### Per-Mechanism Test Suite
```python
# tests/mechanisms/linkages/test_four_bar.py

def test_compute_state_basic():
    """Test basic four-bar state computation"""
    mechanism = FourBarMechanism()
    state = mechanism.compute_state(
        parameters={"ground_link": 150, "input_link": 40, ...},
        input_angle=45.0
    )
    assert state.positions["A"] == (expected_x, expected_y)
    assert state.positions["B"] == (expected_x, expected_y)

def test_grashof_validation():
    """Test Grashof criterion validation"""
    mechanism = FourBarMechanism()
    with pytest.raises(ValidationError):
        mechanism.validate_parameters({
            "ground_link": 150,
            "input_link": 200,  # Too long, violates Grashof
            "coupler_link": 50,
            "output_link": 50,
        })

@pytest.mark.parametrize("angle", [0, 45, 90, 135, 180, 225, 270, 315])
def test_full_rotation(angle):
    """Test four-bar at multiple angles"""
    mechanism = FourBarMechanism()
    state = mechanism.compute_state(DEFAULT_PARAMS, angle)
    assert state.safety_status.level != "danger"

def test_render_pipeline(qgraphics_scene):
    """Test full compute → render pipeline"""
    mechanism = FourBarMechanism()
    state = mechanism.compute_state(DEFAULT_PARAMS, 45.0)
    
    renderer = LinkageRenderer()
    items = renderer.render(state, qgraphics_scene, RenderConfig())
    
    assert len(items) > 0
    assert any(isinstance(item, QGraphicsLineItem) for item in items)
```

---

**End of PRD**
