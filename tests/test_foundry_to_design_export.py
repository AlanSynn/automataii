"""
Test Mechanism Foundry to Design tab export workflow.

Verifies that mechanisms can be exported from Foundry and imported
into the Design tab with correct parameter mapping.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class TestMechanismInstantiationService:
    """Test MechanismInstantiationService Foundry export functionality."""

    def test_create_layer_data_from_foundry_four_bar(self):
        """Test creating layer data from Foundry four-bar export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry four_bar parameters
        foundry_params = {
            "ground_link": 150.0,
            "input_link": 40.0,
            "coupler_link": 120.0,
            "output_link": 130.0,
            "input_angle": 30.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="right_arm",
            scene_position=(400.0, 300.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "4_bar_linkage"
        assert layer_data["part_name"] == "right_arm"
        assert layer_data["source"] == "foundry"

        # Verify parameter mapping
        params = layer_data["params"]
        assert params["l1"] == 150.0  # ground_link -> l1
        assert params["l2"] == 40.0   # input_link -> l2
        assert params["l3"] == 120.0  # coupler_link -> l3
        assert params["l4"] == 130.0  # output_link -> l4

    def test_create_layer_data_from_foundry_cam(self):
        """Test creating layer data from Foundry cam_follower export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry cam_follower parameters
        foundry_params = {
            "cam_radius": 60.0,
            "cam_offset": 20.0,
            "follower_length": 100.0,
            "cam_lobes": 2,
            "profile_harmonic": 0.4,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="left_leg",
            scene_position=(500.0, 400.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "cam"
        assert layer_data["part_name"] == "left_leg"
        assert layer_data["source"] == "foundry"

        # Verify CAM-specific configuration
        assert "cam_position" in layer_data
        assert layer_data["cam_scale_factor"] == 1.0
        assert layer_data["rod_length_multiplier"] == 1.0

        # Verify parameter mapping
        params = layer_data["params"]
        assert params["base_radius"] == 60.0    # cam_radius -> base_radius
        assert params["eccentricity"] == 20.0   # cam_offset -> eccentricity
        assert params["follower_rod_length"] == 100.0  # follower_length -> follower_rod_length
        assert params["cam_lobes"] == 2
        assert params["profile_harmonic"] == 0.4

    def test_create_layer_data_from_foundry_gear(self):
        """Test creating layer data from Foundry gear_train export."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        # Foundry gear_train parameters
        foundry_params = {
            "gear1_teeth": 12,
            "gear2_teeth": 18,
            "input_torque": 200.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="gear_train",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name=None,
        )

        assert layer_data is not None
        assert layer_data["type"] == "gear"
        assert layer_data["source"] == "foundry"

        # Verify gear key_points are created
        assert "gear1_center" in layer_data["key_points"]
        assert "gear2_center" in layer_data["key_points"]

    def test_create_layer_data_from_foundry_slider_crank(self):
        """Slider-crank exports should map to a valid internal 4-bar payload."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        foundry_params = {
            "crank_length": 80.0,
            "rod_length": 140.0,
            "gas_pressure": 500.0,
            "input_angle": 35.0,
        }

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="slider_crank",
            parameters=foundry_params,
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(420.0, 310.0),
        )

        assert layer_data is not None
        assert layer_data["type"] == "4_bar_linkage"
        assert layer_data["source"] == "foundry"
        params = layer_data["params"]
        assert params["l2"] == 80.0
        assert params["l3"] == 140.0
        assert params["l4"] == 140.0
        assert params["l1"] > 0.0
        assert params["crank_angle"] == 35.0

    def test_create_layer_data_from_foundry_normalizes_blank_part_name(self):
        """Blank/whitespace part names should not be preserved in layer data."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters={"cam_radius": 40.0},
            pivot_point=(0.0, 0.0),
            part_name="   ",
        )

        assert layer_data["part_name"] is None

    def test_mechanism_id_uniqueness(self):
        """Test that each created layer has unique ID."""
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        ids = set()
        for _ in range(10):
            layer_data = service.create_layer_data_from_foundry(
                mechanism_type="four_bar",
                parameters={"ground_link": 100.0},
                pivot_point=(0.0, 0.0),
            )
            ids.add(layer_data["id"])

        assert len(ids) == 10  # All IDs should be unique


class TestFoundryViewExportSignal:
    """Test MechanismFoundryView export signal emission."""

    def test_export_signal_exists(self):
        """Test that export_to_design_requested signal exists."""
        from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import (
            MechanismFoundryView,
        )

        # Check signal attribute exists on class
        assert hasattr(MechanismFoundryView, "export_to_design_requested")


class TestMechanismDesignTabImport:
    """Test MechanismDesignTab import functionality."""

    def test_import_method_exists(self):
        """Test that import_mechanism_from_foundry method exists."""
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        assert hasattr(MechanismDesignTab, "import_mechanism_from_foundry")


class TestMechanismDesignPresenterPayloadCompat:
    """Ensure presenter accepts both legacy and normalized mechanism payload keys."""

    def test_handle_mechanism_visuals_accepts_id_type_payload(self):
        from automataii.presentation.qt.tabs.mechanism_design.presenter import (
            MechanismDesignPresenter,
        )

        presenter = MechanismDesignPresenter.__new__(MechanismDesignPresenter)
        presenter._tab = SimpleNamespace(_clear_animation_cache=MagicMock())
        presenter._reset_skeleton_to_initial = MagicMock()
        presenter._visual_item_manager = SimpleNamespace(
            safe_remove_visual_items=MagicMock()
        )
        presenter._transform_service = SimpleNamespace(
            get_scene_transform=MagicMock(return_value=MagicMock(name="transform"))
        )
        presenter._create_mechanism_visuals = MagicMock(return_value=["item"])
        presenter._request_scene_update = MagicMock()
        presenter.mechanism_layers = {
            "mech_1": {
                "id": "mech_1",
                "type": "4_bar_linkage",
                "params": {"l1": 120.0, "l2": 40.0, "l3": 90.0, "l4": 95.0},
                "visual_items": [],
            }
        }

        MechanismDesignPresenter.handle_mechanism_visuals(
            presenter,
            {"id": "mech_1", "type": "4_bar_linkage"},
        )

        presenter._create_mechanism_visuals.assert_called_once()
        call_args = presenter._create_mechanism_visuals.call_args[0]
        assert call_args[0] == "4_bar_linkage"
        assert call_args[1]["mechanism_id"] == "mech_1"
        assert call_args[1]["mechanism_type"] == "4_bar_linkage"


class TestMechanismDesignTabUiState:
    """UI state must respect locally imported mechanisms from Foundry."""

    def test_update_all_ui_states_uses_local_layers_even_with_presenter_vm(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._presenter_view_model = SimpleNamespace(
            parts=[SimpleNamespace(name="torso", enabled=True, has_layers=False)]
        )
        tab.mechanism_layers = {"foundry_1": {"id": "foundry_1", "part_name": "torso"}}
        tab.path_data = {}
        tab.part_enabled_state = {"torso": True}
        tab.parametric_mode_enabled = False
        tab.parts_data = {"torso": object()}
        tab._animation_controller = SimpleNamespace(is_animation_running=lambda: False)
        tab._connect_to_ik_manager = lambda: None

        recorded = {}
        tab.ui_state_manager = SimpleNamespace(
            update_button_states=lambda state: recorded.setdefault("state", state)
        )

        MechanismDesignTab._update_all_ui_states(tab)

        assert tab._current_ui_state.has_mechanisms is True
        assert recorded["state"].has_mechanisms is True


class TestAnchorMovementAliasSync:
    """Ensure 4-bar recomputation keeps parameter aliases consistent."""

    def test_recalculate_4bar_params_sets_lowercase_aliases(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.anchor_movement_handler import (
            AnchorMovementHandler,
        )

        handler = AnchorMovementHandler()
        params: dict[str, float] = {}
        key_points = {
            "ground_pivot_1": [0.0, 0.0],
            "ground_pivot_2": [100.0, 0.0],
            "crank_end": [40.0, 0.0],
            "rocker_end": [80.0, 30.0],
        }

        handler._recalculate_4bar_params(key_points, params)

        assert params["l1"] == params["L1"]
        assert params["l2"] == params["L2"]
        assert params["l3"] == params["L3"]
        assert params["l4"] == params["L4"]


class TestMechanismDesignTabFoundryUpdate:
    """Test Foundry -> Design update path for linkage synchronization."""

    def test_update_from_foundry_syncs_linkage_aliases_and_refreshes(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "params": {"l1": 100.0, "l2": 40.0, "l3": 90.0, "l4": 80.0, "L2": 40.0},
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={"l2": 55.0, "l3": 95.0, "l4": 85.0}
                )
            ),
            _regenerate_foundry_layer_simulation=MagicMock(),
            _visual_animator=SimpleNamespace(build_cache=MagicMock()),
            _render_mechanism_layer=MagicMock(),
            mechanism_scene=SimpleNamespace(update=MagicMock()),
        )

        MechanismDesignTab.update_from_foundry(
            fake_tab,
            mechanism_id="mech_1",
            mechanism_type="four_bar",
            parameters={"input_link": 55.0, "input_angle": 33.0},
        )

        updated = fake_tab.mechanism_layers["mech_1"]["params"]
        assert updated["l2"] == 55.0
        assert updated["L2"] == 55.0
        assert updated["crank_angle"] == 33.0
        fake_tab._regenerate_foundry_layer_simulation.assert_called_once_with("mech_1", layer_data)
        fake_tab._visual_animator.build_cache.assert_called_once_with("mech_1", layer_data)
        fake_tab._render_mechanism_layer.assert_called_once_with("mech_1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
