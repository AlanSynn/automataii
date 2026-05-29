from __future__ import annotations

from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QGraphicsEllipseItem

from automataii.presentation.qt.tabs.mechanism_design.services.anchor_position_service import (
    AnchorPositionService,
)
from automataii.presentation.qt.tabs.mechanism_design.services.handle_position_coordinator import (
    HandlePositionCoordinator,
)
from automataii.presentation.qt.tabs.mechanism_design.services.transform_service import (
    TransformService,
)


class _DummyHandle:
    def __init__(self, handle_id: str) -> None:
        self.handle_id = handle_id
        self._pos = QPointF(0.0, 0.0)

    def setPos(self, pos: QPointF) -> None:
        self._pos = QPointF(pos.x(), pos.y())

    @property
    def pos(self) -> QPointF:
        return self._pos


def test_cam_anchor_positions_include_center_and_follower_keys() -> None:
    service = AnchorPositionService(TransformService())
    layer_data = {
        "type": "cam",
        "params": {
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "full_simulation_data": {},
        "transform_params": {},
        "generated_path": None,
        "visual_items": [],
    }

    anchors = service.get_anchor_positions(layer_data)
    assert "cam_center" in anchors
    assert "center" in anchors
    assert "cam_follower" in anchors
    assert "follower" in anchors
    assert "cam_size" in anchors
    assert "cam_rod_length" in anchors
    assert anchors["cam_follower"].y() == 270.0


def test_cam_anchor_positions_apply_cam_scale_factor_to_contact_and_size() -> None:
    service = AnchorPositionService(TransformService())
    layer_data = {
        "type": "cam",
        "cam_scale_factor": 2.0,
        "rod_length_multiplier": 2.0,
        "params": {
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
        },
        "full_simulation_data": {},
        "transform_params": {},
        "generated_path": None,
        "visual_items": [],
    }

    anchors = service.get_anchor_positions(layer_data)

    # Fallback transform is x/y * 2 + (400, 300). Scaled contact y=50 -> scene y=400,
    # scaled rod=80 and scene unit scale=2 -> follower head y=240.
    assert anchors["cam_follower"].x() == 400.0
    assert anchors["cam_follower"].y() == 240.0
    # Size handle uses the scaled max radius: (25 + 10) * 2, then fallback x * 2 + 400.
    assert anchors["cam_size"].x() == 540.0
    assert anchors["cam_size"].y() == 300.0


def test_gear_anchor_positions_include_radius_handles() -> None:
    service = AnchorPositionService(TransformService())
    layer_data = {
        "type": "gear",
        "params": {"r1": 30.0, "r2": 50.0},
        "full_simulation_data": {},
        "transform_params": {},
        "generated_path": None,
        "visual_items": [],
        "key_points": {},
    }

    anchors = service.get_anchor_positions(layer_data)
    assert "gear1_center" in anchors
    assert "gear2_center" in anchors
    assert "gear1_radius" in anchors
    assert "gear2_radius" in anchors
    assert anchors["gear1_radius"].x() > anchors["gear1_center"].x()
    assert anchors["gear2_radius"].x() > anchors["gear2_center"].x()


def _ellipse_at(x: float, y: float, size: float, tooltip: str = "") -> QGraphicsEllipseItem:
    item = QGraphicsEllipseItem(x - size / 2.0, y - size / 2.0, size, size)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def test_fourbar_anchor_positions_use_named_outer_pivots_not_inner_highlights() -> None:
    service = AnchorPositionService(TransformService())
    visual_items = []
    for x, y, tooltip in [
        (10.0, 20.0, "Ground Pivot 1"),
        (110.0, 20.0, "Ground Pivot 2"),
        (40.0, -10.0, "Moving Joint 1"),
        (80.0, -15.0, "Moving Joint 2"),
    ]:
        visual_items.append(_ellipse_at(x, y, 16.0, tooltip))
        visual_items.append(_ellipse_at(x, y, 8.0))

    anchors = service.get_anchor_positions(
        {
            "type": "4_bar_linkage",
            "params": {},
            "visual_items": visual_items,
            "full_simulation_data": {},
            "transform_params": {},
            "generated_path": None,
        }
    )

    assert anchors["ground_pivot_1"] == QPointF(10.0, 20.0)
    assert anchors["ground_pivot_2"] == QPointF(110.0, 20.0)
    assert anchors["crank_end"] == QPointF(40.0, -10.0)
    assert anchors["rocker_end"] == QPointF(80.0, -15.0)


def test_handle_position_coordinator_updates_cam_size_handles() -> None:
    coordinator = HandlePositionCoordinator()
    handle = _DummyHandle("mechanism_size")
    target = QPointF(12.0, -8.0)

    updated = coordinator.update_handles_for_mechanism(
        mechanism_id="m1",
        handles=[handle],
        layer_data={"type": "cam"},
        anchor_positions={"cam_size": target},
    )

    assert updated == 1
    assert handle.pos.x() == target.x()
    assert handle.pos.y() == target.y()


def test_planetary_anchor_positions_include_radius_and_arm_handles() -> None:
    service = AnchorPositionService(TransformService())
    layer_data = {
        "type": "planetary_gear",
        "params": {
            "sun_x": 120.0,
            "sun_y": 80.0,
            "r_sun": 20.0,
            "r_planet": 30.0,
            "arm_length": 15.0,
        },
        "full_simulation_data": {},
        "transform_params": {},
        "generated_path": None,
        "visual_items": [],
        "key_points": {},
    }

    anchors = service.get_anchor_positions(layer_data)
    assert "sun_center" in anchors
    assert "planet_center" in anchors
    assert "planet_radius" in anchors
    assert "arm_length" in anchors
    assert anchors["sun_center"].x() == 120.0
    assert anchors["sun_center"].y() == 80.0
    assert anchors["planet_center"].x() > anchors["sun_center"].x()
    assert anchors["planet_radius"].x() > anchors["planet_center"].x()
    assert anchors["arm_length"].x() > anchors["planet_center"].x()


def test_handle_position_coordinator_updates_planetary_radius_and_arm_handles() -> None:
    coordinator = HandlePositionCoordinator()
    radius_handle = _DummyHandle("mechanism_planet_radius")
    arm_handle = _DummyHandle("mechanism_arm_length")
    radius_target = QPointF(50.0, 10.0)
    arm_target = QPointF(85.0, 10.0)

    updated = coordinator.update_handles_for_mechanism(
        mechanism_id="m2",
        handles=[radius_handle, arm_handle],
        layer_data={"type": "planetary_gear"},
        anchor_positions={"planet_radius": radius_target, "arm_length": arm_target},
    )

    assert updated == 2
    assert radius_handle.pos.x() == radius_target.x()
    assert radius_handle.pos.y() == radius_target.y()
    assert arm_handle.pos.x() == arm_target.x()
    assert arm_handle.pos.y() == arm_target.y()


def test_transform_service_uses_identity_for_foundry_scene_space_layer() -> None:
    service = TransformService()
    layer_data = {
        "source": "foundry",
        "coordinate_space": "scene",
        "generated_path": None,
        "transform_params": {"center": [0.0, 0.0], "scale": 1.0, "rotation": 0.0},
        "key_points": {"ground_pivot_1": [350.0, 220.0]},
    }

    to_scene = service.get_scene_transform(layer_data)
    assert to_scene is not None
    point = to_scene([350.0, 220.0])
    assert point.x() == 350.0
    assert point.y() == 220.0

    to_mech = service.get_inverse_scene_transform(layer_data)
    assert to_mech is not None
    mech_point = to_mech(QPointF(350.0, 220.0))
    assert float(mech_point[0]) == 350.0
    assert float(mech_point[1]) == 220.0


def test_transform_service_uses_foundry_heuristic_for_legacy_layers() -> None:
    service = TransformService()
    layer_data = {
        "source": "foundry",
        "generated_path": None,
        "transform_params": {"center": [0.0, 0.0], "scale": 1.0, "rotation": 0.0},
        "key_points": {"ground_pivot_1": [500.0, 310.0]},
    }

    to_scene = service.get_scene_transform(layer_data)
    assert to_scene is not None
    point = to_scene([500.0, 310.0])
    assert point.x() == 500.0
    assert point.y() == 310.0


def test_handle_position_coordinator_aliases_foundry_key_points_without_anchor_attrs() -> None:
    coordinator = HandlePositionCoordinator()
    handles = [
        _DummyHandle("m1_anchor1"),
        _DummyHandle("m1_anchor2"),
        _DummyHandle("m1_crank"),
        _DummyHandle("m1_rocker"),
        _DummyHandle("m1_coupler"),
        _DummyHandle("m1_crank_length"),
    ]
    layer_data = {
        "type": "4_bar_linkage",
        "key_points": {
            "ground_pivot_1": [325.0, 300.0],
            "ground_pivot_2": [475.0, 300.0],
            "crank_end": [360.0, 320.0],
            "rocker_end": [460.0, 345.0],
            "coupler_point": [410.0, 360.0],
        },
        "params": {"coupler_point_x": 60.0, "coupler_point_y": 30.0},
    }

    updated = coordinator.update_handles_from_key_points(
        "m1",
        handles,  # type: ignore[arg-type]
        layer_data,
        lambda _layer: lambda point: QPointF(float(point[0]), float(point[1])),
    )

    assert updated == len(handles)
    expected = {
        "m1_anchor1": (325.0, 300.0),
        "m1_anchor2": (475.0, 300.0),
        "m1_crank": (360.0, 320.0),
        "m1_rocker": (460.0, 345.0),
        "m1_coupler": (410.0, 360.0),
        "m1_crank_length": (342.5, 310.0),
    }
    for handle in handles:
        assert (handle.pos.x(), handle.pos.y()) == expected[handle.handle_id]
