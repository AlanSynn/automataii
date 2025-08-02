import logging
import math
from typing import Any

from PyQt6.QtCore import QLineF, QObject, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from automataii.config.z_indices import (
    Z_SKELETON_BONES,
    Z_SKELETON_JOINTS,
    Z_SKELETON_MECHANISM_BONES,
    Z_SKELETON_MECHANISM_JOINTS,
)


class SkeletonSignals(QObject):
    """Signal object for SkeletonGraphicsItem to avoid multiple inheritance issues."""

    joint_clicked = pyqtSignal(str)  # joint_id
    joint_double_clicked = pyqtSignal(str)  # joint_id


class SkeletonGraphicsItem(QGraphicsItem):
    """
    A QGraphicsItem to display a character's skeleton (joints and bones).
    """

    JOINT_RADIUS = 5
    BONE_PEN_WIDTH = 2
    ARROW_SIZE = 15  # Size of bend direction arrows

    def __init__(
        self,
        skeleton_data: list[dict[str, Any]] | None = None,
        hierarchy: dict[str, list[str]] | None = None,
        parent: QGraphicsItem | None = None,
        mechanism_mode: bool = False,
    ):
        """
        Initializes the SkeletonGraphicsItem.

        Args:
            skeleton_data: A list of dictionaries, where each dictionary represents a joint
                           and contains 'id', 'position' (QPointF or [x,y]), 'parent', 'name', 'color'.
            hierarchy: A dictionary mapping parent joint IDs to a list of child joint IDs.
            parent: The parent QGraphicsItem.
            mechanism_mode: If True, uses higher Z-values for mechanism tab visibility above parts.
        """
        super().__init__(parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # Create signals object to handle PyQt signals
        self.signals = SkeletonSignals()
        
        # Control whether double-click automatically toggles bend direction
        self.auto_toggle_bend_on_double_click = True

        # Store mechanism mode for Z-value configuration
        self.mechanism_mode = mechanism_mode

        # Configure Z-values based on mode
        if mechanism_mode:
            self.bone_z_value = Z_SKELETON_MECHANISM_BONES
            self.joint_z_value = Z_SKELETON_MECHANISM_JOINTS
        else:
            self.bone_z_value = Z_SKELETON_BONES
            self.joint_z_value = Z_SKELETON_JOINTS

        self._joint_items: dict[str, QGraphicsEllipseItem] = {}  # joint_id -> QGraphicsEllipseItem
        self._bone_items: list[QGraphicsLineItem] = []
        self._highlighted_joints: set[str] = set()  # Track highlighted joints
        self._joint_bend_directions: dict[str, float] = {}  # joint_id -> bend_angle (radians)
        self._arrow_items: dict[str, QGraphicsPolygonItem] = {}  # joint_id -> arrow item

        # Cache of the original structural data for rebuilding/updating bones
        self._joints_data_cache: list[dict[str, Any]] = []
        self._hierarchy_cache: dict[str, list[str]] = {}

        if skeleton_data and hierarchy:
            self.load_skeleton_data(skeleton_data, hierarchy)
        else:
            logging.info("SkeletonGraphicsItem: Initialized without skeleton data.")

    def __del__(self):
        """Destructor to ensure proper cleanup."""
        try:
            logging.debug("SkeletonItem: Destructor called, ensuring cleanup")
            self.cleanup()
        except Exception as e:
            logging.error(f"SkeletonItem: Error in destructor: {e}")

    def _clear_visuals(self):
        """Clears all joint and bone QGraphicsItems from the scene and internal tracking."""
        logging.debug(
            f"SkeletonItem:_clear_visuals - Clearing {len(self._joint_items)} joints and {len(self._bone_items)} bones."
        )

        # Clear arrows first to avoid reference issues
        self._clear_all_arrows()

        # Remove joint items with proper cleanup
        if self.scene():
            for joint_id, item in list(self._joint_items.items()):
                try:
                    self.scene().removeItem(item)
                    # Ensure item is properly deleted
                    item.setParent(None)
                    item.deleteLater() if hasattr(item, "deleteLater") else None
                except RuntimeError:
                    # Item might already be deleted
                    pass

            # Remove bone items with proper cleanup
            for item in list(self._bone_items):
                try:
                    self.scene().removeItem(item)
                    # Ensure item is properly deleted
                    item.setParent(None)
                    item.deleteLater() if hasattr(item, "deleteLater") else None
                except RuntimeError:
                    # Item might already be deleted
                    pass

        # Clear all collections
        self._joint_items.clear()
        self._bone_items.clear()
        self._highlighted_joints.clear()
        self._joint_bend_directions.clear()

        # Force garbage collection to clean up Qt objects
        import gc

        gc.collect()

    def load_skeleton_data(
        self, skeleton_data: list[dict[str, Any]], hierarchy: dict[str, list[str]]
    ):
        """
        Loads new skeleton data and rebuilds the visual representation.
        skeleton_data: List of joint dicts, each with 'id', 'position' (QPointF), 'parent' (parent_id).
        hierarchy: Dict mapping parent_id to list of child_ids.
        """
        logging.debug(
            f"SkeletonItem:load_skeleton_data - Received skeleton_data (count: {len(skeleton_data) if skeleton_data else 0})."
        )
        logging.debug(
            f"SkeletonItem:load_skeleton_data - Received hierarchy (keys: {list(hierarchy.keys()) if hierarchy else 'None'})."
        )

        self.prepareGeometryChange()
        self._clear_visuals()

        self._joints_data_cache = []  # Reset cache
        self._hierarchy_cache = hierarchy.copy() if hierarchy else {}

        temp_joint_positions = {}  # To build bones later: joint_id -> QPointF

        if not skeleton_data:
            logging.warning("SkeletonItem:load_skeleton_data - skeleton_data is empty or None.")
            self.update()  # Trigger repaint if needed
            return

        for joint_info in skeleton_data:
            joint_id = joint_info.get("id")
            pos_data = joint_info.get("position")

            if not joint_id:
                logging.warning(
                    f"SkeletonItem:load_skeleton_data - Skipping joint with no ID: {joint_info}"
                )
                continue

            position = QPointF()
            if isinstance(pos_data, QPointF):
                position = pos_data
            elif isinstance(pos_data, (list, tuple)) and len(pos_data) == 2:
                try:
                    position = QPointF(float(pos_data[0]), float(pos_data[1]))
                except (ValueError, TypeError):
                    logging.warning(
                        f"SkeletonItem:load_skeleton_data - Invalid position data for joint '{joint_id}': {pos_data}. Using (0,0)."
                    )
            else:
                logging.warning(
                    f"SkeletonItem:load_skeleton_data - Position data for joint '{joint_id}' is not QPointF or list/tuple [x,y]: {pos_data}. Using (0,0)."
                )

            # Cache the processed joint info
            self._joints_data_cache.append(
                {
                    "id": joint_id,
                    "position": position,  # Store the QPointF
                    "parent": joint_info.get("parent"),  # Store original parent ID
                    "name": joint_info.get("name", joint_id),
                    "color": joint_info.get("color", "red"),  # Default color
                }
            )
            temp_joint_positions[joint_id] = position

            # Create visual item for the joint
            joint_item = QGraphicsEllipseItem(
                -self.JOINT_RADIUS,
                -self.JOINT_RADIUS,
                2 * self.JOINT_RADIUS,
                2 * self.JOINT_RADIUS,
                parent=self,  # Add as child of SkeletonGraphicsItem
            )
            joint_item.setPos(position)
            joint_color_str = joint_info.get("color", "red")
            try:
                joint_color = QColor(joint_color_str)
                if not joint_color.isValid():
                    logging.warning(
                        f"SkeletonItem: Invalid color string '{joint_color_str}' for joint '{joint_id}'. Defaulting to red."
                    )
                    joint_color = QColor("red")
            except Exception:
                logging.warning(
                    f"SkeletonItem: Exception parsing color '{joint_color_str}' for joint '{joint_id}'. Defaulting to red."
                )
                joint_color = QColor("red")

            joint_item.setBrush(QBrush(joint_color))
            joint_item.setPen(QPen(Qt.GlobalColor.black, 1))
            joint_item.setZValue(self.joint_z_value)  # Use configured Z-value

            # Make joint clickable
            joint_item.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
            joint_item.setAcceptHoverEvents(True)

            # Store joint_id as data for event handling
            joint_item.setData(0, joint_id)

            self._joint_items[joint_id] = joint_item

        logging.debug(
            f"SkeletonItem:load_skeleton_data - Created {len(self._joint_items)} joint items."
        )
        self._update_bone_lines()  # Create bones based on the newly loaded joints and hierarchy
        self.update()  # Recalculate bounding rect and trigger repaint

    def set_animated_pose(self, joint_positions: dict[str, tuple[float, float]]):
        logging.debug(
            f"SkeletonItem:set_animated_pose - Received joint_positions (count: {len(joint_positions)}): {joint_positions if len(joint_positions) < 5 else str(list(joint_positions.items())[:5]) + '...'}"
        )

        if not self._joint_items:
            logging.warning(
                "SkeletonItem: set_animated_pose called but no joint items to update. Was load_skeleton_data called with valid data?"
            )
            return

        self.prepareGeometryChange()  # Important if bounding box changes

        updated_any_joint = False
        for joint_id, pos_tuple in joint_positions.items():
            if joint_id in self._joint_items:
                new_pos = QPointF(pos_tuple[0], pos_tuple[1])
                current_pos = self._joint_items[joint_id].pos()
                if new_pos != current_pos:
                    self._joint_items[joint_id].setPos(new_pos)

                    # Update the cached position for this joint as well, so _update_bone_lines uses current animated pos
                    for cached_joint in self._joints_data_cache:
                        if cached_joint["id"] == joint_id:
                            cached_joint["position"] = new_pos  # Update QPointF
                            break
                    updated_any_joint = True
            else:
                logging.warning(
                    f"SkeletonItem:set_animated_pose - Joint ID '{joint_id}' from animation data not found in loaded joint items."
                )

        if updated_any_joint:
            self._update_bone_lines()  # Rebuild bones based on new joint positions
            self.update()  # Ensure repaint and bounding box update
        else:
            logging.debug(
                "SkeletonItem:set_animated_pose - No actual joint position changes detected."
            )

    def _update_bone_lines(self):
        # Only create bones if they don't exist yet (avoid recreation every frame)
        if self._bone_items and len(self._bone_items) > 0:
            # UPDATE existing bones instead of recreating
            self._update_existing_bone_positions()
            return

        logging.debug(
            f"SkeletonItem:_update_bone_lines - Creating {len(self._bone_items)} initial bone items."
        )

        if not self._joints_data_cache or not self._hierarchy_cache:
            logging.debug(
                "SkeletonItem:_update_bone_lines - No cached joints or hierarchy to create bones."
            )
            return

        # Create a quick lookup for current joint positions from _joints_data_cache
        current_joint_positions = {
            j["id"]: j["position"]
            for j in self._joints_data_cache
            if isinstance(j.get("position"), QPointF)
        }

        for parent_id, child_ids in self._hierarchy_cache.items():
            parent_pos = current_joint_positions.get(parent_id)
            if not parent_pos:
                continue

            for child_id in child_ids:
                child_pos = current_joint_positions.get(child_id)
                if not child_pos:
                    continue

                line = QLineF(parent_pos, child_pos)
                bone_item = QGraphicsLineItem(line, parent=self)
                bone_item.setPen(QPen(Qt.GlobalColor.gray, self.BONE_PEN_WIDTH))
                bone_item.setZValue(self.bone_z_value)  # Use configured Z-value
                self._bone_items.append(bone_item)

        logging.debug(
            f"SkeletonItem:_update_bone_lines - Created {len(self._bone_items)} new bone items."
        )

    def _update_existing_bone_positions(self):
        """Update existing bone positions without recreating them."""
        if not self._joints_data_cache or not self._hierarchy_cache:
            return

        # Create a quick lookup for current joint positions
        current_joint_positions = {
            j["id"]: j["position"]
            for j in self._joints_data_cache
            if isinstance(j.get("position"), QPointF)
        }

        bone_index = 0
        for parent_id, child_ids in self._hierarchy_cache.items():
            parent_pos = current_joint_positions.get(parent_id)
            if not parent_pos:
                continue

            for child_id in child_ids:
                child_pos = current_joint_positions.get(child_id)
                if not child_pos:
                    continue

                if bone_index < len(self._bone_items):
                    # Update existing bone line
                    new_line = QLineF(parent_pos, child_pos)
                    self._bone_items[bone_index].setLine(new_line)
                bone_index += 1

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ):
        logging.debug(
            f"SkeletonItem:paint CALLED. BoundingRect: ({self.boundingRect().x()},{self.boundingRect().y()},{self.boundingRect().width()},{self.boundingRect().height()}). Joint items: {len(self._joint_items)}, Bone items: {len(self._bone_items)}"
        )
        # Joints and bones are child items. No specific painting needed for the parent item itself,
        # unless for debugging or a background.
        pass

    def boundingRect(self) -> QRectF:
        """
        Calculates the bounding rectangle of all joint items.
        """
        if not self._joint_items:
            return QRectF()

        # Get bounding rect of all child joint items (which are in local coordinates relative to this item)
        # and then map them to this item's coordinate system (which is trivial as they are direct children)
        rect = QRectF()
        for joint_item in self._joint_items.values():
            # joint_item.boundingRect() is in its own local coords (-radius, -radius, 2*radius, 2*radius)
            # joint_item.sceneBoundingRect() is in scene coords
            # We need the rect that encompasses all joint_item.pos() plus their radius
            joint_visual_rect = QRectF(
                joint_item.pos() - QPointF(self.JOINT_RADIUS, self.JOINT_RADIUS),
                joint_item.pos() + QPointF(self.JOINT_RADIUS, self.JOINT_RADIUS),
            )
            rect = rect.united(joint_visual_rect)

        # Also include bones in bounding rect calculation
        for bone_item in self._bone_items:
            rect = rect.united(
                bone_item.boundingRect()
            )  # bone_item.boundingRect() is in its local coords (relative to bone start)
            # but since bone_item is child of SkeletonGraphicsItem, and its line is set with scene-like coords from parent's view, this is tricky.
            # A simpler way for bones that are children:
            # Their lines are p1,p2. The bounding rect in parent coords is just that.
            # The QGraphicsLineItem's boundingRect might be minimal.
            # We need the rect encompassing the line's endpoints.
            p1 = bone_item.line().p1()
            p2 = bone_item.line().p2()
            bone_rect = QRectF(p1, p2).normalized()
            rect = rect.united(bone_rect)

        # Add a small margin
        if not rect.isNull():
            margin = self.JOINT_RADIUS + self.BONE_PEN_WIDTH  # Margin based on visuals
            rect = rect.adjusted(-margin, -margin, margin, margin)

        # logging.debug(f"SkeletonItem:boundingRect calculated: {rect}")
        return rect

    def get_joint_position(self, joint_id: str) -> QPointF | None:
        """Returns the current visual position of a joint by its ID."""
        item = self._joint_items.get(joint_id)
        return item.pos() if item else None

    def get_all_joint_positions(self) -> dict[str, QPointF]:
        """Returns a dictionary of all current joint positions {id: QPointF}."""
        return {id: item.pos() for id, item in self._joint_items.items()}

    def highlight_joints(self, joint_ids: list[str], color: str = "orange") -> None:
        """Highlight specific joints with the given color."""
        highlight_color = QColor(color)
        for joint_id in joint_ids:
            if joint_id in self._joint_items:
                self._highlighted_joints.add(joint_id)
                self._joint_items[joint_id].setBrush(QBrush(highlight_color))
        logging.debug(f"Highlighted joints: {joint_ids} with color {color}")

    def clear_highlights(self) -> None:
        """Clear all joint highlights and restore default colors."""
        for joint_id in self._highlighted_joints:
            if joint_id in self._joint_items:
                # Find original color from cached data
                original_color = "red"  # Default
                for cached_joint in self._joints_data_cache:
                    if cached_joint["id"] == joint_id:
                        original_color = cached_joint.get("color", "red")
                        break
                self._joint_items[joint_id].setBrush(QBrush(QColor(original_color)))
        self._highlighted_joints.clear()
        logging.debug("Cleared all joint highlights")

    def set_joint_bend_direction(self, joint_id: str, bend_angle: float) -> None:
        """Set the bend direction for a joint (in radians)."""
        self._joint_bend_directions[joint_id] = bend_angle
        logging.debug(f"Set bend direction for joint {joint_id}: {bend_angle} radians")

    def get_joint_bend_direction(self, joint_id: str) -> float:
        """Get the bend direction for a joint (in radians). Returns 0 if not set."""
        return self._joint_bend_directions.get(joint_id, 0.0)

    def toggle_joint_bend_direction(self, joint_id: str) -> float:
        """Toggle the bend direction for a joint (flip by 180 degrees)."""
        current_angle = self.get_joint_bend_direction(joint_id)
        new_angle = current_angle + 3.14159  # Add π radians (180 degrees)
        self.set_joint_bend_direction(joint_id, new_angle)
        self._update_arrow_for_joint(joint_id)
        return new_angle

    def _create_arrow_polygon(self, joint_id: str) -> QPolygonF:
        """Create an arrow polygon for a joint's bend direction."""
        bend_angle = self.get_joint_bend_direction(joint_id)

        # Create arrow points relative to joint center
        arrow_length = self.ARROW_SIZE
        arrow_width = self.ARROW_SIZE * 0.6

        # Arrow points (pointing right initially)
        points = [
            QPointF(0, 0),  # Arrow base
            QPointF(arrow_length, 0),  # Arrow tip
            QPointF(arrow_length * 0.7, -arrow_width / 2),  # Upper arrow head
            QPointF(arrow_length, 0),  # Back to tip
            QPointF(arrow_length * 0.7, arrow_width / 2),  # Lower arrow head
            QPointF(arrow_length, 0),  # Back to tip
        ]

        # Rotate points by bend angle
        rotated_points = []
        cos_angle = math.cos(bend_angle)
        sin_angle = math.sin(bend_angle)

        for point in points:
            rotated_x = point.x() * cos_angle - point.y() * sin_angle
            rotated_y = point.x() * sin_angle + point.y() * cos_angle
            rotated_points.append(QPointF(rotated_x, rotated_y))

        return QPolygonF(rotated_points)

    def _update_arrow_for_joint(self, joint_id: str) -> None:
        """Update or create arrow visualization for a joint."""
        if joint_id not in self._joint_items:
            return

        joint_item = self._joint_items[joint_id]

        # Remove existing arrow if it exists
        if joint_id in self._arrow_items:
            if self.scene():
                self.scene().removeItem(self._arrow_items[joint_id])
            del self._arrow_items[joint_id]

        # Create new arrow
        arrow_polygon = self._create_arrow_polygon(joint_id)
        arrow_item = QGraphicsPolygonItem(arrow_polygon, parent=self)
        arrow_item.setPos(joint_item.pos())
        arrow_item.setBrush(QBrush(QColor("yellow")))
        arrow_item.setPen(QPen(Qt.GlobalColor.black, 1))
        arrow_item.setZValue(self.joint_z_value + 1)  # Above joints

        # Make arrow non-selectable so clicks go through to joint
        arrow_item.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, False)

        self._arrow_items[joint_id] = arrow_item
        logging.debug(
            f"Updated arrow for joint {joint_id} at angle {self.get_joint_bend_direction(joint_id)}"
        )

    def show_joint_bend_direction(self, joint_id: str) -> None:
        """Show the bend direction arrow for a joint."""
        if joint_id not in self._joint_items:
            return

        # Set default bend direction if not set
        if joint_id not in self._joint_bend_directions:
            self.set_joint_bend_direction(joint_id, 0.0)  # Default to right

        self._update_arrow_for_joint(joint_id)

    def hide_joint_bend_direction(self, joint_id: str) -> None:
        """Hide the bend direction arrow for a joint."""
        if joint_id in self._arrow_items:
            if self.scene():
                self.scene().removeItem(self._arrow_items[joint_id])
            del self._arrow_items[joint_id]

    def _clear_all_arrows(self) -> None:
        """Clear all arrow visualizations."""
        for arrow_item in list(self._arrow_items.values()):
            try:
                if self.scene():
                    self.scene().removeItem(arrow_item)
                # Ensure arrow is properly deleted
                arrow_item.setParent(None)
                arrow_item.deleteLater() if hasattr(arrow_item, "deleteLater") else None
            except RuntimeError:
                # Item might already be deleted
                pass
        self._arrow_items.clear()

    def cleanup(self) -> None:
        """Perform comprehensive cleanup of all resources."""
        logging.debug("SkeletonItem: Performing comprehensive cleanup")

        # Clear all visuals
        self._clear_visuals()

        # Clear cached data
        self._joints_data_cache.clear()
        self._hierarchy_cache.clear()

        # Disconnect any signals if they exist
        if hasattr(self, "signals") and self.signals:
            try:
                # Disconnect all signals
                self.signals.joint_clicked.disconnect()
                self.signals.joint_double_clicked.disconnect()
            except (RuntimeError, TypeError):
                # Signals might already be disconnected
                pass

        # Remove from parent and scene
        if self.scene():
            try:
                self.scene().removeItem(self)
            except RuntimeError:
                pass

        if self.parentItem():
            try:
                self.setParentItem(None)
            except RuntimeError:
                pass

        # Force garbage collection
        import gc

        gc.collect()

        logging.debug("SkeletonItem: Cleanup completed")

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press events on joints."""
        # Check if click is on a joint
        clicked_joint_id = self._get_joint_at_position(event.pos())

        if clicked_joint_id:
            self.signals.joint_clicked.emit(clicked_joint_id)

            # Show bend direction arrow on single click
            self.show_joint_bend_direction(clicked_joint_id)

            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse double-click events on joints."""
        # Check if double-click is on a joint
        clicked_joint_id = self._get_joint_at_position(event.pos())

        if clicked_joint_id:
            self.signals.joint_double_clicked.emit(clicked_joint_id)

            # Toggle bend direction on double-click only if auto-toggle is enabled
            if self.auto_toggle_bend_on_double_click:
                self.toggle_joint_bend_direction(clicked_joint_id)

            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _get_joint_at_position(self, pos: QPointF) -> str | None:
        """Find which joint (if any) is at the given position."""
        for joint_id, joint_item in self._joint_items.items():
            joint_pos = joint_item.pos()
            distance = math.sqrt((pos.x() - joint_pos.x()) ** 2 + (pos.y() - joint_pos.y()) ** 2)
            if distance <= self.JOINT_RADIUS:
                return joint_id
        return None
