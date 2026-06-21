import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, SupportsFloat, SupportsIndex, cast

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from scipy.spatial.distance import directed_hausdorff

from automataii.presentation.qt.gear_rendering import (
    annulus_path,
    gear_attachment_hole_centers,
    gear_hole_radius,
    gear_outline_polygon,
    radial_tick_lines,
)
from automataii.presentation.qt.tabs.cam_geometry import build_pear_cam_profile
from automataii.shared.physical_kit import (
    PhysicalKitContext,
    fabrication_ready_params,
    gear_attachment_grid_offsets_mm,
    gear_center_distance,
    gear_clearance_from_params,
    grid_enabled_from_params,
    physical_profile_from_params,
)
from automataii.utils.paths import resolve_path

logger = logging.getLogger(__name__)
_NumericPayload = str | bytes | bytearray | SupportsFloat | SupportsIndex
_ScreenTransform = Callable[[np.ndarray], QPointF]
_SimulationTransform = Callable[[np.ndarray, QTransform], QPointF]


# --- Time-aware matching helpers ---
def _finite_path_array(points: object, min_points: int = 2) -> np.ndarray | None:
    """Return a finite ``(N, 2)`` path array, or ``None`` for invalid candidates."""
    try:
        array = np.asarray(points, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim != 2 or array.shape[0] < min_points or array.shape[1] < 2:
        return None
    array = array[:, :2]
    if not np.isfinite(array).all():
        return None
    if min_points >= 2:
        deltas = np.diff(array, axis=0)
        arc_length = float(np.sum(np.linalg.norm(deltas, axis=1)))
        extent = float(np.max(np.ptp(array, axis=0)))
        if arc_length <= 1e-9 or extent <= 1e-9:
            return None
    return array


def _finite_float(value: object, default: float) -> float:
    """Return a finite float, or ``default`` for invalid numeric payloads."""
    try:
        result = float(cast(_NumericPayload, value))
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _stable_recommendation_identity(row: dict[str, Any], json_type: str) -> str:
    """Return a deterministic identity string for tie-breaking equal scores."""
    payload = {
        "id": row.get("id") or row.get("path_id") or row.get("source_id"),
        "name": row.get("name"),
        "type": json_type,
        "reverse_direction": row.get("reverse_direction"),
        "parameters": row.get("parameters", {}),
        "key_points": row.get("key_points", {}),
        "path_coordinates": row.get("path_coordinates"),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _coerce_reverse_direction(value: object, default: bool = False) -> bool:
    """Coerce persisted/UI direction flags without treating junk payloads as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "y", "on", "reverse", "reversed"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "forward"}:
            return False
        return default
    if isinstance(value, int | float | np.integer | np.floating):
        numeric_value = float(value)
        return bool(value) if np.isfinite(numeric_value) else default
    return default


def _candidate_reverse_direction(row: dict[str, Any]) -> bool:
    """Return the candidate's persisted direction flag using dialog/candidate precedence."""
    raw_params = row.get("parameters")
    params = raw_params if isinstance(raw_params, dict) else {}
    if "reverse_direction" in row:
        return _coerce_reverse_direction(row.get("reverse_direction"), False)
    return _coerce_reverse_direction(params.get("reverse_direction"), False)


def _dialog_physical_context(dialog: object) -> PhysicalKitContext | None:
    """Read optional dialog context without requiring QObject initialization in tests."""
    try:
        context = cast(Any, dialog).physical_context
    except (AttributeError, RuntimeError):
        return None
    return context if isinstance(context, PhysicalKitContext) else None


def _cumulative_arc_length(points: np.ndarray) -> np.ndarray:
    """Compute cumulative arc length for a 2D polyline.

    Returns an array s of shape (N,) with s[0]=0 and s[-1]=total length.
    """
    if points is None or len(points) < 2:
        return np.array([0.0])
    deltas = np.diff(points, axis=0)
    seg_lengths = np.linalg.norm(deltas, axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    return s


def _resample_time_aligned(
    points: np.ndarray, num_points: int, times: np.ndarray | None = None
) -> np.ndarray:
    """Resample a polyline to `num_points` using time/arc-length parameterization.

    - If `times` provided (monotonic, same length as points), use it (normalized to [0,1]).
    - Else, use arc-length parameterization to approximate time.
    """
    if points is None or len(points) == 0 or num_points <= 1:
        return points

    n = len(points)
    if times is not None and len(times) == n:
        t = np.array(times, dtype=float)
        # Ensure monotonic and normalized
        t = np.maximum.accumulate(t)
        t0, t1 = t[0], t[-1]
        denom = (t1 - t0) if (t1 - t0) != 0 else 1.0
        tn = (t - t0) / denom
    else:
        s = _cumulative_arc_length(points)
        denom = s[-1] if s[-1] != 0 else 1.0
        tn = s / denom

    # Target time samples uniformly in [0,1]
    tt = np.linspace(0.0, 1.0, num_points)

    # Linear interpolate x and y separately over tn
    x = np.interp(tt, tn, points[:, 0])
    y = np.interp(tt, tn, points[:, 1])
    return np.column_stack([x, y])


def _time_aware_distance(u: np.ndarray, v: np.ndarray) -> float:
    """Compute time-aware distance between two equally-sampled trajectories.

    Uses the maximum pointwise Euclidean distance across synchronized samples.
    Assumes u and v have the same shape (N,2).
    """
    if u is None or v is None or len(u) == 0 or len(v) == 0:
        return float("inf")
    n = min(len(u), len(v))
    du = u[:n] - v[:n]
    d = np.linalg.norm(du, axis=1)
    return float(np.max(d)) if len(d) else float("inf")


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

DEFAULT_NUM_SAMPLES_FOR_PATH = 100  # Default number of points to sample from QPainterPath

_RECOMMENDATION_PHYSICAL_TYPE_MAPPING: dict[str, str] = {
    "4-bar Coupler": "four_bar",
    "3-bar Output": "four_bar",
    "Four-Bar": "four_bar",
    "Four-Bar Linkage": "four_bar",
    "Cam Profile": "cam_follower",
    "Cam-Follower": "cam_follower",
    "Cam Follower": "cam_follower",
    "Cam & Follower": "cam_follower",
    "Cam": "cam_follower",
    "Gear Train": "gear_train",
    "Gear Contact": "gear_train",
    "Simple Gear": "gear_train",
    "Gears": "gear_train",
    "Planetary Gear": "planetary_gear",
}


def _recommendation_physical_type(json_type: object, family: object = None) -> str:
    for value in (json_type, family):
        if isinstance(value, str):
            mapped = _RECOMMENDATION_PHYSICAL_TYPE_MAPPING.get(value.strip())
            if mapped:
                return mapped
    return str(json_type or family or "").strip()


def _fabrication_ready_recommendation_params(
    json_type: object,
    family: object,
    params: dict[str, Any],
    physical_context: PhysicalKitContext | None,
) -> dict[str, object]:
    """Snap recommendation params to the same physical contract used by Design/Fabrication."""
    payload: dict[str, object] = dict(params)
    if physical_context is not None:
        payload.update(physical_context.as_params())
    ready_params = fabrication_ready_params(
        _recommendation_physical_type(json_type, family),
        payload,
    )
    return dict(ready_params)


def qpainterpath_to_numpy_array(
    path: QPainterPath, num_points: int = DEFAULT_NUM_SAMPLES_FOR_PATH
) -> np.ndarray | None:
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
    path1_array = _finite_path_array(path1_points, min_points=1)
    path2_array = _finite_path_array(path2_points, min_points=1)
    if path1_array is None or path2_array is None:
        return float("inf")

    try:
        # Ensure both paths have 2D coordinates
        if len(path1_array.shape) != 2 or path1_array.shape[1] != 2:
            logger.warning("path1 has invalid shape %s", path1_array.shape)
            return float("inf")
        if len(path2_array.shape) != 2 or path2_array.shape[1] != 2:
            logger.warning("path2 has invalid shape %s", path2_array.shape)
            return float("inf")

        # Calculate bidirectional Hausdorff distance
        dist_1_to_2 = directed_hausdorff(path1_array, path2_array)[0]
        dist_2_to_1 = directed_hausdorff(path2_array, path1_array)[0]
        distance = max(dist_1_to_2, dist_2_to_1)

        return float(distance)
    except Exception as e:
        logger.error("Error calculating Hausdorff distance: %s", e)
        return float("inf")


def align_and_compare_paths(
    path1_points: np.ndarray,
    path2_points: np.ndarray,
    rotation_steps: int = 72,
    mechanism_type: str = "",
) -> tuple[float, np.ndarray | None, np.ndarray | None, dict | None]:
    """
    Aligns two paths (translation, scale, rotation) and finds the best match.

    Returns:
        A tuple containing:
        - The minimum Hausdorff distance after alignment.
        - The first path, normalized (centered and scaled).
        - The second path, transformed to best align with the first.
        - A dictionary with the transformation parameters ('center', 'scale', 'rotation').
    """
    path1_array = _finite_path_array(path1_points)
    path2_array = _finite_path_array(path2_points)
    if path1_array is None or path2_array is None:
        return float("inf"), None, None, None

    # 1. Center both paths to origin
    center1 = np.mean(path1_array, axis=0)
    path1_centered = path1_array - center1
    center2 = np.mean(path2_array, axis=0)
    path2_centered = path2_array - center2

    # 2. Normalize scale of both paths to fit in a [-1, 1] box
    max_val1 = np.max(np.abs(path1_centered))
    path1_scaled = path1_centered / max_val1 if not np.isclose(max_val1, 0) else path1_centered

    max_val2 = np.max(np.abs(path2_centered))
    path2_scaled = path2_centered / max_val2 if not np.isclose(max_val2, 0) else path2_centered

    # 3. Find the optimal rotation for path2 to match path1
    # Skip rotation search for cam-followers as they have directional constraints
    min_distance = float("inf")
    best_rotated_path2 = None
    best_angle = 0.0

    # Cam-followers have gravity constraints - cam must be below, follower above
    if "cam" in mechanism_type.lower() or "follower" in mechanism_type.lower():
        # For cam-followers, test both upright and 180-degree rotated orientations
        # This ensures the cam is positioned at the bottom for better matching
        test_angles = [0.0, float(np.pi)]  # Test both 0° and 180° orientations
    else:
        # For other mechanisms (linkages, gears), test full rotation range
        test_angles = [
            float(angle) for angle in np.linspace(0, 2 * np.pi, rotation_steps, endpoint=False)
        ]

    for angle in test_angles:
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

    def __init__(self, mechanism_data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self.setFixedSize(280, 220)  # Reduced size to prevent overlap in dialog
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._preview_scene = QGraphicsScene(self)
        self.setScene(self._preview_scene)
        self.setBackgroundBrush(QColor("#ffffff"))  # White background
        # CAM animation state
        self._cam_poly_item: QGraphicsPolygonItem | None = None
        self._follower_item: QGraphicsRectItem | None = None
        self._rod_item: QGraphicsPathItem | None = None
        self._cam_points_local: np.ndarray | None = None
        self._cam_to_screen: _ScreenTransform | None = None
        self._cam_angle: float = 0.0
        self._cam_timer: QTimer | None = None
        self._render_preview()  # Render after background is set and scene is ready

    def _draw_path_comparison(self, bounds: QRectF) -> None:
        """Draws the aligned path comparison."""
        user_path_points = self.mechanism_data.get("user_path_aligned_np")
        mech_path_points = self.mechanism_data.get("mech_path_aligned_np")

        if user_path_points is None or mech_path_points is None:
            logger.debug("Aligned paths not found for preview.")
            text_item = self._preview_scene.addText("Path data not available", QFont("Arial", 14))
            if text_item is not None:
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
        transform.scale(scale, scale)  # Use positive y-scale to maintain correct orientation

        # Draw the mechanism structure first so it's in the background
        self._draw_mechanism_structure(transform)

        # Draw user path (red, dashed)
        user_item = QGraphicsPathItem(transform.map(user_path))
        user_pen = QPen(BITTERSWEET, 8.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
        user_item.setPen(user_pen)
        self._preview_scene.addItem(user_item)

        # Draw mechanism path (blue, solid)
        mech_item = QGraphicsPathItem(transform.map(mech_path))
        mech_pen = QPen(STEEL_BLUE, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        mech_item.setPen(mech_pen)
        self._preview_scene.addItem(mech_item)

    def _draw_mechanism_structure(self, transform: QTransform) -> None:
        """Draws the mechanism structure (e.g., links and pivots) for a single frame."""
        mech_type = self.mechanism_data.get("original_json_type")
        params = self.mechanism_data.get("parameters")
        full_sim_data = self.mechanism_data.get("full_simulation_data")

        if not isinstance(params, dict) or not isinstance(full_sim_data, dict) or not mech_type:
            return

        # Central dispatcher for drawing mechanisms from simulation data. Preview payloads come
        # from template search files, so malformed rows must be skipped instead of crashing the UI.
        try:
            if mech_type == "4-bar Coupler" and "joint_positions" in full_sim_data:
                self._draw_4_bar_from_sim(transform, full_sim_data, params)
            elif mech_type in ["Cam-Follower", "Cam Follower"] and "cam_data" in full_sim_data:
                self._draw_cam_follower_from_sim(transform, full_sim_data, params)
            elif mech_type in ["Simple Gear", "Gear Contact"] and "gear_data" in full_sim_data:
                self._draw_simple_gear_from_sim(transform, full_sim_data, params)
            elif mech_type == "Planetary Gear" and "gear_positions" in full_sim_data:
                self._draw_planetary_gear_from_sim(transform, full_sim_data, params)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "Skipping malformed %s recommendation preview structure: %s",
                mech_type,
                exc,
                exc_info=True,
            )

    def _get_transform_for_sim_data(
        self, full_sim_data: dict[str, Any], path_key: str
    ) -> _SimulationTransform | None:
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

    def _draw_4_bar_from_sim(
        self, transform: QTransform, full_sim_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
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

        def to_screen_coords(p: np.ndarray) -> QPointF:
            return to_screen_coords_func(p, transform)

        self._draw_4_bar_structure_from_sim(p1, p2, p3, p4, to_screen_coords)

    def _draw_4_bar_structure_from_sim(
        self,
        p1: np.ndarray,
        p2: np.ndarray,
        p3: np.ndarray,
        p4: np.ndarray,
        to_screen_coords: _ScreenTransform,
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

        screen_points: tuple[QPointF, QPointF, QPointF, QPointF, QPointF] = (
            to_screen_coords(p1),
            to_screen_coords(p2),
            to_screen_coords(p3),
            to_screen_coords(p4),
            to_screen_coords(p_coupler),
        )
        p1_t, p2_t, p3_t, p4_t, p_coupler_t = screen_points

        self._preview_scene.addLine(
            QLineF(p1_t, p3_t),
            QPen(QColor("#e74c3c"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap),
        )
        self._preview_scene.addLine(
            QLineF(p2_t, p4_t),
            QPen(QColor("#f39c12"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap),
        )

        area = (
            abs(
                p3[0] * (p4[1] - p_coupler[1])
                + p4[0] * (p_coupler[1] - p3[1])
                + p_coupler[0] * (p3[1] - p4[1])
            )
            / 2
        )
        if area < 1e-3:
            self._preview_scene.addLine(
                QLineF(p3_t, p4_t),
                QPen(QColor("#2ecc71"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap),
            )
        else:
            triangle_polygon = QPolygonF([p3_t, p4_t, p_coupler_t])
            self._preview_scene.addPolygon(
                triangle_polygon, QPen(QColor("#2ecc71"), 2), QBrush(QColor("#2ecc71").lighter(160))
            )

        self._preview_scene.addEllipse(
            p_coupler_t.x() - 3,
            p_coupler_t.y() - 3,
            6,
            6,
            QPen(QColor("#ff0000")),
            QBrush(QColor("#ff0000")),
        )

    def _draw_cam_follower_from_sim(
        self, transform: QTransform, full_sim_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Template-driven cam preview with rigid rotation animation."""
        base_radius = _finite_float(params.get("base_radius", 25.0), 25.0)
        # Override eccentricity with user total lift if available
        eccentricity = _finite_float(params.get("eccentricity", 10.0), 10.0)
        try:
            up = self.mechanism_data.get("user_path_aligned_np")
            if up is not None and len(up) > 0:
                umin = float(np.min(up[:, 1]))
                umax = float(np.max(up[:, 1]))
                user_lift = abs(umax - umin)
                if np.isfinite(user_lift) and user_lift > 1e-9:
                    eccentricity = user_lift
        except Exception:
            logging.debug("Could not derive cam lift from aligned user path", exc_info=True)
        rod_len = _finite_float(params.get("follower_rod_length", 40.0), 40.0)

        cam_data = full_sim_data.get("cam_data", {}) if full_sim_data else {}
        if cam_data and "follower_y_positions" in cam_data:
            follower_path = [[0.0, float(y)] for y in cam_data.get("follower_y_positions", [])]
        else:
            follower_path = [
                [0.0, base_radius + (eccentricity * 0.5) * (1 + np.cos(2 * np.pi * i / 90))]
                for i in range(90)
            ]

        to_screen_coords_func = self._get_transform_for_sim_data(
            {"follower_path": follower_path}, "follower_path"
        )
        if not to_screen_coords_func:
            return
        self._cam_to_screen = lambda p: to_screen_coords_func(p, transform)

        # Load template and build cam polygon points
        default_template_path = resolve_path(Path("resources/blueprints/tom/pear_cam_4.3in.svg"))
        default_template = str(default_template_path)
        svg_path = (
            self.mechanism_data.get("cam_template_svg_path")
            or self.mechanism_data.get("parameters", {}).get("cam_template_svg_path")
            or default_template
        )
        template_points: np.ndarray | None = None
        try:
            axis, poly = self._load_cam_profile_svg(svg_path)
            valid_poly = _finite_path_array(poly, min_points=3)
            if axis is not None and valid_poly is not None:
                template_points = valid_poly - axis
        except Exception:
            logging.debug(
                "Could not load cam template %s; using analytic fallback", svg_path, exc_info=True
            )

        # If base radius is missing or out-of-range, tie it to eccentricity to control on-screen size
        if (base_radius <= 0) or (base_radius > 3 * eccentricity):
            base_radius = 0.3 * max(1e-6, eccentricity)

        if template_points is not None:
            self._cam_points_local = self._build_cam_from_template(
                template_points,
                base_radius=base_radius,
                eccentricity=eccentricity,
                num_samples=180,
            )
        else:
            self._cam_points_local = build_pear_cam_profile(
                base_radius=base_radius,
                eccentricity=eccentricity,
                rise_deg=params.get("rise_deg", 90.0),
                high_dwell_deg=params.get("high_dwell_deg", 60.0),
                return_deg=params.get("return_deg"),
                dwell_low_deg=params.get("low_dwell_deg", params.get("dwell_low_deg", 180.0)),
                align_max_to_deg=params.get("align_max_deg", 90.0),
                num_samples=180,
            )

        # Create items
        cam_polygon = QPolygonF([self._cam_to_screen(p) for p in self._cam_points_local])
        # Draw cam profile as green outline (no fill), matching blueprint style
        cam_color = QColor("#2ecc71")
        self._cam_poly_item = QGraphicsPolygonItem(cam_polygon)
        self._cam_poly_item.setPen(QPen(cam_color, 3))
        self._cam_poly_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._preview_scene.addItem(self._cam_poly_item)

        y_max = float(np.max(self._cam_points_local[:, 1]))
        follower_center = np.array([0.0, y_max - rod_len])  # follower above cam
        w, h = 16.0, 10.0
        follower_color = QColor("#ff7f50")
        follower_scene_center = self._cam_to_screen(follower_center)
        self._follower_item = QGraphicsRectItem(
            follower_scene_center.x() - w / 2, follower_scene_center.y() - h / 2, w, h
        )
        self._follower_item.setPen(QPen(follower_color, 2))
        self._follower_item.setBrush(QBrush(follower_color.lighter(140)))
        self._preview_scene.addItem(self._follower_item)

        cam_top_scene = self._cam_to_screen(np.array([0.0, y_max]))
        rod_path = QPainterPath(cam_top_scene)
        rod_path.lineTo(follower_scene_center)
        rod_pen = QPen(QColor("#2ecc71"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self._rod_item = QGraphicsPathItem(rod_path)
        self._rod_item.setPen(rod_pen)
        self._preview_scene.addItem(self._rod_item)

        # Start animation
        if self._cam_timer is None:
            self._cam_timer = QTimer(self)
            self._cam_timer.timeout.connect(lambda: self._tick_cam_animation(rod_len))
            self._cam_timer.start(60)  # ~16 FPS

    def _tick_cam_animation(self, rod_len: float) -> None:
        if (
            self._cam_points_local is None
            or self._cam_poly_item is None
            or self._follower_item is None
            or self._rod_item is None
            or self._cam_to_screen is None
        ):
            return
        self._cam_angle = (self._cam_angle + 0.06) % (2 * np.pi)
        cos_r, sin_r = np.cos(self._cam_angle), np.sin(self._cam_angle)
        rot = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
        rotated = self._cam_points_local @ rot.T

        self._cam_poly_item.setPolygon(QPolygonF([self._cam_to_screen(p) for p in rotated]))

        y_max = float(np.max(rotated[:, 1]))
        follower_center = np.array([0.0, y_max - rod_len])
        follower_scene_center = self._cam_to_screen(follower_center)
        w, h = 16.0, 10.0
        self._follower_item.setRect(
            follower_scene_center.x() - w / 2, follower_scene_center.y() - h / 2, w, h
        )
        cam_top_scene = self._cam_to_screen(np.array([0.0, y_max]))
        rod_path = QPainterPath(cam_top_scene)
        rod_path.lineTo(follower_scene_center)
        self._rod_item.setPath(rod_path)

    def _load_cam_profile_svg(self, svg_path: str) -> tuple[np.ndarray | None, np.ndarray]:
        import xml.etree.ElementTree as ET

        tree = ET.parse(svg_path)
        root = tree.getroot()

        def strip(tag: str) -> str:
            return tag.split("}", 1)[-1]

        axis = None
        poly_pts = []
        for elem in root.iter():
            tag = strip(elem.tag)
            if tag == "circle" and axis is None:
                try:
                    cx = float(elem.attrib.get("cx", "0"))
                    cy = float(elem.attrib.get("cy", "0"))
                    axis = np.array([cx, cy], dtype=float)
                except Exception:
                    logging.debug("Skipping malformed cam template axis circle", exc_info=True)
            elif tag == "path":
                d = elem.attrib.get("d", "")
                if not d:
                    continue
                tokens = re.findall(
                    r"[MmLlZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?",
                    d.replace(",", " "),
                )
                i = 0
                command = ""
                current = np.array([0.0, 0.0], dtype=float)
                start_point: np.ndarray | None = None
                while i < len(tokens):
                    token = tokens[i]
                    if token in ("Z", "z"):
                        if start_point is not None:
                            current = start_point.copy()
                        i += 1
                        continue
                    if token in ("M", "m", "L", "l"):
                        command = token
                        i += 1
                        continue
                    if command in ("M", "m", "L", "l") and i + 1 < len(tokens):
                        try:
                            next_point = np.array([float(tokens[i]), float(tokens[i + 1])])
                            if command in ("m", "l"):
                                next_point = current + next_point
                            current = next_point
                            if start_point is None:
                                start_point = current.copy()
                            poly_pts.append((float(current[0]), float(current[1])))
                            if command in ("M", "m"):
                                command = "L" if command == "M" else "l"
                            i += 2
                        except Exception:
                            logging.debug(
                                "Skipping malformed cam template path segment", exc_info=True
                            )
                            i += 1
                    else:
                        logging.debug("Skipping unsupported cam template path token: %s", token)
                        i += 1
        valid_poly = _finite_path_array(poly_pts, min_points=3)
        if axis is None and valid_poly is not None:
            arr = valid_poly
            center = (np.min(arr, axis=0) + np.max(arr, axis=0)) / 2.0
            axis = center
        if axis is not None and not np.isfinite(axis).all():
            axis = None
        if valid_poly is None:
            logger.warning(
                "CAM template %s did not contain a finite non-degenerate profile", svg_path
            )
            return axis, np.empty((0, 2), dtype=float)
        return axis, valid_poly

    def _build_cam_from_template(
        self,
        template_points: np.ndarray,
        base_radius: float,
        eccentricity: float,
        num_samples: int = 180,
    ) -> np.ndarray:
        base_radius = max(1e-6, _finite_float(base_radius, 25.0))
        eccentricity = max(0.0, _finite_float(eccentricity, 10.0))
        sample_count = max(3, int(_finite_float(num_samples, 180.0)))

        def fallback_circle() -> np.ndarray:
            circle_thetas = np.linspace(0, 2 * np.pi, sample_count)
            return np.stack(
                [base_radius * np.cos(circle_thetas), base_radius * np.sin(circle_thetas)],
                axis=1,
            )

        valid_template = _finite_path_array(template_points, min_points=3)
        if valid_template is None:
            return fallback_circle()
        thetas = np.linspace(0, 2 * np.pi, sample_count)
        u = np.stack([np.cos(thetas), np.sin(thetas)], axis=1)
        dots = u @ valid_template.T
        r_templ = np.max(dots, axis=1)
        r_min = float(np.min(r_templ))
        r_max = float(np.max(r_templ))
        denom = r_max - r_min
        if not np.isfinite(denom) or denom <= 1e-9:
            return fallback_circle()
        s = (r_templ - r_min) / denom
        r = base_radius + eccentricity * s
        return np.stack([r * np.cos(thetas), r * np.sin(thetas)], axis=1)

    def _draw_simple_gear_from_sim(
        self, transform: QTransform, full_sim_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Draws a simple gear train from simulation data."""
        gear_data = full_sim_data["gear_data"]
        frame_idx = 0

        g1_center = np.array(gear_data["gear1_centers"][frame_idx])
        g2_center = np.array(gear_data["gear2_centers"][frame_idx])
        theta1 = float(gear_data["gear1_angles"][frame_idx])
        theta2 = float(gear_data["gear2_angles"][frame_idx])
        r1 = _finite_float(params.get("r1", params.get("gear1_radius", 20.0)), 20.0)
        r2 = _finite_float(params.get("r2", params.get("gear2_radius", 20.0)), 20.0)

        to_screen_coords_func = self._get_transform_for_sim_data(gear_data, "tracking_points")
        if not to_screen_coords_func:
            return

        def to_screen_coords(p: np.ndarray) -> QPointF:
            return to_screen_coords_func(p, transform)

        def draw_gear(
            center: np.ndarray,
            radius: float,
            angle: float,
            teeth: float,
            color: QColor,
        ) -> None:
            center_screen = to_screen_coords(center)
            edge_screen = to_screen_coords(center + np.array([radius, 0.0]))
            radius_screen = QLineF(center_screen, edge_screen).length()
            polygon = gear_outline_polygon(center_screen, radius_screen, teeth, angle)
            self._preview_scene.addPolygon(polygon, QPen(color, 4), QBrush(color.lighter(170)))
            profile = physical_profile_from_params(params)
            if grid_enabled_from_params(params):
                hole_edge = to_screen_coords(
                    center + np.array([max(profile.hole_diameter_mm / 2.0, 0.5), 0.0])
                )
                hole_radius = max(1.5, QLineF(center_screen, hole_edge).length())
                hole_centers = tuple(
                    to_screen_coords(
                        center
                        + np.array(
                            [
                                dx * np.cos(angle) - dy * np.sin(angle),
                                dx * np.sin(angle) + dy * np.cos(angle),
                            ],
                            dtype=float,
                        )
                    )
                    for dx, dy in gear_attachment_grid_offsets_mm(
                        radius,
                        params.get("grid_cell_cm", 2.0),
                        profile=profile,
                    )
                )
            else:
                hole_radius = gear_hole_radius(radius_screen)
                hole_centers = gear_attachment_hole_centers(
                    center_screen, radius_screen, angle, count=4
                )
            for hole_center in hole_centers:
                self._preview_scene.addEllipse(
                    hole_center.x() - hole_radius,
                    hole_center.y() - hole_radius,
                    hole_radius * 2,
                    hole_radius * 2,
                    QPen(QColor("#5c4033"), 1),
                    QBrush(QColor(255, 255, 255, 220)),
                )

            p1 = center_screen
            p2 = to_screen_coords(center + radius * np.array([np.cos(angle), np.sin(angle)]))
            self._preview_scene.addLine(QLineF(p1, p2), QPen(QColor("white"), 2))

        draw_gear(
            g1_center, r1, theta1, _finite_float(params.get("gear1_teeth"), 12.0), QColor("#3498db")
        )
        draw_gear(
            g2_center, r2, theta2, _finite_float(params.get("gear2_teeth"), 16.0), QColor("#2ecc71")
        )

    def _draw_planetary_gear_from_sim(
        self, transform: QTransform, full_sim_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Draws a planetary gear system from simulation data."""
        gear_pos = full_sim_data["gear_positions"]
        frame_idx = 0

        sun_center = np.array(gear_pos["sun_centers"][frame_idx])
        planet_center = np.array(gear_pos["planet_centers"][frame_idx])
        tracking_point = np.array(gear_pos["tracking_points"][frame_idx])
        r_sun = _finite_float(params.get("r_sun", params.get("sun_radius", 20.0)), 20.0)
        r_planet = _finite_float(params.get("r_planet", params.get("planet_radius", 20.0)), 20.0)
        planet_count = min(max(int(round(_finite_float(params.get("planet_count"), 1.0))), 1), 4)

        to_screen_coords_func = self._get_transform_for_sim_data(gear_pos, "tracking_points")
        if not to_screen_coords_func:
            return

        def to_screen_coords(p: np.ndarray) -> QPointF:
            return to_screen_coords_func(p, transform)

        orbit_vector = planet_center - sun_center
        orbit_radius = float(np.linalg.norm(orbit_vector))
        if not np.isfinite(orbit_radius) or orbit_radius <= 1e-6:
            orbit_radius = r_sun + r_planet
            orbit_vector = np.array([orbit_radius, 0.0], dtype=float)
        base_angle = float(np.arctan2(orbit_vector[1], orbit_vector[0]))
        planet_centers = [
            planet_center
            if index == 0
            else sun_center
            + orbit_radius
            * np.array(
                [
                    np.cos(base_angle + (2.0 * np.pi * index / planet_count)),
                    np.sin(base_angle + (2.0 * np.pi * index / planet_count)),
                ],
                dtype=float,
            )
            for index in range(planet_count)
        ]

        sun_screen = to_screen_coords(sun_center)
        planet_screens = [to_screen_coords(center) for center in planet_centers]
        planet_screen = planet_screens[0]
        r_sun_screen = QLineF(
            sun_screen, to_screen_coords(sun_center + np.array([r_sun, 0.0]))
        ).length()
        r_planet_screen = QLineF(
            planet_screen, to_screen_coords(planet_center + np.array([r_planet, 0.0]))
        ).length()
        ring_inner = QLineF(sun_screen, planet_screen).length() + r_planet_screen * 0.55
        ring_outer = ring_inner + max(7.0, min(14.0, r_planet_screen * 0.45))
        self._preview_scene.addPath(
            annulus_path(sun_screen, ring_outer, ring_inner),
            QPen(QColor("#5d6d7e"), 2),
            QBrush(QColor(180, 185, 190, 80)),
        )
        for start, end in radial_tick_lines(sun_screen, ring_inner - 2, ring_inner + 4, 32):
            self._preview_scene.addLine(QLineF(start, end), QPen(QColor("#5d6d7e"), 1))

        def draw_gear(
            center_screen: QPointF,
            radius_screen: float,
            teeth: float,
            color: QColor,
        ) -> None:
            self._preview_scene.addPolygon(
                gear_outline_polygon(center_screen, radius_screen, teeth, 0.0),
                QPen(color, 4),
                QBrush(color.lighter(150)),
            )

        draw_gear(
            sun_screen,
            r_sun_screen,
            _finite_float(params.get("sun_teeth"), 12.0),
            QColor("#7f8c8d"),
        )
        for current_planet_screen in planet_screens:
            self._preview_scene.addLine(
                QLineF(sun_screen, current_planet_screen), QPen(QColor("#d4a017"), 2)
            )
            draw_gear(
                current_planet_screen,
                r_planet_screen,
                _finite_float(params.get("planet_teeth"), 12.0),
                QColor("#e67e22"),
            )

        p1 = planet_screen
        p2 = to_screen_coords(tracking_point)
        self._preview_scene.addLine(QLineF(p1, p2), QPen(QColor("#f39c12"), 3))
        self._preview_scene.addEllipse(
            p2.x() - 5, p2.y() - 5, 10, 10, QPen(QColor("#e74c3c")), QBrush(QColor("#e74c3c"))
        )

    def _render_preview(self) -> None:
        self._preview_scene.clear()
        margin = 5
        view_rect_int = self.rect()
        view_rect_f = QRectF(view_rect_int)
        view_rect_adjusted_f = view_rect_f.adjusted(margin, margin, -margin, -margin)

        self._preview_scene.setSceneRect(view_rect_f)
        self._draw_path_comparison(view_rect_adjusted_f)


class PreviewContainer(QWidget):
    """Container for a single preview and its title/select button."""

    selected = Signal(dict)
    clicked = Signal(dict)

    def __init__(self, mechanism_data: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mechanism_data = mechanism_data
        self._is_selected = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        name = self.mechanism_data.get("type", "Unnamed Mechanism")
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
        if score is not None and score >= 0:
            similarity_percentage = max(0, min(100, (1 / (1 + score)) * 100))
        else:
            similarity_percentage = 0

        match_label = QLabel(f"Match: {similarity_percentage:.1f}%")
        match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        match_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: normal;
                color: #1e8449;
                padding: 5px;
                background-color: #e8f6ef;
                border-radius: 5px;
                border: 1px solid #d1e7dd;
            }
        """)
        layout.addWidget(match_label)

        logger.debug("PreviewContainer: overall_score = %s", score)

        select_button = QPushButton("Apply this")
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
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.mechanism_data)
            self._set_selected_style(True)
        super().mousePressEvent(event)

    def _set_selected_style(self, selected: bool) -> None:
        """Update visual style to show selection."""
        self._is_selected = selected
        if selected:
            self.preview_widget.setStyleSheet("""
                QGraphicsView {
                    border: 3px solid #3498db;
                    border-radius: 8px;
                    background-color: #ffffff;
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


class MechanismRecommendationDialog(QDialog):
    mechanism_selected = Signal(dict)
    mechanism_preview_selected = Signal(dict)

    def __init__(
        self,
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: QWidget | None = None,
        physical_context: PhysicalKitContext | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mechanism Recommendations")
        self.setMinimumSize(1050, 650)
        self.selected_mechanism_data: dict[str, Any] | None = None
        self.physical_context = physical_context

        self.user_motion_path_original = user_motion_path
        self.user_motion_path_np = qpainterpath_to_numpy_array(
            user_motion_path, num_samples_user_path
        )

        self.generated_paths_filepath = generated_paths_filepath
        self.generated_paths_data = self._load_generated_paths(generated_paths_filepath)
        logger.debug("Loaded %s mechanism paths from JSON", len(self.generated_paths_data))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        instruction_label = QLabel("Choose the mechanism that best matches your desired motion")
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

        # Use scroll area to handle multiple recommendations properly
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        # Use grid layout for better space utilization
        self.previews_layout = QGridLayout(scroll_widget)
        self.previews_layout.setSpacing(15)
        self.previews_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        recommendations = self._get_best_recommendations()
        self.preview_containers = []

        if recommendations:
            # Arrange widgets in a grid for better space utilization
            columns = 3
            for i, rec_data in enumerate(recommendations):
                row = i // columns
                col = i % columns

                if rec_data:
                    rec_data_with_user_path = rec_data.copy()
                    rec_data_with_user_path["user_motion_path_local"] = (
                        self.user_motion_path_original
                    )

                    container = PreviewContainer(rec_data_with_user_path, self)
                    container.selected.connect(self._on_select)
                    container.clicked.connect(self._on_preview_click)
                    self.previews_layout.addWidget(container, row, col)
                    self.preview_containers.append(container)
                else:
                    placeholder_label = QLabel("No mechanism found")
                    placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder_label.setFixedSize(280, 220)  # Match reduced preview size
                    placeholder_label.setStyleSheet(
                        "background-color: #f0f0f0; border: 1px solid #cccccc;"
                    )
                    self.previews_layout.addWidget(placeholder_label, row, col)
        else:
            no_recs_label = QLabel("No mechanism recommendations could be generated or found.")
            no_recs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.previews_layout.addWidget(no_recs_label, 0, 0, 1, 3)

        main_layout.addWidget(scroll_area, 1)

        # Simple close button for users who want to exit without selecting
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        self.close_button = QPushButton("Close")
        self.close_button.setFixedSize(100, 40)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)
        self.close_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()

        main_layout.addSpacing(20)
        main_layout.addLayout(button_layout)
        main_layout.addSpacing(10)

        self.setLayout(main_layout)

    def _load_generated_paths(self, filepath: str) -> list[dict[str, Any]]:
        """Loads mechanism paths from a JSON file and prepares them."""
        loaded_paths: list[dict[str, Any]] = []
        try:
            with open(filepath) as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, list):
                logger.error("Generated paths file must contain a list: %s", filepath)
                return loaded_paths

            for index, item in enumerate(raw_data):
                if not isinstance(item, dict):
                    logger.warning("Skipping malformed generated path row %s: %r", index, item)
                    continue
                path_coords = None
                try:
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

                    if path_coords is None:
                        path_coords = item.get("path_coordinates")

                    path_array = _finite_path_array(path_coords)
                    if path_array is not None:
                        loaded_item = dict(item)
                        loaded_item["path_coordinates_np"] = path_array
                        loaded_paths.append(loaded_item)
                    else:
                        logger.warning(
                            "Missing, malformed, non-finite, or degenerate path coordinates for item: %s",
                            item.get("type", "N/A"),
                        )
                except Exception as exc:
                    logger.warning("Skipping malformed generated path row %s: %s", index, exc)

        except FileNotFoundError:
            logger.error("Generated paths file not found at %s", filepath)
        except json.JSONDecodeError:
            logger.error("Could not decode JSON from %s", filepath)
        except Exception as e:
            logger.error("An unexpected error occurred while loading generated paths: %s", e)
        return loaded_paths

    def _get_best_recommendations(self) -> list[dict[str, Any] | None]:
        """
        Finds the best mechanism per family using time-aware matching.
        Families: Four-Bar Linkage, Cam & Follower, Gears (includes Planetary).
        """
        if self.user_motion_path_np is None:
            logger.error("User motion path is not processed or no generated paths loaded.")
            return []
        if not self.generated_paths_data:
            logger.error("No generated paths loaded.")
            return []

        logger.debug("User path has %s points", len(self.user_motion_path_np))
        logger.debug("Total mechanisms in database: %s", len(self.generated_paths_data))

        type_mapping = {
            "4-bar Coupler": "Four-Bar Linkage",
            "3-bar Output": "Four-Bar Linkage",
            "Four-Bar": "Four-Bar Linkage",
            "Cam Profile": "Cam & Follower",
            "Cam-Follower": "Cam & Follower",
            "Cam": "Cam & Follower",
            "Gear Train": "Gears",
            "Gear Contact": "Gears",
            "Simple Gear": "Gears",
            "Planetary Gear": "Gears",
        }

        # Best per family
        best_by_family: dict[str, dict[str, Any]] = {}
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
            ) = align_and_compare_paths(
                self.user_motion_path_np, gen_path_np, mechanism_type=json_type_str
            )

            if user_path_aligned is None or gen_path_aligned is None or transform_params is None:
                continue

            if total_comparisons <= 5:
                logger.debug(
                    "sample %s: %s - distance: %.2f", total_comparisons, json_type_str, distance
                )

            family = type_mapping.get(json_type_str, None)
            if family is None:
                # Skip types we don't recognize as a target family
                continue

            # Time-aware matching: resample aligned shapes by arc-length (proxy for time).
            # Hausdorff alignment is intentionally shape-only, so compare both traversal
            # directions afterward.  Stored/template paths may be generated in the opposite
            # order from the path the user just drew; the selected direction must therefore
            # become explicit metadata instead of being hidden in a bad score.
            N = DEFAULT_NUM_SAMPLES_FOR_PATH
            user_time = _resample_time_aligned(user_path_aligned, N)
            mech_time_forward = _resample_time_aligned(gen_path_aligned, N)
            mech_path_aligned_reversed = gen_path_aligned[::-1]
            mech_time_reversed = _resample_time_aligned(mech_path_aligned_reversed, N)
            time_score_forward = _time_aware_distance(user_time, mech_time_forward)
            time_score_reversed = _time_aware_distance(user_time, mech_time_reversed)
            matched_reversed = time_score_reversed < time_score_forward
            time_score = time_score_reversed if matched_reversed else time_score_forward
            if not np.isfinite(time_score):
                continue

            existing_reverse_direction = _candidate_reverse_direction(gen_path_data)
            reverse_direction = existing_reverse_direction ^ matched_reversed
            selected_mech_path_aligned = (
                mech_path_aligned_reversed if matched_reversed else gen_path_aligned
            )
            raw_params = gen_path_data.get("parameters", {})
            params = dict(raw_params) if isinstance(raw_params, dict) else {}
            params["reverse_direction"] = reverse_direction
            params = dict(
                _fabrication_ready_recommendation_params(
                    json_type_str,
                    family,
                    params,
                    _dialog_physical_context(self),
                )
            )
            params["reverse_direction"] = reverse_direction

            preview_data = {
                "name": gen_path_data.get("name", f"{json_type_str} Mechanism"),
                "type": family,
                "original_json_type": json_type_str,
                # Prefer time-aware score for selection; include both for transparency
                "overall_score": time_score,
                "scores": {
                    "time_aware": time_score,
                    "time_aware_forward": time_score_forward,
                    "time_aware_reversed": time_score_reversed,
                    "shape_only": distance,
                    "path_direction": "reversed" if matched_reversed else "forward",
                },
                "parameters": params,
                "fabrication_ready": grid_enabled_from_params(params),
                "reverse_direction": reverse_direction,
                "path_coordinates_np": gen_path_np,
                "path_coordinates": gen_path_data.get("path_coordinates"),
                "key_points": gen_path_data.get("key_points", {}),
                "path_normalization": gen_path_data.get("path_normalization", {}),
                "full_simulation_data": gen_path_data.get("full_simulation_data", {}),
                "user_path_aligned_np": user_path_aligned,
                "mech_path_aligned_np": selected_mech_path_aligned,
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

            # Keep best (lowest score) per family
            candidate_key = (
                float(time_score),
                bool(matched_reversed),
                str(json_type_str),
                str(preview_data["name"]),
                _stable_recommendation_identity(gen_path_data, str(json_type_str)),
            )
            preview_data["_selection_key"] = candidate_key
            if (
                family not in best_by_family
                or candidate_key < best_by_family[family]["_selection_key"]
            ):
                best_by_family[family] = preview_data

        logger.debug("Made %s path comparisons", total_comparisons)
        logger.debug("Families found: %s", list(best_by_family.keys()))

        # Return exactly one per family in fixed order
        families_order = ["Four-Bar Linkage", "Cam & Follower", "Gears"]
        results: list[dict[str, Any] | None] = []
        for fam in families_order:
            best = best_by_family.get(fam)
            if best is None:
                results.append(None)
            else:
                cleaned_best = dict(best)
                cleaned_best.pop("_selection_key", None)
                results.append(cleaned_best)

        for i, mech in enumerate(results):
            if mech:
                logger.debug(
                    "Recommendation %s: %s - %s (time_score: %.2f, shape_score: %.2f)",
                    i + 1,
                    mech["type"],
                    mech["name"],
                    mech["scores"]["time_aware"],
                    mech["scores"]["shape_only"],
                )
            else:
                logger.debug("Recommendation %s: None (no candidate in family)", i + 1)

        return results

    def _on_select(self, mechanism_data: dict[str, Any]) -> None:
        """Handle immediate application of selected mechanism."""
        self.selected_mechanism_data = mechanism_data

        # Provide visual feedback for the selection
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)

        # Emit the selection signal and immediately accept the dialog
        self.mechanism_selected.emit(mechanism_data)
        self.accept()

    def _on_preview_click(self, mechanism_data: dict[str, Any]) -> None:
        """Handle preview click to show mechanism in main view."""
        for container in self.preview_containers:
            container._set_selected_style(container.mechanism_data == mechanism_data)
        self.mechanism_preview_selected.emit(mechanism_data)

    @staticmethod
    def get_recommendation(
        user_motion_path: QPainterPath,
        generated_paths_filepath: str,
        num_samples_user_path: int = DEFAULT_NUM_SAMPLES_FOR_PATH,
        parent: QWidget | None = None,
    ) -> dict[str, Any] | None:
        """Static method to show the dialog and return the selected mechanism data."""
        dialog = MechanismRecommendationDialog(
            user_motion_path, generated_paths_filepath, num_samples_user_path, parent
        )
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return dialog.selected_mechanism_data
        return None

    def _get_mechanism_points_orig(self, mechanism_data: dict[str, Any]) -> np.ndarray | None:
        """Gathers all points of the mechanism (structure and path) in original coordinates."""
        params = mechanism_data.get("parameters")
        path_points = mechanism_data.get("path_coordinates_np")

        path_array = _finite_path_array(path_points)
        if path_array is None or not isinstance(params, dict):
            return None

        all_points: list[np.ndarray] = [path_array]
        mech_type = mechanism_data.get("original_json_type")
        raw_key_points = mechanism_data.get("key_points")
        key_points = raw_key_points if isinstance(raw_key_points, dict) else {}

        def point_array(value: object) -> np.ndarray | None:
            if value is None:
                return None
            try:
                point = np.asarray(value, dtype=float).reshape(-1)
            except (TypeError, ValueError):
                return None
            if point.shape[0] < 2:
                return None
            point_pair = point[:2]
            return point_pair if np.isfinite(point_pair).all() else None

        if mech_type == "4-bar Coupler" and key_points:
            p1_coords = key_points.get("ground_pivot_1")
            p2_coords = key_points.get("ground_pivot_2")
            p3_coords = key_points.get("initial_moving_joint_1")
            p4_coords = key_points.get("initial_moving_joint_2")

            pivot_points: list[np.ndarray] = []
            for coords in [p1_coords, p2_coords, p3_coords, p4_coords]:
                point = point_array(coords)
                if point is not None:
                    pivot_points.append(point)

            if pivot_points:
                all_points.append(np.array(pivot_points))

        elif mech_type in ["Cam Follower", "Cam-Follower", "Cam & Follower", "Cam"]:
            base_radius = _finite_float(params.get("base_radius"), float("nan"))
            eccentricity = _finite_float(params.get("eccentricity"), float("nan"))
            if np.isfinite(base_radius) and np.isfinite(eccentricity):
                cam_center = point_array(key_points.get("cam_center"))
                cam_center_orig = (
                    cam_center if cam_center is not None else np.array([eccentricity, 0.0])
                )
                rotation_center = point_array(key_points.get("rotation_center"))
                if rotation_center is not None:
                    all_points.append(np.array([rotation_center]))
                else:
                    all_points.append(np.array([[0.0, 0.0]]))

                # Create proper egg-shaped cam profile with correct physics
                thetas = np.linspace(0, 2 * np.pi, 40)  # More points for smoother egg shape

                # Proper cam profile: lift when convex part is at bottom (pushes follower up)
                # Using sinusoidal lift profile shifted for correct physics
                lift = (
                    eccentricity * (1 + np.cos(thetas + np.pi / 2)) / 2
                )  # Shifted for proper phase
                radii = base_radius + lift

                # Convert to Cartesian coordinates
                cam_points_x = cam_center_orig[0] + radii * np.cos(thetas)
                cam_points_y = cam_center_orig[1] + radii * np.sin(thetas)

                cam_points = np.column_stack([cam_points_x, cam_points_y])
                all_points.append(cam_points)

        elif mech_type in ["Gear Contact", "Simple Gear", "Gears (Simple Pair)", "Gear"]:
            r1 = _finite_float(params.get("r1", params.get("gear1_radius")), float("nan"))
            r2 = _finite_float(params.get("r2", params.get("gear2_radius")), float("nan"))
            if np.isfinite(r1) and np.isfinite(r2) and r1 > 0.0 and r2 > 0.0:
                gear1_center = point_array(key_points.get("gear1_center"))
                gear2_center = point_array(key_points.get("gear2_center"))
                c1_orig = gear1_center if gear1_center is not None else np.array([0.0, 0.0])
                profile = physical_profile_from_params(params)
                c2_orig = (
                    gear2_center
                    if gear2_center is not None
                    else np.array(
                        [
                            gear_center_distance(
                                r1,
                                r2,
                                gear_clearance_from_params(params, profile=profile),
                                profile=profile,
                            ),
                            0.0,
                        ]
                    )
                )
                thetas = np.linspace(0, 2 * np.pi, 20)
                g1_points = c1_orig + r1 * np.array([np.cos(thetas), np.sin(thetas)]).T
                g2_points = c2_orig + r2 * np.array([np.cos(thetas), np.sin(thetas)]).T
                all_points.append(g1_points)
                all_points.append(g2_points)

        return np.vstack(all_points)
