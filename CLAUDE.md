# Automataii

**Stack:** PySide6, uv, Hexagonal Arch (DDD).

## Quick Start
- **Run:** `uv run automataii` (Flags: `--debug`, `--editing`, `--experiment`)
- **Scenarios:** `uv run automataii --scenario <name> --scenario-output <dir>`
- **Test:** `uv run pytest`
- **Lint:** `uv run ruff check`, `uv run mypy src/automataii`

## Architecture (Hexagonal)
`src/automataii/`
1.  **domain/** (CORE): Pure logic. NO deps (Qt/IO).
    - *Mechanisms*: `core` (Protocols), `catalog` (Registry), `linkages`, `cam`.
    - *Kinematics*: `ik_manager.py`, `solvers`.
    - *Animation*: `arap.py`, `templates.py`.
2.  **presentation/** (UI): Qt-specific. Replaceable.
    - `qt/`: `main_window.py`, `tabs/`, `views/`, `graphics_items/`.
3.  **application/** (Use Cases): Orchestration.
    - `mechanism_foundry`, `mechanism_transfer`.
4.  **infrastructure/** (Adapters): IO, Compute (ONNX).
5.  **core/** (Legacy): Migrating.

**Rules:**
- **Imports:** Domain NEVER imports Presentation/Infra. Presentation/Infra import Domain.
- **Strict Typing:** No `Any`. Use `Pydantic`/`assert`.

## Key Components
- **IKManager:** `domain/kinematics/ik_manager.py` (Orchestrates IK).
- **MechanismRegistry:** `domain/mechanisms/catalog/registry.py`.

## Common Tasks
- **New Mechanism:** 1. Domain (`domain/mechanisms/<type>`), 2. Register, 3. UI (`presentation/qt/mechanisms`).
- **New Tab:** `presentation/qt/tabs/<name>_tab.py` -> Register in `main_window.py`.
