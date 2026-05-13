import json
from pathlib import Path

from automataii.application.project import (
    AutoSaveManager,
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


def test_serializer_sanitizes_part_names_before_bundling_assets(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    texture_path = source_dir / "texture.png"
    texture_path.write_bytes(b"texture")

    part = PartData(
        name="../../escape",
        texture_path=str(texture_path),
        mask_path="",
        anchor_joint="neck",
        transform=Transform(x=0.0, y=0.0, rotation=0.0, scale=1.0),
    )
    state = ProjectState.empty().with_project_dir(source_dir).with_parts({"../../escape": part})

    serializer = ProjectSerializer()
    save_result = serializer.save(state, tmp_path / "unsafe_name.automataii")

    assert save_result.success is True
    assert not (tmp_path / "escape.png").exists()
    bundled_assets = sorted((tmp_path / "unsafe_name_assets" / "parts").glob("*.png"))
    assert len(bundled_assets) == 1
    assert bundled_assets[0].parent == tmp_path / "unsafe_name_assets" / "parts"


def test_serializer_sanitizes_collision_candidate_names_before_bundling_assets(tmp_path):
    """Collision suffixes must use the sanitized stem, not the raw part name."""
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    texture_path = source_dir / "texture.png"
    texture_path.write_bytes(b"new-texture")

    bundle_parts = tmp_path / "collision_assets" / "parts"
    bundle_parts.mkdir(parents=True, exist_ok=True)
    # Force the collision path so the serializer exercises the suffixed candidate branch.
    (bundle_parts / "escape_texture.png").write_bytes(b"different-texture")

    part = PartData(
        name="../../escape",
        texture_path=str(texture_path),
        mask_path="",
        anchor_joint="neck",
        transform=Transform(x=0.0, y=0.0, rotation=0.0, scale=1.0),
    )
    state = ProjectState.empty().with_project_dir(source_dir).with_parts({"../../escape": part})

    serializer = ProjectSerializer()
    save_result = serializer.save(state, tmp_path / "collision.automataii")

    assert save_result.success is True
    assert not (tmp_path / "escape_texture_1.png").exists()
    assert (bundle_parts / "escape_texture_1.png").exists()


def test_v1_to_v2_migration_updates_existing_metadata_version():
    serializer = ProjectSerializer()
    migrated = serializer._migrate_if_needed(
        {
            "metadata": {
                "version": "1.0",
                "name": "Legacy Project",
            },
            "layers": {},
        }
    )

    assert migrated["metadata"]["version"] == serializer.CURRENT_VERSION
    assert "parts" in migrated
    assert "paths" in migrated
    assert "mechanisms" in migrated


def test_serializer_validate_file_rejects_non_object_root(tmp_path):
    project_file = tmp_path / "bad.automataii"
    project_file.write_text("[]", encoding="utf-8")

    valid, error = ProjectSerializer().validate_file(project_file)

    assert valid is False
    assert error == "Project root must be a JSON object"


def test_serializer_validate_file_rejects_malformed_sections(tmp_path):
    project_file = tmp_path / "bad_sections.automataii"
    project_file.write_text(
        json.dumps({"metadata": [], "parts": []}),
        encoding="utf-8",
    )

    valid, error = ProjectSerializer().validate_file(project_file)

    assert valid is False
    assert error == "metadata section must be an object"


def test_serializer_get_project_info_handles_malformed_counts(tmp_path):
    project_file = tmp_path / "info.automataii"
    project_file.write_text(
        json.dumps({"metadata": {"name": "Info"}, "parts": [], "mechanisms": []}),
        encoding="utf-8",
    )

    info = ProjectSerializer().get_project_info(project_file)

    assert info is not None
    assert info["name"] == "Info"
    assert info["parts_count"] == 0
    assert info["mechanisms_count"] == 0


def test_serializer_creates_unique_backups_instead_of_overwriting(tmp_path):
    serializer = ProjectSerializer()
    project_file = tmp_path / "backup.automataii"
    project_file.write_text("v1", encoding="utf-8")
    (tmp_path / "backup.backup.automataii").write_text("existing-backup", encoding="utf-8")

    serializer._create_backup(project_file)

    assert (tmp_path / "backup.backup.automataii").read_text(encoding="utf-8") == "existing-backup"
    assert (tmp_path / "backup.backup1.automataii").read_text(encoding="utf-8") == "v1"


def test_autosave_manager_normalizes_invalid_intervals():
    serializer = ProjectSerializer()

    assert AutoSaveManager(serializer, interval_seconds=True)._interval == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    assert AutoSaveManager(serializer, interval_seconds="bad")._interval == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    assert AutoSaveManager(serializer, interval_seconds=0)._interval == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    assert AutoSaveManager(serializer, interval_seconds=5)._interval == 5
