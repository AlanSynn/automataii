from __future__ import annotations

import math
import sys

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from automataii.presentation.qt.tabs.mechanism_design.parametric.controllers.parameter_controller import (
    ParameterController,
)
from automataii.presentation.qt.tabs.mechanism_design.parametric.services.path_optimization_service import (
    PathOptimizationService,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class _DummyMechanismTab:
    def __init__(self) -> None:
        self.mechanism_layers = {
            "m": {"type": "gear", "params": {}},
            "cam": {"type": "cam", "params": []},
        }
        self.emitted: list[str] = []
        self.regenerated: list[str] = []

    def _emit_mechanism_params_changed(self, mechanism_id: str) -> None:
        self.emitted.append(mechanism_id)

    def _regenerate_cam_mechanism_realtime(self, mechanism_id: str, _layer_data: dict) -> None:
        self.regenerated.append(mechanism_id)


class _DummyController:
    def __init__(self) -> None:
        self.mechanism_tab = _DummyMechanismTab()
        self.applied: list[tuple[str, str, float]] = []

    def _on_parameter_changed(self, mechanism_id: str, param_name: str, value: float) -> None:
        self.applied.append((mechanism_id, param_name, value))


def test_parameter_controller_normalizes_throttle_and_ignores_invalid_changes(qapp) -> None:
    tab = _DummyMechanismTab()
    controller = ParameterController(tab, update_throttle_ms=True)

    assert controller.update_throttle_ms == 50

    controller._on_parameter_changed("", "p", 1.0)
    controller._on_parameter_changed("m", "", 1.0)
    controller._on_parameter_changed("m", "p", math.nan)

    assert not controller.pending_updates
    assert not controller.change_history


def test_parameter_controller_preserves_reentrant_updates(qapp) -> None:
    tab = _DummyMechanismTab()
    controller = ParameterController(tab, update_throttle_ms=1000)
    seen: list[dict] = []

    def queue_next(mechanism_id: str, changes: dict) -> None:
        seen.append(changes)
        controller._on_parameter_changed(mechanism_id, "second", 2.0)

    controller.mechanism_update_requested.connect(queue_next)
    controller.pending_updates = {"m": {"first": 1.0}}
    controller._process_pending_updates()

    assert seen == [{"first": 1.0}]
    assert controller.pending_updates == {"m": {"second": 2.0}}


def test_parameter_controller_sanitizes_cam_recalculation_payload(qapp) -> None:
    tab = _DummyMechanismTab()
    controller = ParameterController(tab)

    controller._apply_parameter_changes(
        "cam",
        {
            "base_radius": "bad",
            "eccentricity": math.inf,
            "follower_rod_length": -999.0,
        },
    )

    params = tab.mechanism_layers["cam"]["params"]
    assert params["base_radius"] == 25.0
    assert params["eccentricity"] == 10.0
    assert params["follower_rod_length"] == 15.0
    assert params["cam_center"] == [10.0, 0.0]
    assert tab.regenerated == ["cam"]


def test_path_optimization_extracts_only_finite_parameters(qapp) -> None:
    service = PathOptimizationService(_DummyController())

    params = service._extract_current_parameters(
        {"params": {"l2": -10.0, "l3": math.inf, "l4": "90", "theta2": math.nan}}
    )

    assert params == {"l2": 5.0, "l4": 90.0}


def test_path_optimization_handles_bad_sampling_and_triangle_edges(qapp) -> None:
    service = PathOptimizationService(_DummyController())
    service.path_sample_count = 0

    mechanism_data = {
        "key_points": {
            "ground_pivot_1": [0.0, 0.0],
            "ground_pivot_2": [100.0, 0.0],
        }
    }
    path = service._generate_mechanism_path({"l2": 30.0, "l3": 40.0, "l4": 35.0}, mechanism_data)

    assert path is not None
    assert len(path) <= 4
    assert service._solve_rocker_angle(QPointF(0.0, 0.0), QPointF(0.0, 0.0), 10.0, 10.0) is None


def test_path_optimization_filters_nonfinite_path_points(qapp) -> None:
    service = PathOptimizationService(_DummyController())

    sampled = service._sample_path_points(
        [QPointF(0.0, 0.0), QPointF(math.nan, 1.0), QPointF(10.0, 0.0)],
        2,
    )

    assert [(point.x(), point.y()) for point in sampled] == [(0.0, 0.0), (10.0, 0.0)]


def test_path_optimization_rejects_missing_or_malformed_target_path(qapp) -> None:
    service = PathOptimizationService(_DummyController())
    failures: list[str] = []
    service.optimization_failed.connect(lambda _mid, message: failures.append(message))

    service.target_paths["m"] = [QPointF(math.nan, 0.0)]
    service._run_optimization_async("m", {"l2": 30.0}, {"key_points": {}})

    assert failures == ["Target path must contain at least two finite points"]
    assert service.active_optimizations["m"] is False
