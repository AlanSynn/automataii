Title: Stage 1 — Motion Path Smoothing & Feasibility Snapping

Background
- PAPER.md requires a tolerance‑based smoothing that preserves extremes and shows a dual‑track preview (raw vs smoothed). It also calls for snapping infeasible motion curves to the nearest realizable trajectory while keeping the original visible for reference.
- Current status: EditorTab has a Smoothness slider, and EditorView generates Catmull‑Rom–like splines with Bezier approximation. However, the smoothing control is not tolerance‑based nor designed to preserve extremes, and there is no “nearest feasible” snapping.

Problem Statement
- Users need controllable smoothing that retains expressive extrema while removing jitter. When motions exceed feasible regions for the selected joint/mechanism, the system should suggest and visualize the nearest realizable alternative without losing user intent.

Goals
- Provide tolerance‑based smoothing that preserves extreme poses.
- Show both raw and smoothed curves concurrently.
- Implement “nearest feasible trajectory” snapping and display both the original and corrected versions.
- Keep interactions real‑time on laptop hardware.

Non‑Goals
- Global mechanism optimization (covered in Stage 2 optimization PRD).
- Extending IK solver internals beyond what’s necessary for feasibility evaluation.

User Stories
- As a user, I can adjust a smoothing slider and see my raw path (green) and smoothed path (purple) simultaneously.
- As a user, if my path is infeasible, the system overlays the nearest feasible trajectory while keeping my original visible.

Functional Requirements
- Smoothing:
  - Implement tolerance‑based simplification (e.g., Ramer–Douglas–Peucker with tolerance τ) that preserves original path endpoints and extreme points (peaks/valleys) detected via curvature/turning angle thresholds.
  - Offer a single “Smoothness” control that maps to τ with a perceptual curve (low values gentle, high values aggressive) and a toggle to “Preserve Extremes”.
  - Generate Catmull–Rom spline over simplified control points; expose tension parameter (fixed default 0.5 for now).
- Dual‑track rendering:
  - Raw path: dashed red/green; Smoothed path: solid blue/purple; Legend in the view toolbar.
- Feasibility snapping:
  - Integrate a feasibility checker per target joint using IKManager limits (bone length constraints, bend direction, reachable workspace) to compute a nearest feasible path via projection (minimize L2 distance along normalized arc‑length parameterization).
  - If a mechanism is already assigned, optionally use mechanism path reachable set approximation (coarse) for snapping; otherwise, default to joint‑reach feasibility.
  - Show a translucent corrected path and a small banner “Corrected for feasibility” with undo/accept.

UX / UI
- EditorTab: extend “Smoothness” control with a small caret menu offering “Preserve Extremes” toggle and “Spline Tension” (advanced).
- Add a status line in motion path group when snapping is active with “Revert” and “Accept” buttons.

APIs / Data Flow
- EditorView
  - add_smoothing_options({preserve_extremes: bool, tension: float})
  - compute_smoothed_path(raw: QPainterPath, τ: float, preserve_extremes: bool) -> QPainterPath
- IKManager (feasibility)
  - check_feasible(segment_points: list[QPointF], joint_id: str) -> bool
  - nearest_feasible_path(path: QPainterPath, joint_id: str) -> QPainterPath
- MechanismDesignTab (optional)
  - if mechanism exists for part, provide reachability approximation hook.

Acceptance Criteria
- “Preserve Extremes” on: extreme peaks/valleys (local maxima/minima along principal motion axis) remain within 1 pixel of raw path; slider reduces intermediate jitter.
- Dual‑track preview shows both raw and smoothed concurrently without frame drops; latency < 50 ms for 500 control points.
- For infeasible paths, corrected overlay appears; accepting the correction updates the working path and leaves a small breadcrumb to revert.

Test Plan
- Unit: geometry simplification preserves extremes (synthetic sine with noise), tolerance mapping, spline creation.
- Integration: draw a zig‑zag path; verify smoothing reduces zig‑zags while keeping apexes; check feasibility correction on an out‑of‑reach path for a forearm.
- Performance: 1000‑point path smoothing within 30 ms on a 13” laptop CPU.

Implementation Notes
- Reuse EditorView._create_spline_path; add a pre‑step for RDP simplification and extremes preservation.
- IK feasibility: project each sample point to reachable annulus with bend constraints; for mechanisms, fallback to joint feasibility until Stage 2 optimization is in place.

Dependencies
- IKManager for joint reach/bend constraints.
- No external libs required beyond numpy.

Risks / Mitigations
- Over‑smoothing undermines intent → extremes preservation toggle + preview.
- Snapping may confuse users → keep original visible; explicit accept/revert.

Milestones
1) Geometry module (RDP + extremes) + dual‑track (2 days)
2) IK feasibility checker + projection (2–3 days)
3) UI wiring + tests + docs (2 days)

