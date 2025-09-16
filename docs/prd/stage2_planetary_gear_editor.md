Title: Stage 2 — Planetary Gear Parametric Editor (Optional)

Background
- PAPER.md includes “spur/planetary gears”. The current parametric editor treats planetary gears like simple pairs; a specialized editor is not yet present.

Problem Statement
- Provide focused controls and constraints for planetary sets (sun, ring, planet count/placement), aiding both design and guardrails.

Goals
- Add planet count, module, tooth counts, center distance/clearance, carrier radius, and initial phase controls.
- Enforce standard gear constraints; visualize pitch circles and carrier.

Functional Requirements
- Editor controls and handles:
  - Sun center, ring center (coincident for coaxial), planet count (3–5), module, tooth counts.
  - Auto‑position planets evenly; display carrier arm.
- Constraints:
  - Integer teeth, module consistency, center distance relationships, avoid interference.
- Visuals:
  - Pitch circles, tooth placeholders (not full involute), annotated gear ratio.

Acceptance Criteria
- Editing parameters updates geometry and respects constraints.
- Candidate gear ratio displayed correctly.

Test Plan
- Unit: gear relations (center distances vs module/teeth) validated.
- Integration: editor interactions maintain coherence.

Milestones
1) Editor UI + constraints (1–2 days)
2) Visuals (0.5 day)
3) Tests (0.5 day)

