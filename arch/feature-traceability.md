# Automataii Feature Traceability Matrix

Status values:
- Complete: implemented and tested or statically verified in web app.
- Partial: intentionally approximated with documented browser-local behavior.
- Not applicable: original desktop behavior has no browser equivalent or no original feature exists.
- Missing: must be fixed before completion.

| Original / required capability | Evidence in original repo | Web implementation | Status | Notes |
| --- | --- | --- | --- | --- |
| Workflow tabs: Character Selection, Path Editor, Mechanism Design, Mechanism Foundry | `main_window.py` tab setup | `web/index.html`, `renderTabs()` | Complete | Options is dialog, matching desktop menu behavior. |
| Load image file | `ImageProcessingTab.load_image_btn` | `load-image`, file input | Complete | File API data URL. |
| Capture camera | `ImageProcessingTab.capture_image_btn`, `dialogs/camera_dialog.py` | `openCameraCapture()` | Complete | Browser permission required. |
| Example character | sample image buttons/resources | `use-demo` | Complete | Deterministic demo project. |
| Manual recognition editing | interactive segmentation editor, skeleton buttons | `Edit Parts / Skeleton / Boxes` modal edits part boxes and skeleton joints | Complete | Browser uses numeric box/joint controls instead of freehand mask painting. |
| Save skeleton | `save_skeleton_btn` | `downloadSkeleton()` | Complete | Downloads JSON equivalent. |
| Choose output folder | Qt file dialog | download-based info | Partial | Browser cannot choose arbitrary folders without File System Access API; downloads used. |
| Replace/assign character | image processing and design assign buttons | `assign-character`, image load pipeline | Complete | Demo/manual replacement preserved. |
| Project load/save/save-as | `ActionManager`, `ProjectSerializer` | `.automataii` import/export | Partial | Web-created projects are portable JSON/data URLs; browser cannot dereference arbitrary sibling asset paths from desktop project folders without user file grants. |
| Autosave recovery | `recover_autosave` | LocalStorage autosave + recover | Partial | Browser stores one validated local autosave slot rather than multiple desktop autosave files. |
| Undo/redo | `ActionManager` undo/redo | undo/redo stacks | Complete | Keyboard/menu parity via buttons/actions. |
| Preferences/options | `OptionsTab`, preferences action | Options dialog | Complete | Includes web ONNX/export settings. |
| Workspace layout save/restore/reset | `ActionManager` workspace layout actions | toolbar/options layout actions + LocalStorage layout key | Complete | Browser stores tab/theme/toolbar/panel layout preferences. |
| Detailed processing and part properties panels | `OptionsTab` options and tab panels | `detailedProcessing`, `showPartProperties` settings render panels | Complete | Browser-local panels expose processing steps and selected part properties. |
| About/update dialogs | actions in `ActionManager` | About/info modal; update not required for static web | Partial | Auto-updater is desktop distribution-specific. |
| Path drawing | Editor motion path buttons | canvas click drawing, open/closed path, clear, smoothness | Complete | Smoothness slider stores per-path smoothing and affects drawing/playback. |
| Animation play/stop/reset | editor/design animation controls | play/stop/reset + requestAnimationFrame | Complete | Browser-local scheduler. |
| View controls | zoom buttons in tabs | zoom/status/fit actions | Complete | Browser zoom/fit redraw behavior. |
| Mechanism recommendation | recommendation controllers/dialogs | `addRecommendedMechanism()` | Complete | Deterministic recommendation from selected path/part. |
| Mechanism design/tuning | mechanism design UI/parametric service | parameter controls per mechanism | Complete | Browser sliders update mechanisms. |
| Parametric edit | `Parametric Edit` | visible parameter controls | Complete | Browser uses direct controls instead of Qt drag handles. |
| Delete/toggle mechanism | design layer controls | mechanism list actions | Complete | Enabled/toggle/delete available. |
| Blueprint export | blueprint/fabrication managers | SVG/JSON/ZIP/PDF ZIP with assembly README, recipes, physical contract, SVG fallbacks | Complete | Browser-local fabrication package substitutes SVG fallbacks for deterministic desktop PDF generation. |
| Mechanism Foundry catalog | `resources/mechanism_content`, foundry services | catalog/foundry tab | Complete | Core mechanism types represented. |
| 4/5/6-bar linkages | domain linkage mechanisms | `createMechanism`, simulation | Complete | Deterministic JS linkage approximations. |
| Cam follower | cam mechanism/resources | cam state/render/export | Complete | Browser simulation/export. |
| Gear pair / train | gear rendering/content | gear state/render/export | Complete | Browser simulation/export. |
| Planetary gear | resources/content | planetary state/render/export | Complete | Browser simulation/export. |
| Project validation | pydantic/schema/serializer validation | `validateProject()`, import rejection tests | Complete | Browser throws and surfaces status. |
| Real browser ONNX Runtime Web inference | Python `onnxruntime` dependency and requested web migration | `onnxruntime-web` lazy runtime | Complete | Runtime session/run path is implemented; browser smoke verifies app + ORT module loading, concrete model execution requires a supplied model. |
| ONNX disable switch | explicit user requirement | Preferences `Off` | Complete | No automatic segmentation. |
| Frontend-only no backend | migration requirement | static app, LocalStorage/File APIs | Complete | No API server needed. |

## Tracker result
No `Missing` items are currently known. Partial items are browser-platform substitutions: arbitrary output folder selection, desktop asset-folder dereferencing, multi-file autosave history, and desktop auto-updater.

Workarounds for these substitutions are listed in `arch/ui-ux-flow-audit.md`.
