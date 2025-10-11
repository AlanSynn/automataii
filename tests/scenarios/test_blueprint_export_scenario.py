from __future__ import annotations

import json

from automataii.scenarios import run_blueprint_export_scenario


def test_run_blueprint_export_scenario(tmp_path):
    svg_path = run_blueprint_export_scenario(tmp_path)
    assert svg_path.exists()

    manifest_path = tmp_path / "foundry_blueprint_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data["layout"]["item_count"] >= 2
    assert data["mechanism"]["mechanism_type"] == "four_bar"
    assert "ground_link" in data["mechanism"]["parameter_keys"]

    metrics_path = tmp_path / "foundry_blueprint_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["mechanism_type"] == "four_bar"
    assert metrics["duration_ms"] >= 0
