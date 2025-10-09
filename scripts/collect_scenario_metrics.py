#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class ScenarioMetrics:
    scenario: str
    duration_ms: float | None
    mechanism_type: str | None
    unit_system: str | None
    image: str | None
    part_count: int | None
    artifact_svg: Path | None
    parts_info: Path | None
    manifest: Path | None
    timestamp: str | None

    @classmethod
    def from_path(cls, metrics_path: Path) -> "ScenarioMetrics":
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        scenario = metrics_path.parent.name
        return cls(
            scenario=scenario,
            duration_ms=data.get("duration_ms"),
            mechanism_type=data.get("mechanism_type"),
            unit_system=data.get("unit_system"),
            image=data.get("image"),
            part_count=data.get("part_count"),
            artifact_svg=Path(data["artifact_svg"]).resolve() if data.get("artifact_svg") else None,
            parts_info=Path(data["parts_info"]).resolve() if data.get("parts_info") else None,
            manifest=Path(data["manifest"]).resolve() if data.get("manifest") else None,
            timestamp=data.get("timestamp"),
        )


def discover_metrics(root: Path) -> Iterable[ScenarioMetrics]:
    for metrics_path in root.rglob("*_metrics.json"):
        try:
            yield ScenarioMetrics.from_path(metrics_path)
        except Exception as exc:
            print(f"[warn] failed to parse {metrics_path}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Automataii scenario metrics.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("artifacts"),
        help="Root directory containing scenario artifacts (default: ./artifacts)",
    )
    args = parser.parse_args()

    metrics = list(discover_metrics(args.root))
    if not metrics:
        print(f"No scenario metrics found under {args.root.resolve()}")
        return

    print(f"Discovered {len(metrics)} scenario run(s) under {args.root.resolve()}")

    durations = [m.duration_ms for m in metrics if m.duration_ms is not None]
    if durations:
        print(f"  Duration ms: min={min(durations):.2f}, max={max(durations):.2f}, mean={statistics.mean(durations):.2f}")

    by_scenario: dict[str, list[ScenarioMetrics]] = {}
    for m in metrics:
        by_scenario.setdefault(m.scenario, []).append(m)

    for scenario, runs in sorted(by_scenario.items()):
        print(f"\nScenario: {scenario} ({len(runs)} run(s))")
        for run in runs:
            details = []
            if run.timestamp:
                details.append(run.timestamp)
            if run.mechanism_type:
                details.append(f"mechanism={run.mechanism_type}")
            if run.unit_system:
                details.append(f"unit={run.unit_system}")
            if run.image:
                details.append(f"image={run.image}")
            if run.part_count is not None:
                details.append(f"part_count={run.part_count}")
            if run.duration_ms is not None:
                details.append(f"duration_ms={run.duration_ms}")
            summary = " ".join(details) if details else "n/a"
            print(f"  - {summary}")
            if run.artifact_svg:
                print(f"      svg={run.artifact_svg}")
            if run.parts_info:
                print(f"      parts_info={run.parts_info}")
            if run.manifest:
                print(f"      manifest={run.manifest}")


if __name__ == "__main__":
    main()
