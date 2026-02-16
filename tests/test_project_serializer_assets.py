from pathlib import Path

from automataii.application.project import (
    MechanismData,
    PartData,
    ProjectSerializer,
    ProjectState,
    Transform,
)


def test_serializer_bundles_assets_and_load_resolves_paths(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    texture_path = source_dir / "head.png"
    mask_path = source_dir / "head_mask.png"
    image_path = source_dir / "input.png"

    texture_path.write_bytes(b"texture")
    mask_path.write_bytes(b"mask")
    image_path.write_bytes(b"image")

    part = PartData(
        name="head",
        texture_path=str(texture_path),
        mask_path=str(mask_path),
        anchor_joint="neck",
        transform=Transform(x=10.0, y=20.0, rotation=0.0, scale=1.0),
        z_index=4,
        roi=(10.0, 20.0, 30.0, 40.0),
        fill_color="rgba(255,0,0,0.5)",
        fixed=False,
        opacity=0.95,
        local_pivot_offset=(12.0, 8.0),
    )

    state = (
        ProjectState.empty()
        .with_project_dir(source_dir)
        .with_parts({"head": part})
        .with_image_path(image_path)
    )

    serializer = ProjectSerializer()
    save_path = tmp_path / "demo.automataii"

    save_result = serializer.save(state, save_path)
    assert save_result.success is True
    assert save_result.path == save_path
    assert save_path.exists()
    assert (tmp_path / "demo_assets").exists()

    load_result = serializer.load(save_path)
    assert load_result.success is True
    assert load_result.state is not None

    loaded_state = load_result.state
    assert loaded_state.project_dir == tmp_path
    assert loaded_state.image_path is not None
    assert loaded_state.image_path.exists()

    loaded_head = loaded_state.parts["head"]
    assert Path(loaded_head.texture_path).is_absolute()
    assert Path(loaded_head.texture_path).exists()
    assert Path(loaded_head.mask_path).is_absolute()
    assert Path(loaded_head.mask_path).exists()
    assert loaded_head.roi == (10.0, 20.0, 30.0, 40.0)
    assert loaded_head.local_pivot_offset == (12.0, 8.0)


def test_serializer_round_trip_preserves_mechanism_layer_payload(tmp_path):
    state = ProjectState.empty().with_mechanisms(
        {
            "mech_1": MechanismData(
                id="mech_1",
                part_name="right_arm",
                type="4_bar_linkage",
                params={
                    "l1": 120.0,
                    "l2": 45.0,
                    "input_angle": 30.0,
                },
                layer_data={
                    "foundry_synced": True,
                    "source": "foundry",
                    "key_points": {
                        "ground_pivot_1": [10.0, 20.0],
                        "ground_pivot_2": [130.0, 20.0],
                    },
                    "full_simulation_data": {
                        "joint_positions": {
                            "p1_positions": [[10.0, 20.0]],
                            "p2_positions": [[130.0, 20.0]],
                        },
                    },
                    "generated_path_data": {
                        "points": [[100.0, 100.0], [120.0, 120.0], [140.0, 110.0]],
                        "is_closed": False,
                    },
                },
                enabled=True,
            ),
        }
    )

    serializer = ProjectSerializer()
    save_path = tmp_path / "mechanism_payload.automataii"
    save_result = serializer.save(state, save_path)
    assert save_result.success is True

    load_result = serializer.load(save_path)
    assert load_result.success is True
    assert load_result.state is not None

    loaded_mech = load_result.state.mechanisms["mech_1"]
    assert loaded_mech.params["l1"] == 120.0
    assert loaded_mech.params["input_angle"] == 30.0
    assert loaded_mech.layer_data["foundry_synced"] is True
    assert loaded_mech.layer_data["source"] == "foundry"
    assert loaded_mech.layer_data["key_points"]["ground_pivot_1"] == [10.0, 20.0]
    assert loaded_mech.layer_data["generated_path_data"]["points"][1] == [120.0, 120.0]


def test_serializer_reuses_existing_bundled_assets_on_repeated_save(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    texture_path = source_dir / "head.png"
    texture_path.write_bytes(b"texture-v1")

    part = PartData(
        name="head",
        texture_path=str(texture_path),
        mask_path="",
        anchor_joint="neck",
        transform=Transform(x=0.0, y=0.0, rotation=0.0, scale=1.0),
    )
    state = ProjectState.empty().with_project_dir(source_dir).with_parts({"head": part})
    serializer = ProjectSerializer()
    save_path = tmp_path / "repeat_save.automataii"

    first_result = serializer.save(state, save_path)
    second_result = serializer.save(state, save_path)

    assert first_result.success is True
    assert second_result.success is True

    asset_files = sorted((tmp_path / "repeat_save_assets" / "parts").glob("head_texture*.png"))
    assert len(asset_files) == 1


def test_serializer_deduplicates_shared_sources_within_single_save(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    shared_texture = source_dir / "shared.png"
    shared_texture.write_bytes(b"shared-texture")

    left_part = PartData(
        name="left_arm",
        texture_path=str(shared_texture),
        mask_path="",
        anchor_joint="left_shoulder",
        transform=Transform(x=0.0, y=0.0, rotation=0.0, scale=1.0),
    )
    right_part = PartData(
        name="right_arm",
        texture_path=str(shared_texture),
        mask_path="",
        anchor_joint="right_shoulder",
        transform=Transform(x=0.0, y=0.0, rotation=0.0, scale=1.0),
    )
    state = (
        ProjectState.empty()
        .with_project_dir(source_dir)
        .with_parts({"left_arm": left_part, "right_arm": right_part})
    )

    serializer = ProjectSerializer()
    save_path = tmp_path / "shared_assets.automataii"
    save_result = serializer.save(state, save_path)
    assert save_result.success is True

    asset_files = sorted((tmp_path / "shared_assets_assets" / "parts").glob("*.png"))
    assert len(asset_files) == 1
