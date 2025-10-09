# MM-2.2 — IK Service Abstraction

Date: 2025-10-19  
Scope: Introduce application-layer state + service for inverse-kinematics workflows.

## Deliverables
- `automataii/application/kinematics/state.py`: immutable `IKState` and observable `IKStateStore` capturing skeleton data, project parts, animation timing, and mechanism targets.
- `automataii/application/kinematics/service.py`: `IKService` façade with telemetry-instrumented methods for updating skeleton/project data, controlling animation, and tracking mechanism targets.
- Tests in `tests/test_ik_service.py` exercising state transitions.

## Key Points
- IK logic remains in `IKManager`, but state transitions now have a toolkit-agnostic representation ready for future integration.
- Service exposes primitives (`update_skeleton`, `start_animation`, `set_mechanism_target`, etc.) that mirror the responsibilities currently living in the UI/Qt layer.
- Telemetry spans (`application.ik.*`) aligned with the PRD targets to monitor future regressions.

## Next Steps
1. Adapt `IKManager` to use `IKService` internally (strangler pattern) and emit events via state listeners.
2. Integrate the service with `EditorView` and Mechanism Design flows once controllers adopt it.
3. Expand coverage to include IK solving outputs (joint angles, dynamic joints) in the state once extracted from the legacy manager.
