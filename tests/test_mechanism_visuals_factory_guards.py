"""Regression tests for mechanism initial-render guard paths."""
from __future__ import annotations

import sys

import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QGraphicsEllipseItem, QGraphicsScene

from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory


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
