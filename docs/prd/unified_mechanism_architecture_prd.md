# PRD: Unified Mechanism Architecture Integration

**Date:** 2025-10-20  
**Status:** Draft - Pending Approval  
**Authors:** Claude + Alan Synn  
**Related ADRs:** 002-mechanism-foundry-refactor.md

---

## 1. Problem / Goal

### Current State
The application has **three separate mechanism systems** that operate independently:

1. **Mechanism Foundry** (`ui/tabs/mechanism_foundry/`) - ✅ REFACTORED
   - Standalone mechanism exploration and testing
   - Uses `src/automataii/mechanisms/` (fourbar, cam)
   - Protocol-driven, modular architecture (380 LOC view)
   - **Status:** Complete, 131/132 tests passing

2. **Recommendation Dialog** (`gui/dialogs/recommendation_dialog.py`)
   - Analyzes user-drawn paths, recommends mechanisms
   - **Own rendering logic** (duplicates fourbar/cam rendering)
   - **Own mechanism data format** (JSON-based)
   - **Status:** Independent, not using shared mechanisms

3. **Mechanism Design Tab** (`gui/tabs/mechanism_design_tab.py`) - 4,546 LOC
   - Integrates mechanisms with character animation
   - **Own mechanism computation** (embedded in tab)
   - **Own rendering logic** (separate from foundry)
   - **Status:** Monolithic, high coupling

### Problems

| Issue | Impact | Severity |
|-------|--------|----------|
| **Duplicated rendering logic** | 3 implementations of fourbar/cam rendering | High |
| **Inconsistent behavior** | Same mechanism looks/acts different across UIs | High |
| **No shared mechanism improvements** | Fixes in foundry don't propagate to design tab | High |
| **Code size violations** | `mechanism_design_tab.py` = 4,546 LOC (909% over limit) | Critical |
| **Tight coupling** | Design tab mixes UI + domain + rendering | High |
| **Difficult testing** | Cannot test mechanisms independently | Medium |
| **No mechanism transfer** | Cannot move mechanisms between foundry ↔ design tab | Medium |

### Goals

**Quantitative Targets:**
- ✅ All files < 500 LOC (per codex requirement)
- ✅ Shared mechanism code: 1 implementation for all 3 systems
- ✅ Zero rendering duplication
- ✅ 95%+ test coverage for mechanism modules
- ✅ Mechanism transfer between foundry ↔ design tab in < 100ms

**Qualitative Targets:**
- ✅ Single source of truth for mechanism physics/rendering
- ✅ Consistent mechanism behavior across all UIs
- ✅ Easy to add new mechanisms (follows established pattern)
- ✅ Clear dependency direction (UI → Controller → Domain)

---

## 2. In-Scope / Out-of-Scope

### In-Scope
✅ Unified mechanism architecture using `src/automataii/mechanisms/`  
✅ Refactor recommendation dialog to use shared mechanisms  
✅ Refactor mechanism design tab to use shared mechanisms  
✅ Implement mechanism transfer service (foundry ↔ design tab)  
✅ All modules < 500 LOC compliance  
✅ Protocol-driven design for extensibility  
✅ Integration tests for all three systems  
✅ ADR documentation for architecture decisions  

### Out-of-Scope
❌ Implementing gear train mechanism (deferred to Phase 2)  
❌ Implementing slider-crank mechanism (deferred to Phase 2)  
❌ Performance optimization (lazy rendering, caching)  
❌ Blueprint export format changes  
❌ IK system refactoring (separate workstream)  
❌ Adding new mechanism types beyond existing (fourbar, cam)  

---

## 3. Architecture Overview

### Target Architecture (Hexagonal / Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│                                                                   │
│  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ Mechanism      │  │ Recommendation   │  │ Mechanism       │  │
│  │ Foundry View   │  │ Dialog           │  │ Design Tab      │  │
│  │ (380 LOC)      │  │ (Refactored)     │  │ (Refactored)    │  │
│  └────────┬───────┘  └────────┬─────────┘  └────────┬────────┘  │
│           │                   │                      │           │
└───────────┼───────────────────┼──────────────────────┼───────────┘
            │                   │                      │
            ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CONTROLLER LAYER                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │    MechanismFoundryController                            │   │
│  │    (config, catalog, orchestration)                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │    MechanismTransferService  (NEW)                       │   │
│  │    - export_mechanism(mechanism_id) → MechanismSpec      │   │
│  │    - import_mechanism(spec) → mechanism_id                │   │
│  │    - validate_transfer(spec) → bool                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DOMAIN LAYER                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  src/automataii/mechanisms/                                │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ fourbar/     │  │ cam/         │  │ core/        │    │ │
│  │  │ - compute.py │  │ - compute.py │  │ - protocols  │    │ │
│  │  │ - render.py  │  │ - render.py  │  │ - state      │    │ │
│  │  │ (396 LOC)    │  │ (241 LOC)    │  │ - catalog    │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow (Use Case: Apply Recommended Mechanism)

```
1. User draws path in Editor Tab
   ↓
2. User clicks "Get Recommendations" in Mechanism Design Tab
   ↓
3. RecommendationDialog uses FourBarMechanism.compute() from shared module
   ↓
4. Dialog renders preview using FourBarRenderer.render() from shared module
   ↓
5. User selects mechanism → MechanismTransferService.export_mechanism()
   ↓
6. MechanismDesignTab imports via MechanismTransferService.import_mechanism()
   ↓
7. Animation uses same FourBarMechanism.compute() logic
   ✅ Guaranteed visual consistency
```

---

## 4. Public API

### 4.1 MechanismTransferService (NEW)

```python
# src/automataii/application/mechanism_transfer/service.py

@dataclass
class MechanismSpec:
    """Universal mechanism specification for transfer between systems."""
    mechanism_type: str  # "fourbar", "cam", "gear", "slider_crank"
    parameters: dict[str, float]  # Mechanism-specific parameters
    state: MechanismState  # Current state (angle, position, etc.)
    metadata: dict[str, Any]  # Optional: name, description, tags
    
class MechanismTransferService:
    """Service for transferring mechanisms between UI contexts."""
    
    def export_mechanism(self, mechanism: Mechanism) -> MechanismSpec:
        """Export a mechanism to a universal spec."""
        
    def import_mechanism(self, spec: MechanismSpec) -> Mechanism:
        """Import a mechanism from a universal spec."""
        
    def validate_spec(self, spec: MechanismSpec) -> tuple[bool, list[str]]:
        """Validate a mechanism spec. Returns (is_valid, errors)."""
```

### 4.2 Updated RecommendationDialog Interface

```python
# src/automataii/gui/dialogs/recommendation_dialog.py

class MechanismRecommendationDialog(QDialog):
    """REFACTORED: Now uses shared mechanism modules."""
    
    # Signal: emits MechanismSpec instead of raw dict
    mechanism_selected = Signal(MechanismSpec)
    
    def _render_mechanism_preview(self, spec: MechanismSpec):
        """Use FourBarRenderer/CamRenderer from shared modules."""
        mechanism = self.transfer_service.import_mechanism(spec)
        renderer = self._get_renderer(mechanism)
        items = renderer.render(mechanism.get_state(), self.render_config)
        # ... add items to preview scene
```

### 4.3 Updated MechanismDesignTab Interface

```python
# src/automataii/gui/tabs/mechanism_design_tab.py

class MechanismDesignTab(QWidget):
    """REFACTORED: Modular architecture using shared mechanisms."""
    
    def _handle_recommendation_selection(self, spec: MechanismSpec):
        """Import mechanism from recommendation dialog."""
        mechanism = self.transfer_service.import_mechanism(spec)
        self._add_mechanism_to_scene(mechanism)
        self._register_for_animation(mechanism)
        
    def _add_mechanism_to_scene(self, mechanism: Mechanism):
        """Add mechanism using shared renderer."""
        renderer = self._get_renderer(mechanism)
        items = renderer.render(mechanism.get_state(), self.render_config)
        for item in items:
            self.mechanism_scene.addItem(item)
```

---

## 5. Dependencies

### Internal Modules
- ✅ `src/automataii/mechanisms/core/protocols.py` - Mechanism, MechanismRenderer
- ✅ `src/automataii/mechanisms/core/state.py` - MechanismState, RenderConfig
- ✅ `src/automataii/mechanisms/fourbar/compute.py` - FourBarMechanism (396 LOC)
- ✅ `src/automataii/mechanisms/fourbar/render.py` - FourBarRenderer (258 LOC)
- ✅ `src/automataii/mechanisms/cam/compute.py` - CamFollowerMechanism (241 LOC)
- 🆕 `src/automataii/application/mechanism_transfer/service.py` - MechanismTransferService
- 🆕 `src/automataii/application/mechanism_transfer/spec.py` - MechanismSpec dataclass

### External Dependencies
- PyQt6 (UI rendering)
- NumPy (mechanism mathematics)
- dataclasses (spec serialization)

### Upstream Modules
- `gui/views/editor_view.py` - Scene management, viewport
- `core/project_data_manager.py` - Project state persistence
- `kinematics/ik_manager.py` - Skeleton animation integration

### Downstream Modules
- `gui/blueprint/exporter.py` - Blueprint export (reads mechanism state)
- Tests: `tests/test_mechanism_*` (all mechanism tests)

---

## 6. Test Strategy

### 6.1 Unit Tests

**Module:** `tests/test_mechanism_transfer_service.py`
```python
def test_export_fourbar_mechanism():
    """Test exporting a four-bar mechanism to spec."""
    mechanism = FourBarMechanism(...)
    service = MechanismTransferService()
    spec = service.export_mechanism(mechanism)
    assert spec.mechanism_type == "fourbar"
    assert "l1" in spec.parameters
    
def test_import_fourbar_mechanism():
    """Test importing a four-bar mechanism from spec."""
    spec = MechanismSpec(mechanism_type="fourbar", ...)
    service = MechanismTransferService()
    mechanism = service.import_mechanism(spec)
    assert isinstance(mechanism, FourBarMechanism)
```

**Module:** `tests/test_recommendation_dialog_integration.py`
```python
def test_recommendation_uses_shared_renderer():
    """Test that recommendation dialog uses FourBarRenderer."""
    dialog = MechanismRecommendationDialog(...)
    # Mock FourBarRenderer
    with patch('automataii.mechanisms.fourbar.render.FourBarRenderer') as mock:
        dialog._render_preview(fourbar_spec)
        mock.render.assert_called_once()
```

### 6.2 Integration Tests

**Module:** `tests/test_mechanism_design_integration.py`
```python
def test_transfer_mechanism_from_recommendation_to_design_tab():
    """Test full workflow: recommendation → design tab."""
    # 1. Create recommendation dialog
    dialog = MechanismRecommendationDialog(...)
    
    # 2. Select mechanism
    spec = dialog.get_top_recommendation()
    
    # 3. Transfer to design tab
    design_tab = MechanismDesignTab(...)
    design_tab._handle_recommendation_selection(spec)
    
    # 4. Verify mechanism is added
    assert len(design_tab.mechanisms) == 1
    assert design_tab.mechanisms[0].mechanism_type == spec.mechanism_type
```

### 6.3 Regression Tests

**Module:** `tests/test_rendering_consistency.py`
```python
def test_fourbar_renders_identically_across_contexts():
    """Ensure fourbar renders the same in foundry, dialog, and design tab."""
    mechanism = FourBarMechanism(l1=100, l2=80, l3=120, l4=90)
    renderer = FourBarRenderer()
    config = RenderConfig(show_labels=True)
    
    # Render in all three contexts
    items_foundry = renderer.render(mechanism.get_state(), config)
    items_dialog = renderer.render(mechanism.get_state(), config)
    items_design = renderer.render(mechanism.get_state(), config)
    
    # Compare visual outputs (number of items, positions, colors)
    assert len(items_foundry) == len(items_dialog) == len(items_design)
    assert_visual_equality(items_foundry, items_dialog, items_design)
```

### 6.4 Success Criteria

| Test Category | Target Coverage | Pass Criteria |
|---------------|----------------|---------------|
| Unit tests | > 90% | All mechanisms, transfer service |
| Integration tests | 100% workflows | Foundry ↔ Dialog ↔ Design Tab |
| Regression tests | All existing | No visual or behavioral changes |

---

## 7. Observability / Metrics

### Logging Strategy

```python
# Structured logging with correlation IDs
import logging
logger = logging.getLogger(__name__)

class MechanismTransferService:
    def export_mechanism(self, mechanism: Mechanism) -> MechanismSpec:
        transfer_id = uuid.uuid4()
        logger.info("mechanism_export_start", extra={
            "transfer_id": transfer_id,
            "mechanism_type": mechanism.mechanism_type,
            "timestamp": time.time()
        })
        
        # ... export logic ...
        
        logger.info("mechanism_export_complete", extra={
            "transfer_id": transfer_id,
            "spec_size_bytes": len(json.dumps(spec)),
            "duration_ms": elapsed_ms
        })
```

### Key Metrics

| Metric | Target | Purpose |
|--------|--------|---------|
| `mechanism_transfer_latency_ms` | < 100ms | User experience |
| `mechanism_render_time_ms` | < 16ms (60 FPS) | Animation smoothness |
| `recommendation_accuracy` | > 85% match | Recommendation quality |
| `module_loc` | < 500 LOC all files | Code quality |
| `test_coverage` | > 90% | Reliability |

### Telemetry Tags

- `mechanism_type`: fourbar, cam, gear, slider_crank
- `transfer_direction`: export, import
- `source_context`: foundry, dialog, design_tab
- `version`: mechanism protocol version (for compatibility)

---

## 8. Performance / Resource Constraints

### Input Scale Constraints

| Component | Max Input | Constraint |
|-----------|-----------|------------|
| Path points | 10,000 | User-drawn paths |
| Mechanisms in scene | 50 | Simultaneous rendering |
| Animation FPS | 60 | Smooth animation |
| Transfer latency | < 100ms | Perceived instant |

### Algorithmic Complexity

| Operation | Current | Target | Notes |
|-----------|---------|--------|-------|
| Mechanism compute | O(1) | O(1) | Per frame |
| Mechanism render | O(n) | O(n) | n = items (links, joints) |
| Path matching | O(n²) | O(n log n) | Recommendation system |
| Scene update | O(m) | O(m) | m = active mechanisms |

### Memory Ceilings

- Mechanism state: ~1 KB per instance
- Rendered items: ~10 KB per mechanism (Qt objects)
- Transfer spec: < 5 KB (JSON serialization)

### Optimization Strategies

1. **Lazy Rendering** - Only render visible mechanisms
2. **Object Pooling** - Reuse Qt graphics items
3. **Caching** - Cache transformed coordinates
4. **Throttling** - Limit animation updates to 60 FPS

---

## 9. Risks / Mitigations

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Breaking existing mechanisms** | Medium | High | Comprehensive regression tests |
| **Performance degradation** | Low | Medium | Profile before/after, benchmarks |
| **Qt object lifecycle issues** | Medium | Medium | Explicit object ownership, weak refs |
| **Recommendation accuracy drops** | Low | High | A/B testing, metrics monitoring |
| **Incomplete refactoring** | Low | Critical | Phased rollout, feature flags |

### Detailed Mitigations

**1. Breaking existing mechanisms**
- ✅ Write regression tests BEFORE refactoring
- ✅ Run tests after each file migration
- ✅ Use type hints + mypy for compile-time checks
- ✅ Manual QA: visual comparison screenshots

**2. Performance degradation**
- ✅ Profile `mechanism_design_tab.py` before refactoring
- ✅ Set baseline: render time, FPS, memory usage
- ✅ Profile after refactoring, compare metrics
- ✅ If degraded > 10%, investigate and optimize

**3. Qt object lifecycle issues**
- ✅ Use `QGraphicsScene.addItem()` for ownership transfer
- ✅ Clear references before deleting scenes
- ✅ Use `deleteLater()` for async deletion
- ✅ Add Qt object validity checks (`sip.isdeleted()`)

**4. Recommendation accuracy drops**
- ✅ Preserve existing algorithm logic
- ✅ Only change rendering implementation
- ✅ Monitor `recommendation_accuracy` metric
- ✅ Rollback if accuracy drops > 5%

---

## 10. Rollout / Rollback Plan

### Phase 1: MechanismTransferService (Week 1)
**Goal:** Create shared transfer layer

```
Day 1-2: Design API
  - Define MechanismSpec dataclass
  - Write protocol-compliant export/import
  
Day 3-4: Implement service
  - Create MechanismTransferService
  - Unit tests (export/import/validate)
  
Day 5: Integration
  - Wire into MechanismFoundryController
  - Integration tests
```

**Rollback:** Delete new module, no impact on existing systems

---

### Phase 2: RecommendationDialog Refactor (Week 2)
**Goal:** Use shared mechanism modules for rendering

```
Day 1-2: Remove duplicated rendering
  - Delete custom fourbar rendering code
  - Use FourBarRenderer from shared module
  
Day 3: Remove duplicated cam rendering
  - Use CamRenderer (to be created in shared module)
  
Day 4: Integration with MechanismTransferService
  - Emit MechanismSpec instead of raw dict
  
Day 5: Testing
  - Visual regression tests
  - Integration tests with design tab
```

**Rollback:** Revert to previous `recommendation_dialog.py` version

---

### Phase 3: MechanismDesignTab Refactor (Week 3-4)
**Goal:** Modularize 4,546 LOC monolith

```
Week 3:
Day 1-2: Extract mechanism rendering
  - Move rendering logic to shared modules
  - Use FourBarRenderer/CamRenderer
  
Day 3-4: Extract mechanism computation
  - Use FourBarMechanism.compute() from shared module
  - Remove embedded mechanism math
  
Day 5: Extract animation controller
  - Create MechanismAnimationController (< 500 LOC)

Week 4:
Day 1-2: Extract UI layout
  - Create MechanismDesignTabLayout (< 500 LOC)
  - Similar pattern to foundry_view.py
  
Day 3: Integration with MechanismTransferService
  - Implement import_mechanism()
  - Connect to recommendation dialog
  
Day 4-5: Testing & Polish
  - Integration tests
  - Manual QA
  - Performance profiling
```

**Rollback:** Feature flag to disable new architecture, fall back to old tab

---

### Phase 4: Verification & Cleanup (Week 5)
**Goal:** Ensure system stability and remove deprecated code

```
Day 1-2: System-wide testing
  - Run all 131+ tests
  - Visual regression checks
  - Performance benchmarks
  
Day 3: Code cleanup
  - Remove deprecated code
  - Delete old mechanism rendering
  - Update documentation
  
Day 4-5: ADR updates
  - Document final architecture
  - Update README
  - Create migration guide
```

---

### Feature Flags (Progressive Rollout)

```python
# config/feature_flags.py

FEATURES = {
    "use_shared_mechanism_renderer": True,  # Phase 2
    "use_mechanism_transfer_service": True,  # Phase 1
    "use_refactored_design_tab": False,     # Phase 3 (disabled initially)
}

# Gradual rollout:
# Week 1: 0% users
# Week 2: 10% users (internal testing)
# Week 3: 50% users (canary deployment)
# Week 4: 100% users (full rollout)
```

---

## 11. Definition of Done (DoD)

### Code Quality
- [ ] All modules < 500 LOC
- [ ] All imports using shared `src/automataii/mechanisms/`
- [ ] Zero duplication of mechanism rendering logic
- [ ] Zero duplication of mechanism computation logic
- [ ] Type hints on all public APIs
- [ ] Docstrings on all public functions/classes

### Testing
- [ ] Unit tests for MechanismTransferService (> 90% coverage)
- [ ] Integration tests for all three systems (foundry, dialog, design tab)
- [ ] Regression tests for visual consistency
- [ ] All 131+ existing tests still passing
- [ ] New tests for transfer workflows

### Documentation
- [ ] ADR 002: Mechanism Foundry Refactor (✅ DONE)
- [ ] ADR 003: Unified Mechanism Architecture (NEW)
- [ ] Update README with new architecture diagram
- [ ] Update CHANGELOG with breaking changes
- [ ] Create mechanism extension guide for new types

### Performance
- [ ] No FPS regression in animation (baseline: 60 FPS)
- [ ] Mechanism transfer < 100ms latency
- [ ] Memory usage unchanged (baseline: ~50 MB per mechanism)
- [ ] No visual glitches or flicker

### Observability
- [ ] Logging added for all transfers (export/import)
- [ ] Metrics tracked: transfer_latency_ms, render_time_ms
- [ ] Telemetry tags: mechanism_type, source_context

### Review & Approval
- [ ] Code review by Alan Synn
- [ ] Manual QA testing
- [ ] Architecture review approved
- [ ] PRD signed off

---

## 12. Timeline / Owner / Reviewers

### Timeline
- **Total Duration:** 5 weeks
- **Phase 1:** Week 1 (MechanismTransferService)
- **Phase 2:** Week 2 (RecommendationDialog refactor)
- **Phase 3:** Week 3-4 (MechanismDesignTab refactor)
- **Phase 4:** Week 5 (Verification & cleanup)

### Ownership
- **Primary Owner:** Claude (AI Assistant)
- **Code Reviewer:** Alan Synn
- **Architecture Reviewer:** Alan Synn
- **QA:** Alan Synn

### Review Gates
- **Phase 1 Gate:** MechanismTransferService API approved
- **Phase 2 Gate:** RecommendationDialog renders correctly
- **Phase 3 Gate:** MechanismDesignTab < 500 LOC per file
- **Phase 4 Gate:** All tests passing, no regressions

---

## 13. Success Metrics (Post-Implementation)

### Quantitative Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| **Code duplication** | 3 renderer implementations | 1 shared implementation | Static analysis |
| **Module LOC** | 4,546 (design tab) | < 500 all files | Line count |
| **Test coverage** | 85% | > 90% | pytest-cov |
| **Mechanism types** | 2 (fourbar, cam) | 2 (maintained) | Catalog count |
| **Transfer latency** | N/A | < 100ms | Telemetry |
| **Animation FPS** | 60 | 60 (no regression) | Profiler |

### Qualitative Metrics

✅ **Developer Experience**
- New mechanism types can be added in < 500 LOC
- Clear protocol-driven pattern to follow
- Tests pass first time (high confidence)

✅ **User Experience**
- Mechanisms behave identically across all UIs
- Smooth transfer from recommendation → design tab
- No visual glitches or inconsistencies

✅ **Maintainability**
- Single source of truth for mechanism logic
- Easy to debug (isolated modules)
- Clear dependency graph (no cycles)

---

## Appendix A: File Structure (After Refactoring)

```
src/automataii/
├── mechanisms/                    # SHARED MECHANISM MODULES (✅ DONE)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── protocols.py           # Mechanism, MechanismRenderer protocols
│   │   └── state.py               # MechanismState, RenderConfig, SafetyLevel
│   ├── catalog/
│   │   ├── __init__.py
│   │   └── registry.py            # MechanismRegistry (catalog of types)
│   ├── fourbar/
│   │   ├── __init__.py
│   │   ├── compute.py             # FourBarMechanism (396 LOC) ✅
│   │   └── render.py              # FourBarRenderer (258 LOC) ✅
│   ├── cam/
│   │   ├── __init__.py
│   │   ├── compute.py             # CamFollowerMechanism (241 LOC) ✅
│   │   └── render.py              # CamRenderer (TBD - Phase 2)
│   └── __init__.py
│
├── application/                   # APPLICATION SERVICES
│   ├── mechanism_foundry/
│   │   └── controller.py          # MechanismFoundryController ✅
│   └── mechanism_transfer/        # 🆕 NEW SERVICE (Phase 1)
│       ├── __init__.py
│       ├── service.py             # MechanismTransferService
│       └── spec.py                # MechanismSpec dataclass
│
├── ui/tabs/
│   └── mechanism_foundry/
│       ├── __init__.py
│       └── foundry_view.py        # MechanismFoundryView (380 LOC) ✅
│
├── gui/
│   ├── dialogs/
│   │   └── recommendation_dialog.py  # REFACTORED (Phase 2)
│   └── tabs/
│       └── mechanism_design_tab.py   # REFACTORED (Phase 3)
│
└── tests/
    ├── test_mechanism_transfer_service.py  # 🆕 NEW (Phase 1)
    ├── test_recommendation_dialog_integration.py  # 🆕 NEW (Phase 2)
    └── test_mechanism_design_integration.py  # 🆕 NEW (Phase 3)
```

---

## Appendix B: Dependency Graph (Target State)

```
┌───────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (UI)                                          │
│  - mechanism_foundry/foundry_view.py                              │
│  - dialogs/recommendation_dialog.py                               │
│  - tabs/mechanism_design_tab.py                                   │
└──────────────────┬────────────────────────────────────────────────┘
                   │ depends on
                   ▼
┌───────────────────────────────────────────────────────────────────┐
│  CONTROLLER LAYER (Orchestration)                                 │
│  - application/mechanism_foundry/controller.py                    │
│  - application/mechanism_transfer/service.py  🆕                  │
└──────────────────┬────────────────────────────────────────────────┘
                   │ depends on
                   ▼
┌───────────────────────────────────────────────────────────────────┐
│  DOMAIN LAYER (Business Logic)                                    │
│  - mechanisms/fourbar/compute.py                                  │
│  - mechanisms/fourbar/render.py                                   │
│  - mechanisms/cam/compute.py                                      │
│  - mechanisms/cam/render.py  🆕                                   │
└──────────────────┬────────────────────────────────────────────────┘
                   │ implements
                   ▼
┌───────────────────────────────────────────────────────────────────┐
│  PROTOCOL LAYER (Interfaces)                                      │
│  - mechanisms/core/protocols.py                                   │
│  - mechanisms/core/state.py                                       │
└───────────────────────────────────────────────────────────────────┘

RULES:
- Layers can only depend downward (never upward)
- Domain layer has ZERO knowledge of UI layer
- Protocols define contracts (dependency inversion)
- No circular dependencies between modules
```

---

## Approval

**Status:** 🟡 **Draft - Pending Approval**

**Questions for Review:**
1. Is 5-week timeline acceptable? Can we parallelize?
2. Should we implement cam/render.py in Phase 2 or defer?
3. Feature flag strategy sufficient for safe rollout?
4. Any concerns with MechanismTransferService API design?

**Next Steps:**
1. Review PRD with Alan Synn
2. Q&A session to clarify requirements
3. Revise PRD based on feedback
4. Obtain explicit ACK approval
5. Begin Phase 1 implementation

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-20  
**Related Documents:**
- `docs/adr/002-mechanism-foundry-refactor.md`
- `docs/analysis/mm3.1_foundry_catalog_service.md`
- `AGENTS.md` (Codex: 500 LOC policy, SOLID principles)
