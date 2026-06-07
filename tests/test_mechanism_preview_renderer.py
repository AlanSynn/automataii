from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QGraphicsEllipseItem, QGraphicsScene

from automataii.presentation.qt.dialogs.components.mechanism_preview_renderer import (
    MechanismPreviewRenderer,
)


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_cam_preview_renderer_scales_base_radius_with_transform() -> None:
    _ = _get_app()
    scene = QGraphicsScene()
    renderer = MechanismPreviewRenderer()
    renderer.configure(scene)

    renderer.render_cam_follower(
        center=(10.0, 10.0),
        base_radius=5.0,
        follower_pos=(10.0, 0.0),
        cam_profile=[(15.0, 10.0), (10.0, 15.0), (5.0, 10.0), (10.0, 5.0)],
        transform=lambda x, y: (x * 2.0, y * 2.0),
    )

    ellipse_widths = sorted(
        item.rect().width() for item in scene.items() if isinstance(item, QGraphicsEllipseItem)
    )

    assert 20.0 in ellipse_widths
