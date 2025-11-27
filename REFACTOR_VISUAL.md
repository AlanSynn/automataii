# Automataii Architecture: Current vs Target

## Visual Comparison

### CURRENT STRUCTURE (Complex, Mixed Concerns)

```
src/automataii/
│
├── 🔴 gui/                          # UI Layer (Qt)
│   ├── tabs/
│   │   ├── mechanism_design/
│   │   │   └── parametric/
│   │   │       ├── handles/         # 5+ levels deep!
│   │   │       ├── controllers/
│   │   │       ├── services/
│   │   │       └── strategies/
│   │   ├── mechanism_foundry/
│   │   └── ...
│   ├── mechanisms/                  # 🔴 Mixed: UI + Domain logic
│   │   ├── four_bar/
│   │   ├── visualization/
│   │   └── blueprint/
│   ├── widgets/
│   └── ...
│
├── 🔴 ui/                           # 🔴 DUPLICATE of gui/
│   ├── tabs/
│   │   ├── mechanism_design/        # 🔴 DUPLICATE structure
│   │   │   └── parametric/          # 🔴 Deep nesting again
│   │   └── mechanism_foundry/
│   └── rendering/
│
├── mechanisms/                      # Domain Logic (Mechanisms)
│   ├── linkages/                    # ✅ Good structure
│   │   ├── strategies/
│   │   └── validators/
│   ├── fourbar/
│   ├── fivebar/
│   ├── sixbar/
│   ├── cam/
│   └── core/
│
├── 🔴 animate/                      # Animation logic
├── 🔴 animation/                    # 🔴 DUPLICATE of animate/
│
├── 🔴 application/                  # Application services
├── 🔴 services/                     # 🔴 DUPLICATE of application/
├── 🔴 scenarios/                    # 🔴 OVERLAPS with application/
│
├── core/                            # Core models & infrastructure
│   ├── events/
│   ├── state/
│   ├── serialization/               # 🔴 Should be in infrastructure
│   └── project/                     # 🔴 Should be in infrastructure
│
├── kinematics/
├── domain/                          # 🔴 Underutilized
├── utils/
└── config/

Issues:
🔴 Duplication: gui/ vs ui/, animate/ vs animation/, application/ vs services/
🔴 Deep nesting: 5+ levels in parametric/
🔴 Mixed concerns: gui/mechanisms/ contains domain logic
🔴 Unclear boundaries: application/, services/, scenarios/ overlap
🔴 Misplaced infrastructure: serialization in core/
```

---

### TARGET STRUCTURE (Clean, Hexagonal Architecture)

```
src/automataii/
│
├── 🟢 domain/                       # CORE: Pure business logic
│   │                                # ✅ No external dependencies
│   │                                # ✅ Framework-agnostic
│   ├── mechanisms/
│   │   ├── protocols.py             # Mechanism, Validator, Strategy
│   │   ├── catalog.py               # Registry pattern
│   │   ├── linkages/
│   │   │   ├── models.py            # LinkageConfig, LinkageState
│   │   │   ├── compute.py           # Pure functions
│   │   │   ├── validators/          # Grashof, collision
│   │   │   └── strategies/          # FourBar, FiveBar, SixBar
│   │   ├── cam/
│   │   │   ├── models.py
│   │   │   └── compute.py
│   │   └── gears/
│   │       ├── models.py
│   │       └── compute.py
│   │
│   ├── animation/                   # ✅ Unified (no duplication)
│   │   ├── models.py                # BodyPart, Skeleton
│   │   ├── arap.py                  # ARAP algorithm
│   │   └── templates.py
│   │
│   ├── kinematics/
│   │   ├── models.py
│   │   └── solvers/
│   │
│   └── blueprint/
│       ├── models.py
│       └── generator.py
│
├── 🟢 application/                  # PORTS: Use cases
│   │                                # ✅ Orchestrates domain logic
│   │                                # ✅ Framework-agnostic
│   ├── mechanisms/
│   │   ├── foundry.py               # Browse catalog
│   │   ├── design.py                # Design workflow
│   │   └── transfer.py              # Transfer to skeleton
│   │
│   ├── animation/
│   │   ├── pose_estimation.py
│   │   └── character_animation.py
│   │
│   ├── blueprint/
│   │   └── export.py
│   │
│   └── scenarios/                   # ✅ Test scenarios here
│       ├── blueprint_export.py
│       └── image_processing.py
│
├── 🟢 infrastructure/               # ADAPTERS: External dependencies
│   │                                # ✅ Implements domain protocols
│   │                                # ✅ Framework-specific
│   ├── persistence/
│   │   ├── serializers/
│   │   │   ├── json_serializer.py
│   │   │   └── yaml_serializer.py
│   │   └── project/
│   │       ├── file_manager.py
│   │       └── project_format.py
│   │
│   ├── compute/
│   │   ├── onnx_runtime.py          # ONNX adapter
│   │   └── cv_algorithms.py         # OpenCV adapter
│   │
│   └── telemetry/
│       ├── logging.py
│       └── metrics.py
│
├── 🟢 presentation/                 # ADAPTERS: UI layer
│   │                                # ✅ Qt-specific (replaceable)
│   │                                # ✅ Max 3 levels deep
│   ├── qt/
│   │   ├── main_window.py
│   │   │
│   │   ├── tabs/                    # ✅ Flattened (max 3 levels)
│   │   │   ├── mechanism_foundry.py
│   │   │   ├── mechanism_design.py
│   │   │   ├── image_processing.py
│   │   │   └── options.py
│   │   │
│   │   ├── widgets/
│   │   │   ├── editor/              # Canvas editors
│   │   │   │   ├── parametric_editor.py
│   │   │   │   └── segmentation_editor.py
│   │   │   ├── controls/            # Parameter controls
│   │   │   │   └── parameter_panel.py
│   │   │   └── displays/            # Info displays
│   │   │       └── mechanism_info.py
│   │   │
│   │   └── dialogs/
│   │       ├── camera_dialog.py
│   │       └── recommendation_dialog.py
│   │
│   └── rendering/                   # ✅ Separated rendering
│       ├── protocols.py             # Renderer protocol
│       ├── factory.py
│       └── renderers/
│           ├── mechanism_renderer.py
│           ├── skeleton_renderer.py
│           └── blueprint_renderer.py
│
└── 🟢 shared/                       # SHARED KERNEL
    │                                # ✅ Used by all layers
    ├── events/                      # Event bus (pub/sub)
    │   ├── base.py
    │   ├── event_bus.py
    │   └── decorators.py
    │
    ├── state/                       # State management
    │   ├── store.py
    │   ├── middleware.py
    │   └── selectors.py
    │
    ├── config/
    │   └── z_indices.py
    │
    ├── types/                       # Shared type definitions
    │   └── common.py
    │
    └── utils/                       # Utilities
        ├── paths.py
        └── logging_config.py

Benefits:
✅ No duplication
✅ Clear boundaries (Domain → Application → Adapters)
✅ Testable (domain is pure, no dependencies)
✅ Replaceable (can swap Qt for web UI)
✅ Shallow nesting (max 3 levels)
✅ Single responsibility
```

---

## Dependency Flow Visualization

### CURRENT (Messy, Circular Dependencies)

```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  gui/ ←──────→ ui/         🔴 Circular dependency!          │
│   ↓ ↑          ↓ ↑                                           │
│   ↓ └──────────┘ ↑                                           │
│   ↓              ↑                                           │
│   ↓              ↑                                           │
│  mechanisms/  services/    🔴 UI imports domain directly!    │
│   ↓ ↑          ↓ ↑                                           │
│   ↓ └──────────┘ ↑                                           │
│   ↓              ↑                                           │
│  core/        utils/       🔴 Everything imports core!       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### TARGET (Clean, Unidirectional Flow)

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation                            │
│                  (presentation/qt/)                          │
│                                                               │
│  ✅ Depends on Application & Domain (via interfaces)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ implements
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   Application Services                       │
│                    (application/)                            │
│                                                               │
│  ✅ Orchestrates domain logic                               │
│  ✅ Defines ports (interfaces)                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ uses
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                     Domain (Core)                            │
│                      (domain/)                               │
│                                                               │
│  ✅ Pure business logic                                     │
│  ✅ No external dependencies                                │
│  ✅ Framework-agnostic                                      │
└─────────────────────────────────────────────────────────────┘

                  ┌────────────────────┐
                  │   Infrastructure    │
                  │ (infrastructure/)   │
                  │                     │
                  │ ✅ Implements ports │
                  │ ✅ External deps    │
                  └────────────────────┘
                           ↑
                           │ depends on
                           │
                    (Domain interfaces)
```

---

## Key Improvements

| Aspect | Current | Target | Benefit |
|:-------|:--------|:-------|:--------|
| **Duplication** | 3 pairs | None | -40% files |
| **Max Nesting** | 7 levels | 3 levels | +200% readability |
| **Circular Deps** | ~15 | 0 | +100% testability |
| **Domain Purity** | Mixed | Pure | +300% testability |
| **UI Coupling** | Tight | Loose | Replaceable |
| **Import Depth** | `automataii.ui.tabs.mechanism_design.parametric.handles.base` | `automataii.presentation.qt.widgets.editor` | Cleaner |

---

## Migration Impact

### Files Affected by Phase

| Phase | Files Moved | Imports Rewritten | Risk |
|:------|:------------|:------------------|:-----|
| 1 | 0 | 0 | None (structure only) |
| 2 | ~60 | ~300 | Medium |
| 3 | ~80 | ~400 | High |
| 4 | ~20 | ~100 | Medium |
| 5 | ~15 | ~80 | Low |
| **Total** | **~175** | **~880** | Managed |

### Validation After Each Phase

✅ Syntax check (py_compile)
✅ Import resolution (`import automataii`)
✅ Application launch (`uv run automataii`)

---

## Example Import Changes

### BEFORE (Complex, Deep)

```python
from automataii.gui.mechanisms.four_bar.mechanism import FourBarMechanism
from automataii.mechanisms.fourbar.compute import compute_fourbar_position
from automataii.ui.tabs.mechanism_design.parametric.handles.joint_handle import JointHandle
from automataii.gui.tabs.mechanism_design_tab import MechanismDesignTab
```

### AFTER (Clean, Shallow)

```python
from automataii.domain.mechanisms.linkages.models import FourBarMechanism
from automataii.domain.mechanisms.linkages.compute import compute_fourbar_position
from automataii.presentation.qt.widgets.editor import JointHandle
from automataii.presentation.qt.tabs.mechanism_design import MechanismDesignTab
```

**Improvement:**
- 7 levels → 3 levels (57% reduction)
- Clear layer separation
- Easy to understand module purpose

---

## Success Metrics

**Quantitative:**
- [ ] Import depth reduced by >50%
- [ ] File duplication eliminated (100%)
- [ ] Circular dependencies eliminated (100%)
- [ ] Application starts in <5 seconds

**Qualitative:**
- [ ] Clear separation of concerns
- [ ] Easy to navigate codebase
- [ ] Easy to add new mechanisms
- [ ] Easy to swap UI framework
- [ ] Easy to test domain logic

---

**Ready for execution?** Review this document and approve before running Phase 1.
