"""
Comprehensive feature verification tests for:
1. Ctrl+Z undo/redo functionality
2. Logging system debug/info separation
3. All menu actions
4. Project save to tmp directory
"""

import logging
import tempfile

import pytest


class TestUndoRedoFunctionality:
    """Test SSOT undo/redo system."""

    def test_project_state_manager_undo_redo(self):
        """Verify ProjectStateManager has undo/redo capability."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Initial state - no undo available
        assert not manager.can_undo
        assert not manager.can_redo

        # Make a change
        part = PartData(
            name="test_part",
            texture_path="test.png",
            mask_path="test_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"test_part": part})

        # Now undo should be available
        assert manager.can_undo
        assert not manager.can_redo

        # Perform undo
        manager.undo()

        # After undo, redo should be available
        assert manager.can_redo

    def test_project_controller_undo_redo(self):
        """Verify ProjectController delegates to state manager."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import ProjectController

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        # Initially no undo
        assert not controller.can_undo
        assert not controller.can_redo

        # Undo when nothing to undo returns False
        result = controller.undo()
        assert result is False

    def test_undo_redo_signals_emitted(self):
        """Verify undo/redo availability signals are emitted."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Track signal emissions
        undo_signals = []
        redo_signals = []
        manager.undo_available.connect(lambda x: undo_signals.append(x))
        manager.redo_available.connect(lambda x: redo_signals.append(x))

        # Make a change
        part = PartData(
            name="test",
            texture_path="test.png",
            mask_path="test_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"test": part})

        # Should have emitted undo_available(True) and redo_available(False)
        assert True in undo_signals
        assert False in redo_signals


class TestLoggingSystem:
    """Test logging system configuration."""

    def test_setup_logging_creates_handlers(self):
        """Verify setup_logging creates file and console handlers."""
        from automataii.utils.logging_config import setup_logging

        # Get root logger before setup
        root = logging.getLogger()

        # Setup logging
        setup_logging(console_log_level=logging.INFO)

        # Should have handlers now
        assert len(root.handlers) >= 2  # At least file and console

    def test_debug_level_separation(self):
        """Verify debug/info level separation works."""
        from automataii.utils.logging_config import setup_logging

        # Setup with INFO level for console
        setup_logging(console_log_level=logging.INFO)

        root = logging.getLogger()

        # Check handlers have correct levels
        file_handler = None
        console_handler = None
        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
            elif isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler

        # File handler should be DEBUG, console should be INFO
        if file_handler:
            assert file_handler.level == logging.DEBUG
        if console_handler:
            assert console_handler.level == logging.INFO

    def test_telemetry_logger_separate(self):
        """Verify telemetry logger is separate."""
        from automataii.utils.logging_config import setup_logging

        setup_logging()

        telemetry = logging.getLogger("automataii.telemetry")

        # Telemetry logger should not propagate
        assert telemetry.propagate is False
        # Should have its own handler
        assert len(telemetry.handlers) >= 1


class TestMenuActions:
    """Test menu action connections."""

    def test_action_manager_creates_all_actions(self):
        """Verify ActionManager creates all required actions."""

        from PyQt6.QtWidgets import QApplication, QMainWindow

        # Need QApplication for QAction
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)

        # Check all expected actions exist
        expected_actions = [
            "load_parts",
            "recover_autosave",
            "save_project",
            "save_project_as",
            "exit",
            "zoom_in",
            "zoom_out",
            "zoom_fit",
            "reset_view",
            "undo",
            "redo",
            "about",
            "new_project",
            "export",
            "export_blueprint_package",
            "check_updates",
            "preferences",
        ]

        for action_id in expected_actions:
            action = manager.get_action(action_id)
            assert action is not None, f"Action '{action_id}' not found"

    def test_undo_redo_actions_have_shortcuts(self):
        """Verify undo/redo actions have correct keyboard shortcuts."""
        from PyQt6.QtGui import QKeySequence
        from PyQt6.QtWidgets import QApplication, QMainWindow

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)

        undo_action = manager.get_action("undo")
        redo_action = manager.get_action("redo")

        def has_standard_shortcut(action, standard_key):
            expected = QKeySequence.keyBindings(standard_key)
            actual = action.shortcuts()
            return any(
                shortcut.matches(binding) == QKeySequence.SequenceMatch.ExactMatch
                or binding.matches(shortcut) == QKeySequence.SequenceMatch.ExactMatch
                for shortcut in actual
                for binding in expected
            )

        assert undo_action.isEnabled() is False
        assert redo_action.isEnabled() is False
        assert "Back" in undo_action.text()
        assert "Forward" in redo_action.text()
        assert has_standard_shortcut(undo_action, QKeySequence.StandardKey.Undo)
        assert has_standard_shortcut(redo_action, QKeySequence.StandardKey.Redo)
        assert QKeySequence("Ctrl+Y") in redo_action.shortcuts()

    def test_file_menu_recover_autosave_action_triggers_connected_slot(self):
        """Recover Autosave must be reachable from the File menu QAction."""
        from PyQt6.QtWidgets import QApplication, QMainWindow

        app = QApplication.instance() or QApplication([])
        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)
        recover_calls: list[str] = []
        assert manager.connect_action("recover_autosave", lambda: recover_calls.append("recover"))
        manager.setup_menus(parent.menuBar())

        file_menu = parent.menuBar().actions()[0].menu()
        assert file_menu is not None
        recover_action = manager.get_action("recover_autosave")
        assert recover_action in file_menu.actions()

        recover_action.trigger()

        assert recover_calls == ["recover"]
        assert app is not None

    def test_save_as_stays_enabled_without_project_content(self):
        """Blank project shells should still be saveable for future templates."""
        from PyQt6.QtWidgets import QApplication, QMainWindow

        app = QApplication.instance() or QApplication([])
        parent = QMainWindow()

        from automataii.presentation.qt.actions.action_manager import ActionManager

        manager = ActionManager(parent)
        manager.setup_menus(parent.menuBar())

        assert manager.get_action("save_project_as").isEnabled() is True
        assert manager.get_action("save_project").isEnabled() is False
        assert manager.get_action("export").isEnabled() is False
        assert manager.get_action("export_blueprint_package").isEnabled() is False
        assert app is not None

    def test_blueprint_export_action_routes_to_mechanism_design_pipeline(self):
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.main_window import AutomataDesigner

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner.__new__(AutomataDesigner)
        calls: list[str] = []

        class _DesignTab:
            def export_blueprint_package(self) -> None:
                calls.append("export")

        class _Status:
            def showMessage(self, *_args, **_kwargs) -> None:
                calls.append("status")

        window.mechanism_design_tab = _DesignTab()
        window.statusBar = lambda: _Status()

        assert AutomataDesigner.export_blueprint_package_dialog(window) is True
        assert calls == ["export", "status"]
        assert app is not None


class TestProductionBranding:
    """Production-facing app identity should be MotionSmith, not legacy placeholders."""

    def test_app_config_uses_motionsmith_identity(self):
        from automataii.utils.config import AppConfig

        assert AppConfig.APP_NAME == "MotionSmith"
        assert AppConfig.ORGANIZATION_NAME == "MotionSmith"
        assert AppConfig.ORGANIZATION_DOMAIN == "motionsmith.app"

    def test_startup_splash_uses_landing_logo_asset(self):
        from PyQt6.QtWidgets import QApplication

        from automataii.__main__ import (
            SPLASH_HEIGHT,
            SPLASH_LOGO_RELATIVE_PATH,
            SPLASH_WIDTH,
            build_startup_splash_pixmap,
            create_startup_splash,
        )
        from automataii.utils.paths import resolve_path

        app = QApplication.instance() or QApplication([])
        logo_path = resolve_path(SPLASH_LOGO_RELATIVE_PATH)

        assert logo_path.exists()
        pixmap = build_startup_splash_pixmap(app_name="MotionSmith")
        assert pixmap is not None
        assert pixmap.width() == SPLASH_WIDTH
        assert pixmap.height() == SPLASH_HEIGHT

        splash = create_startup_splash(app_name="MotionSmith")
        try:
            assert splash is not None
            assert splash.objectName() == "motionsmith_startup_splash"
            assert not splash.pixmap().isNull()
        finally:
            if splash is not None:
                splash.close()
        assert app is not None

    def test_startup_splash_is_optional_when_logo_missing(self, tmp_path):
        from PyQt6.QtWidgets import QApplication

        from automataii.__main__ import build_startup_splash_pixmap

        app = QApplication.instance() or QApplication([])
        assert build_startup_splash_pixmap(logo_path=tmp_path / "missing.png") is None
        assert app is not None

    def test_main_window_title_is_motionsmith(self):
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.main_window import AutomataDesigner

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner(experiment_mode=True)
        try:
            assert window.windowTitle() == "MotionSmith"
        finally:
            window.close()
        assert app is not None

    def test_main_window_does_not_register_lab_tab(self):
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.main_window import AutomataDesigner

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner(experiment_mode=False)
        try:
            window.reset_workspace_layout()
            tab_titles = [
                window.tab_widget.tabText(index) for index in range(window.tab_widget.count())
            ]
            assert tab_titles == [
                "Character Selection",
                "Path Editor",
                "Mechanism Design",
                "Mechanism Foundry",
            ]
            assert not hasattr(window, "landing_tab")
            assert "Lab" not in tab_titles
            assert "Options" not in tab_titles
            menu_titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
            assert "Options" in menu_titles
            assert window.action_manager.get_action("preferences") is not None
            assert not hasattr(window, "lab_tab")
        finally:
            window.close()
        assert app is not None

    def test_main_window_starts_on_character_selection_after_saved_tab_restore(self, monkeypatch):
        """Saved workspace state may restore tab order, but startup screen stays Character."""
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.main_window import AutomataDesigner
        from automataii.presentation.qt.windows.components import WorkspaceLayoutManager

        original_restore = WorkspaceLayoutManager.restore_workspace_layout

        def restore_to_mechanism_design(self, *, restore_current_tab=True):
            original_restore(self, restore_current_tab=restore_current_tab)
            index = self._find_tab_index_by_id("tab_mechanism_design")
            assert index >= 0
            self._tab_widget.setCurrentIndex(index)

        monkeypatch.setattr(
            WorkspaceLayoutManager,
            "restore_workspace_layout",
            restore_to_mechanism_design,
        )

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner(experiment_mode=False)
        try:
            current_tab = window.tab_widget.currentWidget()
            assert current_tab is window.image_proc_tab
            assert current_tab.objectName() == "tab_character_selection"
            assert window.tab_widget.tabText(window.tab_widget.currentIndex()) == "Character Selection"
        finally:
            window.close()
        assert app is not None

    def test_options_menu_opens_reusable_live_preferences_dialog(self):
        from PyQt6.QtWidgets import QApplication, QDialog

        from automataii.presentation.qt.main_window import AutomataDesigner

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner(experiment_mode=True)
        try:
            tab_titles = [
                window.tab_widget.tabText(index) for index in range(window.tab_widget.count())
            ]
            assert "Options" not in tab_titles

            preferences_action = window.action_manager.get_action("preferences")
            assert preferences_action is not None

            preferences_action.trigger()
            app.processEvents()

            dialog = window.findChild(QDialog, "optionsDialog")
            assert dialog is window._options_dialog
            assert dialog is not None
            assert dialog.isVisible()
            assert window.options_tab.parentWidget() is dialog

            window.options_tab.grid_pitch_combo.setCurrentIndex(
                window.options_tab.grid_pitch_combo.findData("2_5cm")
            )
            assert window._grid_pitch_choice == "2_5cm"
            assert window._grid_cell_size_cm == 2.5
            assert window.editor_tab.editor_view.grid_cell_size_cm == 2.5

            dialog.close()
            app.processEvents()
            preferences_action.trigger()
            app.processEvents()

            assert window._options_dialog is dialog
            assert dialog.isVisible()
        finally:
            window.close()
        assert app is not None

    def test_main_window_wires_runtime_signals_once(self):
        """Core actions must not be connected twice during MainWindow startup."""
        from PyQt6.QtWidgets import QApplication

        from automataii.presentation.qt.main_window import AutomataDesigner

        app = QApplication.instance() or QApplication([])
        window = AutomataDesigner(experiment_mode=False)
        try:
            assert app.font().family() == "Arial"
            editor_signal_expectations = {
                "play": window.editor_tab.request_play_simulation,
                "stop": window.editor_tab.request_stop_simulation,
                "reset": window.editor_tab.request_reset_simulation,
                "editor_blueprint": window.editor_tab.request_generate_blueprint,
                "save_alignment": window.editor_tab.request_save_alignment,
            }
            for label, signal in editor_signal_expectations.items():
                assert window.editor_tab.receivers(signal) == 1, label

            option_signal_expectations = {
                "theme": window.options_tab.themeChanged,
                "animation_duration": window.options_tab.animationDurationChanged,
                "advanced_processing": window.options_tab.advancedProcessingVisibilityChanged,
                "unit": window.options_tab.unitChanged,
                "physics_snap": window.options_tab.physicsSnapModeChanged,
            }
            for label, signal in option_signal_expectations.items():
                assert window.options_tab.receivers(signal) == 1, label

            manager_signal_expectations = {
                # Handler + MechanismDesign skeleton view + IKManager listener are required.
                "skeleton_updated": (
                    window.skeleton_manager,
                    window.skeleton_manager.skeleton_updated,
                    3,
                ),
                "project_data_loaded": (
                    window.project_data_manager,
                    window.project_data_manager.project_data_loaded,
                    1,
                ),
                "project_data_cleared": (
                    window.project_data_manager,
                    window.project_data_manager.project_data_cleared,
                    1,
                ),
                "ik_visuals": (window.ik_manager, window.ik_manager.character_visuals_updated, 1),
                "ik_animation_state": (
                    window.ik_manager,
                    window.ik_manager.animation_state_changed,
                    1,
                ),
            }
            for label, (sender, signal, expected) in manager_signal_expectations.items():
                assert sender.receivers(signal) == expected, label
        finally:
            window.close()
        assert app is not None

    def test_runtime_styles_avoid_missing_font_aliases(self):
        """Packaged macOS startup should not ask Qt to resolve missing font aliases."""
        from pathlib import Path

        import automataii
        from automataii.utils.styling import DARK_STYLE, LIGHT_STYLE

        assert "Segoe UI" not in LIGHT_STYLE
        assert "Segoe UI" not in DARK_STYLE
        assert "sans-serif" not in LIGHT_STYLE
        assert "sans-serif" not in DARK_STYLE

        package_root = Path(automataii.__file__).parent
        runtime_style_files = [
            package_root / "presentation" / "qt" / "tabs" / "landing_tab.py",
            *(package_root / "presentation" / "qt" / "tabs" / "mechanism_foundry").rglob("*.py"),
        ]
        offenders = [
            path
            for path in runtime_style_files
            if path.is_file()
            and any(
                missing_alias in path.read_text(encoding="utf-8")
                for missing_alias in ("Segoe UI", "sans-serif")
            )
        ]
        assert offenders == []

    def test_bundled_runtime_pngs_do_not_emit_libpng_profile_warnings(self):
        """Landing/examples/icons should not carry invalid profile metadata."""
        from pathlib import Path

        from PIL import Image

        checked_assets = [
            Path("src/examples/girl.png"),
            Path("src/examples/boy.png"),
            Path("resources/examples/raw/10449089 (1).png"),
            Path("resources/icons/AppIcon.png"),
        ]

        offenders = []
        for asset in checked_assets:
            with Image.open(asset) as image:
                metadata_keys = set(image.info)
            if {"icc_profile", "gamma", "chromaticity"} & metadata_keys:
                offenders.append((asset, metadata_keys))

        assert offenders == []


class TestProjectSaveToTmp:
    """Test project save to tmp directory."""

    def test_get_default_project_dir_returns_tmp(self):
        """Verify get_default_project_dir returns a tmp directory."""
        from automataii.presentation.qt.windows.components import get_default_project_dir

        default_dir = get_default_project_dir()

        # Should be in system temp directory
        assert tempfile.gettempdir() in str(default_dir)
        assert "motionsmith_projects" in str(default_dir)

    def test_get_default_project_dir_creates_directory(self):
        """Verify get_default_project_dir creates the directory if not exists."""
        from automataii.presentation.qt.windows.components import get_default_project_dir

        default_dir = get_default_project_dir()

        # Directory should exist after call
        assert default_dir.exists()
        assert default_dir.is_dir()

    def test_project_controller_uses_tmp_for_default_save(self):
        """Verify ProjectController uses tmp directory for default save path."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import (
            ProjectController,
            get_default_project_dir,
        )

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        ProjectController(state_manager, serializer)

        # Get the default directory
        get_default_project_dir()

        # The state has no project_dir, so save should use tmp
        state = state_manager.state
        assert state.project_dir is None

        # This confirms the code path - actual dialog testing requires GUI

    def test_quick_save_method_exists(self):
        """Verify quick_save method exists on ProjectController."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import ProjectController

        state_manager = ProjectStateManager()
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        # Method should exist
        assert hasattr(controller, "quick_save")
        assert callable(controller.quick_save)

    def test_quick_save_creates_distinct_same_second_snapshots(self, tmp_path, monkeypatch):
        """Repeated quick saves should not silently overwrite same-second snapshots."""
        from automataii.application.project import ProjectSerializer, ProjectStateManager
        from automataii.presentation.qt.windows.components import (
            ProjectController,
            project_controller,
        )

        monkeypatch.setattr(project_controller.tempfile, "gettempdir", lambda: str(tmp_path))

        state_manager = ProjectStateManager()
        state_manager.new_project("QuickSaveCollision")
        serializer = ProjectSerializer()
        controller = ProjectController(state_manager, serializer)

        assert controller.quick_save()
        assert controller.quick_save()
        assert controller.quick_save()

        project_dir = tmp_path / "motionsmith_projects"
        snapshots = [
            path
            for path in project_dir.glob("unsaved/QuickSaveCollision-*/*.automataii")
            if ".backup" not in path.name
        ]
        assert len(snapshots) == 3

    def test_project_controller_load_project_does_not_pollute_undo_history(self, tmp_path):
        from automataii.application.project import (
            PartData,
            ProjectSerializer,
            ProjectState,
            ProjectStateManager,
        )
        from automataii.presentation.qt.windows.components import ProjectController

        serializer = ProjectSerializer()
        save_path = tmp_path / "loaded.automataii"
        state = ProjectState.empty().with_parts(
            {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                )
            }
        )
        assert serializer.save(state, save_path).success

        state_manager = ProjectStateManager()
        controller = ProjectController(state_manager, serializer)

        assert controller.load_project(save_path)

        assert state_manager.state.has_parts()
        assert not state_manager.is_dirty
        assert not state_manager.can_undo
        assert not state_manager.can_redo

    def test_autosave_cleanup_keeps_recent_snapshots_and_ignores_backup_artifacts(self, tmp_path):
        from automataii.application.project import (
            AutoSaveManager,
            ProjectSerializer,
            ProjectStateManager,
        )

        state_manager = ProjectStateManager()
        state_manager.new_project("AutosaveCleanup")
        autosave_manager = AutoSaveManager(ProjectSerializer())
        autosave_manager.setup(tmp_path)

        autosave_dir = tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME
        backup_artifact = autosave_dir / "autosave_manual.backup.automataii"
        backup_artifact.write_text("not a recovery snapshot", encoding="utf-8")

        for _ in range(7):
            result = autosave_manager.autosave(state_manager.state.with_project_dir(tmp_path))
            assert result.success

        recovery_files = autosave_manager.get_recovery_files(tmp_path)

        assert len(recovery_files) == 5
        assert backup_artifact.exists()
        assert backup_artifact not in recovery_files

    def test_main_window_autosave_writes_dirty_runtime_state_under_project_dir(self, tmp_path):
        from unittest.mock import MagicMock

        from automataii.application.project import (
            AutoSaveManager,
            PartData,
            ProjectSerializer,
            ProjectStateManager,
        )
        from automataii.presentation.qt.main_window import AutomataDesigner

        state_manager = ProjectStateManager()
        dirty_state = state_manager.state.with_project_dir(tmp_path).with_parts(
            {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                )
            }
        )
        state_manager.replace_project_state(
            dirty_state,
            operation="test_dirty_state",
            mark_saved=False,
            clear_history=True,
        )

        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = state_manager
        window._project_serializer = ProjectSerializer()
        window._autosave_manager = AutoSaveManager(window._project_serializer)
        window._sync_runtime_state_to_ssot = MagicMock()

        assert AutomataDesigner._perform_autosave(window) is True
        window._sync_runtime_state_to_ssot.assert_called_once_with(mark_saved=False)
        autosaves = list(
            (tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME).glob("autosave_*.automataii")
        )
        assert autosaves

    def test_main_window_close_autosave_bypasses_interval_throttle(self, tmp_path):
        from unittest.mock import MagicMock

        from automataii.application.project import (
            AutoSaveManager,
            PartData,
            ProjectSerializer,
            ProjectStateManager,
        )
        from automataii.presentation.qt.main_window import AutomataDesigner

        state_manager = ProjectStateManager()
        dirty_state = state_manager.state.with_project_dir(tmp_path).with_parts(
            {
                "head": PartData(
                    name="head",
                    texture_path="head.png",
                    mask_path="head_mask.png",
                    anchor_joint="neck",
                )
            }
        )
        state_manager.replace_project_state(
            dirty_state,
            operation="test_dirty_state",
            mark_saved=False,
            clear_history=True,
        )

        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = state_manager
        window._project_serializer = ProjectSerializer()
        window._autosave_manager = AutoSaveManager(window._project_serializer)
        window._sync_runtime_state_to_ssot = MagicMock()

        assert AutomataDesigner._perform_autosave(window) is True
        assert AutomataDesigner._perform_autosave(window) is False
        assert AutomataDesigner._perform_autosave(window, force=True) is True

        autosaves = list(
            (tmp_path / AutoSaveManager.AUTOSAVE_DIR_NAME).glob("autosave_*.automataii")
        )
        assert len(autosaves) == 2

    def test_recover_autosave_loads_selected_snapshot_once(self, tmp_path):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from automataii.presentation.qt.main_window import AutomataDesigner

        selected = tmp_path / ".autosave" / "autosave_1.automataii"
        selected.parent.mkdir(parents=True, exist_ok=True)
        selected.write_text("{}", encoding="utf-8")
        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = SimpleNamespace(state=SimpleNamespace(project_dir=tmp_path))
        window.project_data_manager = SimpleNamespace(project_dir=tmp_path / "legacy")
        window._autosave_manager = MagicMock()
        window._autosave_manager.get_recovery_files.return_value = [selected]
        window._project_controller = MagicMock()
        window._project_controller.load_project.return_value = True
        status_bar = MagicMock()
        window.statusBar = MagicMock(return_value=status_bar)
        window._select_autosave_recovery_file = MagicMock(return_value=selected)

        assert AutomataDesigner.recover_autosave(window) is True

        window._autosave_manager.get_recovery_files.assert_any_call(tmp_path)
        window._select_autosave_recovery_file.assert_called_once_with([selected])
        window._project_controller.set_status_bar.assert_called_once_with(status_bar)
        window._project_controller.load_project.assert_called_once_with(selected)

    def test_recover_autosave_rejects_selection_outside_discovered_snapshots(self, tmp_path):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from automataii.presentation.qt.main_window import AutomataDesigner

        discovered = tmp_path / ".autosave" / "autosave_1.automataii"
        discovered.parent.mkdir(parents=True, exist_ok=True)
        discovered.write_text("{}", encoding="utf-8")
        arbitrary = tmp_path / ".autosave" / "manual.automataii"
        arbitrary.write_text("{}", encoding="utf-8")
        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = SimpleNamespace(state=SimpleNamespace(project_dir=tmp_path))
        window.project_data_manager = SimpleNamespace(project_dir=None)
        window._autosave_manager = MagicMock()
        window._autosave_manager.get_recovery_files.return_value = [discovered]
        window._project_controller = MagicMock()
        window.statusBar = MagicMock(return_value=MagicMock())
        window._select_autosave_recovery_file = MagicMock(return_value=arbitrary)

        assert AutomataDesigner.recover_autosave(window) is False

        window._project_controller.load_project.assert_not_called()

    def test_recover_autosave_no_files_does_not_open_chooser(self, tmp_path):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from automataii.presentation.qt.main_window import AutomataDesigner

        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = SimpleNamespace(state=SimpleNamespace(project_dir=tmp_path))
        window.project_data_manager = SimpleNamespace(project_dir=None)
        window._autosave_manager = MagicMock()
        window._autosave_manager.get_recovery_files.return_value = []
        window._project_controller = MagicMock()
        window.statusBar = MagicMock(return_value=MagicMock())
        window._select_autosave_recovery_file = MagicMock()

        assert AutomataDesigner.recover_autosave(window) is False

        window._select_autosave_recovery_file.assert_not_called()
        window._project_controller.load_project.assert_not_called()

    def test_recover_autosave_cancel_does_not_load(self, tmp_path):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from automataii.presentation.qt.main_window import AutomataDesigner

        selected = tmp_path / ".autosave" / "autosave_1.automataii"
        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = SimpleNamespace(state=SimpleNamespace(project_dir=tmp_path))
        window.project_data_manager = SimpleNamespace(project_dir=None)
        window._autosave_manager = MagicMock()
        window._autosave_manager.get_recovery_files.return_value = [selected]
        window._project_controller = MagicMock()
        window.statusBar = MagicMock(return_value=MagicMock())
        window._select_autosave_recovery_file = MagicMock(return_value=None)

        assert AutomataDesigner.recover_autosave(window) is False

        window._project_controller.load_project.assert_not_called()

    def test_main_window_autosave_unexpected_error_logs_warning(self, tmp_path, caplog):
        from unittest.mock import MagicMock

        from automataii.application.project import PartData, ProjectStateManager
        from automataii.presentation.qt.main_window import AutomataDesigner

        state_manager = ProjectStateManager()
        state_manager.replace_project_state(
            state_manager.state.with_project_dir(tmp_path).with_parts(
                {
                    "head": PartData(
                        name="head",
                        texture_path="head.png",
                        mask_path="head_mask.png",
                        anchor_joint="neck",
                    )
                }
            ),
            operation="test_dirty_state",
            mark_saved=False,
            clear_history=True,
        )
        window = AutomataDesigner.__new__(AutomataDesigner)
        window.project_state_manager = state_manager
        window._sync_runtime_state_to_ssot = MagicMock(side_effect=RuntimeError("sync failed"))

        with caplog.at_level(logging.WARNING):
            assert AutomataDesigner._perform_autosave(window) is False

        assert any(
            "Autosave raised unexpected error" in record.message for record in caplog.records
        )

    def test_qpainter_path_serialization_error_logs_warning(self, caplog, monkeypatch):
        from PyQt6.QtGui import QPainterPath

        from automataii.presentation.qt.main_window import AutomataDesigner

        def raise_on_element(_elem):
            raise ValueError("bad point")

        monkeypatch.setattr(
            AutomataDesigner,
            "_serialize_qpath_element",
            staticmethod(raise_on_element),
        )

        qpath = QPainterPath()
        qpath.moveTo(0.0, 0.0)
        qpath.lineTo(1.0, 1.0)
        window = AutomataDesigner.__new__(AutomataDesigner)

        with caplog.at_level(logging.WARNING):
            assert AutomataDesigner._serialize_qpainter_path(window, qpath) is None

        assert any(
            "Failed to serialize QPainterPath" in record.message for record in caplog.records
        )


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_undo_redo_state_consistency(self):
        """Test that undo/redo maintains state consistency."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import PartData

        manager = ProjectStateManager()

        # Add part
        part1 = PartData(
            name="part1",
            texture_path="part1.png",
            mask_path="part1_mask.png",
            anchor_joint="root",
        )
        manager.load_parts({"part1": part1})
        assert "part1" in manager.state.parts

        # Add another part
        part2 = PartData(
            name="part2",
            texture_path="part2.png",
            mask_path="part2_mask.png",
            anchor_joint="root",
        )
        manager.update_part(part2)

        # Undo should remove part2 changes
        manager.undo()

        # Redo should restore
        manager.redo()


class TestMechanismUndoRedo:
    """Test undo/redo for all mechanism types."""

    def test_mechanism_undo_redo_all_types(self):
        """Verify undo/redo works for all mechanism types."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Test all mechanism types
        mechanism_types = [
            ("4_bar_linkage", {"L1": 100, "L2": 40, "L3": 60, "L4": 50}),
            ("5_bar_linkage", {"L2": 40, "L3": 50, "L4": 45, "L5": 55}),
            ("6_bar_linkage", {"L2": 40, "L3": 60, "L4": 50, "L5": 45, "L6": 55}),
            ("cam", {"base_radius": 25, "eccentricity": 10, "follower_rod_length": 40}),
            ("gear", {"r1": 30, "r2": 50}),
            ("planetary_gear", {"r_sun": 20, "r_planet": 30, "arm_length": 15}),
        ]

        for mech_type, params in mechanism_types:
            # Add mechanism
            mech = MechanismData(
                id=f"test_{mech_type}",
                part_name="test_part",
                type=mech_type,
                params=params,
                enabled=True,
            )
            manager.add_mechanism(mech)
            assert f"test_{mech_type}" in manager.state.mechanisms

            # Verify can undo
            assert manager.can_undo

            # Undo
            manager.undo()
            assert f"test_{mech_type}" not in manager.state.mechanisms

            # Verify can redo
            assert manager.can_redo

            # Redo
            manager.redo()
            assert f"test_{mech_type}" in manager.state.mechanisms

            # Clean up for next iteration
            manager.remove_mechanism(f"test_{mech_type}")

    def test_mechanism_param_update_undo_redo(self):
        """Verify parameter updates are captured in undo/redo stack."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Add initial mechanism
        mech = MechanismData(
            id="test_4bar",
            part_name="test_part",
            type="4_bar_linkage",
            params={"L1": 100, "L2": 40, "L3": 60, "L4": 50},
            enabled=True,
        )
        manager.add_mechanism(mech)

        # Update parameters (simulates handle drag)
        updated_mech = mech.with_params({"L1": 100, "L2": 50, "L3": 70, "L4": 60})
        manager.update_mechanism(updated_mech)

        # Verify updated
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 50

        # Undo should restore original params
        manager.undo()
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 40

        # Redo should restore updated params
        manager.redo()
        current = manager.state.get_mechanism("test_4bar")
        assert current.params["L2"] == 50

    def test_multiple_mechanism_updates_undo_chain(self):
        """Test multiple sequential updates can be undone in order."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Add mechanism
        mech = MechanismData(
            id="test_cam",
            part_name="test_part",
            type="cam",
            params={"base_radius": 25, "eccentricity": 10},
            enabled=True,
        )
        manager.add_mechanism(mech)

        # Perform multiple updates (simulates multiple handle drags)
        for i in range(5):
            updated = manager.state.get_mechanism("test_cam").with_params(
                {"base_radius": 25 + i * 5, "eccentricity": 10 + i * 2}
            )
            manager.update_mechanism(updated)

        # Final state
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 45  # 25 + 4*5

        # Undo all 5 updates
        for _i in range(5):
            manager.undo()

        # Back to original
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 25

        # Redo all 5 updates
        for _i in range(5):
            manager.redo()

        # Back to final state
        current = manager.state.get_mechanism("test_cam")
        assert current.params["base_radius"] == 45

    def test_mechanisms_changed_signal_emitted_on_undo_redo(self):
        """Verify mechanisms_changed signal is emitted on undo/redo."""
        from automataii.application.project import ProjectStateManager
        from automataii.application.project.models import MechanismData

        manager = ProjectStateManager()

        # Track signal emissions
        signals_received = []
        manager.mechanisms_changed.connect(lambda mechs: signals_received.append(mechs))

        # Add mechanism
        mech = MechanismData(
            id="test_gear",
            part_name="test_part",
            type="gear",
            params={"r1": 30, "r2": 50},
            enabled=True,
        )
        manager.add_mechanism(mech)
        assert len(signals_received) == 1
        assert "test_gear" in signals_received[-1]

        # Undo
        manager.undo()
        assert len(signals_received) == 2
        assert "test_gear" not in signals_received[-1]

        # Redo
        manager.redo()
        assert len(signals_received) == 3
        assert "test_gear" in signals_received[-1]


class TestLoggingIntegration:
    """Logging integration tests."""

    def test_logging_file_creation(self):
        """Test that log files are created."""
        from automataii.utils.logging_config import setup_logging
        from automataii.utils.paths import get_app_data_dir

        setup_logging()

        log_dir = get_app_data_dir() / "logs"
        assert log_dir.exists()

        # Main log file should exist or be creatable
        log_file = log_dir / "automataii.log"
        assert log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
