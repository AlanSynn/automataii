import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from automataii.shared.physical_kit import LETTER_PAGE_HEIGHT_MM, LETTER_PAGE_SIZE_MM


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
        with (
            patch("automataii.application.managers.MechanismManager"),
            patch("automataii.presentation.qt.kinematics.ik_manager.IKManager"),
            patch(
                "automataii.presentation.qt.tabs.parametric_editing_manager.ParametricEditingManager"
            ),
            patch(
                "automataii.presentation.qt.tabs.mechanism_design.services.mechanism_instantiation_service.MechanismInstantiationService"
            ),
        ):
            tab = MechanismDesignTab(mock_main_window)
            # Mock internal data structures often set by signals or init
            tab.parts_data = {}
            tab.mechanism_layers = {}

            # Mock methods we want to verify or that would trigger UI updates
            tab.apply_character_preset = MagicMock(wraps=tab.apply_character_preset)
            tab._map_orphan_mechanisms_to_character = MagicMock(
                wraps=tab._map_orphan_mechanisms_to_character
            )

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
            mechanism_type="four_bar", parameters={"p": 1}, pivot_point=(0, 0)
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
            mechanism_type="four_bar", parameters={"p": 1}, pivot_point=(0, 0)
        )

        # Assertion
        tab.apply_character_preset.assert_not_called()

    def test_map_orphan_mechanisms(self, tab):
        """Test logic for mapping orphan mechanisms to a newly loaded character."""

        # Setup:
        # 1. Orphan mechanism (no part_name)
        mechanism_id = "mech_1"
        tab.mechanism_layers = {mechanism_id: {"part_name": None, "type": "test_mech"}}

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
        tab.mechanism_layers = {"mech_1": {"part_name": None}}

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
        window.image_proc_tab = MagicMock()
        window.skeleton_manager = MagicMock()
        window.ik_manager = MagicMock()
        window.project_state_manager = MagicMock()
        window.action_manager = MagicMock()
        window.project_dir = "/tmp/project"
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)

        AutomataDesigner._handle_project_data_cleared(window)

        assert window.project_dir is None
        window.image_proc_tab.clear_display_and_data.assert_called_once()
        window.editor_tab.clear_editor_content.assert_called_once()
        window.mechanism_design_tab.clear_mechanism_data.assert_called_once()
        window.skeleton_manager.clear_data.assert_called_once()
        window.ik_manager.reset_all_ik_systems_and_data.assert_called_once()
        window.project_state_manager.new_project.assert_called_once()
        window.action_manager.update_actions_for_project_state.assert_called_once_with(False)
        status_bar.showMessage.assert_called_once()

    def test_new_project_ssot_clears_legacy_runtime_data(self) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window._project_controller = MagicMock()
        window._project_controller.new_project.return_value = True
        window.project_data_manager = MagicMock()
        window._suppress_project_data_cleared_ui_once = True

        result = AutomataDesigner.new_project_ssot(window)

        assert result is True
        window._project_controller.set_status_bar.assert_called_once_with(status_bar)
        window._project_controller.new_project.assert_called_once()
        window.project_data_manager.clear_project_data.assert_called_once()
        assert window._suppress_project_data_cleared_ui_once is False

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

    def test_project_load_scales_skeleton_to_fit_letter_sheet_for_plain_image_load(self) -> None:
        from automataii.presentation.qt.main_window import (
            AutomataDesigner,
            _calculate_skeleton_bbox,
        )

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._character_swap_load_in_progress = False
        window._suppress_project_data_cleared_ui_once = False
        window._auto_scale_character_to_dummy_next_load = False
        window.project_dir = None
        window._sync_runtime_state_to_ssot = MagicMock()
        window._mark_workflow_stage_complete = MagicMock()
        window.switch_to_editor_tab = MagicMock()

        window.project_data_manager = MagicMock()
        window.project_data_manager.raw_skeleton_data = [
            {"name": "root", "position": [0.0, 0.0]},
            {"name": "tip", "position": [0.0, 100.0]},
        ]

        window.editor_tab = MagicMock()
        window.mechanism_design_tab = MagicMock()
        window.ik_manager = MagicMock()
        window.skeleton_manager = MagicMock()
        window.skeleton_manager.load_skeleton_from_project_data.return_value = True
        window.image_proc_tab = MagicMock()
        window.action_manager = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window.tab_widget = MagicMock()
        window.tab_widget.currentWidget.return_value = window.editor_tab

        parts_info = {
            "torso": SimpleNamespace(
                roi=[0.0, 0.0, 100.0, 400.0],
                x=0.0,
                y=0.0,
                local_pivot_offset=[50.0, 50.0],
                effective_bbox_offset_x=0.0,
                effective_bbox_offset_y=0.0,
            )
        }

        AutomataDesigner._handle_project_data_loaded(
            window,
            True,
            "/tmp/project",
            parts_info,
        )

        assert window.skeleton_manager.load_skeleton_from_project_data.called
        loaded_raw = window.skeleton_manager.load_skeleton_from_project_data.call_args[0][0]
        loaded_bbox = _calculate_skeleton_bbox(loaded_raw)
        assert loaded_bbox is not None
        loaded_height = loaded_bbox[3] - loaded_bbox[1]
        assert abs(loaded_height - LETTER_PAGE_HEIGHT_MM) < 1e-6

    def test_project_load_scales_parts_to_fit_letter_sheet_for_plain_image_load(self) -> None:
        from automataii.presentation.qt.main_window import (
            AutomataDesigner,
            _calculate_parts_bbox,
        )

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._character_swap_load_in_progress = False
        window._suppress_project_data_cleared_ui_once = False
        window._auto_scale_character_to_dummy_next_load = False
        window.project_dir = None
        window._sync_runtime_state_to_ssot = MagicMock()
        window._mark_workflow_stage_complete = MagicMock()
        window.switch_to_editor_tab = MagicMock()

        window.project_data_manager = MagicMock()
        window.project_data_manager.raw_skeleton_data = [
            {"name": "root", "position": [50.0, 0.0]},
            {"name": "tip", "position": [50.0, 200.0]},
        ]

        window.editor_tab = MagicMock()
        window.mechanism_design_tab = MagicMock()
        window.ik_manager = MagicMock()
        window.skeleton_manager = MagicMock()
        window.skeleton_manager.load_skeleton_from_project_data.return_value = True
        window.image_proc_tab = MagicMock()
        window.action_manager = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window.tab_widget = MagicMock()
        window.tab_widget.currentWidget.return_value = window.editor_tab

        parts_info = {
            "torso": SimpleNamespace(
                roi=[0.0, 0.0, 60.0, 60.0],
                x=0.0,
                y=0.0,
                local_pivot_offset=[30.0, 30.0],
                effective_bbox_offset_x=0.0,
                effective_bbox_offset_y=0.0,
            )
        }

        AutomataDesigner._handle_project_data_loaded(
            window,
            True,
            "/tmp/project",
            parts_info,
        )

        loaded_parts = window.editor_tab.set_parts_data.call_args[0][0]
        bbox = _calculate_parts_bbox(loaded_parts)
        assert bbox is not None
        height = bbox[3] - bbox[1]
        assert abs(height - LETTER_PAGE_SIZE_MM[0]) < 1e-6

    def test_project_load_forces_skeleton_alignment_for_image_pipeline(self) -> None:
        from automataii.presentation.qt.main_window import (
            AutomataDesigner,
            _calculate_skeleton_bbox,
        )

        window = AutomataDesigner.__new__(AutomataDesigner)
        window._character_swap_load_in_progress = False
        window._suppress_project_data_cleared_ui_once = False
        window._auto_scale_character_to_dummy_next_load = False
        window._force_skeleton_parts_alignment_next_load = True
        window.project_dir = None
        window._sync_runtime_state_to_ssot = MagicMock()
        window._mark_workflow_stage_complete = MagicMock()
        window.switch_to_editor_tab = MagicMock()

        window.project_data_manager = MagicMock()
        # Ratio 130/200 = 0.65 (near threshold), should still align when force flag is set.
        window.project_data_manager.raw_skeleton_data = [
            {"name": "root", "position": [50.0, 20.0]},
            {"name": "tip", "position": [50.0, 150.0]},
        ]

        window.editor_tab = MagicMock()
        window.mechanism_design_tab = MagicMock()
        window.ik_manager = MagicMock()
        window.skeleton_manager = MagicMock()
        window.skeleton_manager.load_skeleton_from_project_data.return_value = True
        window.image_proc_tab = MagicMock()
        window.action_manager = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window.tab_widget = MagicMock()
        window.tab_widget.currentWidget.return_value = window.editor_tab

        parts_info = {
            "torso": SimpleNamespace(
                roi=[0.0, 0.0, 100.0, 200.0],
                x=0.0,
                y=0.0,
                local_pivot_offset=[50.0, 50.0],
                effective_bbox_offset_x=0.0,
                effective_bbox_offset_y=0.0,
            )
        }

        AutomataDesigner._handle_project_data_loaded(
            window,
            True,
            "/tmp/project",
            parts_info,
        )

        loaded_raw = window.skeleton_manager.load_skeleton_from_project_data.call_args[0][0]
        loaded_bbox = _calculate_skeleton_bbox(loaded_raw)
        assert loaded_bbox is not None
        loaded_height = loaded_bbox[3] - loaded_bbox[1]
        assert abs(loaded_height - LETTER_PAGE_HEIGHT_MM) < 1e-6
        assert window._force_skeleton_parts_alignment_next_load is False

    def test_parts_generated_uses_dummy_replacement_context_when_dummy_session(
        self, tmp_path: Path
    ) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window.mechanism_design_tab = MagicMock()
        window.image_proc_tab = MagicMock()
        window.image_proc_tab._is_dummy_mechanism_design_session.return_value = True
        window.project_data_manager = MagicMock()
        window.project_data_manager.load_project_from_file.return_value = True
        window._mark_workflow_stage_complete = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window._suppress_project_data_cleared_ui_once = False
        window._character_swap_load_in_progress = False
        window._auto_scale_character_to_dummy_next_load = False
        window._force_skeleton_parts_alignment_next_load = False

        project_dir = tmp_path / "char"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "parts_info.json").write_text("{}", encoding="utf-8")
        char_cfg_path = project_dir / "char_cfg.yaml"
        char_cfg_path.write_text("skeleton: []\n", encoding="utf-8")

        annotation_results = {
            "char_cfg_path": str(char_cfg_path),
        }

        AutomataDesigner.handle_parts_generated_from_tab(
            window, annotation_results, str(project_dir)
        )

        window.mechanism_design_tab.prepare_character_rebind.assert_called_once()
        window.mechanism_design_tab.cancel_character_rebind.assert_not_called()
        assert window._suppress_project_data_cleared_ui_once is True
        assert window._character_swap_load_in_progress is True
        assert window._auto_scale_character_to_dummy_next_load is True
        assert window._force_skeleton_parts_alignment_next_load is True

    def test_parts_generated_load_image_context_skips_dummy_replacement_flags(
        self, tmp_path: Path
    ) -> None:
        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window.mechanism_design_tab = MagicMock()
        window.image_proc_tab = MagicMock()
        window.image_proc_tab._is_dummy_mechanism_design_session.return_value = False
        window.project_data_manager = MagicMock()
        window.project_data_manager.load_project_from_file.return_value = True
        window._mark_workflow_stage_complete = MagicMock()
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window._suppress_project_data_cleared_ui_once = True
        window._character_swap_load_in_progress = True
        window._auto_scale_character_to_dummy_next_load = True
        window._force_skeleton_parts_alignment_next_load = True

        project_dir = tmp_path / "char"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "parts_info.json").write_text(json.dumps({}), encoding="utf-8")
        char_cfg_path = project_dir / "char_cfg.yaml"
        char_cfg_path.write_text("skeleton: []\n", encoding="utf-8")

        annotation_results = {
            "char_cfg_path": str(char_cfg_path),
        }

        AutomataDesigner.handle_parts_generated_from_tab(
            window, annotation_results, str(project_dir)
        )

        window.mechanism_design_tab.prepare_character_rebind.assert_not_called()
        window.mechanism_design_tab.cancel_character_rebind.assert_called_once()
        assert window._suppress_project_data_cleared_ui_once is False
        assert window._character_swap_load_in_progress is False
        assert window._auto_scale_character_to_dummy_next_load is False
        assert window._force_skeleton_parts_alignment_next_load is False
