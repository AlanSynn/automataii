from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize, QPointF, QLineF, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath, QPolygonF, QTransform
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGroupBox,
    QSizePolicy,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsPathItem,
    QDialogButtonBox
)

# from automataii.utils.qt_helpers import create_round_rect_path # Not used in this version

class MechanismPreviewWidget(QGraphicsView):
    """A widget to display a preview of a single mechanism."""

    def __init__(self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(200, 150) # Fixed size for preview
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#e0e0e0")) # Light gray background for preview
        self._render_preview() # Render after background is set and scene is ready

    def _draw_user_motion_path(self, bounds: QRectF) -> None:
        """Draws the user's motion path, scaled and centered within the given bounds."""
        user_path_local = self.mechanism_data.get("user_motion_path_local")
        if not isinstance(user_path_local, QPainterPath) or user_path_local.isEmpty():
            return

        path_bounds = user_path_local.boundingRect()
        if path_bounds.width() == 0 or path_bounds.height() == 0:
            return

        # Scale the path to fit within 70% of the preview bounds, preserving aspect ratio
        target_rect = bounds.adjusted(bounds.width() * 0.15, bounds.height() * 0.15,
                                      -bounds.width() * 0.15, -bounds.height() * 0.15)

        scale_x = target_rect.width() / path_bounds.width()
        scale_y = target_rect.height() / path_bounds.height()
        scale = min(scale_x, scale_y)

        transform = QTransform()
        # 1. Translate path's top-left to origin
        transform.translate(-path_bounds.left(), -path_bounds.top())
        # 2. Scale
        transform.scale(scale, scale)
        # 3. Translate scaled path to be centered in target_rect
        scaled_path_bounds = transform.mapRect(path_bounds)
        transform.translate(target_rect.left() - scaled_path_bounds.left() + (target_rect.width() - scaled_path_bounds.width()) / 2,
                            target_rect.top() - scaled_path_bounds.top() + (target_rect.height() - scaled_path_bounds.height()) / 2)

        transformed_path = transform.map(user_path_local)

        path_item = QGraphicsPathItem(transformed_path)
        pen = QPen(QColor(100, 200, 100, 180), 1.5, Qt.PenStyle.DashLine) # Light green dashed line
        path_item.setPen(pen)
        path_item.setZValue(-1) # Draw behind the mechanism
        self.scene.addItem(path_item)

    def _render_preview(self) -> None:
        self.scene.clear()
        # Add a small margin for content within the view bounds
        margin = 5
        # Use self.viewport().rect() for accurate available drawing area after scrollbars etc.
        # However, since scrollbars are off, self.rect() is fine.
        view_rect_int = self.rect()
        view_rect_f = QRectF(view_rect_int) # Convert QRect to QRectF
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)

        # Set sceneRect to the viewable area to help with item positioning if items are added at (0,0)
        self.scene.setSceneRect(view_rect_f) # Use QRectF here

        # Common drawing parameters
        dark_offset_x = 1.5
        dark_offset_y = 1.5

        if not self.mechanism_data or not self.mechanism_data.get("type"):
            text_item = self.scene.addText("No Preview")
            text_item.setDefaultTextColor(Qt.black)
            # Center text in the view_rect (area inside margin)
            text_item.setPos(view_rect_adjusted_f.center() - text_item.boundingRect().center())
            return

        preview_type = self.mechanism_data.get("type")
        # Default to "Cam & Follower" if type is "cam" for consistency with generation
        if preview_type == "cam": preview_type = "Cam & Follower"


        if preview_type == "Cam & Follower":
            self._draw_cam_preview(dark_offset_x, dark_offset_y, view_rect_adjusted_f)
        elif preview_type == "4-Bar Linkage" or preview_type == "3-Bar Linkage" or preview_type == "linkage": # Handle generic "linkage" too
            self._draw_linkage_preview(dark_offset_x, dark_offset_y, view_rect_adjusted_f)
        elif preview_type == "Gears (Simple Pair)" or preview_type == "gears": # Handle generic "gears" too
            self._draw_gear_preview(dark_offset_x, dark_offset_y, view_rect_adjusted_f)
        else:
            text_item = self.scene.addText(f"Preview for \"{preview_type}\"\nnot implemented.")
            text_item.setDefaultTextColor(Qt.black)
            text_item.setPos(view_rect_adjusted_f.center() - text_item.boundingRect().center())

        # Draw user's motion path if available, after specific mechanism
        self._draw_user_motion_path(view_rect_adjusted_f)

        # Fit view to scene contents, respecting the view_rect
        # self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        # Ensure the entire sceneRect is visible
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)


    def _draw_cam_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic cam preview
        preview_scale = min(bounds.width(), bounds.height()) / 100.0
        base_radius = 30 * preview_scale
        eccentric_radius = 15 * preview_scale
        angle_offset_rad = _np_deg2rad(45) # Fixed angle for schematic

        # Use the adjusted bounds for drawing
        cam_center_x = bounds.center().x()
        cam_center_y = bounds.center().y() - base_radius * 0.2 # Shift up a bit to make space for follower

        ecc_offset_x = (base_radius - eccentric_radius) * 0.7 * _cos(angle_offset_rad) # further scale down offset
        ecc_offset_y = (base_radius - eccentric_radius) * 0.7 * _sin(angle_offset_rad)

        eff_ecc_center_x = cam_center_x + ecc_offset_x
        eff_ecc_center_y = cam_center_y + ecc_offset_y

        # Back
        cam_back = QGraphicsEllipseItem(0,0, eccentric_radius*2, eccentric_radius*2)
        cam_back.setPos(eff_ecc_center_x - eccentric_radius + dox, eff_ecc_center_y - eccentric_radius + doy)
        cam_back.setBrush(QColor("darkslateblue"))
        cam_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(cam_back)

        shaft_back_rad = base_radius*0.25
        shaft_back = QGraphicsEllipseItem(0,0, shaft_back_rad*2, shaft_back_rad*2)
        shaft_back.setPos(cam_center_x - shaft_back_rad + dox, cam_center_y - shaft_back_rad + doy)
        shaft_back.setBrush(QColor("dimgray"))
        shaft_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(shaft_back)

        # Front
        cam_front = QGraphicsEllipseItem(0,0, eccentric_radius*2, eccentric_radius*2)
        cam_front.setPos(eff_ecc_center_x - eccentric_radius, eff_ecc_center_y - eccentric_radius)
        cam_front.setBrush(QColor("mediumpurple"))
        cam_front.setPen(QPen(Qt.black, 1))
        self.scene.addItem(cam_front)

        shaft_front_rad = base_radius*0.25
        shaft_front = QGraphicsEllipseItem(0,0, shaft_front_rad*2, shaft_front_rad*2)
        shaft_front.setPos(cam_center_x - shaft_front_rad, cam_center_y - shaft_front_rad)
        shaft_front.setBrush(QColor("lightgray"))
        shaft_front.setPen(QPen(Qt.black, 1))
        self.scene.addItem(shaft_front)

        follower_width = base_radius * 0.4
        follower_height = base_radius * 0.8
        follower_x = cam_center_x - follower_width / 2
        follower_y_contact = eff_ecc_center_y + eccentric_radius + 2 # ensure contact

        # Make follower schematic and relative to cam size
        follower_width = base_radius * 0.5
        follower_height = base_radius * 0.7
        follower_x = cam_center_x - follower_width / 2
        # Adjust follower_y_contact if needed based on new base_radius relationship
        # For a generic preview, this should be fine, or tie it to cam_center_y more directly
        follower_y_contact = cam_center_y + base_radius * 0.5 # Example positioning

        follower_back = QGraphicsRectItem(follower_x + dox, follower_y_contact + doy, follower_width, follower_height)
        follower_back.setBrush(QColor("dimgray"))
        follower_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(follower_back)

        follower_front = QGraphicsRectItem(follower_x, follower_y_contact, follower_width, follower_height)
        follower_front.setBrush(QColor("lightsteelblue"))
        follower_front.setPen(QPen(Qt.black, 1))
        self.scene.addItem(follower_front)


    def _draw_gear_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic gear preview
        center_x = bounds.center().x()
        center_y = bounds.center().y()
        preview_scale = min(bounds.width(), bounds.height()) / 100.0

        radius = 35 * preview_scale
        num_teeth = 12 # Fixed number of teeth for schematic
        tooth_height = 8 * preview_scale

        outer_radius = radius + tooth_height / 2
        inner_radius = radius - tooth_height / 2

        # Back body
        gear_back = QGraphicsEllipseItem(0,0, outer_radius*2, outer_radius*2)
        gear_back.setPos(center_x - outer_radius + dox, center_y - outer_radius + doy)
        gear_back.setBrush(QColor("darkgray"))
        gear_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(gear_back)

        # Front body
        gear_front = QGraphicsEllipseItem(0,0, outer_radius*2, outer_radius*2)
        gear_front.setPos(center_x - outer_radius, center_y - outer_radius)
        gear_front.setBrush(QColor("lightgray"))
        gear_front.setPen(QPen(Qt.black, 1))
        self.scene.addItem(gear_front)

        center_hole_rad = inner_radius*0.4
        center_hole = QGraphicsEllipseItem(0,0, center_hole_rad*2, center_hole_rad*2)
        center_hole.setPos(center_x - center_hole_rad, center_y - center_hole_rad)
        center_hole.setBrush(QColor("white"))
        center_hole.setPen(QPen(Qt.black, 1))
        self.scene.addItem(center_hole)

        angle_step = 360.0 / num_teeth
        for i in range(num_teeth):
            angle = _np_deg2rad(i * angle_step)
            tooth_angle_width = _np_deg2rad(angle_step / 2 * 0.6)

            coords = [
                (inner_radius * _cos(angle - tooth_angle_width / 2), inner_radius * _sin(angle - tooth_angle_width / 2)),
                (outer_radius * _cos(angle - tooth_angle_width / 3), outer_radius * _sin(angle - tooth_angle_width / 3)),
                (outer_radius * _cos(angle + tooth_angle_width / 3), outer_radius * _sin(angle + tooth_angle_width / 3)),
                (inner_radius * _cos(angle + tooth_angle_width / 2), inner_radius * _sin(angle + tooth_angle_width / 2))
            ]

            tooth_poly_back = QPolygonF()
            for x, y in coords: tooth_poly_back.append(QPointF(center_x + x + dox, center_y + y + doy))
            self.scene.addPolygon(tooth_poly_back, QPen(Qt.PenStyle.NoPen), QBrush(QColor("dimgray")))

            tooth_poly_front = QPolygonF()
            for x, y in coords: tooth_poly_front.append(QPointF(center_x + x, center_y + y))
            self.scene.addPolygon(tooth_poly_front, QPen(Qt.black, 0.5), QBrush(QColor("silver")))

    def _draw_linkage_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic 4-bar linkage preview
        preview_scale = min(bounds.width(), bounds.height()) / 150.0 # Base size for linkage
        thickness = 8 * preview_scale # Scale thickness too

        # Fixed proportions for a generic 4-bar (e.g., a Grashof crank-rocker)
        l1 = 50 * preview_scale  # Crank
        l2 = 65 * preview_scale  # Coupler
        l3 = 70 * preview_scale  # Follower
        l4 = 60 * preview_scale  # Ground link (frame)
        theta1_deg = 30 # Initial angle for crank

        # Center the linkage within bounds
        total_width_approx = l4 + l1 # Rough total width
        total_height_approx = l1 + l2 * 0.5 # Rough total height

        origin_x = bounds.center().x() - l4 / 2
        origin_y = bounds.center().y() # Adjust y to keep it centered better

        p0 = QPointF(origin_x, origin_y)
        p3_fixed = QPointF(origin_x + l4, origin_y)

        theta1_rad = _np_deg2rad(theta1_deg)
        p1 = p0 + QPointF(l1 * _cos(theta1_rad), l1 * _sin(theta1_rad))

        dist_p1_p3_fixed = QLineF(p1, p3_fixed).length()
        p2 = QPointF() # Initialize p2

        # Check for constructibility before calling acos
        if dist_p1_p3_fixed <= 1e-6 or l3 <= 1e-6: # Avoid division by zero or log of zero
            constructible = False
        else:
            cos_alpha_val_num = (l3**2 + dist_p1_p3_fixed**2 - l2**2)
            cos_alpha_val_den = (2 * l3 * dist_p1_p3_fixed)
            if abs(cos_alpha_val_den) < 1e-6:
                 constructible = False # Avoid division by nearly zero
            else:
                cos_alpha_val = cos_alpha_val_num / cos_alpha_val_den
                if not (-1.0 <= cos_alpha_val <= 1.0) or l2 <= 0 : # Check acos domain and link length
                    constructible = False
                else:
                    constructible = True

        if not constructible:
            # Fallback: just draw links p0-p1 and p0-p3_fixed if not constructible or l2/l3 invalid
            # print("Linkage preview not fully constructible with given parameters.")
            # Set p2 to p1 to avoid issues with drawing link2, link3 will be zero length
            p2 = QPointF(p1.x(), p1.y())
            # Effectively, l2 and l3 become zero for drawing if not constructible
            effective_l2 = 0
            effective_l3 = 0
            link_defs_list = [
                ('link1', p0, p1, l1, QColor("skyblue"), QColor("steelblue")),
                ('link4', p0, p3_fixed, l4, QColor("silver"), QColor("darkgray"))
            ]
        else:
            alpha = _acos(cos_alpha_val)
            beta = _atan2(p1.y() - p3_fixed.y(), p1.x() - p3_fixed.x())
            theta3_from_p3_fixed = beta + alpha # One possible solution for p2
            p2 = p3_fixed + QPointF(l3 * _cos(theta3_from_p3_fixed), l3 * _sin(theta3_from_p3_fixed))
            effective_l2 = l2
            effective_l3 = l3
            link_defs_list = [
                ('link1', p0, p1, l1, QColor("skyblue"), QColor("steelblue")),
                ('link2', p1, p2, effective_l2, QColor("lightcoral"), QColor("indianred")),
                ('link3', p2, p3_fixed, effective_l3, QColor("lightgreen"), QColor("seagreen")),
                ('link4', p0, p3_fixed, l4, QColor("silver"), QColor("darkgray"))
            ]

        points = {'p0': p0, 'p1': p1, 'p2': p2, 'p3_fixed': p3_fixed}

        for name, start_pt, end_pt, length, color_front, color_back in link_defs_list:
            if length <= 1e-3: continue # Don't draw zero-length or tiny links

            link_center_x = (start_pt.x() + end_pt.x()) / 2
            link_center_y = (start_pt.y() + end_pt.y()) / 2
            line = QLineF(start_pt, end_pt)
            angle_deg = -line.angle()

            rect_back = QGraphicsRectItem(-length/2, -thickness/2, length, thickness)
            rect_back.setPos(link_center_x + dox, link_center_y + doy)
            rect_back.setRotation(angle_deg)
            rect_back.setBrush(color_back)
            rect_back.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(rect_back)

            rect_front = QGraphicsRectItem(-length/2, -thickness/2, length, thickness)
            rect_front.setPos(link_center_x, link_center_y)
            rect_front.setRotation(angle_deg)
            rect_front.setBrush(color_front)
            rect_front.setPen(QPen(Qt.black, 0.5))
            self.scene.addItem(rect_front)

        pin_radius = thickness * 0.35
        pin_colors_front = [QColor("blue"), QColor("red"), QColor("green"), QColor("black")]
        pin_colors_back = [QColor("darkblue"), QColor("darkred"), QColor("darkgreen"), QColor("dimgray")]

        # Only draw pins for valid points that form the linkage
        # Link1 connects p0-p1. Link4 connects p0-p3_fixed. Link2 p1-p2. Link3 p2-p3_fixed.
        # The pin_draw_points_indices dictionary was causing a TypeError because QPointF is unhashable.
        # It was also unused, as the unique_pin_coords_for_drawing list below correctly assigns points and color indices.
        # pin_draw_points_indices = {
        #     points['p0']: 0,
        #     points['p1']: 1,
        # }
        # if constructible: # p2 is valid only if constructible
        #      pin_draw_points_indices[points['p2']] = 2
        # pin_draw_points_indices[points['p3_fixed']] = 3

        # Use a list to ensure fixed order for colors if some points are duplicates (e.g. p2=p1)
        unique_pin_coords_for_drawing = []
        if 'p0' in points: unique_pin_coords_for_drawing.append((points['p0'],0))
        if 'p1' in points: unique_pin_coords_for_drawing.append((points['p1'],1))
        if constructible and 'p2' in points : unique_pin_coords_for_drawing.append((points['p2'],2))
        if 'p3_fixed' in points: unique_pin_coords_for_drawing.append((points['p3_fixed'],3))

        # Remove duplicate points for drawing pins to avoid overdrawing at same location
        # but keep original color index
        drawn_locations = set()
        final_pins_to_draw = []
        for pt, color_idx in unique_pin_coords_for_drawing:
            pt_tuple = (pt.x(), pt.y())
            if pt_tuple not in drawn_locations:
                final_pins_to_draw.append((pt, color_idx))
                drawn_locations.add(pt_tuple)

        for pt, color_idx in final_pins_to_draw:
            pin_back = QGraphicsEllipseItem(0,0, pin_radius*2, pin_radius*2)
            pin_back.setPos(pt.x() - pin_radius + dox, pt.y() - pin_radius + doy)
            pin_back.setBrush(pin_colors_back[color_idx])
            pin_back.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(pin_back)

            pin_front = QGraphicsEllipseItem(0,0, pin_radius*2, pin_radius*2)
            pin_front.setPos(pt.x() - pin_radius, pt.y() - pin_radius)
            pin_front.setBrush(pin_colors_front[color_idx])
            pin_front.setPen(QPen(Qt.black, 0.5))
            self.scene.addItem(pin_front)

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 150)

    def sizeHint(self) -> QSize:
        return QSize(200, 150)

import math

def _cos(angle_rad: float) -> float: return math.cos(angle_rad)
def _sin(angle_rad: float) -> float: return math.sin(angle_rad)
def _np_deg2rad(deg: float) -> float: return math.radians(deg)
def _atan2(y: float, x: float) -> float: return math.atan2(y, x)
def _acos(val: float) -> float: return math.acos(min(1.0, max(-1.0, val)))

class MechanismRecommendationDialog(QDialog):
    mechanism_selected = Signal(dict)

    def __init__(self, recommendations: List[Optional[Dict[str, Any]]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Mechanism Recommendations")
        self.setMinimumWidth(700)
        self.selected_mechanism: Optional[Dict[str, Any]] = None
        main_layout = QVBoxLayout(self)
        title_label = QLabel("Choose a mechanism to generate:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        main_layout.addWidget(title_label)
        recommendations_layout = QHBoxLayout()
        main_layout.addLayout(recommendations_layout)

        valid_recommendations = [rec for rec in recommendations if rec is not None and rec.get("type") is not None]
        if not valid_recommendations:
            no_recs_label = QLabel("No mechanism recommendations available at the moment.")
            no_recs_label.setAlignment(Qt.AlignCenter)
            recommendations_layout.addWidget(no_recs_label)
        else:
            for i, rec_data in enumerate(valid_recommendations):
                group_title = f"Option {i+1}: {rec_data.get('name', rec_data.get('type', 'Mechanism').capitalize())}"
                rec_groupbox = QGroupBox(group_title)
                rec_groupbox_layout = QVBoxLayout(rec_groupbox)
                preview_widget = MechanismPreviewWidget(rec_data)
                rec_groupbox_layout.addWidget(preview_widget, alignment=Qt.AlignCenter)
                params_list = []
                if rec_data.get("type") == "cam":
                    params_list.append(f"Base Radius: {rec_data.get('base_radius', 'N/A'):.1f}")
                    params_list.append(f"Ecc. Radius: {rec_data.get('eccentric_radius', 'N/A'):.1f}")
                elif rec_data.get("type") == "linkage":
                    params_list.append(f"Type: {rec_data.get('bar_type', 'N/A')}")
                    ll = rec_data.get('link_lengths', {})
                    if ll: params_list.append(f"L1-L4: {ll.get('l1',0):.0f}, {ll.get('l2',0):.0f}, {ll.get('l3',0):.0f}, {ll.get('l4',0):.0f}")
                elif rec_data.get("type") == "gears":
                    if rec_data.get('gears') and isinstance(rec_data['gears'], list) and rec_data['gears']:
                        g1 = rec_data['gears'][0]
                        params_list.append(f"G1: R={g1.get('radius','N/A'):.0f}, T={g1.get('num_teeth','N/A')}")
                        if len(rec_data['gears']) > 1:
                            g2 = rec_data['gears'][1]
                            params_list.append(f"G2: R={g2.get('radius','N/A'):.0f}, T={g2.get('num_teeth','N/A')}")
                description_label = QLabel("\n".join(params_list) or "Parameters not detailed.")
                description_label.setWordWrap(True)
                description_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
                rec_groupbox_layout.addWidget(description_label)
                rec_groupbox_layout.addStretch()
                select_button = QPushButton(f"Select This")
                select_button.clicked.connect(lambda checked=False, data=rec_data: self._on_select(data))
                rec_groupbox_layout.addWidget(select_button)
                recommendations_layout.addWidget(rec_groupbox)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _on_select(self, mechanism_data: Dict[str, Any]) -> None:
        self.selected_mechanism = mechanism_data
        self.mechanism_selected.emit(self.selected_mechanism)
        self.accept()

    @staticmethod
    def get_recommendation(
        recommendations: List[Optional[Dict[str, Any]]], parent: Optional[QWidget] = None
    ) -> Optional[Dict[str, Any]]:
        dialog = MechanismRecommendationDialog(recommendations, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.selected_mechanism
        return None

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtCore import QTimer
    import sys

    mock_recs_good = [
        {"type": "cam", "name": "Smooth Cam", "base_radius": 30, "eccentric_radius": 15, "angle_offset_rad": _np_deg2rad(30)},
        {"type": "linkage", "name": "Standard 4-Bar", "bar_type": "4-bar", "link_lengths": {"l1": 50, "l2": 65, "l3": 58, "l4": 60}, "theta1_deg": 45},
        {"type": "gears", "name": "Gear Set Alpha", "gears": [ {"radius": 40, "num_teeth": 20, "tooth_height": 8}, {"radius": 20, "num_teeth": 10, "tooth_height": 8}]},
    ]
    mock_recs_mixed = [
        {"type": "cam", "name": "Sharp Cam", "base_radius": 25, "eccentric_radius": 20, "angle_offset_rad": _np_deg2rad(70)},
        None, # Missing recommendation
        {"type": "linkage", "name": "Short Crank 4-Bar", "bar_type": "4-bar", "link_lengths": {"l1": 30, "l2": 70, "l3": 60, "l4": 50}, "theta1_deg": 20},
    ]
    mock_recs_problematic_linkage = [
        {"type": "linkage", "name": "Unconstructible Linkage", "bar_type": "4-bar", "link_lengths": {"l1": 20, "l2": 100, "l3": 20, "l4": 150}, "theta1_deg": 0},
        mock_recs_good[0]
    ]
    mock_recs_empty = []
    mock_recs_all_none = [None, None, None]

    app = QApplication(sys.argv)
    # Dummy main window to act as parent for dialog if needed, and to keep app running for a bit
    # mainWindow = QMainWindow()
    # mainWindow.show()

    def run_test(recs, title):
        print(f"\n--- Testing: {title} ---")
        selected = MechanismRecommendationDialog.get_recommendation(recs)
        if selected:
            print(f"Selected: {selected.get('name', selected.get('type'))}")
        else:
            print("Dialog cancelled or no selection.")

    tests_to_run = [
        (mock_recs_good, "Good Recommendations"),
        (mock_recs_mixed, "Mixed (with None) Recommendations"),
        (mock_recs_problematic_linkage, "Problematic Linkage Recommendation"),
        (mock_recs_empty, "Empty Recommendations List"),
        (mock_recs_all_none, "All None Recommendations")
    ]

    # To run tests sequentially and then exit
    current_test_index = 0
    def run_next_test():
        if current_test_index < len(tests_to_run):
            recs, title = tests_to_run[current_test_index]
            run_test(recs, title)
            current_test_index += 1
            QTimer.singleShot(100, run_next_test) # Short delay before next dialog
        else:
            print("\nAll tests finished.")
            app.quit()

    QTimer.singleShot(0, run_next_test) # Start the first test
    sys.exit(app.exec())
