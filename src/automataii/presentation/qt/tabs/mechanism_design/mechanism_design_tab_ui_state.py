"""
UI State Manager for MechanismDesignTab.

Manages button enablement, tooltip updates, and visual state synchronization
based on business logic state changes.

ULTRATHINK Architecture: Clear separation between UI state and business logic.
"""

from dataclasses import dataclass


@dataclass
class UIState:
    """Data class representing the current UI state."""
    has_paths: bool = False
    has_mechanisms: bool = False
    has_enabled_parts: bool = False
    animation_running: bool = False
    parametric_mode: bool = False
    has_parts_data: bool = False


@dataclass
class AnimationState:
    """Data class representing animation control state."""
    can_play: bool = False
    can_stop: bool = False
    can_reset: bool = False
    is_running: bool = False


class MechanismDesignTabUIState:
    """
    Manages UI state synchronization for MechanismDesignTab.

    Responsibilities:
    - Button enablement based on business state
    - Tooltip updates
    - Visual feedback coordination
    - Parametric mode UI changes

    Does NOT handle:
    - Business logic
    - Event handling
    - Widget creation
    - Layout management
    """

    def __init__(self, widgets: dict):
        """
        Initialize the UI state manager.

        Args:
            widgets: Dictionary of UI widgets to manage
        """
        self.widgets = widgets
        self._current_state = UIState()
        self._animation_state = AnimationState()

    def update_button_states(self, state: UIState) -> None:
        """
        Update all button states based on current business logic state.

        Args:
            state: Current UI state containing flags for different conditions
        """
        self._current_state = state

        self._update_recommendation_button()
        self._update_parametric_button()
        self._update_blueprint_button()
        self._update_animation_buttons()

    def set_parametric_mode(self, enabled: bool) -> None:
        """
        Update UI for parametric mode changes.

        Args:
            enabled: Whether parametric mode is enabled
        """
        self._current_state.parametric_mode = enabled

        parametric_btn = self.widgets.get('parametric_edit_btn')
        if parametric_btn:
            if enabled:
                parametric_btn.setText("Exit Parametric Mode")
                parametric_btn.setStyleSheet(self._get_exit_parametric_style())
            else:
                parametric_btn.setText("Enter Parametric Mode")
                parametric_btn.setStyleSheet(self._get_enter_parametric_style())

        # Show/hide parametric-specific buttons
        self._update_parametric_specific_buttons(enabled)

        # Update animation controls (disabled during parametric mode)
        self._update_animation_controls_for_parametric(enabled)

    def set_animation_state(self, animation_state: AnimationState) -> None:
        """
        Update animation control states.

        Args:
            animation_state: Current animation state
        """
        self._animation_state = animation_state

        play_btn = self.widgets.get('play_btn')
        stop_btn = self.widgets.get('stop_btn')
        reset_btn = self.widgets.get('reset_btn')

        if play_btn:
            play_btn.setEnabled(animation_state.can_play)

        if stop_btn:
            stop_btn.setEnabled(animation_state.can_stop)

        if reset_btn:
            reset_btn.setEnabled(animation_state.can_reset)

    def update_part_enabled_tooltip(self, part_name: str, enabled: bool, has_path: bool) -> None:
        """
        Update tooltip for a specific part based on its state.

        Args:
            part_name: Name of the part
            enabled: Whether the part is enabled
            has_path: Whether the part has a motion path
        """
        # This would be used by the parts list management
        # Implementation depends on how parts list is structured
        pass

    def get_current_state(self) -> UIState:
        """Get the current UI state."""
        return self._current_state

    def get_animation_state(self) -> AnimationState:
        """Get the current animation state."""
        return self._animation_state

    # =================== PRIVATE METHODS ===================

    def _update_recommendation_button(self) -> None:
        """Update recommendation button state."""
        recommendation_btn = self.widgets.get('recommendation_btn')
        if not recommendation_btn:
            return

        recommendation_btn.setEnabled(self._current_state.has_paths)

        if self._current_state.has_paths:
            recommendation_btn.setToolTip("Generate mechanisms for motion paths")
        else:
            recommendation_btn.setToolTip("No motion paths available - draw paths in Editor tab first")

    def _update_parametric_button(self) -> None:
        """Update parametric edit button state."""
        parametric_btn = self.widgets.get('parametric_edit_btn')
        if not parametric_btn:
            return

        parametric_btn.setEnabled(self._current_state.has_mechanisms)

        if self._current_state.has_mechanisms:
            parametric_btn.setToolTip("Enable interactive parameter editing with drag handles")
        else:
            parametric_btn.setToolTip("Generate mechanisms first to enable parametric editing")

    def _update_blueprint_button(self) -> None:
        """Update blueprint export button state."""
        blueprint_btn = self.widgets.get('blueprint_btn')
        if not blueprint_btn:
            return

        # Blueprint requires both mechanisms and parts data
        can_export = self._current_state.has_mechanisms and self._current_state.has_parts_data
        blueprint_btn.setEnabled(can_export)

        if can_export:
            blueprint_btn.setToolTip("Export character parts and mechanisms as SVG blueprint")
        else:
            blueprint_btn.setToolTip("Load character parts and generate mechanisms to enable export")

    def _update_animation_buttons(self) -> None:
        """Update animation control buttons."""
        # Don't update if in parametric mode
        if self._current_state.parametric_mode:
            return

        play_btn = self.widgets.get('play_btn')
        stop_btn = self.widgets.get('stop_btn')
        reset_btn = self.widgets.get('reset_btn')

        can_animate = self._current_state.has_enabled_parts and self._current_state.has_paths

        if play_btn:
            play_btn.setEnabled(can_animate and not self._current_state.animation_running)

        if stop_btn:
            stop_btn.setEnabled(self._current_state.animation_running)

        if reset_btn:
            reset_btn.setEnabled(can_animate)

    def _update_parametric_specific_buttons(self, parametric_enabled: bool) -> None:
        """Update buttons that are only visible in parametric mode."""
        pass

    def _update_animation_controls_for_parametric(self, parametric_enabled: bool) -> None:
        """Update animation controls when parametric mode changes."""
        play_btn = self.widgets.get('play_btn')
        stop_btn = self.widgets.get('stop_btn')
        reset_btn = self.widgets.get('reset_btn')

        if parametric_enabled:
            # Disable animation controls in parametric mode
            if play_btn:
                play_btn.setEnabled(False)
                play_btn.setToolTip("⚠️ Animation disabled during parametric editing")

            if stop_btn:
                stop_btn.setEnabled(False)
                stop_btn.setToolTip("⚠️ Animation disabled during parametric editing")

            if reset_btn:
                reset_btn.setEnabled(False)
                reset_btn.setToolTip("⚠️ Animation disabled during parametric editing")
        else:
            # Re-enable animation controls
            if play_btn:
                play_btn.setToolTip("▶️ Play mechanism animation")

            if stop_btn:
                stop_btn.setToolTip("⏹️ Stop mechanism animation")

            if reset_btn:
                reset_btn.setToolTip("🔄 Reset mechanism to initial state")

            # Update states based on current conditions
            self._update_animation_buttons()

    # =================== STYLING METHODS ===================

    def _get_exit_parametric_style(self) -> str:
        """Get styling for parametric exit button (red)."""
        return """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """

    def _get_enter_parametric_style(self) -> str:
        """Get styling for parametric enter button (green)."""
        return """
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """
