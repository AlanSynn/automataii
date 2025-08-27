Title: Stage 2 — Mechanism Optimization Engine (CMA‑ES with Feasibility Constraints)

Background
- PAPER.md specifies: candidate retrieval from a database followed by constrained optimization of parameters θ to minimize (normalized) Hausdorff distance subject to constraints c_m(θ) > 0; warm‑start on edits; report Acc%.
- Current status: MechanismRecommendationDialog selects best static paths from a JSON dataset via Hausdorff alignment. There is no per‑edit optimization or constraint‑aware refinement.

Problem Statement
- We need a mechanism parameter optimizer that refines candidates and responds to on‑canvas edits while preserving feasibility.

Goals
- Implement a generic optimization engine (CMA‑ES or equivalent) per mechanism family.
- Add constraint checks and soft penalties for feasibility.
- Warm‑start from current parameters on each user edit.
- Report Acc% consistent with paper (1 − d*_haus / D_norm).

Non‑Goals
- Dynamic simulation beyond kinematic constraints.

Functional Requirements
- Optimization target:
  - Objective: minimize Hausdorff distance between user path and mechanism output path (both resampled to N points with matched timing, see time‑aware PRD).
  - Constraints by family:
    - 4‑bar: branch consistency, transmission angle band (e.g., 20°–160° soft, 40°–140° preferred), non‑degenerate lengths.
    - Cam: curvature minima thresholds, single‑lobe integrity for pear‑cam, follower contact continuity.
    - Gears: module/center‑distance compatibility, integer tooth counts, no interference.
  - Use soft penalties λ Σ max(0, −c_m(θ))^2 with configurable weights.
- Architecture:
  - Optimizer service with pluggable family strategies: forward model θ → path, constraints θ → vector.
  - Warm‑start from current θ; early termination for small improvements.
  - Deterministic seed for reproducibility in UI.

UX / UI
- When editing params, show a subtle “Refining…” indicator; allow cancel.
- Display Acc% and constraint statuses (ticks/warnings) inline with param panel.

APIs
- optimization.optimize(mech_type, user_path, θ0, bounds, options) -> (θ*, diagnostics)
- forward_models:
  - fourbar.forward(θ) -> np.ndarray[N,2]
  - cam.forward(θ) -> np.ndarray[N,2]
  - gear.forward(θ) -> np.ndarray[N,2]
- constraints.evaluate(mech_type, θ) -> dict[name -> value]

Acceptance Criteria
- On a standard test suite of 12 user paths, optimizer improves Acc% by ≥ 15% median vs dataset‑only selection.
- Edits trigger warm‑start runs (< 300 ms for 50 iterations on laptop) with visible improvements or no‑worse result.
- Constraint violations are respected (no invalid θ emitted).

Test Plan
- Unit: constraint functions return expected signs across curated θ.
- Integration: run optimizer on canned paths; compare pre/post Acc% distribution.
- Performance: microbenchmarks per family; ensure UI remains responsive.

Implementation Notes
- Use pycma (if permitted) or a lightweight in‑house CMA‑like sampler; keep a fallback (Nelder–Mead) if dependencies are restricted.
- Forward models can reuse existing kinematic generators used by dataset builder (generate_comprehensive_dataset.py) for consistency.

Dependencies
- Time‑aware matching PRD for path resampling (or implement internal).

Milestones
1) Constraints + forward models (3–4 days)
2) CMA‑ES scaffolding + UI hooks (3 days)
3) Warm‑start + diagnostics + tests (2 days)

