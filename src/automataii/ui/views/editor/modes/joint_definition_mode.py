# src/automataii/ui/views/editor/modes/joint_definition_mode.py

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QGraphicsItem

from .base_mode import IInteractionMode

logger = logging.getLogger(__name__)


class JointDefinitionMode(IInteractionMode):
    """
    Interaction mode for defining joints between parts.
    Allows users to select parent and child parts to create joint connections.
    """

    def __init__(self, state_manager, view_ref: Optional = None):
        super().__init__(state_manager, view_ref)
        self.highlighted_item = None

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press for joint definition."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if not self.view_ref or not self.view_ref.scene():
            return False

        # Find item at click position
        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        if not item:
            return True  # Consume event but no item found

        # Check if we're awaiting parent selection
        if self.state.joint_definition_state["awaiting_parent"]:
            self._select_parent_item(item)
            return True

        # Check if we're awaiting child selection
        elif self.state.joint_definition_state["awaiting_child"]:
            self._select_child_item(item)
            return True

        return True

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for highlighting potential selections."""
        if not self.view_ref or not self.view_ref.scene():
            return False

        # Find item under cursor
        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        # Update highlighting
        self._update_item_highlighting(item)

        return False  # Don't consume - allow other processing

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release - no special behavior needed."""
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key presses for joint definition shortcuts."""
        key = event.key()

        # Escape to cancel joint definition
        if key == Qt.Key.Key_Escape:
            self._cancel_joint_definition()
            return True

        # Enter to confirm current selection
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._confirm_current_selection()
            return True

        return False

    def _select_parent_item(self, item: QGraphicsItem) -> None:
        """Select an item as the parent for joint definition."""
        self.state.joint_definition_state["target_parent_item"] = item
        self.state.joint_definition_state["awaiting_parent"] = False
        self.state.joint_definition_state["awaiting_child"] = True

        logger.info(f"Selected parent item for joint definition: {item}")

        # Update cursor to indicate we're now selecting child
        if self.view_ref:
            self.view_ref.setCursor(Qt.CursorShape.CrossCursor)

    def _select_child_item(self, item: QGraphicsItem) -> None:
        """Select an item as the child for joint definition."""
        parent_item = self.state.joint_definition_state["target_parent_item"]

        # Validate selection
        if item == parent_item:
            logger.warning("Cannot select same item as both parent and child")
            return

        self.state.joint_definition_state["target_child_item"] = item

        logger.info(f"Selected child item for joint definition: {item}")

        # Complete joint definition
        self._complete_joint_definition()

    def _complete_joint_definition(self) -> None:
        """Complete the joint definition process."""
        parent_item = self.state.joint_definition_state["target_parent_item"]
        child_item = self.state.joint_definition_state["target_child_item"]

        if parent_item and child_item:
            logger.info(f"Joint definition completed: {parent_item} -> {child_item}")

            # TODO: Emit signal to create actual joint
            # This would typically emit a signal that the main application handles
            # For now, we just log the completion

            # Reset state and return to pan/zoom mode
            self._reset_joint_definition()
            from ..state_manager import EditorMode

            self.state.set_mode(EditorMode.PAN_ZOOM)

    def _cancel_joint_definition(self) -> None:
        """Cancel joint definition and return to pan/zoom mode."""
        logger.info("Joint definition cancelled")
        self._reset_joint_definition()
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def _confirm_current_selection(self) -> None:
        """Confirm current selection step."""
        if self.state.joint_definition_state["awaiting_parent"]:
            # Need to select a parent first
            logger.warning("Must select parent item first")
        elif self.state.joint_definition_state["awaiting_child"]:
            # Need to select a child
            logger.warning("Must select child item")

    def _reset_joint_definition(self) -> None:
        """Reset joint definition state."""
        self.state.joint_definition_state = {
            "target_parent_item": None,
            "target_child_item": None,
            "awaiting_parent": True,
            "awaiting_child": False,
        }
        self._clear_highlighting()

    def _update_item_highlighting(self, item: QGraphicsItem | None) -> None:
        """Update highlighting for the item under cursor."""
        # Clear previous highlighting
        if self.highlighted_item and hasattr(self.highlighted_item, "setHighlighted"):
            self.highlighted_item.setHighlighted(False)

        self.highlighted_item = item

        # Apply new highlighting
        if item and hasattr(item, "setHighlighted"):
            item.setHighlighted(True)

    def _clear_highlighting(self) -> None:
        """Clear all highlighting."""
        if self.highlighted_item and hasattr(self.highlighted_item, "setHighlighted"):
            self.highlighted_item.setHighlighted(False)
        self.highlighted_item = None

    def get_cursor(self):
        """Return cursor for joint definition mode."""
        if self.state.joint_definition_state["awaiting_parent"]:
            return Qt.CursorShape.PointingHandCursor
        elif self.state.joint_definition_state["awaiting_child"]:
            return Qt.CursorShape.CrossCursor
        return Qt.CursorShape.ArrowCursor

    def enter_mode(self) -> None:
        """Setup when entering joint definition mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())
        logger.info("Entered joint definition mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting joint definition mode."""
        self._clear_highlighting()
        self._reset_joint_definition()
        logger.info("Exited joint definition mode")
