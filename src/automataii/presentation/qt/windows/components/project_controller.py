"""
Project Controller - SSOT project operations management.

Extracted from AutomataDesigner (main_window.py) to handle project
save, load, new, undo, and redo operations using SSOT architecture.

Design Pattern: Controller (handles project lifecycle operations)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

if TYPE_CHECKING:
    from automataii.application.project import ProjectSerializer, ProjectStateManager


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

    def set_status_bar(self, status_bar: StatusBarProvider) -> None:
        """Set the status bar for operation feedback."""
        self._status_bar = status_bar

    def new_project(self) -> bool:
        """
        Create a new project with unsaved changes check.

        Returns:
            True if new project was created, False if cancelled
        """
        # Check for unsaved changes
        if self._state_manager.is_dirty:
            reply = QMessageBox.question(
                self._parent_widget,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before creating a new project?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Save:
                if not self.save_project():
                    return False  # Save cancelled or failed
            elif reply == QMessageBox.StandardButton.Cancel:
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

        # Determine save path
        if filepath is None:
            if state.project_dir:
                default_path = state.project_dir / f"{state.metadata.name}.automataii"
            else:
                default_path = Path.home() / f"{state.metadata.name}.automataii"

            filepath_str, _ = QFileDialog.getSaveFileName(
                self._parent_widget,
                "Save Project (SSOT)",
                str(default_path),
                "Automataii Project (*.automataii);;All files (*)",
            )

            if not filepath_str:
                return False
            filepath = Path(filepath_str)
        else:
            filepath = Path(filepath)

        # Save using serializer
        result = self._serializer.save(state, filepath)

        if result.success:
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
        # Check for unsaved changes
        if self._state_manager.is_dirty:
            reply = QMessageBox.question(
                self._parent_widget,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before loading?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Save:
                if not self.save_project():
                    return False
            elif reply == QMessageBox.StandardButton.Cancel:
                return False

        # File dialog if no path provided
        if filepath is None:
            start_dir = str(Path.home())
            filepath_str, _ = QFileDialog.getOpenFileName(
                self._parent_widget,
                "Load Project (SSOT)",
                start_dir,
                "Automataii Project (*.automataii);;All files (*)",
            )

            if not filepath_str:
                return False
            filepath = Path(filepath_str)
        else:
            filepath = Path(filepath)

        # Load using serializer
        result = self._serializer.load(filepath)

        if result.success and result.state:
            # Batch load state components
            state = result.state

            self._state_manager.begin_batch()

            if state.parts:
                self._state_manager.load_parts(dict(state.parts))
            if state.skeleton:
                self._state_manager.load_skeleton(state.skeleton)
            if state.paths:
                self._state_manager.load_paths(dict(state.paths))
            if state.mechanisms:
                self._state_manager.load_mechanisms(dict(state.mechanisms))

            self._state_manager.end_batch()
            self._state_manager.mark_saved()

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
        return self._state_manager.can_undo

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._state_manager.can_redo

    @property
    def is_dirty(self) -> bool:
        """Check if project has unsaved changes."""
        return self._state_manager.is_dirty

    def _show_status(self, message: str, timeout: int = 0) -> None:
        """Show status message if status bar is available."""
        if self._status_bar:
            self._status_bar.showMessage(message, timeout)
