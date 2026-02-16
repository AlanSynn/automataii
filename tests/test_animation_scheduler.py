"""
Tests for Animation Scheduler and Viewport Controller.
"""
from unittest.mock import MagicMock

import pytest

from automataii.presentation.qt.animation import (
    AnimationPriority,
    CentralAnimationScheduler,
    ViewportController,
)

# Module-level QApplication to persist across tests
_app = None


def get_qapp():
    """Get or create QApplication singleton."""
    global _app
    if _app is None:
        try:
            import sys

            from PyQt6.QtWidgets import QApplication
            _app = QApplication.instance() or QApplication(sys.argv)
        except ImportError:
            pytest.skip("PyQt6 not available")
    return _app


class TestCentralAnimationScheduler:
    """Tests for CentralAnimationScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create scheduler for testing."""
        app = get_qapp()
        # Parent to app to prevent premature deletion
        scheduler = CentralAnimationScheduler()
        yield scheduler
        # Cleanup
        if scheduler.is_running:
            scheduler.stop()

    def test_initialization(self, scheduler):
        """Test scheduler initializes correctly."""
        assert not scheduler.is_running
        assert not scheduler.is_paused
        assert scheduler.frame_count == 0
        assert scheduler.total_time == 0.0
        assert scheduler.target_fps == 30

    def test_subscribe(self, scheduler):
        """Test subscription management."""
        callback = MagicMock()

        sub_id = scheduler.subscribe(
            callback=callback,
            priority=AnimationPriority.HIGH,
            owner_id="test_subscriber",
        )

        assert sub_id == "test_subscriber"
        assert len(scheduler.list_subscriptions()) == 1

    def test_unsubscribe(self, scheduler):
        """Test unsubscription."""
        callback = MagicMock()
        scheduler.subscribe(
            callback=callback,
            priority=AnimationPriority.NORMAL,
            owner_id="test",
        )

        assert scheduler.unsubscribe("test")
        assert len(scheduler.list_subscriptions()) == 0

    def test_enable_disable(self, scheduler):
        """Test enabling/disabling subscriptions."""
        callback = MagicMock()
        scheduler.subscribe(
            callback=callback,
            priority=AnimationPriority.NORMAL,
            owner_id="test",
        )

        scheduler.enable_subscription("test", False)
        subs = scheduler.list_subscriptions()
        assert subs[0]["enabled"] is False

        scheduler.enable_subscription("test", True)
        subs = scheduler.list_subscriptions()
        assert subs[0]["enabled"] is True

    def test_start_stop(self, scheduler):
        """Test start/stop lifecycle."""
        scheduler.start()
        assert scheduler.is_running
        assert not scheduler.is_paused

        scheduler.stop()
        assert not scheduler.is_running

    def test_pause_resume(self, scheduler):
        """Test pause/resume."""
        scheduler.start()

        scheduler.pause()
        assert scheduler.is_running
        assert scheduler.is_paused

        scheduler.resume()
        assert scheduler.is_running
        assert not scheduler.is_paused

        scheduler.stop()

    def test_priority_ordering(self, scheduler):
        """Test callbacks are ordered by priority."""
        call_order = []

        def critical_callback(dt):
            call_order.append("critical")

        def normal_callback(dt):
            call_order.append("normal")

        def low_callback(dt):
            call_order.append("low")

        # Subscribe in reverse order
        scheduler.subscribe(low_callback, AnimationPriority.LOW, "low")
        scheduler.subscribe(critical_callback, AnimationPriority.CRITICAL, "critical")
        scheduler.subscribe(normal_callback, AnimationPriority.NORMAL, "normal")

        # Simulate frame
        scheduler._on_frame()

        # Should be ordered by priority
        assert call_order == ["critical", "normal", "low"]

    def test_frame_skip(self, scheduler):
        """Test frame skip functionality."""
        call_count = 0

        def callback(dt):
            nonlocal call_count
            call_count += 1

        scheduler.subscribe(
            callback=callback,
            priority=AnimationPriority.NORMAL,
            owner_id="test",
            frame_skip=3,  # Call every 3 frames
        )

        # Simulate 6 frames
        for _ in range(6):
            scheduler._on_frame()

        # Should be called twice (frames 3 and 6)
        assert call_count == 2

    def test_stats(self, scheduler):
        """Test statistics retrieval."""
        stats = scheduler.get_stats()

        assert "running" in stats
        assert "paused" in stats
        assert "frame_count" in stats
        assert "subscriptions" in stats


class TestViewportController:
    """Tests for ViewportController."""

    @pytest.fixture
    def mock_view(self):
        """Create mock QGraphicsView."""
        view = MagicMock()
        view.transform.return_value.m11.return_value = 1.0
        view.horizontalScrollBar.return_value.value.return_value = 0
        view.verticalScrollBar.return_value.value.return_value = 0
        return view

    @pytest.fixture
    def controller(self, mock_view):
        """Create controller with mock view."""
        app = get_qapp()
        controller = ViewportController(mock_view)
        yield controller

    def test_initialization(self, controller):
        """Test controller initializes correctly."""
        assert controller.zoom_level == 0
        assert controller.zoom_scale == 1.0

    def test_zoom_in(self, controller, mock_view):
        """Test zoom in operation."""
        controller.zoom_in()
        assert controller.zoom_level == 1
        mock_view.resetTransform.assert_called()
        mock_view.scale.assert_called()

    def test_zoom_out(self, controller, mock_view):
        """Test zoom out operation."""
        controller.zoom_out()
        assert controller.zoom_level == -1
        mock_view.resetTransform.assert_called()

    def test_zoom_limits(self, controller):
        """Test zoom level limits."""
        # Zoom in many times
        for _ in range(100):
            controller.zoom_in()

        assert controller.zoom_level <= controller.config.max_zoom_level

        # Zoom out many times
        for _ in range(200):
            controller.zoom_out()

        assert controller.zoom_level >= controller.config.min_zoom_level

    def test_zoom_to_level(self, controller):
        """Test zoom to specific level."""
        controller.zoom_to_level(10)
        assert controller.zoom_level == 10

        controller.zoom_to_level(-10)
        assert controller.zoom_level == -10

    def test_config(self, controller):
        """Test configuration."""
        config = controller.config
        assert config.zoom_factor_base == 1.05
        assert config.min_zoom_level == -47
        assert config.max_zoom_level == 47

    def test_camera_state(self, controller, mock_view):
        """Test camera state save/restore."""
        controller.zoom_in(5)

        state = controller.get_camera_state()
        assert state["zoom_level"] == 5
        assert "h_scroll" in state
        assert "v_scroll" in state

    def test_reset_view(self, controller, mock_view):
        """Test reset view operation."""
        controller.zoom_in(10)
        controller.reset_view()

        assert controller.zoom_level == 0
        mock_view.resetTransform.assert_called()
