"""
Cam Editor - Editor for cam mechanisms with physics-based follower.

Extracted from parametric_editor.py.

Design Pattern: Concrete Strategy (mechanism-specific editing)
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float,
    positive_finite_float,
)
from automataii.presentation.qt.tabs.cam_geometry import (
    cam_contact_y_from_params,
    cam_follower_base_scene,
    cam_scene_unit_scale,
)
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    physical_profile_from_params,
    snap_cam_params,
)

from .base_editor import HandleStyle, MechanismEditor, ParametricHandle


class CamEditor(MechanismEditor):
    """Editor for cam mechanisms with physics-based follower."""

    _MIN_TOTAL_RADIUS = 15.0
    _MAX_TOTAL_RADIUS = 130.0  # base_radius max (80) + eccentricity max (50)

    def _physical_profile(self):
        params = self.mechanism_data.get("params", {}) if hasattr(self, "mechanism_data") else {}
        if "physical_profile_key" in params:
            return physical_profile_from_params(params)
        return DEFAULT_PHYSICAL_KIT_PROFILE

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for cam shape and follower rod."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})

        if "cam_position" in mechanism_data:
            cam_position = mechanism_data["cam_position"]
            center = QPointF(
                finite_float(cam_position[0], 0.0),
                finite_float(cam_position[1], 0.0),
            )
        else:
            center = QPointF(
                finite_float(params.get("center_x"), 0.0),
                finite_float(params.get("center_y"), 0.0),
            )

        params["center_x"] = center.x()
        params["center_y"] = center.y()

        # Cam center handle
        center_handle = ParametricHandle(
            center,
            f"{self.mechanism_id}_center",
            "center",
            self._on_center_moved,
            style=HandleStyle(size=16, color=QColor(100, 200, 100)),
        )
        center_handle.setToolTip("Cam Center - Drag to move")
        self.scene.addItem(center_handle)
        self.handles["center"] = center_handle

        # Default parameters
        base_radius = positive_finite_float(params.get("base_radius"), 25.0)
        eccentricity = max(0.0, finite_float(params.get("eccentricity"), 10.0))
        params["base_radius"] = base_radius
        params["eccentricity"] = eccentricity
        params.setdefault("rise_deg", 90.0)
        params.setdefault("high_dwell_deg", 60.0)
        params.setdefault("return_deg", 30.0)
        params.setdefault("align_max_deg", 90.0)
        if self._physical_grid_enabled():
            params.update(
                snap_cam_params(
                    params,
                    self._physical_grid_cell_cm(),
                    profile=self._physical_profile(),
                )
            )

        self._create_cam_size_handle(params)
        self._create_follower_handle(params)

        try:
            self._create_cam_angle_handles(
                QPointF(params.get("center_x", 0), params.get("center_y", 0)), params
            )
        except Exception as e:
            logging.debug(f"[CAM-EDITOR] Skipped angle handles: {e}")

    def _physical_grid_enabled(self) -> bool:
        params = self.mechanism_data.get("params", {}) if hasattr(self, "mechanism_data") else {}
        raw_value = params.get(
            "grid_system_enabled",
            self.mechanism_data.get("grid_system_enabled", True)
            if hasattr(self, "mechanism_data")
            else True,
        )
        if isinstance(raw_value, str):
            return raw_value.strip().lower() not in {"0", "false", "no", "off", ""}
        return bool(raw_value)

    def _physical_grid_cell_cm(self) -> float:
        params = self.mechanism_data.get("params", {}) if hasattr(self, "mechanism_data") else {}
        return finite_float(
            params.get(
                "grid_cell_cm",
                self.mechanism_data.get("grid_cell_cm", DEFAULT_GRID_CELL_CM)
                if hasattr(self, "mechanism_data")
                else DEFAULT_GRID_CELL_CM,
            ),
            DEFAULT_GRID_CELL_CM,
        )

    def _create_cam_size_handle(self, params: dict) -> None:
        """Create handle for adjusting cam size (base_radius and eccentricity).

        The handle is placed at the cam's outer edge (base_radius + eccentricity)
        on the right side (+X direction). Dragging it horizontally adjusts the
        cam size while maintaining the base_radius/eccentricity ratio.
        """
        center = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        base_radius = positive_finite_float(params.get("base_radius"), 25.0)
        eccentricity = max(0.0, finite_float(params.get("eccentricity"), 10.0))

        # Apply scale factor if available
        cam_scale_factor = positive_finite_float(self.mechanism_data.get("cam_scale_factor"), 1.0)
        scaled_total_radius = (base_radius + eccentricity) * cam_scale_factor

        # Position handle at the right edge of the cam
        size_handle_pos = QPointF(center.x() + scaled_total_radius, center.y())

        # Constraints: min/max radius
        min_radius = self._MIN_TOTAL_RADIUS * cam_scale_factor
        max_radius = self._MAX_TOTAL_RADIUS * cam_scale_factor

        handle = ParametricHandle(
            size_handle_pos,
            f"{self.mechanism_id}_size",
            "size",
            self._on_size_moved,
            style=HandleStyle(size=14, color=QColor(255, 165, 0)),  # Orange
        )
        handle.setToolTip("Cam Size - Drag horizontally to adjust radius")
        handle.constraints = {
            "min_x": center.x() + min_radius,
            "max_x": center.x() + max_radius,
            "fixed_y": center.y(),
        }

        self.scene.addItem(handle)
        self.handles["size"] = handle

    @staticmethod
    def _contact_y(center_y: float, params: dict[str, Any], *, scale: float = 1.0) -> float:
        """Return cam contact Y in the same local convention used by cam visuals."""
        return float(center_y + cam_contact_y_from_params(params, scale=scale))

    @staticmethod
    def _follower_y_bounds(
        contact_y: float,
        *,
        unit_scale: float = 1.0,
        rod_length_multiplier: float = 1.0,
    ) -> tuple[float, float]:
        """Return scene-space Y bounds for the follower handle.

        Bounds are expressed in visual rod length, while the stored
        ``follower_rod_length`` remains the unscaled physical parameter.
        """
        multiplier = rod_length_multiplier if rod_length_multiplier > 0.0 else 1.0
        return (
            float(contact_y - 300.0 * multiplier * unit_scale),
            float(contact_y - 20.0 * multiplier * unit_scale),
        )

    def _on_size_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle cam size adjustment.

        Adjusts base_radius and eccentricity proportionally based on the
        handle's distance from the cam center.
        """
        params = self.mechanism_data.get("params", {})
        center = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )

        # Calculate new total radius from handle position
        cam_scale_factor = positive_finite_float(self.mechanism_data.get("cam_scale_factor"), 1.0)
        new_scaled_total_radius = abs(new_pos.x() - center.x())

        # Unscale to get the base values
        if cam_scale_factor > 0:
            new_total_radius = new_scaled_total_radius / cam_scale_factor
        else:
            new_total_radius = new_scaled_total_radius

        # Maintain the ratio between base_radius and eccentricity
        old_base_radius = positive_finite_float(params.get("base_radius"), 25.0)
        old_eccentricity = max(0.0, finite_float(params.get("eccentricity"), 10.0))
        old_total = old_base_radius + old_eccentricity

        if old_total > 0:
            ratio = old_base_radius / old_total
            new_base_radius = new_total_radius * ratio
            new_eccentricity = new_total_radius * (1 - ratio)
        else:
            # Default 60/40 split if no prior values
            new_base_radius = new_total_radius * 0.6
            new_eccentricity = new_total_radius * 0.4

        # Clamp to valid ranges
        new_base_radius = max(10.0, min(80.0, new_base_radius))
        new_eccentricity = max(2.0, min(50.0, new_eccentricity))

        params["base_radius"] = new_base_radius
        params["eccentricity"] = new_eccentricity
        if self._physical_grid_enabled():
            params.update(
                snap_cam_params(
                    params,
                    self._physical_grid_cell_cm(),
                    profile=self._physical_profile(),
                )
            )
            new_base_radius = positive_finite_float(params.get("base_radius"), new_base_radius)
            new_eccentricity = max(0.0, finite_float(params.get("eccentricity"), new_eccentricity))

        # Keep the visual handle attached to the clamped physical outer radius.
        if "size" in self.handles:
            clamped_scaled_total_radius = (new_base_radius + new_eccentricity) * cam_scale_factor
            size_handle = self.handles["size"]
            size_handle.setPos(QPointF(center.x() + clamped_scaled_total_radius, center.y()))
            size_handle.constraints["min_x"] = (
                center.x() + self._MIN_TOTAL_RADIUS * cam_scale_factor
            )
            size_handle.constraints["max_x"] = (
                center.x() + self._MAX_TOTAL_RADIUS * cam_scale_factor
            )
            size_handle.constraints["fixed_y"] = center.y()

        logging.debug(
            f"[CAM-EDITOR] Size adjusted: base_radius={new_base_radius:.1f}, "
            f"eccentricity={new_eccentricity:.1f}"
        )

        self._trigger_cam_update()

    def _create_follower_handle(self, params: dict[str, Any]) -> None:
        """Create handle for follower rod adjustment."""
        center = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        rod_length = positive_finite_float(params.get("follower_rod_length"), 40.0)
        rod_length_multiplier = positive_finite_float(
            self.mechanism_data.get("rod_length_multiplier"), 1.0
        )
        cam_scale_factor = positive_finite_float(self.mechanism_data.get("cam_scale_factor"), 1.0)

        # Calculate follower position using transforms if available
        if self.to_scene_coords is not None and self.to_mech_coords is not None:
            # Get center in mechanism space
            center_mech = self._to_mech(center)
            if center_mech is not None:
                # Visuals place the follower rod from the cam's max-radius contact
                # point to the follower head, with scene/mechanism Y increasing downward.
                contact_y = self._contact_y(center_mech[1], params, scale=cam_scale_factor)
                # Convert to scene
                contact_scene = self._to_scene((float(center_mech[0]), float(contact_y)))
                if contact_scene is not None:
                    unit_scale = cam_scene_unit_scale(self._to_scene)
                    scaled_rod_length = rod_length * rod_length_multiplier
                    follower_pos = cam_follower_base_scene(
                        contact_scene, scaled_rod_length, unit_scale
                    )
                    # Calculate min/max constraints in scene space
                    min_y, max_y = self._follower_y_bounds(
                        contact_scene.y(),
                        unit_scale=unit_scale,
                        rod_length_multiplier=rod_length_multiplier,
                    )

                    handle = ParametricHandle(
                        follower_pos,
                        f"{self.mechanism_id}_follower",
                        "follower",
                        self._on_follower_moved,
                        style=HandleStyle(size=12, color=QColor(100, 100, 255)),
                    )
                    handle.setToolTip("Follower Rod - Drag vertically to adjust length")
                    handle.constraints = {
                        "min_y": min_y,
                        "max_y": max_y,
                        "fixed_x": follower_pos.x(),
                    }
                    self.scene.addItem(handle)
                    self.handles["follower"] = handle
                    return

        # Fallback: use scale factors
        cam_scale_factor = positive_finite_float(self.mechanism_data.get("cam_scale_factor"), 1.0)
        rod_length_multiplier = positive_finite_float(
            self.mechanism_data.get("rod_length_multiplier"), 1.0
        )

        scaled_rod_length = rod_length * rod_length_multiplier
        scaled_contact_y = center.y() + cam_contact_y_from_params(params, scale=cam_scale_factor)

        follower_pos = QPointF(center.x(), scaled_contact_y - scaled_rod_length)

        handle = ParametricHandle(
            follower_pos,
            f"{self.mechanism_id}_follower",
            "follower",
            self._on_follower_moved,
            style=HandleStyle(size=12, color=QColor(100, 100, 255)),
        )
        handle.setToolTip("Follower Rod - Drag vertically to adjust length")
        min_y, max_y = self._follower_y_bounds(
            scaled_contact_y,
            rod_length_multiplier=rod_length_multiplier,
        )
        handle.constraints = {
            "min_y": min_y,
            "max_y": max_y,
            "fixed_x": center.x(),
        }

        self.scene.addItem(handle)
        self.handles["follower"] = handle

    def _get_cam_radius_at_angle(self, angle: float, params: dict[str, Any]) -> float:
        """Get cam radius at specific angle."""
        base_radius = positive_finite_float(params.get("base_radius"), 40.0)
        lift = max(0.0, finite_float(params.get("lift"), 20.0))
        profile_angle = math.radians(angle)
        radius = base_radius + lift * (1 + math.cos(profile_angle)) / 2
        return float(radius)

    def _on_center_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle cam center movement."""
        old_center = QPointF(
            finite_float(self.mechanism_data["params"].get("center_x"), 0.0),
            finite_float(self.mechanism_data["params"].get("center_y"), 0.0),
        )

        self.mechanism_data["params"]["center_x"] = new_pos.x()
        self.mechanism_data["params"]["center_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_center_x"] = mech[0]
            self.mechanism_data["params"]["m_center_y"] = mech[1]

        self.mechanism_data["cam_position"] = [new_pos.x(), new_pos.y()]

        if "key_points" not in self.mechanism_data:
            self.mechanism_data["key_points"] = {}
        if mech is not None:
            self.mechanism_data["key_points"]["cam_center"] = [float(mech[0]), float(mech[1])]
        else:
            self.mechanism_data["key_points"]["cam_center"] = [new_pos.x(), new_pos.y()]

        logging.debug(f"[CAM-EDITOR] Updated center to ({new_pos.x():.1f}, {new_pos.y():.1f})")

        offset = new_pos - old_center

        # Update size handle position and constraints
        if "size" in self.handles:
            size_handle = self.handles["size"]
            current_size_pos = size_handle.scenePos()
            new_size_pos = current_size_pos + offset
            size_handle.setPos(new_size_pos)
            # Update constraints to track new center
            cam_scale_factor = positive_finite_float(
                self.mechanism_data.get("cam_scale_factor"), 1.0
            )
            min_radius = self._MIN_TOTAL_RADIUS * cam_scale_factor
            max_radius = self._MAX_TOTAL_RADIUS * cam_scale_factor
            size_handle.constraints["min_x"] = new_pos.x() + min_radius
            size_handle.constraints["max_x"] = new_pos.x() + max_radius
            size_handle.constraints["fixed_y"] = new_pos.y()

        if "follower" in self.handles:
            follower_handle = self.handles["follower"]
            params = self.mechanism_data["params"]
            cam_scale_factor = positive_finite_float(
                self.mechanism_data.get("cam_scale_factor"), 1.0
            )
            rod_length_multiplier = positive_finite_float(
                self.mechanism_data.get("rod_length_multiplier"), 1.0
            )
            contact_y = new_pos.y() + cam_contact_y_from_params(params, scale=cam_scale_factor)
            min_y, max_y = self._follower_y_bounds(
                contact_y,
                rod_length_multiplier=rod_length_multiplier,
            )

            # Keep follower constraints consistent with mechanism-space transforms.
            center_mech = self._to_mech(new_pos)
            if center_mech is not None:
                mech_contact_y = self._contact_y(center_mech[1], params, scale=cam_scale_factor)
                contact_scene = self._to_scene((float(center_mech[0]), mech_contact_y))
                if contact_scene is not None:
                    unit_scale = cam_scene_unit_scale(self._to_scene)
                    min_y, max_y = self._follower_y_bounds(
                        contact_scene.y(),
                        unit_scale=unit_scale,
                        rod_length_multiplier=rod_length_multiplier,
                    )

            follower_handle.constraints["min_y"] = min_y
            follower_handle.constraints["max_y"] = max_y
            current_follower_pos = follower_handle.scenePos()
            new_follower_pos = current_follower_pos + offset
            follower_handle.setPos(new_follower_pos)
            follower_handle.constraints["fixed_x"] = new_follower_pos.x()

        # Keep profile-angle controls centered on the moved cam center.
        center_constraint = QPointF(new_pos.x(), new_pos.y())
        for angle_handle_id in ("align_max", "rise_end", "dwell_high_end", "return_end"):
            handle = self.handles.get(angle_handle_id)
            if handle is not None:
                handle.constraints["center"] = center_constraint
        self._refresh_angle_handles()

        self._trigger_cam_update()

    def _on_follower_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle follower movement."""
        center = QPointF(
            finite_float(self.mechanism_data["params"].get("center_x"), 0.0),
            finite_float(self.mechanism_data["params"].get("center_y"), 0.0),
        )

        # Prefer mechanism-space update when transforms are available.
        center_mech = self._to_mech(center)
        follower_mech = self._to_mech(new_pos)
        if center_mech is not None and follower_mech is not None:
            cam_scale_factor = positive_finite_float(
                self.mechanism_data.get("cam_scale_factor"), 1.0
            )
            contact_y = self._contact_y(
                center_mech[1], self.mechanism_data["params"], scale=cam_scale_factor
            )
            contact_scene = self._to_scene((float(center_mech[0]), contact_y))
            if contact_scene is not None:
                unit_scale = cam_scene_unit_scale(self._to_scene)
                rod_length_multiplier = positive_finite_float(
                    self.mechanism_data.get("rod_length_multiplier"), 1.0
                )
                denominator = max(1e-9, unit_scale * rod_length_multiplier)
                self.mechanism_data["params"]["follower_rod_length"] = max(
                    20.0, (contact_scene.y() - new_pos.y()) / denominator
                )
                self._trigger_cam_update()
                return

        cam_scale_factor = positive_finite_float(self.mechanism_data.get("cam_scale_factor"), 1.0)

        params = self.mechanism_data["params"]
        contact_y = center.y() + cam_contact_y_from_params(params, scale=cam_scale_factor)
        new_rod_length = max(20, contact_y - new_pos.y())

        rod_length_multiplier = positive_finite_float(
            self.mechanism_data.get("rod_length_multiplier"), 1.0
        )
        self.mechanism_data["params"]["follower_rod_length"] = (
            new_rod_length / rod_length_multiplier
        )

        self._trigger_cam_update()

    def _create_cam_angle_handles(self, center: QPointF, params: dict) -> None:
        """Create angle handles for cam profile control."""
        ui_radius = 50.0

        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(
                center.x() + ui_radius * math.cos(a),
                center.y() + ui_radius * math.sin(a),
            )

        align_max = finite_float(params.get("align_max_deg"), 90.0)
        rise_deg = finite_float(params.get("rise_deg"), 90.0)
        high_dwell_deg = finite_float(params.get("high_dwell_deg"), 60.0)
        return_deg = finite_float(params.get("return_deg"), 30.0)

        angles_abs = {
            "align_max": align_max,
            "rise_end": self._wrap_deg(align_max + rise_deg),
            "dwell_high_end": self._wrap_deg(align_max + rise_deg + high_dwell_deg),
            "return_end": self._wrap_deg(align_max + rise_deg + high_dwell_deg + return_deg),
        }

        constraints = {"center": center, "min_radius": ui_radius, "max_radius": ui_radius}

        defs = [
            ("align_max", "Align Max (orientation)", self._on_align_max_moved),
            ("rise_end", "Rise End", self._on_rise_end_moved),
            ("dwell_high_end", "High Dwell End", self._on_dwell_high_end_moved),
            ("return_end", "Return End", self._on_return_end_moved),
        ]

        for hid, tip, cb in defs:
            handle = ParametricHandle(
                pos_for_angle(angles_abs[hid]),
                f"{self.mechanism_id}_{hid}",
                hid,
                cb,
                style=HandleStyle(size=10, color=QColor(220, 120, 80)),
                constraints=constraints,
            )
            handle.setToolTip(tip)
            self.scene.addItem(handle)
            self.handles[hid] = handle

    def _wrap_deg(self, deg: float) -> float:
        """Wrap degrees to 0-360 range."""
        d = deg % 360.0
        return d + 360.0 if d < 0 else d

    def _angle_from(self, origin: QPointF, p: QPointF) -> float:
        """Calculate angle from origin to point."""
        return self._wrap_deg(math.degrees(math.atan2(p.y() - origin.y(), p.x() - origin.x())))

    def _pos_angle_diff(self, start_deg: float, end_deg: float) -> float:
        """Calculate positive angle difference."""
        d = self._wrap_deg(end_deg) - self._wrap_deg(start_deg)
        return d if d >= 0 else d + 360.0

    def _refresh_angle_handles(self) -> None:
        """Refresh positions of angle handles."""
        params = self.mechanism_data.get("params", {})
        center = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        ui_radius = 50.0

        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(
                center.x() + ui_radius * math.cos(a),
                center.y() + ui_radius * math.sin(a),
            )

        align = finite_float(params.get("align_max_deg"), 90.0)
        rise = finite_float(params.get("rise_deg"), 90.0)
        dwell = finite_float(params.get("high_dwell_deg"), 60.0)
        ret = finite_float(params.get("return_deg"), 30.0)

        targets = {
            "align_max": align,
            "rise_end": self._wrap_deg(align + rise),
            "dwell_high_end": self._wrap_deg(align + rise + dwell),
            "return_end": self._wrap_deg(align + rise + dwell + ret),
        }
        for hid, ang in targets.items():
            h = self.handles.get(hid)
            if h:
                try:
                    h.setPos(pos_for_angle(ang))
                except Exception:
                    logging.debug("Suppressed exception", exc_info=True)

    def _on_align_max_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle align max angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        params["align_max_deg"] = float(self._angle_from(c, new_pos))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_rise_end_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle rise end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        align = finite_float(params.get("align_max_deg"), 90.0)
        end = float(self._angle_from(c, new_pos))
        params["rise_deg"] = float(self._pos_angle_diff(align, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_dwell_high_end_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle dwell high end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        align = finite_float(params.get("align_max_deg"), 90.0)
        rise = finite_float(params.get("rise_deg"), 90.0)
        end = float(self._angle_from(c, new_pos))
        params["high_dwell_deg"] = float(self._pos_angle_diff(align + rise, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_return_end_moved(self, handle_id: str, new_pos: QPointF) -> None:
        """Handle return end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(
            finite_float(params.get("center_x"), 0.0),
            finite_float(params.get("center_y"), 0.0),
        )
        align = finite_float(params.get("align_max_deg"), 90.0)
        rise = finite_float(params.get("rise_deg"), 90.0)
        dwell = finite_float(params.get("high_dwell_deg"), 60.0)
        end = float(self._angle_from(c, new_pos))
        params["return_deg"] = float(self._pos_angle_diff(align + rise + dwell, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _trigger_cam_update(self) -> None:
        """Trigger cam mechanism update."""
        logging.debug("[CAM-EDITOR] Triggered update for cam mechanism")

    def _simulate_cam_follower_physics(self) -> dict[str, Any]:
        """Simulate cam-follower interaction with physics."""
        params = self.mechanism_data["params"]
        center = np.array(
            [
                finite_float(params.get("center_x"), 0.0),
                finite_float(params.get("center_y"), 0.0),
            ],
            dtype=float,
        )
        rod_length = positive_finite_float(params.get("follower_rod_length"), 40.0)
        base_radius = positive_finite_float(params.get("base_radius"), 25.0)

        angles = np.linspace(0, 360, 100)
        follower_positions = []
        cam_profiles = []

        for angle in angles:
            radius = self._get_cam_radius_at_angle(angle, params)

            if "profile_mods" in params:
                for mod_angle, mod_radius in params["profile_mods"].items():
                    if abs(angle - mod_angle) < 45:
                        weight = 1 - abs(angle - mod_angle) / 45
                        radius = radius * (1 - weight) + mod_radius * weight

            rad = math.radians(angle)
            cam_point = center + radius * np.array([np.cos(rad), np.sin(rad)])
            cam_profiles.append(cam_point.tolist())

            follower_y = center[1] - radius - rod_length
            spring_force = 0.1 * (follower_y - (center[1] - base_radius - rod_length))
            follower_y += spring_force

            follower_positions.append([center[0], follower_y])

        return {
            "type": "cam",
            "cam_profile": cam_profiles,
            "follower_path": follower_positions,
            "params": params,
        }

    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update cam mechanism."""
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value
        return self._simulate_cam_follower_physics()

    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update cam visuals."""
        pass
