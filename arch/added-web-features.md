# Added Web Migration Features

These are additions required by the frontend-only migration or explicitly requested for this pass.

## Real browser ONNX Runtime Web
- Files: `web/src/onnx-segmentation.js`, `web/package.json`, `web/scripts/build.mjs`.
- Purpose: run segmentation/inference in the browser without a Python backend.
- User controls: Preferences → `Segmentation Mode`; buttons to load ONNX model file/URL and run segmentation.
- Disable switch: Preferences → `Segmentation Mode` → `Off`.

## Local heuristic fallback
- Files: `web/src/automataii-core.js`, `web/src/app.js`.
- Purpose: keep the product usable without a model or network.
- Behavior: creates deterministic editable body-part boxes/skeleton from the image.

## Browser camera capture
- Files: `web/src/app.js`.
- Purpose: replace the Qt camera dialog with native browser camera APIs.
- Behavior: opens a modal video preview, captures a still frame to canvas, then sends it through the selected segmentation mode.

## Browser manual recognition editor
- Files: `web/src/app.js`.
- Purpose: preserve the desktop “Edit Parts / Skeleton / Boxes” workflow without Qt graphics items.
- Behavior: modal editor updates body-part rectangles and skeleton joint coordinates, then commits the result to the shared project state.

## Frontend-local persistence
- Files: `web/src/app.js`, `web/src/automataii-core.js`.
- Purpose: emulate project/session persistence without a backend.
- Behavior: LocalStorage stores project, autosave, and settings; file APIs handle import/export.

## ZIP/PDF exports
- Files: `web/src/zip.js`, `web/src/app.js`, `web/src/automataii-core.js`.
- Purpose: preserve fabrication package behavior in browser-only form.
- Behavior: ZIP contains manifest, `.automataii` project, skeleton JSON, blueprint SVG, `assembly/README.md`, `recipes.json`, `physical-contract.json`, and SVG fallback guide/parts pages. PDF uses browser print/save-as-PDF from generated SVG.

## Browser smoke test
- Files: `web/browser-smoke.html`, `web/scripts/browser-smoke.mjs`.
- Purpose: prove the app and real ONNX Runtime Web module load in a real headless browser, not only Node.
