# src/automataii/ui/views/editor/modes/end_effector_selection_mode.py

import logging
from typing import Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

from .base_mode import IInteractionMode

logger = logging.getLogger(__name__)


class EndEffectorSelectionMode(IInteractionMode):
    """
    Interaction mode for selecting end effectors.
    Allows users to click on parts to designate them as end effectors for IK solving.
    """

    def __init__(self, state_manager, view_ref: Optional = None):
        super().__init__(state_manager, view_ref)

        # Visual elements
        self.highlighted_item = None
        self.selection_markers: list[QGraphicsEllipseItem] = []

        # Styling for end effector markers
        self.marker_pen = QPen(QColor(255, 0, 0), 3)  # Red marker
        self.marker_brush = QBrush(QColor(255, 0, 0, 80))  # Semi-transparent red
        self.marker_radius = 12

        # Highlight styling
        self.highlight_pen = QPen(QColor(255, 165, 0), 2)  # Orange highlight

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press for end effector selection."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if not self.view_ref or not self.view_ref.scene():
            return False

        # Find item at click position
        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        if item and self._is_selectable_item(item):
            self._toggle_end_effector(item, scene_pos)
            return True

        return True  # Consume event even if no valid item

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for highlighting potential selections."""
        if not self.view_ref or not self.view_ref.scene():
            return False

        # Find item under cursor
        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        # Update highlighting
        if self._is_selectable_item(item):
            self._update_item_highlighting(item)
        else:
            self._clear_highlighting()

        return False  # Don't consume - allow other processing

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release - no special behavior needed."""
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle key presses for end effector selection shortcuts."""
        key = event.key()

        # Escape to exit mode
        if key == Qt.Key.Key_Escape:
            self._exit_selection_mode()
            return True

        # Enter to complete selection
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._complete_selection()
            return True

        # Delete to clear all selections
        elif key == Qt.Key.Key_Delete:
            self._clear_all_selections()
            return True

        return False

    def _is_selectable_item(self, item: QGraphicsItem | None) -> bool:
        """Check if an item can be selected as an end effector."""
        if not item:
            return False

        # Check if it's a part item (this would depend on your specific item types)
        # For now, we'll accept any graphics item that's not one of our markers
        return item not in self.selection_markers

    def _toggle_end_effector(self, item: QGraphicsItem, position: QPointF) -> None:
        """Toggle end effector status for the selected item."""
        # Check if this item is already selected
        existing_marker = self._find_marker_for_item(item)

        if existing_marker:
            # Remove existing selection
            self._remove_end_effector_marker(existing_marker, item)
            logger.info(f"Removed end effector: {item}")
        else:
            # Add new selection
            self._add_end_effector_marker(item, position)
            logger.info(f"Added end effector: {item}")

    def _add_end_effector_marker(self, item: QGraphicsItem, position: QPointF) -> None:
        """Add a visual marker for the end effector."""
        if not self.view_ref or not self.view_ref.scene():
            return

        # Create marker at the clicked position
        marker = QGraphicsEllipseItem(
            position.x() - self.marker_radius,
            position.y() - self.marker_radius,
            self.marker_radius * 2,
            self.marker_radius * 2,
        )
        marker.setPen(self.marker_pen)
        marker.setBrush(self.marker_brush)

        # Store reference to the associated item
        marker.setData(0, item)  # Store item reference in user data

        self.view_ref.scene().addItem(marker)
        self.selection_markers.append(marker)

    def _remove_end_effector_marker(
        self, marker: QGraphicsEllipseItem, item: QGraphicsItem
    ) -> None:
        """Remove an end effector marker."""
        if not self.view_ref or not self.view_ref.scene():
            return

        self.view_ref.scene().removeItem(marker)
        if marker in self.selection_markers:
            self.selection_markers.remove(marker)

    def _find_marker_for_item(self, item: QGraphicsItem) -> QGraphicsEllipseItem | None:
        """Find the marker associated with a given item."""
        for marker in self.selection_markers:
            if marker.data(0) == item:
                return marker
        return None

    def _clear_all_selections(self) -> None:
        """Clear all end effector selections."""
        if not self.view_ref or not self.view_ref.scene():
            return

        # Remove all markers
        for marker in self.selection_markers[:]:  # Copy list to avoid modification during iteration
            self.view_ref.scene().removeItem(marker)

        self.selection_markers.clear()
        logger.info("Cleared all end effector selections")

    def _update_item_highlighting(self, item: QGraphicsItem | None) -> None:
        """Update highlighting for the item under cursor."""
        # Clear previous highlighting
        if self.highlighted_item and hasattr(self.highlighted_item, "setHighlighted"):
            self.highlighted_item.setHighlighted(False)

        self.highlighted_item = item

        # Apply new highlighting if item supports it
        if item and hasattr(item, "setHighlighted"):
            item.setHighlighted(True)

    def _clear_highlighting(self) -> None:
        """Clear all highlighting."""
        if self.highlighted_item and hasattr(self.highlighted_item, "setHighlighted"):
            self.highlighted_item.setHighlighted(False)
        self.highlighted_item = None

    def _complete_selection(self) -> None:
        """Complete end effector selection and return to pan/zoom mode."""
        selected_items = [marker.data(0) for marker in self.selection_markers]

        logger.info(f"End effector selection completed with {len(selected_items)} items")

        # TODO: Emit signal with selected end effectors
        # This would typically emit a signal that the main application handles

        # Return to pan/zoom mode (keep selections visible)
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def _exit_selection_mode(self) -> None:
        """Exit selection mode and return to pan/zoom mode."""
        logger.info("Exited end effector selection mode")

        # Clear highlighting but keep selections
        self._clear_highlighting()

        # Return to pan/zoom mode
        from ..state_manager import EditorMode

        self.state.set_mode(EditorMode.PAN_ZOOM)

    def get_cursor(self):
        """Return cursor for end effector selection mode."""
        return Qt.CursorShape.PointingHandCursor

    def enter_mode(self) -> None:
        """Setup when entering end effector selection mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())
        logger.info("Entered end effector selection mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting end effector selection mode."""
        self._clear_highlighting()
        # Note: We keep the selection markers visible even after exiting the mode
        # They can be cleared explicitly with the delete key or by other means
        logger.info("Exited end effector selection mode")
