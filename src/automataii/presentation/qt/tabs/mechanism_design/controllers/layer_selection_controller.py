"""
Layer Selection Controller for MechanismDesignTab.

Extracted from god class decomposition to handle layer list selection,
part visibility toggling, and mechanism visual visibility.

Design Pattern: Controller (handles layer selection operations)
Architecture: Hexagonal - Presentation Layer
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, Qt
from PyQt6.QtGui import QPainterPath

if TYPE_CHECKING:
    from PyQt6.QtGui import QTransform
    from PyQt6.QtWidgets import QGraphicsScene, QListWidget, QListWidgetItem

    from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import PathTraceManager


class LayerSelectionController(QObject):
    """
    Controls layer selection and visibility operations for MechanismDesignTab.

    Responsibilities:
    - Handle selection changes in mechanism layers list
    - Toggle part enabled/disabled state
    - Update part visibility in scene
    - Toggle mechanism visual visibility
    - Coordinate with parametric mode for handle updates

    This controller manages the relationship between list selection and scene state.
    """

    def __init__(
        self,
        *,
        path_trace_manager: PathTraceManager,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize controller.

        Args:
            path_trace_manager: Manager for path trace visualization
            parent: Parent QObject
        """
        super().__init__(parent)
        self._path_trace_manager = path_trace_manager

        # Callbacks (injected from Tab)
        self._get_mechanism_layers_list_fn: Callable[[], QListWidget | None] | None = None
        self._get_mechanism_layers_fn: Callable[[], dict] | None = None
        self._get_path_data_fn: Callable[[], dict[str, QPainterPath]] | None = None
        self._get_part_enabled_state_fn: Callable[[], dict[str, bool]] | None = None
        self._get_current_editor_items_fn: Callable[[], dict] | None = None
        self._get_mechanism_view_fn: Callable[[], Any] | None = None
        self._get_scene_fn: Callable[[], QGraphicsScene] | None = None
        self._get_parametric_mode_enabled_fn: Callable[[], bool] | None = None
        self._get_presenter_fn: Callable[[], Any | None] | None = None
        self._get_presenter_view_model_fn: Callable[[], Any | None] | None = None

        # Action callbacks
        self._clear_animation_cache_fn: Callable[[], None] | None = None
        self._reset_skeleton_fn: Callable[[], None] | None = None
        self._update_parametric_handles_fn: Callable[[str], None] | None = None
        self._hide_parametric_handles_fn: Callable[[], None] | None = None
        self._update_mechanism_layers_list_fn: Callable[[], None] | None = None
        self._update_all_ui_states_fn: Callable[[], None] | None = None
        self._part_has_mechanism_fn: Callable[[str], bool] | None = None

        # State setters
        self._set_selected_part_name_fn: Callable[[str | None], None] | None = None
        self._set_part_enabled_state_fn: Callable[[str, bool], None] | None = None

    def configure_callbacks(
        self,
        *,
        get_mechanism_layers_list: Callable[[], QListWidget | None],
        get_mechanism_layers: Callable[[], dict],
        get_path_data: Callable[[], dict[str, QPainterPath]],
        get_part_enabled_state: Callable[[], dict[str, bool]],
        get_current_editor_items: Callable[[], dict],
        get_mechanism_view: Callable[[], Any],
        get_scene: Callable[[], QGraphicsScene],
        get_parametric_mode_enabled: Callable[[], bool],
        get_presenter: Callable[[], Any | None],
        get_presenter_view_model: Callable[[], Any | None],
        clear_animation_cache: Callable[[], None],
        reset_skeleton: Callable[[], None],
        update_parametric_handles: Callable[[str], None],
        hide_parametric_handles: Callable[[], None],
        update_mechanism_layers_list: Callable[[], None],
        update_all_ui_states: Callable[[], None],
        part_has_mechanism: Callable[[str], bool],
        set_selected_part_name: Callable[[str | None], None],
        set_part_enabled_state: Callable[[str, bool], None],
    ) -> None:
        """Configure callbacks for Tab method delegation."""
        self._get_mechanism_layers_list_fn = get_mechanism_layers_list
        self._get_mechanism_layers_fn = get_mechanism_layers
        self._get_path_data_fn = get_path_data
        self._get_part_enabled_state_fn = get_part_enabled_state
        self._get_current_editor_items_fn = get_current_editor_items
        self._get_mechanism_view_fn = get_mechanism_view
        self._get_scene_fn = get_scene
        self._get_parametric_mode_enabled_fn = get_parametric_mode_enabled
        self._get_presenter_fn = get_presenter
        self._get_presenter_view_model_fn = get_presenter_view_model
        self._clear_animation_cache_fn = clear_animation_cache
        self._reset_skeleton_fn = reset_skeleton
        self._update_parametric_handles_fn = update_parametric_handles
        self._hide_parametric_handles_fn = hide_parametric_handles
        self._update_mechanism_layers_list_fn = update_mechanism_layers_list
        self._update_all_ui_states_fn = update_all_ui_states
        self._part_has_mechanism_fn = part_has_mechanism
        self._set_selected_part_name_fn = set_selected_part_name
        self._set_part_enabled_state_fn = set_part_enabled_state

    def on_selection_changed(self) -> None:
        """
        Handle selection changes in the mechanism layers list.

        Clears animation cache, path traces, resets skeleton,
        and coordinates with parametric mode.
        """
        # Clear animation cache
        if self._clear_animation_cache_fn:
            self._clear_animation_cache_fn()

        # Clear all mechanism traces to prevent old paths from lingering
        scene = self._get_scene_fn() if self._get_scene_fn else None
        if scene:
            for mechanism_id in self._path_trace_manager.get_all_mechanism_ids():
                self._path_trace_manager.clear_trace(mechanism_id, scene)

        # Save current view transform to preserve user's view
        mechanism_view = self._get_mechanism_view_fn() if self._get_mechanism_view_fn else None
        current_view_transform: QTransform | None = None
        if mechanism_view:
            current_view_transform = mechanism_view.transform()

        # Reset skeleton
        if self._reset_skeleton_fn:
            self._reset_skeleton_fn()

        # Restore view transform
        if mechanism_view and current_view_transform:
            mechanism_view.setTransform(current_view_transform)

        # Handle selection
        layers_list = self._get_mechanism_layers_list_fn() if self._get_mechanism_layers_list_fn else None
        selected_items = layers_list.selectedItems() if layers_list else []
        is_selection_valid = bool(selected_items)
        parametric_mode = self._get_parametric_mode_enabled_fn() if self._get_parametric_mode_enabled_fn else False
        presenter = self._get_presenter_fn() if self._get_presenter_fn else None

        if is_selection_valid:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)

            if presenter:
                presenter.select_part(part_name)

            if self._set_selected_part_name_fn:
                self._set_selected_part_name_fn(part_name)

            if parametric_mode and self._update_parametric_handles_fn:
                self._update_parametric_handles_fn(part_name)
        else:
            if presenter:
                presenter.select_part(None)

            if self._set_selected_part_name_fn:
                self._set_selected_part_name_fn(None)

            if parametric_mode and self._hide_parametric_handles_fn:
                self._hide_parametric_handles_fn()

    def on_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle clicking on a layer item.

        In normal mode: Toggle part enabled/disabled state
        In parametric mode: Allow selection change without toggling state

        Args:
            item: The clicked list widget item
        """
        part_name = item.data(Qt.ItemDataRole.UserRole)
        path_data = self._get_path_data_fn() if self._get_path_data_fn else {}

        # Only process clicks on parts with motion paths
        if part_name not in path_data:
            return

        # In parametric mode, don't toggle enabled/disabled state
        parametric_mode = self._get_parametric_mode_enabled_fn() if self._get_parametric_mode_enabled_fn else False
        if parametric_mode:
            return

        # Normal mode: Toggle enabled/disabled state
        presenter_view_model = self._get_presenter_view_model_fn() if self._get_presenter_view_model_fn else None
        presenter = self._get_presenter_fn() if self._get_presenter_fn else None
        part_enabled_state = self._get_part_enabled_state_fn() if self._get_part_enabled_state_fn else {}

        if presenter_view_model and presenter:
            part_vm = presenter_view_model.find_part(part_name)
            current_state = part_vm.enabled if part_vm else True
        else:
            current_state = part_enabled_state.get(part_name, True)

        new_state = not current_state

        if presenter:
            presenter.enable_part(part_name, new_state)

        if self._set_part_enabled_state_fn:
            self._set_part_enabled_state_fn(part_name, new_state)

        self.update_part_visibility_and_animation(part_name, new_state)

        if self._update_mechanism_layers_list_fn:
            self._update_mechanism_layers_list_fn()

    def update_part_visibility_and_animation(self, part_name: str, enabled: bool) -> None:
        """
        Update part visibility and animation control based on enabled state.

        Args:
            part_name: Name of the part
            enabled: Whether the part is enabled
        """
        current_editor_items = self._get_current_editor_items_fn() if self._get_current_editor_items_fn else {}

        # Control part visibility in the scene
        if part_name in current_editor_items:
            part_item = current_editor_items[part_name]
            if hasattr(part_item, 'setVisible'):
                part_item.setVisible(enabled)

        # Control mechanism visuals if they exist
        has_mechanism = self._part_has_mechanism_fn(part_name) if self._part_has_mechanism_fn else False
        if has_mechanism:
            self.toggle_mechanism_visuals(part_name, enabled)

        # Update UI state
        if self._update_all_ui_states_fn:
            self._update_all_ui_states_fn()

    def toggle_mechanism_visuals(self, part_name: str, enabled: bool) -> None:
        """
        Toggle visibility of mechanism visuals for a specific part.

        Args:
            part_name: Name of the part
            enabled: Whether to show or hide visuals
        """
        mechanism_layers = self._get_mechanism_layers_fn() if self._get_mechanism_layers_fn else {}

        for mechanism_id, layer_data in mechanism_layers.items():
            if layer_data.get("part_name") == part_name:
                # Update visual items visibility
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setVisible'):
                        item.setVisible(enabled)

                # Update trace visibility using manager
                trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                if trace_item and hasattr(trace_item, 'setVisible'):
                    trace_item.setVisible(enabled)
