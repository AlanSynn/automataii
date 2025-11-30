"""
Unit tests for PathPreviewOverlay module

Tests:
- Path rendering correctness
- Marker/arrow placement
- Auto-fade timer behavior
- Enable/disable toggle
- Z-level layering
"""

import time
from unittest.mock import MagicMock, Mock

import pytest
from PyQt6.QtWidgets import QApplication, QGraphicsScene

from automataii.application.mechanism_foundry.path_cache import CachedPath
from automataii.presentation.qt.tabs.mechanism_foundry.path_preview import PathPreviewOverlay


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def scene(qapp):
    return QGraphicsScene()


@pytest.fixture
def mock_cache():
    cache = Mock()
    cache.compute_and_cache = Mock()
    return cache


@pytest.fixture
def overlay(qapp, scene, mock_cache):
    return PathPreviewOverlay(scene, mock_cache)


class TestPathPreviewOverlay:
    def test_initial_state(self, overlay):
        assert overlay.enabled is True
        assert len(overlay._items) == 0

    def test_set_enabled_hides_path_when_disabled(self, overlay, mock_cache, scene):
        mock_mechanism = Mock()
        mock_mechanism.mechanism_type = "fourbar"

        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0)), angles=(0.0, 180.0), timestamp=time.time()
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")
        assert len(overlay._items) > 0

        overlay.set_enabled(False)

        assert overlay.enabled is False
        assert len(overlay._items) == 0

    def test_show_path_creates_graphics_items(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        mock_mechanism.mechanism_type = "fourbar"

        points = tuple((float(i), float(i)) for i in range(36))
        cached_path = CachedPath(points=points, angles=tuple(range(36)), timestamp=time.time())
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        assert len(overlay._items) > 0
        assert mock_cache.compute_and_cache.called

    def test_show_path_clears_previous_items(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        mock_mechanism.mechanism_type = "fourbar"

        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0)), angles=(0.0, 180.0), timestamp=time.time()
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")
        first_count = sum(len(items) for items in overlay._items.values())

        overlay.show_path(mock_mechanism, {"a": 2.0}, "output")
        second_count = sum(len(items) for items in overlay._items.values())

        assert second_count > first_count

    def test_hide_path_removes_all_items(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        mock_mechanism.mechanism_type = "fourbar"

        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0)), angles=(0.0, 180.0), timestamp=time.time()
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")
        assert len(overlay._items) > 0

        overlay.hide_path()

        assert len(overlay._items) == 0

    def test_show_path_does_nothing_when_disabled(self, overlay, mock_cache):
        overlay.set_enabled(False)

        mock_mechanism = Mock()
        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        assert not mock_cache.compute_and_cache.called

    def test_fade_timer_starts_on_show(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0)), angles=(0.0, 180.0), timestamp=time.time()
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler", auto_fade=True)

        assert overlay._fade_timer.isActive()

    def test_fade_timer_stops_on_hide(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0)), angles=(0.0, 180.0), timestamp=time.time()
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler", auto_fade=True)
        overlay.hide_path()

        assert not overlay._fade_timer.isActive()

    def test_toggle_visibility(self, overlay):
        assert overlay.enabled is True

        overlay.toggle_visibility()
        assert overlay.enabled is False

        overlay.toggle_visibility()
        assert overlay.enabled is True

    def test_path_line_z_level(self, overlay, mock_cache, scene, qapp):
        mock_mechanism = Mock()
        cached_path = CachedPath(
            points=((0.0, 0.0), (10.0, 10.0), (20.0, 20.0)),
            angles=(0.0, 180.0, 360.0),
            timestamp=time.time(),
        )
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        path_items = [item for item in scene.items() if item.data(0) == "path_preview"]
        assert len(path_items) > 0

        path_lines = [item for item in path_items if item.zValue() == 100]
        assert len(path_lines) > 0

    def test_marker_z_level(self, overlay, mock_cache, scene, qapp):
        mock_mechanism = Mock()
        points = tuple((float(i), float(i)) for i in range(36))
        cached_path = CachedPath(points=points, angles=tuple(range(36)), timestamp=time.time())
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        markers = [item for item in scene.items() if item.zValue() == 101]
        assert len(markers) > 0

    def test_arrow_z_level(self, overlay, mock_cache, scene, qapp):
        mock_mechanism = Mock()
        points = tuple((float(i), float(i)) for i in range(36))
        cached_path = CachedPath(points=points, angles=tuple(range(36)), timestamp=time.time())
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        arrows = [item for item in scene.items() if item.zValue() == 102]
        assert len(arrows) > 0

    def test_handles_empty_path(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        cached_path = CachedPath(points=(), angles=(), timestamp=time.time())
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        assert len(overlay._items) == 0

    def test_handles_single_point_path(self, overlay, mock_cache, qapp):
        mock_mechanism = Mock()
        cached_path = CachedPath(points=((0.0, 0.0),), angles=(0.0,), timestamp=time.time())
        mock_cache.compute_and_cache.return_value = cached_path

        overlay.show_path(mock_mechanism, {"a": 1.0}, "coupler")

        assert len(overlay._items) == 0
