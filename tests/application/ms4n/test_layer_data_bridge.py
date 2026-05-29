import math

import pytest
from ms4n_helpers import make_episode

from automataii.application.ms4n.layer_data_bridge import (
    LAYER_SCHEMA_VERSION,
    LayerDataBridgeError,
    extract_ms4n_payload,
    merge_ms4n_layer_data,
    validate_ms4n_payload,
)
from automataii.domain.ms4n import BreakdownRepairEpisode


def test_layer_data_bridge_adds_ms4n_without_removing_generated_path_data():
    layer_data = {"generated_path_data": {"points": [[0, 0], [1, 1]]}}
    merged = merge_ms4n_layer_data(layer_data, (make_episode(),), active_episode_id="ep_001")
    assert merged["generated_path_data"] == layer_data["generated_path_data"]
    assert merged["ms4n"]["schema_version"] == LAYER_SCHEMA_VERSION


def test_bridge_extracts_empty_payload_when_ms4n_key_missing():
    payload = extract_ms4n_payload({"generated_path_data": {}})
    assert payload == {
        "schema_version": LAYER_SCHEMA_VERSION,
        "active_episode_id": "",
        "episodes": [],
    }


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_bridge_rejects_non_finite_payloads(bad):
    payload = {"schema_version": LAYER_SCHEMA_VERSION, "episodes": [{"schema_version": bad}]}
    with pytest.raises(LayerDataBridgeError):
        validate_ms4n_payload(payload)


def test_bridge_rejects_qt_derived_null_required_payloads():
    payload = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "episodes": [{"schema_version": "ms4n.episode.v1", "episode_id": None}],
    }
    with pytest.raises(LayerDataBridgeError):
        validate_ms4n_payload(payload)


def test_bridge_rejects_invalid_repaired_episode_payload():
    invalid = BreakdownRepairEpisode(
        episode_id="ep_invalid",
        session_id="session_fake_001",
        participant_hash="p_hash_fake",
        mechanism_id="mech_1",
        mechanism_type="4_bar_linkage",
        part_name="arm",
        kit_asset_ids=("bar-board",),
        status="repaired",
    )
    payload = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "active_episode_id": "",
        "episodes": [invalid.to_dict()],
    }
    with pytest.raises(LayerDataBridgeError):
        validate_ms4n_payload(payload)


def test_bridge_rejects_runtime_object_inside_ms4n_payload():
    payload = {
        "schema_version": LAYER_SCHEMA_VERSION,
        "episodes": [
            {
                **make_episode().to_dict(),
                "artifact_refs": [{"artifact_id": "a1", "artifact_type": object(), "uri": "x"}],
            }
        ],
    }
    with pytest.raises(LayerDataBridgeError):
        validate_ms4n_payload(payload)
