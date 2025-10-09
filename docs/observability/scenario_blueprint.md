# Blueprint Scenario Telemetry Checklist

**Scenario:** `automataii.scenarios.blueprint`  
**CLI:** `uv run automataii --scenario blueprint-export [--scenario-output <dir>]`

## Generated Artifacts
| File | Contents | Notes |
|------|----------|-------|
| `foundry_blueprint.svg` | Rendered single-page blueprint using controller/default parts | Saved under the provided output directory |
| `foundry_blueprint_manifest.json` | Mechanism metadata, unit system, parameter keys | Deterministic payload for diffing runs |
| `foundry_blueprint_metrics.json` | Duration, timestamp, output paths, mechanism type | Parsed by `scripts/collect_scenario_metrics.py` |

## Telemetry
- Span name: `scenario.blueprint_export`
- Fields recorded:
  - `mechanism_type`, `mechanism_key`
  - `unit_system`
  - `item_count`, `width_mm`, `height_mm`
  - `duration_ms` (auto)
- Logs emit `scenario_complete blueprint-export ...` for quick grep.

### Sample handling
```bash
uv run automataii --scenario blueprint-export --scenario-output artifacts/local-run
python scripts/collect_scenario_metrics.py --root artifacts
tail -n 20 logs/telemetry.log
```

## Acceptance Criteria
- Scenario completes without selecting UI widgets.
- Telemetry span + metrics JSON include mechanism defaults.
- Aggregator picks up the run (either in CI or local QA execution).
