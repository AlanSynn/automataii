"""Filesystem loader for the Lab/MS4N kit manifest."""

from __future__ import annotations

import json
from pathlib import Path

from automataii.domain.ms4n import KitManifest, KitManifestError


def load_kit_manifest(manifest_path: Path, project_root: Path | None = None) -> KitManifest:
    """Load and validate a kit manifest and referenced asset files."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise KitManifestError("Kit manifest root must be an object")
    manifest = KitManifest.from_dict(data)
    root = project_root or _infer_project_root(manifest_path)
    for asset in manifest.assets:
        asset_path = root / asset.filename
        if not asset_path.exists():
            raise KitManifestError(f"Kit asset file does not exist: {asset_path}")
    return manifest


def _infer_project_root(manifest_path: Path) -> Path:
    parent = manifest_path.resolve().parent
    if parent.name == "kit":
        return parent.parent
    return parent
