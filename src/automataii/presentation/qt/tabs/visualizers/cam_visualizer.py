"""
Cam Visualizer - Visual representation for cam and follower mechanisms.

Extracted from MechanismVisualsFactory to support polymorphic dispatch.
Handles creation and update of cam mechanism visuals using analytic pear-cam profile.

Design Pattern: Strategy (implements MechanismVisualizerProtocol)
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
)

from .protocol import BaseMechanismVisualizer


class CamVisualizer(BaseMechanismVisualizer):
    """Visualizer for cam and follower mechanisms.

    Creates visual representation using analytic pear-cam profile:
    - No dataset/template dependency: profile is built from base_radius and eccentricity
    - Pear-cam lobe: single-sided rise/return with dwells; shape preserved under rotation
    """

    @property
    def mechanism_type(self) -> str:
        return "cam"

    def create_visuals(
        self,
        mechanism_data: dict[str, Any],
        transform_function: Any | None = None,
        **kwargs: Any,
    ) -> list[QGraphicsItem]:
        """Create visual representation of cam and follower mechanism.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state
            transform_function: Optional coordinate transform function
            **kwargs: May include 'character_position' for placement

        Returns:
            List of QGraphicsItem objects representing the cam mechanism
        """
        base_transform = self._get_transform_function(mechanism_data, transform_function)
        params = mechanism_data.get("params", {})

        if not params:
            return []

        # Extract cam parameters with defaults
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        follower_rod_length = params.get("follower_rod_length", 40.0)

        # Scale factors for CAM size adjustment
        cam_scale_factor = mechanism_data.get("cam_scale_factor", 1.0)
        rod_length_multiplier = mechanism_data.get("rod_length_multiplier", 1.0)

        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Build cam profile from parameters
        profile_params = self._extract_profile_params(params)
        cam_points_local = self._build_pear_cam_profile(
            base_radius=scaled_base_radius,
            eccentricity=scaled_eccentricity,
            rise_deg=profile_params["rise_deg"],
            high_dwell_deg=profile_params["high_dwell_deg"],
            dwell_low_deg=profile_params["low_dwell_deg"],
            align_max_to_deg=profile_params["align_max_deg"],
            num_samples=360,
        )
        mechanism_data["cam_points_local"] = cam_points_local

        # Determine cam transform function
        cam_to_scene = self._setup_cam_transform(
            mechanism_data,
            base_transform,
            cam_points_local,
            scaled_rod_length,
        )
        if cam_to_scene is None:
            return []

        # Store scaling factors for animation consistency
        mechanism_data["cam_scale_factor"] = cam_scale_factor
        mechanism_data["rod_length_multiplier"] = rod_length_multiplier

        # Create visual items
        visual_items: list[QGraphicsItem] = []

        # Build cam polygon and create visuals
        self._create_cam_body(visual_items, mechanism_data, cam_to_scene)
        self._create_follower(visual_items, mechanism_data, cam_to_scene)
        self._create_cam_center(visual_items, cam_to_scene)
        self._create_follower_rod(visual_items, mechanism_data, cam_to_scene)
        self._add_curvature_diagnostics(visual_items, mechanism_data, cam_to_scene)

        return visual_items

    def update_visuals(
        self,
        time: float,
        layer_data: dict[str, Any],
        visual_items: list[QGraphicsItem],
        **kwargs: Any,
    ) -> None:
        """Update cam mechanism visuals for animation frame.

        Args:
            time: Animation time in radians (0 to 2π for one cycle)
            layer_data: Layer data containing mechanism state
            visual_items: List of visual items to update
            **kwargs: Additional arguments
        """
        # Cam animation is handled by MechanismVisualAnimator
        pass

    def regenerate_simulation(
        self,
        params: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Regenerate simulation data for cam mechanism.

        Args:
            params: Cam mechanism parameters
            **kwargs: Additional options

        Returns:
            Dictionary containing simulation results
        """
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)

        profile_params = self._extract_profile_params(params)
        cam_points = self._build_pear_cam_profile(
            base_radius=base_radius,
            eccentricity=eccentricity,
            rise_deg=profile_params["rise_deg"],
            high_dwell_deg=profile_params["high_dwell_deg"],
            dwell_low_deg=profile_params["low_dwell_deg"],
            align_max_to_deg=profile_params["align_max_deg"],
            num_samples=360,
        )

        return {
            "cam_points_local": cam_points,
            "base_radius": base_radius,
            "eccentricity": eccentricity,
        }

    def _extract_profile_params(self, params: dict[str, Any]) -> dict[str, float]:
        """Extract and validate cam profile parameters.

        Args:
            params: Raw mechanism parameters

        Returns:
            Validated profile parameters
        """
        rise_deg = float(params.get("rise_deg", 90.0))
        high_dwell_deg = float(params.get("high_dwell_deg", 60.0))

        # Calculate low dwell from explicit value or derive from return
        if "low_dwell_deg" in params:
            low_dwell_deg = float(params.get("low_dwell_deg", 180.0))
            low_dwell_deg = max(0.0, min(360.0, low_dwell_deg))
        else:
            return_deg = float(params.get("return_deg", 30.0))
            low_dwell_deg = max(0.0, 360.0 - (rise_deg + high_dwell_deg + return_deg))

        align_max_deg = float(params.get("align_max_deg", 90.0))

        # Guard against invalid sums - scale proportionally to fit 360°
        total = rise_deg + high_dwell_deg + low_dwell_deg
        if total > 360.0:
            scale = 360.0 / max(1e-6, total)
            rise_deg *= scale
            high_dwell_deg *= scale
            low_dwell_deg *= scale

        return {
            "rise_deg": rise_deg,
            "high_dwell_deg": high_dwell_deg,
            "low_dwell_deg": low_dwell_deg,
            "align_max_deg": align_max_deg,
        }

    def _setup_cam_transform(
        self,
        mechanism_data: dict[str, Any],
        base_transform: Any | None,
        cam_points_local: np.ndarray,
        scaled_rod_length: float,
    ) -> Any | None:
        """Setup coordinate transform function for cam positioning.

        Aligns follower center with bottom of user's path if available.

        Args:
            mechanism_data: Mechanism data dictionary (will be modified)
            base_transform: Base coordinate transform function
            cam_points_local: Local cam profile points
            scaled_rod_length: Scaled follower rod length

        Returns:
            Transform function for cam coordinates, or None if invalid
        """
        if base_transform is None:
            return None

        gen_path = mechanism_data.get("generated_path")
        if gen_path is None:
            mechanism_data["cam_transform_function"] = base_transform
            return base_transform

        try:
            brect = gen_path.boundingRect()
            path_x_center = float(brect.center().x())
            path_y_bottom = float(brect.bottom())
            local_y_max = float(np.max(cam_points_local[:, 1]))

            # Place cam such that its top touches path bottom
            follower_local = np.array([0.0, local_y_max])
            follower_scene_raw = base_transform(follower_local)
            dx = path_x_center - follower_scene_raw.x()
            dy = path_y_bottom - follower_scene_raw.y()

            def cam_to_scene_coords(p: Any) -> QPointF:
                if p is None or len(p) != 2:
                    return QPointF(follower_scene_raw.x() + dx, follower_scene_raw.y() + dy)
                mapped = base_transform(p)
                return QPointF(mapped.x() + dx, mapped.y() + dy)

            mechanism_data["cam_transform_function"] = cam_to_scene_coords
            mechanism_data["cam_position"] = [path_x_center, path_y_bottom - local_y_max - scaled_rod_length]
            return cam_to_scene_coords

        except Exception:
            mechanism_data["cam_transform_function"] = base_transform
            return base_transform

    def _create_cam_body(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict[str, Any],
        cam_to_scene: Any,
    ) -> None:
        """Create the cam body polygon visual.

        Args:
            visual_items: List to append created items
            mechanism_data: Mechanism data containing cam points
            cam_to_scene: Coordinate transform function
        """
        cam_points = mechanism_data.get("cam_points_local")
        if cam_points is None:
            return

        # Build polygon from cam profile points
        cam_polygon_points = [cam_to_scene(p) for p in cam_points]
        cam_polygon = QPolygonF(cam_polygon_points)

        # Create cam body with gear blue color
        cam_color = QColor("#3498db")
        cam_body = QGraphicsPolygonItem(cam_polygon)
        cam_body.setPen(QPen(cam_color, 4))
        cam_body.setBrush(QBrush(cam_color.lighter(170)))
        cam_body.setZValue(15)
        cam_body.setOpacity(1.0)
        cam_body.setToolTip("Cam Profile")
        self.scene.addItem(cam_body)
        visual_items.append(cam_body)

    def _create_follower(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict[str, Any],
        cam_to_scene: Any,
    ) -> None:
        """Create the follower body visual.

        Args:
            visual_items: List to append created items
            mechanism_data: Mechanism data
            cam_to_scene: Coordinate transform function
        """
        cam_points = mechanism_data.get("cam_points_local")
        if cam_points is None:
            return

        y_max = float(np.max(cam_points[:, 1]))
        follower_pos = np.array([0.0, y_max], dtype=float)
        follower_scene = cam_to_scene(follower_pos)

        # Store follower's fixed X position for vertical motion constraint
        try:
            mechanism_data["follower_fixed_x_scene"] = float(follower_scene.x())
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        # Create follower rectangle
        follower_color = QColor("#ff9800")  # Orange
        follower_width, follower_height = 20, 15
        follower_body = QGraphicsRectItem(
            follower_scene.x() - follower_width / 2,
            follower_scene.y() - follower_height / 2,
            follower_width,
            follower_height,
        )
        follower_body.setPen(QPen(follower_color.darker(120), 2))
        follower_body.setBrush(QBrush(follower_color))
        follower_body.setZValue(16)
        follower_body.setToolTip("Follower - Moves up/down as cam rotates")
        self.scene.addItem(follower_body)
        visual_items.append(follower_body)

    def _create_cam_center(
        self,
        visual_items: list[QGraphicsItem],
        cam_to_scene: Any,
    ) -> None:
        """Create the cam center marker (rotation point).

        Args:
            visual_items: List to append created items
            cam_to_scene: Coordinate transform function
        """
        cam_center = np.array([0.0, 0.0], dtype=float)
        cam_center_scene = cam_to_scene(cam_center)

        cam_center_color = QColor("#f44336")  # Red
        cam_center_marker = QGraphicsEllipseItem(
            cam_center_scene.x() - 5,
            cam_center_scene.y() - 5,
            10,
            10,
        )
        cam_center_marker.setPen(QPen(cam_center_color.darker(150), 2))
        cam_center_marker.setBrush(QBrush(cam_center_color))
        cam_center_marker.setZValue(20)
        cam_center_marker.setToolTip("Cam Center - Rotation axis")
        self.scene.addItem(cam_center_marker)
        visual_items.append(cam_center_marker)

    def _create_follower_rod(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict[str, Any],
        cam_to_scene: Any,
    ) -> None:
        """Create the follower rod line visual.

        Args:
            visual_items: List to append created items
            mechanism_data: Mechanism data containing cam points
            cam_to_scene: Coordinate transform function
        """
        cam_points = mechanism_data.get("cam_points_local")
        if cam_points is None:
            return

        y_max = float(np.max(cam_points[:, 1]))
        cam_top = np.array([0.0, y_max])
        cam_top_scene = cam_to_scene(cam_top)

        follower_pos = np.array([0.0, y_max], dtype=float)
        follower_scene = cam_to_scene(follower_pos)

        rod_pen = QPen(QColor("#9e9e9e"), 3, Qt.PenStyle.DashLine)
        follower_rod = QGraphicsLineItem(
            cam_top_scene.x(),
            cam_top_scene.y(),
            follower_scene.x(),
            follower_scene.y(),
        )
        follower_rod.setPen(rod_pen)
        follower_rod.setZValue(14)
        follower_rod.setToolTip("Connecting Rod")
        self.scene.addItem(follower_rod)
        visual_items.append(follower_rod)

    def _add_curvature_diagnostics(
        self,
        visual_items: list[QGraphicsItem],
        mechanism_data: dict[str, Any],
        cam_to_scene: Any,
    ) -> None:
        """Add high-curvature highlight overlay on cam profile.

        Highlights regions where curvature exceeds 90th percentile.

        Args:
            visual_items: List to append created items
            mechanism_data: Mechanism data containing cam points
            cam_to_scene: Coordinate transform function
        """
        cam_points = mechanism_data.get("cam_points_local")
        if cam_points is None or len(cam_points) < 5:
            return

        try:
            # Calculate discrete curvature at each point
            k_values = []
            for i in range(1, len(cam_points) - 2):
                x1, y1 = cam_points[i - 1]
                x2, y2 = cam_points[i]
                x3, y3 = cam_points[i + 1]
                dx1, dy1 = x2 - x1, y2 - y1
                dx2, dy2 = x3 - x2, y3 - y2
                num = abs(dx1 * dy2 - dy1 * dx2)
                den = (dx1 * dx1 + dy1 * dy1) ** 1.5 + 1e-6
                k_values.append(num / den)

            if not k_values:
                return

            # Find high-curvature threshold (90th percentile)
            k_arr = np.array(k_values)
            threshold = float(np.percentile(k_arr, 90))

            # Build highlight path
            highlight = QPainterPath()
            for i, kval in enumerate(k_values, start=1):
                if kval >= threshold:
                    scene_point = cam_to_scene(cam_points[i])
                    if highlight.isEmpty():
                        highlight.moveTo(scene_point)
                    else:
                        highlight.lineTo(scene_point)

            if not highlight.isEmpty():
                hp = QGraphicsPathItem(highlight)
                hp.setPen(QPen(QColor("#e74c3c"), 3, Qt.PenStyle.SolidLine))
                hp.setZValue(25)
                self.scene.addItem(hp)
                visual_items.append(hp)

        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _build_pear_cam_profile(
        self,
        base_radius: float,
        eccentricity: float,
        rise_deg: float = 90.0,
        high_dwell_deg: float = 60.0,
        dwell_low_deg: float = 180.0,
        align_max_to_deg: float = 90.0,
        num_samples: int = 360,
    ) -> np.ndarray:
        """Build analytic pear-cam (single-lobe) profile with sinusoidal rise/return.

        Matches blueprint script defaults:
        - rise=90deg, high dwell=60deg, low dwell=180deg, fall inferred
        - align_max_to_deg: angle where radius is maximum (default 90deg => +Y)
        - r(theta) = base_radius + eccentricity * s(theta)

        Args:
            base_radius: Base circle radius
            eccentricity: Maximum lift (added to base_radius)
            rise_deg: Rise segment in degrees
            high_dwell_deg: High dwell segment in degrees
            dwell_low_deg: Low dwell segment in degrees
            align_max_to_deg: Angle where max radius occurs
            num_samples: Number of profile samples

        Returns:
            Array of shape (num_samples, 2) with cam profile points

        Time Complexity: O(num_samples)
        """
        rise = np.deg2rad(rise_deg)
        dwell_high = np.deg2rad(high_dwell_deg)
        dwell_low = np.deg2rad(dwell_low_deg)
        total = 2 * np.pi
        fall = max(0.0, total - (rise + dwell_high + dwell_low))

        # Phase reference: ensure max radius at align_max_to_deg
        theta0 = np.deg2rad(align_max_to_deg)
        seg1_end = theta0 + rise
        seg2_end = seg1_end + dwell_high
        seg3_end = seg2_end + fall

        thetas = np.linspace(0, 2 * np.pi, num_samples, endpoint=False)
        s = np.zeros_like(thetas)

        for i, t in enumerate(thetas):
            rel = (t - theta0) % (2 * np.pi) + theta0
            if rel < seg1_end:  # rise 0->1
                u = (rel - theta0) / rise if rise > 0 else 1.0
                s[i] = 0.5 * (1 - np.cos(np.pi * u))
            elif rel < seg2_end:  # high dwell at 1
                s[i] = 1.0
            elif rel < seg3_end:  # fall 1->0
                u = (rel - seg2_end) / fall if fall > 0 else 1.0
                s[i] = 0.5 * (1 + np.cos(np.pi * u))
            else:  # low dwell at 0
                s[i] = 0.0

        r = base_radius + eccentricity * s
        pts = np.stack([r * np.cos(thetas), r * np.sin(thetas)], axis=1)
        return pts.astype(float)

    def _load_cam_profile_svg(self, svg_path: str) -> tuple[np.ndarray, np.ndarray]:
        """Parse a simple SVG cam profile and return (axis, polygon_points).

        Assumptions:
        - Uses a <path> composed of M/L commands for the cam outline
        - A <circle> in construction layer gives axis (cx, cy)
        - Ignores group transforms as both elements share the same space

        Args:
            svg_path: Path to SVG file

        Returns:
            Tuple of (axis_point, polygon_points)

        Time Complexity: O(n) where n is number of path commands
        """
        tree = ET.parse(svg_path)
        root = tree.getroot()

        def strip(tag: str) -> str:
            return tag.split("}", 1)[-1]

        axis = None
        poly_pts: list[tuple[float, float]] = []

        for elem in root.iter():
            tag = strip(elem.tag)
            if tag == "circle" and axis is None:
                cx = float(elem.attrib.get("cx", "0"))
                cy = float(elem.attrib.get("cy", "0"))
                axis = np.array([cx, cy], dtype=float)
            elif tag == "path":
                d = elem.attrib.get("d", "")
                if not d:
                    continue
                # Simple M/L tokenizer
                tokens = d.replace(",", " ").split()
                i = 0
                while i < len(tokens):
                    cmd = tokens[i]
                    if cmd in ("M", "L") and i + 2 < len(tokens):
                        try:
                            x = float(tokens[i + 1])
                            y = float(tokens[i + 2])
                            poly_pts.append((x, y))
                            i += 3
                        except ValueError:
                            i += 1
                    else:
                        # Handle implicit L commands
                        try:
                            x = float(cmd)
                            y = float(tokens[i + 1])
                            poly_pts.append((x, y))
                            i += 2
                        except Exception:
                            i += 1

        if axis is None and poly_pts:
            # Fallback: center of bounding box
            arr = np.array(poly_pts, dtype=float)
            center = (np.min(arr, axis=0) + np.max(arr, axis=0)) / 2.0
            axis = center

        arr = np.array(poly_pts, dtype=float) if poly_pts else np.zeros((0, 2))
        return axis if axis is not None else np.array([0.0, 0.0]), arr

    def _build_cam_from_template(
        self,
        template_points: np.ndarray,
        base_radius: float,
        eccentricity: float,
        num_samples: int = 180,
    ) -> np.ndarray:
        """Build a cam polygon from a template profile using normalized radial mapping.

        - Compute support function r_templ(theta) = max(dot(p, u_theta)) over template points
        - Normalize: s(theta) = (r_templ(theta) - min) / (max - min + eps)
        - New radius: r(theta) = base_radius + eccentricity * s(theta)
        - Return polygon points: r(theta) * [cos(theta), sin(theta)]

        Args:
            template_points: Template profile points array
            base_radius: Base circle radius
            eccentricity: Maximum lift
            num_samples: Number of output samples

        Returns:
            Array of shape (num_samples+1, 2) with cam profile points

        Time Complexity: O(num_samples * template_points)
        """
        if template_points is None or len(template_points) < 3:
            # Fallback to circular cam
            pts = []
            for i in range(num_samples + 1):
                theta = 2 * np.pi * i / num_samples
                pts.append([base_radius * np.cos(theta), base_radius * np.sin(theta)])
            return np.array(pts, dtype=float)

        thetas = np.linspace(0, 2 * np.pi, num_samples + 1)
        u = np.stack([np.cos(thetas), np.sin(thetas)], axis=1)  # (N,2)

        # Compute support: for each theta, max over points dot(p, u_theta)
        # template_points shape (M,2), dots shape (N,M) = u @ p^T
        dots = u @ template_points.T
        r_templ = np.max(dots, axis=1)
        r_min = float(np.min(r_templ))
        r_max = float(np.max(r_templ))
        denom = max(1e-9, r_max - r_min)
        s = (r_templ - r_min) / denom
        r_new = base_radius + eccentricity * s
        pts = np.stack([r_new * np.cos(thetas), r_new * np.sin(thetas)], axis=1)
        return pts.astype(float)
