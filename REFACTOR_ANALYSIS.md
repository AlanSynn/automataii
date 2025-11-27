# Automataii Architecture Refactoring Analysis

**Date:** 2025-11-26
**Scope:** 232 Python files, ~60k LOC
**Objective:** Restructure src/ for modularity, composability, and Hexagonal Architecture

---

## I. CURRENT STATE ANALYSIS

### 1.1 Directory Structure Issues

| Issue | Severity | Description |
|:------|:---------|:------------|
| **Duplication** | HIGH | `gui/` vs `ui/` (overlapping UI concerns) |
| **Duplication** | HIGH | `animate/` vs `animation/` (unclear distinction) |
| **Deep Nesting** | HIGH | `ui/tabs/mechanism_design/parametric/handles/` (5+ levels) |
| **Mixed Concerns** | HIGH | `gui/mechanisms/` contains UI + domain logic |
| **Unclear Boundaries** | MEDIUM | `application/`, `services/`, `scenarios/` overlap |
| **Underutilized Domain** | MEDIUM | `domain/` exists but most logic elsewhere |
| **Inconsistent Naming** | LOW | `fourbar` vs `four_bar` vs `FourBar` |

### 1.2 Module Inventory

**Top-Level Modules (18):**
```
src/automataii/
├── animate/          # Animation logic (partial)
├── animation/        # Animation logic (duplicate?)
├── application/      # Application services
├── config/           # Configuration
├── core/             # Core models, state, events
├── domain/           # Domain logic (underutilized)
├── examples/         # Examples
├── generation/       # Generation logic
├── gui/              # Qt GUI (legacy)
├── kinematics/       # Kinematics solvers
├── mechanisms/       # Mechanism domain logic
├── modules/          # External modules
├── scenarios/        # Test scenarios
├── services/         # Services (overlaps with application)
├── ui/               # Qt UI (new)
└── utils/            # Utilities
```

### 1.3 Dependency Analysis

**High-Coupling Areas:**
- `mechanisms/linkages/` → imported by 20+ files
- `gui/mechanisms/` → tightly coupled to domain
- `core/models.py` → God object pattern
- `ui/tabs/mechanism_design/` → 6 levels deep, 30+ files

**Cross-Layer Violations:**
- UI imports domain directly (should use application layer)
- Services import GUI components (reversed dependency)
- Infrastructure leaks into domain (`onnxruntime` imports)

---

## II. TARGET ARCHITECTURE (HEXAGONAL/CLEAN)

### 2.1 Architectural Principles

1. **Dependency Rule:** Dependencies point INWARD (towards domain)
2. **Single Responsibility:** Each module has ONE reason to change
3. **Interface Segregation:** Small, focused protocols
4. **Dependency Inversion:** Depend on abstractions, not concretions

### 2.2 Proposed Directory Structure

```
src/automataii/
│
├── domain/                          # CORE (Pure Logic, No External Dependencies)
│   ├── mechanisms/
│   │   ├── protocols.py            # Mechanism, Validator, Strategy protocols
│   │   ├── catalog.py              # Mechanism registry
│   │   ├── linkages/
│   │   │   ├── models.py           # LinkageConfig, LinkageState
│   │   │   ├── compute.py          # Pure computation functions
│   │   │   ├── validators/         # Grashof, collision, etc.
│   │   │   └── strategies/         # FourBar, FiveBar, SixBar
│   │   ├── cam/
│   │   │   ├── models.py
│   │   │   └── compute.py
│   │   └── gears/
│   │       ├── models.py
│   │       └── compute.py
│   │
│   ├── animation/                  # Unified animation domain
│   │   ├── models.py               # BodyPart, Skeleton, Animation
│   │   ├── arap.py                 # ARAP deformation algorithm
│   │   └── templates.py            # Animation templates
│   │
│   ├── kinematics/
│   │   ├── models.py               # IK configuration
│   │   └── solvers/                # IK solver implementations
│   │
│   └── blueprint/
│       ├── models.py               # Blueprint domain model
│       └── generator.py            # Blueprint generation logic
│
├── application/                     # USE CASES (Application Services)
│   ├── mechanisms/
│   │   ├── foundry.py              # Mechanism catalog browsing
│   │   ├── design.py               # Mechanism design workflow
│   │   └── transfer.py             # Mechanism-to-skeleton transfer
│   │
│   ├── animation/
│   │   ├── pose_estimation.py      # Pose estimation workflow
│   │   └── character_animation.py  # Character animation workflow
│   │
│   └── blueprint/
│       └── export.py               # Blueprint export workflow
│
├── infrastructure/                  # ADAPTERS (External Dependencies)
│   ├── persistence/
│   │   ├── serializers/            # JSON, YAML serializers
│   │   └── file_manager.py         # File I/O operations
│   │
│   ├── compute/
│   │   ├── onnx_runtime.py         # ONNX model execution
│   │   └── cv_algorithms.py        # OpenCV wrappers
│   │
│   └── telemetry/
│       ├── logging.py              # Logging adapter
│       └── metrics.py              # Metrics collection
│
├── presentation/                    # UI LAYER (Qt Adapter)
│   ├── qt/
│   │   ├── main_window.py
│   │   ├── tabs/
│   │   │   ├── mechanism_foundry/
│   │   │   ├── mechanism_design/
│   │   │   ├── image_processing/
│   │   │   └── options/
│   │   │
│   │   ├── widgets/
│   │   │   ├── editor/            # Canvas editors
│   │   │   ├── controls/          # Parameter controls
│   │   │   └── displays/          # Info displays
│   │   │
│   │   └── dialogs/
│   │
│   └── rendering/
│       ├── protocols.py            # Renderer protocol
│       ├── factory.py              # Renderer factory
│       └── renderers/
│           ├── mechanism.py        # Mechanism visualization
│           ├── skeleton.py         # Skeleton visualization
│           └── blueprint.py        # Blueprint visualization
│
└── shared/                          # SHARED KERNEL
    ├── events/                     # Event bus (pub/sub)
    ├── state/                      # State management
    ├── config/                     # Configuration
    └── types/                      # Shared type definitions
```

### 2.3 Dependency Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation (UI)                       │
│                    presentation/qt/                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ (depends on)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Services                       │
│                    application/                              │
└──────────────────────────┬──────────────────────────────────┘
                           │ (depends on)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Domain (Core)                            │
│                    domain/                                   │
│              (Pure logic, no dependencies)                   │
└──────────────────────────────────────────────────────────────┘

                Infrastructure (Adapters)
                 infrastructure/
            (Implements domain protocols)
```

---

## III. MIGRATION STRATEGY

### 3.1 Migration Phases

**Phase 1: Create Target Structure (Safe)**
- Create new directory structure
- Define protocols and interfaces
- NO file moves yet

**Phase 2: Extract Domain Logic**
- Move pure computation to `domain/`
- Move mechanism logic to `domain/mechanisms/`
- Merge `animate/` + `animation/` → `domain/animation/`

**Phase 3: Consolidate UI**
- Merge `gui/` + `ui/` → `presentation/qt/`
- Flatten deep nesting (5+ levels → 3 levels max)
- Extract reusable widgets

**Phase 4: Refactor Application Layer**
- Move use cases to `application/`
- Merge `services/`, `scenarios/` into application layer

**Phase 5: Infrastructure Adapters**
- Move I/O to `infrastructure/persistence/`
- Move CV/ONNX to `infrastructure/compute/`

### 3.2 Risk Mitigation

| Risk | Mitigation |
|:-----|:-----------|
| **Broken imports** | Automated import rewriter tool |
| **Runtime failures** | Validation after each phase (`uv run automataii`) |
| **Incomplete migration** | Git worktree for parallel development |
| **Lost functionality** | Comprehensive test suite before migration |

### 3.3 Success Metrics

- [ ] Application starts without errors
- [ ] All tabs load correctly
- [ ] Mechanism design workflow works
- [ ] Blueprint export works
- [ ] Image processing works
- [ ] No import depth > 3 levels
- [ ] No circular dependencies

---

## IV. TACTICAL DECISIONS

### 4.1 Module Consolidation

| Current | Target | Rationale |
|:--------|:-------|:----------|
| `gui/` + `ui/` | `presentation/qt/` | Single UI layer |
| `animate/` + `animation/` | `domain/animation/` | Unified animation domain |
| `application/` + `services/` + `scenarios/` | `application/` | Clear use case layer |
| `core/models.py` | Split into domain models | Eliminate god object |
| `mechanisms/linkage/` + `mechanisms/linkages/` | `domain/mechanisms/linkages/` | Consistent naming |

### 4.2 Import Path Changes

**Before:**
```python
from automataii.gui.mechanisms.four_bar.mechanism import FourBarMechanism
from automataii.mechanisms.fourbar.compute import compute_fourbar_position
from automataii.ui.tabs.mechanism_design.tab import MechanismDesignTab
```

**After:**
```python
from automataii.domain.mechanisms.linkages.models import FourBarMechanism
from automataii.domain.mechanisms.linkages.compute import compute_fourbar_position
from automataii.presentation.qt.tabs.mechanism_design import MechanismDesignTab
```

### 4.3 Backwards Compatibility

**Option 1: Re-exports (Temporary)**
```python
# automataii/gui/mechanisms/four_bar/mechanism.py
from automataii.domain.mechanisms.linkages.models import FourBarMechanism
__all__ = ['FourBarMechanism']
```

**Option 2: Clean Break (Preferred)**
- Use automated import rewriter
- No backwards compatibility layer
- Faster, cleaner migration

---

## V. IMPLEMENTATION TOOLING

### 5.1 Required Tools

1. **Import Rewriter**
   - Parse all Python files
   - Build import dependency graph
   - Rewrite imports based on migration map
   - Validate syntax after rewrite

2. **File Mover**
   - Move files to target locations
   - Update `__init__.py` files
   - Preserve git history (`git mv`)

3. **Validation Runner**
   - Run `uv run automataii` after each phase
   - Check for import errors
   - Verify UI loads correctly

### 5.2 Validation Checkpoints

**After Each Phase:**
```bash
# 1. Syntax check
python -m py_compile src/automataii/**/*.py

# 2. Import check
python -c "import automataii"

# 3. Application launch
timeout 15 uv run automataii

# 4. Run test suite (if exists)
uv run pytest tests/
```

---

## VI. NEXT STEPS

1. **Review & Approve** this analysis
2. **Create migration tool** (`scripts/refactor_tool.py`)
3. **Execute Phase 1** (create target structure)
4. **Validate Phase 1** (`uv run automataii`)
5. **Execute remaining phases** iteratively

---

**Approval Required:** Review target architecture before proceeding.
