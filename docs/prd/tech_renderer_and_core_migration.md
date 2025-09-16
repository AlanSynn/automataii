Title: Tech — Renderer/Core Migration (QtQuick/OpenGL + pybind11 Core)

Background
- PAPER.md describes a PyQt6 interface with QtQuick/OpenGL rendering and a C++/Python core exposed via pybind11 for geometry/kinematics; 60 FPS target. Current app uses QGraphicsView‑based rendering and Python implementations; no QtQuick or pybind11 modules are present.

Problem Statement
- Align implementation with paper’s architecture to improve rendering performance and unlock native kinematics modules.

Goals
- Migrate rendering hotspots to QtQuick/OpenGL (scene drawing, overlays).
- Introduce a C++ core (pybind11) for geometry and kinematics kernels (e.g., four‑bar forward kinematics, curvature, collision/constraints, path sampling), maintaining Python APIs.
- Maintain 60 FPS on laptops for typical scenes.

Non‑Goals
- A complete rewrite of all UI to QML in one release. Target hybrid approach first.

Plan (Phased)
Phase 1 — Hybrid Rendering (2–3 weeks)
- Identify hotspots (mechanism visuals and overlays) and implement QQuickPaintedItem/QSG custom nodes for high‑frequency drawing.
- Bridge current QGraphicsScene where needed; maintain functional parity.

Phase 2 — Native Kernels (3–4 weeks)
- Stand up a small C++ lib with pybind11: vector math, forward models, constraints, curvature, Hausdorff/DTW variants.
- Replace Python hotspots; keep pure‑Python fallback for dev.

Phase 3 — Full Scene Migration (optional)
- Consider moving EditorView and MechanismView to QML with a unified render graph.

APIs / Boundaries
- Python keeps orchestration/UI; C++ exposes stateless compute kernels.
- Mechanism forward models: fourbar_fwd(θ,N) → np.ndarray; cam_profile(params,N) → np.ndarray; gears_contact(θ) …

Acceptance Criteria
- Benchmarks: ≥2× speed‑up for mechanism overlays; stable 60 FPS during parametric edits.
- Feature parity with existing visuals.

Risks / Mitigations
- Build complexity (C++ toolchain) → prebuilt wheels for CI targets; optional pure‑Python fallback.
- Cross‑platform support → limit to macOS/Windows initially.

Dependencies
- CI changes, build scripts, minimal CMake project for pybind11.

