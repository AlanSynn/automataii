# src/automataii/ui/tabs/options/tab.py

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout

from automataii.ui.tabs.base.tab import BaseTab

from .action_handler import OptionsActionHandler
from .state_manager import OptionsStateManager
from .ui_panel import OptionsUIPanel

logger = logging.getLogger(__name__)


class OptionsTab(BaseTab):
    """
    Options tab orchestrator following the new architecture pattern.

    This class acts as the main coordinator, connecting:
    - OptionsStateManager: Manages all settings state
    - OptionsActionHandler: Handles business logic and user actions
    - OptionsUIPanel: Pure UI component for the options layout
    """

    # Signals for external communication (maintaining backwards compatibility)
    themeChanged = pyqtSignal(str)
    animationDurationChanged = pyqtSignal(float)
    toolbarVisibilityChanged = pyqtSignal(bool)
    partPropertiesVisibilityChanged = pyqtSignal(bool)
    debugModeChanged = pyqtSignal(bool)
    setting_changed = pyqtSignal(str, object)
    advancedProcessingVisibilityChanged = pyqtSignal(bool)
    unitChanged = pyqtSignal(str)

    def __init__(self, main_window, parent=None):
        super().__init__(main_window, parent)

        # Initialize components
        self.state_manager: OptionsStateManager | None = None
        self.action_handler: OptionsActionHandler | None = None
        self.ui_panel: OptionsUIPanel | None = None

        # Initialize architecture
        self._init_architecture()

    def _init_architecture(self) -> None:
        """Initialize the architecture components and connect them."""
        # Create state manager
        self.state_manager = OptionsStateManager(self)

        # Create action handler
        self.action_handler = OptionsActionHandler(self.state_manager, self)

        # Create UI panel
        self.ui_panel = OptionsUIPanel(self)

        # Set up layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui_panel)

        # Connect components
        self._connect_components()

        logger.info("OptionsTab architecture initialized")

    def _connect_components(self) -> None:
        """Connect signals between components."""
        # Connect state manager to UI updates
        self.state_manager.state_changed.connect(self._on_state_changed)

        # Connect state manager signals to external signals (backwards compatibility)
        self.state_manager.theme_changed.connect(self.themeChanged.emit)
        self.state_manager.animation_duration_changed.connect(self.animationDurationChanged.emit)
        self.state_manager.toolbar_visibility_changed.connect(self.toolbarVisibilityChanged.emit)
        self.state_manager.part_properties_visibility_changed.connect(
            self.partPropertiesVisibilityChanged.emit
        )
        self.state_manager.debug_mode_changed.connect(self.debugModeChanged.emit)
        self.state_manager.setting_changed.connect(self.setting_changed.emit)
        self.state_manager.advanced_processing_visibility_changed.connect(
            self.advancedProcessingVisibilityChanged.emit
        )
        self.state_manager.unit_changed.connect(self.unitChanged.emit)

        # Connect UI panel to action handler
        self.ui_panel.theme_changed.connect(self.action_handler.handle_theme_changed)
        self.ui_panel.animation_duration_changed.connect(
            self.action_handler.handle_animation_duration_changed
        )
        self.ui_panel.toolbar_visibility_changed.connect(
            self.action_handler.handle_toolbar_visibility_changed
        )
        self.ui_panel.part_properties_visibility_changed.connect(
            self.action_handler.handle_part_properties_visibility_changed
        )
        self.ui_panel.debug_mode_changed.connect(self.action_handler.handle_debug_mode_changed)
        self.ui_panel.advanced_processing_visibility_changed.connect(
            self.action_handler.handle_advanced_processing_visibility_changed
        )
        self.ui_panel.unit_system_changed.connect(self.action_handler.handle_unit_system_changed)

    def _on_state_changed(self) -> None:
        """Handle state changes and update UI accordingly."""
        if self.ui_panel and self.state_manager:
            self.ui_panel.update_ui_from_state(self.state_manager)

    # Backwards compatibility methods (maintaining the original API)
    def set_theme(self, theme_name: str) -> None:
        """Set the theme combo box to the given theme name."""
        if self.action_handler:
            self.action_handler.handle_theme_changed(theme_name)

    def get_animation_duration(self) -> float:
        """Return the current animation duration."""
        if self.action_handler:
            return self.action_handler.get_current_animation_duration()
        return 2.0

    def set_toolbar_visibility(self, visible: bool) -> None:
        """Set the 'Show Toolbar' checkbox state."""
        if self.action_handler:
            self.action_handler.handle_toolbar_visibility_changed(visible)

    def set_part_properties_visibility(self, visible: bool) -> None:
        """Set the 'Show Part Properties Panel' checkbox state."""
        if self.action_handler:
            self.action_handler.handle_part_properties_visibility_changed(visible)

    def activate_tab(self) -> None:
        """Called when the tab becomes active."""
        super().activate_tab()  # Call parent to apply theme styles
        logger.debug("OptionsTab activated")
        # Refresh UI state to reflect current settings
        self._on_state_changed()

        # Resume any background tasks if needed
        if self.action_handler:
            self.action_handler.resume_background_tasks()

    def deactivate_tab(self) -> None:
        """Called when the tab becomes inactive."""
        logger.debug("OptionsTab deactivated")
        # Save any pending settings changes
        if self.action_handler:
            self.action_handler.save_pending_changes()
            self.action_handler.pause_background_tasks()

        # Clear any temporary UI states
        if self.ui_panel:
            self.ui_panel.clear_temporary_states()

        # Force garbage collection for this tab's resources
        import gc

        gc.collect()

    def set_debug_mode(self, enabled: bool) -> None:
        """Set the 'Enable Debug Visuals' checkbox state."""
        if self.action_handler:
            self.action_handler.handle_debug_mode_changed(enabled)

    def set_animation_duration_input(self, duration_seconds: float) -> None:
        """Set the value of the animation duration spin box."""
        if self.action_handler:
            self.action_handler.handle_animation_duration_changed(duration_seconds)

    def get_state_manager(self) -> OptionsStateManager | None:
        """Get the state manager for external access."""
        return self.state_manager

    def get_action_handler(self) -> OptionsActionHandler | None:
        """Get the action handler for external access."""
        return self.action_handler

    def get_ui_panel(self) -> OptionsUIPanel | None:
        """Get the UI panel for external access."""
        return self.ui_panel

    def load_settings(self, settings: dict) -> None:
        """Load settings from external source."""
        if self.action_handler:
            self.action_handler.load_settings(settings)

    def get_current_settings(self) -> dict:
        """Get the current settings as a dictionary."""
        if self.action_handler:
            return self.action_handler.get_current_state()
        return {}

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        if self.action_handler:
            self.action_handler.handle_reset_to_defaults()
