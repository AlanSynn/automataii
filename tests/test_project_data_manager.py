import json
from pathlib import Path

import yaml

from automataii.application.managers.project_data_manager import ProjectDataManager


def _standardized_char_cfg_dict() -> dict:
    return {
        "skeleton": {
            "joints": {
                "root": {
                    "id": "root",
                    "name": "root",
                    "position": [10.0, 20.0],
                    "parent_id": None,
                },
                "torso": {
                    "id": "torso",
                    "name": "torso",
                    "position": [15.0, 35.0],
                    "parent_id": "root",
                },
            },
            "hierarchy": {"root": ["torso"]},
        }
    }


def test_extract_skeleton_list_supports_standardized_dict(tmp_path: Path) -> None:
    manager = ProjectDataManager()

    extracted = manager._extract_skeleton_list(
        _standardized_char_cfg_dict(), tmp_path / "char_cfg.yaml"
    )

    assert extracted is not None
    assert len(extracted) == 2
    by_name = {entry["name"]: entry for entry in extracted}
    assert by_name["root"]["parent"] is None
    assert by_name["root"]["loc"] == [10.0, 20.0]
    assert by_name["torso"]["parent"] == "root"
    assert by_name["torso"]["loc"] == [15.0, 35.0]


def test_load_project_from_file_reads_standardized_supplemental_char_cfg(tmp_path: Path) -> None:
    project_file = tmp_path / "parts_info.json"
    project_file.write_text(
        json.dumps({"character": {"name": "demo", "parts": {}}}), encoding="utf-8"
    )

    char_cfg_path = tmp_path / "char_cfg.yaml"
    char_cfg_path.write_text(
        yaml.safe_dump(_standardized_char_cfg_dict(), sort_keys=False), encoding="utf-8"
    )

    manager = ProjectDataManager()
    assert manager.load_project_from_file(str(project_file)) is True

    raw = manager.raw_skeleton_data
    assert raw is not None
    assert len(raw) == 2
    ids = {joint["id"] for joint in raw}
    assert ids == {"root", "torso"}


def test_load_project_from_file_reads_primary_skeleton_joints_without_clear_signal(
    tmp_path: Path,
) -> None:
    project_file = tmp_path / "parts_info.json"
    project_file.write_text(
        json.dumps(
            {
                "character": {
                    "name": "generated",
                    "parts": {},
                    "skeleton_joints": [
                        {
                            "id": "root",
                            "name": "root",
                            "position": [10.0, 20.0],
                            "parent": None,
                        },
                        {
                            "id": "torso",
                            "name": "torso",
                            "position": [15.0, 35.0],
                            "parent": "root",
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manager = ProjectDataManager()
    clear_count = 0

    def _on_cleared() -> None:
        nonlocal clear_count
        clear_count += 1

    manager.project_data_cleared.connect(_on_cleared)

    assert manager.load_project_from_file(str(project_file)) is True

    raw = manager.raw_skeleton_data
    assert raw is not None
    assert [joint["id"] for joint in raw] == ["root", "torso"]
    assert clear_count == 0


def test_legacy_direct_save_fails_explicitly_instead_of_writing_partial_project(
    tmp_path: Path,
) -> None:
    project_file = tmp_path / "parts_info.json"
    project_file.write_text(
        json.dumps({"character": {"name": "generated", "parts": {}}}),
        encoding="utf-8",
    )
    save_path = tmp_path / "legacy-output.json"

    manager = ProjectDataManager()
    assert manager.load_project_from_file(str(project_file)) is True

    assert manager.save_project_to_file(str(save_path)) is False
    assert not save_path.exists()
