# src/automataii/ui/views/image_processing/modes/joint_drag_mode.py

import logging

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QGraphicsView

from .base_mode import IImageProcessingMode

logger = logging.getLogger(__name__)


class JointDragMode(IImageProcessingMode):
    """
    Interaction mode for dragging skeleton joints.
    Handles joint selection, dragging, and position updates.
    """

    def __init__(self, state_manager, view_ref: QGraphicsView | None = None):
        super().__init__(state_manager, view_ref)

    def handle_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse press for joint selection."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if not self.view_ref or not self.view_ref.scene():
            return False

        # Check if click is on a joint item
        item = self.view_ref.scene().itemAt(scene_pos, self.view_ref.transform())

        # Check if item is a joint (this would need to be adapted to your joint item type)
        if self._is_joint_item(item):
            # Start dragging this joint
            drag_offset = item.scenePos() - scene_pos
            self.state.start_joint_drag(item, scene_pos, drag_offset)

            # Bring joint to front
            item.setZValue(item.zValue() + 1)

            # Update cursor
            if self.view_ref:
                self.view_ref.setCursor(Qt.CursorShape.ClosedHandCursor)

            # Update cut guides for active joint
            self._update_cut_guides(item)

            logger.debug(f"Started dragging joint: {item}")
            return True

        return False

    def handle_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse move for joint dragging."""
        if not self.state.dragged_joint_item or not self.state.drag_start_pos:
            return False

        # Calculate new position
        new_pos = scene_pos + self.state.drag_start_pos_offset

        # Update joint position
        self.state.dragged_joint_item.setPos(new_pos)

        # Update connected lines
        self._update_connected_lines(self.state.dragged_joint_item)

        # Update joint label position
        self._update_joint_label_position(self.state.dragged_joint_item)

        # Update linked character part position
        self._update_linked_part_position(self.state.dragged_joint_item)

        # Update cut guides
        self._update_cut_guides(self.state.dragged_joint_item)

        return True

    def handle_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> bool:
        """Handle mouse release to end joint dragging."""
        if self.state.dragged_joint_item:
            # Reset Z-value
            self.state.dragged_joint_item.setZValue(self.state.dragged_joint_item.zValue() - 1)

            # Stop dragging
            self.state.stop_joint_drag()

            # Reset cursor
            if self.view_ref:
                self.view_ref.setCursor(self.get_cursor())

            logger.debug("Stopped dragging joint")
            return True

        return False

    def _is_joint_item(self, item) -> bool:
        """Check if an item is a joint item."""
        if not item:
            return False

        # This would need to be adapted based on your actual joint item type
        # For now, check if it has joint-like attributes
        return hasattr(item, "joint_name") or hasattr(item, "is_joint")

    def _update_connected_lines(self, joint_item) -> None:
        """Update lines connected to the moved joint."""
        if not hasattr(joint_item, "get_connected_lines"):
            return

        connected_lines = joint_item.get_connected_lines()
        for line in connected_lines:
            if hasattr(line, "update_position"):
                line.update_position()

    def _update_joint_label_position(self, joint_item) -> None:
        """Update the position of the joint's label."""
        if not hasattr(joint_item, "joint_name"):
            return

        joint_name = joint_item.joint_name

        # Check if there's a label for this joint
        if hasattr(self.state, "joint_labels") and joint_name in self.state.joint_labels:
            label_item = self.state.joint_labels[joint_name]
            # Position label slightly offset from joint
            label_item.setPos(joint_item.pos() + QPointF(5, -10))

    def _update_linked_part_position(self, joint_item) -> None:
        """Update the position of character parts linked to this joint."""
        if not hasattr(joint_item, "joint_name"):
            return

        joint_name = joint_item.joint_name
        new_joint_scene_pos = joint_item.scenePos()

        # Find which part is controlled by this joint
        if hasattr(self.state, "skeleton_to_part_map"):
            part_name = self.state.skeleton_to_part_map.get(joint_name)

            if part_name and part_name in self.state.part_items:
                part_item = self.state.part_items[part_name]

                # Update part position based on joint position
                if hasattr(part_item, "anchor_offset"):
                    # Calculate new part position based on anchor offset
                    anchor_vector = part_item.transform().map(
                        part_item.anchor_offset
                    ) - part_item.transform().map(QPointF(0, 0))
                    new_part_pos = new_joint_scene_pos - anchor_vector
                    part_item.setPos(new_part_pos)

                    logger.debug(f"Updated part '{part_name}' position for joint '{joint_name}'")

    def _update_cut_guides(self, joint_item) -> None:
        """Update perpendicular cut guides for the active joint."""
        if not hasattr(joint_item, "joint_name"):
            return

        # Clear existing guides
        for guide_line in self.state.current_guide_lines:
            if guide_line.scene():
                guide_line.scene().removeItem(guide_line)
        self.state.current_guide_lines.clear()

        # Calculate and draw new guide
        guide_line_data = self._calculate_perpendicular_cut_guide(joint_item)

        if guide_line_data and self.view_ref and self.view_ref.scene():
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QColor, QPen

            pen = QPen(QColor("cyan"), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)

            guide_item = self.view_ref.scene().addLine(guide_line_data, pen)
            guide_item.setZValue(150)  # Above most items
            self.state.current_guide_lines.append(guide_item)

    def _calculate_perpendicular_cut_guide(self, joint_item):
        """Calculate perpendicular cut guide for a joint."""
        from PyQt6.QtCore import QLineF

        from ..utils import (
            calculate_guide_direction,
            get_lines_connected_to_joint,
            normalize_vector,
        )

        if not joint_item or not hasattr(joint_item, "joint_name"):
            return None

        if not self.view_ref or not self.view_ref.scene():
            return None

        # Get all items in the scene to find connected lines
        scene_items = self.view_ref.scene().items()
        connected_lines = get_lines_connected_to_joint(joint_item, scene_items)

        if not connected_lines:
            logger.debug(f"No connected lines for joint {joint_item.joint_name}")
            return None

        # Calculate guide direction
        guide_direction = calculate_guide_direction(joint_item, connected_lines)

        if not guide_direction or guide_direction.isNull():
            logger.debug(f"Guide direction is null for {joint_item.joint_name}")
            return None

        # Normalize the guide direction
        normalized_guide_dir = normalize_vector(guide_direction)
        guide_length = 60  # pixels in local coordinates

        # Calculate guide line endpoints
        joint_pos = joint_item.scenePos()
        p1_scene = joint_pos + normalized_guide_dir * (guide_length / 2)
        p2_scene = joint_pos - normalized_guide_dir * (guide_length / 2)

        return QLineF(p1_scene, p2_scene)

    def get_cursor(self):
        """Return cursor for joint drag mode."""
        if self.state.dragged_joint_item:
            return Qt.CursorShape.ClosedHandCursor
        return Qt.CursorShape.OpenHandCursor

    def enter_mode(self) -> None:
        """Setup when entering joint drag mode."""
        if self.view_ref:
            self.view_ref.setCursor(self.get_cursor())
        logger.debug("Entered joint drag mode")

    def exit_mode(self) -> None:
        """Cleanup when exiting joint drag mode."""
        if self.state.dragged_joint_item:
            self.state.stop_joint_drag()

        # Clear cut guides
        for guide_line in self.state.current_guide_lines:
            if guide_line.scene():
                guide_line.scene().removeItem(guide_line)
        self.state.current_guide_lines.clear()

        logger.debug("Exited joint drag mode")

    def update_mode_state(self) -> None:
        """Update joint drag mode state."""
        # Update guide lines if there's an active joint
        if self.state.dragged_joint_item:
            self._update_cut_guides(self.state.dragged_joint_item)
