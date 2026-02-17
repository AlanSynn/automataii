from unittest.mock import MagicMock, patch

import pytest


class TestAutoCharacterAssignment:
    @pytest.fixture
    def app(self):
        try:
            import sys

            from PyQt6.QtWidgets import QApplication
            return QApplication.instance() or QApplication(sys.argv)
        except ImportError:
            pytest.skip("PyQt6 not available")

    @pytest.fixture
    def mock_main_window(self):
        mw = MagicMock()
        mw.skeleton_manager = MagicMock()
        mw.project_data_manager = MagicMock()
        return mw

    @pytest.fixture
    def tab(self, app, mock_main_window):
        # We need to mock MechanismDesignTab to avoid complex init or just instantiate it if possible.
        # Given it has many dependencies, partial mocking might be safer if we can't instantiate easily.
        # But let's try to instantiate it with a mocked MainWindow.

        # We need to ensure we can import it first
        from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

        # We need to mock the managers that the tab initializes or uses
        with patch('automataii.application.managers.MechanismManager'), \
             patch('automataii.presentation.qt.kinematics.ik_manager.IKManager'), \
             patch('automataii.presentation.qt.tabs.parametric_editing_manager.ParametricEditingManager'), \
             patch('automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service.MechanismInstantiationService'):

             tab = MechanismDesignTab(mock_main_window)
             # Mock internal data structures often set by signals or init
             tab.parts_data = {}
             tab.mechanism_layers = {}

             # Mock methods we want to verify or that would trigger UI updates
             tab.apply_character_preset = MagicMock(wraps=tab.apply_character_preset)
             tab._map_orphan_mechanisms_to_character = MagicMock(wraps=tab._map_orphan_mechanisms_to_character)

             # Mock preset loading to avoid file system reading
             tab.character_preset_service = MagicMock()
             # Mock create_silhouette_human to return a dummy preset object
             mock_preset = MagicMock()
             mock_preset.name = "Human Silhouette"
             mock_preset.skeleton = {}
             mock_preset.parts = {"head": MagicMock(name="head"), "torso": MagicMock(name="torso")}
             tab.character_preset_service.get_preset.return_value = mock_preset

             # Mock set_parts_data to actually populate parts_data for the logic to work
             def side_effect_set_parts(parts, clear_mechanisms=False):
                 tab.parts_data = parts
             tab.set_parts_data = MagicMock(side_effect=side_effect_set_parts)

             return tab

    def test_auto_load_dummy_character_on_empty_import(self, tab):
        """Test that importing a mechanism when no parts exist triggers dummy character loading."""

        # Setup: Empty parts data
        tab.parts_data = {}

        # Action: Import mechanism
        # We need to mock _add_mechanism_layer to avoid failure
        tab._add_mechanism_layer = MagicMock()

        tab.import_mechanism_from_foundry(
            mechanism_type="four_bar",
            parameters={"p": 1},
            pivot_point=(0,0)
        )

        # Assertion: fallback preset path can still be used in isolated tests
        # (dummy project load signal chain is not fully wired in this fixture).
        tab.apply_character_preset.assert_called_once_with("silhouette_human")

    def test_auto_load_prefers_dummy_character_when_available(self, tab):
        """Dummy character directory should be tried before preset fallback."""
        from pathlib import Path

        tab.parts_data = {}
        tab._resolve_dummy_character_dir = MagicMock(return_value=Path("/tmp/dummy"))

        def _load_dummy(_path):
            tab.parts_data = {"torso": {}}
            return True

        tab.load_character_from_directory = MagicMock(side_effect=_load_dummy)
        tab.apply_character_preset = MagicMock(return_value=False)
        tab._add_mechanism_layer = MagicMock(
            side_effect=lambda mid, layer: tab.mechanism_layers.__setitem__(mid, layer)
        )
        tab._regenerate_foundry_layer_simulation = MagicMock()
        tab._render_mechanism_layer = MagicMock()
        tab._update_mechanism_layers_list = MagicMock()
        tab._update_all_ui_states = MagicMock()
        tab.play_btn = MagicMock()
        tab.reset_btn = MagicMock()
        tab._mechanism_instantiation = MagicMock()
        tab._mechanism_instantiation.create_layer_data_from_foundry.return_value = {
            "id": "m1",
            "type": "4_bar_linkage",
            "part_name": "torso",
            "params": {},
        }

        result = tab.import_mechanism_from_foundry(
            mechanism_type="four_bar",
            parameters={"ground_link": 100.0},
            pivot_point=(0.0, 0.0),
            mechanism_id="m1",
        )

        assert result is True
        tab.load_character_from_directory.assert_called_once()
        tab.apply_character_preset.assert_not_called()

    def test_no_auto_load_if_parts_exist(self, tab):
        """Test that importing a mechanism DOES NOT trigger load if parts already exist."""

        # Setup: Existing parts
        tab.parts_data = {"existing_part": {}}

        # Action
        tab._add_mechanism_layer = MagicMock()
        tab.import_mechanism_from_foundry(
            mechanism_type="four_bar",
            parameters={"p": 1},
            pivot_point=(0,0)
        )

        # Assertion
        tab.apply_character_preset.assert_not_called()

    def test_map_orphan_mechanisms(self, tab):
        """Test logic for mapping orphan mechanisms to a newly loaded character."""

        # Setup:
        # 1. Orphan mechanism (no part_name)
        mechanism_id = "mech_1"
        tab.mechanism_layers = {
            mechanism_id: {"part_name": None, "type": "test_mech"}
        }

        # 2. Simulate parts being loaded (e.g. by applying preset)
        tab.parts_data = {"head": {}, "torso": {}}

        # Action: Manually call the mapping method (or via apply_character_preset)
        tab._map_orphan_mechanisms_to_character()

        # Assertion
        # It should map to the first available part (e.g. 'head' given default dict order)
        # Note: dict order is preserved in Python 3.7+
        assigned_part = tab.mechanism_layers[mechanism_id]["part_name"]
        assert assigned_part in ["head", "torso"]
        print(f"Orphan mechanism mapped to: {assigned_part}")

    def test_apply_preset_triggers_mapping(self, tab):
        """Test that applying a preset triggers the orphan mapping logic."""

        # Setup
        tab.mechanism_layers = {
            "mech_1": {"part_name": None}
        }

        # Action
        tab.apply_character_preset("silhouette_human")

        # Assertion
        tab._map_orphan_mechanisms_to_character.assert_called_once()

    def test_apply_preset_failure_clears_pending_rebind_flags(self, tab):
        """apply_character_preset should clear rebind flags when an exception occurs."""
        tab.cancel_character_rebind = MagicMock(wraps=tab.cancel_character_rebind)
        tab.set_parts_data.side_effect = RuntimeError("simulated preset failure")

        result = tab.apply_character_preset("silhouette_human")

        assert result is False
        tab.cancel_character_rebind.assert_called()

    def test_pending_rebind_waits_for_new_skeleton_generation(self, tab):
        """Rebind should not run against stale cached skeleton while character replacement is in progress."""
        tab.parts_data = {"torso": MagicMock(anchor_joint_id="torso")}
        tab.mechanism_layers = {
            "mech_1": {
                "id": "mech_1",
                "type": "4_bar_linkage",
                "part_name": None,
                "params": {},
                "key_points": {},
            }
        }
        tab._initial_skeleton_data_cache = {"joints": {"root": {"position": [10.0, 10.0]}}}
        tab._skeleton_cache_generation = 5
        tab._map_orphan_mechanisms_to_character = MagicMock()

        tab.prepare_character_rebind()
        tab._attempt_pending_character_rebind()

        tab._map_orphan_mechanisms_to_character.assert_not_called()
        assert tab._pending_character_rebind is True

        tab.cache_initial_skeleton({"joints": {"root": {"position": [100.0, 200.0]}}})

        tab._map_orphan_mechanisms_to_character.assert_called_once()
        assert tab._pending_character_rebind is False

    def test_project_data_cleared_is_suppressed_during_character_swap_load(self) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._suppress_project_data_cleared_ui_once = True
        window.editor_tab = MagicMock()
        window.mechanism_design_tab = MagicMock()
        window.skeleton_manager = MagicMock()
        window.ik_manager = MagicMock()
        window.project_state_manager = MagicMock()
        window.action_manager = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)

        AutomataDesigner._handle_project_data_cleared(window)

        window.editor_tab.clear_editor_content.assert_not_called()
        window.mechanism_design_tab.clear_mechanism_data.assert_not_called()
        window.skeleton_manager.clear_data.assert_not_called()
        window.project_state_manager.new_project.assert_not_called()
        window.action_manager.update_actions_for_project_state.assert_not_called()
        assert window._suppress_project_data_cleared_ui_once is True

    def test_project_data_cleared_resets_ui_when_not_suppressed(self) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._suppress_project_data_cleared_ui_once = False
        window.editor_tab = MagicMock()
        window.mechanism_design_tab = MagicMock()
        window.skeleton_manager = MagicMock()
        window.ik_manager = MagicMock()
        window.project_state_manager = MagicMock()
        window.action_manager = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)

        AutomataDesigner._handle_project_data_cleared(window)

        window.editor_tab.clear_editor_content.assert_called_once()
        window.mechanism_design_tab.clear_mechanism_data.assert_called_once()
        window.skeleton_manager.clear_data.assert_called_once()
        window.ik_manager.reset_all_ik_systems_and_data.assert_called_once()
        window.project_state_manager.new_project.assert_called_once()
        window.action_manager.update_actions_for_project_state.assert_called_once_with(False)
        status_bar.showMessage.assert_called_once()

    def test_failed_character_swap_load_keeps_existing_ui_state(self) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._character_swap_load_in_progress = True
        window._suppress_project_data_cleared_ui_once = False
        window._auto_scale_character_to_dummy_next_load = False
        window.mechanism_design_tab = MagicMock()
        window._clear_ui_for_failed_load = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window.action_manager = MagicMock()

        with patch("automataii.presentation.qt.main_window.QMessageBox.critical"):
            AutomataDesigner._handle_project_data_loaded(window, False, "/tmp/project", {})

        window._clear_ui_for_failed_load.assert_not_called()
        window.action_manager.update_actions_for_project_state.assert_not_called()
        status_bar.showMessage.assert_called()

    def test_failed_non_swap_load_clears_ui_state(self) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._character_swap_load_in_progress = False
        window._suppress_project_data_cleared_ui_once = False
        window._auto_scale_character_to_dummy_next_load = False
        window.mechanism_design_tab = MagicMock()
        window._clear_ui_for_failed_load = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window.action_manager = MagicMock()

        with patch("automataii.presentation.qt.main_window.QMessageBox.critical"):
            AutomataDesigner._handle_project_data_loaded(window, False, "/tmp/project", {})

        window._clear_ui_for_failed_load.assert_called_once()
        window.action_manager.update_actions_for_project_state.assert_called_once_with(False)
        status_bar.showMessage.assert_called()
