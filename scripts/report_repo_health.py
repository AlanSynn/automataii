#!/usr/bin/env python3
"""
Generate a lightweight repository health report.

The report captures:
- Top-level entry counts (non-hidden)
- Size summary for key directories
- Presence of large artefact directories that should remain empty

Output is written to docs/reports/repo_health.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT_TARGET_MAX_ENTRIES = 30
REPORT_PATH = Path("docs/reports/repo_health.md")
DEFAULT_SIZE_DIRS = (
    "archive",
    "config",
    "data",
    "docs",
    "models",
    "resources",
    "scripts",
    "src",
    "tests",
    "tools",
)
EMPTY_EXPECTED_DIRS = ("build", "dist", "logs", "tmp")


@dataclass
class DirectoryStat:
    path: Path
    total_bytes: int

    @property
    def size_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)


def iter_non_hidden(entries: Iterable[Path]) -> Iterable[Path]:
    for entry in entries:
        if entry.name.startswith("."):
            continue
        yield entry


def collect_directory_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path, topdown=True):
        # Skip hidden directories early
        if Path(root).name.startswith("."):
            continue
        for name in files:
            file_path = Path(root, name)
            try:
                total += file_path.stat().st_size
            except OSError:
                # Ignore transient files removed between os.walk and stat
                continue
    return total


def gather_stats(project_root: Path, size_dirs: Iterable[str]) -> list[DirectoryStat]:
    stats: list[DirectoryStat] = []
    for relative in size_dirs:
        target = project_root / relative
        if not target.exists():
            continue
        stats.append(DirectoryStat(target, collect_directory_size(target)))
    return stats


def render_report(
    project_root: Path,
    root_entries: list[Path],
    dir_stats: list[DirectoryStat],
    missing_empty_dirs: list[str],
    non_empty_expected_dirs: list[tuple[str, float]],
) -> str:
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    lines: list[str] = []
    lines.append("# Repository Health Report")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append("## Root Inventory")
    lines.append(f"- Top-level entries (non-hidden): {len(root_entries)} (target ≤ {ROOT_TARGET_MAX_ENTRIES})")
    lines.append("- Entries:")
    for entry in sorted(root_entries):
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"  - `{entry.name}{suffix}`")
    lines.append("")
    lines.append("## Directory Size Summary")
    lines.append("| Path | Size (MB) |")
    lines.append("| --- | ---: |")
    for stat in sorted(dir_stats, key=lambda s: s.size_mb, reverse=True):
        rel = stat.path.relative_to(project_root)
        lines.append(f"| `{rel}` | {stat.size_mb:,.2f} |")
    lines.append("")
    lines.append("## Empty Artefact Directories")
    if missing_empty_dirs:
        lines.append("- Newly created (did not exist): " + ", ".join(sorted(missing_empty_dirs)))
    else:
        lines.append("- All expected directories exist.")
    if non_empty_expected_dirs:
        lines.append("- ⚠️ Non-empty directories that should be clean:")
        for path, size in non_empty_expected_dirs:
            lines.append(f"  - `{path}` → {size:,.2f} MB")
    else:
        lines.append("- ✅ `build/`, `dist/`, `logs/`, and `tmp/` are empty.")
    lines.append("")
    lines.append("> Run `uv run python scripts/report_repo_health.py` after large cleanups.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate repository health report.")
    parser.add_argument(
        "--dirs",
        nargs="*",
        default=DEFAULT_SIZE_DIRS,
        help="Relative directories to include in the size summary (default: %(default)s).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    root_entries = list(iter_non_hidden(project_root.iterdir()))
    dir_stats = gather_stats(project_root, args.dirs)

    missing_empty_dirs: list[str] = []
    non_empty_expected_dirs: list[tuple[str, float]] = []
    for rel in EMPTY_EXPECTED_DIRS:
        target = project_root / rel
        if not target.exists():
            missing_empty_dirs.append(rel)
            continue
        stat = collect_directory_size(target)
        if stat > 0:
            non_empty_expected_dirs.append((rel, stat / (1024 * 1024)))

    report = render_report(project_root, root_entries, dir_stats, missing_empty_dirs, non_empty_expected_dirs)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
