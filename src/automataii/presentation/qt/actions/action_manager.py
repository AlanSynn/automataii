"""
ActionManager module for centralizing QAction management.
"""

import logging
from collections.abc import Callable
from typing import cast

from PyQt6.QtCore import QObject, QSize
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import QMenuBar, QStyle, QToolBar, QWidget


class ActionManager(QObject):
    """
    Centralizes the creation, configuration, and management of QActions.

    This class helps reduce code duplication and improves maintainability by
    providing a single place to manage application actions.
    """

    def __init__(self, parent: QObject):
        """
        Initialize the ActionManager.

        Args:
            parent: The parent object (typically MainWindow) that will own the actions
        """
        super().__init__(parent)
        self._owner = parent
        self.actions: dict[str, QAction] = {}
        self.updater: object | None = None
        self._initialize_actions()

    def _initialize_actions(self) -> None:
        """Initialize all application actions with their default properties."""
        # File actions
        self.create_action(
            action_id="load_parts",
            text="&Load Project...",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton),
            tooltip="Load a project file",
            shortcut=QKeySequence(QKeySequence.StandardKey.Open),
            status_tip="Load a project file",
        )

        self.create_action(
            action_id="save_project",
            text="&Save Project",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton),
            tooltip="Save the current project",
            shortcut=QKeySequence(QKeySequence.StandardKey.Save),
            status_tip="Save the current project",
        )

        self.create_action(
            action_id="save_project_as",
            text="Save Project &As...",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton),
            tooltip="Save the current project to a new file",
            shortcut=QKeySequence(QKeySequence.StandardKey.SaveAs),
            status_tip="Save the current project to a new file",
        )

        self.create_action(
            action_id="recover_autosave",
            text="Recover Autosave...",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton),
            tooltip="Recover an autosaved project snapshot",
            status_tip="Recover an autosaved project snapshot",
        )

        self.create_action(
            action_id="exit",
            text="E&xit",
            tooltip="Exit the application",
            shortcut=QKeySequence(QKeySequence.StandardKey.Quit),
            status_tip="Exit the application",
        )

        # View actions
        self.create_action(
            action_id="zoom_in",
            text="Zoom &In",
            tooltip="Zoom in",
            shortcut=QKeySequence("Ctrl++"),
            status_tip="Zoom in on the view",
        )

        self.create_action(
            action_id="zoom_out",
            text="Zoom &Out",
            tooltip="Zoom out",
            shortcut=QKeySequence("Ctrl+-"),
            status_tip="Zoom out from the view",
        )

        self.create_action(
            action_id="zoom_fit",
            text="Zoom to &Fit",
            tooltip="Zoom to fit all content",
            shortcut=QKeySequence("Ctrl+0"),
            status_tip="Zoom to fit all content in view",
        )

        self.create_action(
            action_id="reset_view",
            text="&Reset View",
            tooltip="Reset the view to default",
            status_tip="Reset the view to default position and scale",
        )

        self.create_action(
            action_id="save_workspace_layout",
            text="Save Workspace Layout",
            tooltip="Persist current docks and tab order",
            status_tip="Save current workspace layout",
        )

        self.create_action(
            action_id="restore_workspace_layout",
            text="Restore Workspace Layout",
            tooltip="Restore last saved docks and tab order",
            status_tip="Restore workspace layout",
        )

        self.create_action(
            action_id="reset_workspace_layout",
            text="Reset Workspace Layout",
            tooltip="Reset workspace layout to defaults",
            status_tip="Reset workspace layout to defaults",
        )

        # Edit actions
        undo_action = self.create_action(
            action_id="undo",
            text="&Back (Undo)",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowLeft),
            tooltip="Go back: undo the last action",
            shortcut=QKeySequence(QKeySequence.StandardKey.Undo),
            status_tip="Go back by undoing the last action",
            enabled=False,  # Initially disabled
        )

        redo_action = self.create_action(
            action_id="redo",
            text="&Forward (Redo)",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowRight),
            tooltip="Go forward: redo the last undone action",
            shortcut=QKeySequence(QKeySequence.StandardKey.Redo),
            status_tip="Go forward by redoing the last undone action",
            enabled=False,  # Initially disabled
        )
        # Qt maps StandardKey.Redo to the platform default (for example
        # Cmd+Shift+Z on macOS). Keep common cross-platform fallbacks too.
        redo_action.setShortcuts(
            [
                QKeySequence(QKeySequence.StandardKey.Redo),
                QKeySequence("Ctrl+Y"),
                QKeySequence("Ctrl+Shift+Z"),
            ]
        )
        undo_action.setShortcuts([QKeySequence(QKeySequence.StandardKey.Undo)])

        # Options actions
        self.create_action(
            action_id="preferences",
            text="&Preferences...",
            tooltip="Open application options",
            shortcut=QKeySequence(QKeySequence.StandardKey.Preferences),
            status_tip="Open application options",
        )

        # Help actions
        self.create_action(
            action_id="about",
            text="&About...",
            tooltip="Show information about the application",
            status_tip="Show information about the application",
        )

        self.create_action(
            action_id="check_updates",
            text="Check for &Updates...",
            tooltip="Check for application updates",
            status_tip="Check for application updates",
        )

        # Toolbar-specific actions (placeholders)
        self.create_action(
            action_id="new_project",
            text="New",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_FileIcon),
            tooltip="Create a new project",
            status_tip="Create a new project",
        )

        self.create_action(
            action_id="export",
            text="Export Project Copy",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowRight),
            tooltip="Export a copy of the current project file",
            status_tip="Export a copy of the current project file",
        )

        self.create_action(
            action_id="export_blueprint_package",
            text="Export Blueprint Package",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DriveHDIcon),
            tooltip="Export fabrication cut sheets, kit parts, and board assembly guide",
            status_tip="Export fabrication cut sheets, kit parts, and board assembly guide",
        )

    def create_action(
        self,
        action_id: str,
        text: str,
        icon: QIcon | None = None,
        tooltip: str | None = None,
        shortcut: QKeySequence | None = None,
        status_tip: str | None = None,
        checkable: bool = False,
        checked: bool = False,
        enabled: bool = True,
    ) -> QAction:
        """
        Create a QAction and add it to the managed actions dictionary.

        Args:
            action_id: Unique identifier for the action
            text: Display text for the action
            icon: Icon for the action
            tooltip: Tooltip text
            shortcut: Keyboard shortcut
            status_tip: Text to show in the status bar
            checkable: Whether the action can be toggled
            checked: Initial checked state (if checkable)
            enabled: Whether the action is enabled

        Returns:
            The created QAction
        """
        if action_id in self.actions:
            logging.warning(f"Action '{action_id}' already exists, overwriting")

        action = QAction(text, self._owner)

        if icon:
            action.setIcon(icon)
        if tooltip:
            action.setToolTip(tooltip)
        if shortcut:
            action.setShortcut(shortcut)
        if status_tip:
            action.setStatusTip(status_tip)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled)

        self.actions[action_id] = action
        return action

    def get_action(self, action_id: str) -> QAction | None:
        """
        Get an action by its ID.

        Args:
            action_id: The unique identifier for the action

        Returns:
            The QAction object or None if not found
        """
        action = self.actions.get(action_id)
        if action is None:
            logging.warning(f"Action '{action_id}' not found")
        return action

    def connect_action(self, action_id: str, slot: Callable) -> bool:
        """
        Connect an action's triggered signal to a slot.

        Args:
            action_id: The unique identifier for the action
            slot: The slot function to connect

        Returns:
            True if connection succeeded, False otherwise
        """
        action = self.get_action(action_id)
        if action:
            action.triggered.connect(slot)
            return True
        return False

    def set_action_enabled(self, action_id: str, enabled: bool) -> bool:
        """
        Set whether an action is enabled.

        Args:
            action_id: The unique identifier for the action
            enabled: Whether the action should be enabled

        Returns:
            True if the action was found and updated, False otherwise
        """
        action = self.get_action(action_id)
        if action:
            action.setEnabled(enabled)
            return True
        return False

    def _get_standard_icon(self, standard_pixmap: QStyle.StandardPixmap) -> QIcon:
        """
        Get a standard icon from the application style.

        Args:
            standard_pixmap: The standard pixmap enum value

        Returns:
            The requested icon
        """
        style = cast(QWidget, self._owner).style()
        return style.standardIcon(standard_pixmap) if style is not None else QIcon()

    def setup_toolbar(self, toolbar: QToolBar, icon_size: QSize | None = None) -> None:
        """
        Set up the main toolbar with the appropriate actions.

        Args:
            toolbar: The toolbar to set up
            icon_size: Size for toolbar icons
        """
        if icon_size is None:
            icon_size = QSize(20, 20)

        toolbar.clear()
        toolbar.setIconSize(icon_size)

        # Add actions to toolbar
        toolbar.addAction(self.get_action("new_project"))
        toolbar.addAction(self.get_action("load_parts"))
        toolbar.addAction(self.get_action("save_project"))
        toolbar.addAction(self.get_action("export_blueprint_package"))
        toolbar.addAction(self.get_action("export"))

    def setup_menus(self, menubar: QMenuBar) -> None:
        """
        Set up the application menus with the appropriate actions.

        Args:
            menubar: The menu bar to set up
        """
        # Clear existing menus
        menubar.clear()

        # File menu
        file_menu = menubar.addMenu("&File")
        assert file_menu is not None
        file_menu.addAction(self.get_action("new_project"))
        file_menu.addAction(self.get_action("load_parts"))
        file_menu.addAction(self.get_action("recover_autosave"))
        file_menu.addAction(self.get_action("save_project"))
        file_menu.addAction(self.get_action("save_project_as"))
        file_menu.addSeparator()
        file_menu.addAction(self.get_action("export_blueprint_package"))
        file_menu.addAction(self.get_action("export"))
        file_menu.addSeparator()
        file_menu.addAction(self.get_action("exit"))

        # View menu
        view_menu = menubar.addMenu("&View")
        assert view_menu is not None
        view_menu.addAction(self.get_action("zoom_in"))
        view_menu.addAction(self.get_action("zoom_out"))
        view_menu.addAction(self.get_action("zoom_fit"))
        view_menu.addAction(self.get_action("reset_view"))
        view_menu.addSeparator()
        view_menu.addAction(self.get_action("save_workspace_layout"))
        view_menu.addAction(self.get_action("restore_workspace_layout"))
        view_menu.addAction(self.get_action("reset_workspace_layout"))

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        assert edit_menu is not None
        edit_menu.addAction(self.get_action("undo"))
        edit_menu.addAction(self.get_action("redo"))

        # Options menu
        options_menu = menubar.addMenu("&Options")
        assert options_menu is not None
        options_menu.addAction(self.get_action("preferences"))

        # Help menu
        help_menu = menubar.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self.get_action("check_updates"))
        help_menu.addSeparator()
        help_menu.addAction(self.get_action("about"))

        # Initially disable project-specific actions
        self.update_actions_for_project_state(False)

    def update_actions_for_project_state(self, project_loaded: bool) -> None:
        """
        Enables or disables actions based on whether a project is loaded.

        Args:
            project_loaded: True if a project is loaded, False otherwise.
        """
        project_dependent_actions = [
            "save_project",
            "export",
            "export_blueprint_package",
            # Add other action IDs here that depend on a project being loaded
            # e.g., "add_part", "define_mechanism", etc.
        ]

        for action_id in project_dependent_actions:
            self.set_action_enabled(action_id, project_loaded)

    def set_updater(self, updater: object) -> None:
        """Set the auto-updater and keep the update action safe."""
        self.updater = updater
        self.set_action_enabled("check_updates", True)
