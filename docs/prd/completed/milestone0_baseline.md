# Milestone 0 Baseline — Modular UI & Core Refactor

_Date_: 2025-10-19  
_Scope_: `src/automataii`

## 1. LOC Snapshot
- Top oversized modules (≥600 LOC):
  - `automataii/gui/tabs/mechanism_design_tab.py` — 4,648
  - `automataii/ui/tabs/mechanism_foundry/enhanced_macanism_tab.py` — 3,483
  - `automataii/generation/blueprint_optimizer.py` — 2,355
  - `automataii/gui/tabs/editor_tab.py` — 2,294
  - `automataii/kinematics/ik_manager.py` — 1,888
- High-density directories (≥2,000 LOC):
  - `automataii/gui/tabs` — 11,185
  - `automataii/generation` — 5,221
  - `automataii/gui` — 4,934
  - `automataii/ui/tabs/mechanism_foundry` — 3,504
  - `automataii/core` — 2,897
  - `automataii/animate` — 2,503

## 2. Naive Complexity Indicator
- AST branch counts highlight hotspots:
  - `automataii/gui/tabs/mechanism_design_tab.py` — 1,244
  - `automataii/kinematics/ik_manager.py` — 505
  - `automataii/ui/tabs/mechanism_foundry/enhanced_macanism_tab.py` — 474
  - `automataii/gui/tabs/editor_tab.py` — 459
  - `automataii/gui/tabs/parametric_editing_manager.py` — 383
- Recommendation: target these modules first for decomposition into view-models, command handlers, and strategies.

## 3. Import Fan-Out
- Files with highest dependency breadth (unique top-level imports):
  - `automataii/core/project/serialization.py` — 14
  - `automataii/core/project/file_integration.py` — 14
  - `automataii/animate/body_parts_extractor.py` — 13
  - `automataii/kinematics/ik_manager.py` — 11
  - `automataii/gui/dialogs/recommendation_dialog.py` — 11
- Distribution summary:
  - 11–14 imports: 6 files
  - 6–10 imports: 38 files
  - ≤5 imports: 84 files

## 4. Proposed Measurements to Capture Next
- Runtime latency baselines for top 10 workflows.
- Manual test case inventory mapped to scenario automation plan.
- Asset size and render time stats for representative scenes.
- Dead-code verification: confirm import graph findings (99 modules without inbound static references) and classify into entry points, dynamic loads, or removal targets.
- Automate vulture runs via `scripts/run_dead_code_scan.sh` (uses `uv run --with vulture` and writes `docs/prd/vulture_<date>.txt`).

## 5. Notes
- Data gathered via ad-hoc Python scripts (available in shell history). Integrate into repeatable tooling during Milestone 1.
- Initial dead-code cleanup (2025-10-19): removed obsolete modules/scripts
  - Animation utilities: `animate/image_to_animation.py`, `animate/interactive_body_editor.py`
  - Legacy tooling: `carsegnet/`, `generate_animations.py`, `generate_comprehensive_dataset.py`, `print_sys_path.py`, `visualize_dataset.py`, `services/inference_service.py`
  - Unused GUI/manual artifacts: `gui/tabs/mechanism_design_tab.bak*`, `ui/tabs/mechanism_foundry/hci/`
  - Dormant utils: `utils/helpers.py`, `utils/image_utils.py`, `utils/path_utils.py`, `utils/svg_utils.py`
- Telemetry scaffolding landed via `automataii.core.telemetry.telemetry_span`; initial hooks wired for image processing and blueprint export.
- Workflow inventory tracked in `docs/prd/milestone0_workflow_inventory.md` for automation planning.
- Use `scripts/run_dead_code_scan.sh` (uv) to regenerate Vulture report artifacts on a host machine.
