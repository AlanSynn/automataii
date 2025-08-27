Title: Stage 1 — Timing Profile Controls (Speed + Easing)

Background
- PAPER.md calls for “Animation control: play/stop, speed, and timing profile (linear/eased) for pacing review independent of geometry.”
- Current status: Play/Stop exist; there is no user‑facing speed slider nor timing profile selector wired to IKManager animation schedule.

Problem Statement
- Designers need to explore pacing independent of a mechanism’s geometry. A simple UI should control loop duration and the timing profile (linear/ease‑in/ease‑out/ease‑in‑out).

Goals
- Add playback speed (loop duration) control and timing profile selection.
- Decouple geometry from time mapping; maintain backwards compatibility.

Non‑Goals
- Mechanism‑specific non‑uniform gear timing (future work).

User Stories
- I can change animation speed and see the entire motion run faster/slower.
- I can choose ease‑in/ease‑out profiles and feel more expressive pacing.

Functional Requirements
- Animation group in EditorTab:
  - Speed slider (e.g., 0.25×–2.0×) mapped to IKManager.animation_duration (e.g., 1–8 s loop).
  - Timing profile selector: linear, ease‑in, ease‑out, ease‑in‑out (sine/cubic).
- IKManager:
  - Add timing curve function f(t) ∈ [0,1] that remaps normalized progress before path sampling.
  - Preserve current per‑part path sampling; only remap param via f(t).

Acceptance Criteria
- Changing speed updates loop duration without stutter.
- Switching timing profiles produces expected acceleration/deceleration (verified on uniform circular path and on a non‑uniform spline path).
- No regression to mechanism drive integration (MechanismDesignTab play/stop continues to work).

Test Plan
- Unit: timing function monotonicity and boundary conditions (f(0)=0, f(1)=1).
- Integration: measure average frame interval stability while changing speed.
- UX: interactive test to confirm perceived easing on a reference path.

Implementation Notes
- EditorTab: add QSlider + QComboBox; persist selections into IKManager.
- IKManager: apply easing curve to _current_animation_progress before sampling.

Dependencies
- None external; use math/numpy for easing.

Milestones
1) UI controls + wiring (1 day)
2) IKManager timing function (0.5 day)
3) Tests + QA (0.5 day)

