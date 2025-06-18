from typing import Any, Dict, List, Optional, Tuple

import numpy as np  # Add numpy import
from scipy.spatial.distance import directed_hausdorff  # Add scipy import
import json  # Add json import

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize, QSizeF, QPointF, QLineF, QRectF
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QPainterPath,
    QPolygonF,
    QTransform,
    QFont,
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

# Mechanism type constants for display
MECHANISM_TYPE_USER_DISPLAY_4_BAR = "4-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_3_BAR = "3-Bar Linkage"
MECHANISM_TYPE_USER_DISPLAY_CAM = "Cam & Follower"

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

    try:
        # Ensure both paths have 2D coordinates
        if len(path1_points.shape) != 2 or path1_points.shape[1] != 2:
            print(f"Warning: path1 has invalid shape {path1_points.shape}")
            return float("inf")
        if len(path2_points.shape) != 2 or path2_points.shape[1] != 2:
            print(f"Warning: path2 has invalid shape {path2_points.shape}")
            return float("inf")

        # Calculate bidirectional Hausdorff distance
        dist_1_to_2 = directed_hausdorff(path1_points, path2_points)[0]
        dist_2_to_1 = directed_hausdorff(path2_points, path1_points)[0]
        distance = max(dist_1_to_2, dist_2_to_1)

        return distance
    except Exception as e:
        print(f"Error calculating Hausdorff distance: {e}")
        return float("inf")


def align_and_compare_paths(
    path1_points: np.ndarray, path2_points: np.ndarray, rotation_steps: int = 72
) -> Tuple[float, Optional[np.ndarray], Optional[np.ndarray], Optional[Dict]]:
    """
    Aligns two paths (translation, scale, rotation) and finds the best match.

    Returns:
        A tuple containing:
        - The minimum Hausdorff distance after alignment.
        - The first path, normalized (centered and scaled).
        - The second path, transformed to best align with the first.
        - A dictionary with the transformation parameters ('center', 'scale', 'rotation').
    """
    if (
        path1_points is None
        or path1_points.shape[0] < 2
        or path2_points is None
        or path2_points.shape[0] < 2
    ):
        return float("inf"), None, None, None

    # 1. Center both paths to origin
    center1 = np.mean(path1_points, axis=0)
    path1_centered = path1_points - center1
    center2 = np.mean(path2_points, axis=0)
    path2_centered = path2_points - center2

    # 2. Normalize scale of both paths to fit in a [-1, 1] box
    max_val1 = np.max(np.abs(path1_centered))
    path1_scaled = (
        path1_centered / max_val1 if not np.isclose(max_val1, 0) else path1_centered
    )

    max_val2 = np.max(np.abs(path2_centered))
    path2_scaled = (
        path2_centered / max_val2 if not np.isclose(max_val2, 0) else path2_centered
    )

    # 3. Find the optimal rotation for path2 to match path1
    min_distance = float("inf")
    best_rotated_path2 = None
    best_angle = 0
    angles = np.linspace(0, 2 * np.pi, rotation_steps, endpoint=False)

    for angle in angles:
        rotation_matrix = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        path2_rotated = path2_scaled @ rotation_matrix.T
        distance = calculate_hausdorff_distance(path1_scaled, path2_rotated)

        if distance < min_distance:
            min_distance = distance
            best_rotated_path2 = path2_rotated
            best_angle = angle

    transform_params = {
        "center": center2.tolist(),
        "scale": max_val2,
        "rotation": best_angle,
    }

    return min_distance, path1_scaled, best_rotated_path2, transform_params


class MechanismPreviewWidget(QGraphicsView):
    """A widget to display a preview of a single mechanism."""

    def __init__(
        self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(500, 400)  # Larger size for better path visibility
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QColor("#ffffff"))  # White background
        self._render_preview()  # Render after background is set and scene is ready

    def _draw_path_comparison(self, bounds: QRectF) -> None:
        """Draws the aligned path comparison."""
        user_path_points = self.mechanism_data.get("user_path_aligned_np")
        mech_path_points = self.mechanism_data.get("mech_path_aligned_np")

        if user_path_points is None or mech_path_points is None:
            print("Debug: Aligned paths not found for preview.")
            text_item = self.scene.addText(
                "Path data not available", QFont("Arial", 14)
            )
            text_item.setDefaultTextColor(QColor("#666666"))
            text_item.setPos(bounds.center().x() - 80, bounds.center().y() - 20)
            return

        def numpy_to_qpainterpath(points: np.ndarray) -> QPainterPath:
            path = QPainterPath()
            if points.shape[0] > 0:
                path.moveTo(QPointF(points[0, 0], points[0, 1]))
                for i in range(1, points.shape[0]):
                    path.lineTo(QPointF(points[i, 0], points[i, 1]))
            return path

        user_path = numpy_to_qpainterpath(user_path_points)
        mech_path = numpy_to_qpainterpath(mech_path_points)

        # The paths are normalized. We just need to scale them to fit the widget.
        draw_area = bounds.adjusted(20, 20, -20, -20)

        # Map the normalized space [-1.1, 1.1] x [-1.1, 1.1] to the draw_area
        source_rect_size = 2.2
        scale_x = draw_area.width() / source_rect_size
        scale_y = draw_area.height() / source_rect_size
        scale = min(scale_x, scale_y) * 0.9  # Use 90% to leave a visual margin

        # Create the transform: move to center, then scale (with Y-flip)
        transform = QTransform()
        transform.translate(draw_area.center().x(), draw_area.center().y())
        transform.scale(scale, -scale)  # Negative y-scale to flip Qt's coordinate system

        # Draw the mechanism structure first so it's in the background
        self._draw_mechanism_structure(transform)

        # Draw user path (red, dashed)
        user_item = QGraphicsPathItem(transform.map(user_path))
        user_pen = QPen(BITTERSWEET, 8.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        user_item.setPen(user_pen)
        self.scene.addItem(user_item)

        # Draw mechanism path (blue, solid)
        mech_item = QGraphicsPathItem(transform.map(mech_path))
        mech_pen = QPen(STEEL_BLUE, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        mech_item.setPen(mech_pen)
        self.scene.addItem(mech_item)

    def _draw_mechanism_structure(self, transform: QTransform) -> None:
        """Draws the mechanism structure (e.g., links and pivots) for a single frame."""
        mech_type = self.mechanism_data.get("original_json_type")
        params = self.mechanism_data.get("parameters")
        full_sim_data = self.mechanism_data.get("full_simulation_data", {})

        if not all([mech_type, params, full_sim_data]):
            return

        # Central dispatcher for drawing mechanisms from simulation data
        if mech_type == "4-bar Coupler" and "joint_positions" in full_sim_data:
            self._draw_4_bar_from_sim(transform, full_sim_data, params)
        elif mech_type in ["Cam-Follower", "Cam Follower"] and "cam_data" in full_sim_data:
            self._draw_cam_follower_from_sim(transform, full_sim_data, params)
        elif mech_type in ["Simple Gear", "Gear Contact"] and "gear_data" in full_sim_data:
            self._draw_simple_gear_from_sim(transform, full_sim_data, params)
        elif mech_type == "Planetary Gear" and "gear_positions" in full_sim_data:
            self._draw_planetary_gear_from_sim(transform, full_sim_data, params)

    def _get_transform_for_sim_data(self, full_sim_data: Dict, path_key: str) -> Optional[callable]:
        """Helper to create a transformation function to align simulation data with the displayed path."""
        mech_path = np.array(full_sim_data.get(path_key, []))
        user_path_aligned = self.mechanism_data.get("user_path_aligned_np")

        if mech_path.size == 0 or user_path_aligned is None:
            return None

        mech_center = np.mean(mech_path, axis=0)
        user_center = np.mean(user_path_aligned, axis=0)

        mech_bbox = np.max(mech_path, axis=0) - np.min(mech_path, axis=0)
        user_bbox = np.max(user_path_aligned, axis=0) - np.min(user_path_aligned, axis=0)

        mech_size = np.max(mech_bbox)
        user_size = np.max(user_bbox)
        scale_factor = user_size / mech_size if mech_size > 0 else 1.0

        def to_screen_coords(p_orig: np.ndarray, transform: QTransform) -> QPointF:
            p_centered = p_orig - mech_center
            p_scaled = p_centered * scale_factor
            p_final = p_scaled + user_center
            return transform.map(QPointF(p_final[0], p_final[1]))

        return to_screen_coords

    def _draw_4_bar_from_sim(self, transform: QTransform, full_sim_data: Dict, params: Dict) -> None:
        """Draws the 4-bar linkage structure using exact simulation positions."""
        joint_positions = full_sim_data["joint_positions"]
        frame_idx = 0

        p1 = np.array(joint_positions["p1_positions"][frame_idx])
        p2 = np.array(joint_positions["p2_positions"][frame_idx])
        p3 = np.array(joint_positions["p3_positions"][frame_idx])
        p4 = np.array(joint_positions["p4_positions"][frame_idx])

        to_screen_coords_func = self._get_transform_for_sim_data(full_sim_data, "coupler_path")
        if not to_screen_coords_func:
            return

        to_screen_coords = lambda p: to_screen_coords_func(p, transform)
        self._draw_4_bar_structure_from_sim(p1, p2, p3, p4, to_screen_coords)

    def _draw_4_bar_structure_from_sim(
        self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray, to_screen_coords: callable
    ) -> None:
        """Draws the 4-bar linkage structure using exact simulation positions with triangular coupler."""
        params = self.mechanism_data.get("parameters", {})
        coupler_point_x = params.get("p_x", 0.0)
        coupler_point_y = params.get("p_y", 0.0)

        coupler_vec = p4 - p3
        if np.linalg.norm(coupler_vec) > 0:
            coupler_unit = coupler_vec / np.linalg.norm(coupler_vec)
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
        else:
            p_coupler = p3

        p1_t, p2_t, p3_t, p4_t, p_coupler_t = map(to_screen_coords, [p1, p2, p3, p4, p_coupler])

        self.scene.addLine(QLineF(p1_t, p3_t), QPen(QColor("#e74c3c"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        self.scene.addLine(QLineF(p2_t, p4_t), QPen(QColor("#f39c12"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2
        if area < 1e-3:
            self.scene.addLine(QLineF(p3_t, p4_t), QPen(QColor("#2ecc71"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        else:
            triangle_polygon = QPolygonF([p3_t, p4_t, p_coupler_t])
            self.scene.addPolygon(triangle_polygon, QPen(QColor("#2ecc71"), 2), QBrush(QColor("#2ecc71").lighter(160)))

        self.scene.addEllipse(p_coupler_t.x() - 3, p_coupler_t.y() - 3, 6, 6, QPen(QColor("#ff0000")), QBrush(QColor("#ff0000")))

    def _draw_cam_follower_from_sim(self, transform: QTransform, full_sim_data: Dict, params: Dict):
        """Draws a cam and follower from simulation data."""
        cam_data = full_sim_data["cam_data"]
        frame_idx = 0

        cam_center = np.array(cam_data["cam_centers"][frame_idx])
        follower_y = cam_data["follower_y_positions"][frame_idx]
        base_radius = params.get("base_radius")

        to_screen_coords_func = self._get_transform_for_sim_data(
            {"follower_path": [[0, y] for y in cam_data["follower_y_positions"]]}, "follower_path"
        )
        if not to_screen_coords_func:
            return

        to_screen_coords = lambda p: to_screen_coords_func(p, transform)

        cam_path = QPainterPath()
        for i in range(101):
            theta = 2 * np.pi * i / 100
            p_orig = cam_center + base_radius * np.array([np.cos(theta), np.sin(theta)])
            p_screen = to_screen_coords(p_orig)
            if i == 0: cam_path.moveTo(p_screen)
            else: cam_path.lineTo(p_screen)
        self.scene.addPath(cam_path, QPen(QColor("#e74c3c"), 4), QBrush(QColor("#e74c3c").lighter(160)))

        follower_pos_orig = np.array([0, follower_y])
        w, h = 20, 10
        tl = follower_pos_orig + np.array([-w/2, h/2]); tr = follower_pos_orig + np.array([w/2, h/2])
        br = follower_pos_orig + np.array([w/2, -h/2]); bl = follower_pos_orig + np.array([-w/2, -h/2])
        follower_poly = QPolygonF([to_screen_coords(p) for p in [tl, tr, br, bl]])
        self.scene.addPolygon(follower_poly, QPen(QColor("#2ecc71"), 3), QBrush(QColor("#2ecc71").lighter(160)))

    def _draw_simple_gear_from_sim(self, transform: QTransform, full_sim_data: Dict, params: Dict):
        """Draws a simple gear train from simulation data."""
        gear_data = full_sim_data["gear_data"]
        frame_idx = 0

        g1_center = np.array(gear_data["gear1_centers"][frame_idx])
        g2_center = np.array(gear_data["gear2_centers"][frame_idx])
        theta1 = gear_data["gear1_angles"][frame_idx]
        theta2 = gear_data["gear2_angles"][frame_idx]
        r1, r2 = params.get("r1"), params.get("r2")

        to_screen_coords_func = self._get_transform_for_sim_data(gear_data, "tracking_points")
        if not to_screen_coords_func:
            return

        to_screen_coords = lambda p: to_screen_coords_func(p, transform)

        def draw_gear(center, radius, angle, color):
            path = QPainterPath()
            for i in range(101):
                theta = 2 * np.pi * i / 100
                p_orig = center + radius * np.array([np.cos(theta), np.sin(theta)])
                p_screen = to_screen_coords(p_orig)
                if i == 0: path.moveTo(p_screen)
                else: path.lineTo(p_screen)
            self.scene.addPath(path, QPen(color, 4), QBrush(color.lighter(170)))

            p1 = to_screen_coords(center)
            p2 = to_screen_coords(center + radius * np.array([np.cos(angle), np.sin(angle)]))
            self.scene.addLine(QLineF(p1, p2), QPen(QColor("white"), 2))

        draw_gear(g1_center, r1, theta1, QColor("#3498db"))
        draw_gear(g2_center, r2, theta2, QColor("#2ecc71"))

    def _draw_planetary_gear_from_sim(self, transform: QTransform, full_sim_data: Dict, params: Dict):
        """Draws a planetary gear system from simulation data."""
        gear_pos = full_sim_data["gear_positions"]
        frame_idx = 0

        sun_center = np.array(gear_pos["sun_centers"][frame_idx])
        planet_center = np.array(gear_pos["planet_centers"][frame_idx])
        tracking_point = np.array(gear_pos["tracking_points"][frame_idx])
        r_sun, r_planet = params.get("r_sun"), params.get("r_planet")

        to_screen_coords_func = self._get_transform_for_sim_data(gear_pos, "tracking_points")
        if not to_screen_coords_func:
            return

        to_screen_coords = lambda p: to_screen_coords_func(p, transform)

        def draw_gear(center, radius, color):
            p1_screen = to_screen_coords(center)
            p2_screen = to_screen_coords(center + np.array([radius, 0]))
            radius_screen = QLineF(p1_screen, p2_screen).length()

            self.scene.addEllipse(
                p1_screen.x() - radius_screen, p1_screen.y() - radius_screen,
                radius_screen * 2, radius_screen * 2,
                QPen(color, 4), QBrush(color.lighter(150))
            )

        draw_gear(sun_center, r_sun, QColor("#7f8c8d"))
        draw_gear(planet_center, r_planet, QColor("#e67e22"))

        p1 = to_screen_coords(planet_center)
        p2 = to_screen_coords(tracking_point)
        self.scene.addLine(QLineF(p1, p2), QPen(QColor("#f39c12"), 3))
        self.scene.addEllipse(p2.x() - 5, p2.y() - 5, 10, 10, QPen(QColor("#e74c3c")), QBrush(QColor("#e74c3c")))

    def _render_preview(self) -> None:
        self.scene.clear()
        margin = 5
        view_rect_int = self.rect()
        view_rect_f = QRectF(view_rect_int)
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)

        self.scene.setSceneRect(view_rect_f)
        self._draw_path_comparison(view_rect_adjusted_f)

    def _setup_scene_and_transform(self) -> QRectF:
        """Clears and sets up the scene, returns the drawing area."""
        self.scene.clear()
        margin = 5
        view_rect_f = QRectF(self.rect())
        self.scene.setSceneRect(view_rect_f)
        return view_rect_f.adjusted(margin, margin, -margin, -margin)


class PreviewContainer(QWidget):
    """Container for a single preview and its title/select button."""

    selected = Signal(dict)
    clicked = Signal(dict)

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

        name = self.mechanism_data.get("name", "Unnamed Mechanism")
        if ":" in name:
            mech_type = name.split(":")[0].strip()
        else:
            mech_type = name
        title_label = QLabel(mech_type)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 5px;
            }
        """)
        layout.addWidget(title_label)

        self.preview_widget = MechanismPreviewWidget(self.mechanism_data, self)
        self.preview_widget.setStyleSheet("""
            QGraphicsView {
                border: 3px solid transparent;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)
        layout.addWidget(self.preview_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        score = self.mechanism_data.get("overall_score", 0)
        print(f"Debug PreviewContainer: overall_score = {score}")

        if score is not None and score >= 0:
            import math
            similarity_percentage = max(0, min(100, math.exp(-score * 5) * 100))
        else:
            similarity_percentage = 0

        match_label = QLabel(f"Match: {similarity_percentage:.1f}%")
        match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        match_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #1e8449;
                padding: 10px;
                background-color: #e8f6ef;
                border-radius: 5px;
                border: 1px solid #d1e7dd;
            }
        """)
        layout.addWidget(match_label)

        select_button = QPushButton("Select This")
        select_button.setFixedSize(140, 40)
        select_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 15px;
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
        self.setMinimumWidth(520)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_data)
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
        return QSize(520, 550)

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()


class MechanismRecommendationDialog(QDialog):
    mechanism_selected = Signal(dict)
    mechanism_preview_selected = Signal(dict)

    def __init__(
        self,
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Choose a Mechanism")
        self.setMinimumSize(1400, 800)
        self.selected_mechanism_data: Optional[Dict[str, Any]] = None

        self.user_motion_path_original = user_motion_path
        self.user_motion_path_np = qpainterpath_to_numpy_array(
            user_motion_path, num_samples_user_path
        )

        self.generated_paths_filepath = generated_paths_filepath
        self.generated_paths_data = self._load_generated_paths(generated_paths_filepath)
        print(f"Debug: Loaded {len(self.generated_paths_data)} mechanism paths from JSON")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

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

        subtitle_label = QLabel(
            "The red dashed line shows your drawn path. The blue line is the mechanism's path. Click on a mechanism to select it."
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
                    rec_data_with_user_path = rec_data.copy()
                    rec_data_with_user_path["user_motion_path_local"] = (
                        self.user_motion_path_original
                    )

                    container = PreviewContainer(rec_data_with_user_path, self)
                    container.selected.connect(self._on_select)
                    container.clicked.connect(self._on_preview_click)
                    self.previews_layout.addWidget(container)
                    self.preview_containers.append(container)
                else:
                    placeholder_label = QLabel("No mechanism found")
                    placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder_label.setFixedSize(220, 280)
                    placeholder_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #cccccc;")
                    self.previews_layout.addWidget(placeholder_label)
            self.previews_layout.addStretch()
        else:
            no_recs_label = QLabel(
                "No mechanism recommendations could be generated or found."
            )
            no_recs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.previews_layout.addWidget(no_recs_label)

        main_layout.addLayout(self.previews_layout)

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
        self.ok_button.clicked.connect(self._on_ok_clicked)
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
                path_coords = None
                mech_type = item.get("type")

                if mech_type == "4-bar Coupler":
                    full_sim_data = item.get("full_simulation_data", {})
                    if "coupler_path" in full_sim_data:
                        path_coords = full_sim_data["coupler_path"]
                    else:
                        path_coords = item.get("key_points", {}).get("coupler_point_path")

                elif mech_type == "Cam-Follower":
                    full_sim_data = item.get("full_simulation_data", {})
                    if "follower_path" in full_sim_data:
                        path_coords = full_sim_data["follower_path"]

                elif mech_type == "Simple Gear":
                    full_sim_data = item.get("full_simulation_data", {})
                    if "tracking_path" in full_sim_data:
                        path_coords = full_sim_data["tracking_path"]

                elif mech_type == "Planetary Gear":
                    full_sim_data = item.get("full_simulation_data", {})
                    if "tracking_path" in full_sim_data:
                        path_coords = full_sim_data["tracking_path"]

                if not path_coords:
                    path_coords = item.get("path_coordinates")

                if (
                    path_coords
                    and isinstance(path_coords, list)
                    and len(path_coords) > 0
                ):
                    try:
                        item["path_coordinates_np"] = np.array(path_coords, dtype=float)
                        loaded_paths.append(item)
                    except ValueError as e:
                        print(
                            f"Warning: Could not convert path_coordinates to numpy array for item: {item.get('type', 'N/A')}. Error: {e}"
                        )
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
        Finds the best mechanism from each type by comparing user path with JSON database.
        """
        if self.user_motion_path_np is None or not self.generated_paths_data:
            print("Error: User motion path is not processed or no generated paths loaded.")
            return []

        print(f"Debug: User path has {len(self.user_motion_path_np)} points")
        print(f"Debug: Total mechanisms in database: {len(self.generated_paths_data)}")

        type_mapping = {
            "4-bar Coupler": "4-Bar Linkage",
            "3-bar Output": "3-Bar Linkage",
            "Cam Profile": "Cam & Follower",
            "Cam-Follower": "Cam & Follower",
            "Gear Train": "Gears (Simple Pair)",
            "Gear Contact": "Gears (Simple Pair)",
            "Simple Gear": "Gears (Simple Pair)",
            "Planetary Gear": "Planetary Gear",
            "line": "Linear Motion"
        }

        mechanisms_by_type = {}
        total_comparisons = 0

        for gen_path_data in self.generated_paths_data:
            gen_path_np = gen_path_data.get("path_coordinates_np")
            json_type_str = gen_path_data.get("type")

            if gen_path_np is None or json_type_str is None:
                continue

            total_comparisons += 1

            (
                distance,
                user_path_aligned,
                gen_path_aligned,
                transform_params,
            ) = align_and_compare_paths(self.user_motion_path_np, gen_path_np)

            if user_path_aligned is None or gen_path_aligned is None:
                continue

            if total_comparisons <= 5:
                print(
                    f"Debug sample {total_comparisons}: {json_type_str} - distance: {distance:.2f}"
                )

            display_type = type_mapping.get(json_type_str, json_type_str)

            preview_data = {
                "name": gen_path_data.get("name", f"{json_type_str} Mechanism"),
                "type": display_type,
                "original_json_type": json_type_str,
                "overall_score": distance,
                "parameters": gen_path_data.get("parameters", {}),
                "path_coordinates_np": gen_path_np,
                "path_coordinates": gen_path_data.get("path_coordinates"),
                "key_points": gen_path_data.get("key_points", {}),
                "path_normalization": gen_path_data.get("path_normalization", {}),
                "full_simulation_data": gen_path_data.get("full_simulation_data", {}),
                "user_path_aligned_np": user_path_aligned,
                "mech_path_aligned_np": gen_path_aligned,
                "transform_params": transform_params,
            }

            dataset_vis_params = gen_path_data.get("visualization_params")
            if dataset_vis_params:
                preview_data["visualization_params"] = dataset_vis_params
            else:
                all_mech_points = self._get_mechanism_points_orig(preview_data)
                if all_mech_points is not None:
                    vis_center = np.mean(all_mech_points, axis=0)
                    vis_scale = np.max(np.abs(all_mech_points - vis_center))
                    preview_data["visualization_params"] = {
                        "center": vis_center.tolist(),
                        "scale": vis_scale if not np.isclose(vis_scale, 0) else 1.0,
                    }
                else:
                    preview_data["visualization_params"] = {
                        "center": transform_params["center"],
                        "scale": transform_params["scale"],
                    }

            if display_type not in mechanisms_by_type:
                mechanisms_by_type[display_type] = preview_data
            else:
                if distance < mechanisms_by_type[display_type]["overall_score"]:
                    mechanisms_by_type[display_type] = preview_data

        print(f"Debug: Made {total_comparisons} path comparisons")
        print(f"Debug: Found {len(mechanisms_by_type)} mechanism types: {list(mechanisms_by_type.keys())}")

        best_mechanisms = list(mechanisms_by_type.values())
        best_mechanisms.sort(key=lambda x: x["overall_score"])
        top_3 = best_mechanisms[:3]

        for i, mech in enumerate(top_3):
            print(f"Debug: Recommendation {i+1}: {mech['type']} - {mech['name']} (score: {mech['overall_score']:.2f})")

        while len(top_3) < 3:
            top_3.append(None)

        return top_3

    def _on_select(self, mechanism_data: Dict[str, Any]) -> None:
        self.selected_mechanism_data = mechanism_data
        self.ok_button.setEnabled(True)
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)

    def _on_preview_click(self, mechanism_data: Dict[str, Any]) -> None:
        """Handle preview click to show mechanism in main view."""
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)
        self.mechanism_preview_selected.emit(mechanism_data)

    def _on_ok_clicked(self) -> None:
        """Handle OK button click - emit signal and accept dialog."""
        if self.selected_mechanism_data:
            self.mechanism_selected.emit(self.selected_mechanism_data)
        self.accept()

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

    def _get_mechanism_points_orig(
        self, mechanism_data: Dict[str, Any]
    ) -> Optional[np.ndarray]:
        """Gathers all points of the mechanism (structure and path) in original coordinates."""
        params = mechanism_data.get("parameters")
        path_points = mechanism_data.get("path_coordinates_np")

        if path_points is None or params is None:
            return None

        all_points = [path_points]
        mech_type = mechanism_data.get("original_json_type")
        key_points = mechanism_data.get("key_points")

        if mech_type == "4-bar Coupler" and key_points:
            p1_coords = key_points.get("ground_pivot_1")
            p2_coords = key_points.get("ground_pivot_2")
            p3_coords = key_points.get("initial_moving_joint_1")
            p4_coords = key_points.get("initial_moving_joint_2")

            pivot_points = []
            for coords in [p1_coords, p2_coords, p3_coords, p4_coords]:
                if coords:
                    pivot_points.append(coords)

            if pivot_points:
                all_points.append(np.array(pivot_points))

        elif mech_type == "Cam Follower":
            base_radius = params.get("base_radius")
            eccentricity = params.get("eccentricity")
            if base_radius is not None and eccentricity is not None:
                if key_points:
                    cam_center_coords = key_points.get("cam_center")
                    rotation_center_coords = key_points.get("rotation_center")
                    if cam_center_coords:
                        cam_center_orig = np.array(cam_center_coords)
                    else:
                        cam_center_orig = np.array([eccentricity, 0])
                    if rotation_center_coords:
                        all_points.append(np.array([rotation_center_coords]))
                else:
                    cam_center_orig = np.array([eccentricity, 0])
                    all_points.append(np.array([[0, 0]]))

                thetas = np.linspace(0, 2 * np.pi, 20)
                cam_points = cam_center_orig + base_radius * np.array(
                    [np.cos(thetas), np.sin(thetas)]
                ).T
                all_points.append(cam_points)

        elif mech_type == "Gear Contact":
            r1, r2 = params.get("r1"), params.get("r2")
            if r1 and r2:
                if key_points:
                    gear1_center = key_points.get("gear1_center", [0, 0])
                    gear2_center = key_points.get("gear2_center", [r1 + r2, 0])
                else:
                    gear1_center = [0, 0]
                    gear2_center = [r1 + r2, 0]

                c1_orig = np.array(gear1_center)
                c2_orig = np.array(gear2_center)
                thetas = np.linspace(0, 2 * np.pi, 20)
                g1_points = c1_orig + r1 * np.array([np.cos(thetas), np.sin(thetas)]).T
                g2_points = c2_orig + r2 * np.array(
                    [np.cos(thetas), np.sin(thetas)]
                ).T
                all_points.append(g1_points)
                all_points.append(g2_points)

        return np.vstack(all_points)


if __name__ == "__main__":
    import sys
    import logging
    from PyQt6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

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
        None,
        {
            "name": "Another Cam",
            "type": "cam",
            "overall_score": 0.60,
        },
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
    current_test_index_ref = [0]

    def run_test(recs, title):
        print(f"\n--- Running Test: {title} ---")
        selected_mechanism = MechanismRecommendationDialog.get_recommendation(
            recs, None
        )
        if selected_mechanism:
            print(f"Mechanism selected: {selected_mechanism.get('name')}")
        else:
            print("Dialog cancelled or no mechanism selected.")
        run_next_test()

    def run_next_test():
        if current_test_index_ref[0] < len(tests):
            recs, title = tests[current_test_index_ref[0]]
            current_test_index_ref[0] += 1
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(100, lambda: run_test(recs, title))
        else:
            print("\n--- All tests completed ---")
            app.quit()

    run_next_test()

    sys.exit(app.exec())
