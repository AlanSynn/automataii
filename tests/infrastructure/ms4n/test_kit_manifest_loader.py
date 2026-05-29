import json
from pathlib import Path

import pytest

from automataii.domain.ms4n import KitManifestError
from automataii.infrastructure.ms4n import load_kit_manifest


def test_manifest_loader_accepts_p0_manifest_with_existing_files():
    manifest = load_kit_manifest(Path("kit/ms4n-kit-manifest.json"))
    assert manifest.schema_version == "ms4n.kit.v1"
    asset_ids = {asset.asset_id for asset in manifest.assets}
    assert {
        "bar-board",
        "ms4n-00-bar-board-guide",
        "ms4n-01-linkage-bars",
        "ms4n-06-trace-prompt-cards",
        "ms4n-07-fabrication-checks",
    } <= asset_ids
    for asset in manifest.assets:
        assert Path(asset.filename).exists()


def test_manifest_loader_rejects_missing_required_fields(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": "ms4n.kit.v1", "assets": [{"label": "No id"}]}))
    with pytest.raises(KitManifestError):
        load_kit_manifest(path, project_root=tmp_path)


def test_manifest_loader_rejects_missing_asset_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "ms4n.kit.v1",
                "assets": [
                    {
                        "id": "missing",
                        "label": "Missing",
                        "filename": "kit/missing.svg",
                        "asset_type": "svg",
                    }
                ],
            }
        )
    )
    with pytest.raises(KitManifestError, match="missing.svg"):
        load_kit_manifest(path, project_root=tmp_path)
