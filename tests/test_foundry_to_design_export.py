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
        assert params["l1"] == pytest.approx(150.0)  # ground_link -> l1
        assert params["l2"] == pytest.approx(40.0)   # input_link -> l2
        assert params["l3"] == pytest.approx(120.0)  # coupler_link -> l3
        assert params["l4"] == pytest.approx(130.0)  # output_link -> l4

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
            "output_point_mode": "contact_point",
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
        assert params["output_point_mode"] == "contact_point"

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
        assert params["l2"] == pytest.approx(80.0)
        assert params["l3"] == pytest.approx(140.0)
        assert params["l4"] == pytest.approx(140.0)
        assert params["l1"] > 0.0
        assert params["crank_angle"] == 35.0

    def test_create_layer_data_from_foundry_preserves_four_bar_snapshot_geometry(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                    "A": [-40.0, 20.0],
                    "B": [60.0, 45.0],
                }
            },
        )

        key_points = layer_data["key_points"]
        assert key_points["ground_pivot_1"] == [325.0, 300.0]
        assert key_points["ground_pivot_2"] == [475.0, 300.0]
        assert key_points["crank_end"] == [360.0, 320.0]
        assert key_points["rocker_end"] == [460.0, 345.0]
        assert layer_data["params"]["l1"] == 150.0
        assert layer_data["params"]["L1"] == 150.0

    def test_create_layer_data_from_foundry_preserves_cam_snapshot_center(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="cam_follower",
            parameters={
                "cam_radius": 60.0,
                "cam_offset": 20.0,
                "follower_length": 100.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(520.0, 360.0),
            foundry_snapshot={
                "positions": {
                    "cam_center": [0.0, 0.0],
                    "follower_base": [0.0, -140.0],
                    "follower_end": [0.0, -70.0],
                    "contact_point": [0.0, -60.0],
                }
            },
        )

        assert layer_data["cam_position"] == [520.0, 360.0]
        assert layer_data["params"]["center_x"] == 520.0
        assert layer_data["params"]["center_y"] == 360.0
        assert layer_data["key_points"]["cam_center"] == [520.0, 360.0]
        assert layer_data["key_points"]["follower_base"] == [520.0, 220.0]

    def test_create_layer_data_from_foundry_anchors_to_snapshot_coupler_point(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()
        layer_data = service.create_layer_data_from_foundry(
            mechanism_type="four_bar",
            parameters={
                "ground_link": 150.0,
                "input_link": 40.0,
                "coupler_link": 120.0,
                "output_link": 130.0,
                "input_angle": 30.0,
            },
            pivot_point=(0.0, 0.0),
            part_name="torso",
            scene_position=(400.0, 300.0),
            foundry_snapshot={
                "positions": {
                    "O1": [-75.0, 0.0],
                    "O4": [75.0, 0.0],
                    "A": [-40.0, 20.0],
                    "B": [60.0, 45.0],
                    "coupler_point": [10.0, 15.0],
                }
            },
        )

        key_points = layer_data["key_points"]
        assert key_points["ground_pivot_1"] == [315.0, 285.0]
        assert key_points["ground_pivot_2"] == [465.0, 285.0]
        assert key_points["crank_end"] == [350.0, 305.0]
        assert key_points["rocker_end"] == [450.0, 330.0]

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

    def test_map_foundry_params_to_internal_preserves_output_point_mode(self):
        from automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service import (
            MechanismInstantiationService,
        )

        service = MechanismInstantiationService()

        linkage_params = service.map_foundry_params_to_internal(
            "four_bar",
            {"ground_link": 150.0, "output_point_mode": "joint_a"},
        )
        cam_params = service.map_foundry_params_to_internal(
            "cam_follower",
            {"cam_radius": 60.0, "output_point_mode": "follower_end"},
        )

        assert linkage_params["output_point_mode"] == "joint_a"
        assert cam_params["output_point_mode"] == "follower_base"


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

    def test_resolve_target_part_uses_existing_selection_when_valid(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        fake_tab = SimpleNamespace(
            selected_part_name="left_arm",
            parts_data={
                "head": SimpleNamespace(anchor_joint_id="neck"),
                "left_arm": SimpleNamespace(anchor_joint_id="left_elbow"),
            },
            _prompt_target_part_for_foundry_import=lambda _: "head",
            _select_part_in_list=lambda _: None,
        )

        part_name = MechanismDesignTab._resolve_target_part_for_foundry_import(fake_tab)
        assert part_name == "left_arm"

    def test_resolve_target_part_prompts_user_when_none_selected(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        selected: list[str] = []
        fake_tab = SimpleNamespace(
            selected_part_name=None,
            parts_data={
                "head": SimpleNamespace(anchor_joint_id="neck"),
                "torso": SimpleNamespace(anchor_joint_id="root"),
            },
            _prompt_target_part_for_foundry_import=lambda parts: "torso",
            _select_part_in_list=lambda part: selected.append(part),
            _mvp_presenter=SimpleNamespace(select_part=lambda _: None),
        )

        part_name = MechanismDesignTab._resolve_target_part_for_foundry_import(fake_tab)
        assert part_name == "torso"
        assert fake_tab.selected_part_name == "torso"
        assert selected == ["torso"]

    def test_resolve_foundry_import_scene_position_prefers_part_anchor_joint(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        fake_tab = SimpleNamespace(
            parts_data={"left_arm": SimpleNamespace(anchor_joint_id="left_shoulder", roi=[0, 0, 50, 20])},
            initial_skeleton_cache={
                "joints": {
                    "left_shoulder": {"position": [512.0, 274.0]},
                }
            },
            mechanism_view=None,
        )
        fake_tab._resolve_joint_scene_position_for_part = (
            lambda part_name: MechanismDesignTab._resolve_joint_scene_position_for_part(
                fake_tab, part_name
            )
        )

        position = MechanismDesignTab._resolve_foundry_import_scene_position(fake_tab, "left_arm")
        assert position == (512.0, 274.0)

    def test_resolve_joint_scene_position_prefers_part_item_anchor(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import (
            MechanismDesignTab,
        )

        class _DummyPoint:
            def __init__(self, x: float, y: float):
                self._x = x
                self._y = y

            def x(self) -> float:
                return self._x

            def y(self) -> float:
                return self._y

        class _DummyPartItem:
            def transformOriginPoint(self):
                return _DummyPoint(0.0, 0.0)

            def mapToScene(self, _point):
                return _DummyPoint(450.0, 260.0)

        fake_tab = SimpleNamespace(
            current_editor_items={"left_arm": _DummyPartItem()},
            parts_data={"left_arm": SimpleNamespace(anchor_joint_id="left_shoulder", roi=[0, 0, 50, 20])},
            initial_skeleton_cache=None,
        )

        position = MechanismDesignTab._resolve_joint_scene_position_for_part(fake_tab, "left_arm")
        assert position == (450.0, 260.0)


class TestMechanismDesignGridSettings:
    def test_snap_lengths_to_grid_2_5cm_for_four_bar(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        snapped = MechanismDesignTab._snap_lengths_to_grid(
            tab,
            "four_bar",
            {"l2": 41.0, "l3": 59.9, "l4": 76.2},
        )

        assert snapped["l2"] == 50.0
        assert snapped["l3"] == 50.0
        assert snapped["l4"] == 75.0
        assert snapped["L2"] == 50.0
        assert snapped["L3"] == 50.0
        assert snapped["L4"] == 75.0

    def test_extract_grid_settings_from_foundry_payload(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        tab = MechanismDesignTab.__new__(MechanismDesignTab)
        tab._grid_system_enabled = True
        tab._grid_cell_cm = 2.5

        settings = MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            tab,
            {"grid_system_enabled": False, "grid_cell_cm": 5.0},
        )

        assert settings == (False, 5.0)


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

    def test_update_from_foundry_applies_output_point_mode(self):
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        layer_data = {
            "type": "4_bar_linkage",
            "foundry_synced": True,
            "params": {"l1": 100.0, "l2": 40.0, "l3": 90.0, "l4": 80.0},
        }
        fake_tab = SimpleNamespace(
            mechanism_layers={"mech_1": layer_data},
            _suppress_foundry_sync=False,
            _mechanism_instantiation=SimpleNamespace(
                map_foundry_params_to_internal=MagicMock(
                    return_value={"output_point_mode": "joint_a"}
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
            parameters={"output_point_mode": "joint_a"},
        )

        assert fake_tab.mechanism_layers["mech_1"]["params"]["output_point_mode"] == "joint_a"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
