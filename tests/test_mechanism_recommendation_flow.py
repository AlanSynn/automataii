"""
Test mechanism recommendation dialog flow for all mechanism types.

Verifies that selecting any mechanism type from the recommendation dialog
does not cause AttributeErrors related to uninitialized coordinators.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
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
            if hasattr(tab, "_animation_frame_coordinator") and tab._animation_frame_coordinator:
                tab._animation_frame_coordinator.clear_animation_cache(tab)

        # Should not raise
        clear_animation_cache()

    def test_animation_time_property_without_coordinator(self):
        """Test animation_time property returns default when coordinator is None."""
        tab = MagicMock(spec=[])

        def get_animation_time():
            if hasattr(tab, "_animation_frame_coordinator") and tab._animation_frame_coordinator:
                return tab._animation_frame_coordinator.animation_time
            return 0.0

        result = get_animation_time()
        assert result == 0.0

    def test_update_animation_without_coordinator(self):
        """Test _update_animation works when coordinator is None."""
        tab = MagicMock(spec=[])

        def update_animation():
            if (
                not hasattr(tab, "_animation_frame_coordinator")
                or not tab._animation_frame_coordinator
            ):
                return
            tab._animation_frame_coordinator.update_frame()

        # Should not raise
        update_animation()

    def test_apply_performance_preset_without_coordinator(self):
        """Test apply_performance_preset works when coordinator is None."""
        tab = MagicMock(spec=[])

        def apply_performance_preset(preset: str):
            if (
                not hasattr(tab, "_animation_frame_coordinator")
                or not tab._animation_frame_coordinator
            ):
                return
            return tab._animation_frame_coordinator.apply_performance_preset(preset)

        # Should not raise
        result = apply_performance_preset("balanced")
        assert result is None


class TestMechanismTypeHandling:
    """Test handling of different mechanism types in recommendation flow."""

    def test_recommendation_physical_banner_defaults_to_fabrication_ready(self):
        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            _recommendation_physical_mode_summary,
        )
        from automataii.shared.physical_kit import physical_context_from_settings

        assert "Fabrication-ready preset mode ON" in _recommendation_physical_mode_summary(None)
        assert "G1/G3/G5/G7" in _recommendation_physical_mode_summary(None)
        assert "Simulation-only" in _recommendation_physical_mode_summary(
            physical_context_from_settings(False, 2.0)
        )

    @pytest.mark.parametrize(
        "mechanism_type,internal_type",
        [
            ("4-Bar Linkage", "4_bar_linkage"),
            ("4-bar Coupler", "4_bar_linkage"),
            ("Cam & Follower", "cam"),
            ("Cam-Follower", "cam"),
            ("Gears (Simple Pair)", "gear"),
            ("Simple Gear", "gear"),
            ("Planetary Gear", "planetary_gear"),
        ],
    )
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

    @pytest.mark.parametrize("mechanism_type", ["Cam & Follower", "Simple Gear", "Planetary Gear"])
    def test_preview_supported_non_4bar_families_do_not_silently_noop(
        self, mechanism_type: str, caplog
    ):
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

        with caplog.at_level(logging.INFO):
            controller._show_preview({"type": mechanism_type})

        controller._create_4bar_visuals_fn.assert_not_called()
        assert controller._preview_items == []
        assert "Design-scene preview is not available" in caplog.text


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

    @pytest.mark.parametrize(
        "family",
        [
            "Four-Bar Linkage",
            "Cam & Follower",
            "Gears",
        ],
    )
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


class TestRecommendationTemplateSearchContracts:
    """Regression tests for generated-path recommendation/template search."""

    def test_align_and_compare_paths_rejects_non_finite_candidates(self):
        """NaN/inf generated paths must not be scored as best matches."""
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            align_and_compare_paths,
        )

        user_path = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]])
        candidate = np.array([[0.0, 0.0], [float("nan"), 1.0], [2.0, 0.0]])

        distance, user_aligned, candidate_aligned, transform = align_and_compare_paths(
            user_path,
            candidate,
        )

        assert distance == float("inf")
        assert user_aligned is None
        assert candidate_aligned is None
        assert transform is None

    def test_load_generated_paths_skips_non_finite_candidates(self, tmp_path):
        """Malformed template-search rows should not enter recommendation ranking."""
        import json

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        generated_paths = [
            {
                "type": "4-bar Coupler",
                "name": "poisoned",
                "path_coordinates": [[0.0, 0.0], [float("nan"), 1.0], [2.0, 0.0]],
            },
            {
                "type": "4-bar Coupler",
                "name": "finite",
                "path_coordinates": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
            },
        ]
        generated_path = tmp_path / "generated_paths.json"
        generated_path.write_text(json.dumps(generated_paths), encoding="utf-8")

        loaded = MechanismRecommendationDialog._load_generated_paths(
            object(),
            str(generated_path),
        )

        assert [row["name"] for row in loaded] == ["finite"]

    def test_load_generated_paths_skips_malformed_rows_without_aborting_later_rows(self, tmp_path):
        import json

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        generated_paths = [
            None,
            "not-a-row",
            {
                "type": "4-bar Coupler",
                "name": "finite-after-malformed",
                "path_coordinates": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
            },
        ]
        generated_path = tmp_path / "generated_paths.json"
        generated_path.write_text(json.dumps(generated_paths), encoding="utf-8")

        loaded = MechanismRecommendationDialog._load_generated_paths(object(), str(generated_path))

        assert [row["name"] for row in loaded] == ["finite-after-malformed"]

    def test_align_and_compare_paths_rejects_degenerate_zero_length_paths(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            align_and_compare_paths,
        )

        degenerate = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]])
        valid = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 0.0]])

        distance, user_aligned, candidate_aligned, transform = align_and_compare_paths(
            degenerate,
            valid,
        )

        assert distance == float("inf")
        assert user_aligned is None
        assert candidate_aligned is None
        assert transform is None

    def test_cam_template_path_is_packaged_for_template_backed_recommendations(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        template_path = MechanismInstantiationService().get_cam_template_path()

        assert template_path is not None
        assert template_path.endswith("pear_cam_4.3in.svg")

    def test_cam_template_svg_is_not_gitignored_or_untracked(self):
        """Guard against clean-checkout/package loss of the template-backed CAM asset."""
        repo_root = Path(__file__).resolve().parents[1]
        if not (repo_root / ".git").exists():
            pytest.skip("git metadata is required for source asset tracking check")

        rel_path = "resources/blueprints/tom/pear_cam_4.3in.svg"
        resource_path = repo_root / rel_path
        assert resource_path.exists()

        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", rel_path],
            cwd=repo_root,
            check=False,
        )
        assert ignored.returncode != 0, f"{rel_path} must not be ignored"

        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_path],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, f"{rel_path} must be tracked for clean checkout/package"

    def test_best_recommendation_tie_break_is_input_order_independent(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]]

        def row(name: str) -> dict[str, Any]:
            return {
                "type": "4-bar Coupler",
                "name": name,
                "parameters": {},
                "path_coordinates": user_path,
                "path_coordinates_np": np.asarray(user_path, dtype=float),
            }

        def best_name(rows: list[dict[str, Any]]) -> str:
            dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
            dialog.user_motion_path_np = np.asarray(user_path, dtype=float)
            dialog.generated_paths_data = rows
            dialog._get_mechanism_points_orig = MagicMock(return_value=None)
            result = MechanismRecommendationDialog._get_best_recommendations(dialog)
            assert result[0] is not None
            return str(result[0]["name"])

        assert best_name([row("Beta"), row("Alpha")]) == "Alpha"
        assert best_name([row("Alpha"), row("Beta")]) == "Alpha"

    def test_recommendation_scores_reversed_saved_path_against_current_user_drawing(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray(
            [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [3.0, 1.0], [3.0, 2.0]],
            dtype=float,
        )
        stored_reversed_path = user_path[::-1].copy()
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = user_path
        dialog.generated_paths_data = [
            {
                "name": "reverse-saved-fourbar",
                "type": "4-bar Coupler",
                "parameters": {"l1": 10.0},
                "path_coordinates": stored_reversed_path.tolist(),
                "path_coordinates_np": stored_reversed_path,
            }
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        best = result[0]
        assert best is not None
        assert best["name"] == "reverse-saved-fourbar"
        assert best["scores"]["path_direction"] == "reversed"
        assert best["scores"]["time_aware_reversed"] < best["scores"]["time_aware_forward"]
        assert best["scores"]["time_aware"] == best["scores"]["time_aware_reversed"]
        assert best["reverse_direction"] is True
        assert best["parameters"]["reverse_direction"] is True

    def test_recommendation_reversed_match_toggles_existing_reverse_direction(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [1.5, 2.0], [3.0, 2.0]],
            dtype=float,
        )
        stored_reversed_path = user_path[::-1].copy()
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = user_path
        dialog.generated_paths_data = [
            {
                "name": "already-reversed-fourbar",
                "type": "4-bar Coupler",
                "reverse_direction": True,
                "parameters": {},
                "path_coordinates": stored_reversed_path.tolist(),
                "path_coordinates_np": stored_reversed_path,
            }
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        best = result[0]
        assert best is not None
        assert best["scores"]["path_direction"] == "reversed"
        assert best["reverse_direction"] is False
        assert best["parameters"]["reverse_direction"] is False

    def test_recommendation_keeps_forward_direction_on_exact_direction_tie(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        palindromic_path = np.asarray([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]], dtype=float)
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = palindromic_path
        dialog.generated_paths_data = [
            {
                "name": "direction-tie-fourbar",
                "type": "4-bar Coupler",
                "reverse_direction": False,
                "parameters": {},
                "path_coordinates": palindromic_path.tolist(),
                "path_coordinates_np": palindromic_path,
            }
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        best = result[0]
        assert best is not None
        assert best["scores"]["path_direction"] == "forward"
        assert best["scores"]["time_aware_forward"] == best["scores"]["time_aware_reversed"]
        assert best["reverse_direction"] is False

    def test_recommendation_direction_coerces_string_and_numeric_reverse_flags(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray(
            [[0.0, 0.0], [2.0, 1.0], [4.0, 1.0], [5.0, 3.0]],
            dtype=float,
        )
        stored_reversed_path = user_path[::-1].copy()

        def best_reverse_flag(row: dict[str, Any]) -> bool:
            dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
            dialog.user_motion_path_np = user_path
            row = {
                "name": "coerced-fourbar",
                "type": "4-bar Coupler",
                "path_coordinates": stored_reversed_path.tolist(),
                "path_coordinates_np": stored_reversed_path,
                **row,
            }
            dialog.generated_paths_data = [row]
            dialog._get_mechanism_points_orig = MagicMock(return_value=None)
            result = MechanismRecommendationDialog._get_best_recommendations(dialog)
            best = result[0]
            assert best is not None
            assert best["scores"]["path_direction"] == "reversed"
            return best["reverse_direction"]

        assert best_reverse_flag({"reverse_direction": "reverse", "parameters": {}}) is False
        assert best_reverse_flag({"parameters": {"reverse_direction": "true"}}) is False
        assert best_reverse_flag({"reverse_direction": 1, "parameters": {}}) is False

    def test_recommendation_prefers_forward_candidate_over_same_shape_reversed_candidate(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray(
            [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [4.0, 1.0], [5.0, 3.0]],
            dtype=float,
        )

        def row(name: str, path: np.ndarray) -> dict[str, Any]:
            return {
                "name": name,
                "type": "4-bar Coupler",
                "parameters": {},
                "path_coordinates": path.tolist(),
                "path_coordinates_np": path,
            }

        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = user_path
        dialog.generated_paths_data = [
            row("a-same-shape-reversed", user_path[::-1].copy()),
            row("z-same-shape-forward", user_path.copy()),
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        best = result[0]
        assert best is not None
        assert best["name"] == "z-same-shape-forward"
        assert best["scores"]["path_direction"] == "forward"
        assert best["scores"]["time_aware_forward"] <= best["scores"]["time_aware_reversed"]

    def test_recommendation_top_level_reverse_flag_wins_over_parameter_flag(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray([[0.0, 0.0], [2.0, 1.0], [4.0, 0.0]], dtype=float)
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = user_path
        dialog.generated_paths_data = [
            {
                "name": "top-level-wins",
                "type": "4-bar Coupler",
                "reverse_direction": True,
                "parameters": {"reverse_direction": False},
                "path_coordinates": user_path.tolist(),
                "path_coordinates_np": user_path,
            }
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        best = result[0]
        assert best is not None
        assert best["scores"]["path_direction"] == "forward"
        assert best["reverse_direction"] is True
        assert best["parameters"]["reverse_direction"] is True

    def test_best_recommendations_snap_template_params_to_fabrication_presets(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray([[0.0, 0.0], [1.0, 2.0], [2.0, 0.0]], dtype=float)
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = user_path
        dialog.physical_context = None
        dialog.generated_paths_data = [
            {
                "name": "freeform-fourbar",
                "type": "4-bar Coupler",
                "parameters": {"l1": 45.1, "l2": 11.8, "l3": 80.2, "l4": 60.6},
                "path_coordinates": user_path.tolist(),
                "path_coordinates_np": user_path.copy(),
            },
            {
                "name": "freeform-planetary",
                "type": "Planetary Gear",
                "parameters": {"r_sun": 18.0, "r_planet": 36.0, "arm_length": 13.0},
                "path_coordinates": user_path.tolist(),
                "path_coordinates_np": user_path.copy(),
            },
        ]
        dialog._get_mechanism_points_orig = MagicMock(return_value=None)

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        fourbar = result[0]
        gears = result[2]
        assert fourbar is not None
        assert fourbar["fabrication_ready"] is True
        assert (fourbar["parameters"]["l1"], fourbar["parameters"]["l2"]) == (40.0, 40.0)
        assert (fourbar["parameters"]["l3"], fourbar["parameters"]["l4"]) == (80.0, 80.0)
        assert gears is not None
        assert gears["parameters"]["sun_teeth"] == 8
        assert gears["parameters"]["planet_teeth"] == 24
        assert gears["parameters"]["arm_length"] == 40.0

    def test_equal_path_reverse_direction_tie_is_input_order_independent(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        user_path = np.asarray([[0.0, 0.0], [1.0, 2.0], [2.0, 0.0]], dtype=float)

        def row(reverse_direction: bool) -> dict[str, Any]:
            return {
                "name": "same-candidate",
                "type": "4-bar Coupler",
                "reverse_direction": reverse_direction,
                "parameters": {},
                "path_coordinates": user_path.tolist(),
                "path_coordinates_np": user_path.copy(),
            }

        def best_reverse(rows: list[dict[str, Any]]) -> bool:
            dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
            dialog.user_motion_path_np = user_path
            dialog.generated_paths_data = rows
            dialog._get_mechanism_points_orig = MagicMock(return_value=None)
            result = MechanismRecommendationDialog._get_best_recommendations(dialog)
            best = result[0]
            assert best is not None
            return best["reverse_direction"]

        assert best_reverse([row(True), row(False)]) is False
        assert best_reverse([row(False), row(True)]) is False

    def test_create_layer_data_from_recommendation_preserves_direction_metadata(self):
        from PyQt6.QtGui import QPainterPath

        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        user_path = QPainterPath()
        user_path.moveTo(0.0, 0.0)
        user_path.lineTo(10.0, 10.0)

        layer_data, graphics_data = service.create_layer_data_from_recommendation(
            {
                "type": "Four-Bar Linkage",
                "original_json_type": "4-bar Coupler",
                "name": "reverse-selected",
                "reverse_direction": True,
                "parameters": {"l1": 10.0},
                "user_motion_path_local": user_path,
            },
            target_path=None,
        )

        assert layer_data["reverse_direction"] is True
        assert layer_data["params"]["reverse_direction"] is True
        assert graphics_data["reverse_direction"] is True
        assert graphics_data["params"]["reverse_direction"] is True

    def test_create_layer_data_from_recommendation_coerces_parameter_direction_metadata(self):
        from PyQt6.QtGui import QPainterPath

        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        user_path = QPainterPath()
        user_path.moveTo(0.0, 0.0)
        user_path.lineTo(10.0, 10.0)

        layer_data, graphics_data = (
            MechanismInstantiationService().create_layer_data_from_recommendation(
                {
                    "type": "Four-Bar Linkage",
                    "original_json_type": "4-bar Coupler",
                    "name": "parameter-reverse-selected",
                    "parameters": {"reverse_direction": "reversed"},
                    "user_motion_path_local": user_path,
                },
                target_path=None,
            )
        )

        assert layer_data["reverse_direction"] is True
        assert layer_data["params"]["reverse_direction"] is True
        assert graphics_data["reverse_direction"] is True
        assert graphics_data["params"]["reverse_direction"] is True

    def test_create_layer_data_prefers_dialog_user_path_over_stale_target_path(self):
        from PyQt6.QtGui import QPainterPath

        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        dialog_path = QPainterPath()
        dialog_path.moveTo(0.0, 0.0)
        dialog_path.lineTo(10.0, 10.0)
        stale_path = QPainterPath()
        stale_path.moveTo(100.0, 100.0)
        stale_path.lineTo(200.0, 200.0)

        layer_data, graphics_data = (
            MechanismInstantiationService().create_layer_data_from_recommendation(
                {
                    "type": "Four-Bar Linkage",
                    "original_json_type": "4-bar Coupler",
                    "name": "fresh-path-selected",
                    "parameters": {},
                    "user_motion_path_local": dialog_path,
                },
                target_path=stale_path,
            )
        )

        assert layer_data["generated_path"] is dialog_path
        assert graphics_data["generated_path"] is dialog_path

    def test_degenerate_cam_template_svg_falls_back_to_finite_circle(self, tmp_path):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismPreviewWidget,
        )

        template = tmp_path / "degenerate_cam.svg"
        template.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<circle cx="0" cy="0" r="1"/>'
            '<path d="M 1 1 L 1 1 L 1 1 Z"/>'
            "</svg>",
            encoding="utf-8",
        )

        axis, poly = MechanismPreviewWidget._load_cam_profile_svg(object(), str(template))
        assert axis is not None
        assert poly.shape == (0, 2)

        fallback = MechanismPreviewWidget._build_cam_from_template(
            object(),
            poly,
            base_radius=25.0,
            eccentricity=10.0,
            num_samples=16,
        )

        assert fallback.shape == (16, 2)
        assert np.isfinite(fallback).all()
        radii = np.linalg.norm(fallback, axis=1)
        assert np.allclose(radii, 25.0)

    def test_cam_follower_alias_contributes_to_preview_envelope(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        path_points = np.asarray([[0.0, 0.0], [10.0, 5.0], [20.0, 0.0]], dtype=float)
        mechanism_data = {
            "original_json_type": "Cam-Follower",
            "parameters": {"base_radius": 25.0, "eccentricity": 10.0},
            "path_coordinates_np": path_points,
            "key_points": {"cam_center": [3.0, 4.0]},
        }

        envelope = MechanismRecommendationDialog._get_mechanism_points_orig(
            object(),
            mechanism_data,
        )

        assert envelope is not None
        assert envelope.shape[0] > path_points.shape[0]
        assert np.isfinite(envelope).all()

    def test_best_recommendations_tolerates_string_numeric_template_params(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        path_points = np.asarray(
            [[0.0, 0.0], [10.0, 4.0], [20.0, 0.0], [30.0, 4.0]],
            dtype=float,
        )
        dialog = MechanismRecommendationDialog.__new__(MechanismRecommendationDialog)
        dialog.user_motion_path_np = path_points
        dialog.generated_paths_data = [
            {
                "name": "string-cam",
                "type": "Cam-Follower",
                "parameters": {"base_radius": "25.0", "eccentricity": "10.0"},
                "path_coordinates": path_points.tolist(),
                "path_coordinates_np": path_points,
                "key_points": {"cam_center": ["3.0", "4.0"], "rotation_center": ["0", "0"]},
            },
            {
                "name": "string-gear",
                "type": "Simple Gear",
                "parameters": {"r1": "40.0", "r2": "60.0"},
                "path_coordinates": path_points.tolist(),
                "path_coordinates_np": path_points,
                "key_points": {"gear1_center": ["0", "0"], "gear2_center": ["100", "0"]},
            },
        ]

        result = MechanismRecommendationDialog._get_best_recommendations(dialog)

        assert result[1] is not None
        assert result[1]["name"] == "string-cam"
        assert result[2] is not None
        assert result[2]["name"] == "string-gear"

    def test_mechanism_preview_envelope_rejects_malformed_numeric_params_without_crash(self):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )

        path_points = np.asarray([[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]], dtype=float)
        mechanism_data = {
            "original_json_type": "Simple Gear",
            "parameters": {"r1": "not-a-number", "r2": "60.0"},
            "path_coordinates_np": path_points,
            "key_points": ["not", "a", "dict"],
        }

        envelope = MechanismRecommendationDialog._get_mechanism_points_orig(
            object(),
            mechanism_data,
        )

        assert envelope is not None
        assert np.array_equal(envelope, path_points)

    def test_cam_template_svg_parser_accepts_lowercase_relative_repeated_commands(self, tmp_path):
        import numpy as np

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismPreviewWidget,
        )

        template = tmp_path / "lowercase_cam.svg"
        template.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><path d="m 0 0 l 10 0 0 10 -10 0 z"/></svg>',
            encoding="utf-8",
        )

        axis, poly = MechanismPreviewWidget._load_cam_profile_svg(object(), str(template))

        assert axis is not None
        assert poly.shape == (4, 2)
        assert np.allclose(poly, [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])

    def test_draw_mechanism_structure_ignores_malformed_sim_payloads(self, caplog):
        import sys

        import numpy as np
        from PyQt6.QtGui import QTransform
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismPreviewWidget,
        )

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        with caplog.at_level(logging.WARNING):
            MechanismPreviewWidget(
                {
                    "original_json_type": "4-bar Coupler",
                    "parameters": {"p_x": 0.0, "p_y": 0.0},
                    "user_path_aligned_np": np.asarray(
                        [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
                        dtype=float,
                    ),
                    "mech_path_aligned_np": np.asarray(
                        [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
                        dtype=float,
                    ),
                    "full_simulation_data": {
                        "coupler_path": [[0.0, 0.0], [1.0, 1.0], [2.0, 0.0]],
                        "joint_positions": {
                            "p1_positions": [],
                            "p2_positions": [],
                            "p3_positions": [],
                            "p4_positions": [],
                        },
                    },
                }
            )._draw_mechanism_structure(QTransform())

        assert "Skipping malformed 4-bar Coupler recommendation preview structure" in caplog.text


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
            if (
                hasattr(mock_tab, "_animation_frame_coordinator")
                and mock_tab._animation_frame_coordinator
            ):
                mock_tab._animation_frame_coordinator.clear_animation_cache(mock_tab)

        # Should not raise AttributeError
        clear_animation_cache()

    def test_presenter_handle_mechanism_visuals_with_none_coordinator(self):
        """Test that presenter gracefully handles None coordinator."""
        mock_tab = MagicMock()
        mock_tab._animation_frame_coordinator = None

        def clear_animation_cache():
            if (
                hasattr(mock_tab, "_animation_frame_coordinator")
                and mock_tab._animation_frame_coordinator
            ):
                mock_tab._animation_frame_coordinator.clear_animation_cache(mock_tab)

        # Should not raise AttributeError
        clear_animation_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
