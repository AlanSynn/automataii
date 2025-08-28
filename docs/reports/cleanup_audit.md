# Cleanup Audit – Repository Restructure

_Generated: 2025-08-26_

## Summary

- Reduced root-level clutter to 17 entries (target ≤ 30) by consolidating specs, scripts, reports, and assets into owned directories.
- Archived experimental/one-off utilities under `archive/` to keep `scripts/` production-focused while retaining historical context.
- Normalized runtime assets under `resources/` and documentation artefacts under `docs/assets` and `docs/reports`.
- Moved manual/UI regression harnesses to `tests/manual/` so default `pytest` runs stay fast and deterministic.
- Removed heavyweight build artefacts (`build/`, `dist/`, `logs/`, `tmp/`) from source control and codified expectations in the health report.
- Updated build automation to use `packaging/pyinstaller/*.spec`.

## Relocated Artefacts

| Previous Location | New Location | Notes |
| --- | --- | --- |
| `automataii*.spec`, `app.spec` | `packaging/pyinstaller/` | Build scripts updated accordingly. |
| `test_*.py` (root) | `tests/manual/` | Opt-in manual suites excluded via `pytest.ini`. |
| `blueprints/`, `tom/pear_cam*.svg` | `resources/blueprints/` | Runtime references switched to `resolve_path`. |
| `Robot-*.{svg,png}`, `cam.svg`, etc. | `docs/assets/` | Documentation-only imagery moved out of runtime path. |
| Logging cleanup utilities & debug scripts | `archive/scripts/` | Retained for audit/reference. |
| PRDs, task notes, refactor plans | `docs/notes/` | Documentation hub for planning material. |
| `example/` debug artefacts | `archive/example/` | Keeps heavy logs out of main workspace. |
| `tasks/` historical records | `docs/notes/tasks/history/` | Preserved with clearer ownership. |

## Follow-up

- Run `uv run python scripts/report_repo_health.py` after subsequent large cleanups to refresh metrics.
- Ensure new tooling/docs continue to land under the consolidated directories above.
