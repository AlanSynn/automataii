Title: Stage 1 — Template‑Based Skeleton Initializer Upgrade

Background
- PAPER.md: upload image → initializer proposes a skeleton with editable part masks and attachment handles; supports human‑like defaults and alternative/non‑human templates.
- Current status: ImageProcessingTab + ONNX pipeline (detector/pose) exist, BodyPartsExtractor segments parts using joint maps. Alternative templates and a clear template selection UX are missing; attachment handles are implicit, not explicitly exposed as a first‑class UI.

Problem Statement
- We need a robust, user‑visible initializer workflow with template selection (human/creature/etc.), explicit attachment handles, and reliable part masks.

Goals
- Add template selection and preview.
- Ensure masks + attachment handles output consistently; allow manual corrections.
- Persist outputs to project with explicit units and part/joint metadata.

Non‑Goals
- Training new models (stick to provided ONNX models for this release).

User Stories
- I choose a character template (Human, Quadruped, Custom) before processing.
- I get editable part masks and visible attachment handles to anchor mechanisms later.
- I can switch templates and re‑initialize without reloading the app.

Functional Requirements
- Template selection UI in ImageProcessingTab with thumbnails and descriptions.
- ONNXImageProcessor integrates with template mapping to produce joint_map compatible with BodyPartsExtractor.
- Attachment handles: show and allow moving named handle points per part; save into char_cfg (JSON/YAML) with units.
- Manual correction tool opens editor (existing interactive_body_editor) directly from the flow.

Acceptance Criteria
- At least two templates (Human default, Quadruped) selectable and functional.
- After processing, handles are visible and persisted; parts_data includes handle positions.
- Manual corrections update saved masks and handles.

Test Plan
- Unit: template mapping correctness (joint id remap), serialization round‑trip.
- Integration: run pipeline on sample images; verify masks and handles load in EditorTab and MechanismDesignTab.

Implementation Notes
- Add a thin TemplateManager (models/template definitions + mapping from COCO‑style keypoints to internal skeleton ids).
- Store handles in ProjectDataManager schema.

Dependencies
- Existing ONNX models and BodyPartsExtractor.

Milestones
1) TemplateManager + UI (1–2 days)
2) Handle visualization + persistence (1 day)
3) Manual correction integration (0.5–1 day)

