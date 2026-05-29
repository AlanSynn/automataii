import pytest
from ms4n_helpers import make_episode

from automataii.application.ms4n.layer_data_bridge import (
    LAYER_SCHEMA_VERSION,
    LayerDataBridgeError,
    merge_ms4n_layer_data,
    validate_ms4n_payload,
)
from automataii.application.project import MechanismData, ProjectSerializer, ProjectState
from automataii.domain.ms4n import BreakdownRepairEpisode


def test_serializer_round_trip_preserves_ms4n_layer_payload(tmp_path):
    layer_data = merge_ms4n_layer_data(
        {"generated_path_data": {"points": [[0, 0], [1, 1]]}},
        (make_episode(),),
        active_episode_id="ep_001",
    )
    state = ProjectState.empty().with_mechanisms(
        {
            "mech_1": MechanismData(
                id="mech_1",
                part_name="arm",
                type="4_bar_linkage",
                params={"l1": 100.0},
                layer_data=layer_data,
            )
        }
    )
    serializer = ProjectSerializer()
    path = tmp_path / "ms4n.automataii"
    assert serializer.save(state, path).success is True
    load = serializer.load(path)
    assert load.success is True
    assert load.state is not None
    loaded = load.state.mechanisms["mech_1"].layer_data
    assert loaded["ms4n"]["schema_version"] == "ms4n.layer.v1"
    assert loaded["ms4n"]["episodes"][0]["episode_id"] == "ep_001"
    assert loaded["generated_path_data"]["points"][1] == [1, 1]


def test_ms4n_bridge_rejects_runtime_object_before_project_serialization():
    payload = {
        "schema_version": "ms4n.layer.v1",
        "episodes": [
            {
                **make_episode().to_dict(),
                "artifact_refs": [{"artifact_id": "a1", "artifact_type": object(), "uri": "x"}],
            }
        ],
    }
    with pytest.raises(LayerDataBridgeError):
        validate_ms4n_payload(payload)


def test_project_serializer_rejects_invalid_ms4n_layer_payload_before_write(tmp_path):
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
    state = ProjectState.empty().with_mechanisms(
        {
            "mech_1": MechanismData(
                id="mech_1",
                part_name="arm",
                type="4_bar_linkage",
                layer_data={
                    "ms4n": {
                        "schema_version": LAYER_SCHEMA_VERSION,
                        "active_episode_id": "",
                        "episodes": [invalid.to_dict()],
                    }
                },
            )
        }
    )
    path = tmp_path / "invalid_ms4n.automataii"
    result = ProjectSerializer().save(state, path)
    assert result.success is False
    assert result.error is not None
    assert "Invalid MS4N layer data" in result.error
    assert not path.exists()
