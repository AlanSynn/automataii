# src/automataii/ui/tabs/options/state_manager.py

import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class OptionsStateManager(QObject):
    """
    Manages state for the Options tab.
    Handles all configuration settings as a single source of truth.
    """

    # Signals
    state_changed = pyqtSignal()
    theme_changed = pyqtSignal(str)
    animation_duration_changed = pyqtSignal(float)
    toolbar_visibility_changed = pyqtSignal(bool)
    part_properties_visibility_changed = pyqtSignal(bool)
    debug_mode_changed = pyqtSignal(bool)
    setting_changed = pyqtSignal(str, object)
    advanced_processing_visibility_changed = pyqtSignal(bool)
    unit_changed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Appearance settings
        self.theme: str = "Light"
        self.toolbar_visible: bool = False
        self.part_properties_visible: bool = False

        # Simulation settings
        self.animation_duration: float = 2.0

        # Debug settings
        self.debug_mode: bool = False

        # Workflow settings
        self.advanced_processing_visible: bool = False

        # Unit settings
        self.unit_system: str = "cm"

    def set_theme(self, theme: str) -> None:
        """Set the application theme."""
        if self.theme != theme:
            self.theme = theme
            self.theme_changed.emit(theme)
            self.setting_changed.emit("theme", theme)
            self.state_changed.emit()
            logger.info(f"Theme set to: {theme}")

    def set_animation_duration(self, duration: float) -> None:
        """Set the animation duration."""
        if self.animation_duration != duration:
            self.animation_duration = duration
            self.animation_duration_changed.emit(duration)
            self.setting_changed.emit("animation_duration", duration)
            self.state_changed.emit()
            logger.info(f"Animation duration set to: {duration}")

    def set_toolbar_visibility(self, visible: bool) -> None:
        """Set toolbar visibility."""
        if self.toolbar_visible != visible:
            self.toolbar_visible = visible
            self.toolbar_visibility_changed.emit(visible)
            self.setting_changed.emit("toolbar_visibility", visible)
            self.state_changed.emit()
            logger.info(f"Toolbar visibility set to: {visible}")

    def set_part_properties_visibility(self, visible: bool) -> None:
        """Set part properties panel visibility."""
        if self.part_properties_visible != visible:
            self.part_properties_visible = visible
            self.part_properties_visibility_changed.emit(visible)
            self.setting_changed.emit("part_properties_visibility", visible)
            self.state_changed.emit()
            logger.info(f"Part properties visibility set to: {visible}")

    def set_debug_mode(self, enabled: bool) -> None:
        """Set debug mode."""
        if self.debug_mode != enabled:
            self.debug_mode = enabled
            self.debug_mode_changed.emit(enabled)
            self.setting_changed.emit("debug_mode", enabled)
            self.state_changed.emit()
            logger.info(f"Debug mode set to: {enabled}")

    def set_advanced_processing_visibility(self, visible: bool) -> None:
        """Set advanced processing steps visibility."""
        if self.advanced_processing_visible != visible:
            self.advanced_processing_visible = visible
            self.advanced_processing_visibility_changed.emit(visible)
            self.setting_changed.emit("detailed_processing_visibility", visible)
            self.state_changed.emit()
            logger.info(f"Advanced processing visibility set to: {visible}")

    def set_unit_system(self, unit: str) -> None:
        """Set the unit system."""
        if self.unit_system != unit:
            self.unit_system = unit
            self.unit_changed.emit(unit)
            self.setting_changed.emit("unit_system", unit)
            self.state_changed.emit()
            logger.info(f"Unit system set to: {unit}")

    def get_animation_duration(self) -> float:
        """Get the current animation duration."""
        return self.animation_duration

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        self.theme = "Light"
        self.toolbar_visible = False
        self.part_properties_visible = False
        self.animation_duration = 2.0
        self.debug_mode = False
        self.advanced_processing_visible = False
        self.unit_system = "cm"
        self.state_changed.emit()
        logger.info("Settings reset to defaults")

    def get_current_state(self) -> dict:
        """Get the current state as a dictionary."""
        return {
            "theme": self.theme,
            "toolbar_visible": self.toolbar_visible,
            "part_properties_visible": self.part_properties_visible,
            "animation_duration": self.animation_duration,
            "debug_mode": self.debug_mode,
            "advanced_processing_visible": self.advanced_processing_visible,
            "unit_system": self.unit_system,
        }

    def load_state(self, state: dict) -> None:
        """Load state from a dictionary."""
        self.theme = state.get("theme", "Light")
        self.toolbar_visible = state.get("toolbar_visible", False)
        self.part_properties_visible = state.get("part_properties_visible", False)
        self.animation_duration = state.get("animation_duration", 2.0)
        self.debug_mode = state.get("debug_mode", False)
        self.advanced_processing_visible = state.get("advanced_processing_visible", False)
        self.unit_system = state.get("unit_system", "cm")
        self.state_changed.emit()
        logger.info("State loaded from dictionary")
