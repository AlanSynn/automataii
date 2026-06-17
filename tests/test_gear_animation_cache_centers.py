"""Regression tests for cached gear animation center placement."""

from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsEllipseItem, QGraphicsLineItem

from automataii.presentation.qt.tabs.mechanism_design.components.mechanism_visual_animator import (
    MechanismVisualAnimator,
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


def test_cached_gear_update_preserves_key_point_centers(qapp: QApplication) -> None:
    layer_data = {
        "type": "gear",
        "params": {"r1": 10.0, "r2": 20.0},
        "key_points": {
            "gear1_center": [100.0, 50.0],
            "gear2_center": [130.0, 50.0],
        },
    }
    visual_items = [
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
    ]
    animator = MechanismVisualAnimator(lambda _layer_data: _identity)

    animator.build_cache("gear-layer", layer_data)
    animator._update_gear_visuals(0.0, layer_data, visual_items, "gear-layer")

    assert _rect_center(visual_items[0]) == pytest.approx((100.0, 50.0))
    assert _rect_center(visual_items[1]) == pytest.approx((130.0, 50.0))


def test_cached_gear_update_uses_simulation_centers_when_key_points_absent(
    qapp: QApplication,
) -> None:
    layer_data = {
        "type": "gear",
        "params": {"r1": 10.0, "r2": 20.0},
        "full_simulation_data": {
            "gear_data": {
                "gear1_centers": [[40.0, 10.0]],
                "gear2_centers": [[70.0, 10.0]],
                "gear1_angles": [0.0],
                "gear2_angles": [0.0],
            },
        },
    }
    visual_items = [
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsLineItem(),
        QGraphicsLineItem(),
    ]
    animator = MechanismVisualAnimator(lambda _layer_data: _identity)

    animator.build_cache("gear-layer", layer_data)
    animator._update_gear_visuals(0.0, layer_data, visual_items, "gear-layer")

    assert _rect_center(visual_items[0]) == pytest.approx((40.0, 10.0))
    assert _rect_center(visual_items[1]) == pytest.approx((70.0, 10.0))


def test_cached_planetary_update_preserves_key_point_phase(qapp: QApplication) -> None:
    layer_data = {
        "type": "planetary_gear",
        "params": {"r_sun": 20.0, "r_planet": 30.0, "arm_length": 15.0},
        "key_points": {
            "sun_center": [100.0, 100.0],
            "planet_center": [100.0, 150.0],
            "tracking_point": [100.0, 165.0],
        },
    }
    visual_items = [
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
        QGraphicsLineItem(),
        QGraphicsEllipseItem(),
        QGraphicsEllipseItem(),
    ]
    animator = MechanismVisualAnimator(lambda _layer_data: _identity)

    animator.build_cache("planetary-layer", layer_data)
    animator._update_planetary_gear_visuals(0.0, layer_data, visual_items, "planetary-layer")

    assert _rect_center(visual_items[1]) == pytest.approx((100.0, 150.0))
    assert _rect_center(visual_items[3]) == pytest.approx((100.0, 165.0))
