# Image Processing Scenario Observability

**Scenario:** `automataii.scenarios.image_processing`  
**CLI:** `uv run automataii --scenario image-processing [--scenario-output <dir>]`

## Requirements
- ONNXRuntime (installed automatically via `uv sync`)  
- ONNX detector/pose models present under `models/onnx/`

## Generated Artifacts
| File | Description |
|------|-------------|
| `annotations/` | Copy of `image_to_annotations` output (char_cfg.yaml, mask/texture, overlays) |
| `parts/` | Segmented part PNGs plus `parts_info.json` |
| `image_processing_manifest.json` | Absolute paths for annotations + parts, original image |
| `image_processing_metrics.json` | Duration, part count, manifest locations |

## Telemetry
- Span: `scenario.image_processing`
- Fields captured:
  - `image`, `detector`, `pose` (inputs)
  - `annotation_dir`, `parts_dir`, `part_count`
  - `duration_ms` (automatic)
- Log line: `scenario_complete image-processing ...`

### Verification
```bash
uv run automataii --scenario image-processing --scenario-output artifacts/ip-run
python scripts/collect_scenario_metrics.py --root artifacts
tail -n 20 logs/telemetry.log | grep scenario.image_processing
```

## Acceptance Criteria
- ONNX inference succeeds (char_cfg.yaml + mask/texture exist).
- Body parts extractor generates `parts_info.json` with > 0 parts.
- Manifest + metrics files written in the target directory.
- Telemetry span recorded with `part_count` and `duration_ms`.
