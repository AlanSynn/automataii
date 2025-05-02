import logging
import cv2
import numpy as np
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath, QTransform, QImage, QPolygonF
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF

class CharacterPartItem(QGraphicsItem):
    """Graphical representation of a character part"""
    def __init__(self, part_info, parent=None):
        super().__init__(parent)
        self.part_info = part_info

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self.is_fixed = False
        self.is_hover = False
        self.setZValue(part_info.z_value)

        self.pixmap = None
        self.image_contour_path = None
        if hasattr(part_info, 'image_path') and part_info.image_path:
            try:
                self.pixmap = QPixmap(part_info.image_path)
                if self.pixmap.isNull():
                    logging.warning(f"Failed to load image: {part_info.image_path}")
                    self.pixmap = None
                else:
                    try:
                        qimage = self.pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                        width = qimage.width()
                        height = qimage.height()
                        ptr = qimage.constBits()
                        ptr.setsize(height * width * 4)
                        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4))

                        alpha_channel = arr[:, :, 3]
                        blurred_alpha = cv2.GaussianBlur(alpha_channel, (5, 5), 0)
                        _, thresh = cv2.threshold(blurred_alpha, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        kernel = np.ones((3,3), np.uint8)
                        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations = 2)
                        contours, _ = cv2.findContours(opening, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                        if contours:
                            largest_contour = max(contours, key=cv2.contourArea)
                            epsilon = 0.005 * cv2.arcLength(largest_contour, True)
                            approx_contour = cv2.approxPolyDP(largest_contour, epsilon, True)
                            polygon = QPolygonF([QPointF(p[0][0], p[0][1]) for p in approx_contour])
                            contour_path = QPainterPath()
                            contour_path.addPolygon(polygon)
                            contour_path.closeSubpath()
                            self.image_contour_path = contour_path
                            logging.debug(f"Generated blurred & approximated contour path for {self.part_info.name}")
                        else:
                            logging.warning(f"No contours found in image for {self.part_info.name}")

                    except Exception as contour_err:
                         logging.error(f"Error detecting contour for {self.part_info.name}: {contour_err}")

            except Exception as e:
                logging.error(f"Error loading image {part_info.image_path}: {e}")
                self.pixmap = None

        self.motion_path = None
        self.motion_path_visual_item = None
        self.mechanism_path = None
        self.mechanism_path_item = None

        self.end_effector_offset = None
        self.end_effector_marker = None
        self.ik_target_point = None

        self.child_joints = []

        self.shape_path_for_drawing = QPainterPath()
        original_path = part_info.qpainter_path
        roi = part_info.roi

        if self.image_contour_path:
            self.shape_path_for_drawing = QPainterPath(self.image_contour_path)
            logging.debug(f"Using image contour for shape: {self.part_info.name}")
        elif original_path and not original_path.isEmpty():
            if roi and isinstance(roi, (list, tuple)) and len(roi) == 4:
                try:
                    x_min, y_min = float(roi[0]), float(roi[1])
                    self.shape_path_for_drawing = original_path.translated(-x_min, -y_min)
                    logging.debug(f"Using translated SVG path for shape: '{self.part_info.name}' by (-{x_min}, -{y_min})")
                except (ValueError, TypeError):
                    logging.warning(f"Invalid ROI for {self.part_info.name}: {roi}. Using original SVG path coordinates.")
                    self.shape_path_for_drawing = QPainterPath(original_path)
            else:
                logging.debug(f"No ROI found for {self.part_info.name}. Using original SVG path coordinates.")
                self.shape_path_for_drawing = QPainterPath(original_path)
        else:
             logging.warning(f"No image contour or SVG path found for {self.part_info.name}. Shape path will be empty.")

        self._path_points = []

        # Anchor point initialization order fixed
        self.is_anchor_visible = False # Define this first
        self._anchor_radius = 5
        self._dragging_anchor = False
        # Initialize _anchor_item to a basic state or None.
        # Its full setup might depend on anchor_offset, which depends on boundingRect.
        self._anchor_item = QGraphicsEllipseItem(-self._anchor_radius, -self._anchor_radius,
                                                 self._anchor_radius * 2, self._anchor_radius * 2, self)
        self._anchor_item.setPen(QPen(QColor("red"), 2))
        self._anchor_item.setBrush(QBrush(QColor("pink")))
        self._anchor_item.setZValue(self.zValue() + 2)
        self._anchor_item.setVisible(False) # Initially hidden, visibility controlled by is_anchor_visible and selection

        # Now that is_anchor_visible and _anchor_item are defined, boundingRect can be called safely.
        self.anchor_offset = self.boundingRect().center()
        self.setTransformOriginPoint(self.anchor_offset)
        self._anchor_item.setPos(self.anchor_offset) # Set position after anchor_offset is calculated

    def boundingRect(self):
        """Return the bounding rect of the part, relative to the item's local origin (0,0)."""
        base_rect = QRectF()
        if self.pixmap:
            base_rect = QRectF(self.pixmap.rect())
        elif not self.shape_path_for_drawing.isEmpty():
            base_rect = self.shape_path_for_drawing.boundingRect()
        else:
            base_rect = QRectF(-5, -5, 10, 10)

        # Ensure bounding rect includes anchor point if visible/active
        if self.is_anchor_visible and self._anchor_item:
            anchor_rect = self._anchor_item.boundingRect().translated(self.anchor_offset)
            return base_rect.united(anchor_rect)
        return base_rect

    def shape(self):
        """Return the precise shape of the item for collision detection and interactions."""
        return self.shape_path_for_drawing

    def paint(self, painter: QPainter, option, widget):
        """Paint the character part"""
        pen = QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine) if self.isSelected() else QPen(Qt.GlobalColor.black, 1)
        painter.setPen(pen)

        if self.pixmap:
            painter.drawPixmap(0, 0, self.pixmap)
            # If pixmap is drawn, we might still want a selection border
            if self.isSelected():
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(self.shape_path_for_drawing) # Draw border based on shape

        if not self.shape_path_for_drawing.isEmpty() and not self.pixmap : # Draw shape only if no pixmap
            if self.isSelected() or self.is_hover:
                brush_color = QColor(255, 255, 0, 40)
            else:
                try:
                    brush_color = QColor(self.part_info.fill_color)
                except (ValueError, AttributeError): # Added AttributeError
                     logging.warning(f"Invalid fill color for {self.part_info.name}: {self.part_info.fill_color}. Using default.")
                     brush_color = QColor('rgba(128,128,128,0.5)') # Ensure valid default
                # Ensure alpha is reasonable if not specified in fill_color string
                if brush_color.alpha() == 255: # If fully opaque from string
                    brush_color.setAlpha(100) # Apply custom alpha

            painter.setPen(pen) # Set pen for shape path
            painter.setBrush(QBrush(brush_color))
            painter.drawPath(self.shape_path_for_drawing)

        if self.is_fixed:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.red))
            fixed_marker_pos = self.anchor_offset # Draw fixed marker at anchor
            painter.drawEllipse(fixed_marker_pos, 3, 3) # Smaller fixed marker

        # Update anchor item position and visibility before paint
        if self._anchor_item:
            self._anchor_item.setPos(self.anchor_offset)
            self._anchor_item.setVisible(self.is_anchor_visible and self.isSelected())

        if self.end_effector_offset:
             self._update_end_effector_marker()

    def _update_end_effector_marker(self):
        """Update the visual marker for end effector"""
        if not self.end_effector_offset or not self.scene():
            if self.end_effector_marker and self.end_effector_marker.parentItem() == self:
                self.end_effector_marker.setParentItem(None) # Remove from parent
                if self.scene(): self.scene().removeItem(self.end_effector_marker)
                self.end_effector_marker = None
            return

        if not self.end_effector_marker:
            self.end_effector_marker = QGraphicsEllipseItem(
                -4, -4, 8, 8,
            )
            self.end_effector_marker.setPen(QPen(Qt.GlobalColor.red, 2))
            self.end_effector_marker.setBrush(QBrush(Qt.GlobalColor.yellow))
            self.end_effector_marker.setParentItem(self) # Parent it to this item
            self.end_effector_marker.setZValue(self.zValue() + 1) # On top of this part

        self.end_effector_marker.setPos(self.end_effector_offset)

    def mousePressEvent(self, event):
        # Check if anchor is clicked
        if self.is_anchor_visible and self.isSelected() and self._anchor_item.isVisible() and \
           self._anchor_item.contains(self._anchor_item.mapFromParent(event.pos())):
            self._dragging_anchor = True
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False) # Disable item movement while dragging anchor
            logging.debug(f"Anchor drag started for {self.part_info.name}")
            event.accept()
            return

        super().mousePressEvent(event)
        logging.debug(f"{self.part_info.name} clicked at local pos: {event.pos()}")

    def mouseMoveEvent(self, event):
        if self._dragging_anchor:
            new_anchor_pos = event.pos() # This is in item's local coordinates
            # Optional: Clamp new_anchor_pos to be within item's bounding rectangle
            # item_bounds = self.boundingRect()
            # new_anchor_pos.setX(max(item_bounds.left(), min(new_anchor_pos.x(), item_bounds.right())))
            # new_anchor_pos.setY(max(item_bounds.top(), min(new_anchor_pos.y(), item_bounds.bottom())))

            if self.anchor_offset != new_anchor_pos:
                self.prepareGeometryChange() # Important for QGraphicsItem
                self.anchor_offset = new_anchor_pos
                self.setTransformOriginPoint(self.anchor_offset)
                if self._anchor_item:
                    self._anchor_item.setPos(self.anchor_offset)
                self.update() # Repaint
                # logging.debug(f"Anchor for {self.part_info.name} moved to {self.anchor_offset}") # Can be too verbose
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_anchor:
            self._dragging_anchor = False
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True) # Re-enable item movement
            logging.debug(f"Anchor drag ended for {self.part_info.name} at {self.anchor_offset}")
            event.accept()
            # Emit a signal if needed, e.g., anchor_moved_signal.emit(self.part_info.name, self.anchor_offset)
            return
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Highlight effect when mouse hovers over part"""
        self.is_hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Remove highlight when mouse leaves"""
        self.is_hover = False
        self.update()
        super().hoverLeaveEvent(event)

    def update_motion_path_visual(self, path: QPainterPath = None):
        """Updates the persistent visual representation of the assigned motion path."""
        self.motion_path = path

        if path and not path.isEmpty():
            center_offset = self.boundingRect().center()
            if self.end_effector_offset != center_offset:
                self.end_effector_offset = center_offset
                self._update_end_effector_marker()
                logging.debug(f"Set end effector offset for {self.part_info.name} to center: {center_offset}")
        else:
            if self.end_effector_offset is not None:
                self.end_effector_offset = None
                self._update_end_effector_marker()

        if self.motion_path_visual_item:
            # Properly remove the old visual item.
            # If it's a child, setParentItem(None) is enough to remove it from this parent.
            # If it was added to scene directly (old method), scene().removeItem() is needed.
            if self.motion_path_visual_item.parentItem() == self:
                self.motion_path_visual_item.setParentItem(None)
            elif self.motion_path_visual_item.scene(): # Fallback for items not parented as expected
                self.scene().removeItem(self.motion_path_visual_item)
            # The QGraphicsPathItem object will be garbage collected by Python.
            self.motion_path_visual_item = None

        if path and not path.isEmpty():
            pen = QPen(QColor(0, 180, 0, 120), 10, Qt.PenStyle.SolidLine) # Current thickness from file

            # Create the QGraphicsPathItem and set self (CharacterPartItem) as its parent.
            # This makes the path item's coordinates relative to the parent item.
            new_path_item = QGraphicsPathItem(path, self)
            new_path_item.setPen(pen)
            # Z-value for child items is relative to the parent.
            # A small positive value ensures it's drawn on top of the parent's own graphics.
            new_path_item.setZValue(0.1)

            self.motion_path_visual_item = new_path_item
            # The item is automatically added to the scene if the parent (self) is in a scene.
            logging.debug(f"Added persistent motion path visual for {self.part_info.name} as child item")

    def set_motion_path(self, path, end_effector_point=None):
        """DEPRECATED: Use update_motion_path_visual instead. Kept for potential compatibility."""
        logging.warning("set_motion_path is deprecated. Use update_motion_path_visual.")

    def set_mechanism_path(self, path):
        """Set mechanism-generated path for this part and visualize it"""
        if path is None:
            if self.mechanism_path_item and self.scene():
                self.scene().removeItem(self.mechanism_path_item)
            self.mechanism_path_item = None
            self.mechanism_path = None
            return

        self.mechanism_path = QPainterPath(path)

        if self.mechanism_path_item and self.scene():
            self.scene().removeItem(self.mechanism_path_item)
            self.mechanism_path_item = None

        if self.scene():
            pen = QPen(QColor(0, 120, 255), 3, Qt.PenStyle.SolidLine)
            self.mechanism_path_item = self.scene().addPath(self.mechanism_path, pen)
            self.mechanism_path_item.setZValue(self.zValue() - 0.2)

        self._update_end_effector_marker()

    def start_select_end_effector(self):
        """Starts the mode to select the end effector point on the selected part."""
        self._path_points = []

    def get_center_offset(self):
        """Calculates the offset from the item's origin (0,0) to its visual center."""
        return self.boundingRect().center()

    def set_anchor_visibility(self, visible: bool):
        self.is_anchor_visible = visible
        if self._anchor_item:
            self._anchor_item.setVisible(visible and self.isSelected()) # Only show if selected
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemTransformOriginPointHasChanged:
            # If external code changes transform origin, update our anchor_offset
            new_origin = self.transformOriginPoint()
            if new_origin != self.anchor_offset:
                self.prepareGeometryChange()
                self.anchor_offset = new_origin
                if self._anchor_item:
                    self._anchor_item.setPos(self.anchor_offset)
        return super().itemChange(change, value)
