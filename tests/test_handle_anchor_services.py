from __future__ import annotations

from PyQt6.QtCore import QPointF

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
