"""Regression tests for mechanism initial-render guard paths."""

from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
)

from automataii.presentation.qt.mechanisms.visualization.base import VisualizationConfig
from automataii.presentation.qt.mechanisms.visualization.visualizers.cam import (
    CamVisualizer as RegisteredCamVisualizer,
)
from automataii.presentation.qt.tabs.cam_geometry import cam_contact_local_from_profile
from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_output_calculator import (
    MechanismOutputCalculator,
)
from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_visual_animator import (
    MechanismVisualAnimator,
)
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
from automataii.presentation.qt.tabs.visualizers.cam_visualizer import (
    CamVisualizer as TabCamVisualizer,
)


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _identity(point: object) -> QPointF:
    coords = np.asarray(point, dtype=float)
    return QPointF(float(coords[0]), float(coords[1]))


def _rect_center(item: QGraphicsEllipseItem) -> tuple[float, float]:
    center = item.rect().center()
    return float(center.x()), float(center.y())


def _assert_items_have_finite_bounds(items: list[object]) -> None:
    for item in items:
        rect = item.sceneBoundingRect()
        assert np.isfinite([rect.left(), rect.top(), rect.width(), rect.height()]).all()


def test_planetary_visuals_ignore_partial_simulation_positions_and_use_key_points(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "type": "planetary_gear",
        "params": {"r_sun": float("nan"), "r_planet": 0.0, "arm_length": -5.0},
        "key_points": {
            "sun_center": [100.0, 100.0],
            "planet_center": [100.0, 150.0],
            "tracking_point": [100.0, 165.0],
        },
        "full_simulation_data": {
            "gear_positions": {
                "sun_centers": [[float("nan"), 0.0]],
            }
        },
    }

    items = MechanismVisualsFactory(scene).create_planetary_gear_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert len(items) == 6
    assert isinstance(items[0], QGraphicsEllipseItem)
    assert isinstance(items[1], QGraphicsEllipseItem)
    assert isinstance(items[3], QGraphicsEllipseItem)
    assert _rect_center(items[0]) == pytest.approx((100.0, 100.0))
    assert _rect_center(items[1]) == pytest.approx((100.0, 150.0))
    assert _rect_center(items[3]) == pytest.approx((100.0, 165.0))


def test_fourbar_visuals_use_foundry_scene_key_points_without_simulation_data(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "type": "4_bar_linkage",
        "coordinate_space": "scene",
        "source": "foundry",
        "params": {
            "l1": 150.0,
            "l2": 40.0,
            "l3": 120.0,
            "l4": 130.0,
            "coupler_point_x": 60.0,
            "coupler_point_y": 30.0,
        },
        "key_points": {
            "ground_pivot_1": [325.0, 300.0],
            "ground_pivot_2": [475.0, 300.0],
            "crank_end": [360.0, 320.0],
            "rocker_end": [460.0, 345.0],
            "coupler_point": [410.0, 360.0],
        },
    }

    items = MechanismVisualsFactory(scene).create_4bar_linkage_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert items
    assert isinstance(items[0], QGraphicsLineItem)
    driver = items[0].line()
    follower = items[1].line()
    assert (driver.p1().x(), driver.p1().y()) == pytest.approx((325.0, 300.0))
    assert (driver.p2().x(), driver.p2().y()) == pytest.approx((360.0, 320.0))
    assert (follower.p1().x(), follower.p1().y()) == pytest.approx((475.0, 300.0))
    assert (follower.p2().x(), follower.p2().y()) == pytest.approx((460.0, 345.0))


def test_fourbar_diagnostics_hidden_by_default_in_non_debug_ui(qapp: QApplication) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "params": {"l1": 100.0, "l2": 40.0, "l3": 80.0, "l4": 90.0},
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0], [0.0, 0.0]],
                "p2_positions": [[100.0, 0.0], [100.0, 0.0]],
                "p3_positions": [[40.0, 0.0], [30.0, 10.0]],
                "p4_positions": [[80.0, 30.0], [78.0, 25.0]],
            }
        },
    }

    items = MechanismVisualsFactory(scene).create_4bar_linkage_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert items
    assert not any(
        isinstance(item, QGraphicsTextItem) and "μ_min" in item.toPlainText()
        for item in scene.items()
    )


def test_fourbar_diagnostics_can_be_enabled_for_debug_ui(qapp: QApplication) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "params": {"l1": 100.0, "l2": 40.0, "l3": 80.0, "l4": 90.0},
        "full_simulation_data": {
            "joint_positions": {
                "p1_positions": [[0.0, 0.0], [0.0, 0.0]],
                "p2_positions": [[100.0, 0.0], [100.0, 0.0]],
                "p3_positions": [[40.0, 0.0], [30.0, 10.0]],
                "p4_positions": [[80.0, 30.0], [78.0, 25.0]],
            }
        },
    }

    MechanismVisualsFactory(scene, show_diagnostics=True).create_4bar_linkage_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert any(
        isinstance(item, QGraphicsTextItem) and "μ_min" in item.toPlainText()
        for item in scene.items()
    )


def test_cam_visual_animator_and_output_use_rotated_scene_vertical_follower(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "type": "cam",
        "params": {
            "m_center_x": 0.0,
            "m_center_y": 0.0,
            "base_radius": 25.0,
            "eccentricity": 10.0,
            "follower_rod_length": 40.0,
            "output_point_mode": "follower_end",
        },
    }

    def rotate_90(point: object) -> QPointF:
        coords = np.asarray(point, dtype=float)
        return QPointF(-float(coords[1]), float(coords[0]))

    factory = MechanismVisualsFactory(scene)
    visual_items = factory.create_cam_visuals(layer_data, transform_function=rotate_90)
    layer_data["visual_items"] = visual_items

    animator = MechanismVisualAnimator(get_scene_transform=lambda _layer: rotate_90)
    animator.update_visuals("cam_1", 0.0, layer_data, factory)

    assert isinstance(visual_items[2], QGraphicsLineItem)
    rod = visual_items[2].line()
    assert rod.p1().x() == pytest.approx(-25.0)
    assert rod.p1().y() == pytest.approx(0.0)
    assert rod.p2().x() == pytest.approx(-25.0)
    assert rod.p2().y() == pytest.approx(-40.0)

    calculator = MechanismOutputCalculator(get_scene_transform=lambda _layer: rotate_90)
    output = calculator.calculate_output(
        mech_type="cam",
        params=layer_data["params"],
        time=0.0,
        layer_data=layer_data,
    )

    assert output is not None
    assert output.x() == pytest.approx(-25.0)
    assert output.y() == pytest.approx(-40.0)


def test_gear_linkage_visuals_survive_export_and_animate(
    qapp: QApplication,
) -> None:
    from automataii.shared.physical_kit import DEFAULT_HOLE_DIAMETER_MM

    scene = QGraphicsScene()
    layer_data = {
        "type": "gear",
        "coordinate_space": "scene",
        "source": "foundry",
        "params": {
            "gear1_x": 0.0,
            "gear1_y": 0.0,
            "gear2_x": 100.0,
            "gear2_y": 0.0,
            "gear1_radius": 30.0,
            "gear2_radius": 50.0,
            "r1": 30.0,
            "r2": 50.0,
            "gear_linkage_enabled": True,
            "linkage_pin_radius": 999.0,
            "linkage_arm_length": 40.0,
        },
        "key_points": {
            "gear1_center": [0.0, 0.0],
            "gear2_center": [100.0, 0.0],
        },
    }

    visual_items = MechanismVisualsFactory(scene).create_gear_visuals(layer_data)
    layer_data["visual_items"] = visual_items

    linkage_items = {item.data(0): item for item in visual_items if hasattr(item, "data")}
    assert isinstance(linkage_items.get("gear_linkage_arm"), QGraphicsLineItem)
    assert isinstance(linkage_items.get("gear_linkage_pin"), QGraphicsEllipseItem)
    assert isinstance(linkage_items.get("gear_linkage_end"), QGraphicsEllipseItem)

    arm = linkage_items["gear_linkage_arm"]
    assert isinstance(arm, QGraphicsLineItem)
    before = arm.line()
    expected_pin_x = 100.0 + 50.0 - (DEFAULT_HOLE_DIAMETER_MM / 2.0)
    assert before.p1().x() == pytest.approx(expected_pin_x)
    assert before.p2().x() == pytest.approx(expected_pin_x + 40.0)

    animator = MechanismVisualAnimator(get_scene_transform=lambda _layer: _identity)
    animator.update_visuals("gear_linkage_1", np.pi / 2.0, layer_data)

    after = arm.line()
    assert after.p1().x() != pytest.approx(before.p1().x())
    assert after.p1().y() != pytest.approx(before.p1().y())


def test_gear_linkage_output_uses_linkage_end(
    qapp: QApplication,
) -> None:
    from automataii.shared.physical_kit import DEFAULT_HOLE_DIAMETER_MM

    layer_data = {
        "type": "gear",
        "coordinate_space": "scene",
        "source": "foundry",
        "params": {
            "gear1_radius": 30.0,
            "gear2_radius": 50.0,
            "r1": 30.0,
            "r2": 50.0,
            "gear_linkage_enabled": True,
            "linkage_pin_radius": 999.0,
            "linkage_arm_length": 40.0,
        },
        "key_points": {
            "gear1_center": [0.0, 0.0],
            "gear2_center": [100.0, 0.0],
        },
        "full_simulation_data": {
            "gear_data": {
                "tracking_points": [[999.0, 999.0]],
            },
        },
    }

    calculator = MechanismOutputCalculator(get_scene_transform=lambda _layer: _identity)
    output = calculator.calculate_output(
        mech_type="gear",
        params=layer_data["params"],
        time=0.0,
        layer_data=layer_data,
    )

    assert output is not None
    expected_pin_x = 100.0 + 50.0 - (DEFAULT_HOLE_DIAMETER_MM / 2.0)
    assert output.x() == pytest.approx(expected_pin_x + 40.0)
    assert output.y() == pytest.approx(0.0)


def test_cam_visual_animator_honors_reverse_direction_phase(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    asymmetric_profile = np.asarray(
        [
            [0.0, 10.0],
            [20.0, 0.0],
            [0.0, -10.0],
            [-5.0, 0.0],
        ],
        dtype=float,
    )
    visual_items = [
        QGraphicsPolygonItem(),
        QGraphicsEllipseItem(),
        QGraphicsLineItem(),
        QGraphicsRectItem(),
        QGraphicsRectItem(),
        QGraphicsEllipseItem(),
    ]
    for item in visual_items:
        scene.addItem(item)
    layer_data = {
        "type": "cam",
        "reverse_direction": True,
        "cam_points_local": asymmetric_profile,
        "visual_items": visual_items,
        "params": {
            "base_radius": 20.0,
            "eccentricity": 5.0,
            "follower_rod_length": 30.0,
        },
    }

    phase = 0.6
    animator = MechanismVisualAnimator(get_scene_transform=lambda _layer: _identity)
    animator.update_visuals("cam_reverse", phase, layer_data, None)

    expected_contact = cam_contact_local_from_profile(asymmetric_profile, -phase)
    assert _rect_center(visual_items[1]) == pytest.approx(
        (float(expected_contact[0]), float(expected_contact[1]))
    )
    rod = visual_items[2].line()
    assert (rod.p1().x(), rod.p1().y()) == pytest.approx(
        (float(expected_contact[0]), float(expected_contact[1]))
    )
    assert rod.p2().y() == pytest.approx(float(expected_contact[1]) - 30.0)


def test_cam_generated_path_alignment_uses_shared_contact_and_center(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    generated_path = QPainterPath()
    generated_path.addRect(100.0, 50.0, 80.0, 50.0)
    layer_data = {
        "type": "cam",
        "generated_path": generated_path,
        "params": {
            "base_radius": 25.0,
            "eccentricity": 0.0,
            "follower_rod_length": 40.0,
        },
    }

    visual_items = MechanismVisualsFactory(scene).create_cam_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert len(visual_items) >= 6
    assert isinstance(visual_items[1], QGraphicsEllipseItem)
    assert isinstance(visual_items[2], QGraphicsLineItem)
    assert isinstance(visual_items[5], QGraphicsEllipseItem)

    assert _rect_center(visual_items[1]) == pytest.approx((140.0, 100.0))
    rod = visual_items[2].line()
    assert (rod.p1().x(), rod.p1().y()) == pytest.approx((140.0, 100.0))
    assert (rod.p2().x(), rod.p2().y()) == pytest.approx((140.0, 60.0))
    assert _rect_center(visual_items[5]) == pytest.approx((140.0, 75.0))
    assert layer_data["cam_position"] == pytest.approx([140.0, 75.0])


def test_cam_generated_path_alignment_uses_scaled_profile(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    generated_path = QPainterPath()
    generated_path.addRect(100.0, 50.0, 80.0, 50.0)
    layer_data = {
        "type": "cam",
        "generated_path": generated_path,
        "cam_scale_factor": 2.0,
        "rod_length_multiplier": 2.0,
        "params": {
            "base_radius": 25.0,
            "eccentricity": 0.0,
            "follower_rod_length": 40.0,
        },
    }

    visual_items = MechanismVisualsFactory(scene).create_cam_visuals(
        layer_data,
        transform_function=_identity,
    )

    assert len(visual_items) >= 6
    assert isinstance(visual_items[1], QGraphicsEllipseItem)
    assert isinstance(visual_items[2], QGraphicsLineItem)
    assert isinstance(visual_items[5], QGraphicsEllipseItem)

    assert _rect_center(visual_items[1]) == pytest.approx((140.0, 100.0))
    rod = visual_items[2].line()
    assert (rod.p1().x(), rod.p1().y()) == pytest.approx((140.0, 100.0))
    assert (rod.p2().x(), rod.p2().y()) == pytest.approx((140.0, 20.0))
    assert _rect_center(visual_items[5]) == pytest.approx((140.0, 50.0))
    assert layer_data["cam_position"] == pytest.approx([140.0, 50.0])


def test_foundry_scene_cam_visuals_and_initial_animation_use_snapshot_key_points(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "type": "cam",
        "source": "foundry",
        "coordinate_space": "scene",
        "cam_position": [520.0, 360.0],
        "params": {
            "center_x": 520.0,
            "center_y": 360.0,
            "base_radius": 60.0,
            "eccentricity": 20.0,
            "follower_rod_length": 100.0,
        },
        "key_points": {
            "cam_center": [520.0, 360.0],
            "contact_point": [520.0, 300.0],
            "follower_base": [520.0, 220.0],
        },
    }
    factory = MechanismVisualsFactory(scene)

    visual_items = factory.create_cam_visuals(layer_data, transform_function=_identity)
    layer_data["visual_items"] = visual_items

    assert len(visual_items) >= 6
    assert isinstance(visual_items[1], QGraphicsEllipseItem)
    assert isinstance(visual_items[2], QGraphicsLineItem)
    assert _rect_center(visual_items[1]) == pytest.approx((520.0, 300.0))
    rod = visual_items[2].line()
    assert (rod.p1().x(), rod.p1().y()) == pytest.approx((520.0, 300.0))
    assert (rod.p2().x(), rod.p2().y()) == pytest.approx((520.0, 220.0))

    animator = MechanismVisualAnimator(get_scene_transform=lambda _layer: _identity)
    animator.update_visuals("foundry_cam", 0.0, layer_data, factory)

    assert _rect_center(visual_items[1]) == pytest.approx((520.0, 300.0))
    rod = visual_items[2].line()
    assert (rod.p1().x(), rod.p1().y()) == pytest.approx((520.0, 300.0))
    assert (rod.p2().x(), rod.p2().y()) == pytest.approx((520.0, 220.0))


def test_secondary_cam_visualizers_use_shared_scene_vertical_follower(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()
    layer_data = {
        "params": {
            "base_radius": 25.0,
            "eccentricity": 0.0,
            "follower_rod_length": 40.0,
        }
    }

    tab_items = TabCamVisualizer(scene).create_visuals(layer_data, transform_function=_identity)
    assert isinstance(tab_items[3], QGraphicsLineItem)
    tab_rod = tab_items[3].line()
    assert (tab_rod.p1().x(), tab_rod.p1().y()) == pytest.approx((0.0, 25.0))
    assert (tab_rod.p2().x(), tab_rod.p2().y()) == pytest.approx((0.0, -15.0))

    registered_items = RegisteredCamVisualizer(
        VisualizationConfig(transform_function=_identity)
    ).create_visuals(layer_data)
    assert isinstance(registered_items[2], QGraphicsLineItem)
    registered_rod = registered_items[2].line()
    assert (registered_rod.p1().x(), registered_rod.p1().y()) == pytest.approx((0.0, 25.0))
    assert (registered_rod.p2().x(), registered_rod.p2().y()) == pytest.approx((0.0, -15.0))


def test_cam_visualizers_sanitize_malformed_foundry_params(
    qapp: QApplication,
) -> None:
    raw_params = {
        "base_radius": float("nan"),
        "eccentricity": -10.0,
        "follower_rod_length": "bad",
        "rise_deg": float("inf"),
        "return_deg": "bad",
        "align_max_deg": float("-inf"),
        "center_x": float("inf"),
        "center_y": float("nan"),
    }

    scene = QGraphicsScene()
    factory_data = {
        "type": "cam",
        "params": dict(raw_params),
        "cam_scale_factor": float("nan"),
        "rod_length_multiplier": 0.0,
    }
    factory_items = MechanismVisualsFactory(scene).create_cam_visuals(
        factory_data,
        transform_function=_identity,
    )
    assert len(factory_items) >= 6
    assert bool(np.isfinite(factory_data["cam_points_local"]).all())
    _assert_items_have_finite_bounds(factory_items)

    tab_data = {
        "params": dict(raw_params),
        "cam_scale_factor": float("nan"),
        "rod_length_multiplier": 0.0,
    }
    tab_items = TabCamVisualizer(scene).create_visuals(tab_data, transform_function=_identity)
    assert len(tab_items) >= 4
    assert bool(np.isfinite(tab_data["cam_points_local"]).all())
    _assert_items_have_finite_bounds(tab_items)

    registered_data = {
        "params": {
            "base_radius": 20.0,
            "eccentricity": 60.0,
            "follower_rod_length": "bad",
            "cam_lobes": "bad",
            "profile_harmonic": 0.8,
            "center_x": float("inf"),
            "center_y": float("nan"),
        },
        "cam_scale_factor": float("nan"),
        "rod_length_multiplier": 0.0,
    }
    registered_items = RegisteredCamVisualizer(
        VisualizationConfig(transform_function=_identity)
    ).create_visuals(registered_data)
    assert len(registered_items) >= 6
    _assert_items_have_finite_bounds(registered_items)
