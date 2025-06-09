"""Rendering logic for different mechanism type previews."""

from math import cos, sin, radians
from typing import Tuple

from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import (
    QPen,
    QBrush,
    QColor,
    QPainterPath,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsPathItem,
)

from .constants import (
    BITTERSWEET, SUNGLOW, YELLOW_GREEN, STEEL_BLUE, ULTRA_VIOLET
)


class MechanismPreviewRenderer:
    """Handles rendering of different mechanism types."""
    
    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self.dark_offset_x = 1.5
        self.dark_offset_y = 1.5
    
    def render_cam_preview(self, bounds: QRectF) -> None:
        """Render a cam and follower mechanism preview."""
        preview_scale = min(bounds.width(), bounds.height()) / 280.0
        base_radius = 80 * preview_scale
        eccentric_radius = 60 * preview_scale
        angle_offset_rad = radians(45)
        
        cam_center_x = bounds.center().x()
        cam_center_y = bounds.center().y() - base_radius * 0.2
        
        ecc_offset_x = (base_radius - eccentric_radius) * 0.7 * cos(angle_offset_rad)
        ecc_offset_y = (base_radius - eccentric_radius) * 0.7 * sin(angle_offset_rad)
        
        eff_ecc_center_x = cam_center_x + ecc_offset_x
        eff_ecc_center_y = cam_center_y + ecc_offset_y
        
        # Draw cam back (shadow)
        self._draw_ellipse(
            eff_ecc_center_x - eccentric_radius + self.dark_offset_x,
            eff_ecc_center_y - eccentric_radius + self.dark_offset_y,
            eccentric_radius * 2,
            eccentric_radius * 2,
            ULTRA_VIOLET,
            Qt.PenStyle.NoPen
        )
        
        # Draw shaft back
        shaft_back_rad = base_radius * 0.25
        self._draw_ellipse(
            cam_center_x - shaft_back_rad + self.dark_offset_x,
            cam_center_y - shaft_back_rad + self.dark_offset_y,
            shaft_back_rad * 2,
            shaft_back_rad * 2,
            QColor(ULTRA_VIOLET).darker(130),
            Qt.PenStyle.NoPen
        )
        
        # Draw cam front
        self._draw_ellipse(
            eff_ecc_center_x - eccentric_radius,
            eff_ecc_center_y - eccentric_radius,
            eccentric_radius * 2,
            eccentric_radius * 2,
            STEEL_BLUE,
            QPen(Qt.GlobalColor.black, 1)
        )
        
        # Draw shaft front
        self._draw_ellipse(
            cam_center_x - shaft_back_rad,
            cam_center_y - shaft_back_rad,
            shaft_back_rad * 2,
            shaft_back_rad * 2,
            QColor(STEEL_BLUE).lighter(130),
            QPen(Qt.GlobalColor.black, 1)
        )
        
        # Draw follower
        follower_width = base_radius * 0.4
        follower_height = base_radius * 0.6
        follower_x = cam_center_x - follower_width / 2
        follower_y_contact = cam_center_y + base_radius * 0.4
        
        # Follower back
        self._draw_rect(
            follower_x + self.dark_offset_x,
            follower_y_contact + self.dark_offset_y,
            follower_width,
            follower_height,
            QColor(BITTERSWEET).darker(130),
            Qt.PenStyle.NoPen
        )
        
        # Follower front
        self._draw_rect(
            follower_x,
            follower_y_contact,
            follower_width,
            follower_height,
            BITTERSWEET,
            QPen(Qt.GlobalColor.black, 1)
        )
    
    def render_gear_preview(self, bounds: QRectF) -> None:
        """Render a gear pair mechanism preview."""
        center_x = bounds.center().x()
        center_y = bounds.center().y()
        preview_scale = min(bounds.width(), bounds.height()) / 220.0
        
        # First gear (larger)
        radius1 = 60 * preview_scale
        num_teeth1 = 18
        tooth_height1 = 15 * preview_scale
        
        # Second gear (smaller)
        radius2 = 40 * preview_scale
        num_teeth2 = 12
        tooth_height2 = 12 * preview_scale
        
        # Position gears to mesh
        gear1_x = center_x - radius1 * 0.8
        gear1_y = center_y
        gear2_x = gear1_x + radius1 + radius2 + (tooth_height1 + tooth_height2) * 0.5
        gear2_y = center_y
        
        # Draw first gear
        self._draw_gear(
            gear1_x, gear1_y, radius1, tooth_height1, num_teeth1,
            ULTRA_VIOLET, STEEL_BLUE, YELLOW_GREEN
        )
        
        # Draw second gear with phase offset
        phase_offset = 360.0 / num_teeth2 / 2
        self._draw_gear(
            gear2_x, gear2_y, radius2, tooth_height2, num_teeth2,
            QColor(BITTERSWEET).darker(130), BITTERSWEET, SUNGLOW,
            phase_offset
        )
    
    def render_linkage_preview(self, bounds: QRectF) -> None:
        """Render a 4-bar linkage mechanism preview."""
        preview_scale = min(bounds.width(), bounds.height()) / 280.0
        thickness = 20 * preview_scale
        
        center_x = bounds.center().x()
        center_y = bounds.center().y()
        
        # Define linkage points
        p0 = QPointF(center_x - 80 * preview_scale, center_y + 30 * preview_scale)
        p1 = QPointF(center_x - 60 * preview_scale, center_y - 40 * preview_scale)
        p2 = QPointF(center_x + 40 * preview_scale, center_y - 50 * preview_scale)
        p3 = QPointF(center_x + 80 * preview_scale, center_y + 25 * preview_scale)
        
        # Draw ground line
        self._draw_ground_line(bounds, max(p0.y(), p3.y()) + 20 * preview_scale)
        
        # Draw links
        links = [(p0, p1), (p1, p2), (p2, p3)]
        for start_pt, end_pt in links:
            self._draw_link(start_pt, end_pt, thickness, ULTRA_VIOLET, STEEL_BLUE)
        
        # Draw pivots
        pivot_radius = thickness * 0.8
        for pt in [p0, p1, p2, p3]:
            self._draw_pivot(pt, pivot_radius, SUNGLOW)
    
    def _draw_ellipse(self, x: float, y: float, width: float, height: float,
                      brush: QBrush, pen: QPen) -> None:
        """Helper to draw an ellipse."""
        ellipse = QGraphicsEllipseItem(0, 0, width, height)
        ellipse.setPos(x, y)
        ellipse.setBrush(brush)
        ellipse.setPen(pen)
        self.scene.addItem(ellipse)
    
    def _draw_rect(self, x: float, y: float, width: float, height: float,
                   brush: QBrush, pen: QPen) -> None:
        """Helper to draw a rectangle."""
        rect = QGraphicsRectItem(x, y, width, height)
        rect.setBrush(brush)
        rect.setPen(pen)
        self.scene.addItem(rect)
    
    def _draw_gear(self, x: float, y: float, radius: float, tooth_height: float,
                   num_teeth: int, back_color: QColor, front_color: QColor,
                   tooth_color: QColor, phase_offset: float = 0) -> None:
        """Helper to draw a gear with teeth."""
        outer_radius = radius + tooth_height / 2
        inner_radius = radius - tooth_height / 2
        
        # Back body
        self._draw_ellipse(
            x - outer_radius + self.dark_offset_x,
            y - outer_radius + self.dark_offset_y,
            outer_radius * 2,
            outer_radius * 2,
            back_color,
            QPen(Qt.PenStyle.NoPen)
        )
        
        # Front body
        self._draw_ellipse(
            x - outer_radius,
            y - outer_radius,
            outer_radius * 2,
            outer_radius * 2,
            front_color,
            QPen(Qt.GlobalColor.black, 1)
        )
        
        # Center hole
        center_hole_rad = inner_radius * 0.4
        self._draw_ellipse(
            x - center_hole_rad,
            y - center_hole_rad,
            center_hole_rad * 2,
            center_hole_rad * 2,
            QColor("white"),
            QPen(Qt.GlobalColor.black, 1)
        )
        
        # Draw teeth
        angle_step = 360.0 / num_teeth
        for i in range(num_teeth):
            angle = radians(i * angle_step + phase_offset)
            tooth_angle_width = radians(angle_step / 2 * 0.6)
            
            coords = [
                (inner_radius * cos(angle - tooth_angle_width / 2),
                 inner_radius * sin(angle - tooth_angle_width / 2)),
                (outer_radius * cos(angle - tooth_angle_width / 3),
                 outer_radius * sin(angle - tooth_angle_width / 3)),
                (outer_radius * cos(angle + tooth_angle_width / 3),
                 outer_radius * sin(angle + tooth_angle_width / 3)),
                (inner_radius * cos(angle + tooth_angle_width / 2),
                 inner_radius * sin(angle + tooth_angle_width / 2)),
            ]
            
            # Back tooth
            tooth_poly_back = QPolygonF()
            for px, py in coords:
                tooth_poly_back.append(QPointF(x + px + self.dark_offset_x,
                                               y + py + self.dark_offset_y))
            self.scene.addPolygon(
                tooth_poly_back,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(tooth_color).darker(130))
            )
            
            # Front tooth
            tooth_poly_front = QPolygonF()
            for px, py in coords:
                tooth_poly_front.append(QPointF(x + px, y + py))
            self.scene.addPolygon(
                tooth_poly_front,
                QPen(Qt.GlobalColor.black, 0.5),
                QBrush(tooth_color)
            )
    
    def _draw_link(self, start: QPointF, end: QPointF, thickness: float,
                   back_color: QColor, front_color: QColor) -> None:
        """Helper to draw a link between two points."""
        # Back link (shadow)
        path_back = QPainterPath()
        path_back.moveTo(start + QPointF(self.dark_offset_x, self.dark_offset_y))
        path_back.lineTo(end + QPointF(self.dark_offset_x, self.dark_offset_y))
        link_back = QGraphicsPathItem(path_back)
        pen_back = QPen(
            back_color, thickness, Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        )
        link_back.setPen(pen_back)
        self.scene.addItem(link_back)
        
        # Front link
        path_front = QPainterPath()
        path_front.moveTo(start)
        path_front.lineTo(end)
        link_front = QGraphicsPathItem(path_front)
        pen_front = QPen(
            front_color, thickness, Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        )
        link_front.setPen(pen_front)
        self.scene.addItem(link_front)
    
    def _draw_pivot(self, point: QPointF, radius: float, color: QColor) -> None:
        """Helper to draw a pivot point."""
        # Back pivot (shadow)
        self._draw_ellipse(
            point.x() - radius + self.dark_offset_x,
            point.y() - radius + self.dark_offset_y,
            radius * 2,
            radius * 2,
            QColor(color).darker(150),
            QPen(Qt.PenStyle.NoPen)
        )
        
        # Front pivot
        self._draw_ellipse(
            point.x() - radius,
            point.y() - radius,
            radius * 2,
            radius * 2,
            color,
            QPen(Qt.GlobalColor.black, 1)
        )
    
    def _draw_ground_line(self, bounds: QRectF, y_pos: float) -> None:
        """Helper to draw a ground line."""
        ground_line = QLineF(bounds.left() + 20, y_pos, bounds.right() - 20, y_pos)
        ground_path = QPainterPath()
        ground_path.moveTo(ground_line.p1())
        ground_path.lineTo(ground_line.p2())
        ground_item = QGraphicsPathItem(ground_path)
        ground_pen = QPen(QColor("#888888"), 2, Qt.PenStyle.DashLine)
        ground_item.setPen(ground_pen)
        self.scene.addItem(ground_item)