"""
Tab Data Coordinator for managing path data and UI list updates.

Extracted from MechanismDesignTab as part of god class decomposition.
Handles path data from editor, parts data, and mechanism layers list UI.

Design Pattern: Coordinator (orchestrates data flow and UI updates)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QListWidget,
    QListWidgetItem,
)

if TYPE_CHECKING:
    from automataii.presentation.qt.models import PartInfo


class TabDataCoordinator:
    """
    Coordinates path data management and UI list updates.

    Responsibilities:
    - Process path data from editor tab
    - Process parts data
    - Display motion paths in preview
    - Update mechanism layers list UI
    - Manage control points for paths

    This coordinator reduces coupling between Tab and its data sources.
    """

    # Z-index constants
    Z_MOTION_PATH_LINE = 50
    Z_MOTION_PATH_POINT = 51

    def __init__(self) -> None:
        """Initialize coordinator."""
        self._path_visual_items: dict[str, QGraphicsPathItem] = {}
        self._control_point_items: dict[str, list[QGraphicsEllipseItem]] = {}

        # Callbacks (injected)
        self._clear_mechanism_for_part_fn: Callable[[str], None] | None = None
        self._part_has_mechanism_fn: Callable[[str], bool] | None = None

    def configure_callbacks(
        self,
        *,
        clear_mechanism_for_part: Callable[[str], None],
        part_has_mechanism: Callable[[str], bool],
    ) -> None:
        """
        Configure callbacks for Tab method delegation.

        Args:
            clear_mechanism_for_part: Function to clear mechanism for a part
            part_has_mechanism: Function to check if part has mechanism
        """
        self._clear_mechanism_for_part_fn = clear_mechanism_for_part
        self._part_has_mechanism_fn = part_has_mechanism

    def set_path_data_from_editor(
        self,
        path_data: dict[str, QPainterPath] | None,
        *,
        current_path_data: dict[str, QPainterPath],
        part_enabled_state: dict[str, bool],
        mechanism_layers: dict[str, Any],
        scene: QGraphicsScene,
        update_ui_fn: Callable[[], None],
    ) -> dict[str, QPainterPath]:
        """
        Process path data received from editor tab.

        Args:
            path_data: New path data from editor
            current_path_data: Current path data state
            part_enabled_state: Part enabled states
            mechanism_layers: Current mechanism layers
            scene: Graphics scene for visualization
            update_ui_fn: Function to update UI states

        Returns:
            Updated path data dictionary
        """
        if path_data is None:
            path_data = {}

        # Track parts that need mechanism clearing
        current_parts = set(path_data.keys())
        previous_parts = set(current_path_data.keys())
        parts_to_clear = previous_parts - current_parts

        # Clear mechanisms for removed or changed parts
        for part_name in current_parts:
            if part_name in current_path_data:
                old_path = current_path_data.get(part_name)
                new_path = path_data.get(part_name)
                if old_path != new_path and self._clear_mechanism_for_part_fn:
                    parts_to_clear.add(part_name)

        for part_name in parts_to_clear:
            if self._clear_mechanism_for_part_fn:
                self._clear_mechanism_for_part_fn(part_name)

        # Update part enabled state for new parts
        updated_path_data = path_data.copy()
        for part_name in updated_path_data.keys():
            if part_name not in part_enabled_state:
                part_enabled_state[part_name] = True

        # Remove state for removed parts
        for name in list(part_enabled_state.keys()):
            if name not in updated_path_data:
                del part_enabled_state[name]

        # Display paths and update UI
        self.display_paths_in_preview(
            path_data=updated_path_data,
            scene=scene,
        )

        update_ui_fn()

        return updated_path_data

    def set_parts_data(
        self,
        parts_data: dict[str, PartInfo] | None,
        *,
        current_parts_data: dict[str, PartInfo],
        part_enabled_state: dict[str, bool],
        current_editor_items: dict[str, Any],
        mechanism_layers: dict[str, Any],
    ) -> tuple[dict[str, PartInfo], dict[str, Any]]:
        """
        Process parts data from editor.

        Args:
            parts_data: New parts data
            current_parts_data: Current parts data
            part_enabled_state: Part enabled states
            current_editor_items: Current editor items
            mechanism_layers: Mechanism layers

        Returns:
            Tuple of (updated_parts_data, updated_editor_items)
        """
        if parts_data is None:
            parts_data = {}

        updated_parts = parts_data.copy()
        updated_items = current_editor_items.copy()

        # Initialize enabled state for new parts
        for part_name in updated_parts.keys():
            if part_name not in part_enabled_state:
                part_enabled_state[part_name] = True

        return updated_parts, updated_items

    def display_paths_in_preview(
        self,
        path_data: dict[str, QPainterPath],
        scene: QGraphicsScene,
    ) -> None:
        """
        Display motion paths from editor in the preview scene.

        Args:
            path_data: Path data to display
            scene: Graphics scene to add items to
        """
        # Clear existing path visual items
        for item in self._path_visual_items.values():
            if item.scene():
                scene.removeItem(item)
        self._path_visual_items.clear()

        # Clear existing control points
        for _part_name, control_points in self._control_point_items.items():
            for control_point in control_points:
                if control_point.scene():
                    scene.removeItem(control_point)
        self._control_point_items.clear()

        if not path_data:
            return

        # Add new path visuals
        for part_name, path in path_data.items():
            if path and not path.isEmpty():
                # Create path item with styling
                path_item = QGraphicsPathItem(path)
                pen = QPen(QColor(0, 150, 255, 180))  # Blue with alpha
                pen.setWidth(3)
                pen.setStyle(Qt.PenStyle.DashLine)
                path_item.setPen(pen)
                path_item.setZValue(self.Z_MOTION_PATH_LINE)

                scene.addItem(path_item)
                self._path_visual_items[part_name] = path_item

                # Add control points along the path
                self._add_control_points_for_path(part_name, path, scene)

    def _add_control_points_for_path(
        self,
        part_name: str,
        path: QPainterPath,
        scene: QGraphicsScene,
    ) -> None:
        """
        Add control points along a path for visualization.

        Args:
            part_name: Name of the part
            path: Path to add points for
            scene: Graphics scene
        """
        control_point_items: list[QGraphicsEllipseItem] = []

        total_length = path.length()
        if total_length > 0:
            num_points = min(20, max(5, int(total_length / 50)))

            for i in range(num_points + 1):
                t = i / num_points if num_points > 0 else 0
                point = path.pointAtPercent(t)

                # Create control point
                control_point = QGraphicsEllipseItem(-4, -4, 8, 8)
                control_point.setPos(point)
                control_point.setBrush(QBrush(QColor(0, 100, 255)))
                control_point.setPen(QPen(QColor(0, 50, 200), 1))
                control_point.setZValue(self.Z_MOTION_PATH_POINT)
                control_point.setVisible(True)
                control_point.setEnabled(True)

                scene.addItem(control_point)
                control_point_items.append(control_point)

        self._control_point_items[part_name] = control_point_items

    def update_mechanism_layers_list(
        self,
        mechanism_layers_list: QListWidget | None,
        *,
        presenter_view_model: Any | None,
        part_enabled_state: dict[str, bool],
        main_window: Any | None,
    ) -> None:
        """
        Update the mechanism layers list UI.

        Args:
            mechanism_layers_list: List widget to update
            presenter_view_model: Optional presenter view model
            part_enabled_state: Part enabled states
            main_window: Main window reference for editor data
        """
        if mechanism_layers_list is None:
            return

        mechanism_layers_list.clear()

        # Use presenter view-model if available
        if presenter_view_model:
            self._populate_from_view_model(
                mechanism_layers_list,
                presenter_view_model,
                part_enabled_state,
            )
            return

        # Fallback to editor data
        self._populate_from_editor(
            mechanism_layers_list,
            main_window,
            part_enabled_state,
        )

    def _populate_from_view_model(
        self,
        list_widget: QListWidget,
        view_model: Any,
        part_enabled_state: dict[str, bool],
    ) -> None:
        """Populate list from presenter view model."""
        for part_vm in view_model.parts:
            part_name = part_vm.name
            enabled = part_vm.enabled
            has_layers = part_vm.has_layers

            # Check local mechanism state
            if self._part_has_mechanism_fn:
                has_layers = has_layers or self._part_has_mechanism_fn(part_name)

            part_enabled_state[part_name] = enabled

            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)
            item.setForeground(Qt.GlobalColor.black if enabled else Qt.GlobalColor.gray)

            if has_layers:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
                item.setToolTip(f"{part_name} — mechanism layers active")
            elif not enabled:
                item.setToolTip(f"{part_name} — disabled")
            else:
                item.setToolTip(f"{part_name} — no mechanism applied")

            item.setSelected(part_vm.is_selected)
            list_widget.addItem(item)

    def _populate_from_editor(
        self,
        list_widget: QListWidget,
        main_window: Any | None,
        part_enabled_state: dict[str, bool],
    ) -> None:
        """Populate list from editor tab data."""
        if not main_window:
            return

        editor_tab = getattr(main_window, "editor_tab", None)
        if not editor_tab:
            return

        editor_parts_data = getattr(editor_tab, "current_parts_info", None)
        editor_path_data = None
        if hasattr(editor_tab, "get_current_path_data"):
            editor_path_data = editor_tab.get_current_path_data()

        if not editor_parts_data:
            return

        # Filter out disabled parts
        disabled_parts = {
            "torso",
            "left_arm_upper",
            "right_arm_upper",
            "left_leg_upper",
            "right_leg_upper",
        }

        all_parts = [part for part in editor_parts_data.keys() if part not in disabled_parts]

        for part in all_parts:
            item = QListWidgetItem(part)
            item.setData(Qt.ItemDataRole.UserRole, part)

            # Color based on whether part has motion path
            has_motion_path = (
                editor_path_data
                and part in editor_path_data
                and editor_path_data[part] is not None
                and not editor_path_data[part].isEmpty()
            )

            if has_motion_path:
                item.setForeground(Qt.GlobalColor.black)
                item.setToolTip(f"{part} — has motion path")
            else:
                item.setForeground(Qt.GlobalColor.gray)
                item.setToolTip(f"{part} — no motion path")

            # Initialize enabled state
            if part not in part_enabled_state:
                part_enabled_state[part] = True

            list_widget.addItem(item)

    def clear_path_visuals(self, scene: QGraphicsScene) -> None:
        """
        Clear all path visual items from the scene.

        Args:
            scene: Graphics scene to clear items from
        """
        for item in self._path_visual_items.values():
            if item.scene():
                scene.removeItem(item)
        self._path_visual_items.clear()

        for _part_name, control_points in self._control_point_items.items():
            for control_point in control_points:
                if control_point.scene():
                    scene.removeItem(control_point)
        self._control_point_items.clear()

    def get_enabled_parts_with_paths(
        self,
        path_data: dict[str, QPainterPath],
        part_enabled_state: dict[str, bool],
    ) -> dict[str, QPainterPath]:
        """
        Get enabled parts that have motion paths.

        Args:
            path_data: All path data
            part_enabled_state: Part enabled states

        Returns:
            Dict of enabled parts with their paths
        """
        return {
            name: path for name, path in path_data.items() if part_enabled_state.get(name, True)
        }

    def resolve_target_part(
        self,
        enabled_parts_with_paths: dict[str, QPainterPath],
        selected_part: str | None,
        list_widget: QListWidget | None,
    ) -> str | None:
        """
        Resolve the target part for mechanism generation.

        Args:
            enabled_parts_with_paths: Dict of enabled parts with paths
            selected_part: Currently selected part name (from list)
            list_widget: List widget to check selection

        Returns:
            Target part name, or None if selection needed/cancelled
        """
        if not enabled_parts_with_paths:
            return None

        # Check if a part is selected from the list
        target_part_name = None
        if list_widget:
            selected_items = list_widget.selectedItems()
            if selected_items:
                sel_part = selected_items[0].data(Qt.ItemDataRole.UserRole)
                if sel_part and sel_part in enabled_parts_with_paths:
                    target_part_name = sel_part

        # Use provided selection if valid
        if not target_part_name and selected_part and selected_part in enabled_parts_with_paths:
            target_part_name = selected_part

        # If still no target and only one part, use it
        if not target_part_name and len(enabled_parts_with_paths) == 1:
            target_part_name = next(iter(enabled_parts_with_paths.keys()))

        return target_part_name
