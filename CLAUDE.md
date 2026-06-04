# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automataii is an interactive mechanism design and character animation platform. It combines mechanical linkage computation, kinematics, and a PyQt6 GUI for designing mechanisms, attaching them to characters, and animating the result.

Python >=3.10,<3.13. Tooling targets 3.12.

## Commands

```bash
# Dependencies (uv is the package manager)
uv sync                          # install deps
uv sync --group dev              # install with dev deps

# Run
uv run automataii                # launch GUI
uv run automataii --debug        # debug mode
uv run automataii --experiment   # hides Foundry/Options tabs

# Test
uv run pytest                    # all tests (tests/manual/ excluded via norecursedirs)
uv run pytest tests/test_foo.py  # single file
uv run pytest -k "test_name"    # single test by name
uv run pytest -m unit            # by marker (unit, integration, slow, core, gui, services)

# Quality
uv run ruff check src/           # lint
uv run ruff check src/ --fix     # lint + autofix
uv run ruff format src/          # format
uv run mypy src/automataii       # type check
make quality                     # lint + format-check + type-check combined

# Build (PyInstaller / release)
make build                       # distribution artifact; macOS uses signed + notarized release flow
make build-macos                 # signed + notarized macOS release
```

## Architecture

Clean Architecture with strict inward dependency flow:

```
Domain (pure Python) <-- Application <-- Presentation (Qt)
                              |
                        Infrastructure
```

### Layer Rules

- **Domain** (`src/automataii/domain/`): Zero UI deps. Frozen dataclasses, protocols, pure computation. Contains mechanisms (linkages, cam), kinematics, animation, character, skeleton.
- **Application** (`src/automataii/application/`): Use-case orchestration. Managers (SkeletonManager, MechanismManager, ProjectDataManager). Qt signals as Observer for cross-component communication.
- **Infrastructure** (`src/automataii/infrastructure/`): DI container (singleton/transient/scoped lifetimes), event bus (pub/sub with priority), Pydantic validation schemas, SVG/PNG generation adapters.
- **Presentation** (`src/automataii/presentation/qt/`): PyQt6 UI. Tabs, dialogs, animation scheduler, mechanism visualizers, renderers.
- **Shared** (`src/automataii/shared/`): Cross-layer types with no deps. `Result[T, E]` (Ok/Err), `Point2D`.

### Key Patterns

- **Strategy + Registry**: Mechanism computation dispatches by `bar_count` (4/5/6-bar). `UnifiedLinkageMechanism` is the entry point for all linkage types.
- **Two registries**: Domain `MechanismRegistry` (type -> Mechanism protocol impl) and Presentation `MechanismRegistry` (type -> mechanism/editor/serializer triple).
- **Result monad**: `from automataii.shared import Result, Ok, Err`. Logic returns `Result[T, E]`; exceptions only for system panic.
- **Protocol contracts**: `Mechanism`, `MechanismVisualizerProtocol`, `MechanismRendererProtocol` -- all `@runtime_checkable`.
- **Event Bus**: `EventBus` with priority ordering, sync/async/queued modes. Immutable event hierarchy: DomainEvent, SystemEvent, UIEvent.
- **MVP Presenter**: Mechanism design tab uses `presenter.py` + `view_protocol.py` + `controller_adapter.py`.
- **DI Container**: Constructor injection with lifetime management and circular-dep detection.

### Mechanism Design Tab (most complex)

`src/automataii/presentation/qt/tabs/mechanism_design/` -- decomposed into:
- `tab.py` (widget), `presenter.py` (MVP), `view_protocol.py` (interface)
- `components/` (animation lifecycle, visual animator, skeleton viz, scene transforms)
- `parametric/` (handles, controllers, strategies for interactive parameter editing)
- `services/` (anchor movement, animation frame coordination, mechanism instantiation, etc.)
- `path_trace_manager.py` (path recording/visualization)

### Animation System

- `CentralAnimationScheduler` / `AcceleratedAnimationScheduler` (off-thread compute, 60 FPS target)
- Single QTimer, priority-based updates, frame skipping

### Supported Mechanisms

- **Linkages**: 4-bar, 5-bar, 6-bar (via `UnifiedLinkageMechanism` dispatching by `bar_count`)
- **Cam-follower**: Parametric cam profile generation (NumPy vectorized)
- **Gears**: Simple gear pair, planetary gear (visualization layer)

## Test Structure

- `tests/golden_master/` -- snapshot regression tests with stable float normalization. Use `--update-snapshots` to regenerate.
- `tests/manual/` -- excluded from `uv run pytest` (via `norecursedirs = manual` in pytest.ini).
- Markers: `@pytest.mark.unit`, `integration`, `slow`, `core`, `gui`, `services`.

## Code Conventions

- Line length: 100 (ruff)
- Frozen dataclasses for all domain types (`frozen=True`)
- No `Any` types. Use `Protocol`, `TypeVar`.
- `__init__.py` re-exports are allowed (F401 ignored)
- Ruff rules: E, W, F, I, B, C4, UP
