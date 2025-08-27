Title: Stage 2 — Candidate Policy (One‑Per‑Family) + Time‑Aware Matching

Background
- PAPER.md: present three alternative mechanism designs (four‑bar, cam–follower, gears) with similarity scores; resample time indices to match velocity profile before distance computation.
- Current status: Dialog aligns spatially via Hausdorff distance and sorts across all dataset entries; not guaranteed one per family; velocity profile is not considered.

Problem Statement
- Ensure coverage (one per family) and improve perceptual fidelity by matching timing profiles, not just spatial shapes.

Goals
- Always surface top candidate per family (≥3 when planetary gears are available; choose overall best “gears” variant).
- Incorporate time‑aware matching by comparing paths in a normalized time domain.

Functional Requirements
- Family policy:
  - Partition dataset by family label → select min‑score candidate in each family.
  - If a family has no entries, show a placeholder tile.
- Time‑aware matching:
  - Resample both user and candidate paths to the same number of time steps (N), preserving relative speed if available.
  - Distance metric: max of bidirectional directed Hausdorff over time‑aligned samples; optionally augment with L2 curvature difference.
- Scoring:
  - Acc% = 100 × (1 − d*_haus / D_norm). Display as “Match %”.

UX / UI
- Dialog shows exactly three tiles: Four‑Bar, Cam–Follower, Gears (Planetary chosen if it wins within gears family).
- Include a “Details” tooltip explaining time‑aware matching.

Acceptance Criteria
- On a mixed test set, dialog always shows one candidate per family when dataset contains all families.
- For paths with non‑uniform speed, time‑aware matching ranks candidates differently than shape‑only matching (validated in tests).

Test Plan
- Unit: time resampling preserves monotonic parameterization and velocity ordering.
- Integration: controlled examples where cam vs linkage differ only by speed profile; assert ranking change.

Implementation Notes
- Extend align_and_compare_paths to accept timestamps or generate uniform time grid; keep rotation handling per family.
- Update MechanismRecommendationDialog to assemble per‑family bests.

Milestones
1) Family partitioning + UI guarantees (0.5–1 day)
2) Time‑aware metric + tests (1–2 days)

