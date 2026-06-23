# Automataii Web Migration Architecture

## Runtime shape
The migrated web app is a static frontend application. It can be served by any static file server and does not require a deployed backend.

```text
web/index.html
  -> web/src/app.js                 UI orchestration, tabs, dialogs, events
  -> web/src/automataii-core.js     project model, mechanism math, serializers, SVG export
  -> web/src/onnx-segmentation.js   optional browser ONNX Runtime Web inference
  -> web/src/zip.js                 minimal uncompressed ZIP writer
  -> web/src/styles.css             PyQt-inspired visual parity
```

## Original clean-architecture mapping
| Original layer | Web equivalent |
| --- | --- |
| Domain pure computation | `web/src/automataii-core.js` mechanism/path/project functions |
| Application managers/use cases | `web/src/app.js` event handlers + core service calls |
| Infrastructure persistence/events | LocalStorage, File/Blob, browser events |
| PyQt presentation | `web/index.html`, `web/src/styles.css`, canvas renderers |
| Shared types/result patterns | Validated plain JS project contract and thrown validation errors |

## Frontend-only backend emulation
| Original behavior | Browser-local replacement |
| --- | --- |
| Project save/load `.automataii` | File input/download + JSON serializer/migrator |
| Autosave/recovery | LocalStorage `automataii.autosave` / recovery action |
| Settings/preferences | LocalStorage `automataii.settings` |
| Camera dialog | `getUserMedia` modal + canvas capture |
| ONNX/OpenCV processing | ONNX Runtime Web plus local heuristic/off modes |
| Blueprint/package output | SVG/JSON/ZIP Blob downloads; PDF via print window |
| Status/dialog feedback | aria-live status + modal dialog |

## ONNX behavior
- Default mode: `Local heuristic`, so the app works without a model.
- Optional mode: `ONNX Runtime Web`, using `onnxruntime-web` in the browser.
- Off mode: image is loaded without automatic part segmentation.
- Model source: user-uploaded `.onnx` file or guarded URL.
- URL guard: HTTPS, same-origin HTTP, localhost HTTP, or relative only.
- Failure behavior: status message; current project remains unchanged.

## Build behavior
`npm --prefix web run build` copies static assets into `web/dist` and requires ONNX Runtime Web vendor assets. If `onnxruntime-web/dist/ort.all.min.mjs` is missing or the vendor copy fails, build fails loudly.
