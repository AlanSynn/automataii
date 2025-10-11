from __future__ import annotations

import json
from pathlib import Path

import pytest

from automataii.scenarios import run_image_processing_scenario


def test_run_image_processing_scenario(tmp_path):
    pytest.importorskip("onnxruntime")

    parts_dir = run_image_processing_scenario(tmp_path)
    assert parts_dir.exists()

    manifest_path = tmp_path / "image_processing_manifest.json"
    metrics_path = tmp_path / "image_processing_metrics.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    parts_info_path = Path(manifest["parts"]["parts_info"])
    parts_info = json.loads(parts_info_path.read_text(encoding="utf-8"))

    part_count = manifest["parts"]["part_count"]
    assert part_count > 0
    assert len(parts_info["character"]["parts"]) == part_count
    assert metrics["part_count"] == part_count
