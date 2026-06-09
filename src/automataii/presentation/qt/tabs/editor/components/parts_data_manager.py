"""
Parts Data Manager - Character parts list and data management.

Extracted from EditorTab god class. Handles parts list population,
data loading, selection management, and part item creation.

Design Pattern: Manager (coordinates part data operations)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QListWidget

    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.models import PartInfo
    from automataii.presentation.qt.views.editor_view import EditorView


class PartsDataManager(QObject):
    """
    Manages character parts data and list widget.

    Responsibilities:
    - Populate parts list widget
    - Load parts data and create CharacterPartItems
    - Handle part selection changes
    - Clear editor content
    - Update visual styles for parts with paths

    Signals:
        parts_loaded: Emitted when parts are loaded (bool: has_parts)
        parts_cleared: Emitted when editor content is cleared
        part_selected: Emitted when a part is selected (part_name)
    """

    parts_loaded = pyqtSignal(bool)
    parts_cleared = pyqtSignal()
    part_selected = pyqtSignal(str)

    # Parts that should be disabled in the list
    DISABLED_PARTS = frozenset(
        {
            "torso",
            "left_arm_upper",
            "right_arm_upper",
            "left_leg_upper",
            "right_leg_upper",
        }
    )

    def __init__(
        self,
        editor_view: EditorView,
        editor_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize parts data manager.

        Args:
            editor_view: The EditorView
            editor_scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._editor_view = editor_view
        self._editor_scene = editor_scene

        # UI reference
        self._parts_list: QListWidget | None = None

        # State
        self._current_parts_info: dict[str, PartInfo] = {}
        self._current_editor_items: dict[str, CharacterPartItem] = {}
        self._selected_part_name: str | None = None
        self._joints: list[dict] = []

        # Callbacks
        self._get_main_window: Callable[[], Any] = lambda: None
        self._get_debug_mode: Callable[[], bool] = lambda: False
        self._get_skeleton_cache: Callable[[], dict | None] = lambda: None
        self._set_skeleton_cache: Callable[[dict | None], None] = lambda x: None
        self._update_button_states: Callable[[], None] = lambda: None
        self._update_part_list_styles: Callable[[], None] = lambda: None
        self._update_active_part_visuals: Callable[[], None] = lambda: None
        self._emit_path_data: Callable[[], None] = lambda: None
        self._validate_position: Callable[[Any, QPointF, dict], bool] = lambda a, b, c: True

    def configure_ui(self, parts_list: QListWidget) -> None:
        """Configure UI element reference."""
        self._parts_list = parts_list

    def configure_callbacks(
        self,
        get_main_window: Callable[[], Any],
        get_debug_mode: Callable[[], bool],
        get_skeleton_cache: Callable[[], dict | None],
        set_skeleton_cache: Callable[[dict | None], None],
        update_button_states: Callable[[], None],
        update_part_list_styles: Callable[[], None],
        update_active_part_visuals: Callable[[], None],
        emit_path_data: Callable[[], None],
        validate_position: Callable[[Any, QPointF, dict], bool],
    ) -> None:
        """Configure callback functions."""
        self._get_main_window = get_main_window
        self._get_debug_mode = get_debug_mode
        self._get_skeleton_cache = get_skeleton_cache
        self._set_skeleton_cache = set_skeleton_cache
        self._update_button_states = update_button_states
        self._update_part_list_styles = update_part_list_styles
        self._update_active_part_visuals = update_active_part_visuals
        self._emit_path_data = emit_path_data
        self._validate_position = validate_position

    # --- Properties ---

    @property
    def current_parts_info(self) -> dict[str, PartInfo]:
        """Get current parts info dictionary."""
        return self._current_parts_info

    @property
    def current_editor_items(self) -> dict[str, CharacterPartItem]:
        """Get current editor items dictionary."""
        return self._current_editor_items

    @property
    def selected_part_name(self) -> str | None:
        """Get currently selected part name."""
        return self._selected_part_name

    @selected_part_name.setter
    def selected_part_name(self, value: str | None) -> None:
        """Set currently selected part name."""
        self._selected_part_name = value

    @property
    def joints(self) -> list[dict]:
        """Get joints list."""
        return self._joints

    # --- Parts List Management ---

    def populate_parts_list(self, part_names: list[str]) -> None:
        """
        Populate the parts list widget with given names.

        Disables upper limb parts and torso.

        Args:
            part_names: List of part names to display
        """
        if not self._parts_list:
            return

        self._parts_list.clear()

        for part_name in part_names:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)

            # Disable upper parts and torso
            if any(disabled in part_name.lower() for disabled in self.DISABLED_PARTS):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QBrush(QColor(150, 150, 150)))
                item.setBackground(QBrush(QColor(240, 240, 240)))
            else:
                self._parts_list.addItem(item)

        self._update_button_states()
        self._update_part_list_styles()
        self._update_active_part_visuals()

    def handle_part_selection_change(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """
        Handle selection changes from the parts list widget.

        Args:
            current: Currently selected item
            _previous: Previously selected item (unused, required by Qt signal signature)
        """
        logging.debug(f"PartsDataManager: Selection changed. Current: {current}")

        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)
            logging.debug(f"PartsDataManager: Part name from UserRole: {part_name}")

            if part_name:
                self._selected_part_name = part_name

                # Highlight in scene
                if part_name in self._current_editor_items:
                    item_to_select = self._current_editor_items[part_name]
                    self._editor_scene.clearSelection()
                    item_to_select.setSelected(True)
                    logging.info(f"PartsDataManager: Part '{part_name}' selected and highlighted")
                else:
                    self._editor_scene.clearSelection()
                    logging.debug(f"PartsDataManager: Part '{part_name}' not in scene")

                self.part_selected.emit(part_name)
            else:
                self._selected_part_name = None
                self._editor_scene.clearSelection()
                logging.warning("PartsDataManager: No part name in UserRole")
        else:
            self._selected_part_name = None
            self._editor_scene.clearSelection()
            logging.debug("PartsDataManager: No part selected")

        self._update_part_list_styles()

    def handle_part_item_clicked(self, clicked_item: CharacterPartItem) -> None:
        """
        Handle CharacterPartItem clicked in EditorView.

        Args:
            clicked_item: The clicked part item
        """
        if not self._parts_list:
            return

        part_name = clicked_item.name()
        logging.debug(f"PartsDataManager: Part '{part_name}' clicked in view")

        # Update QListWidget selection
        for i in range(self._parts_list.count()):
            list_item = self._parts_list.item(i)
            if list_item and list_item.text() == part_name:
                self._parts_list.setCurrentItem(
                    list_item, Qt.ItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                break

    def handle_part_item_double_clicked(self, double_clicked_item: CharacterPartItem) -> None:
        """
        Handle CharacterPartItem double-clicked in EditorView.

        Args:
            double_clicked_item: The double-clicked part item
        """
        part_name = double_clicked_item.name()
        logging.debug(f"PartsDataManager: Part '{part_name}' double-clicked")
        QMessageBox.information(
            None, "Part Double-Clicked", f"Part '{part_name}' was double-clicked."
        )

    # --- Parts Data Loading ---

    def set_parts_data(self, parts_info: dict[str, PartInfo]) -> None:
        """
        Load parts data and create CharacterPartItems.

        Args:
            parts_info: Dictionary of part name to PartInfo
        """
        from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem

        self.clear_editor_content()

        self._current_parts_info = parts_info if parts_info else {}
        created_editor_items: dict[str, CharacterPartItem] = {}

        if not self._current_parts_info:
            logging.info("PartsDataManager: No parts data to set")
            self.parts_loaded.emit(False)
            self.populate_parts_list([])
            self._update_button_states()
            return

        # Get project directory
        main_window = self._get_main_window()
        project_dir = None
        if (
            main_window
            and hasattr(main_window, "project_data_manager")
            and main_window.project_data_manager.project_dir
        ):
            project_dir = main_window.project_data_manager.project_dir
        else:
            logging.error("PartsDataManager: Project directory not available")
            QMessageBox.critical(
                None,
                "Error",
                "Project directory is missing. Cannot load part textures.",
            )
            self.parts_loaded.emit(False)
            self.populate_parts_list(list(self._current_parts_info.keys()))
            self._update_button_states()
            return

        debug_mode = self._get_debug_mode()
        skeleton_cache = self._get_skeleton_cache()

        # Import BODY_PARTS for fallback
        try:
            from automataii.domain.animation.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}
            logging.warning("PartsDataManager: Could not import BODY_PARTS")

        for part_name, p_info in self._current_parts_info.items():
            item = CharacterPartItem(
                part_info=p_info,
                project_dir=project_dir,
                debug_mode=debug_mode,
            )

            self._editor_scene.addItem(item)
            created_editor_items[part_name] = item

            # Get anchor joint ID with fallback
            anchor_joint_id = p_info.anchor_joint_id
            if not anchor_joint_id and BODY_PARTS:
                part_def = BODY_PARTS.get(part_name, {})
                anchor_joint_id = part_def.get("anchor_joint")
                if anchor_joint_id:
                    logging.info(
                        f"PartsDataManager: Fallback anchor '{anchor_joint_id}' for '{part_name}'"
                    )

            # Position at anchor joint if skeleton data available
            if anchor_joint_id and skeleton_cache:
                joint_map = skeleton_cache.get("joint_map", {})
                joints_dict = skeleton_cache.get("joints", {})

                std_joint_id = None
                for orig_name, std_id in joint_map.items():
                    if orig_name == anchor_joint_id:
                        std_joint_id = std_id
                        break

                if std_joint_id and std_joint_id in joints_dict:
                    joint_data = joints_dict[std_joint_id]
                    joint_pos = joint_data.get("position", [0, 0])

                    if len(joint_pos) >= 2:
                        scene_pos = QPointF(joint_pos[0], joint_pos[1])

                        position_valid = self._validate_position(item, scene_pos, joints_dict)

                        if position_valid:
                            item.set_scene_position_from_anchor(scene_pos, bypass_validation=True)
                            logging.info(
                                f"PartsDataManager: Positioned '{part_name}' at '{std_joint_id}'"
                            )

                    # Update lock status
                    is_locked = joint_data.get("is_locked", False)
                    item.set_joint_locked(is_locked)
                else:
                    logging.warning(f"PartsDataManager: Could not find anchor for '{part_name}'")

        self._current_editor_items = created_editor_items

        self.populate_parts_list(list(self._current_parts_info.keys()))
        self._update_button_states()
        self._editor_view.reset_view()

        logging.info(f"PartsDataManager: Added {len(self._current_editor_items)} items to scene")

        self.parts_loaded.emit(True)
        self._emit_path_data()

    def clear_editor_content(self) -> None:
        """Clear all parts and joints from the editor scene."""
        logging.info("PartsDataManager: Clearing content")

        if not self._editor_scene:
            logging.warning("PartsDataManager: Scene not available")
            return

        # Remove CharacterPartItems
        for item in list(self._current_editor_items.values()):
            if item.scene() == self._editor_scene:
                self._editor_scene.removeItem(item)
        self._current_editor_items.clear()

        # Clear joints
        self._joints.clear()

        self._selected_part_name = None
        self.populate_parts_list([])
        self._update_button_states()

        # Reset view state
        self._editor_view.reset_temp_visuals()
        self._editor_view.set_mode("select")

        self.parts_cleared.emit()
        self.parts_loaded.emit(False)

        # Clear skeleton cache
        self._set_skeleton_cache(None)
        logging.info("PartsDataManager: Cleared skeleton cache")

        if hasattr(self._editor_view, "set_joint_map"):
            self._editor_view.set_joint_map(None)

    # --- Part List Styling ---

    def update_part_list_styles(self, has_motion_path: Callable[[str], bool]) -> None:
        """
        Update item backgrounds to show which parts have paths.

        Args:
            has_motion_path: Function to check if part has motion path
        """
        if not self._parts_list:
            return

        orange_brush = QBrush(QColor(255, 165, 0, 100))
        transparent_brush = QBrush(QColor(Qt.GlobalColor.transparent))

        for i in range(self._parts_list.count()):
            item = self._parts_list.item(i)
            if not item:
                continue

            part_name = item.data(Qt.ItemDataRole.UserRole)
            if not part_name:
                part_name = item.text().replace(" ●", "")

            has_path = has_motion_path(part_name)

            if has_path:
                item.setBackground(orange_brush)
                if not item.text().endswith(" ●"):
                    item.setText(f"{part_name} ●")
            else:
                item.setBackground(transparent_brush)
                if item.text().endswith(" ●"):
                    item.setText(part_name)

    def update_active_part_visuals(self, has_motion_path: Callable[[str], bool]) -> None:
        """
        Update visual state of CharacterPartItems.

        Args:
            has_motion_path: Function to check if part has motion path
        """
        for name, item in self._current_editor_items.items():
            has_path = has_motion_path(name)
            item.set_active(has_path)
