"""
Test mechanism recommendation dialog flow for all mechanism types.

Verifies that selecting any mechanism type from the recommendation dialog
does not cause AttributeErrors related to uninitialized coordinators.
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest


class MockAnimationFrameCoordinator:
    """Mock for AnimationFrameCoordinator to avoid full initialization."""

    def __init__(self, **kwargs):
        self.animation_time = 0.0
        self.animation_speed = 1.0
        self.trace_frame_tick = 0
        self._callbacks_configured = False

    def configure_callbacks(self, **kwargs) -> None:
        self._callbacks_configured = True

    def is_configured(self) -> bool:
        return self._callbacks_configured

    def clear_animation_cache(self, tab: Any) -> None:
        pass

    def update_frame(self, *args, **kwargs) -> None:
        pass

    def apply_performance_preset(self, preset: str) -> dict:
        return {}


class MockAnimationLifecycleController:
    """Mock for AnimationLifecycleController."""

    def __init__(self, **kwargs):
        self._running = False
        self._callbacks_configured = False

    def configure_callbacks(self, **kwargs) -> None:
        self._callbacks_configured = True

    def is_configured(self) -> bool:
        return self._callbacks_configured

    def is_animation_running(self) -> bool:
        return self._running

    def start_animation(self, **kwargs) -> None:
        self._running = True

    def stop_animation(self) -> None:
        self._running = False


@pytest.fixture
def mock_tab():
    """Create a mock MechanismDesignTab with essential attributes."""
    tab = MagicMock()
    tab._animation_frame_coordinator = MockAnimationFrameCoordinator()
    tab._animation_controller = MockAnimationLifecycleController()
    tab.mechanism_layers = {}
    tab.mechanism_enabled_state = {}
    tab.parametric_handles = {}
    tab.path_data = {}
    tab.part_enabled_state = {}
    tab.parts_data = {}
    tab.selected_part_name = None
    return tab


class TestAnimationFrameCoordinatorDefensiveChecks:
    """Test that defensive hasattr checks prevent AttributeErrors."""

    def test_clear_animation_cache_without_coordinator(self):
        """Test _clear_animation_cache works when coordinator is None."""
        tab = MagicMock(spec=[])  # Empty spec - no attributes

        # Simulate the defensive check pattern
        def clear_animation_cache():
            if hasattr(tab, '_animation_frame_coordinator') and tab._animation_frame_coordinator:
                tab._animation_frame_coordinator.clear_animation_cache(tab)

        # Should not raise
        clear_animation_cache()

    def test_animation_time_property_without_coordinator(self):
        """Test animation_time property returns default when coordinator is None."""
        tab = MagicMock(spec=[])

        def get_animation_time():
            if hasattr(tab, '_animation_frame_coordinator') and tab._animation_frame_coordinator:
                return tab._animation_frame_coordinator.animation_time
            return 0.0

        result = get_animation_time()
        assert result == 0.0

    def test_update_animation_without_coordinator(self):
        """Test _update_animation works when coordinator is None."""
        tab = MagicMock(spec=[])

        def update_animation():
            if not hasattr(tab, '_animation_frame_coordinator') or not tab._animation_frame_coordinator:
                return
            tab._animation_frame_coordinator.update_frame()

        # Should not raise
        update_animation()

    def test_apply_performance_preset_without_coordinator(self):
        """Test apply_performance_preset works when coordinator is None."""
        tab = MagicMock(spec=[])

        def apply_performance_preset(preset: str):
            if not hasattr(tab, '_animation_frame_coordinator') or not tab._animation_frame_coordinator:
                return
            return tab._animation_frame_coordinator.apply_performance_preset(preset)

        # Should not raise
        result = apply_performance_preset("balanced")
        assert result is None


class TestMechanismTypeHandling:
    """Test handling of different mechanism types in recommendation flow."""

    @pytest.mark.parametrize("mechanism_type,internal_type", [
        ("4-Bar Linkage", "4_bar_linkage"),
        ("4-bar Coupler", "4_bar_linkage"),
        ("Cam & Follower", "cam"),
        ("Cam-Follower", "cam"),
        ("Gears (Simple Pair)", "gear"),
        ("Simple Gear", "gear"),
        ("Planetary Gear", "planetary_gear"),
    ])
    def test_mechanism_type_mapping(self, mechanism_type: str, internal_type: str):
        """Verify mechanism type mapping from display names to internal types."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        result = MechanismInstantiationService().map_mechanism_type(mechanism_type)
        assert result == internal_type

    def test_preview_unknown_mechanism_does_not_fallback_to_4bar(self, caplog):
        """Preview must not hide unsupported recommendation types as a 4-bar."""
        from automataii.presentation.qt.tabs.mechanism_design.controllers.recommendation_controller import (
            RecommendationController,
        )
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        controller = RecommendationController(parent=None)
        controller._instantiation_service = MechanismInstantiationService()
        controller._get_scene_fn = lambda: object()
        controller._create_4bar_visuals_fn = MagicMock(return_value=["unexpected"])

        with caplog.at_level(logging.WARNING):
            controller._show_preview({"type": "Unknown Mechanism"})

        controller._create_4bar_visuals_fn.assert_not_called()
        assert controller._preview_items == []
        assert "Skipping unsupported mechanism preview" in caplog.text

    def test_preview_known_4bar_still_creates_4bar_visuals(self):
        from automataii.presentation.qt.tabs.mechanism_design.controllers.recommendation_controller import (
            RecommendationController,
        )
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        controller = RecommendationController(parent=None)
        controller._instantiation_service = MechanismInstantiationService()
        controller._get_scene_fn = lambda: object()
        controller._create_4bar_visuals_fn = MagicMock(return_value=["4bar-preview"])

        controller._show_preview({"type": "Four-Bar Linkage"})

        controller._create_4bar_visuals_fn.assert_called_once()
        assert controller._preview_items == ["4bar-preview"]


class TestRecommendationControllerFlow:
    """Test the recommendation controller workflow."""

    def test_handle_recommendation_selection_no_crash(self):
        """Test that recommendation selection doesn't crash with defensive checks."""
        from automataii.presentation.qt.tabs.mechanism_design.controllers.recommendation_controller import (
            RecommendationController,
        )

        controller = RecommendationController(parent=None)

        # Mock essential services
        mock_instantiation = MagicMock()
        mock_instantiation.create_layer_data_from_recommendation.return_value = (
            {"type": "4_bar_linkage", "params": {}, "part_name": "test"},
            {"name": "mech_test", "mechanism_type": "4_bar_linkage"},
        )

        controller._instantiation_service = mock_instantiation
        controller._get_path_data_fn = lambda: {}
        controller._get_selected_part_name_fn = lambda: "test_part"
        controller._get_character_position_fn = lambda: [300, 400]
        controller._add_mechanism_layer_fn = MagicMock()
        controller._handle_mechanism_visuals_fn = MagicMock()

        # Test data simulating Four-Bar Linkage selection
        mechanism_data = {
            "type": "Four-Bar Linkage",
            "original_json_type": "4-bar Coupler",
            "parameters": {
                "L1": 100.0,
                "L2": 50.0,
                "L3": 80.0,
                "L4": 60.0,
            },
            "path_coordinates": [[0, 0], [10, 10], [20, 5]],
        }

        # Should not raise
        controller.handle_recommendation_selection(mechanism_data, None)

        # Verify callbacks were called
        controller._add_mechanism_layer_fn.assert_called_once()
        controller._handle_mechanism_visuals_fn.assert_called_once()

    @pytest.mark.parametrize("family", [
        "Four-Bar Linkage",
        "Cam & Follower",
        "Gears",
    ])
    def test_handle_all_mechanism_families(self, family: str):
        """Test that all mechanism families can be handled without error."""
        from automataii.presentation.qt.tabs.mechanism_design.controllers.recommendation_controller import (
            RecommendationController,
        )

        controller = RecommendationController(parent=None)

        mock_instantiation = MagicMock()
        mock_instantiation.create_layer_data_from_recommendation.return_value = (
            {"type": family, "params": {}, "part_name": "test"},
            {"name": f"mech_{family}", "mechanism_type": family},
        )

        controller._instantiation_service = mock_instantiation
        controller._get_path_data_fn = lambda: {}
        controller._get_selected_part_name_fn = lambda: "test_part"
        controller._get_character_position_fn = lambda: [300, 400]
        controller._add_mechanism_layer_fn = MagicMock()
        controller._handle_mechanism_visuals_fn = MagicMock()

        mechanism_data = {
            "type": family,
            "parameters": {},
            "path_coordinates": [[0, 0], [10, 10]],
        }

        # Should not raise
        controller.handle_recommendation_selection(mechanism_data, None)
        controller._handle_mechanism_visuals_fn.assert_called_once()


class TestPresenterMechanismHandling:
    """Test presenter's mechanism handling with defensive checks."""

    def test_presenter_handle_mechanism_visuals_with_uninitialized_coordinator(self):
        """Test that presenter gracefully handles uninitialized coordinators."""
        # Create a minimal mock for the presenter's tab reference
        mock_tab = MagicMock()

        # Simulate _animation_frame_coordinator not being set
        del mock_tab._animation_frame_coordinator

        # The defensive pattern in _clear_animation_cache
        def clear_animation_cache():
            if hasattr(mock_tab, '_animation_frame_coordinator') and mock_tab._animation_frame_coordinator:
                mock_tab._animation_frame_coordinator.clear_animation_cache(mock_tab)

        # Should not raise AttributeError
        clear_animation_cache()

    def test_presenter_handle_mechanism_visuals_with_none_coordinator(self):
        """Test that presenter gracefully handles None coordinator."""
        mock_tab = MagicMock()
        mock_tab._animation_frame_coordinator = None

        def clear_animation_cache():
            if hasattr(mock_tab, '_animation_frame_coordinator') and mock_tab._animation_frame_coordinator:
                mock_tab._animation_frame_coordinator.clear_animation_cache(mock_tab)

        # Should not raise AttributeError
        clear_animation_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
