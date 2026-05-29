"""Kit manifest value objects for the Lab/MS4N physical scaffold."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


class KitManifestError(ValueError):
    """Raised when a kit manifest is missing required P0 metadata."""


@dataclass(frozen=True)
class KitAsset:
    """One physical/digital kit artifact that can be selected in Lab."""

    asset_id: str
    label: str
    filename: str
    asset_type: str
    mechanism_types: tuple[str, ...] = field(default_factory=tuple)
    pilot_priority: str = "P0"
    evidence_outputs: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.asset_id,
            "label": self.label,
            "filename": self.filename,
            "asset_type": self.asset_type,
            "mechanism_types": list(self.mechanism_types),
            "pilot_priority": self.pilot_priority,
            "evidence_outputs": list(self.evidence_outputs),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> KitAsset:
        for field_name in ("id", "label", "filename", "asset_type"):
            if not data.get(field_name):
                raise KitManifestError(f"Kit asset missing required field: {field_name}")
        return cls(
            asset_id=str(data["id"]),
            label=str(data["label"]),
            filename=str(data["filename"]),
            asset_type=str(data["asset_type"]),
            mechanism_types=_string_tuple(data.get("mechanism_types", ())),
            pilot_priority=str(data.get("pilot_priority", "P0")),
            evidence_outputs=_string_tuple(data.get("evidence_outputs", ())),
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True)
class KitManifest:
    """A JSON-safe manifest of constrained kit assets for P0 pilots."""

    schema_version: str
    assets: tuple[KitAsset, ...]
    title: str = "Lab Kit"

    def assets_by_priority(self, priority: str) -> tuple[KitAsset, ...]:
        return tuple(asset for asset in self.assets if asset.pilot_priority == priority)

    def get_asset(self, asset_id: str) -> KitAsset | None:
        return next((asset for asset in self.assets if asset.asset_id == asset_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "assets": [asset.to_dict() for asset in self.assets],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> KitManifest:
        schema_version = data.get("schema_version")
        if schema_version != "ms4n.kit.v1":
            raise KitManifestError("Kit manifest schema_version must be 'ms4n.kit.v1'")
        raw_assets = data.get("assets")
        if not isinstance(raw_assets, Sequence) or isinstance(raw_assets, str | bytes):
            raise KitManifestError("Kit manifest assets must be a list")
        assets = tuple(
            KitAsset.from_dict(_mapping_value(raw_asset, index))
            for index, raw_asset in enumerate(raw_assets)
        )
        if not assets:
            raise KitManifestError("Kit manifest must include at least one asset")
        return cls(
            schema_version=str(schema_version),
            title=str(data.get("title", "Lab Kit")),
            assets=assets,
        )


def _mapping_value(value: object, index: int) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise KitManifestError(f"Kit asset at index {index} must be an object")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, bytes | bytearray):
        raise KitManifestError(f"Expected list of strings, got {value!r}")
    return tuple(str(item) for item in value)
