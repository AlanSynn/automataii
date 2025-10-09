# Telemetry Usage Guide

## Overview
Automataii uses lightweight structured telemetry spans to observe critical UI workflows without altering the PyQt interface. The helper `automataii.core.telemetry.telemetry_span` emits `telemetry_start/telemetry_end` entries which are persisted in `logs/telemetry.log` with JSON payloads (one line per event). Console/file logs also continue to capture human-readable context.

## Instrumentation Checklist
- Wrap long-running or business-critical workflows in `telemetry_span("namespace.action", **fields)`.
- Call `span.set(...)` to add derived fields (e.g., `status`, `output_path`, counts).
- Ensure `setup_logging()` from `automataii.utils.logging_config` is invoked at startup; this creates `logs/telemetry.log`.
- Stick to lowercase dotted names (`ui.image_processing.process_image`, `ui.blueprint.export_all`, `application.mechanism.recommend`, etc.).

### Example
```python
from automataii.core.telemetry import telemetry_span

def generate_blueprint(request):
    with telemetry_span("application.blueprint.compose", mechanism_count=len(request.mechanisms)) as span:
        try:
            result = _do_work(request)
        except Exception as err:
            span.set(status="error", error=str(err))
            raise
        else:
            span.set(status="success", output_path=result.path)
            return result
```

## Current Coverage (2025-10-19)
| Workflow | Span | Status |
|----------|------|--------|
| Image processing (segmentation) | `ui.image_processing.process_image` | ✅ |
| Blueprint export (all) | `ui.blueprint.export_all` | ✅ |
| Blueprint export (single mechanism) | `ui.blueprint.export_mechanism` | ✅ |
| Scenario: blueprint automation | `scenario.blueprint_export` | ✅ |
| Scenario: image automation | `scenario.image_processing` | ✅ |
| Mechanism recommendation | `application.mechanism.recommend` | ⏳ (planned MM-1.2) |
| Motion path definition | `application.editor.define_motion_path` | ⏳ |
| Mechanism Foundry catalog load | `application.foundry.catalog_load` | ⏳ |

## Reviewing Telemetry
1. Start the app (`uv run automataii --editing`) with logging configured.
2. Execute workflows; spans append to `logs/telemetry.log`.
3. Tail the log for quick inspection: `tail -f logs/telemetry.log`.
4. For ad-hoc analysis, parse JSON lines:
   ```bash
   python - <<'PY'
   import json
   from pathlib import Path
   for line in Path("logs/telemetry.log").read_text().splitlines():
       event = json.loads(line.split(" ", 1)[-1])
       print(event["event"], event.get("status"), event.get("duration_ms"))
   PY
   ```

## Next Steps
- Extend spans to mechanism recommendation, editor workflows, and Foundry interactions during MM-1.x/MM-3.x milestones.
- Integrate telemetry parsing into scenario automation (MM-4.2) to assert latency thresholds.
- Feed `telemetry.log` into dashboards (e.g., Grafana/Datadog) once CI collection is wired.
