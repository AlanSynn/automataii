#!/usr/bin/env python3
"""Run mypy while preventing legacy type debt from growing."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / "mypy_baseline.json"
TARGET = "src/automataii"
SUMMARY_LIMIT = 10

LAYER_PREFIXES = (
    ("legacy-qt-ui", "src/automataii/presentation/qt/"),
    ("presentation-other", "src/automataii/presentation/"),
    ("opencv-image-pipeline", "src/automataii/domain/animation/"),
    ("domain-core", "src/automataii/domain/"),
    ("application", "src/automataii/application/"),
    ("infrastructure", "src/automataii/infrastructure/"),
    ("shared", "src/automataii/shared/"),
)


class BaselineSummary(TypedDict):
    total_errors: int
    files: dict[str, int]
    error_codes: dict[str, int]
    layers: dict[str, int]


class BaselineData(BaselineSummary):
    target: str
    errors: list[str]


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


def _source_excerpt(path: str, line_no: int | None) -> str:
    if line_no is None:
        return "<unknown>"
    try:
        return (ROOT / path).read_text().splitlines()[line_no - 1].strip()
    except (OSError, IndexError, UnicodeDecodeError):
        return "<unavailable>"


def _parse_error_location(location: str) -> tuple[str, int | None]:
    parts = location.split(":")
    path = parts[0]
    if len(parts) > 1 and parts[1].isdigit():
        return path, int(parts[1])
    return path, None


def _error_signatures(output: str) -> list[str]:
    """Return stable mypy error signatures from stdout.

    Store normalized error lines instead of only file totals.  We replace
    volatile line/column numbers with the source line content, so harmless line
    shifts do not force a baseline update while same-message new errors usually
    still fail the gate.
    """
    errors: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("src/") or ": error:" not in line:
            continue
        location, message = line.split(": error:", 1)
        path, line_no = _parse_error_location(location)
        errors.append(f"{path}: error:{message} | source:{_source_excerpt(path, line_no)}")
    return sorted(errors)


def _error_code(error: str) -> str:
    error = error.split(" | source:", 1)[0]
    if error.endswith("]") and "[" in error:
        return error.rsplit("[", 1)[1][:-1]
    return "unknown"


def _layer_for_path(path: str) -> str:
    for layer, prefix in LAYER_PREFIXES:
        if path.startswith(prefix):
            return layer
    return "other"


def _path_from_error(error: str) -> str:
    return error.split(": error:", 1)[0]


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _summary(errors: Iterable[str]) -> BaselineSummary:
    by_file: Counter[str] = Counter()
    by_code: Counter[str] = Counter()
    by_layer: Counter[str] = Counter()

    for error in errors:
        path = _path_from_error(error)
        by_file[path] += 1
        by_code[_error_code(error)] += 1
        by_layer[_layer_for_path(path)] += 1

    return {
        "total_errors": sum(by_file.values()),
        "files": _sorted_counts(by_file),
        "error_codes": _sorted_counts(by_code),
        "layers": _sorted_counts(by_layer),
    }


def _counts(output: str) -> BaselineData:
    errors = _error_signatures(output)
    summary = _summary(errors)
    return {
        "target": TARGET,
        "errors": errors,
        **summary,
    }


def _write_baseline(data: BaselineData) -> None:
    BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _coerce_int_dict(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(count) for key, count in value.items()}


def _load_baseline() -> BaselineData:
    raw = json.loads(BASELINE_PATH.read_text())
    if not isinstance(raw, dict):
        raise ValueError("mypy baseline must be a JSON object")
    errors_raw = raw.get("errors", [])
    errors = [str(error) for error in errors_raw] if isinstance(errors_raw, list) else []
    return {
        "target": str(raw.get("target", TARGET)),
        "total_errors": int(raw.get("total_errors", len(errors))),
        "files": _coerce_int_dict(raw.get("files", {})),
        "error_codes": _coerce_int_dict(raw.get("error_codes", {})),
        "layers": _coerce_int_dict(raw.get("layers", {})),
        "errors": errors,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _print_report(label: str, data: BaselineData) -> None:
    print(f"{label}: {data['total_errors']} errors")
    for key in ("layers", "error_codes", "files"):
        values = data[key]
        if not values:
            continue
        print(f"top {key}:")
        for name, count in list(values.items())[:SUMMARY_LIMIT]:
            print(f"  {count:>4}  {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    parser.add_argument(
        "--report",
        action="store_true",
        help="print debt by layer, error code, and file without changing the gate",
    )
    args = parser.parse_args()

    returncode, output = _run_mypy()
    current = _counts(output)
    infrastructure_failure = returncode not in (0, 1) or (returncode != 0 and not current["errors"])

    if infrastructure_failure:
        print(f"mypy did not complete normally (exit {returncode}); baseline unchanged.")
        if output:
            print(output.strip())
        return 1

    if args.update:
        _write_baseline(current)
        print(
            f"Updated mypy baseline: {current['total_errors']} errors across "
            f"{len(current['files'])} files"
        )
        if args.report:
            _print_report("current", current)
        return 0

    if not BASELINE_PATH.exists():
        print(
            f"Missing mypy baseline at {_display_path(BASELINE_PATH)}; "
            "run this script with --update intentionally."
        )
        return 1

    baseline = _load_baseline()
    baseline_files = baseline["files"]
    current_files = current["files"]
    baseline_errors = Counter(baseline["errors"])
    current_errors = Counter(current["errors"])

    increases: list[str] = []
    for path, count in sorted(current_files.items()):
        old_count = int(baseline_files.get(path, 0))
        if int(count) > old_count:
            increases.append(f"{path}: {old_count} -> {count}")

    new_errors = sorted((current_errors - baseline_errors).elements())
    fixed_errors = sorted((baseline_errors - current_errors).elements())

    current_total = int(current["total_errors"])
    baseline_total = int(baseline["total_errors"])
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
        if args.report:
            _print_report("current", current)
        return 1

    if returncode == 0:
        print("mypy clean.")
    else:
        delta = baseline_total - current_total
        print(
            f"mypy legacy debt within baseline: {current_total}/{baseline_total} errors "
            f"across {len(current_files)} files" + (f" ({delta} fewer)" if delta else "")
        )
        if fixed_errors:
            print(f"fixed legacy errors waiting for baseline update: {len(fixed_errors)}")
    if args.report:
        _print_report("current", current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
