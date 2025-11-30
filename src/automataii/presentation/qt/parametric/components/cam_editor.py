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

from .base_editor import HandleStyle, MechanismEditor, ParametricHandle


class CamEditor(MechanismEditor):
    """Editor for cam mechanisms with physics-based follower."""

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for cam shape and follower rod."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})

        if "cam_position" in mechanism_data:
            cam_position = mechanism_data["cam_position"]
            center = QPointF(cam_position[0], cam_position[1])
        else:
            center = QPointF(params.get("center_x", 0), params.get("center_y", 0))

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
        base_radius = float(params.get("base_radius", 25.0))
        eccentricity = float(params.get("eccentricity", 10.0))
        params["base_radius"] = base_radius
        params["eccentricity"] = eccentricity
        params.setdefault("rise_deg", 90.0)
        params.setdefault("high_dwell_deg", 60.0)
        params.setdefault("return_deg", 30.0)
        params.setdefault("align_max_deg", 90.0)

        self._create_follower_handle(params)

        try:
            self._create_cam_angle_handles(
                QPointF(params.get("center_x", 0), params.get("center_y", 0)), params
            )
        except Exception as e:
            logging.debug(f"[CAM-EDITOR] Skipped angle handles: {e}")

    def _create_follower_handle(self, params: dict):
        """Create handle for follower rod adjustment."""
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        base_radius = params.get("base_radius", 25.0)
        rod_length = params.get("follower_rod_length", 40.0)

        cam_scale_factor = self.mechanism_data.get("cam_scale_factor", 1.0)
        rod_length_multiplier = self.mechanism_data.get("rod_length_multiplier", 1.0)

        scaled_base_radius = base_radius * cam_scale_factor
        scaled_rod_length = rod_length * rod_length_multiplier

        follower_pos = QPointF(
            center.x(), center.y() - (scaled_base_radius + scaled_rod_length)
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
            "min_y": center.y() - 300,
            "max_y": center.y() - (scaled_base_radius + 20),
            "fixed_x": center.x(),
        }

        self.scene.addItem(handle)
        self.handles["follower"] = handle

    def _get_cam_radius_at_angle(self, angle: float, params: dict) -> float:
        """Get cam radius at specific angle."""
        base_radius = params.get("base_radius", 40)
        lift = params.get("lift", 20)
        profile_angle = math.radians(angle)
        radius = base_radius + lift * (1 + math.cos(profile_angle)) / 2
        return radius

    def _on_center_moved(self, handle_id: str, new_pos: QPointF):
        """Handle cam center movement."""
        old_center = QPointF(
            self.mechanism_data["params"].get("center_x", 0),
            self.mechanism_data["params"].get("center_y", 0),
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
        self.mechanism_data["key_points"]["cam_center"] = [new_pos.x(), new_pos.y()]

        logging.debug(f"[CAM-EDITOR] Updated center to ({new_pos.x():.1f}, {new_pos.y():.1f})")

        offset = new_pos - old_center

        if "follower" in self.handles:
            follower_handle = self.handles["follower"]
            follower_handle.constraints["fixed_x"] = new_pos.x()
            current_follower_pos = follower_handle.scenePos()
            new_follower_pos = current_follower_pos + offset
            follower_handle.setPos(new_follower_pos)

        self._trigger_cam_update()

    def _on_follower_moved(self, handle_id: str, new_pos: QPointF):
        """Handle follower movement."""
        center = QPointF(
            self.mechanism_data["params"]["center_x"],
            self.mechanism_data["params"]["center_y"],
        )

        base_radius = self.mechanism_data["params"].get("base_radius", 25.0)
        cam_scale_factor = self.mechanism_data.get("cam_scale_factor", 1.0)
        scaled_base_radius = base_radius * cam_scale_factor

        distance_from_center = abs(center.y() - new_pos.y())
        new_rod_length = max(20, distance_from_center - scaled_base_radius)

        rod_length_multiplier = self.mechanism_data.get("rod_length_multiplier", 1.0)
        if rod_length_multiplier > 0:
            self.mechanism_data["params"]["follower_rod_length"] = new_rod_length / rod_length_multiplier
        else:
            self.mechanism_data["params"]["follower_rod_length"] = new_rod_length

        self._trigger_cam_update()

    def _create_cam_angle_handles(self, center: QPointF, params: dict) -> None:
        """Create angle handles for cam profile control."""
        ui_radius = 50.0

        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(center.x() + ui_radius * math.cos(a), center.y() + ui_radius * math.sin(a))

        align_max = float(params.get("align_max_deg", 90.0))
        rise_deg = float(params.get("rise_deg", 90.0))
        high_dwell_deg = float(params.get("high_dwell_deg", 60.0))
        return_deg = float(params.get("return_deg", 30.0))

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
        center = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        ui_radius = 50.0

        def pos_for_angle(deg: float) -> QPointF:
            a = math.radians(deg)
            return QPointF(center.x() + ui_radius * math.cos(a), center.y() + ui_radius * math.sin(a))

        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        dwell = float(params.get("high_dwell_deg", 60.0))
        ret = float(params.get("return_deg", 30.0))

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
                    pass

    def _on_align_max_moved(self, handle_id: str, new_pos: QPointF):
        """Handle align max angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        params["align_max_deg"] = float(self._angle_from(c, new_pos))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_rise_end_moved(self, handle_id: str, new_pos: QPointF):
        """Handle rise end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        end = float(self._angle_from(c, new_pos))
        params["rise_deg"] = float(self._pos_angle_diff(align, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_dwell_high_end_moved(self, handle_id: str, new_pos: QPointF):
        """Handle dwell high end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        end = float(self._angle_from(c, new_pos))
        params["high_dwell_deg"] = float(self._pos_angle_diff(align + rise, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _on_return_end_moved(self, handle_id: str, new_pos: QPointF):
        """Handle return end angle movement."""
        params = self.mechanism_data.get("params", {})
        c = QPointF(params.get("center_x", 0), params.get("center_y", 0))
        align = float(params.get("align_max_deg", 90.0))
        rise = float(params.get("rise_deg", 90.0))
        dwell = float(params.get("high_dwell_deg", 60.0))
        end = float(self._angle_from(c, new_pos))
        params["return_deg"] = float(self._pos_angle_diff(align + rise + dwell, end))
        self._refresh_angle_handles()
        self._trigger_cam_update()

    def _trigger_cam_update(self):
        """Trigger cam mechanism update."""
        logging.debug("[CAM-EDITOR] Triggered update for cam mechanism")

    def _simulate_cam_follower_physics(self) -> dict[str, Any]:
        """Simulate cam-follower interaction with physics."""
        params = self.mechanism_data["params"]
        center = np.array([params["center_x"], params["center_y"]])
        rod_length = params["follower_rod_length"]

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
            spring_force = 0.1 * (follower_y - (center[1] - params["base_radius"] - rod_length))
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
