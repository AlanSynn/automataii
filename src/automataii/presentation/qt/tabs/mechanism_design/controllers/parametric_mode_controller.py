"""
Parametric Mode Controller for MechanismDesignTab.

Extracted from god class decomposition to handle parametric editing mode
toggle and handle visibility management.

Design Pattern: Controller (handles parametric mode operations)
Architecture: Hexagonal - Presentation Layer
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager
    from automataii.presentation.qt.parametric_editor import ParametricEditor


class ParametricModeController(QObject):
    """
    Controls parametric editing mode operations for MechanismDesignTab.

    Responsibilities:
    - Toggle parametric mode on/off
    - Coordinate with ParametricEditingManager
    - Update parametric handles based on selection
    - Hide handles when no selection

    This controller manages the parametric editing UI state.
    """

    def __init__(
        self,
        *,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize controller.

        Args:
            parent: Parent QObject
        """
        super().__init__(parent)

        # State
        self._parametric_mode_enabled: bool = False

        # Callbacks (injected from Tab)
        self._get_parametric_manager_fn: Callable[[], "ParametricEditingManager | None"] | None = None
        self._get_parametric_editor_fn: Callable[[], "ParametricEditor | None"] | None = None
        self._get_mechanism_layers_fn: Callable[[], dict] | None = None
        self._get_presenter_fn: Callable[[], Any | None] | None = None

        # Action callbacks
        self._update_all_ui_states_fn: Callable[[], None] | None = None
        self._set_selected_part_name_fn: Callable[[str | None], None] | None = None

    def configure_callbacks(
        self,
        *,
        get_parametric_manager: Callable[[], "ParametricEditingManager | None"],
        get_parametric_editor: Callable[[], "ParametricEditor | None"],
        get_mechanism_layers: Callable[[], dict],
        get_presenter: Callable[[], Any | None],
        update_all_ui_states: Callable[[], None],
        set_selected_part_name: Callable[[str | None], None],
    ) -> None:
        """Configure callbacks for Tab method delegation."""
        self._get_parametric_manager_fn = get_parametric_manager
        self._get_parametric_editor_fn = get_parametric_editor
        self._get_mechanism_layers_fn = get_mechanism_layers
        self._get_presenter_fn = get_presenter
        self._update_all_ui_states_fn = update_all_ui_states
        self._set_selected_part_name_fn = set_selected_part_name

    @property
    def is_enabled(self) -> bool:
        """Check if parametric mode is currently enabled."""
        return self._parametric_mode_enabled

    def toggle_mode(self, enabled: bool | None = None) -> bool:
        """
        Toggle parametric editing mode on/off.

        Args:
            enabled: Explicit enable state, or None to toggle

        Returns:
            New enabled state after toggle
        """
        parametric_manager = self._get_parametric_manager_fn() if self._get_parametric_manager_fn else None

        if parametric_manager:
            parametric_manager.toggle_parametric_mode(enabled)
            self._parametric_mode_enabled = parametric_manager.parametric_mode_enabled
        else:
            # Fallback: simple toggle
            if enabled is None:
                self._parametric_mode_enabled = not self._parametric_mode_enabled
            else:
                self._parametric_mode_enabled = enabled

        # Notify presenter
        presenter = self._get_presenter_fn() if self._get_presenter_fn else None
        if presenter:
            presenter.set_parametric_mode(self._parametric_mode_enabled)

        # Update UI
        if self._update_all_ui_states_fn:
            self._update_all_ui_states_fn()

        return self._parametric_mode_enabled

    def update_handles_for_selection(self, part_name: str) -> None:
        """
        Update parametric handles for selected part.

        Args:
            part_name: Name of the selected part
        """
        if not self._parametric_mode_enabled:
            return

        parametric_editor = self._get_parametric_editor_fn() if self._get_parametric_editor_fn else None
        if not parametric_editor:
            return

        mechanism_layers = self._get_mechanism_layers_fn() if self._get_mechanism_layers_fn else {}

        # Find first mechanism for this part
        mech_id = next(
            (mid for mid, ld in mechanism_layers.items() if ld.get("part_name") == part_name),
            None
        )

        if mech_id:
            if self._set_selected_part_name_fn:
                self._set_selected_part_name_fn(part_name)
            parametric_editor.set_active_editor(mech_id)
        else:
            parametric_editor.set_active_editor(None)

    def hide_all_handles(self) -> None:
        """
        Hide all parametric handles when no part is selected.

        Delegates to ParametricEditor.set_active_editor(None).
        """
        parametric_editor = self._get_parametric_editor_fn() if self._get_parametric_editor_fn else None
        if parametric_editor:
            parametric_editor.set_active_editor(None)

    def sync_mode_state(self, external_enabled: bool) -> None:
        """
        Synchronize internal mode state with external state.

        Used when Tab's parametric_mode_enabled is set externally.

        Args:
            external_enabled: The external enabled state to sync
        """
        self._parametric_mode_enabled = external_enabled
