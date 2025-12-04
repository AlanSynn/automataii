"""
Recommendation Controller for MechanismDesignTab.

Extracted from god class decomposition to handle mechanism recommendation
dialog flow, preview, and selection operations.

Design Pattern: Controller (handles recommendation workflow)
Architecture: Hexagonal - Presentation Layer
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from automataii.presentation.qt.tabs.mechanism_design.services import (
        MechanismInstantiationService,
        TabDataCoordinator,
    )


class RecommendationController(QObject):
    """
    Controls mechanism recommendation dialog operations for MechanismDesignTab.

    Responsibilities:
    - Show recommendation dialog
    - Handle mechanism preview selection
    - Handle recommendation selection/generation
    - Create preview visuals

    This controller manages the recommendation workflow separate from Tab.
    """

    # Mapping from display names to internal mechanism types
    MECHANISM_TYPE_MAPPING: dict[str, str] = {
        # Four-bar linkage variants
        "4-Bar Linkage": "4_bar_linkage",
        "4-bar Coupler": "4_bar_linkage",
        "Four-Bar Linkage": "4_bar_linkage",
        "Four-Bar": "4_bar_linkage",
        "3-bar Output": "4_bar_linkage",
        # Cam mechanism variants
        "Cam & Follower": "cam",
        "Cam-Follower": "cam",
        "Cam Profile": "cam",
        "Cam": "cam",
        # Gear mechanism variants
        "Gears": "gear",  # Family name from recommendation dialog
        "Gears (Simple Pair)": "gear",
        "Gear Train": "gear",
        "Gear Contact": "gear",
        "Simple Gear": "gear",
        "Planetary Gear": "planetary_gear",
    }

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

        # Preview items tracking
        self._preview_items: list = []

        # Callbacks (injected from Tab)
        self._get_path_data_fn: Callable[[], dict[str, QPainterPath]] | None = None
        self._get_part_enabled_state_fn: Callable[[], dict[str, bool]] | None = None
        self._get_selected_part_name_fn: Callable[[], str | None] | None = None
        self._get_mechanism_layers_list_fn: Callable[[], Any] | None = None
        self._get_mechanism_layers_fn: Callable[[], dict] | None = None
        self._get_scene_fn: Callable[[], Any] | None = None
        self._get_character_position_fn: Callable[[], list[float]] | None = None

        # Service references
        self._tab_data_coordinator: TabDataCoordinator | None = None
        self._instantiation_service: MechanismInstantiationService | None = None

        # Action callbacks
        self._set_selected_part_name_fn: Callable[[str], None] | None = None
        self._presenter_select_part_fn: Callable[[str], None] | None = None
        self._generate_mechanism_from_candidate_fn: Callable[[dict], None] | None = None
        self._add_mechanism_layer_fn: Callable[[str, dict], None] | None = None
        self._handle_mechanism_visuals_fn: Callable[[dict], None] | None = None
        self._create_4bar_visuals_fn: Callable[[dict], list] | None = None

    def configure_callbacks(
        self,
        *,
        get_path_data: Callable[[], dict[str, QPainterPath]],
        get_part_enabled_state: Callable[[], dict[str, bool]],
        get_selected_part_name: Callable[[], str | None],
        get_mechanism_layers_list: Callable[[], Any],
        get_mechanism_layers: Callable[[], dict],
        get_scene: Callable[[], Any],
        get_character_position: Callable[[], list[float]],
        tab_data_coordinator: TabDataCoordinator,
        instantiation_service: MechanismInstantiationService,
        set_selected_part_name: Callable[[str], None],
        presenter_select_part: Callable[[str], None] | None,
        generate_mechanism_from_candidate: Callable[[dict], None],
        add_mechanism_layer: Callable[[str, dict], None],
        handle_mechanism_visuals: Callable[[dict], None],
        create_4bar_visuals: Callable[[dict], list] | None = None,
    ) -> None:
        """Configure callbacks for Tab method delegation."""
        self._get_path_data_fn = get_path_data
        self._get_part_enabled_state_fn = get_part_enabled_state
        self._get_selected_part_name_fn = get_selected_part_name
        self._get_mechanism_layers_list_fn = get_mechanism_layers_list
        self._get_mechanism_layers_fn = get_mechanism_layers
        self._get_scene_fn = get_scene
        self._get_character_position_fn = get_character_position

        self._tab_data_coordinator = tab_data_coordinator
        self._instantiation_service = instantiation_service

        self._set_selected_part_name_fn = set_selected_part_name
        self._presenter_select_part_fn = presenter_select_part
        self._generate_mechanism_from_candidate_fn = generate_mechanism_from_candidate
        self._add_mechanism_layer_fn = add_mechanism_layer
        self._handle_mechanism_visuals_fn = handle_mechanism_visuals
        self._create_4bar_visuals_fn = create_4bar_visuals

    def show_recommendations(self, parent_widget: QWidget) -> None:
        """
        Show mechanism recommendation dialog.

        Args:
            parent_widget: Parent widget for dialogs
        """
        if not self._tab_data_coordinator:
            return

        path_data = self._get_path_data_fn() if self._get_path_data_fn else {}
        part_enabled_state = self._get_part_enabled_state_fn() if self._get_part_enabled_state_fn else {}

        enabled_parts = self._tab_data_coordinator.get_enabled_parts_with_paths(
            path_data, part_enabled_state
        )
        if not enabled_parts:
            QMessageBox.warning(parent_widget, "Warning", "No enabled parts with motion paths available.")
            return

        selected_part_name = self._get_selected_part_name_fn() if self._get_selected_part_name_fn else None
        mechanism_layers_list = self._get_mechanism_layers_list_fn() if self._get_mechanism_layers_list_fn else None

        target_part_name = self._tab_data_coordinator.resolve_target_part(
            enabled_parts, selected_part_name, mechanism_layers_list
        )

        # If multiple parts and no resolution, show selection dialog
        if not target_part_name and len(enabled_parts) > 1:
            selected_part, ok = QInputDialog.getItem(
                parent_widget, "Select Part", "Select which enabled part to generate mechanism for:",
                list(enabled_parts.keys()), 0, False
            )
            if not ok:
                return
            target_part_name = selected_part

        if not target_part_name:
            return

        # Update selected part
        if self._set_selected_part_name_fn:
            self._set_selected_part_name_fn(target_part_name)
        if self._presenter_select_part_fn:
            self._presenter_select_part_fn(target_part_name)

        # Show recommendation dialog
        from automataii.presentation.qt.dialogs.recommendation_dialog import (
            MechanismRecommendationDialog,
        )
        from automataii.utils.paths import resolve_path

        generated_paths_file = resolve_path("resources/data/generated_mechanism_paths.json")
        if not generated_paths_file.exists():
            QMessageBox.critical(parent_widget, "Error", "Generated mechanism paths file not found.")
            return

        dialog = MechanismRecommendationDialog(
            enabled_parts[target_part_name], generated_paths_file, parent=parent_widget
        )
        dialog.setWindowTitle(f"Mechanism Recommendations for {target_part_name}")
        dialog.mechanism_preview_selected.connect(self._on_preview_selected)

        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_mechanism_data:
            if self._generate_mechanism_from_candidate_fn:
                self._generate_mechanism_from_candidate_fn(dialog.selected_mechanism_data)

    def _on_preview_selected(self, mechanism_data: dict[str, Any]) -> None:
        """
        Handle mechanism preview selection from dialog.

        Args:
            mechanism_data: Mechanism data to preview
        """
        self._show_preview(mechanism_data)

    def _show_preview(self, mechanism_data: dict[str, Any]) -> None:
        """
        Preview a mechanism without adding it to the layers.

        Args:
            mechanism_data: Mechanism data to preview
        """
        scene = self._get_scene_fn() if self._get_scene_fn else None
        if not scene:
            return

        # Clear any existing preview items safely
        for item in self._preview_items:
            try:
                if item and hasattr(item, 'scene') and item.scene():
                    scene.removeItem(item)
            except RuntimeError:
                # Item was already deleted by Qt - ignore
                pass
        self._preview_items = []

        # Create temporary visuals for the preview
        mechanism_type_value = mechanism_data.get('type', 'Unknown')
        internal_type = self.MECHANISM_TYPE_MAPPING.get(mechanism_type_value, "4_bar_linkage")

        if internal_type == "4_bar_linkage" and self._create_4bar_visuals_fn:
            visual_items = self._create_4bar_visuals_fn(mechanism_data)
            self._preview_items.extend(visual_items)

    def handle_recommendation_selection(
        self,
        mechanism_data: dict[str, Any],
        parent_widget: QWidget,
    ) -> None:
        """
        Handle mechanism selection from recommendation dialog.

        Args:
            mechanism_data: Selected mechanism data
            parent_widget: Parent widget for potential dialogs
        """
        if not self._instantiation_service:
            return

        # Get target path for this part
        path_data = self._get_path_data_fn() if self._get_path_data_fn else {}
        selected_part_name = self._get_selected_part_name_fn() if self._get_selected_part_name_fn else None
        target_path: QPainterPath | None = None

        if selected_part_name:
            target_path = path_data.get(selected_part_name)

        # Fallback: create path from coordinates if no user path
        if not target_path:
            path_coords = mechanism_data.get("path_coordinates")
            if path_coords and isinstance(path_coords, list) and len(path_coords) > 0:
                target_path = QPainterPath()
                target_path.moveTo(path_coords[0][0], path_coords[0][1])
                for coord in path_coords[1:]:
                    target_path.lineTo(coord[0], coord[1])

        # Get character position for fallback
        fallback_position = self._get_character_position_fn() if self._get_character_position_fn else [300, 400]

        # Create layer and graphics data via service
        layer_data, graphics_data = self._instantiation_service.create_layer_data_from_recommendation(
            mechanism_data=mechanism_data,
            target_path=target_path,
            fallback_position=fallback_position,
        )

        # Add mechanism layer and create visuals
        if self._add_mechanism_layer_fn:
            self._add_mechanism_layer_fn(graphics_data["name"], layer_data)
        if self._handle_mechanism_visuals_fn:
            self._handle_mechanism_visuals_fn(graphics_data)

    def clear_preview(self) -> None:
        """Clear any existing preview items."""
        scene = self._get_scene_fn() if self._get_scene_fn else None
        if not scene:
            self._preview_items = []
            return

        for item in self._preview_items:
            try:
                if item and hasattr(item, 'scene') and item.scene():
                    scene.removeItem(item)
            except RuntimeError:
                pass
        self._preview_items = []
