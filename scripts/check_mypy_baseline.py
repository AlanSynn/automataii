#!/usr/bin/env python3
"""Run mypy while preventing legacy type debt from growing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / "mypy_baseline.json"
TARGET = "src/automataii"


def _run_mypy() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", TARGET],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout


def _error_signatures(output: str) -> list[str]:
    """Return stable mypy error signatures from stdout.

    Store normalized error lines instead of only file totals.  We strip volatile
    line/column numbers so harmless edits above legacy errors do not force a
    baseline update, but a new error message/code still fails the gate.
    """
    errors: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("src/") or ": error:" not in line:
            continue
        location, message = line.split(": error:", 1)
        path = location.split(":", 1)[0]
        errors.append(f"{path}: error:{message}")
    return sorted(errors)


def _counts(output: str) -> dict[str, object]:
    by_file: Counter[str] = Counter()
    errors = _error_signatures(output)
    for line in errors:
        by_file[line.split(":", 1)[0]] += 1
    return {
        "target": TARGET,
        "total_errors": sum(by_file.values()),
        "files": dict(sorted(by_file.items())),
        "errors": errors,
    }


def _write_baseline(data: dict[str, object]) -> None:
    BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args()

    returncode, output = _run_mypy()
    current = _counts(output)

    if args.update:
        _write_baseline(current)
        print(
            f"Updated mypy baseline: {current['total_errors']} errors across "
            f"{len(current['files'])} files"
        )
        return 0

    if not BASELINE_PATH.exists():
        print(
            f"Missing mypy baseline at {BASELINE_PATH.relative_to(ROOT)}; "
            "run this script with --update intentionally."
        )
        return 1

    baseline = json.loads(BASELINE_PATH.read_text())
    baseline_files = baseline.get("files", {})
    current_files = current.get("files", {})
    baseline_errors = Counter(str(error) for error in baseline.get("errors", []))
    current_errors = Counter(str(error) for error in current.get("errors", []))

    increases: list[str] = []
    for path, count in sorted(current_files.items()):
        old_count = int(baseline_files.get(path, 0))
        if int(count) > old_count:
            increases.append(f"{path}: {old_count} -> {count}")

    new_errors = sorted((current_errors - baseline_errors).elements())

    current_total = int(current["total_errors"])
    baseline_total = int(baseline.get("total_errors", 0))
    if current_total > baseline_total or increases or new_errors:
        print("mypy debt increased; fix new errors or run with --update intentionally.")
        print(f"baseline total: {baseline_total}; current total: {current_total}")
        for item in increases[:20]:
            print(f"  {item}")
        if len(increases) > 20:
            print(f"  ... {len(increases) - 20} more files")
        for item in new_errors[:20]:
            print(f"  new: {item}")
        if len(new_errors) > 20:
            print(f"  ... {len(new_errors) - 20} more new errors")
        return 1

    if returncode == 0:
        print("mypy clean.")
    else:
        delta = baseline_total - current_total
        print(
            f"mypy legacy debt within baseline: {current_total}/{baseline_total} errors "
            f"across {len(current_files)} files"
            + (f" ({delta} fewer)" if delta else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
