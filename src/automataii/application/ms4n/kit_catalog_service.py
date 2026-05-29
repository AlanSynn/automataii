"""Application service for selecting Lab kit assets without UI JSON parsing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from automataii.application.ms4n.view_models import KitAssetViewModel
from automataii.domain.ms4n import KitAsset, KitManifest

ManifestLoader = Callable[[Path], KitManifest]


class KitCatalogService:
    """Read-only catalog facade for the Lab tab."""

    def __init__(
        self, manifest: KitManifest | None = None, loader: ManifestLoader | None = None
    ) -> None:
        self._manifest = manifest
        self._loader = loader

    def load(self, manifest_path: Path) -> KitManifest:
        if self._loader is None:
            raise RuntimeError("KitCatalogService requires a manifest loader port")
        self._manifest = self._loader(manifest_path)
        return self._manifest

    def list_assets(self, pilot_priority: str | None = None) -> tuple[KitAssetViewModel, ...]:
        manifest = self._require_manifest()
        assets = (
            manifest.assets
            if pilot_priority is None
            else manifest.assets_by_priority(pilot_priority)
        )
        return tuple(KitAssetViewModel.from_asset(asset) for asset in assets)

    def get_asset(self, asset_id: str) -> KitAsset | None:
        return self._require_manifest().get_asset(asset_id)

    def compatible_assets(
        self, mechanism_type: str, pilot_priority: str | None = None
    ) -> tuple[KitAssetViewModel, ...]:
        assets = self._require_manifest().assets
        if pilot_priority is not None:
            assets = tuple(asset for asset in assets if asset.pilot_priority == pilot_priority)
        filtered = tuple(
            asset
            for asset in assets
            if not asset.mechanism_types or mechanism_type in asset.mechanism_types
        )
        return tuple(KitAssetViewModel.from_asset(asset) for asset in filtered)

    def _require_manifest(self) -> KitManifest:
        if self._manifest is None:
            raise RuntimeError("Kit manifest has not been loaded")
        return self._manifest
