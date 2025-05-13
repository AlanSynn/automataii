import logging
import cv2
import numpy as np
from PyQt6.QtWidgets import QGraphicsItem
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

    def boundingRect(self):
        """Return the bounding rect of the part, relative to the item's local origin (0,0)."""
        if self.pixmap:
            return QRectF(self.pixmap.rect())
        elif not self.shape_path_for_drawing.isEmpty():
            return self.shape_path_for_drawing.boundingRect()
        return QRectF(-5, -5, 10, 10)

    def shape(self):
        """Return the precise shape of the item for collision detection and interactions."""
        return self.shape_path_for_drawing

    def paint(self, painter: QPainter, option, widget):
        """Paint the character part"""
        pen = QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine) if self.isSelected() else QPen(Qt.GlobalColor.black, 1)
        painter.setPen(pen)

        if self.pixmap:
            painter.drawPixmap(0, 0, self.pixmap)

        if not self.shape_path_for_drawing.isEmpty():
            if self.isSelected() or self.is_hover:
                brush_color = QColor(255, 255, 0, 40)
            else:
                try:
                    brush_color = QColor(self.part_info.fill_color)
                except ValueError:
                     logging.warning(f"Invalid fill color for {self.part_info.name}: {self.part_info.fill_color}. Using default.")
                     brush_color = QColor('rgba(128,128,128,0.5)')
                brush_color.setAlpha(100)

            painter.setBrush(QBrush(brush_color))
            painter.drawPath(self.shape_path_for_drawing)

        if self.is_fixed:
            painter.setPen(QPen(Qt.GlobalColor.red, 2))
            painter.setBrush(QBrush(Qt.GlobalColor.red))
            painter.drawEllipse(QPointF(0, 0), 5, 5)

        if self.end_effector_offset:
             self._update_end_effector_marker()

    def _update_end_effector_marker(self):
        """Update the visual marker for end effector"""
        if not self.end_effector_offset or not self.scene():
            return

        if self.end_effector_marker:
            self.scene().removeItem(self.end_effector_marker)
            self.end_effector_marker = None

        self.end_effector_marker = self.scene().addEllipse(
            -4, -4, 8, 8,
            QPen(Qt.GlobalColor.red, 2),
            QBrush(Qt.GlobalColor.yellow)
        )
        self.end_effector_marker.setParentItem(self)
        self.end_effector_marker.setPos(self.end_effector_offset)
        self.end_effector_marker.setZValue(self.zValue() + 1)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        logging.debug(f"{self.part_info.name} clicked at local pos: {event.pos()}")

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

        if self.motion_path_visual_item and self.motion_path_visual_item.scene():
            self.scene().removeItem(self.motion_path_visual_item)
            self.motion_path_visual_item = None

        if path and not path.isEmpty() and self.scene():
            pen = QPen(QColor(0, 180, 0, 120), 1.5, Qt.PenStyle.SolidLine)
            self.motion_path_visual_item = self.scene().addPath(path, pen)
            self.motion_path_visual_item.setZValue(100)
            logging.debug(f"Added persistent motion path visual for {self.part_info.name}")

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