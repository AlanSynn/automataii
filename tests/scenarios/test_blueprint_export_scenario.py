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
    assert data["generated_at"].endswith("Z")
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "MotionSmith Platform" in svg_text
    assert "Automataii Manufacturing System" not in svg_text

    metrics_path = tmp_path / "foundry_blueprint_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["mechanism_type"] == "four_bar"
    assert metrics["duration_ms"] >= 0
    assert metrics["timestamp"] == data["generated_at"]
