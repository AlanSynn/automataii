# src/automataii/ui/tabs/options/action_handler.py

import logging

from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)


class OptionsActionHandler(QObject):
    """
    Handles all business logic and user actions for the Options tab.
    Translates UI interactions into state changes.
    """

    def __init__(self, state_manager, parent: QObject | None = None):
        super().__init__(parent)
        self.state = state_manager

    def handle_theme_changed(self, theme: str) -> None:
        """Handle theme change from UI."""
        logger.info(f"Theme changed to: {theme}")
        self.state.set_theme(theme)

    def handle_animation_duration_changed(self, duration: float) -> None:
        """Handle animation duration change from UI."""
        logger.info(f"Animation duration changed to: {duration}")
        self.state.set_animation_duration(duration)

    def handle_toolbar_visibility_changed(self, visible: bool) -> None:
        """Handle toolbar visibility change from UI."""
        logger.info(f"Toolbar visibility changed to: {visible}")
        self.state.set_toolbar_visibility(visible)

    def handle_part_properties_visibility_changed(self, visible: bool) -> None:
        """Handle part properties visibility change from UI."""
        logger.info(f"Part properties visibility changed to: {visible}")
        self.state.set_part_properties_visibility(visible)

    def handle_debug_mode_changed(self, enabled: bool) -> None:
        """Handle debug mode change from UI."""
        logger.info(f"Debug mode changed to: {enabled}")
        self.state.set_debug_mode(enabled)

    def handle_advanced_processing_visibility_changed(self, visible: bool) -> None:
        """Handle advanced processing visibility change from UI."""
        logger.info(f"Advanced processing visibility changed to: {visible}")
        self.state.set_advanced_processing_visibility(visible)

    def handle_unit_system_changed(self, unit: str) -> None:
        """Handle unit system change from UI."""
        logger.info(f"Unit system changed to: {unit}")
        self.state.set_unit_system(unit)

    def handle_reset_to_defaults(self) -> None:
        """Handle reset to defaults action."""
        logger.info("Resetting all settings to defaults")
        self.state.reset_to_defaults()

    def handle_setting_changed(self, setting_name: str, value) -> None:
        """Handle generic setting change."""
        logger.info(f"Setting '{setting_name}' changed to: {value}")
        # This can be used for any custom settings handling if needed

    def get_current_animation_duration(self) -> float:
        """Get the current animation duration."""
        return self.state.get_animation_duration()

    def get_current_state(self) -> dict:
        """Get the current state for external access."""
        return self.state.get_current_state()

    def load_settings(self, settings: dict) -> None:
        """Load settings from external source."""
        logger.info("Loading settings from external source")
        self.state.load_state(settings)

    def save_pending_changes(self) -> None:
        """Save any pending changes when tab is deactivated."""
        logger.debug("OptionsActionHandler: Saving pending changes")
        # Save current state to persistent storage
        if hasattr(self.state, 'save_to_persistent_storage'):
            self.state.save_to_persistent_storage()
        
        # Apply any pending theme changes
        if hasattr(self.state, 'apply_pending_changes'):
            self.state.apply_pending_changes()
        
        # For now, just log that save was requested
        logger.info("Options settings saved successfully")
