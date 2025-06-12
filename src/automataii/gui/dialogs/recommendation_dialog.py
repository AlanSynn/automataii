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
        key_points = self.mechanism_data.get("key_points")
        full_sim_data = self.mechanism_data.get("full_simulation_data", {})
        
        if not all([mech_type, params]):
            return

        # Use the full simulation data for accurate positioning that matches the displayed paths
        if mech_type == "4-bar Coupler" and "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            frame_idx = 0  # Use first frame for static display
            
            if all(key in joint_positions for key in ["p1_positions", "p2_positions", "p3_positions", "p4_positions"]):
                p1 = np.array(joint_positions["p1_positions"][frame_idx])
                p2 = np.array(joint_positions["p2_positions"][frame_idx])
                p3 = np.array(joint_positions["p3_positions"][frame_idx])
                p4 = np.array(joint_positions["p4_positions"][frame_idx])
                
                # Create a direct transformation that matches the displayed paths exactly
                user_path_aligned = self.mechanism_data.get("user_path_aligned_np")
                mech_path_aligned = self.mechanism_data.get("mech_path_aligned_np")
                
                if user_path_aligned is not None and mech_path_aligned is not None:
                    # Get the mechanism's coupler path from simulation data
                    mech_coupler_path = None
                    if "coupler_path" in full_sim_data:
                        mech_coupler_path = np.array(full_sim_data["coupler_path"])
                    elif "coupler_positions" in joint_positions:
                        mech_coupler_path = np.array(joint_positions["coupler_positions"])
                    
                    if mech_coupler_path is not None:
                        # Calculate transformation that maps mechanism space to aligned display space
                        mech_center = np.mean(mech_coupler_path, axis=0)
                        user_center = np.mean(user_path_aligned, axis=0)
                        
                        mech_bbox = np.max(mech_coupler_path, axis=0) - np.min(mech_coupler_path, axis=0)
                        user_bbox = np.max(user_path_aligned, axis=0) - np.min(user_path_aligned, axis=0)
                        
                        # Calculate scale to match the aligned paths
                        if np.any(mech_bbox == 0):
                            scale_factor = 1.0
                        else:
                            mech_size = np.max(mech_bbox)
                            user_size = np.max(user_bbox)
                            scale_factor = user_size / mech_size if mech_size > 0 else 1.0
                        
                        def to_screen_coords(p_orig: np.ndarray) -> QPointF:
                            # Transform to match the aligned paths exactly
                            p_centered = p_orig - mech_center
                            p_scaled = p_centered * scale_factor
                            p_final = p_scaled + user_center
                            # Apply the final transform to screen coordinates
                            return transform.map(QPointF(p_final[0], p_final[1]))
                        
                        self._draw_4_bar_structure_from_sim(p1, p2, p3, p4, to_screen_coords)
                        return
        
        # Fallback to original method if simulation data not available
        transform_params = self.mechanism_data.get("transform_params")
        vis_params = self.mechanism_data.get("visualization_params")
        path_norm = self.mechanism_data.get("path_normalization", {})

        if not all([transform_params, vis_params]):
            return

        # Use transformation parameters from the alignment process for consistency
        center = np.array(transform_params["center"])
        scale = transform_params["scale"]
        angle = transform_params["rotation"]

        if np.isclose(scale, 0):
            return

        rotation_matrix = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )

        def to_screen_coords(p_orig: np.ndarray) -> QPointF:
            # Apply the same transformation as align_and_compare_paths to the mechanism points
            p_centered = p_orig - center
            p_scaled = p_centered / scale
            p_rotated = p_scaled @ rotation_matrix.T
            p_qpoint_norm = QPointF(p_rotated[0], p_rotated[1])
            # The 'transform' object handles scaling to view and centering
            return transform.map(p_qpoint_norm)

        if mech_type == "4-bar Coupler" and key_points:
            self._draw_4_bar_structure(params, key_points, to_screen_coords)
        elif mech_type in ["Cam Follower", "Cam-Follower"]:
            self._draw_cam_follower_structure(params, key_points, to_screen_coords)
        elif mech_type in ["Gear Contact", "Simple Gear"]:
            self._draw_gear_contact_structure(params, key_points, to_screen_coords)
        elif mech_type == "Planetary Gear":
            self._draw_planetary_gear_structure(params, key_points, to_screen_coords)

    def _draw_4_bar_structure_from_sim(
        self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray, to_screen_coords: callable
    ) -> None:
        """Draws the 4-bar linkage structure using exact simulation positions with triangular coupler."""
        # Get coupler point parameters from mechanism data
        params = self.mechanism_data.get("parameters", {})
        coupler_point = params.get("coupler_point", {})
        coupler_point_x = coupler_point.get("x", 0.0)
        coupler_point_y = coupler_point.get("y", 0.0)
        
        # Calculate coupler point position (same as dataset generator)
        coupler_vec = p4 - p3
        coupler_length = np.linalg.norm(coupler_vec)
        if coupler_length > 0:
            coupler_unit = coupler_vec / coupler_length
            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
        else:
            p_coupler = p3

        # Transform all points to screen coordinates
        p1_t = to_screen_coords(p1)
        p2_t = to_screen_coords(p2)
        p3_t = to_screen_coords(p3)
        p4_t = to_screen_coords(p4)
        p_coupler_t = to_screen_coords(p_coupler)

        # Draw basic links (driver and follower)
        driver_pen = QPen(QColor("#e74c3c"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.scene.addLine(QLineF(p1_t, p3_t), driver_pen)  # Driver link - red
        
        follower_pen = QPen(QColor("#f39c12"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.scene.addLine(QLineF(p2_t, p4_t), follower_pen)  # Follower link - orange

        # Check if coupler forms a triangle or is collinear (same as dataset generator)
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2
        
        if area < 1e-3:  # Collinear - show as line
            coupler_pen = QPen(QColor("#2ecc71"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            self.scene.addLine(QLineF(p3_t, p4_t), coupler_pen)
        else:  # Non-collinear - show as triangle
            # Create triangular coupler plate (p3, p4, coupler_point)
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)
            
            triangle_pen = QPen(QColor("#2ecc71"), 2, Qt.PenStyle.SolidLine)
            triangle_brush = QBrush(QColor("#2ecc71").lighter(160))
            triangle_path_item = self.scene.addPolygon(triangle_polygon, triangle_pen, triangle_brush)
            triangle_path_item.setOpacity(0.7)

        # Add coupler point marker (red dot)
        coupler_pen = QPen(QColor("#ff0000"), 2)
        coupler_brush = QBrush(QColor("#ff0000"))
        self.scene.addEllipse(p_coupler_t.x() - 3, p_coupler_t.y() - 3, 6, 6, coupler_pen, coupler_brush)

    def _draw_4_bar_structure(
        self, params: Dict, key_points: Dict, to_screen_coords: callable
    ) -> None:
        """Draws the structure of a 4-bar linkage for the initial position."""
        l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
        p1_coords = key_points.get("ground_pivot_1")
        p2_coords = key_points.get("ground_pivot_2")

        if not all([l2, l3, l4, p1_coords, p2_coords]):
            return

        # Define pivots in their original coordinate system
        p1 = np.array(p1_coords, dtype=float)
        p2 = np.array(p2_coords, dtype=float)

        # Use pre-calculated initial positions from the dataset if available
        p3_coords = key_points.get("initial_moving_joint_1")
        p4_coords = key_points.get("initial_moving_joint_2")

        if p3_coords and p4_coords:
            p3 = np.array(p3_coords, dtype=float)
            p4 = np.array(p4_coords, dtype=float)
        else:
            # Fallback to calculation if points are not in dataset
            theta2 = 0
            p3 = p1 + np.array([l2 * np.cos(theta2), l2 * np.sin(theta2)])
            d_sq = np.sum((p2 - p3) ** 2)
            d = np.sqrt(d_sq)
            if d > (l3 + l4) or d < abs(l3 - l4): return
            a = (l3**2 - l4**2 + d_sq) / (2 * d)
            h = np.sqrt(max(0, l3**2 - a**2))
            p3_p2_unit = (p2 - p3) / d
            midpoint = p3 + a * p3_p2_unit
            p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        # Transform all points to screen coordinates
        p1_t = to_screen_coords(p1)
        p2_t = to_screen_coords(p2)
        p3_t = to_screen_coords(p3)
        p4_t = to_screen_coords(p4)

        # Draw links with colorful style
        link_colors = [QColor("#e74c3c"), QColor("#3498db"), QColor("#2ecc71"), QColor("#9b59b6")]
        links = [
            QLineF(p1_t, p3_t),  # Link 1 - red
            QLineF(p3_t, p4_t),  # Link 2 - blue
            QLineF(p4_t, p2_t),  # Link 3 - green
            QLineF(p2_t, p1_t)   # Link 4 (ground) - purple
        ]

        for i, (line, color) in enumerate(zip(links, link_colors)):
            link_pen = QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            self.scene.addLine(line, link_pen)

        # Draw pivots with colorful style
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]

        for pos, color in zip(pivot_positions, pivot_colors):
            # Outer circle
            self.scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                QPen(color.darker(150), 2),
                QBrush(color)
            )
            # Inner highlight
            self.scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )

    def _draw_cam_follower_structure(
        self, params: Dict, key_points: Dict, to_screen_coords: callable
    ) -> None:
        """Draws a cam and follower mechanism."""
        base_radius = params.get("base_radius")
        eccentricity = params.get("eccentricity")
        if not all([base_radius, eccentricity is not None]):
            return

        # Use key_points for accurate positioning if available
        if key_points and "cam_center" in key_points:
            cam_center_orig = np.array(key_points["cam_center"])
        else:
            # Cam is a circle with center offset by eccentricity. Assume rotation center is origin.
            cam_center_orig = np.array([eccentricity, 0])

        # Draw cam profile by transforming a set of points on its circumference
        cam_path = QPainterPath()
        num_points = 100
        for i in range(num_points + 1):
            theta = 2 * np.pi * i / num_points
            p_orig = cam_center_orig + base_radius * np.array(
                [np.cos(theta), np.sin(theta)]
            )
            p_screen = to_screen_coords(p_orig)
            if i == 0:
                cam_path.moveTo(p_screen)
            else:
                cam_path.lineTo(p_screen)

        cam_pen = QPen(QColor("#e74c3c"), 6, Qt.PenStyle.SolidLine)
        cam_fill = QBrush(QColor("#e74c3c").lighter(160))
        self.scene.addPath(cam_path, cam_pen, cam_fill)

        # Draw center of rotation and cam center with colorful style
        rot_center_screen = to_screen_coords(np.array([0, 0]))
        cam_center_screen = to_screen_coords(cam_center_orig)

        # Rotation center - orange
        rot_color = QColor("#f39c12")
        self.scene.addEllipse(
            rot_center_screen.x() - 8,
            rot_center_screen.y() - 8,
            16,
            16,
            QPen(rot_color.darker(150), 2),
            QBrush(rot_color),
        )
        self.scene.addEllipse(
            rot_center_screen.x() - 4,
            rot_center_screen.y() - 4,
            8,
            8,
            QPen(Qt.PenStyle.NoPen),
            QBrush(rot_color.lighter(150)),
        )

        # Cam center - blue
        cam_center_color = QColor("#3498db")
        self.scene.addEllipse(
            cam_center_screen.x() - 6,
            cam_center_screen.y() - 6,
            12,
            12,
            QPen(cam_center_color.darker(150), 2),
            QBrush(cam_center_color),
        )

    def _draw_gear_contact_structure(
        self, params: Dict, key_points: Dict, to_screen_coords: callable
    ) -> None:
        """Draws a simple gear train."""
        r1 = params.get("r1")
        r2 = params.get("r2")
        if not all([r1, r2]):
            return

        # Use key_points for accurate positioning if available
        if key_points:
            c1_orig = np.array(key_points.get("gear1_center", [-r1, 0]))
            c2_orig = np.array(key_points.get("gear2_center", [r2, 0]))
        else:
            # Default positions from dataset generation
            c1_orig = np.array([-r1, 0])
            c2_orig = np.array([r2, 0])

        def draw_gear(center_orig, radius, color, pivot_color):
            gear_path = QPainterPath()
            num_points = 100
            for i in range(num_points + 1):
                theta = 2 * np.pi * i / num_points
                p_orig = center_orig + radius * np.array(
                    [np.cos(theta), np.sin(theta)]
                )
                p_screen = to_screen_coords(p_orig)
                if i == 0:
                    gear_path.moveTo(p_screen)
                else:
                    gear_path.lineTo(p_screen)
            gear_pen = QPen(color, 6, Qt.PenStyle.SolidLine)
            gear_fill = QBrush(color.lighter(170))
            self.scene.addPath(gear_path, gear_pen, gear_fill)

            center_screen = to_screen_coords(center_orig)
            # Center pivot with colorful style
            self.scene.addEllipse(
                center_screen.x() - 8,
                center_screen.y() - 8,
                16,
                16,
                QPen(pivot_color.darker(150), 2),
                QBrush(pivot_color),
            )
            self.scene.addEllipse(
                center_screen.x() - 4,
                center_screen.y() - 4,
                8,
                8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(pivot_color.lighter(150)),
            )

        # Draw gears with different colors
        draw_gear(c1_orig, r1, QColor("#3498db"), QColor("#f39c12"))
        draw_gear(c2_orig, r2, QColor("#2ecc71"), QColor("#e74c3c"))

    def _draw_planetary_gear_structure(
        self, params: Dict, key_points: Dict, to_scene_coords: callable
    ) -> None:
        """Draws a planetary gear system."""
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)
        
        # Initial positions
        sun_center_orig = np.array([0, 0])
        planet_center_orig = np.array([r_sun + r_planet, 0])  # Initial planet position
        tracking_point_orig = planet_center_orig + np.array([arm_length, 0])
        
        # Transform to scene coordinates
        sun_center_scene = to_scene_coords(sun_center_orig)
        planet_center_scene = to_scene_coords(planet_center_orig)
        tracking_scene = to_scene_coords(tracking_point_orig)
        
        # Draw sun gear (stationary)
        sun_color = QColor("#7f8c8d")  # Gray
        self.scene.addEllipse(
            sun_center_scene.x() - r_sun, sun_center_scene.y() - r_sun,
            r_sun * 2, r_sun * 2,
            QPen(sun_color, 4),
            QBrush(sun_color.lighter(140))
        )
        
        # Draw planet gear
        planet_color = QColor("#e67e22")  # Orange
        self.scene.addEllipse(
            planet_center_scene.x() - r_planet, planet_center_scene.y() - r_planet,
            r_planet * 2, r_planet * 2,
            QPen(planet_color, 4),
            QBrush(planet_color.lighter(150))
        )
        
        # Draw arm from planet center to tracking point
        arm_color = QColor("#f39c12")  # Gold
        self.scene.addLine(
            planet_center_scene.x(), planet_center_scene.y(),
            tracking_scene.x(), tracking_scene.y(),
            QPen(arm_color, 3)
        )
        
        # Draw tracking point
        tracking_color = QColor("#e74c3c")  # Red
        self.scene.addEllipse(
            tracking_scene.x() - 8, tracking_scene.y() - 8, 16, 16,
            QPen(tracking_color.darker(150), 3),
            QBrush(tracking_color)
        )
        
        # Sun center marker
        sun_center_color = QColor("#34495e")  # Dark gray
        self.scene.addEllipse(
            sun_center_scene.x() - 6, sun_center_scene.y() - 6, 12, 12,
            QPen(sun_center_color, 2),
            QBrush(sun_center_color)
        )

    def _render_preview(self) -> None:
        self.scene.clear()
        # Use the ENTIRE widget area with minimal margin
        margin = 5
        view_rect_int = self.rect()
        view_rect_f = QRectF(view_rect_int)
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)

        # Set sceneRect to the viewable area
        self.scene.setSceneRect(view_rect_f)

        # Draw ONLY path comparison - no mechanism structures
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
        # Extract just the mechanism type from name
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

        # Similarity percentage label
        score = self.mechanism_data.get("overall_score", 0)
        print(f"Debug PreviewContainer: overall_score = {score}")  # Debug

        # Convert Hausdorff distance score to similarity percentage
        if score is not None and score >= 0:
            import math
            # Use exponential decay: lower score = higher similarity. Tuned for normalized scores.
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

        # Select Button with better styling
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
        self.setMinimumWidth(520)  # Width to match new preview widget size
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
        return QSize(520, 550)  # Increased height to accommodate larger preview widget

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
        self.setMinimumSize(1400, 800)  # Increased dialog size for better visibility
        self.selected_mechanism_data: Optional[Dict[str, Any]] = None

        self.user_motion_path_original = (
            user_motion_path  # Keep original QPainterPath for preview
        )
        self.user_motion_path_np = qpainterpath_to_numpy_array(
            user_motion_path, num_samples_user_path
        )

        self.generated_paths_filepath = generated_paths_filepath
        self.generated_paths_data = self._load_generated_paths(generated_paths_filepath)
        print(f"Debug: Loaded {len(self.generated_paths_data)} mechanism paths from JSON")

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
                path_coords = None
                mech_type = item.get("type")

                # For 4-bar, use the full simulation coupler path if available, otherwise normalized path
                if mech_type == "4-bar Coupler":
                    # Try to get the full simulation path first (from new dataset structure)
                    full_sim_data = item.get("full_simulation_data", {})
                    if "coupler_path" in full_sim_data:
                        path_coords = full_sim_data["coupler_path"]
                    else:
                        # Fallback to old structure
                        path_coords = item.get("key_points", {}).get("coupler_point_path")

                # Use normalized path coordinates for all types if full path not available
                if not path_coords:
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
        Finds the best mechanism from each type by comparing user path with JSON database.
        """
        if self.user_motion_path_np is None or not self.generated_paths_data:
            print("Error: User motion path is not processed or no generated paths loaded.")
            return []

        print(f"Debug: User path has {len(self.user_motion_path_np)} points")
        print(f"Debug: Total mechanisms in database: {len(self.generated_paths_data)}")

        # Mapping from JSON type strings to user-friendly display names
        type_mapping = {
            "4-bar Coupler": "4-Bar Linkage",
            "3-bar Output": "3-Bar Linkage",
            "Cam Profile": "Cam & Follower",
            "Cam-Follower": "Cam & Follower",  # Match dataset type
            "Gear Train": "Gears (Simple Pair)",
            "Gear Contact": "Gears (Simple Pair)",
            "Simple Gear": "Gears (Simple Pair)",  # Match dataset type
            "Planetary Gear": "Planetary Gear",  # Match dataset type
            "line": "Linear Motion"
        }

        # Group mechanisms by type and find best match for each
        mechanisms_by_type = {}
        total_comparisons = 0

        for gen_path_data in self.generated_paths_data:
            gen_path_np = gen_path_data.get("path_coordinates_np")
            json_type_str = gen_path_data.get("type")

            if gen_path_np is None or json_type_str is None:
                continue

            total_comparisons += 1

            # Align paths and calculate distance
            (
                distance,
                user_path_aligned,
                gen_path_aligned,
                transform_params,
            ) = align_and_compare_paths(self.user_motion_path_np, gen_path_np)

            if user_path_aligned is None or gen_path_aligned is None:
                continue

            # Log some samples for debugging
            if total_comparisons <= 5:
                print(
                    f"Debug sample {total_comparisons}: {json_type_str} - distance: {distance:.2f}"
                )

            display_type = type_mapping.get(json_type_str, json_type_str)

            # Create mechanism data for preview
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

            # Use visualization parameters from dataset if available, otherwise calculate from geometry
            dataset_vis_params = gen_path_data.get("visualization_params")
            if dataset_vis_params:
                preview_data["visualization_params"] = dataset_vis_params
            else:
                # Fallback: calculate from mechanism geometry
                all_mech_points = self._get_mechanism_points_orig(preview_data)
                if all_mech_points is not None:
                    vis_center = np.mean(all_mech_points, axis=0)
                    vis_scale = np.max(np.abs(all_mech_points - vis_center))
                    preview_data["visualization_params"] = {
                        "center": vis_center.tolist(),
                        "scale": vis_scale if not np.isclose(vis_scale, 0) else 1.0,
                    }
                else:
                    # Final fallback to path-based transform
                    preview_data["visualization_params"] = {
                        "center": transform_params["center"],
                        "scale": transform_params["scale"],
                    }

            # Group by display type and keep only the best (lowest distance)
            if display_type not in mechanisms_by_type:
                mechanisms_by_type[display_type] = preview_data
            else:
                if distance < mechanisms_by_type[display_type]["overall_score"]:
                    mechanisms_by_type[display_type] = preview_data

        print(f"Debug: Made {total_comparisons} path comparisons")
        print(f"Debug: Found {len(mechanisms_by_type)} mechanism types: {list(mechanisms_by_type.keys())}")

        # Get best from each type
        best_mechanisms = list(mechanisms_by_type.values())

        # Sort by similarity score (lower is better)
        best_mechanisms.sort(key=lambda x: x["overall_score"])

        # Take top 3 most similar
        top_3 = best_mechanisms[:3]

        # Debug output
        for i, mech in enumerate(top_3):
            print(f"Debug: Recommendation {i+1}: {mech['type']} - {mech['name']} (score: {mech['overall_score']:.2f})")

        # Ensure we have exactly 3 slots
        while len(top_3) < 3:
            top_3.append(None)

        return top_3

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
            # Use the new key_points structure with more detailed information
            p1_coords = key_points.get("ground_pivot_1")
            p2_coords = key_points.get("ground_pivot_2")
            p3_coords = key_points.get("initial_moving_joint_1")
            p4_coords = key_points.get("initial_moving_joint_2")

            # Include all available pivot points
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
                # Use key_points if available for more accurate positioning
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
                    all_points.append(np.array([[0, 0]]))  # rotation center

                thetas = np.linspace(0, 2 * np.pi, 20)
                cam_points = cam_center_orig + base_radius * np.array(
                    [np.cos(thetas), np.sin(thetas)]
                ).T
                all_points.append(cam_points)

        elif mech_type == "Gear Contact":
            r1, r2 = params.get("r1"), params.get("r2")
            if r1 and r2:
                # Use key_points if available for more accurate positioning
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
