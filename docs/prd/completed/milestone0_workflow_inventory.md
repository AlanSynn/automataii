# Milestone 0 — UI Workflow Inventory

Date: 2025-10-19  
Scope: Automataii desktop application (PyQt6 shell)

| # | Workflow | Priority | Current QA | Automation Target | Telemetry Hook | Notes |
|---|----------|----------|------------|-------------------|----------------|-------|
| 1 | Launch app and initialize services | P0 | Manual smoke | Scenario harness starts binary headless, assert telemetry heartbeat | `telemetry_span("app.startup")` (planned) | Baseline cold-start ≤ 8 s |
| 2 | Open existing project from disk | P0 | Manual w/ regression list | Scripted scenario loads sample project, confirms tabs populated | `telemetry_span("core.project.open")` (planned) | Requires fixture repo with trimmed assets |
| 3 | Save active project snapshot | P0 | Manual only | Scenario issues save command and asserts output files | `telemetry_span("core.project.save")` (planned) | Hook into `ProjectManager.save_project` |
| 4 | Import character sketch & run segmentation (Image Processing tab) | P0 | Manual path | Automate via harness with seeded PNG fixture | `telemetry_span("ui.image_processing.process_image")` | Instrumented in Milestone 0 |
| 5 | Manual skeleton edit & extend | P1 | Manual path | Capture scripted pointer events manipulating joints | Pending | Needs deterministic input abstraction |
| 6 | Define freehand motion path in Editor tab | P0 | Manual path | Scenario replays control-point edits and asserts resulting path | Pending | Requires event replay driver |
| 7 | Play/stop motion path simulation | P1 | Manual | Capture frame metrics + event log asserts | Pending | Add telemetry around `_play_simulation_clicked` |
| 8 | Mechanism recommendation from motion path | P0 | Manual | Scenario seeds motion path, checks recommendation list + metadata | Pending | Wrap `MechanismDesignTab._trigger_mechanism_recommendation` |
| 9 | Parametric handle adjustments (Mechanism Design) | P1 | Manual | Scenario drives deterministic handle drags and validates state diff | Pending | Telemetry when param handles mutate state |
|10 | Timeline playback in mechanism preview | P1 | Manual | Scenario sweeps timeline slider, verifies keyframe states | Pending | Log `timeline.update` spans (planned) |
|11 | Export full blueprint (legacy exporter) | P0 | Manual regression | Automation verifies SVG output hash + metadata | `telemetry_span("ui.blueprint.export_all")` | Instrumented in Milestone 0 |
|12 | Export single mechanism blueprint | P0 | Manual regression | Automation writes to temp path, validates SVG sections | `telemetry_span("ui.blueprint.export_mechanism")` | Instrumented in Milestone 0 |
|13 | Mechanism Foundry workshop: browse catalog | P1 | Manual | Scenario selects mechanisms, asserts component inventory | Pending | Add telemetry around catalog load |
|14 | Mechanism Foundry interactive controls (speed, parameters) | P1 | Manual | Scenario exercises sliders/checkboxes, checks derived outputs | Pending | Telemetry via `EnhancedMacanismTab._on_speed_changed` etc. |
|15 | Options tab theme toggle | P2 | Manual | Automate toggle + screenshot diff | Pending | Telemetry on `_apply_theme` planned |

## Next Actions
- Prioritise telemetry hooks marked “planned” for Milestone 1 so automated scripts can collect latency baselines.
- For P0 workflows without instrumentation, capture quick timings via manual span wrappers during test runs.
- Publish fixtures (sample project, PNG, mechanism configs) under `tests/fixtures/milestone0/` for repeatability.
