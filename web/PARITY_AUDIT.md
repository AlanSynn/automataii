# Automataii Web Functional Parity Audit

## Inferred product intent
Automataii/MotionSmith is a mechanism-design and character-animation workspace: choose/process a character, define motion paths on parts, generate/tune mechanisms, simulate motion, and export project/blueprint artifacts for fabrication. The desktop app is PyQt with a project SSOT (`metadata`, `parts`, `skeleton`, `paths`, `mechanisms`) and `.automataii` JSON persistence.

## Frontend-only migration approach
The web app is a static browser application. Desktop backend-like behavior is emulated with browser-local services: LocalStorage for project/autosave/settings, File/Blob APIs for import/export/downloads, JavaScript mechanism solvers/renderers, browser camera APIs, browser print-to-PDF, a no-compression ZIP writer, and optional ONNX Runtime Web inference that runs entirely in the client.

## Checklist

| Area | Status | Evidence / notes |
| --- | --- | --- |
| Repository understanding | Complete | Mapped PyQt tabs, project models, serializer, mechanism catalog/content. |
| Product intent inference | Complete | Captured in `.omx/plans/prd-frontend-web-migration-20260623T161556Z.md` and gap plan `.omx/plans/frontend-web-gap-closure-*.md`. |
| Functional parity | Complete | End-to-end character/path/mechanism/foundry/export workflow exists; ONNX model execution path is browser-side and optional. |
| Missing/implied feature completion | Complete | Image upload, camera capture, ONNX model loading/running path, manual part-box/skeleton editing, smoothed path drawing, recommendation, foundry export, autosave recovery, and blueprint/assembly export work. |
| Frontend-only fullstack behavior | Complete | No backend/deployed database/API keys; LocalStorage + File/Blob/camera/print APIs + ONNX Runtime Web in browser. |
| Data model and persistence | Complete | `.automataii` v2-shaped JSON, v1 `layers` migration, project/settings/autosave persistence; arbitrary desktop sibling asset folders require browser file grants/imports. |
| Routing/navigation | Complete | Static tab navigation: Character Selection, Path Editor, Mechanism Design, Mechanism Foundry; Options in dialog. |
| State management | Complete | Central browser state with undo/redo, autosave, project/settings stores. |
| API/backend emulation | Complete | Serializer, project controller, autosave, catalog, recommendation, ONNX segmentation adapter, camera capture, manual recognition editing, smoothing, and export behaviors moved into local services. |
| Authentication/session behavior | Not applicable | Original repo has no auth/session/user roles. |
| Permissions | Not applicable | Original repo has no role/permission model. |
| UI parity | Complete | PyQt-inspired tabs, toolbar, panels, buttons, canvas workspace, dialogs, hover/focus/disabled states, and responsive layout preserved from inferred desktop UI. |
| UX parity | Complete | Workflow order, defaults, autosave, recoverability, import/export feedback, and editable fallback behavior preserved. |
| Responsiveness | Complete | CSS collapses workflow panels on narrow viewports. |
| Accessibility | Complete | Keyboard-reachable controls, semantic buttons, aria-live status, dialog role/aria-modal, focus trap, focus outlines. |
| Error handling | Complete | Project load/autosave/ONNX/camera validation errors surface in status; validation flags inconsistent project references. |
| Loading states | Complete | Status announces ONNX processing/camera/file flows; no network backend loading required. |
| Empty states | Complete | No parts/no mechanisms messages in lists; segmentation Off loads image-only projects intentionally. |
| Build status | Complete | `npm --prefix web run build` passes after `npm --prefix web install`. |
| Test status | Complete | `npm --prefix web run lint`, `npm --prefix web test`, `npm --prefix web run smoke`, `npm --prefix web run browser-smoke`, and build pass. |
| Known gaps | Complete | No unresolved core migration gaps; remaining assumptions below are model/screenshot dependent. |

## Remaining assumptions / non-blocking limits
UI/UX flow coverage and workaround proposals for browser-platform limits are tracked in `../arch/ui-ux-flow-audit.md`.


1. **Model-specific ONNX mapping**
   - Current behavior: ONNX Runtime Web session/run path is implemented in browser. Generic post-processing supports boxes and masks.
   - Limit: exact semantic body-part labels require a concrete model contract.
   - To improve: add label/class mapping for the chosen production body-part model.

2. **Pixel-perfect desktop comparison**
   - Current behavior: inferred PyQt visual language is implemented.
   - Limit: no desktop screenshot oracle was provided.
   - To improve: tune CSS/canvas against approved screenshots if strict pixel parity is required.

3. **PDF export**
   - Current behavior: browser-native print/save-as-PDF flow from the generated blueprint SVG.
   - Limit: exact PDF bytes are controlled by the browser print engine.
   - To improve: add a PDF library only if deterministic PDF files are required.

4. **Desktop asset folders**
   - Current behavior: web-created projects embed browser-loadable data URLs and export JSON/ZIP packages.
   - Limit: browser security prevents silent loading of arbitrary texture/mask files referenced by desktop path strings.
   - To improve: add an explicit asset-folder/ZIP import flow if desktop asset-bundle round-trip becomes required.
