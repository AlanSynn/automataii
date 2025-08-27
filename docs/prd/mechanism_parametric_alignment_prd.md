Mechanism Tab — Parametric Editing Alignment PRD

Author: Automataii Team (owner: Alan Synn)
Scope: `MechanismDesignTab` parametric mode (handles, anchors, transform), `ParametricEditingManager`, `ParametricEditor` family
Goal: Eliminate misalignment between parametric handles/anchors and rendered mechanism geometry across zoom/pan, transforms, and mechanism types.

1) Problem Statement
- User impact: When entering Parametric Edit, draggable handles and anchors do not sit on top of the drawn mechanisms (4-bar pivots, coupler, cam center/follower, gears). Dragging feels “off,” and constraints are not respected visually.
- Symptoms reported:
  - Handles appear offset from expected pivot circles and coupler points.
  - Anchors do not remain aligned after zoom/pan.
  - Some constraints (vertical-only follower, radial cam control) are ignored.
  - Adjustments produce mechanism visuals that don’t match the new handle positions.

2) Likely Root Causes (Code Analysis)
- Handle geometry and position misuse (scene vs local):
  - `ParametricHandle` constructs the ellipse with scene coordinates baked into the item’s local rect: `QGraphicsEllipseItem(center.x() - r, center.y() - r, ...)`, then later calls `setPos(new_pos - r)`. This double-offsets and breaks alignment after movement.
  - Correct pattern: local rect centered at origin `(-r, -r, 2r, 2r)` + `setPos(scene_center)`; during drag, `setPos(new_scene_pos)` without subtracting radius.
- Missing/partial constraint logic:
  - Cam follower uses a `fixed_x` constraint in comments/usage, but `_apply_constraints` does not support `fixed_x` (horizontal lock). Radial constraints for cam profile (`min_radius`, `max_radius`, `center`, `angle`) are defined but never applied.
  - 4‑bar length constraints exist only for crank; other links lack symmetric constraints.
- Transform consistency (mechanism space ↔ scene space):
  - `MechanismDesignTab._get_scene_transform_function` maps mechanism coordinates into scene; parametric mode should use that for initial handle placement and an exact inverse for writing parameter changes back into mechanism parameter space.
  - `ParametricEditingManager` currently writes scene coordinates directly into `params` (e.g., `anchor1_x/y`, `crank_x/y`). This can drift from original mechanism coordinate frame and create scale/rotation inconsistencies.
- Coupler point scaling:
  - `_calculate_coupler_position` scales `coupler_point_x/y` by `transform_params['scale']`. Given `_get_scene_transform_function` divides by `scale` then applies `user_scale`, this may over/under-scale offsets depending on pipeline order.
- Visual update path and delta checks:
  - Visuals update from simulation data, while handles update `params` in scene units. If mapping is inconsistent, visuals and handles won’t coincide.
- Zoom invariance (optional):
  - Handles grow/shrink with zoom; intended? If not, `ItemIgnoresTransformations` should be used for fixed-pixel handles.

3) Goals & Acceptance Criteria
- Alignment:
  - G1: Pivot/anchor handles center within ≤ 1 px of corresponding mechanism pivot renderings at 100% zoom.
  - G2: Alignment error ≤ 2 px up to 2× zoom in/out.
- Constraints:
  - G3: Cam follower horizontal locked; only Y moves between defined min/max.
  - G4: Cam profile control points constrained by radial min/max around cam center at specified angle.
  - G5: 4‑bar link length constraints applied where appropriate to preserve geometry during drags.
- Transform consistency:
  - G6: Round‑trip scene drag → params → visuals → scene keeps handles and visuals coincident.
  - G7: Switching parametric mode on/off preserves alignment and param values consistently.

4) Non-Goals
- Replacing QGraphics with Qt Quick or fully GPU‑based renderer.
- Mechanism kinematics refactors beyond alignment/constraints.

5) Proposed Design & Changes
5.1 Handle Geometry and Positioning
- Change `ParametricHandle` to:
  - Use local rect centered at origin: `setRect(-r, -r, 2r, 2r)`.
  - Initial place via `setPos(scene_center)` instead of embedding scene coords in rect.
  - On drag: `setPos(new_scene_pos)` directly (no `- r`).
  - Optional: `setFlag(ItemIgnoresTransformations, True)` behind a setting to keep handles a constant on-screen size.

5.2 Constraint Engine
- Extend `_apply_constraints` to support:
  - `fixed_x`: lock x; only y changes.
  - Radial constraints `{ center, min_radius, max_radius, angle }` for cam profile points; project to the permitted radius on the given angle.
  - Symmetric link length constraints (where required) based on current anchor positions.
  - Grid snapping that adapts to view scale (optional improvement).

5.3 Transform Consistency and Round-Trip
- Introduce strict two-way transforms:
  - Use `to_scene = _get_scene_transform_function(layer_data)` for initial handle positions.
  - Use `to_mech = _get_inverse_scene_transform_function(layer_data)` when writing user drags back into params (store params in mechanism space, not scene space).
  - During visual updates, always derive scene geometry from mechanism space via `to_scene` to ensure consistency.

5.4 Coupler and Offsets
- Normalize coupler offsets: ensure `coupler_point_x/y` live in mechanism space. Map to scene with `to_scene` only during rendering/handle placement. Remove direct use of `transform_params['scale']` in offset application.

5.5 Visual Update Sequencing
- On handle move:
  1) Apply constraints in scene space (using scene handle pos).
  2) Convert constrained scene pos → mechanism space via inverse transform.
  3) Update `params` in mechanism space.
  4) Recompute dependent geometry in mechanism space.
  5) Re-render visuals by mapping to scene via `to_scene`.
  6) Reposition handles via `to_scene` from updated mechanism params (authoritative).
- Add small delta thresholds to avoid redundant QGraphics updates.

5.6 Zoom and Z-Order
- Keep handles above visuals: maintain high Z for handles; ensure skeleton/overlays don’t obscure.
- Optional: Offer “fixed handle size” toggle in Options → Performance (defer if scope creep).

6) Implementation Plan (Incremental)
- Step 1: Fix `ParametricHandle` rect/pos semantics; add optional `ItemIgnoresTransformations` flag.
- Step 2: Implement `fixed_x`, radial constraints; add tests by simulating drags.
- Step 3: Wire inverse transform usage in `ParametricEditingManager` and `ParametricEditor` updates; ensure params are mechanism-space canonical.
- Step 4: Remove ad‑hoc scale use in `_calculate_coupler_position`; compute in mechanism space.
- Step 5: Rework handle update loop to reproject from params→scene after every change.
- Step 6: Add debug overlay (toggle) to visualize:
  - Mechanism-space origin/axes mapped to scene
  - Anchor points before/after transform
  - Current constraint radii/lines
- Step 7: QA across mechanism types (4‑bar, cam/follower, gears, planetary) and zoom levels.

7) Risks & Mitigations
- Risk: Legacy params consumed elsewhere in scene units.
  - Mitigation: Introduce accessors to always convert mechanism→scene on read at boundaries.
- Risk: Visual flicker after reproject on each drag.
  - Mitigation: Coalesce updates; only update on drag move throttle (e.g., every 16 ms) and skip tiny deltas.
- Risk: Inverse transform numerical stability.
  - Mitigation: Clamp/guard in inverse as done in forward transform; unit tests on round‑trip equality within tolerance.

8) Validation & Acceptance Tests
- T1: 4‑bar anchors align with pivot circles within ≤1 px at 1× zoom; ≤2 px up to 2× zoom.
- T2: Dragging crank endpoint preserves crank length constraint relative to anchor1.
- T3: Cam center and follower remain vertically aligned (fixed x); follower obeys y‑bounds.
- T4: Cam profile control points move only along given angles within min/max radius.
- T5: Switching parametric mode on/off does not drift handle positions.
- T6: Export/blueprint path consistency unaffected (visuals and params agree).

9) Rollout Plan
- Phase A (1–2 days): Handle rect/pos fix + constraints, 4‑bar validation.
- Phase B (2 days): Two‑way transform integration and coupler normalization.
- Phase C (1 day): Debug overlays, polish, delta‑update coalescing.

10) Out of Scope / Future
- Add manipulator widgets for rotation/scale with screen‑space handles.
- Snapping to skeleton joints and feature points.

