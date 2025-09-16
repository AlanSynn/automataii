Title: Stage 2 — Guardrails & Diagnostics Overlays

Background
- PAPER.md highlights guard‑aware editing: transmission angle, branch consistency, curvature minima, module/center‑distance compatibility, plus diagnostic overlays for infeasible/conflicting poses.
- Current status: Some prototype visualization and constraint text exist under ui/tabs/mechanism_foundry, but not integrated in MechanismDesignTab and not enforced during editing.

Problem Statement
- Users need real‑time feedback about feasibility while tinkering; violations should be made visible and, where possible, gently constrained.

Goals
- Inline guardrails during parametric edits for all families.
- Visual overlays: safe/caution/unreachable zones and violation markers.
- Non‑intrusive UX that educates rather than blocks.

Functional Requirements
- Linkages (4‑bar/5‑bar/6‑bar):
  - Compute transmission angle through cycle; flag <20° or >160° as “caution”, <10°/ >170° as “critical”.
  - Branch consistency check on assembly.
  - Visual: polar heatmap ribbon or colored arcs around pivots; text badges in panel.
- Cam–Follower:
  - Curvature minima threshold on cam profile; ensure continuous contact.
  - Visual: highlight high‑curvature regions; show follower contact point along rotation.
- Gears:
  - Enforce module/center‑distance compatibility and integer teeth; warn on interference.
  - Visual: pitch circles and contact path overlay.
- Editing behavior:
  - Soft clamp sliders into preferred ranges; allow overrides with explicit “Allow violation” toggle per parameter.

UX / UI
- Parameter controls show green/yellow/red ribbons corresponding to ranges.
- A collapsible “Diagnostics” panel appears during edits.

APIs
- diagnostics.compute(mech_type, θ) -> dict with per‑constraint statuses and geometry overlays
- parametric_controls render visual ranges based on constraints metadata.

Acceptance Criteria
- Constraints update within 50 ms of handle movement.
- Overlays are legible and do not cripple performance (GPU‑friendly drawing in QGraphicsView for now).
- Users can reproduce the transmission‑angle diagrams shown in PAPER.md with our overlays.

Test Plan
- Unit: constraint math vs. known textbook examples.
- Integration: parametric editing flows across families with predictable overlays.

Implementation Notes
- Port selectively from mechanism_foundry to MechanismDesignTab; unify constraint models.

Milestones
1) Constraint computation & metadata (2–3 days)
2) Overlay drawing per family (2–3 days)
3) Param control ribbons + tests (1–2 days)

