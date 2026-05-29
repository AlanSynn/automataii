from pathlib import Path

from automataii.application.ms4n import KitCatalogService
from automataii.domain.ms4n import KitAsset, KitManifest
from automataii.infrastructure.ms4n import load_kit_manifest


def test_catalog_service_returns_p0_assets_without_ui_reading_json():
    manifest = KitManifest(
        schema_version="ms4n.kit.v1",
        assets=(
            KitAsset("a", "A", "kit/a.svg", "svg", pilot_priority="P0"),
            KitAsset("b", "B", "kit/b.svg", "svg", pilot_priority="P1"),
        ),
    )
    service = KitCatalogService(manifest=manifest)
    assets = service.list_assets("P0")
    assert len(assets) == 1
    assert assets[0].asset_id == "a"
    assert hasattr(assets[0], "evidence_outputs")


def test_catalog_service_includes_bar_board_asset():
    manifest = load_kit_manifest(Path("kit/ms4n-kit-manifest.json"))
    service = KitCatalogService(manifest=manifest)
    asset = service.get_asset("bar-board")
    assert asset is not None
    assert asset.filename == "kit/bar-board.svg"
