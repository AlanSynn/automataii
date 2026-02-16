import logging
import math
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsObject,
    QGraphicsPolygonItem,
)

from automataii.config.z_indices import (
    Z_SKELETON_BONES,
    Z_SKELETON_JOINTS,
    Z_SKELETON_MECHANISM_BONES,
    Z_SKELETON_MECHANISM_JOINTS,
)


class SkeletonGraphicsItem(QGraphicsObject):
    """
    A QGraphicsObject to display a character's skeleton (joints and bones).
    Changed to QGraphicsObject to support signals.
    """

    # Signal emitted when a joint is clicked (joint_id, new_bend_direction)
    joint_clicked = pyqtSignal(str, float)

    JOINT_RADIUS = 5
    BONE_PEN_WIDTH = 2

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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

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
        self._bend_arrows: dict[str, QGraphicsPolygonItem] = {}  # joint_id -> arrow polygon
        self._joint_bend_directions: dict[
            str, float
        ] = {}  # joint_id -> bend direction (1.0 or -1.0)

        # Cache of the original structural data for rebuilding/updating bones
        self._joints_data_cache: list[dict[str, Any]] = []
        self._hierarchy_cache: dict[str, list[str]] = {}

        if skeleton_data and hierarchy:
            self.load_skeleton_data(skeleton_data, hierarchy)
        else:
            logging.info("SkeletonGraphicsItem: Initialized without skeleton data.")

    def _clear_visuals(self):
        """Clears all joint and bone QGraphicsItems from the scene and internal tracking."""
        logging.debug(
            f"SkeletonItem:_clear_visuals - Clearing {len(self._joint_items)} joints and {len(self._bone_items)} bones."
        )
        if self.scene():
            for item in self._joint_items.values():
                self.scene().removeItem(item)
            for item in self._bone_items:
                self.scene().removeItem(item)
            for item in self._bend_arrows.values():
                self.scene().removeItem(item)
        self._joint_items.clear()
        self._bone_items.clear()
        self._bend_arrows.clear()
        self._joint_bend_directions.clear()

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
            elif isinstance(pos_data, list | tuple) and len(pos_data) == 2:
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

            # Get bend direction (default to 1.0 if not specified)
            bend_direction = joint_info.get("bend_direction", 1.0)
            self._joint_bend_directions[joint_id] = bend_direction

            # Cache the processed joint info
            self._joints_data_cache.append(
                {
                    "id": joint_id,
                    "position": position,  # Store the QPointF
                    "parent": joint_info.get("parent"),  # Store original parent ID
                    "name": joint_info.get("name", joint_id),
                    "color": joint_info.get("color", "blue"),  # Default color blue
                    "bend_direction": bend_direction,
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

            # Set color based on bend direction (only for elbow/knee joints)
            if bend_direction is not None and bend_direction < 0:
                joint_color = QColor("green")  # Green for inverted
            else:
                joint_color = QColor("blue")  # Blue for default or joints without bend direction

            joint_item.setBrush(QBrush(joint_color))
            joint_item.setPen(QPen(Qt.GlobalColor.black, 1))
            joint_item.setZValue(self.joint_z_value)  # Use configured Z-value
            joint_item.setData(0, joint_id)  # Store joint_id in the item's data
            self._joint_items[joint_id] = joint_item

        logging.debug(
            f"SkeletonItem:load_skeleton_data - Created {len(self._joint_items)} joint items."
        )
        self._update_bone_lines()  # Create bones based on the newly loaded joints and hierarchy
        self._update_bend_arrows()  # Create bend direction arrows
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

        # First pass: collect joints that need updating (avoid prepareGeometryChange if nothing changed)
        joints_to_update: list[tuple[str, QPointF]] = []
        for joint_id, pos_tuple in joint_positions.items():
            if joint_id in self._joint_items:
                new_pos = QPointF(pos_tuple[0], pos_tuple[1])
                current_pos = self._joint_items[joint_id].pos()
                if new_pos != current_pos:
                    joints_to_update.append((joint_id, new_pos))
            else:
                logging.warning(
                    f"SkeletonItem:set_animated_pose - Joint ID '{joint_id}' from animation data not found in loaded joint items."
                )

        if not joints_to_update:
            logging.debug(
                "SkeletonItem:set_animated_pose - No actual joint position changes detected."
            )
            return

        # Only call prepareGeometryChange once, before making changes
        self.prepareGeometryChange()

        # Second pass: apply updates
        for joint_id, new_pos in joints_to_update:
            self._joint_items[joint_id].setPos(new_pos)

            # Update the cached position for this joint
            for cached_joint in self._joints_data_cache:
                if cached_joint["id"] == joint_id:
                    cached_joint["position"] = new_pos
                    break

        self._update_bone_lines()
        self._update_bend_arrows()
        self.update()

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

    def paint(self, painter, option, widget=None):
        """
        Paint method required by QGraphicsObject.

        This item doesn't paint itself directly - it uses child items
        (QGraphicsEllipseItem for joints, QGraphicsLineItem for bones)
        which handle their own painting.
        """
        # No direct painting - child items handle their own rendering
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

    def _update_bend_arrows(self):
        """
        Update bend direction arrows for joints that have children.

        Optimized: Reuses existing arrow items instead of recreating them.
        """
        if not self._hierarchy_cache:
            # Hide all existing arrows if no hierarchy
            for arrow in self._bend_arrows.values():
                arrow.setVisible(False)
            return

        # Track used arrows to hide unused ones later
        used_parent_ids = set()

        # Create arrows only for elbow/knee joints that have children
        for parent_id, child_ids in self._hierarchy_cache.items():
            if not child_ids or parent_id not in self._joint_items:
                continue

            # Only show bend arrows for elbow/knee joints
            if "elbow" not in parent_id.lower() and "knee" not in parent_id.lower():
                continue

            parent_item = self._joint_items[parent_id]
            parent_pos = parent_item.pos()

            # Calculate average direction to children
            avg_direction = QPointF(0, 0)
            valid_children = 0

            for child_id in child_ids:
                if child_id in self._joint_items:
                    child_pos = self._joint_items[child_id].pos()
                    direction = child_pos - parent_pos
                    if direction.manhattanLength() > 0.001:  # Avoid zero-length vectors
                        avg_direction += direction
                        valid_children += 1

            if valid_children == 0:
                continue

            # Normalize average direction
            avg_direction /= valid_children
            length = math.sqrt(avg_direction.x() ** 2 + avg_direction.y() ** 2)
            if length < 0.001:
                continue

            avg_direction /= length

            # Get bend direction for this joint (default to 1.0 for elbow/knee)
            bend_dir = self._joint_bend_directions.get(parent_id, 1.0)

            # Calculate perpendicular direction (for bend)
            perp_direction = QPointF(-avg_direction.y(), avg_direction.x()) * bend_dir

            # Create arrow polygon points
            arrow_length = 20
            arrow_width = 8

            # Arrow tip position
            arrow_tip = parent_pos + perp_direction * arrow_length

            # Arrow base positions
            base_direction = perp_direction * (arrow_length - arrow_width)
            side_direction = avg_direction * (arrow_width / 2)

            arrow_base1 = parent_pos + base_direction + side_direction
            arrow_base2 = parent_pos + base_direction - side_direction

            # Polygon geometry
            arrow_polygon = QPolygonF([parent_pos, arrow_base1, arrow_tip, arrow_base2])

            # Determine color
            if bend_dir < 0:
                arrow_color = QColor(0, 200, 0, 150)  # Green for inverted
            else:
                arrow_color = QColor(0, 100, 200, 150)  # Blue for default

            # Update or create arrow item
            if parent_id in self._bend_arrows:
                arrow_item = self._bend_arrows[parent_id]
                arrow_item.setPolygon(arrow_polygon)
                arrow_item.setBrush(QBrush(arrow_color))
                arrow_item.setVisible(True)
            else:
                arrow_item = QGraphicsPolygonItem(arrow_polygon, parent=self)
                arrow_item.setBrush(QBrush(arrow_color))
                arrow_item.setPen(QPen(Qt.GlobalColor.darkGray, 1))
                arrow_item.setZValue(self.joint_z_value - 1)  # Slightly below joints
                self._bend_arrows[parent_id] = arrow_item

            used_parent_ids.add(parent_id)

        # Hide unused arrows
        for parent_id, arrow in self._bend_arrows.items():
            if parent_id not in used_parent_ids:
                arrow.setVisible(False)

    def mousePressEvent(self, event):
        """Handle mouse press events on joints."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Find which joint was clicked
            click_pos = event.pos()

            for joint_id, joint_item in self._joint_items.items():
                joint_pos = joint_item.pos()
                # Check if click is within joint circle
                distance = math.sqrt(
                    (click_pos.x() - joint_pos.x()) ** 2 + (click_pos.y() - joint_pos.y()) ** 2
                )

                if distance <= self.JOINT_RADIUS:
                    # Only allow toggling bend direction for elbow/knee joints
                    if "elbow" in joint_id.lower() or "knee" in joint_id.lower():
                        # Toggle bend direction
                        current_dir = self._joint_bend_directions.get(joint_id, 1.0)
                        new_dir = -current_dir
                        self._joint_bend_directions[joint_id] = new_dir

                        # Update joint color
                        if new_dir < 0:
                            joint_color = QColor("green")  # Green for inverted
                        else:
                            joint_color = QColor("blue")  # Blue for default

                        joint_item.setBrush(QBrush(joint_color))

                        # Update cached data
                        for cached_joint in self._joints_data_cache:
                            if cached_joint["id"] == joint_id:
                                cached_joint["bend_direction"] = new_dir
                                break

                        # Update arrows
                        self._update_bend_arrows()

                        # Emit signal
                        self.joint_clicked.emit(joint_id, new_dir)

                        logging.info(f"Joint '{joint_id}' bend direction changed to {new_dir}")
                    else:
                        logging.debug(
                            f"Joint '{joint_id}' is not an elbow/knee joint, ignoring bend direction toggle"
                        )

                    event.accept()
                    return

        # Call parent implementation
        super().mousePressEvent(event)

    def set_joint_bend_direction(self, joint_id: str, direction: float):
        """Set the bend direction for a specific joint."""
        if joint_id in self._joint_items:
            self._joint_bend_directions[joint_id] = direction

            # Update joint color
            joint_item = self._joint_items[joint_id]
            if direction < 0:
                joint_color = QColor("green")  # Green for inverted
            else:
                joint_color = QColor("blue")  # Blue for default

            joint_item.setBrush(QBrush(joint_color))

            # Update cached data
            for cached_joint in self._joints_data_cache:
                if cached_joint["id"] == joint_id:
                    cached_joint["bend_direction"] = direction
                    break

            # Update arrows
            self._update_bend_arrows()
            self.update()
