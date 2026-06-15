"""
Project Controller - SSOT project operations management.

Extracted from AutomataDesigner (main_window.py) to handle project
save, load, new, undo, and redo operations using SSOT architecture.

Design Pattern: Controller (handles project lifecycle operations)
"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

if TYPE_CHECKING:
    from automataii.application.project import ProjectSerializer, ProjectState, ProjectStateManager


def get_default_project_dir() -> Path:
    """
    Get default project directory for temporary saves.

    Returns a directory in the system's temp location for storing
    projects before user explicitly saves to a custom location.

    Returns:
        Path to default project directory (created if not exists)
    """
    tmp_base = Path(tempfile.gettempdir()) / "motionsmith_projects"
    tmp_base.mkdir(parents=True, exist_ok=True)
    return tmp_base


def _safe_path_component(value: str) -> str:
    """Return a conservative filesystem component for project-scoped temp paths."""
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    safe = safe.strip("._-")
    return safe or "untitled"


def get_unsaved_project_dir(state: ProjectState) -> Path:
    """
    Return an isolated temp root for an unsaved project.

    The namespace is deterministic for a ProjectState's metadata so quick-save
    and autosave recovery do not share one global temp root across unrelated
    unsaved projects.
    """
    metadata = getattr(state, "metadata", None)
    project_name = _safe_path_component(getattr(metadata, "name", "Untitled"))
    created_at = getattr(metadata, "created_at", datetime.now())
    created_key = created_at.strftime("%Y%m%d%H%M%S%f")
    project_dir = get_default_project_dir() / "unsaved" / f"{project_name}-{created_key}"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def get_project_storage_dir(state: ProjectState) -> Path:
    """Return the stable project directory or unsaved-project temp namespace."""
    if state.project_dir:
        project_dir = Path(state.project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    return get_unsaved_project_dir(state)


class StatusBarProvider(Protocol):
    """Protocol for status bar access."""

    def showMessage(self, message: str, timeout: int = 0) -> None: ...


class ProjectController(QObject):
    """
    Manages SSOT project lifecycle operations.

    Responsibilities:
    - Create new projects with unsaved changes check
    - Save projects to file system
    - Load projects from file system
    - Undo/redo state mutations
    - Status bar updates for operations

    Time Complexity: O(n) where n = project state size for save/load
    """

    # Signals for operation results
    project_created = pyqtSignal()
    project_saved = pyqtSignal(str)  # filepath
    project_loaded = pyqtSignal(str)  # filepath
    operation_failed = pyqtSignal(str)  # error message

    def __init__(
        self,
        state_manager: ProjectStateManager,
        serializer: ProjectSerializer,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize project controller.

        Args:
            state_manager: The ProjectStateManager for state access
            serializer: The ProjectSerializer for file I/O
            parent: Parent widget for dialogs
        """
        super().__init__(parent)
        self._state_manager = state_manager
        self._serializer = serializer
        self._parent_widget = parent
        self._logger = logging.getLogger(__name__)
        self._status_bar: StatusBarProvider | None = None
        self.last_dirty_decision: str | None = None

    def set_status_bar(self, status_bar: StatusBarProvider) -> None:
        """Set the status bar for operation feedback."""
        self._status_bar = status_bar

    def new_project(self) -> bool:
        """
        Create a new project with unsaved changes check.

        Returns:
            True if new project was created, False if cancelled
        """
        if not self.confirm_save_discard_cancel(
            "You have unsaved changes. Do you want to save before creating a new project?"
        ):
            return False

        # Clear state and create new project
        self._state_manager.new_project()
        self._show_status("New project created", 3000)
        self._logger.info("New project created via SSOT")
        self.project_created.emit()
        return True

    def save_project(self, filepath: str | Path | None = None) -> bool:
        """
        Save project to file system.

        Args:
            filepath: Optional explicit path. If None, shows dialog.

        Returns:
            True if save was successful, False otherwise
        """
        state = self._state_manager.state
        if filepath is None:
            if state.project_file_path is None:
                return self.save_project_as()
            filepath = state.project_file_path
        return self._save_project_to_path(Path(filepath), update_current_path=True)

    def save_project_as(self, filepath: str | Path | None = None) -> bool:
        """
        Save project to a new user-selected path and remember it as the current project file.
        """
        state = self._state_manager.state
        if filepath is None:
            default_path = self._default_project_file_path(state)
            filepath_str, _ = QFileDialog.getSaveFileName(
                self._parent_widget,
                "Save Project As",
                str(default_path),
                "MotionSmith Project (*.automataii);;All files (*)",
            )
            if not filepath_str:
                return False
            filepath = filepath_str

        return self._save_project_to_path(Path(filepath), update_current_path=True)

    def export_project(self, filepath: str | Path | None = None) -> bool:
        """
        Export a project copy without changing the current save path or dirty state.
        """
        state = self._state_manager.state
        if filepath is None:
            default_path = self._default_project_file_path(state, suffix="_export")
            filepath_str, _ = QFileDialog.getSaveFileName(
                self._parent_widget,
                "Export Project Copy",
                str(default_path),
                "MotionSmith Project (*.automataii);;All files (*)",
            )
            if not filepath_str:
                return False
            filepath = filepath_str

        result = self._serializer.save(state, Path(filepath))
        if result.success and result.path:
            self._show_status(f"Project copy exported to {result.path}", 3000)
            self._logger.info("Project copy exported via SSOT to %s", result.path)
            return True

        QMessageBox.critical(
            self._parent_widget,
            "Export Error",
            f"Failed to export project: {result.error}",
        )
        self._logger.error("Failed to export project: %s", result.error)
        self.operation_failed.emit(str(result.error))
        return False

    def _default_project_file_path(self, state: ProjectState, suffix: str = "") -> Path:
        """Return the default file path for Save As / Export dialogs."""
        if state.project_file_path and not suffix:
            return Path(state.project_file_path)
        project_dir = get_project_storage_dir(state)
        stem = _safe_path_component(state.metadata.name)
        return project_dir / f"{stem}{suffix}.automataii"

    def _save_project_to_path(self, filepath: Path, *, update_current_path: bool) -> bool:
        """Save using serializer and optionally update the remembered current path."""
        state = self._state_manager.state
        result = self._serializer.save(state, filepath)

        if result.success:
            if result.path:
                updated_state = self._state_manager.state.with_project_dir(result.path.parent)
                if update_current_path:
                    updated_state = updated_state.with_project_file_path(result.path)
                self._state_manager.replace_project_state(
                    updated_state,
                    operation="save_project",
                    clear_history=False,
                    mark_saved=True,
                    emit_signals=True,
                    categories=set(),
                )
            else:
                self._state_manager.mark_saved()
            self._show_status(f"Project saved to {result.path}", 3000)
            self._logger.info(f"Project saved via SSOT to {result.path}")
            self.project_saved.emit(str(result.path))
            return True
        else:
            QMessageBox.critical(
                self._parent_widget,
                "Save Error",
                f"Failed to save project: {result.error}",
            )
            self._logger.error(f"Failed to save project: {result.error}")
            self.operation_failed.emit(str(result.error))
            return False

    def load_project(self, filepath: str | Path | None = None) -> bool:
        """
        Load project from file system.

        Args:
            filepath: Optional explicit path. If None, shows dialog.

        Returns:
            True if load was successful, False otherwise
        """
        if not self.confirm_save_discard_cancel(
            "You have unsaved changes. Do you want to save before loading?"
        ):
            return False

        # File dialog if no path provided
        if filepath is None:
            start_dir = str(Path.home())
            filepath_str, _ = QFileDialog.getOpenFileName(
                self._parent_widget,
                "Load Project (SSOT)",
                start_dir,
                "MotionSmith Project (*.automataii);;All files (*)",
            )

            if not filepath_str:
                return False
            filepath = Path(filepath_str)
        else:
            filepath = Path(filepath)

        # Load using serializer
        result = self._serializer.load(filepath)

        if result.success and result.state:
            path = Path(filepath)
            state = result.state.with_project_dir(path.parent).with_project_file_path(path)
            self._state_manager.replace_project_state(
                state,
                operation="load_project",
                clear_history=True,
                mark_saved=True,
                emit_signals=True,
                categories={"parts", "skeleton", "paths", "mechanisms"},
            )

            self._show_status(f"Project loaded from {filepath}", 3000)
            self._logger.info(f"Project loaded via SSOT from {filepath}")
            self.project_loaded.emit(str(filepath))
            return True
        else:
            QMessageBox.critical(
                self._parent_widget,
                "Load Error",
                f"Failed to load project: {result.error}",
            )
            self._logger.error(f"Failed to load project: {result.error}")
            self.operation_failed.emit(str(result.error))
            return False

    def quick_save(self) -> bool:
        """
        Quick save to tmp directory without dialog.

        Saves the project to the system's temp directory immediately.
        Useful for periodic auto-saves or quick saves during work.

        Returns:
            True if save was successful
        """
        state = self._state_manager.state
        project_name = state.metadata.name if state.metadata else "Untitled"

        # Generate a collision-resistant filename; quick-save can be triggered
        # repeatedly within the same second by shortcuts/autosave.
        save_dir = get_project_storage_dir(state)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename_stem = f"{project_name}_{timestamp}"
        filepath = save_dir / f"{filename_stem}.automataii"
        counter = 1
        while filepath.exists():
            filepath = save_dir / f"{filename_stem}_{counter}.automataii"
            counter += 1

        result = self._serializer.save(state, filepath)

        if result.success:
            self._show_status(f"Quick saved to {result.path}", 2000)
            self._logger.info(f"Quick save to tmp: {result.path}")
            return True
        else:
            self._logger.error(f"Quick save failed: {result.error}")
            return False

    def confirm_save_discard_cancel(self, message: str) -> bool:
        """
        Ask how to handle dirty state before destructive lifecycle actions.

        Returns True when the caller may continue, False when the action should
        be cancelled because the user chose Cancel or Save failed/cancelled.
        """
        if not self._state_manager.is_dirty:
            self.last_dirty_decision = "clean"
            return True

        reply = QMessageBox.question(
            self._parent_widget,
            "Unsaved Changes",
            message,
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            saved = self.save_project()
            self.last_dirty_decision = "save" if saved else "cancel"
            return saved
        if reply == QMessageBox.StandardButton.Discard:
            self.last_dirty_decision = "discard"
            return True
        self.last_dirty_decision = "cancel"
        return False

    def undo(self) -> bool:
        """
        Undo last state mutation.

        Returns:
            True if undo was performed
        """
        if self._state_manager.can_undo:
            self._state_manager.undo()
            self._show_status("Undo", 1000)
            return True
        return False

    def redo(self) -> bool:
        """
        Redo last undone mutation.

        Returns:
            True if redo was performed
        """
        if self._state_manager.can_redo:
            self._state_manager.redo()
            self._show_status("Redo", 1000)
            return True
        return False

    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return bool(self._state_manager.can_undo)

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return bool(self._state_manager.can_redo)

    @property
    def is_dirty(self) -> bool:
        """Check if project has unsaved changes."""
        return bool(self._state_manager.is_dirty)

    def _show_status(self, message: str, timeout: int = 0) -> None:
        """Show status message if status bar is available."""
        if self._status_bar:
            self._status_bar.showMessage(message, timeout)
