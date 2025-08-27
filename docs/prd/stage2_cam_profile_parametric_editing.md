Title: Stage 2 — Cam Profile Parametric Editing (Rise/Return/Dwell + Base/Eccentricity)

Background
- PAPER.md: cam parameters should be editable, and shape preserved under rotation. Current code supports center and follower rod length; full profile parameters (rise/return/dwell, base radius, eccentricity as lift) and multi‑handle editing are not yet exposed.

Problem Statement
- Designers need to modify cam pacing via rise/return/dwell angles and lift while maintaining rigid rotation of the profile.

Goals
- Expose base_radius, eccentricity (lift), rise_deg, return_deg, high_dwell_deg, low_dwell_deg in the parametric editor.
- Live rebuild of analytic pear‑cam profile used in MechanismVisualsFactory; rigid rotation only (no deformation).

Functional Requirements
- CamEditor:
  - Add radial handles for key profile angles or a compact panel with sliders (degrees) and numeric inputs.
  - Keep follower above cam (gravity convention) and validate rod length vs max radius.
- Visuals:
  - MechanismVisualsFactory already builds analytic pears; update to respect new parameters live.
- Constraints:
  - Maintain positive dwells; rise+return+dwells = 360°; limit eccentricity relative to base to prevent self‑intersection.

UX / UI
- Provide real‑time preview with an optional ghost overlay of the previous profile.
- Pause animation while adjusting parameters; resume on release.

Acceptance Criteria
- Editing angles updates the cam shape instantly with no per‑vertex scaling during rotation.
- Follower remains above cam; contact top aligns visually with rod.

Test Plan
- Unit: profile generator sums angles to 360°, maintains continuity, radii positive.
- Integration: UI handles adjust parameters; changes propagate to visuals and animation.

Implementation Notes
- Reuse _build_pear_cam_profile; factor parameters; store into mechanism layer params; route via ParametricEditingManager update hooks.

Milestones
1) Editor controls + wiring (1–2 days)
2) Visuals factory param integration (0.5 day)
3) Tests + UX polish (0.5 day)

