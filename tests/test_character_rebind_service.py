from __future__ import annotations

from types import SimpleNamespace

from automataii.presentation.qt.tabs.mechanism_design.services.character_rebind_service import (
    MechanismCharacterRebindService,
)


def _part(anchor_joint_id: str, x: float = 0.0, y: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(anchor_joint_id=anchor_joint_id, x=x, y=y, roi=[x, y, 20.0, 20.0])


def test_rebind_linkage_uses_name_match_first_and_refits_to_anchor() -> None:
    service = MechanismCharacterRebindService(scene_to_mech=lambda _layer, pos: pos)

    mechanism_layers = {
        "right_arm_linkage_1": {
            "type": "4_bar_linkage",
            "part_name": "missing_part",
            "params": {
                "l1": 100.0,
                "l2": 40.0,
                "l3": 120.0,
                "l4": 130.0,
                "input_angle": 25.0,
                "ground_pivot_1": [0.0, 0.0],
                "ground_pivot_2": [100.0, 0.0],
            },
            "key_points": {
                "ground_pivot_1": [0.0, 0.0],
                "ground_pivot_2": [100.0, 0.0],
                "crank_end": [40.0, 0.0],
                "rocker_end": [80.0, 30.0],
            },
        }
    }
    parts_data = {
        "torso": _part("root", x=120.0, y=110.0),
        "right_arm": _part("right_elbow", x=50.0, y=40.0),
    }
    skeleton_cache = {"joints": {"right_elbow": {"position": [300.0, 200.0]}}}

    result = service.rebind_all(mechanism_layers, parts_data, skeleton_cache)

    assert result.failed_ids == []
    assert result.changed_ids == ["right_arm_linkage_1"]

    layer = mechanism_layers["right_arm_linkage_1"]
    assert layer["part_name"] == "right_arm"
    assert layer["params"]["ground_pivot_1"] == [250.0, 200.0]
    assert layer["params"]["ground_pivot_2"] == [350.0, 200.0]
    assert layer["params"]["input_angle"] == 25.0
    assert layer["params"]["crank_angle"] == 25.0
    assert layer["params"]["l2"] == layer["params"]["L2"]
    assert layer["params"]["l3"] == layer["params"]["L3"]
    assert layer["params"]["l4"] == layer["params"]["L4"]


def test_rebind_cam_clamps_and_updates_center_position() -> None:
    service = MechanismCharacterRebindService(scene_to_mech=lambda _layer, pos: pos)

    mechanism_layers = {
        "cam_1": {
            "type": "cam",
            "part_name": None,
            "params": {
                "base_radius": -2.0,
                "eccentricity": -5.0,
                "follower_rod_length": 1.0,
                "cam_lobes": 0.0,
                "profile_harmonic": 3.5,
            },
            "key_points": {},
        }
    }
    parts_data = {"torso": _part("root", x=10.0, y=20.0)}
    skeleton_cache = {"joints": {"root": {"position": [500.0, 350.0]}}}

    result = service.rebind_all(mechanism_layers, parts_data, skeleton_cache)

    assert result.failed_ids == []
    assert result.changed_ids == ["cam_1"]

    layer = mechanism_layers["cam_1"]
    params = layer["params"]
    assert layer["part_name"] == "torso"
    assert params["base_radius"] == 5.0
    assert params["eccentricity"] == 0.0
    assert params["follower_rod_length"] == 15.0
    assert params["cam_lobes"] == 1
    assert params["profile_harmonic"] == 1.0
    assert params["center_x"] == 500.0
    assert params["center_y"] == 350.0
    assert layer["cam_position"] == [500.0, 350.0]
    assert layer["key_points"]["cam_center"] == [500.0, 350.0]
    assert layer["key_points"]["follower_base"] == [500.0, 330.0]


def test_rebind_falls_back_to_torso_when_no_name_match() -> None:
    service = MechanismCharacterRebindService(scene_to_mech=lambda _layer, pos: pos)

    mechanism_layers = {
        "random_mechanism": {
            "type": "gear",
            "part_name": "not_present",
            "params": {},
            "key_points": {},
        }
    }
    parts_data = {
        "torso": _part("root", x=200.0, y=150.0),
        "left_leg": _part("left_knee", x=50.0, y=90.0),
    }

    result = service.rebind_all(mechanism_layers, parts_data, skeleton_cache=None)

    assert result.failed_ids == []
    assert result.changed_ids == ["random_mechanism"]
    assert mechanism_layers["random_mechanism"]["part_name"] == "torso"
