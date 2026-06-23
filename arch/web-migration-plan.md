# Automataii Frontend-Only Web Migration Plan

## Objective
Migrate Automataii into a browser-runnable web application while preserving the original PyQt product intent: character selection/recognition, path editing, mechanism design, mechanism foundry exploration, project persistence, and fabrication export. The web app must run without a separately deployed backend.

## Non-negotiables
- Functional equivalence before polish.
- Real browser ONNX Runtime Web support for segmentation/inference.
- ONNX must be optional and switchable off.
- Original repository workflows must be traceable to explicit web behavior.
- Added web-only migration features must be documented.
- No backend, database, private key, cloud service, or server auth dependency.
- Any missing behavior must be tracked with evidence, not hidden.

## Source-of-truth evidence
- Workflow shell: `src/automataii/presentation/qt/main_window.py`
- Application actions: `src/automataii/presentation/qt/actions/action_manager.py`
- Character/image workflow: `src/automataii/presentation/qt/tabs/image_processing_tab.py`
- Path editor workflow: `src/automataii/presentation/qt/tabs/editor/`
- Mechanism design workflow: `src/automataii/presentation/qt/tabs/mechanism_design/`
- Mechanism foundry workflow/content: `src/automataii/application/mechanism_foundry/`, `resources/mechanism_content/`
- Project contracts: `src/automataii/application/project/models.py`, `serializer.py`
- Fabrication/blueprint contracts: `src/automataii/application/blueprint/`, `fabrication/`, `resources/blueprints/`
- Existing web migration: `web/`

## Architecture decision
Use a static browser app under `web/` with small local service modules instead of introducing a frontend framework or backend emulator server.

- UI: native HTML/CSS/JS tabs and dialogs.
- State: one browser app state object + undo/redo stack.
- Persistence: LocalStorage for current project, autosave, and settings.
- Project files: `.automataii` JSON import/export via File/Blob APIs.
- Inference: optional `onnxruntime-web`, lazy-loaded only in ONNX mode.
- Camera: browser `navigator.mediaDevices.getUserMedia`.
- Fabrication exports: generated SVG/JSON, browser print-to-PDF, and local ZIP package.

## Execution plan
1. Create root `arch/` documentation and traceability matrix.
2. Audit original repo features against current `web/` implementation.
3. Patch only confirmed functional gaps.
4. Add/update tests for every non-trivial branch.
5. Run lint, unit/static tests, smoke, real browser smoke, build, vendor asset check, and npm audit.
6. Run independent code review and QA verification gates.
7. Keep `arch/feature-traceability.md` updated as the missing-feature tracker.

## Current implementation status
The web migration already implements the core workflow and browser ONNX support. This pass focuses on root documentation, explicit traceability, and any confirmed omissions from the original repository audit.
