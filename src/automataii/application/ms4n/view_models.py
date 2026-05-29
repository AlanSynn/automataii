"""Small immutable view models for the user-facing Lab tab."""

from __future__ import annotations

from dataclasses import dataclass, field

from automataii.domain.ms4n import KitAsset


@dataclass(frozen=True)
class KitAssetViewModel:
    asset_id: str
    label: str
    filename: str
    asset_type: str
    mechanism_types: tuple[str, ...] = field(default_factory=tuple)
    evidence_outputs: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""

    @classmethod
    def from_asset(cls, asset: KitAsset) -> KitAssetViewModel:
        return cls(
            asset_id=asset.asset_id,
            label=asset.label,
            filename=asset.filename,
            asset_type=asset.asset_type,
            mechanism_types=asset.mechanism_types,
            evidence_outputs=asset.evidence_outputs,
            description=asset.description,
        )


@dataclass(frozen=True)
class EpisodeSummaryViewModel:
    episode_id: str
    mechanism_id: str
    mechanism_type: str
    part_name: str
    status: str
    change_count: int
    repair_count: int
    learner_explanation_present: bool
