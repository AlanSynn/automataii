# MM-1.2 — MechanismDesignController

Date: 2025-10-19  
Scope: Application-layer controller + view-model for Mechanism Design workflows.

## Deliverables
- `automataii/application/mechanism_design/state.py`: immutable view-models (`PartPath`, `MechanismLayer`, `Recommendation`, `MechanismDesignState`).
- `automataii/application/mechanism_design/controller.py`: orchestrator with telemetry, listener support, and pure state transitions.
- `automataii/gui/tabs/mechanism_design/controller_adapter.py`: bridge converting Qt paths to domain-friendly structures (feature flagged via `AUTOMATAII_MECH_CONTROLLER`).
- Tests (`tests/test_mechanism_design_controller.py`) validating state updates, recommendation flow, and layer application.

## Controller Responsibilities
- Maintain immutable state and notify listeners on change.
- Convert editor paths into application state (`update_paths`).
- Request mechanism recommendations through injected service; store results in state.
- Apply recommendation by delegating to mechanism generation service and updating layers.
- Manage part enablement, selections, animation and parametric flags.
- Provide serialization helper (`state_to_serializable`) for debugging.

## Dependencies & Interfaces
- `MechanismRecommendationService`: protocol returning iterable of `Recommendation` for part/path.
- `MechanismGenerationService`: protocol to build and clear mechanism layers.
- Telemetry spans (e.g., `application.mechanism_design.update_paths`, `.recommend`, `.apply_recommendation`).

## Open Integration Tasks
1. Wire adapter into `MechanismDesignTab` behind `AUTOMATAII_MECH_CONTROLLER` flag (MM-1.3/2.x).
2. Implement concrete services wrapping existing `MechanismService` and recommendation dialog loader.
3. Extend controller to cover animation trace management and blueprint orchestration.
4. Add unit tests for adapter conversions once integrated with Qt bridge logic.
