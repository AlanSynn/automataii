from typing import Any, Dict, List, Optional

import numpy as np # Add numpy import
from scipy.spatial.distance import directed_hausdorff # Add scipy import
import json # Add json import

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

DEFAULT_NUM_SAMPLES_FOR_PATH = 100 # Default number of points to sample from QPainterPath

def qpainterpath_to_numpy_array(path: QPainterPath, num_points: int = DEFAULT_NUM_SAMPLES_FOR_PATH) -> Optional[np.ndarray]:
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

def calculate_hausdorff_distance(path1_points: np.ndarray, path2_points: np.ndarray) -> float:
    """Calculates the Hausdorff distance between two sets of points.

    Args:
        path1_points: Numpy array of points for the first path (N, 2).
        path2_points: Numpy array of points for the second path (M, 2).

    Returns:
        The Hausdorff distance. Returns float('inf') if either path is empty or invalid.
    """
    if path1_points is None or path1_points.shape[0] == 0 or \
       path2_points is None or path2_points.shape[0] == 0:
        return float('inf')

    # For a more robust measure, consider the maximum of the two directed distances
    dist_1_to_2 = directed_hausdorff(path1_points, path2_points)[0]
    dist_2_to_1 = directed_hausdorff(path2_points, path1_points)[0]
    return max(dist_1_to_2, dist_2_to_1)

class MechanismPreviewWidget(QGraphicsView):
    """A widget to display a preview of a single mechanism."""

    def __init__(self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(200, 150) # Fixed size for preview
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
            text_item.setDefaultTextColor(Qt.GlobalColor.black)
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
            text_item.setDefaultTextColor(Qt.GlobalColor.black)
            text_item.setPos(view_rect_adjusted_f.center() - text_item.boundingRect().center())

        # Draw user's motion path if available, after specific mechanism
        self._draw_user_motion_path(view_rect_adjusted_f)

        # Fit view to scene contents, respecting the view_rect
        # self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        # Ensure the entire sceneRect is visible
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


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
        cam_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(cam_front)

        shaft_front_rad = base_radius*0.25
        shaft_front = QGraphicsEllipseItem(0,0, shaft_front_rad*2, shaft_front_rad*2)
        shaft_front.setPos(cam_center_x - shaft_front_rad, cam_center_y - shaft_front_rad)
        shaft_front.setBrush(QColor("lightgray"))
        shaft_front.setPen(QPen(Qt.GlobalColor.black, 1))
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
        follower_front.setPen(QPen(Qt.GlobalColor.black, 1))
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
        gear_front.setPen(QPen(Qt.GlobalColor.black, 1))
        self.scene.addItem(gear_front)

        center_hole_rad = inner_radius*0.4
        center_hole = QGraphicsEllipseItem(0,0, center_hole_rad*2, center_hole_rad*2)
        center_hole.setPos(center_x - center_hole_rad, center_y - center_hole_rad)
        center_hole.setBrush(QColor("white"))
        center_hole.setPen(QPen(Qt.GlobalColor.black, 1))
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
            self.scene.addPolygon(tooth_poly_front, QPen(Qt.GlobalColor.black, 0.5), QBrush(QColor("silver")))

    def _draw_linkage_preview(self, dox: float, doy: float, bounds: QRectF) -> None:
        # Generic schematic 4-bar linkage preview
        preview_scale = min(bounds.width(), bounds.height()) / 150.0 # Base size for linkage
        thickness = 8 * preview_scale # Scale thickness too

        # Define points relative to bounds center, then scale
        center_x = bounds.center().x()
        center_y = bounds.center().y()

        # Normalized points (example four-bar)
        p0_norm = QPointF(-50, -20)  # Fixed ground pivot 1
        p1_norm = QPointF(-30, 30)   # Crank pivot
        p2_norm = QPointF(40, 40)    # Coupler end / Rocker pivot
        p3_norm = QPointF(50, -10)   # Fixed ground pivot 2

        # Scale points
        p0 = QPointF(center_x + p0_norm.x() * preview_scale, center_y + p0_norm.y() * preview_scale)
        p1 = QPointF(center_x + p1_norm.x() * preview_scale, center_y + p1_norm.y() * preview_scale)
        p2 = QPointF(center_x + p2_norm.x() * preview_scale, center_y + p2_norm.y() * preview_scale)
        p3 = QPointF(center_x + p3_norm.x() * preview_scale, center_y + p3_norm.y() * preview_scale)

        # Draw links (back then front)
        link_color_front = QColor("cornflowerblue")
        link_color_back = QColor("darkblue")
        pivot_color_front = QColor("lightgray")
        pivot_color_back = QColor("dimgray")
        pivot_radius = thickness * 0.7 # Scale pivot radius with thickness

        links = [
            (p0, p1, "crank"),
            (p1, p2, "coupler"),
            (p2, p3, "rocker"),
            (p3, p0, "ground") # Ground link often conceptual
        ]

        for start_pt, end_pt, _ in links:
            # Back link
            path_back = QPainterPath()
            path_back.moveTo(start_pt + QPointF(dox, doy))
            path_back.lineTo(end_pt + QPointF(dox, doy))
            link_back = QGraphicsPathItem(path_back)
            pen_back = QPen(link_color_back, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            link_back.setPen(pen_back)
            self.scene.addItem(link_back)

            # Front link
            path_front = QPainterPath()
            path_front.moveTo(start_pt)
            path_front.lineTo(end_pt)
            link_front = QGraphicsPathItem(path_front)
            pen_front = QPen(link_color_front, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            link_front.setPen(pen_front)
            self.scene.addItem(link_front)

        # Draw pivots (back then front)
        pivot_points = [p0, p1, p2, p3]
        for pt in pivot_points:
            # Back pivot
            pivot_item_back = QGraphicsEllipseItem(pt.x() - pivot_radius + dox, pt.y() - pivot_radius + doy, pivot_radius * 2, pivot_radius * 2)
            pivot_item_back.setBrush(pivot_color_back)
            pivot_item_back.setPen(QPen(Qt.PenStyle.NoPen))
            self.scene.addItem(pivot_item_back)

            # Front pivot
            pivot_item_front = QGraphicsEllipseItem(pt.x() - pivot_radius, pt.y() - pivot_radius, pivot_radius * 2, pivot_radius * 2)
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
    selected = Signal(dict) # Emits the mechanism data when selected

    def __init__(self, mechanism_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Title/Name
        name = self.mechanism_data.get("name", "Unnamed Mechanism")
        title_label = QLabel(f"<b>{name}</b>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Preview Widget
        self.preview_widget = MechanismPreviewWidget(self.mechanism_data, self)
        layout.addWidget(self.preview_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Score (if available)
        score = self.mechanism_data.get("overall_score")
        if score is not None:
            score_label = QLabel(f"Score: {score:.2f}")
            score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(score_label)

        # Select Button
        select_button = QPushButton("Select")
        select_button.clicked.connect(self._emit_selected)
        layout.addWidget(select_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        self.setMinimumWidth(220) # Ensure enough space for contents
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed) # Fixed height based on content

    def _emit_selected(self) -> None:
        self.selected.emit(self.mechanism_data)

    def minimumSizeHint(self) -> QSize:
        return QSize(220, 280) # Adjust based on typical content height

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()


# Wrapper for math functions to avoid numpy dependency if not strictly needed here
# And to ensure degrees are converted to radians correctly for math.cos/sin.

class MechanismRecommendationDialog(QDialog):
    mechanism_selected = Signal(dict) # Emitted when a mechanism is chosen

    def __init__(self, user_motion_path: QPainterPath, generated_paths_filepath: str, num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Mechanism Recommendations")
        self.setMinimumSize(700, 400)
        self.selected_mechanism_data: Optional[Dict[str, Any]] = None

        self.user_motion_path_original = user_motion_path # Keep original QPainterPath for preview
        self.user_motion_path_np = qpainterpath_to_numpy_array(user_motion_path, num_samples_user_path)

        self.generated_paths_filepath = generated_paths_filepath
        self.generated_paths_data = self._load_generated_paths(generated_paths_filepath)

        main_layout = QVBoxLayout(self)
        self.previews_layout = QHBoxLayout()
        self.previews_layout.setSpacing(10)
        self.previews_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        recommendations = self._get_best_recommendations()

        if recommendations:
            for rec_data in recommendations:
                if rec_data:
                    # Add user_motion_path_local to each recommendation for preview
                    rec_data_with_user_path = rec_data.copy()
                    rec_data_with_user_path["user_motion_path_local"] = self.user_motion_path_original

                    container = PreviewContainer(rec_data_with_user_path, self)
                    container.selected.connect(self._on_select)
                    self.previews_layout.addWidget(container)
                else:
                    placeholder_label = QLabel("Invalid Recommendation Data")
                    placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder_label.setFrameShape(QLabel.FrameShape.Box)
                    placeholder_label.setFixedSize(220, 280)
                    self.previews_layout.addWidget(placeholder_label)
            self.previews_layout.addStretch()
        else:
            no_recs_label = QLabel("No mechanism recommendations could be generated or found.")
            no_recs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.previews_layout.addWidget(no_recs_label)

        main_layout.addLayout(self.previews_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def _load_generated_paths(self, filepath: str) -> List[Dict[str, Any]]:
        """Loads mechanism paths from a JSON file and prepares them."""
        loaded_paths = []
        try:
            with open(filepath, 'r') as f:
                raw_data = json.load(f)

            for item in raw_data:
                path_coords = item.get("path_coordinates")
                if path_coords and isinstance(path_coords, list) and len(path_coords) > 0:
                    # Ensure coordinates are suitable for numpy array (e.g., list of lists/tuples)
                    try:
                        item["path_coordinates_np"] = np.array(path_coords, dtype=float)
                        loaded_paths.append(item)
                    except ValueError as e:
                        print(f"Warning: Could not convert path_coordinates to numpy array for item: {item.get('type', 'N/A')}. Error: {e}")
                        # Optionally skip this item or handle error
                else:
                    print(f"Warning: Missing or invalid 'path_coordinates' for item: {item.get('type', 'N/A')}")

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
        and returns the best match for each defined mechanism type.
        """
        if self.user_motion_path_np is None or not self.generated_paths_data:
            print("User motion path is not processed or no generated paths loaded.")
            return []

        best_recommendations_map = {
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: {"best_score": float('inf'), "data": None},
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: {"best_score": float('inf'), "data": None},
            MECHANISM_TYPE_USER_DISPLAY_CAM:   {"best_score": float('inf'), "data": None}
        }

        # Mapping from JSON type strings to our user-facing display type constants.
        # This needs to be accurate based on the strings in your JSON file.
        type_mapping = {
            # Example: If your JSON has a specific type for 3-bar mechanisms:
            # "3-bar Output": MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            "4-bar Coupler": MECHANISM_TYPE_USER_DISPLAY_4_BAR, # Actual type from JSON
            # Example: If your JSON has a specific type for cam mechanisms:
            # "Cam Profile": MECHANISM_TYPE_USER_DISPLAY_CAM,
            # Add other mappings if necessary for different mechanism variations.
        }

        for gen_path_data in self.generated_paths_data:
            gen_path_np = gen_path_data.get("path_coordinates_np")
            json_type_str = gen_path_data.get("type")

            if gen_path_np is None or json_type_str is None:
                continue

            distance = calculate_hausdorff_distance(self.user_motion_path_np, gen_path_np)

            target_mech_type = type_mapping.get(json_type_str)

            if target_mech_type and distance < best_recommendations_map[target_mech_type]["best_score"]:
                best_recommendations_map[target_mech_type]["best_score"] = distance

                # Prepare data for PreviewContainer
                # The 'name' could be derived or use json_type_str or a more descriptive field from JSON
                # 'type' should be the user-friendly display type
                # 'overall_score' is our Hausdorff distance (lower is better)
                preview_data = {
                    "name": gen_path_data.get("name", json_type_str), # Use a 'name' field if available in JSON
                    "type": target_mech_type, # Use the consistent type
                    "original_json_type": json_type_str, # Keep original type for reference if needed
                    "overall_score": distance, # This is the Hausdorff distance
                    "parameters": gen_path_data.get("parameters"),
                    "path_coordinates_np": gen_path_np, # The mechanism's own path
                    # "user_motion_path_local" will be added in __init__ before passing to PreviewContainer
                }
                best_recommendations_map[target_mech_type]["data"] = preview_data

        # Collect valid recommendations
        final_recommendations = []
        # Iterate through the user display types to ensure order and check if recommendations were found
        for mech_display_type in [MECHANISM_TYPE_USER_DISPLAY_3_BAR, MECHANISM_TYPE_USER_DISPLAY_4_BAR, MECHANISM_TYPE_USER_DISPLAY_CAM]:
            if best_recommendations_map[mech_display_type]["data"] is not None:
                final_recommendations.append(best_recommendations_map[mech_display_type]["data"])
            else:
                # Optionally, add a placeholder if no recommendation found for a type
                print(f"No suitable recommendation found for type: {mech_display_type}")
                # final_recommendations.append(None) # Or a placeholder dict like:
                # final_recommendations.append({"name": f"No {mech_display_type} found", "type": mech_display_type, "overall_score": float('inf')})

        return final_recommendations

    def _on_select(self, mechanism_data: Dict[str, Any]) -> None:
        self.selected_mechanism_data = mechanism_data
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        # Optionally provide visual feedback on the selected PreviewContainer

    @staticmethod
    def get_recommendation(
        user_motion_path: QPainterPath, generated_paths_filepath: str, num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH, parent: Optional[QWidget] = None
    ) -> Optional[Dict[str, Any]]:
        """Static method to show the dialog and return the selected mechanism data."""
        dialog = MechanismRecommendationDialog(user_motion_path, generated_paths_filepath, num_samples_user_path, parent)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return dialog.selected_mechanism_data
        return None

if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Example recommendations (replace with actual data from MechanismManager)
    dummy_path = QPainterPath()
    dummy_path.moveTo(10, 10)
    dummy_path.lineTo(50, 80)
    dummy_path.quadTo(100, 100, 150, 50)

    example_recs_data = [
        {"name": "Recommended Cam 1", "type": "Cam & Follower", "overall_score": 0.85, "user_motion_path_local": dummy_path.translated(0,0) },
        {"name": "Recommended Linkage A", "type": "4-Bar Linkage", "overall_score": 0.72, "user_motion_path_local": dummy_path.translated(10,10) },
        {"name": "Simple Gears", "type": "gears", "overall_score": 0.91, "user_motion_path_local": dummy_path.translated(-5,5) },
        None, # Test None placeholder
        {"name": "Another Cam", "type": "cam", "overall_score": 0.60 }, # Test with no path
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
    current_test_index_ref = [0] # Use a list to pass by reference

    def run_test(recs, title):
        print(f"\n--- Running Test: {title} ---")
        selected_mechanism = MechanismRecommendationDialog.get_recommendation(recs, None)
        if selected_mechanism:
            print(f"Mechanism selected: {selected_mechanism.get('name')}")
        else:
            print("Dialog cancelled or no mechanism selected.")
        run_next_test() # Proceed to next test

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
            app.quit() # Exit application after tests

    # Start the first test
    run_next_test()

    sys.exit(app.exec())