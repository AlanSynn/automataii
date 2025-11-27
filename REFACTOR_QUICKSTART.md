# Refactoring Quick Start Guide

## TL;DR

```bash
# 1. Analyze current structure
python3 scripts/refactor_tool.py --analyze

# 2. Preview changes (safe, no modifications)
python3 scripts/refactor_tool.py --phase 1 --dry-run

# 3. Execute Phase 1
python3 scripts/refactor_tool.py --phase 1

# 4. Validate
uv run automataii

# 5. Continue with remaining phases
python3 scripts/refactor_tool.py --phase 2
python3 scripts/refactor_tool.py --phase 3
python3 scripts/refactor_tool.py --phase 4
python3 scripts/refactor_tool.py --phase 5

# If anything breaks:
python3 scripts/refactor_tool.py --restore
```

## Current State

- **232 Python files**
- **~60k LOC**
- **18 top-level modules**
- **Issues:**
  - Duplication: `gui/` vs `ui/`, `animate/` vs `animation/`
  - Deep nesting: 5-7 levels in `ui/tabs/mechanism_design/parametric/`
  - Mixed concerns: UI + domain logic in same modules
  - Unclear boundaries between `application/`, `services/`, `scenarios/`

## Target Architecture

```
domain/              # Pure business logic (no dependencies)
application/         # Use cases (orchestrates domain)
infrastructure/      # External adapters (DB, ONNX, CV)
presentation/        # UI layer (Qt, replaceable)
shared/             # Shared utilities (events, state, config)
```

## Migration Strategy

| Phase | Task | Duration | Risk |
|:------|:-----|:---------|:-----|
| **1** | Create structure | 5 min | None |
| **2** | Extract domain | 30 min | Medium |
| **3** | Consolidate UI | 45 min | High |
| **4** | Refactor app layer | 20 min | Medium |
| **5** | Infrastructure | 20 min | Low |

**Total: 2-3 hours**

## Safety Features

✅ **Automatic backups** before each phase
✅ **Git integration** (preserves history)
✅ **Dry-run mode** (preview without changes)
✅ **Validation gates** (syntax, imports, app launch)
✅ **One-click restore** if anything breaks

## Key Documents

1. **REFACTOR_ANALYSIS.md** - Detailed architectural analysis
2. **REFACTOR_VISUAL.md** - Visual before/after comparison
3. **scripts/REFACTOR_README.md** - Complete tool documentation
4. **scripts/refactor_tool.py** - Migration orchestration tool

## Decision Point

**Before proceeding, confirm:**
- [ ] Current branch is `refactoring/mech_design` (or create new branch)
- [ ] All changes committed (clean git status preferred)
- [ ] Application currently works (`uv run automataii`)
- [ ] You have 2-3 hours available
- [ ] You've reviewed target architecture

## Execute

```bash
# Start with Phase 1 (safest)
python3 scripts/refactor_tool.py --phase 1

# Then validate
uv run automataii

# If successful, proceed to Phase 2
python3 scripts/refactor_tool.py --phase 2

# Continue...
```

## Emergency Rollback

```bash
python3 scripts/refactor_tool.py --restore
```

---

**Questions?** See `scripts/REFACTOR_README.md` for detailed documentation.
