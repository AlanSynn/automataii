import json
from datetime import datetime as real_datetime
from datetime import timedelta
from pathlib import Path

from automataii.application.project import (
    AutoSaveManager,
    BoneData,
    JointData,
    MechanismData,
    PartData,
    PathData,
    Point,
    ProjectSerializer,
    ProjectState,
    SkeletonData,
    Transform,
)
from automataii.application.project.models import TimedPoint


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


def test_serializer_round_trip_preserves_mixed_project_payload(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    image_path = source_dir / "character.png"
    texture_path = source_dir / "torso.png"
    image_path.write_bytes(b"image")
    texture_path.write_bytes(b"texture")

    state = (
        ProjectState.empty()
        .with_project_dir(source_dir)
        .with_image_path(image_path)
        .with_parts(
            {
                "torso": PartData(
                    name="torso",
                    texture_path=str(texture_path),
                    mask_path="",
                    anchor_joint="root",
                    transform=Transform(x=12.0, y=34.0, rotation=5.0, scale=1.2),
                )
            }
        )
        .with_skeleton(
            SkeletonData(
                root_joint="root",
                joints={
                    "root": JointData(id="root", name="Root", position=Point(10.0, 20.0)),
                    "elbow": JointData(
                        id="elbow",
                        name="Elbow",
                        parent="root",
                        position=Point(40.0, 55.0),
                        is_locked=True,
                    ),
                },
                bones=(BoneData("root", "elbow"),),
            )
        )
        .with_paths(
            {
                "torso": PathData(
                    part_name="torso",
                    points=(Point(0.0, 0.0), Point(10.0, 5.0), Point(20.0, 0.0)),
                    timed_points=(
                        TimedPoint(0.0, 0.0, 0.0),
                        TimedPoint(10.0, 5.0, 0.5),
                        TimedPoint(20.0, 0.0, 1.0),
                    ),
                    total_duration=1.0,
                    is_closed=False,
                )
            }
        )
        .with_mechanisms(
            {
                "cam": MechanismData(
                    id="cam",
                    part_name="torso",
                    type="cam",
                    params={"base_radius": 25.0, "eccentricity": 10.0},
                    layer_data={
                        "full_simulation_data": {
                            "cam_data": {"follower_y_positions": [1.0, 2.0, 3.0]}
                        },
                        "key_points": {"cam_center": [10.0, 20.0]},
                    },
                ),
                "gear": MechanismData(
                    id="gear",
                    part_name="torso",
                    type="gear",
                    params={"gear1_radius": 40.0, "gear2_radius": 60.0},
                    layer_data={"key_points": {"gear2_center": [102.0, 0.0]}},
                    enabled=False,
                ),
            }
        )
    )

    serializer = ProjectSerializer()
    save_path = tmp_path / "mixed_project.automataii"
    assert serializer.save(state, save_path).success is True

    load_result = serializer.load(save_path)
    assert load_result.success is True
    assert load_result.state is not None

    loaded = load_result.state
    assert loaded.image_path is not None and loaded.image_path.exists()
    assert loaded.parts["torso"].transform.scale == 1.2
    assert loaded.skeleton is not None
    assert loaded.skeleton.joints["elbow"].is_locked is True
    assert loaded.paths["torso"].timed_points is not None
    assert loaded.paths["torso"].timed_points[1].t == 0.5
    assert loaded.mechanisms["cam"].layer_data["key_points"]["cam_center"] == [10.0, 20.0]
    assert loaded.mechanisms["gear"].enabled is False


def test_serializer_round_trip_preserves_cam_direction_and_gear_drag_payload(tmp_path):
    state = ProjectState.empty().with_mechanisms(
        {
            "cam_reverse": MechanismData(
                id="cam_reverse",
                part_name="torso",
                type="cam",
                params={
                    "base_radius": 32.0,
                    "eccentricity": 14.0,
                    "cam_lobes": 3,
                    "profile_harmonic": 0.45,
                    "output_point_mode": "contact_point",
                    "reverse_direction": True,
                },
                layer_data={
                    "source": "foundry",
                    "reverse_direction": True,
                    "cam_scale_factor": 1.25,
                    "rod_length_multiplier": 1.5,
                    "cam_points_local": [[0.0, 32.0], [20.0, 0.0], [0.0, -18.0]],
                    "key_points": {
                        "cam_center": [410.0, 320.0],
                        "contact_point": [410.0, 285.0],
                        "follower_base": [410.0, 225.0],
                    },
                },
            ),
            "gear_dragged": MechanismData(
                id="gear_dragged",
                part_name="torso",
                type="gear",
                params={
                    "gear1_radius": 38.0,
                    "gear2_radius": 57.0,
                    "gear1_x": 120.0,
                    "gear1_y": 140.0,
                    "gear2_x": 215.0,
                    "gear2_y": 140.0,
                },
                layer_data={
                    "key_points": {
                        "gear1_center": [120.0, 140.0],
                        "gear2_center": [215.0, 140.0],
                    }
                },
            ),
        }
    )

    serializer = ProjectSerializer()
    save_path = tmp_path / "cam_gear_payload.automataii"
    assert serializer.save(state, save_path).success is True

    load_result = serializer.load(save_path)
    assert load_result.success is True
    assert load_result.state is not None

    cam = load_result.state.mechanisms["cam_reverse"]
    assert cam.params["reverse_direction"] is True
    assert cam.params["cam_lobes"] == 3
    assert cam.params["profile_harmonic"] == 0.45
    assert cam.params["output_point_mode"] == "contact_point"
    assert cam.layer_data["reverse_direction"] is True
    assert cam.layer_data["cam_scale_factor"] == 1.25
    assert cam.layer_data["rod_length_multiplier"] == 1.5
    assert cam.layer_data["key_points"]["follower_base"] == [410.0, 225.0]

    gear = load_result.state.mechanisms["gear_dragged"]
    assert gear.params["gear1_radius"] == 38.0
    assert gear.params["gear2_radius"] == 57.0
    assert gear.layer_data["key_points"]["gear1_center"] == [120.0, 140.0]
    assert gear.layer_data["key_points"]["gear2_center"] == [215.0, 140.0]


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

    assert (
        AutoSaveManager(serializer, interval_seconds=True)._interval
        == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    )
    assert (
        AutoSaveManager(serializer, interval_seconds="bad")._interval
        == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    )
    assert (
        AutoSaveManager(serializer, interval_seconds=0)._interval
        == AutoSaveManager.DEFAULT_INTERVAL_SECONDS
    )
    assert AutoSaveManager(serializer, interval_seconds=5)._interval == 5


def test_autosave_manager_interval_can_be_updated_from_options():
    manager = AutoSaveManager(ProjectSerializer())

    manager.set_interval(120)

    assert manager.interval_seconds == 120


def test_autosave_manager_creates_distinct_same_second_snapshots(tmp_path, monkeypatch):
    from automataii.application.project import serializer as project_serializer

    class FrozenDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2026, 1, 2, 3, 4, 5, 123456)

    monkeypatch.setattr(project_serializer, "datetime", FrozenDateTime)

    serializer = ProjectSerializer()
    manager = AutoSaveManager(serializer)
    manager.setup(tmp_path)
    state = ProjectState.empty().with_project_dir(tmp_path)

    assert manager.autosave(state).success
    assert manager.autosave(state).success

    autosaves = [
        path
        for path in (tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME).glob("autosave_*.automataii")
        if ".backup" not in path.name
    ]
    assert len(autosaves) == 2


def test_autosave_throttle_skips_unchanged_content_after_interval(tmp_path):
    manager = AutoSaveManager(ProjectSerializer(), interval_seconds=1)
    manager.setup(tmp_path)
    state = (
        ProjectState.empty()
        .with_project_dir(tmp_path)
        .with_parts(
            {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                )
            }
        )
    )

    assert manager.autosave(state).success
    manager._last_save = real_datetime.now() - timedelta(seconds=2)

    assert manager.should_save(state) is False


def test_autosave_does_not_bundle_duplicate_asset_directories(tmp_path):
    asset = tmp_path / "head.png"
    asset.write_bytes(b"image")
    manager = AutoSaveManager(ProjectSerializer())
    manager.setup(tmp_path)
    state = (
        ProjectState.empty()
        .with_project_dir(tmp_path)
        .with_parts(
            {
                "head": PartData(
                    name="head",
                    texture_path=str(asset),
                    mask_path=str(asset),
                    anchor_joint="neck",
                )
            }
        )
    )

    assert manager.autosave(state).success

    assert not list((tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME).glob("*_assets"))


def test_autosave_recovery_files_exclude_serializer_backups(tmp_path):
    manager = AutoSaveManager(ProjectSerializer())
    autosave_dir = tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME
    autosave_dir.mkdir()
    real_autosave = autosave_dir / "autosave_20260102_030405_123456.automataii"
    backup_autosave = autosave_dir / "autosave_20260102_030405_123456.backup.automataii"
    real_autosave.write_text("{}", encoding="utf-8")
    backup_autosave.write_text("backup", encoding="utf-8")

    assert manager.get_recovery_files(tmp_path) == [real_autosave]
