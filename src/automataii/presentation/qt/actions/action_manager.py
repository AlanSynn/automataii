"""
ActionManager module for centralizing QAction management.
"""

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, QSize
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import QStyle


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
        self.parent = parent
        self.actions: dict[str, QAction] = {}
        self.updater = None
        self._initialize_actions()

    def _initialize_actions(self):
        """Initialize all application actions with their default properties."""
        # File actions
        self.create_action(
            action_id="load_parts",
            text="&Load Character Parts...",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton),
            tooltip="Load character parts from a file",
            shortcut=QKeySequence("Ctrl+O"),
            status_tip="Load character parts from a file",
        )

        self.create_action(
            action_id="save_project",
            text="&Save Project...",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton),
            tooltip="Save the current project",
            shortcut=QKeySequence("Ctrl+S"),
            status_tip="Save the current project",
        )

        self.create_action(
            action_id="exit",
            text="E&xit",
            tooltip="Exit the application",
            shortcut=QKeySequence("Ctrl+Q"),
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

        # Edit actions
        self.create_action(
            action_id="undo",
            text="&Undo",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowLeft),
            tooltip="Undo last action",
            shortcut=QKeySequence("Ctrl+Z"),
            status_tip="Undo the last action",
            enabled=False,  # Initially disabled
        )

        self.create_action(
            action_id="redo",
            text="&Redo",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowRight),
            tooltip="Redo last undone action",
            shortcut=QKeySequence("Ctrl+Y"),
            status_tip="Redo the last undone action",
            enabled=False,  # Initially disabled
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
            text="Export",
            icon=self._get_standard_icon(QStyle.StandardPixmap.SP_ArrowRight),
            tooltip="Export the current project",
            status_tip="Export the current project",
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

        action = QAction(text, self.parent)

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
        if enabled:
            action.setEnabled(True)

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
        return self.parent.style().standardIcon(standard_pixmap)

    def setup_toolbar(self, toolbar, icon_size: QSize | None = None):
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
        toolbar.addAction(self.get_action("export"))

    def setup_menus(self, menubar):
        """
        Set up the application menus with the appropriate actions.

        Args:
            menubar: The menu bar to set up
        """
        # Clear existing menus
        menubar.clear()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.get_action("new_project"))
        file_menu.addAction(self.get_action("load_parts"))
        file_menu.addAction(self.get_action("save_project"))
        file_menu.addSeparator()
        file_menu.addAction(self.get_action("export"))
        file_menu.addSeparator()
        file_menu.addAction(self.get_action("exit"))

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.get_action("zoom_in"))
        view_menu.addAction(self.get_action("zoom_out"))
        view_menu.addAction(self.get_action("zoom_fit"))
        view_menu.addAction(self.get_action("reset_view"))

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.get_action("undo"))
        edit_menu.addAction(self.get_action("redo"))

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.get_action("check_updates"))
        help_menu.addSeparator()
        help_menu.addAction(self.get_action("about"))

        # Initially disable project-specific actions
        self.update_actions_for_project_state(False)

    def update_actions_for_project_state(self, project_loaded: bool):
        """
        Enables or disables actions based on whether a project is loaded.

        Args:
            project_loaded: True if a project is loaded, False otherwise.
        """
        project_dependent_actions = [
            "save_project",
            "export",
            # Add other action IDs here that depend on a project being loaded
            # e.g., "add_part", "define_mechanism", etc.
        ]

        for action_id in project_dependent_actions:
            self.set_action_enabled(action_id, project_loaded)

    def set_updater(self, updater):
        """Set the auto-updater and connect the update action"""
        self.updater = updater

        # Connect the check_updates action to the main window's check method
        if hasattr(self.parent, 'check_for_updates'):
            self.connect_action("check_updates", self.parent.check_for_updates)
