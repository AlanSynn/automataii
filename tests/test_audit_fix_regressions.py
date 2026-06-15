from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_project_state_file_path_is_runtime_only(tmp_path):
    from automataii.application.project import ProjectSerializer, ProjectState

    serializer = ProjectSerializer()
    path = tmp_path / "runtime_path.automataii"

    assert serializer.save(ProjectState.empty().with_project_file_path(path), path).success

    assert "project_file_path" not in path.read_text(encoding="utf-8")
    loaded = serializer.load(path)
    assert loaded.success
    assert loaded.state is not None
    assert loaded.state.project_file_path == path


def test_save_project_reuses_current_path_without_dialog(tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from automataii.application.project import ProjectSerializer, ProjectStateManager
    from automataii.presentation.qt.windows.components import ProjectController

    state_manager = ProjectStateManager()
    path = tmp_path / "remembered.automataii"
    state_manager.replace_project_state(
        state_manager.state.with_project_dir(tmp_path).with_project_file_path(path),
        mark_saved=False,
        clear_history=True,
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dialog opened")),
    )

    controller = ProjectController(state_manager, ProjectSerializer())

    assert controller.save_project()
    assert path.exists()
    assert state_manager.state.project_file_path == path
    assert not state_manager.is_dirty


def test_save_project_path_survives_undo_after_first_save(tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from automataii.application.project import ProjectSerializer, ProjectStateManager
    from automataii.presentation.qt.windows.components import ProjectController

    state_manager = ProjectStateManager()
    source_image = tmp_path / "source.png"
    source_image.write_text("image", encoding="utf-8")
    state_manager.set_image_path(source_image)

    path = tmp_path / "first-save.automataii"
    controller = ProjectController(state_manager, ProjectSerializer())

    assert controller.save_project(path)
    assert state_manager.state.project_file_path == path
    assert controller.undo()
    assert state_manager.state.project_file_path == path
    assert state_manager.state.project_dir == tmp_path
    assert controller.redo()
    assert state_manager.state.project_file_path == path
    assert controller.undo()
    assert state_manager.state.project_file_path == path

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dialog opened")),
    )
    assert controller.save_project()


def test_save_project_as_updates_remembered_path(tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from automataii.application.project import ProjectSerializer, ProjectStateManager
    from automataii.presentation.qt.windows.components import ProjectController

    target = tmp_path / "new-name.automataii"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(target), ""))

    state_manager = ProjectStateManager()
    controller = ProjectController(state_manager, ProjectSerializer())

    assert controller.save_project_as()
    assert target.exists()
    assert state_manager.state.project_file_path == target
    assert state_manager.state.project_dir == tmp_path


def test_export_project_copy_preserves_current_path_and_dirty_state(tmp_path):
    from automataii.application.project import ProjectSerializer, ProjectStateManager
    from automataii.presentation.qt.windows.components import ProjectController

    current = tmp_path / "current.automataii"
    exported = tmp_path / "copy.automataii"
    state_manager = ProjectStateManager()
    state_manager.replace_project_state(
        state_manager.state.with_project_dir(tmp_path).with_project_file_path(current),
        mark_saved=False,
        clear_history=True,
    )
    controller = ProjectController(state_manager, ProjectSerializer())

    assert controller.export_project(exported)
    assert exported.exists()
    assert state_manager.state.project_file_path == current
    assert state_manager.is_dirty


def test_main_window_export_dialog_preserves_clean_dirty_state(tmp_path):
    from automataii.application.project import ProjectStateManager
    from automataii.presentation.qt.main_window import AutomataDesigner

    state_manager = ProjectStateManager()
    state_manager.replace_project_state(
        state_manager.state.with_project_dir(tmp_path),
        mark_saved=True,
        clear_history=True,
    )
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.project_state_manager = state_manager
    window._sync_runtime_state_to_ssot = MagicMock()
    window._project_controller = MagicMock()
    window._project_controller.export_project.return_value = True
    window.statusBar = MagicMock()

    assert AutomataDesigner.export_project_dialog(window) is True
    window._sync_runtime_state_to_ssot.assert_called_once_with(mark_saved=True)
    assert not state_manager.is_dirty


def test_main_window_cancelled_save_as_restores_clean_state(tmp_path):
    from automataii.application.project import ProjectStateManager
    from automataii.presentation.qt.main_window import AutomataDesigner

    state_manager = ProjectStateManager()
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.project_state_manager = state_manager
    window._project_controller = MagicMock()
    window._project_controller.save_project_as.return_value = False
    window.statusBar = MagicMock()

    def dirtying_sync(*, mark_saved: bool) -> None:
        state_manager.replace_project_state(
            state_manager.state.with_project_dir(tmp_path),
            operation="test_sync",
            mark_saved=mark_saved,
            clear_history=False,
        )

    window._sync_runtime_state_to_ssot = dirtying_sync

    assert AutomataDesigner.save_project_as_dialog(window) is False
    assert not state_manager.is_dirty
    assert state_manager.state.project_dir is None


def test_main_window_cancelled_save_as_preserves_existing_dirty_state(tmp_path):
    from automataii.application.project import ProjectStateManager
    from automataii.presentation.qt.main_window import AutomataDesigner

    state_manager = ProjectStateManager()
    state_manager.replace_project_state(
        state_manager.state.with_project_dir(tmp_path / "previous"),
        operation="test_dirty",
        mark_saved=False,
        clear_history=True,
    )
    previous_state = state_manager.state
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.project_state_manager = state_manager
    window._project_controller = MagicMock()
    window._project_controller.save_project_as.return_value = False
    window.statusBar = MagicMock()

    def dirtying_sync(*, mark_saved: bool) -> None:
        state_manager.replace_project_state(
            state_manager.state.with_project_dir(tmp_path / "synced"),
            operation="test_sync",
            mark_saved=mark_saved,
            clear_history=False,
        )

    window._sync_runtime_state_to_ssot = dirtying_sync

    assert AutomataDesigner.save_project_as_dialog(window) is False
    assert state_manager.is_dirty
    assert state_manager.state == previous_state


def test_unsaved_project_storage_dir_is_namespaced(tmp_path, monkeypatch):
    from automataii.application.project import ProjectMetadata, ProjectState
    from automataii.presentation.qt.windows.components import (
        get_project_storage_dir,
        project_controller,
    )

    monkeypatch.setattr(project_controller.tempfile, "gettempdir", lambda: str(tmp_path))
    first = ProjectState.empty().with_metadata(
        ProjectMetadata(name="Untitled", created_at=datetime(2026, 1, 1, 0, 0, 0))
    )
    second = ProjectState.empty().with_metadata(
        ProjectMetadata(name="Untitled", created_at=datetime(2026, 1, 1, 0, 0, 1))
    )

    first_dir = get_project_storage_dir(first)
    second_dir = get_project_storage_dir(second)

    assert first_dir != second_dir
    assert first_dir.parent == second_dir.parent
    assert first_dir.parent.name == "unsaved"


def test_confirm_save_discard_cancel_cancel_blocks_action(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from automataii.application.project import ProjectSerializer, ProjectStateManager
    from automataii.presentation.qt.windows.components import ProjectController

    state_manager = ProjectStateManager()
    state_manager.replace_project_state(state_manager.state, mark_saved=False, clear_history=True)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel
    )
    controller = ProjectController(state_manager, ProjectSerializer())

    assert controller.confirm_save_discard_cancel("Save?") is False
    assert controller.last_dirty_decision == "cancel"


def test_main_window_close_confirmation_syncs_before_prompt():
    from automataii.presentation.qt.main_window import AutomataDesigner

    window = AutomataDesigner.__new__(AutomataDesigner)
    window.project_state_manager = SimpleNamespace(is_dirty=True)
    window._sync_runtime_state_to_ssot = MagicMock()
    window._project_controller = MagicMock()
    window._project_controller.confirm_save_discard_cancel.return_value = False
    status_bar = MagicMock()
    window.statusBar = MagicMock(return_value=status_bar)

    assert AutomataDesigner._confirm_close_with_unsaved_changes(window) is False
    window._sync_runtime_state_to_ssot.assert_called_once_with(mark_saved=False)
    window._project_controller.set_status_bar.assert_called_once_with(status_bar)


def test_active_zoom_dispatcher_routes_to_current_tab_view():
    from automataii.presentation.qt.main_window import AutomataDesigner

    view = MagicMock()
    current_tab = SimpleNamespace(image_proc_view=view)
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.tab_widget = SimpleNamespace(currentWidget=lambda: current_tab)
    window.statusBar = MagicMock()

    assert AutomataDesigner._invoke_active_zoom(window, "zoom_in") is True
    view.zoom_in.assert_called_once_with()


def test_active_zoom_dispatcher_supports_generic_zoom_step():
    from automataii.presentation.qt.main_window import AutomataDesigner

    view = SimpleNamespace(zoom=MagicMock())
    current_tab = SimpleNamespace(view=view)
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.tab_widget = SimpleNamespace(currentWidget=lambda: current_tab)
    window.statusBar = MagicMock()

    assert AutomataDesigner._invoke_active_zoom(window, "zoom_out") is True
    view.zoom.assert_called_once_with(-1)


def test_active_zoom_dispatcher_reports_unsupported_tab():
    from automataii.presentation.qt.main_window import AutomataDesigner

    status_bar = MagicMock()
    window = AutomataDesigner.__new__(AutomataDesigner)
    window.tab_widget = SimpleNamespace(currentWidget=lambda: SimpleNamespace())
    window.statusBar = MagicMock(return_value=status_bar)

    assert AutomataDesigner._invoke_active_zoom(window, "zoom_in") is False
    status_bar.showMessage.assert_called_once()


def test_restart_recovery_discovers_prior_unsaved_namespace(tmp_path, monkeypatch):
    from automataii.application.project import AutoSaveManager, ProjectSerializer, ProjectState
    from automataii.presentation.qt.main_window import AutomataDesigner
    from automataii.presentation.qt.windows.components import (
        get_unsaved_project_dir,
        project_controller,
    )

    monkeypatch.setattr(project_controller.tempfile, "gettempdir", lambda: str(tmp_path))
    previous_state = ProjectState.empty()
    previous_root = get_unsaved_project_dir(previous_state)
    autosave_dir = previous_root / AutoSaveManager.AUTOSAVE_DIR_NAME
    autosave_dir.mkdir(parents=True)
    snapshot = autosave_dir / "autosave_restart.automataii"
    snapshot.write_text("{}", encoding="utf-8")

    window = AutomataDesigner.__new__(AutomataDesigner)
    window.project_state_manager = SimpleNamespace(state=ProjectState.empty())
    window.project_data_manager = SimpleNamespace(project_dir=None)
    window._autosave_manager = AutoSaveManager(ProjectSerializer())

    assert AutomataDesigner._get_autosave_recovery_files(window) == [snapshot]


def test_mechanism_design_params_emit_for_non_foundry_synced_layer():
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab

    signal = MagicMock()
    tab_like = SimpleNamespace(
        _suppress_foundry_sync=False,
        mechanism_layers={"mech-1": {"foundry_synced": False, "params": {"l1": 10}}},
        mechanism_parameters_changed=SimpleNamespace(emit=signal),
    )

    MechanismDesignTab._emit_mechanism_params_changed(tab_like, "mech-1")

    signal.assert_called_once_with("mech-1", {"l1": 10})


def test_mechanism_design_adapter_creates_ssot_mechanism_from_layer_context():
    from automataii.application.project import ProjectStateManager
    from automataii.application.project.adapters.mechanism_design import MechanismDesignTabAdapter

    state_manager = ProjectStateManager()
    adapter = MechanismDesignTabAdapter(state_manager)
    adapter._tab = SimpleNamespace(
        mechanism_layers={
            "mech-1": {
                "part_name": "arm",
                "type": "4_bar_linkage",
                "params": {"l1": 10},
                "visual_items": [object()],
                "enabled": True,
            }
        }
    )

    adapter._on_mechanism_params_changed("mech-1", {"l1": 20})

    mechanism = state_manager.state.get_mechanism("mech-1")
    assert mechanism is not None
    assert mechanism.part_name == "arm"
    assert mechanism.type == "4_bar_linkage"
    assert mechanism.params["l1"] == 20
    assert "visual_items" not in mechanism.layer_data
    assert state_manager.is_dirty
    assert state_manager.can_undo


def test_foundry_view_exposes_public_zoom_methods():
    from automataii.presentation.qt.tabs.mechanism_foundry.foundry_view import MechanismFoundryView

    controller = MagicMock()
    view_like = SimpleNamespace(_viewport_controller=controller)

    MechanismFoundryView.zoom_in(view_like)
    MechanismFoundryView.zoom_out(view_like)
    MechanismFoundryView.zoom_to_fit(view_like)
    MechanismFoundryView.reset_view(view_like)

    controller.zoom_in.assert_called_once_with()
    controller.zoom_out.assert_called_once_with()
    controller.zoom_to_fit.assert_called_once_with()
    controller.reset_view.assert_called_once_with()
