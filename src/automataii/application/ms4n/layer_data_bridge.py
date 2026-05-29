"""Validated MS4N payload bridge for `MechanismData.layer_data`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from automataii.domain.ms4n import BreakdownRepairEpisode, EpisodeValidationError, ensure_json_safe

MS4N_LAYER_KEY = "ms4n"
LAYER_SCHEMA_VERSION = "ms4n.layer.v1"
_REQUIRED_EPISODE_FIELDS = (
    "schema_version",
    "episode_id",
    "session_id",
    "participant_hash",
    "mechanism_id",
    "mechanism_type",
    "part_name",
    "kit_asset_ids",
    "status",
)


class LayerDataBridgeError(ValueError):
    """Raised when MS4N layer payload validation fails before serializer fallback."""


def make_layer_payload(
    episodes: Sequence[BreakdownRepairEpisode],
    *,
    active_episode_id: str = "",
) -> dict[str, object]:
    for episode in episodes:
        episode.assert_valid_for_p0()
    payload: dict[str, object] = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "active_episode_id": active_episode_id,
        "episodes": [episode.to_dict() for episode in episodes],
    }
    validate_ms4n_payload(payload)
    return payload


def merge_ms4n_layer_data(
    layer_data: Mapping[str, object],
    episodes: Sequence[BreakdownRepairEpisode],
    *,
    active_episode_id: str = "",
) -> dict[str, object]:
    merged = dict(layer_data)
    merged[MS4N_LAYER_KEY] = make_layer_payload(episodes, active_episode_id=active_episode_id)
    return merged


def extract_ms4n_payload(layer_data: Mapping[str, object]) -> dict[str, object]:
    payload = layer_data.get(MS4N_LAYER_KEY)
    if payload is None:
        return {"schema_version": LAYER_SCHEMA_VERSION, "active_episode_id": "", "episodes": []}
    if not isinstance(payload, Mapping):
        raise LayerDataBridgeError("layer_data['ms4n'] must be an object")
    payload_dict = dict(payload)
    validate_ms4n_payload(payload_dict)
    return payload_dict


def extract_ms4n_episodes(layer_data: Mapping[str, object]) -> tuple[BreakdownRepairEpisode, ...]:
    payload = extract_ms4n_payload(layer_data)
    raw_episodes = payload.get("episodes", ())
    if not isinstance(raw_episodes, Sequence) or isinstance(raw_episodes, str | bytes):
        raise LayerDataBridgeError("MS4N episodes must be a list")
    episodes: list[BreakdownRepairEpisode] = []
    for index, item in enumerate(raw_episodes):
        if not isinstance(item, Mapping):
            raise LayerDataBridgeError(f"MS4N episode {index} must be an object")
        episodes.append(_episode_from_payload(item, index))
    return tuple(episodes)


def validate_ms4n_payload(payload: Mapping[str, object]) -> None:
    try:
        ensure_json_safe(payload, "ms4n")
    except EpisodeValidationError as exc:
        raise LayerDataBridgeError(str(exc)) from exc
    if payload.get("schema_version") != LAYER_SCHEMA_VERSION:
        raise LayerDataBridgeError("MS4N payload schema_version must be 'ms4n.layer.v1'")
    raw_episodes = payload.get("episodes")
    if raw_episodes is None:
        raise LayerDataBridgeError("MS4N payload episodes cannot be null")
    if not isinstance(raw_episodes, Sequence) or isinstance(raw_episodes, str | bytes):
        raise LayerDataBridgeError("MS4N payload episodes must be a list")
    for index, raw_episode in enumerate(raw_episodes):
        if not isinstance(raw_episode, Mapping):
            raise LayerDataBridgeError(f"MS4N episode {index} must be an object")
        _validate_episode_payload(raw_episode, index)


def _validate_episode_payload(episode_payload: Mapping[str, object], index: int) -> None:
    for field_name in _REQUIRED_EPISODE_FIELDS:
        value = episode_payload.get(field_name)
        if value is None or value == "":
            raise LayerDataBridgeError(
                f"MS4N episode {index} required field {field_name!r} cannot be null/empty"
            )
    if episode_payload.get("schema_version") != "ms4n.episode.v1":
        raise LayerDataBridgeError(f"MS4N episode {index} has unsupported schema_version")
    for forbidden in ("participant_name", "learner_name", "email", "raw_name"):
        if forbidden in episode_payload:
            raise LayerDataBridgeError(
                f"MS4N episode {index} contains raw identifier {forbidden!r}"
            )
    raw_kit_assets = episode_payload.get("kit_asset_ids")
    if (
        not isinstance(raw_kit_assets, Sequence)
        or isinstance(raw_kit_assets, str | bytes)
        or not raw_kit_assets
        or any(not isinstance(item, str) or not item.strip() for item in raw_kit_assets)
    ):
        raise LayerDataBridgeError(
            f"MS4N episode {index} required field 'kit_asset_ids' must be a non-empty list"
        )
    episode = _episode_from_payload(episode_payload, index)
    try:
        episode.assert_valid_for_p0()
    except ValueError as exc:
        raise LayerDataBridgeError(f"MS4N episode {index} failed P0 validation: {exc}") from exc


def _episode_from_payload(
    episode_payload: Mapping[str, object],
    index: int,
) -> BreakdownRepairEpisode:
    try:
        return BreakdownRepairEpisode.from_dict(episode_payload)
    except ValueError as exc:
        raise LayerDataBridgeError(f"MS4N episode {index} is invalid: {exc}") from exc
