from __future__ import annotations

import json
from pathlib import Path

import pytest

from automataii.scenarios import run_image_processing_scenario
from automataii.scenarios.image_processing import GENERATED_TREE_MARKER, _copy_tree


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
    annotations_dir = tmp_path / "annotations"

    part_count = manifest["parts"]["part_count"]
    assert part_count > 0
    assert len(parts_info["character"]["parts"]) == part_count
    assert metrics["part_count"] == part_count
    assert Path(manifest["annotation"]["dir"]) == annotations_dir.resolve()
    for key in ("char_cfg", "texture", "mask", "joint_overlay", "bounding_box"):
        artifact_path = Path(manifest["annotation"][key])
        assert artifact_path.exists()
        assert artifact_path.parent == annotations_dir.resolve()


def test_copy_tree_preserves_existing_unmarked_user_folder(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "char_cfg.yaml").write_text("name: generated\n", encoding="utf-8")

    existing = tmp_path / "annotations"
    existing.mkdir()
    sentinel = existing / "user-note.txt"
    sentinel.write_text("keep", encoding="utf-8")

    copied = _copy_tree(source, existing)

    assert copied != existing
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (copied / "char_cfg.yaml").exists()
    assert (copied / GENERATED_TREE_MARKER).exists()


def test_copy_tree_replaces_marked_generated_folder(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "char_cfg.yaml").write_text("name: generated\n", encoding="utf-8")

    existing = tmp_path / "annotations"
    existing.mkdir()
    (existing / GENERATED_TREE_MARKER).write_text("", encoding="utf-8")
    (existing / "stale.txt").write_text("old", encoding="utf-8")

    copied = _copy_tree(source, existing)

    assert copied == existing
    assert not (existing / "stale.txt").exists()
    assert (existing / "char_cfg.yaml").exists()
    assert (existing / GENERATED_TREE_MARKER).exists()
