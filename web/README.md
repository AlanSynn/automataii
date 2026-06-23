# Automataii Web

Frontend-only static migration of the PyQt MotionSmith/Automataii workflow.

```bash
npm --prefix web install     # installs ONNX Runtime Web
npm --prefix web run dev     # serve at http://localhost:5173
npm --prefix web test        # node built-in tests
npm --prefix web run lint    # syntax checks
npm --prefix web run smoke           # HTTP asset smoke check
npm --prefix web run browser-smoke   # headless browser smoke check
npm --prefix web run build   # copy static app + ONNX runtime assets to web/dist
```

No backend, database, private API key, or server-side auth is required.

## Browser ONNX segmentation

Preferences → **Segmentation Mode** controls character processing:

- `Local heuristic`: default editable parts/skeleton generation.
- `ONNX Runtime Web`: loads a user-supplied `.onnx`/`.ort` model file or model URL and runs inference in the browser using `onnxruntime-web`.
- `Off`: imports the image only; no automatic segmentation.

ONNX output handling is intentionally generic: box outputs become part ROIs, mask outputs become a foreground silhouette split into Automataii body parts. Add model-specific label mapping when a concrete body-part model is selected.

## Exports

Blueprint export formats: SVG, JSON package, ZIP fabrication kit, and browser print/save-as-PDF. ZIP packages include the project, blueprint SVG, skeleton JSON, `assembly/README.md`, `recipes.json`, `physical-contract.json`, and SVG fallback pages for assembly guide / kit parts.

## Browser substitutions

- Manual recognition editing is available as **Edit Parts / Skeleton / Boxes** with numeric body-part boxes and skeleton joints.
- Web-created projects are portable as `.automataii` JSON/data URLs. Browser security prevents automatic loading of arbitrary sibling asset files from desktop project folders unless the user imports those assets separately.
- Autosave uses one validated LocalStorage snapshot rather than the desktop multi-file autosave folder.

## Bun / deployment fast path

```bash
bun install --frozen-lockfile
bun run check:bun
bun run dev:bun
```

For static hosts, publish `web/dist/` after `bun run build`. See `DEPLOYMENT.md`.
