"""Regression tests for 4-bar coupler parameter alias handling."""

from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
)

from automataii.presentation.qt.mechanisms.visualization.visualizers.four_bar import (
    FourBarVisualizer as PolymorphicFourBarVisualizer,
)
from automataii.presentation.qt.tabs.mechanism_design.components.animation_cache import (
    LinkageCache,
)
from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_visual_animator import (
    MechanismVisualAnimator,
)
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
from automataii.presentation.qt.tabs.visualizers.linkage_visualizer import FourBarVisualizer


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _identity(point: object) -> QPointF:
    coords = np.asarray(point, dtype=float)
    return QPointF(float(coords[0]), float(coords[1]))


def _joint_position_data() -> dict[str, object]:
    return {
        "p1_positions": [[0.0, 0.0]],
        "p2_positions": [[10.0, 0.0]],
        "p3_positions": [[2.0, 0.0]],
        "p4_positions": [[7.0, 0.0]],
    }


def _layer_data_with_alias_conflict() -> dict[str, object]:
    return {
        "type": "4_bar_linkage",
        "params": {
            "l1": 10.0,
            "l2": 2.0,
            "l3": 5.0,
            "l4": 3.0,
            "coupler_point_x": 0.0,
            "coupler_point_y": 5.0,
            "p_x": 99.0,
            "p_y": 99.0,
        },
        "full_simulation_data": {"joint_positions": _joint_position_data()},
    }


def _polygon_vertex(item: QGraphicsPolygonItem, index: int) -> tuple[float, float]:
    polygon = item.polygon()
    try:
        point = polygon[index]
    except TypeError:
        point = polygon.at(index)
    return float(point.x()), float(point.y())


def _assert_coupler_triangle_uses_explicit_zero(item: QGraphicsPolygonItem) -> None:
    vertices = [_polygon_vertex(item, index) for index in range(item.polygon().count())]
    assert any(
        x_coord == pytest.approx(2.0) and y_coord == pytest.approx(5.0)
        for x_coord, y_coord in vertices
    ), vertices


def test_visuals_factory_respects_explicit_zero_coupler_offset_over_alias(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()

    items = MechanismVisualsFactory(scene).create_4bar_linkage_visuals(
        _layer_data_with_alias_conflict(),
        transform_function=_identity,
    )

    assert isinstance(items[2], QGraphicsPolygonItem)
    _assert_coupler_triangle_uses_explicit_zero(items[2])


def test_strategy_visualizer_respects_explicit_zero_coupler_offset_over_alias(
    qapp: QApplication,
) -> None:
    scene = QGraphicsScene()

    items = FourBarVisualizer(scene).create_visuals(
        _layer_data_with_alias_conflict(),
        transform_function=_identity,
    )

    assert isinstance(items[2], QGraphicsPolygonItem)
    _assert_coupler_triangle_uses_explicit_zero(items[2])


def test_visual_animator_fallback_respects_explicit_zero_coupler_offset_over_alias(
    qapp: QApplication,
) -> None:
    visual_items = [
        QGraphicsLineItem(),
        QGraphicsLineItem(),
        QGraphicsPolygonItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
    ]
    animator = MechanismVisualAnimator(lambda _layer_data: _identity)

    animator._update_4bar_visuals(
        time=0.0,
        layer_data=_layer_data_with_alias_conflict(),
        visual_items=visual_items,
        mechanism_id="",
    )

    assert isinstance(visual_items[2], QGraphicsPolygonItem)
    _assert_coupler_triangle_uses_explicit_zero(visual_items[2])


def test_animation_cache_supports_legacy_coupler_aliases() -> None:
    cache = LinkageCache.from_simulation_data(
        _joint_position_data(),
        params={"p_x": 7.0, "p_y": -3.0},
    )

    assert np.allclose(cache.coupler_point_offset, [7.0, -3.0])


def test_animation_cache_respects_explicit_zero_coupler_offset_over_alias() -> None:
    cache = LinkageCache.from_simulation_data(
        _joint_position_data(),
        params={
            "coupler_point_x": 0.0,
            "coupler_point_y": 0.0,
            "p_x": 7.0,
            "p_y": -3.0,
        },
    )

    assert np.allclose(cache.coupler_point_offset, [0.0, 0.0])


def test_polymorphic_visualizer_respects_explicit_zero_coupler_offset_over_alias() -> None:
    visualizer = PolymorphicFourBarVisualizer()

    point = visualizer._calculate_coupler_point(
        np.array([2.0, 0.0]),
        np.array([7.0, 0.0]),
        {
            "coupler_point_x": 0.0,
            "coupler_point_y": 5.0,
            "p_x": 99.0,
            "p_y": 99.0,
        },
    )

    assert np.allclose(point, [2.0, 5.0])
