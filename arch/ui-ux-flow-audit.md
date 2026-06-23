# Automataii Web UI/UX Flow Audit

Date: 2026-06-23

## Scope
Checked user-facing workflow continuity, feedback, transitions, accessibility basics, and browser-platform limitations for the frontend-only Automataii migration.

## Audit method
- Read current `web/src/app.js`, `web/src/styles.css`, `web/index.html`, and migration docs.
- Extended real Headless Chrome browser smoke coverage in `web/browser-smoke.html`.
- Re-ran lint, tests, HTTP smoke, real browser smoke, build, ONNX asset check, and npm audit.
- `agent-browser` CLI was attempted first, but its daemon socket failed in this environment with a permission error. Headless Chrome smoke is the browser fallback used here.

## Flow checklist

| Flow | Status | Evidence |
| --- | --- | --- |
| Initial landing and demo project load | Complete | App initializes with deterministic demo when no valid local project exists. |
| Character Selection -> Path Editor -> Mechanism Design -> Foundry | Complete | `data-tab-target` transitions are now exercised in browser smoke. |
| Direct tab navigation | Complete | `data-tab` navigation, active tab state, `aria-current`. |
| Project new/load/save/export/autosave recover | Complete | Toolbar actions, LocalStorage validation, import/export tests. |
| Image import with Local heuristic | Complete | Browser File API creates segmented editable project. |
| Image import with segmentation Off | Complete | Browser smoke verifies image-only project and `0 parts`. |
| ONNX Runtime Web path | Complete | Real `onnxruntime-web` module import and app ONNX failure path are browser-smoked; valid inference requires a supplied model. |
| ONNX disable switch | Complete | Preferences `Off`; smoke verifies no segmentation. |
| Manual recognition edit | Complete | Modal edits part rectangles and skeleton joints. |
| Skeleton edit/save | Complete | Modal editing and JSON download. |
| Path drawing/clear/smoothness | Complete | Canvas drawing flow, smoothness persistence, core tests. |
| Animation play/stop/reset | Complete | requestAnimationFrame scheduler and status feedback. |
| Mechanism recommendation/tune/toggle/delete | Complete | Design tab controls and param sliders. |
| Foundry search/preview/export | Complete | Foundry tab, search box, parameter controls, export to selected part. |
| Blueprint/package export | Complete | SVG/JSON/ZIP/PDF branches; ZIP includes assembly docs and SVG fallbacks. |
| Preferences/options | Complete | Modal, settings persistence, theme/layout/export/ONNX controls. |
| About/update feedback | Complete | Modal explains static-web update path. |
| Camera capture and cleanup | Complete | Browser smoke verifies stream track stop on close. |
| Empty/error/loading states | Complete | Empty list messages, `role=status`, ONNX/camera/import error statuses. |
| Keyboard/accessibility basics | Complete | Buttons, labels, focus-visible, dialog role/aria-modal, focus trap, Escape close, reduced-motion fallback. |
| UI transitions | Complete | Tabs/views/dialogs/buttons now have lightweight transitions; reduced motion disables them. |

## UI/UX findings
No broken core user flow is currently known. The only issue found in this pass was weak visual transition feedback during tab/dialog/button changes; this was fixed in `web/src/styles.css` with minimal CSS-only transitions and reduced-motion support.

## Limitation workaround matrix

| Limitation | Impact | Workaround | Deployability |
| --- | --- | --- | --- |
| Browser cannot silently choose arbitrary output folders | Exports go to Downloads by default | Add optional File System Access API path (`showDirectoryPicker` / `showSaveFilePicker`) for Chromium/Edge on HTTPS/localhost; keep Downloads fallback for Firefox/Safari | Practical, optional enhancement |
| Browser cannot dereference desktop sibling asset paths from `.automataii` JSON | Old desktop projects with external texture/mask paths need assets reselected | Accept a user-provided asset ZIP/folder, map files by basename/path, and rewrite project image/texture fields to Blob URLs/data URLs during import | Practical if desktop round-trip is required |
| LocalStorage single autosave slot vs desktop autosave files | Less recovery history | Store a small IndexedDB autosave ring buffer keyed by project id/time; keep current LocalStorage slot as fast startup fallback | Practical |
| Browser PDF bytes controlled by print engine | PDF output differs by browser | For deterministic PDFs, add a client-side PDF library only for the PDF export path; keep SVG/ZIP as canonical exports | Practical but adds dependency, only needed for byte-stable PDFs |
| ONNX semantic labels depend on production model contract | Generic boxes/masks cannot infer model-specific class names perfectly | Add a small JSON label-map upload/setting next to the model URL and map class ids to Automataii part names | Practical |
| ONNX large model load time / WASM asset hosting | First run can be slow or fail if assets not served | Ship `vendor/onnxruntime-web` from `npm run build`, host models with CORS/HTTPS, document recommended quantized model size | Practical |
| Camera permissions require secure context | Camera may fail on plain remote HTTP | Deploy over HTTPS; localhost remains acceptable for development | Practical |
| Mobile canvas precision/touch ergonomics | Small screens can be harder for drawing | Add pointer/touch handle enlargement and optional snap/grid controls; current responsive layout already stacks panels | Practical if mobile editing is a priority |
| Desktop auto-updater absent | Static web app does not self-update like packaged desktop | Use normal static deployment versioning/cache busting and expose version text in About | Practical deployment process |
| Pixel-perfect PyQt comparison unavailable | Exact visual parity cannot be proven without screenshots | Capture approved desktop screenshots and run visual diff against browser screenshots | Needs source screenshots, otherwise not actionable |

## Stop condition
Current stop condition is met: no known broken core UI/UX flow, transition feedback exists, reduced-motion fallback exists, and remaining limits have documented workarounds.
