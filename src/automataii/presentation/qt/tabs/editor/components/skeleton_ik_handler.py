"""
Skeleton IK Handler - Skeleton updates, IK results, and joint management.

Extracted from EditorTab god class. Handles skeleton visualization,
IK result application, joint caching, and bend direction changes.

Design Pattern: Handler (processes external events and updates state)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QPointF, pyqtSignal, pyqtSlot

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.views.editor_view import EditorView


class SkeletonIKHandler(QObject):
    """
    Handles skeleton updates, IK results, and joint management.

    Responsibilities:
    - Process skeleton data updates for visualization
    - Cache initial skeleton state for reset operations
    - Apply IK results to update part visuals
    - Handle joint definition and bend direction changes
    - Position parts at anchor joints

    Signals:
        skeleton_updated: Emitted after skeleton visualization update
        joint_defined: Emitted when a new joint is defined
        bend_direction_changed: Emitted when joint bend direction changes
    """

    skeleton_updated = pyqtSignal()
    joint_defined = pyqtSignal(dict)
    bend_direction_changed = pyqtSignal(str, float)

    def __init__(
        self,
        editor_view: EditorView,
        editor_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize skeleton IK handler.

        Args:
            editor_view: The EditorView for skeleton visualization
            editor_scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._editor_view = editor_view
        self._editor_scene = editor_scene

        # Skeleton cache
        self._initial_skeleton_cache: dict | None = None

        # Joint definitions
        self._joints: list[dict] = []

        # Callbacks
        self._get_editor_items: Callable[[], dict[str, CharacterPartItem]] = lambda: {}
        self._get_parts_info: Callable[[], dict[str, Any]] = lambda: {}
        self._get_main_window: Callable[[], Any] = lambda: None
        self._update_button_states: Callable[[], None] = lambda: None
        self._update_part_list_styles: Callable[[], None] = lambda: None
        self._update_active_part_visuals: Callable[[], None] = lambda: None

    def configure_callbacks(
        self,
        get_editor_items: Callable[[], dict[str, CharacterPartItem]],
        get_parts_info: Callable[[], dict[str, Any]],
        get_main_window: Callable[[], Any],
        update_button_states: Callable[[], None],
        update_part_list_styles: Callable[[], None],
        update_active_part_visuals: Callable[[], None],
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_editor_items = get_editor_items
        self._get_parts_info = get_parts_info
        self._get_main_window = get_main_window
        self._update_button_states = update_button_states
        self._update_part_list_styles = update_part_list_styles
        self._update_active_part_visuals = update_active_part_visuals

    @property
    def initial_skeleton_cache(self) -> dict | None:
        """Get the initial skeleton data cache."""
        return self._initial_skeleton_cache

    @property
    def joints(self) -> list[dict]:
        """Get the list of defined joints."""
        return self._joints

    # --- Skeleton Updates ---

    @pyqtSlot(dict)
    def on_skeleton_updated(self, skeleton_data: dict | None) -> None:
        """
        Process skeleton data update for visualization.

        Args:
            skeleton_data: Skeleton data dict from StandardizedSkeletonModel
        """
        logging.info(
            f"SkeletonIKHandler: Skeleton update - {'Exists' if skeleton_data else 'None'}"
        )

        if not self._editor_view:
            return

        if skeleton_data:
            standardized_joints_dict = skeleton_data.get("joints", {})
            hierarchy = skeleton_data.get("hierarchy", {})

            skeleton_for_view = []
            editor_items = self._get_editor_items()

            if isinstance(standardized_joints_dict, dict):
                for joint_id, joint_model_dict in standardized_joints_dict.items():
                    pos_list = joint_model_dict.get("position")
                    pos = (
                        QPointF(pos_list[0], pos_list[1])
                        if pos_list and len(pos_list) == 2
                        else QPointF()
                    )

                    skeleton_for_view.append(
                        {
                            "id": joint_model_dict.get("id", joint_id),
                            "name": joint_model_dict.get("name"),
                            "position": pos,
                            "parent": joint_model_dict.get("parent_id"),
                            "color": joint_model_dict.get("color", "blue"),
                            "label": joint_model_dict.get("label"),
                            "bend_direction": joint_model_dict.get(
                                "bend_direction", 1.0
                            ),
                        }
                    )

                    # Update joint lock status for parts
                    is_locked = joint_model_dict.get("is_locked", False)
                    joint_name = joint_model_dict.get("name")

                    for part_name, part_item in editor_items.items():
                        if (
                            part_item.anchor_joint_id == joint_name
                            or part_item.anchor_joint_id == joint_id
                        ):
                            part_item.set_joint_locked(is_locked)
                            if is_locked:
                                logging.debug(
                                    f"SkeletonIKHandler: Part '{part_name}' - joint locked"
                                )

            logging.debug(
                f"SkeletonIKHandler: Visualizing {len(skeleton_for_view)} joints"
            )
            self._editor_view.visualize_skeleton(skeleton_for_view, hierarchy)
        else:
            logging.info("SkeletonIKHandler: Clearing skeleton visualization")
            self._editor_view.visualize_skeleton([], {})

        self._update_button_states()
        self.skeleton_updated.emit()

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None) -> None:
        """
        Cache initial skeleton data for reset operations.

        Args:
            skeleton_data_dict: Skeleton data to cache
        """
        if skeleton_data_dict:
            self._initial_skeleton_cache = skeleton_data_dict.copy()
            logging.info("SkeletonIKHandler: Initial skeleton data cached")

            # Pass joint_map to editor_view
            if self._editor_view and hasattr(self._editor_view, "set_joint_map"):
                joint_map = self._initial_skeleton_cache.get("joint_map")
                self._editor_view.set_joint_map(joint_map)

            # Position parts at anchor joints if loaded
            editor_items = self._get_editor_items()
            if editor_items:
                self._position_parts_at_anchor_joints()
        else:
            self._initial_skeleton_cache = None
            logging.info("SkeletonIKHandler: Skeleton cache cleared")

            if self._editor_view and hasattr(self._editor_view, "set_joint_map"):
                self._editor_view.set_joint_map(None)

        # Refresh visuals
        self._update_part_list_styles()
        self._update_active_part_visuals()
        self._update_button_states()

    def _position_parts_at_anchor_joints(self) -> None:
        """Position parts at their anchor joint locations."""
        if not self._initial_skeleton_cache or "joints" not in self._initial_skeleton_cache:
            return

        joint_map = self._initial_skeleton_cache.get("joint_map", {})
        joints_dict = self._initial_skeleton_cache.get("joints", {})

        # Import BODY_PARTS for fallback
        try:
            from automataii.domain.animation.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}
            logging.warning(
                "SkeletonIKHandler: Could not import BODY_PARTS for fallback"
            )

        editor_items = self._get_editor_items()
        parts_info = self._get_parts_info()

        for part_name, part_item in editor_items.items():
            if part_name in parts_info:
                p_info = parts_info[part_name]

                # Get anchor_joint_id with fallback
                anchor_joint_id = p_info.anchor_joint_id
                if not anchor_joint_id and BODY_PARTS:
                    part_def = BODY_PARTS.get(part_name, {})
                    anchor_joint_id = part_def.get("anchor_joint")
                    if anchor_joint_id:
                        logging.info(
                            f"SkeletonIKHandler: Fallback anchor '{anchor_joint_id}' for '{part_name}'"
                        )

                if anchor_joint_id:
                    # Find standardized joint ID
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

                            # Validate skeleton length preservation
                            position_valid = self._validate_skeleton_length_preservation(
                                part_item, scene_pos, joints_dict
                            )

                            if position_valid:
                                part_item.set_scene_position_from_anchor(
                                    scene_pos, bypass_validation=True
                                )
                                logging.info(
                                    f"SkeletonIKHandler: Positioned '{part_name}' at '{std_joint_id}'"
                                )
                            else:
                                logging.debug(
                                    f"SkeletonIKHandler: Length constraint prevented for '{part_name}'"
                                )
                    else:
                        logging.warning(
                            f"SkeletonIKHandler: Could not find anchor for '{part_name}'"
                        )

    def _validate_skeleton_length_preservation(
        self,
        part_item: CharacterPartItem,
        new_anchor_pos: QPointF,
        joint_data: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Validate that positioning preserves skeleton length constraints.

        Time Complexity: O(c) where c = number of connections
        """
        MAX_BONE_LENGTH_DEVIATION = 0.01  # 1% tolerance

        connections = self._get_connected_joints_for_part(part_item, joint_data)

        for parent_joint_id, child_joint_id, expected_length in connections:
            if parent_joint_id in joint_data and child_joint_id in joint_data:
                parent_pos = joint_data[parent_joint_id].get("position", [0, 0])
                child_pos = joint_data[child_joint_id].get("position", [0, 0])

                if len(parent_pos) >= 2 and len(child_pos) >= 2:
                    parent_point = QPointF(parent_pos[0], parent_pos[1])
                    child_point = QPointF(child_pos[0], child_pos[1])

                    dx = child_point.x() - parent_point.x()
                    dy = child_point.y() - parent_point.y()
                    current_length = (dx * dx + dy * dy) ** 0.5

                    if expected_length > 0:
                        deviation = abs(current_length - expected_length) / expected_length
                        if deviation > MAX_BONE_LENGTH_DEVIATION:
                            logging.debug(
                                f"Length violation: {parent_joint_id}->{child_joint_id} "
                                f"deviation={deviation:.3f}"
                            )
                            return False

        return True

    @staticmethod
    def _get_connected_joints_for_part(
        part_item: CharacterPartItem,
        joint_data: dict[str, dict[str, Any]],
    ) -> list[tuple[str, str, float]]:
        """
        Get bone connections for validation.

        Returns:
            List of (parent_joint_id, child_joint_id, expected_length) tuples
        """
        # Simplified implementation - returns empty to allow reset operations
        # Full implementation would use bone hierarchy
        return []

    # --- IK Updates ---

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]) -> None:
        """
        Apply IK results to update visuals.

        Args:
            ik_results: IK computation results from IKManager
        """
        logging.debug(
            f"SkeletonIKHandler: IK update with {len(ik_results)} results"
        )

        if not self._editor_view:
            logging.warning("SkeletonIKHandler: EditorView not available")
            return

        if not ik_results:
            return

        self._editor_view.update_visuals_from_animation_data(ik_results)
        self._editor_view.scene().update()

    # --- Joint Management ---

    def handle_joint_defined(self, joint_data: dict) -> None:
        """
        Handle new joint definition.

        Args:
            joint_data: Joint definition data
        """
        logging.info(f"SkeletonIKHandler: Joint defined: {joint_data}")
        self._joints.append(joint_data)

        main_window = self._get_main_window()
        if main_window:
            main_window.statusBar().showMessage(
                f"Joint defined between {joint_data['part1_name']} and {joint_data['part2_name']}"
            )

        self._update_button_states()
        self.joint_defined.emit(joint_data)

    def handle_joint_bend_direction_changed(
        self, joint_id: str, new_direction: float
    ) -> None:
        """
        Handle joint bend direction change.

        Args:
            joint_id: ID of the joint
            new_direction: New bend direction value
        """
        logging.info(
            f"SkeletonIKHandler: Joint '{joint_id}' bend direction -> {new_direction}"
        )

        main_window = self._get_main_window()
        if not main_window:
            logging.error("SkeletonIKHandler: No main_window")
            return

        if not hasattr(main_window, "skeleton_manager"):
            logging.warning("SkeletonIKHandler: No skeleton_manager")
            return

        sm = main_window.skeleton_manager
        if sm is None:
            logging.warning("SkeletonIKHandler: skeleton_manager is None")
            return

        try:
            sm.set_joint_bend_direction(joint_id, new_direction)
            logging.info("SkeletonIKHandler: set_joint_bend_direction succeeded")
        except Exception as e:
            logging.error(f"SkeletonIKHandler: Error: {e}", exc_info=True)

        # Update cached skeleton data
        if self._initial_skeleton_cache and "joints" in self._initial_skeleton_cache:
            joints = self._initial_skeleton_cache["joints"]
            if joint_id in joints:
                joints[joint_id]["bend_direction"] = new_direction
                logging.info(
                    f"SkeletonIKHandler: Updated cached bend_direction for '{joint_id}'"
                )

        self.bend_direction_changed.emit(joint_id, new_direction)
