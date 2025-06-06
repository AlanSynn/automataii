from typing import Any, Dict, List, Optional

import numpy as np  # Add numpy import
from scipy.spatial.distance import directed_hausdorff  # Add scipy import
import json  # Add json import

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize, QPointF, QLineF, QRectF
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPainterPath,
    QPolygonF,
    QTransform,
)
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
    QDialogButtonBox,
)

# Color palette
BITTERSWEET = QColor("#ff595e")
SUNGLOW = QColor("#ffca3a")
YELLOW_GREEN = QColor("#8ac926")
STEEL_BLUE = QColor("#1982c4")
ULTRA_VIOLET = QColor("#6a4c93")

# from automataii.utils.qt_helpers import create_round_rect_path # Not used in this version

DEFAULT_NUM_SAMPLES_FOR_PATH = (
    100  # Default number of points to sample from QPainterPath
)


def qpainterpath_to_numpy_array(
    path: QPainterPath, num_points: int = DEFAULT_NUM_SAMPLES_FOR_PATH
) -> Optional[np.ndarray]:
    """Converts a QPainterPath to a numpy array of (x, y) coordinates.

    Args:
        path: The QPainterPath to convert.
        num_points: The number of points to sample along the path.

    Returns:
        A numpy array of shape (num_points, 2) or None if the path is empty or invalid.
    """
    if path.isEmpty() or num_points <= 0:
        return None

    points = []
    for i in range(num_points):
        percent = i / (num_points - 1) if num_points > 1 else 0
        pt = path.pointAtPercent(percent)
        points.append([pt.x(), pt.y()])
    return np.array(points)


def calculate_hausdorff_distance(
    path1_points: np.ndarray, path2_points: np.ndarray
) -> float:
    """Calculates the Hausdorff distance between two sets of points.

    Args:
        path1_points: Numpy array of points for the first path (N, 2).
        path2_points: Numpy array of points for the second path (M, 2).

    Returns:
        The Hausdorff distance. Returns float('inf') if either path is empty or invalid.
    """
    if (
        path1_points is None
        or path1_points.shape[0] == 0
        or path2_points is None
        or path2_points.shape[0] == 0
    ):
        return float("inf")

    # For a more robust measure, consider the maximum of the two directed distances
    dist_1_to_2 = directed_hausdorff(path1_points, path2_points)[0]
    dist_2_to_1 = directed_hausdorff(path2_points, path1_points)[0]
    return max(dist_1_to_2, dist_2_to_1)


class MechanismPreviewWidget(QGraphicsView):
    """A widget to display a preview of a single mechanism."""

    def __init__(
        self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(350, 300)  # Much larger size for better visibility
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#f8f8f8"))  # Light background
        self._render_preview()  # Render after background is set and scene is ready

    def _draw_user_motion_path(self, bounds: QRectF) -> None:
        """Draws the user's motion path, scaled and centered within the given bounds."""
        user_path_local = self.mechanism_data.get("user_motion_path_local")
        if not isinstance(user_path_local, QPainterPath) or user_path_local.isEmpty():
            return

        path_bounds = user_path_local.boundingRect()
        if path_bounds.width() == 0 or path_bounds.height() == 0:
            return

        # Scale the path to fit within 80% of the preview bounds, preserving aspect ratio
        target_rect = bounds.adjusted(
            bounds.width() * 0.1,
            bounds.height() * 0.1,
            -bounds.width() * 0.1,
            -bounds.height() * 0.1,
        )

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
        transform.translate(
            target_rect.left()
            - scaled_path_bounds.left()
            + (target_rect.width() - scaled_path_bounds.width()) / 2,
            target_rect.top()
            - scaled_path_bounds.top()
            + (target_rect.height() - scaled_path_bounds.height()) / 2,
        )

        transformed_path = transform.map(user_path_local)

        path_item = QGraphicsPathItem(transformed_path)
        pen = QPen(BITTERSWEET, 4.0, Qt.PenStyle.DashLine)  # Thicker, red dashed line for visibility
        path_item.setPen(pen)
        path_item.setZValue(10)  # Draw on top of the mechanism
        self.scene.addItem(path_item)

    def _render_preview(self) -> None:
        self.scene.clear()
        # Add a small margin for content within the view bounds
        margin = 5
        # Use self.viewport().rect() for accurate available drawing area after scrollbars etc.
        # However, since scrollbars are off, self.rect() is fine.
        view_rect_int = self.rect()
        view_rect_f = QRectF(view_rect_int)  # Convert QRect to QRectF
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)

        # Set sceneRect to the viewable area to help with item positioning if items are added at (0,0)
        self.scene.setSceneRect(view_rect_f)  # Use QRectF here

        # Common drawing parameters
        dark_offset_x = 1.5
        dark_offset_y = 1.5

        if not self.mechanism_data or not self.mechanism_data.get("type"):
            text_item = self.scene.addText("No Preview")
            text_item.setDefaultTextColor(Qt.GlobalColor.black)
            # Center text in the view_rect (area inside margin)
            text_item.setPos(
                view_rect_adjusted_f.center() - text_item.boundingRect().center()
            )
            return

        preview_type = self.mechanism_data.get("type")
        # Default to "Cam & Follower" if type is "cam" for consistency with generation
        if preview_type == "cam":
            preview_type = "Cam & Follower"

        if preview_type == "Cam & Follower":
            self._draw_cam_preview(dark_offset_x, dark_offset_y, view_rect_adjusted_f)
        elif (
            preview_type == "4-Bar Linkage"
            or preview_type == "3-Bar Linkage"
            or preview_type == "linkage"
        ):  # Handle generic "linkage" too
            self._draw_linkage_preview(
                dark_offset_x, dark_offset_y, view_rect_adjusted_f
            )
        elif (
            preview_type == "Gears (Simple Pair)" or preview_type == "gears"
        ):  # Handle generic "gears" too
            self._draw_gear_preview(dark_offset_x, dark_offset_y, view_rect_adjusted_f)
        else:
            text_item = self.scene.addText(
                f'Preview for "{preview_type}"\nnot implemented.'
            )
            text_item.setDefaultTextColor(Qt.GlobalColor.black)
            text_item.setPos(
                view_rect_adjusted_f.center() - text_item.boundingRect().center()
            )

        # Draw user's motion path if available, after specific mechanism
        self._draw_user_motion_path(view_rect_adjusted_f)

        # Fit view to scene contents, respecting the view_rect
        # self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        # Ensure the entire sceneRect is visible
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_cam_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic cam preview
        preview_scale = min(bounds.width(), bounds.height()) / 150.0  # Larger scale
        base_radius = 50 * preview_scale
        eccentric_radius = 30 * preview_scale
        angle_offset_rad = _np_deg2rad(45)  # Fixed angle for schematic

        # Use the adjusted bounds for drawing
        cam_center_x = bounds.center().x()
        cam_center_y = (
            bounds.center().y() - base_radius * 0.2
        )  # Shift up a bit to make space for follower

        ecc_offset_x = (
            (base_radius - eccentric_radius) * 0.7 * _cos(angle_offset_rad)
        )  # further scale down offset
        ecc_offset_y = (base_radius - eccentric_radius) * 0.7 * _sin(angle_offset_rad)

        eff_ecc_center_x = cam_center_x + ecc_offset_x
        eff_ecc_center_y = cam_center_y + ecc_offset_y

        # Back
        cam_back = QGraphicsEllipseItem(
            0, 0, eccentric_radius * 2, eccentric_radius * 2
        )
        cam_back.setPos(
            eff_ecc_center_x - eccentric_radius + dox,
            eff_ecc_center_y - eccentric_radius + doy,
        )
        cam_back.setBrush(ULTRA_VIOLET)  # Use ULTRA_VIOLET
        cam_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(cam_back)

        shaft_back_rad = base_radius * 0.25
        shaft_back = QGraphicsEllipseItem(0, 0, shaft_back_rad * 2, shaft_back_rad * 2)
        shaft_back.setPos(
            cam_center_x - shaft_back_rad + dox, cam_center_y - shaft_back_rad + doy
        )
        shaft_back.setBrush(QColor(ULTRA_VIOLET).darker(130))  # Darker ULTRA_VIOLET
        shaft_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(shaft_back)

        # Front
        cam_front = QGraphicsEllipseItem(
            0, 0, eccentric_radius * 2, eccentric_radius * 2
        )
        cam_front.setPos(
            eff_ecc_center_x - eccentric_radius, eff_ecc_center_y - eccentric_radius
        )
        cam_front.setBrush(STEEL_BLUE)  # Use STEEL_BLUE
        cam_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(cam_front)

        shaft_front_rad = base_radius * 0.25
        shaft_front = QGraphicsEllipseItem(
            0, 0, shaft_front_rad * 2, shaft_front_rad * 2
        )
        shaft_front.setPos(
            cam_center_x - shaft_front_rad, cam_center_y - shaft_front_rad
        )
        shaft_front.setBrush(QColor(STEEL_BLUE).lighter(130))  # Lighter STEEL_BLUE
        shaft_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(shaft_front)

        follower_width = base_radius * 0.4
        follower_height = base_radius * 0.8
        follower_x = cam_center_x - follower_width / 2
        follower_y_contact = eff_ecc_center_y + eccentric_radius + 2  # ensure contact

        # Make follower schematic and relative to cam size
        follower_width = base_radius * 0.5
        follower_height = base_radius * 0.7
        follower_x = cam_center_x - follower_width / 2
        # Adjust follower_y_contact if needed based on new base_radius relationship
        # For a generic preview, this should be fine, or tie it to cam_center_y more directly
        follower_y_contact = cam_center_y + base_radius * 0.5  # Example positioning

        follower_back = QGraphicsRectItem(
            follower_x + dox, follower_y_contact + doy, follower_width, follower_height
        )
        follower_back.setBrush(QColor(BITTERSWEET).darker(130))  # Darker BITTERSWEET
        follower_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(follower_back)

        follower_front = QGraphicsRectItem(
            follower_x, follower_y_contact, follower_width, follower_height
        )
        follower_front.setBrush(BITTERSWEET)  # Use BITTERSWEET
        follower_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(follower_front)

    def _draw_gear_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Two meshing gears preview
        center_x = bounds.center().x()
        center_y = bounds.center().y()
        preview_scale = min(bounds.width(), bounds.height()) / 150.0  # Larger scale

        # First gear (larger)
        radius1 = 45 * preview_scale
        num_teeth1 = 18
        tooth_height1 = 10 * preview_scale
        
        # Second gear (smaller)
        radius2 = 30 * preview_scale
        num_teeth2 = 12
        tooth_height2 = 8 * preview_scale
        
        # Position gears to mesh
        gear1_x = center_x - radius1 * 0.8
        gear1_y = center_y
        gear2_x = gear1_x + radius1 + radius2 + (tooth_height1 + tooth_height2) * 0.5
        gear2_y = center_y

        # Draw first gear
        outer_radius1 = radius1 + tooth_height1 / 2
        inner_radius1 = radius1 - tooth_height1 / 2

        # Back body
        gear1_back = QGraphicsEllipseItem(0, 0, outer_radius1 * 2, outer_radius1 * 2)
        gear1_back.setPos(gear1_x - outer_radius1 + dox, gear1_y - outer_radius1 + doy)
        gear1_back.setBrush(ULTRA_VIOLET)
        gear1_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(gear1_back)

        # Front body
        gear1_front = QGraphicsEllipseItem(0, 0, outer_radius1 * 2, outer_radius1 * 2)
        gear1_front.setPos(gear1_x - outer_radius1, gear1_y - outer_radius1)
        gear1_front.setBrush(STEEL_BLUE)
        gear1_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(gear1_front)

        # Center hole for first gear
        center_hole_rad1 = inner_radius1 * 0.4
        center_hole1 = QGraphicsEllipseItem(
            0, 0, center_hole_rad1 * 2, center_hole_rad1 * 2
        )
        center_hole1.setPos(gear1_x - center_hole_rad1, gear1_y - center_hole_rad1)
        center_hole1.setBrush(QColor("white"))
        center_hole1.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(center_hole1)

        # Draw teeth for first gear
        angle_step1 = 360.0 / num_teeth1
        for i in range(num_teeth1):
            angle = _np_deg2rad(i * angle_step1)
            tooth_angle_width = _np_deg2rad(angle_step1 / 2 * 0.6)

            coords = [
                (
                    inner_radius1 * _cos(angle - tooth_angle_width / 2),
                    inner_radius1 * _sin(angle - tooth_angle_width / 2),
                ),
                (
                    outer_radius1 * _cos(angle - tooth_angle_width / 3),
                    outer_radius1 * _sin(angle - tooth_angle_width / 3),
                ),
                (
                    outer_radius1 * _cos(angle + tooth_angle_width / 3),
                    outer_radius1 * _sin(angle + tooth_angle_width / 3),
                ),
                (
                    inner_radius1 * _cos(angle + tooth_angle_width / 2),
                    inner_radius1 * _sin(angle + tooth_angle_width / 2),
                ),
            ]

            tooth_poly_back = QPolygonF()
            for x, y in coords:
                tooth_poly_back.append(QPointF(gear1_x + x + dox, gear1_y + y + doy))
            self.scene.addPolygon(
                tooth_poly_back,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(YELLOW_GREEN).darker(130)),
            )

            tooth_poly_front = QPolygonF()
            for x, y in coords:
                tooth_poly_front.append(QPointF(gear1_x + x, gear1_y + y))
            self.scene.addPolygon(
                tooth_poly_front, QPen(Qt.GlobalColor.black, 0.5), QBrush(YELLOW_GREEN)
            )

        # Draw second gear
        outer_radius2 = radius2 + tooth_height2 / 2
        inner_radius2 = radius2 - tooth_height2 / 2

        # Back body
        gear2_back = QGraphicsEllipseItem(0, 0, outer_radius2 * 2, outer_radius2 * 2)
        gear2_back.setPos(gear2_x - outer_radius2 + dox, gear2_y - outer_radius2 + doy)
        gear2_back.setBrush(QColor(BITTERSWEET).darker(130))
        gear2_back.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(gear2_back)

        # Front body
        gear2_front = QGraphicsEllipseItem(0, 0, outer_radius2 * 2, outer_radius2 * 2)
        gear2_front.setPos(gear2_x - outer_radius2, gear2_y - outer_radius2)
        gear2_front.setBrush(BITTERSWEET)
        gear2_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(gear2_front)

        # Center hole for second gear
        center_hole_rad2 = inner_radius2 * 0.4
        center_hole2 = QGraphicsEllipseItem(
            0, 0, center_hole_rad2 * 2, center_hole_rad2 * 2
        )
        center_hole2.setPos(gear2_x - center_hole_rad2, gear2_y - center_hole_rad2)
        center_hole2.setBrush(QColor("white"))
        center_hole2.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(center_hole2)

        # Draw teeth for second gear with phase offset for meshing
        angle_step2 = 360.0 / num_teeth2
        phase_offset = angle_step2 / 2  # Offset for meshing
        for i in range(num_teeth2):
            angle = _np_deg2rad(i * angle_step2 + phase_offset)
            tooth_angle_width = _np_deg2rad(angle_step2 / 2 * 0.6)

            coords = [
                (
                    inner_radius2 * _cos(angle - tooth_angle_width / 2),
                    inner_radius2 * _sin(angle - tooth_angle_width / 2),
                ),
                (
                    outer_radius2 * _cos(angle - tooth_angle_width / 3),
                    outer_radius2 * _sin(angle - tooth_angle_width / 3),
                ),
                (
                    outer_radius2 * _cos(angle + tooth_angle_width / 3),
                    outer_radius2 * _sin(angle + tooth_angle_width / 3),
                ),
                (
                    inner_radius2 * _cos(angle + tooth_angle_width / 2),
                    inner_radius2 * _sin(angle + tooth_angle_width / 2),
                ),
            ]

            tooth_poly_back = QPolygonF()
            for x, y in coords:
                tooth_poly_back.append(QPointF(gear2_x + x + dox, gear2_y + y + doy))
            self.scene.addPolygon(
                tooth_poly_back,
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(SUNGLOW).darker(130)),
            )

            tooth_poly_front = QPolygonF()
            for x, y in coords:
                tooth_poly_front.append(QPointF(gear2_x + x, gear2_y + y))
            self.scene.addPolygon(
                tooth_poly_front, QPen(Qt.GlobalColor.black, 0.5), QBrush(SUNGLOW)
            )

    def _draw_linkage_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic 4-bar linkage preview
        preview_scale = (
            min(bounds.width(), bounds.height()) / 200.0
        )  # Larger scale for linkage
        thickness = 12 * preview_scale  # Thicker links for visibility

        # Define points relative to bounds center, then scale
        center_x = bounds.center().x()
        center_y = bounds.center().y()

        # Normalized points for a better looking four-bar
        p0_norm = QPointF(-60, 20)   # Fixed ground pivot 1
        p1_norm = QPointF(-40, -30)  # Crank pivot
        p2_norm = QPointF(30, -40)   # Coupler end / Rocker pivot
        p3_norm = QPointF(60, 15)    # Fixed ground pivot 2

        # Scale points
        p0 = QPointF(
            center_x + p0_norm.x() * preview_scale,
            center_y + p0_norm.y() * preview_scale,
        )
        p1 = QPointF(
            center_x + p1_norm.x() * preview_scale,
            center_y + p1_norm.y() * preview_scale,
        )
        p2 = QPointF(
            center_x + p2_norm.x() * preview_scale,
            center_y + p2_norm.y() * preview_scale,
        )
        p3 = QPointF(
            center_x + p3_norm.x() * preview_scale,
            center_y + p3_norm.y() * preview_scale,
        )

        # Draw ground line first
        ground_y = max(p0.y(), p3.y()) + 20 * preview_scale
        ground_line = QLineF(
            bounds.left() + 20, ground_y,
            bounds.right() - 20, ground_y
        )
        ground_path = QPainterPath()
        ground_path.moveTo(ground_line.p1())
        ground_path.lineTo(ground_line.p2())
        ground_item = QGraphicsPathItem(ground_path)
        ground_pen = QPen(QColor("#888888"), 2, Qt.PenStyle.DashLine)
        ground_item.setPen(ground_pen)
        self.scene.addItem(ground_item)

        # Draw links (back then front)
        link_color_front = STEEL_BLUE
        link_color_back = ULTRA_VIOLET
        pivot_color_front = SUNGLOW
        pivot_color_back = QColor(SUNGLOW).darker(150)  # Darker SUNGLOW
        pivot_radius = thickness * 0.7  # Scale pivot radius with thickness

        links = [
            (p0, p1, "crank"),
            (p1, p2, "coupler"),
            (p2, p3, "rocker"),
            # Skip ground link as we drew the ground line
        ]

        for start_pt, end_pt, _ in links:
            # Back link
            path_back = QPainterPath()
            path_back.moveTo(start_pt + QPointF(dox, doy))
            path_back.lineTo(end_pt + QPointF(dox, doy))
            link_back = QGraphicsPathItem(path_back)
            pen_back = QPen(
                link_color_back,
                thickness,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            link_back.setPen(pen_back)
            self.scene.addItem(link_back)

            # Front link
            path_front = QPainterPath()
            path_front.moveTo(start_pt)
            path_front.lineTo(end_pt)
            link_front = QGraphicsPathItem(path_front)
            pen_front = QPen(
                link_color_front,
                thickness,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            link_front.setPen(pen_front)
            self.scene.addItem(link_front)

        # Draw pivots (back then front)
        pivot_points = [p0, p1, p2, p3]
        for pt in pivot_points:
            # Back pivot
            pivot_item_back = QGraphicsEllipseItem(
                pt.x() - pivot_radius + dox,
                pt.y() - pivot_radius + doy,
                pivot_radius * 2,
                pivot_radius * 2,
            )
            pivot_item_back.setBrush(pivot_color_back)
            pivot_item_back.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(pivot_item_back)

            # Front pivot
            pivot_item_front = QGraphicsEllipseItem(
                pt.x() - pivot_radius,
                pt.y() - pivot_radius,
                pivot_radius * 2,
                pivot_radius * 2,
            )
            pivot_item_front.setBrush(pivot_color_front)
            pivot_item_front.setPen(QPen(Qt.GlobalColor.black, 1))
            self.scene.addItem(pivot_item_front)


# Python's math functions for cos and sin
from math import cos as _cos, sin as _sin, radians as _np_deg2rad

# Define mechanism type constants for display and internal logic
MECHANISM_TYPE_USER_DISPLAY_3_BAR = "3-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_4_BAR = "4-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_CAM = "Cam Profile"

# Constants that might be used if JSON types are more specific or internal logic needs them
# For now, we map directly from JSON types to user display types if simple,
# or use these for more complex mapping logic if needed later.
# MECHANISM_INTERNAL_TYPE_3_BAR = "3_BAR_INTERNAL_TYPE_KEY_FROM_JSON_IF_DIFFERENT"
# MECHANISM_INTERNAL_TYPE_4_BAR_COUPLER = "4-bar Coupler" # Actual key from JSON
# MECHANISM_INTERNAL_TYPE_CAM_PROFILE = "CAM_PROFILE_INTERNAL_TYPE_KEY_FROM_JSON_IF_DIFFERENT"


class PreviewContainer(QWidget):
    """Container for a single preview and its title/select button."""

    selected = Signal(dict)  # Emits the mechanism data when selected
    clicked = Signal(dict)  # Emits the mechanism data when clicked for preview

    def __init__(
        self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self._is_selected = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title/Name with better styling
        name = self.mechanism_data.get("name", "Unnamed Mechanism")
        title_label = QLabel(name)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px;
            }
        """)
        layout.addWidget(title_label)

        # Preview Widget with rounded corners
        self.preview_widget = MechanismPreviewWidget(self.mechanism_data, self)
        self.preview_widget.setStyleSheet("""
            QGraphicsView {
                border: 3px solid transparent;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)
        layout.addWidget(self.preview_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Select Button with better styling
        select_button = QPushButton("Select This")
        select_button.setFixedSize(120, 35)
        select_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        select_button.clicked.connect(self._emit_selected)
        layout.addWidget(select_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        self.setMinimumWidth(370)  # Ensure enough space for larger preview
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )  # Fixed height based on content

        # Make the container clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_data)
            # Update visual selection
            self._set_selected_style(True)
        super().mousePressEvent(event)

    def _set_selected_style(self, selected: bool):
        """Update visual style to show selection."""
        self._is_selected = selected
        if selected:
            self.preview_widget.setStyleSheet("""
                QGraphicsView {
                    border: 3px solid #3498db;
                    border-radius: 8px;
                    background-color: #ffffff;
                    box-shadow: 0 0 10px rgba(52, 152, 219, 0.5);
                }
            """)
            self.setStyleSheet("""
                PreviewContainer {
                    background-color: #f0f8ff;
                    border-radius: 10px;
                }
            """)
        else:
            self.preview_widget.setStyleSheet("""
                QGraphicsView {
                    border: 3px solid transparent;
                    border-radius: 8px;
                    background-color: #ffffff;
                }
            """)
            self.setStyleSheet("")

    def _emit_selected(self) -> None:
        self.selected.emit(self.mechanism_data)

    def minimumSizeHint(self) -> QSize:
        return QSize(370, 400)  # Adjust based on larger preview

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()


# Wrapper for math functions to avoid numpy dependency if not strictly needed here
# And to ensure degrees are converted to radians correctly for math.cos/sin.


class MechanismRecommendationDialog(QDialog):
    mechanism_selected = Signal(dict)  # Emitted when a mechanism is chosen
    mechanism_preview_selected = Signal(
        dict
    )  # Emitted when a mechanism is clicked for preview

    def __init__(
        self,
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Choose a Mechanism")
        self.setMinimumSize(1200, 600)  # Much larger dialog
        self.selected_mechanism_data: Optional[Dict[str, Any]] = None

        self.user_motion_path_original = (
            user_motion_path  # Keep original QPainterPath for preview
        )
        self.user_motion_path_np = qpainterpath_to_numpy_array(
            user_motion_path, num_samples_user_path
        )

        self.generated_paths_filepath = generated_paths_filepath
        self.generated_paths_data = self._load_generated_paths(generated_paths_filepath)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Add instruction label with better styling
        instruction_label = QLabel(
            "Choose the mechanism that best matches your desired motion"
        )
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333333;
                padding: 10px;
            }
        """)
        main_layout.addWidget(instruction_label)
        
        # Add subtitle
        subtitle_label = QLabel(
            "The red dashed line shows your drawn path. Click on a mechanism to select it."
        )
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666666;
                padding-bottom: 20px;
            }
        """)
        main_layout.addWidget(subtitle_label)

        self.previews_layout = QHBoxLayout()
        self.previews_layout.setSpacing(10)
        self.previews_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        recommendations = self._get_best_recommendations()
        self.preview_containers = []

        if recommendations:
            for rec_data in recommendations:
                if rec_data:
                    # Add user_motion_path_local to each recommendation for preview
                    rec_data_with_user_path = rec_data.copy()
                    rec_data_with_user_path["user_motion_path_local"] = (
                        self.user_motion_path_original
                    )

                    container = PreviewContainer(rec_data_with_user_path, self)
                    container.selected.connect(self._on_select)
                    container.clicked.connect(
                        self._on_preview_click
                    )  # Add preview click handler
                    self.previews_layout.addWidget(container)
                    self.preview_containers.append(container)
                else:
                    placeholder_label = QLabel("No mechanism found")
                    placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder_label.setFrameShape(QLabel.FrameShape.Box)
                    placeholder_label.setFixedSize(220, 280)
                    placeholder_label.setStyleSheet("background-color: #f0f0f0;")
                    self.previews_layout.addWidget(placeholder_label)
            self.previews_layout.addStretch()
        else:
            no_recs_label = QLabel(
                "No mechanism recommendations could be generated or found."
            )
            no_recs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.previews_layout.addWidget(no_recs_label)

        main_layout.addLayout(self.previews_layout)

        # Custom button area with smaller, styled buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedSize(80, 30)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedSize(80, 30)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #ba1a0d;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        
        main_layout.addSpacing(20)
        main_layout.addLayout(button_layout)
        main_layout.addSpacing(10)

        self.setLayout(main_layout)

    def _load_generated_paths(self, filepath: str) -> List[Dict[str, Any]]:
        """Loads mechanism paths from a JSON file and prepares them."""
        loaded_paths = []
        try:
            with open(filepath, "r") as f:
                raw_data = json.load(f)

            for item in raw_data:
                path_coords = item.get("path_coordinates")
                if (
                    path_coords
                    and isinstance(path_coords, list)
                    and len(path_coords) > 0
                ):
                    # Ensure coordinates are suitable for numpy array (e.g., list of lists/tuples)
                    try:
                        item["path_coordinates_np"] = np.array(path_coords, dtype=float)
                        loaded_paths.append(item)
                    except ValueError as e:
                        print(
                            f"Warning: Could not convert path_coordinates to numpy array for item: {item.get('type', 'N/A')}. Error: {e}"
                        )
                        # Optionally skip this item or handle error
                else:
                    print(
                        f"Warning: Missing or invalid 'path_coordinates' for item: {item.get('type', 'N/A')}"
                    )

        except FileNotFoundError:
            print(f"Error: Generated paths file not found at {filepath}")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {filepath}")
        except Exception as e:
            print(f"An unexpected error occurred while loading generated paths: {e}")
        return loaded_paths

    def _get_best_recommendations(self) -> List[Optional[Dict[str, Any]]]:
        """
        Compares the user's motion path with generated paths using Hausdorff distance
        and returns the top 2-3 matches across all mechanism types.
        """
        if self.user_motion_path_np is None or not self.generated_paths_data:
            print("User motion path is not processed or no generated paths loaded.")
            return []

        # Collect all mechanisms with their scores
        all_recommendations = []

        # Mapping from JSON type strings to our user-facing display type constants.
        type_mapping = {
            "4-bar Coupler": MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            "3-bar Output": MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            "Cam Profile": MECHANISM_TYPE_USER_DISPLAY_CAM,
            # Add other mappings as needed
        }

        for gen_path_data in self.generated_paths_data:
            gen_path_np = gen_path_data.get("path_coordinates_np")
            json_type_str = gen_path_data.get("type")

            if gen_path_np is None or json_type_str is None:
                continue

            distance = calculate_hausdorff_distance(
                self.user_motion_path_np, gen_path_np
            )

            target_mech_type = type_mapping.get(
                json_type_str, json_type_str
            )  # Default to json_type_str if not mapped

            # Prepare data for PreviewContainer
            preview_data = {
                "name": gen_path_data.get("name", json_type_str),
                "type": target_mech_type,
                "original_json_type": json_type_str,
                "overall_score": distance,
                "parameters": gen_path_data.get("parameters"),
                "path_coordinates_np": gen_path_np,
                "path_coordinates": gen_path_data.get(
                    "path_coordinates"
                ),  # Keep original coordinates
            }
            all_recommendations.append(preview_data)

        # Sort by score (lower is better) and take top 3
        all_recommendations.sort(key=lambda x: x["overall_score"])
        top_recommendations = all_recommendations[:3]

        # Ensure we have at least 2-3 slots (can be empty)
        while len(top_recommendations) < 3:
            top_recommendations.append(None)

        return top_recommendations

    def _on_select(self, mechanism_data: Dict[str, Any]) -> None:
        self.selected_mechanism_data = mechanism_data
        self.ok_button.setEnabled(True)
        # Update visual selection for all containers
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)

    def _on_preview_click(self, mechanism_data: Dict[str, Any]) -> None:
        """Handle preview click to show mechanism in main view."""
        # Update visual selection for all containers
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)
        # Emit the preview signal
        self.mechanism_preview_selected.emit(mechanism_data)

    @staticmethod
    def get_recommendation(
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: Optional[QWidget] = None,
    ) -> Optional[Dict[str, Any]]:
        """Static method to show the dialog and return the selected mechanism data."""
        dialog = MechanismRecommendationDialog(
            user_motion_path, generated_paths_filepath, num_samples_user_path, parent
        )
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return dialog.selected_mechanism_data
        return None


if __name__ == "__main__":
    import sys
    import logging
    from PyQt6.QtWidgets import QApplication  # Import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Example recommendations (replace with actual data from MechanismManager)
    dummy_path = QPainterPath()
    dummy_path.moveTo(10, 10)
    dummy_path.lineTo(50, 80)
    dummy_path.quadTo(100, 100, 150, 50)

    example_recs_data = [
        {
            "name": "Recommended Cam 1",
            "type": "Cam & Follower",
            "overall_score": 0.85,
            "user_motion_path_local": dummy_path.translated(0, 0),
        },
        {
            "name": "Recommended Linkage A",
            "type": "4-Bar Linkage",
            "overall_score": 0.72,
            "user_motion_path_local": dummy_path.translated(10, 10),
        },
        {
            "name": "Simple Gears",
            "type": "gears",
            "overall_score": 0.91,
            "user_motion_path_local": dummy_path.translated(-5, 5),
        },
        None,  # Test None placeholder
        {
            "name": "Another Cam",
            "type": "cam",
            "overall_score": 0.60,
        },  # Test with no path
    ]
    empty_recs = []
    error_recs = [None, None]

    tests = [
        (example_recs_data, "Full Example Recommendations"),
        (empty_recs, "Empty Recommendations"),
        (error_recs, "Error/None Recommendations"),
        ([example_recs_data[0]], "Single Cam Recommendation"),
        ([example_recs_data[1]], "Single Linkage Recommendation"),
    ]
    current_test_index_ref = [0]  # Use a list to pass by reference

    def run_test(recs, title):
        print(f"\n--- Running Test: {title} ---")
        selected_mechanism = MechanismRecommendationDialog.get_recommendation(
            recs, None
        )
        if selected_mechanism:
            print(f"Mechanism selected: {selected_mechanism.get('name')}")
        else:
            print("Dialog cancelled or no mechanism selected.")
        run_next_test()  # Proceed to next test

    def run_next_test():
        if current_test_index_ref[0] < len(tests):
            recs, title = tests[current_test_index_ref[0]]
            current_test_index_ref[0] += 1
            # Schedule the test to run after the current event loop iteration
            # to allow the previous dialog to close properly.
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(100, lambda: run_test(recs, title))
        else:
            print("\n--- All tests completed ---")
            app.quit()  # Exit application after tests

    # Start the first test
    run_next_test()

    sys.exit(app.exec())
