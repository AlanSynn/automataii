"""
Four-Bar Editor - Editor for 4-bar linkage mechanisms.

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


class FourBarEditor(MechanismEditor):
    """Editor for 4-bar linkage mechanisms with full vertex control."""

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for all vertices and link midpoints."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})

        p1 = QPointF(params.get("anchor1_x", 0), params.get("anchor1_y", 0))
        p2 = QPointF(params.get("anchor2_x", 100), params.get("anchor2_y", 0))

        crank_pos = self._calculate_crank_position(p1, params)
        rocker_pos = self._calculate_rocker_position(p2, params)
        coupler_pos = self._calculate_coupler_position(params)

        handle_configs = [
            ("anchor1", p1, "Fixed Pivot 1", self._on_anchor1_moved),
            ("anchor2", p2, "Fixed Pivot 2", self._on_anchor2_moved),
            ("crank", crank_pos, "Crank Joint", self._on_crank_moved),
            ("rocker", rocker_pos, "Rocker Joint", self._on_rocker_moved),
            ("coupler", coupler_pos, "Coupler Point", self._on_coupler_moved),
        ]

        for handle_id, position, tooltip, callback in handle_configs:
            constraints = self._get_handle_constraints(handle_id)
            handle = ParametricHandle(
                position,
                f"{self.mechanism_id}_{handle_id}",
                handle_id,
                callback,
                style=self._get_handle_style(handle_id),
                constraints=constraints,
            )
            handle.setToolTip(tooltip)
            self.scene.addItem(handle)
            self.handles[handle_id] = handle

        self._create_link_handles()

        try:
            for hid, h in self.handles.items():
                mech = self._to_mech(h.scenePos())
                if mech is not None:
                    self._reproject_handle(hid, mech)
        except Exception:
            pass

    def _create_link_handles(self):
        """Create handles at link midpoints for length adjustment."""
        if "anchor1" in self.handles and "crank" in self.handles:
            p1 = self.handles["anchor1"].scenePos()
            p_crank = self.handles["crank"].scenePos()
            midpoint = (p1 + p_crank) / 2
            handle = ParametricHandle(
                midpoint,
                f"{self.mechanism_id}_crank_length",
                "crank_length",
                self._on_crank_length_changed,
                style=self._get_link_handle_style(),
            )
            handle.setToolTip("Drag to adjust crank length")
            self.scene.addItem(handle)
            self.handles["crank_length"] = handle

    def _get_handle_style(self, handle_id: str) -> HandleStyle:
        """Get style for specific handle type."""
        if "anchor" in handle_id:
            return HandleStyle(
                size=14, color=QColor(100, 150, 255), hover_color=QColor(150, 200, 255)
            )
        elif handle_id == "coupler":
            return HandleStyle(
                size=10, color=QColor(255, 150, 100), hover_color=QColor(255, 200, 150)
            )
        else:
            return HandleStyle()

    def _get_link_handle_style(self) -> HandleStyle:
        """Get style for link adjustment handles."""
        return HandleStyle(
            size=8, color=QColor(150, 255, 150), hover_color=QColor(200, 255, 200), opacity=0.7
        )

    def _get_handle_constraints(self, handle_id: str) -> dict:
        """Get movement constraints for handle."""
        if handle_id in ["anchor1", "anchor2"]:
            return {}

        constraints = {"min_x": -2000, "max_x": 2000, "min_y": -2000, "max_y": 2000}

        if handle_id == "crank":
            if "anchor1" in self.handles:
                anchor_pos = self.handles["anchor1"].scenePos()
                crank_length = self.mechanism_data.get("params", {}).get("l2", 60)
                constraints["fixed_distance"] = {"anchor": anchor_pos, "distance": crank_length}
        elif handle_id == "rocker":
            if "anchor2" in self.handles:
                anchor_pos = self.handles["anchor2"].scenePos()
                rocker_length = self.mechanism_data.get("params", {}).get("l4", 70)
                constraints["fixed_distance"] = {"anchor": anchor_pos, "distance": rocker_length}

        return constraints

    def _calculate_crank_position(self, anchor1: QPointF, params: dict) -> QPointF:
        """Calculate crank joint position."""
        if "crank_x" in params and "crank_y" in params:
            return QPointF(params["crank_x"], params["crank_y"])
        angle = params.get("crank_angle", 0)
        length = params.get("l2", 60)
        x = anchor1.x() + length * math.cos(math.radians(angle))
        y = anchor1.y() + length * math.sin(math.radians(angle))
        return QPointF(x, y)

    def _calculate_rocker_position(self, anchor2: QPointF, params: dict) -> QPointF:
        """Calculate rocker joint position."""
        if "rocker_x" in params and "rocker_y" in params:
            return QPointF(params["rocker_x"], params["rocker_y"])
        angle = params.get("rocker_angle", 45)
        length = params.get("l4", 70)
        x = anchor2.x() + length * math.cos(math.radians(angle))
        y = anchor2.y() + length * math.sin(math.radians(angle))
        return QPointF(x, y)

    def _calculate_coupler_position(self, params: dict) -> QPointF:
        """Calculate coupler point position."""
        if "coupler_x" in params and "coupler_y" in params:
            return QPointF(params["coupler_x"], params["coupler_y"])
        return QPointF(params.get("coupler_point_x", 350), params.get("coupler_point_y", 250))

    def _on_anchor1_moved(self, handle_id: str, new_pos: QPointF):
        """Handle anchor1 movement."""
        old_scene = QPointF(
            self.mechanism_data["params"].get("anchor1_x", new_pos.x()),
            self.mechanism_data["params"].get("anchor1_y", new_pos.y()),
        )
        delta = new_pos - old_scene
        self._last_move_delta = delta

        self.mechanism_data["params"]["anchor1_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor1_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_anchor1_x"] = mech[0]
            self.mechanism_data["params"]["m_anchor1_y"] = mech[1]

        self._update_dependent_handles("anchor1", new_pos)
        if mech is not None:
            self._reproject_handle("anchor1", mech)
        self._trigger_mechanism_update()

    def _on_anchor2_moved(self, handle_id: str, new_pos: QPointF):
        """Handle anchor2 movement."""
        old_scene = QPointF(
            self.mechanism_data["params"].get("anchor2_x", new_pos.x()),
            self.mechanism_data["params"].get("anchor2_y", new_pos.y()),
        )
        delta = new_pos - old_scene
        self._last_move_delta = delta

        self.mechanism_data["params"]["anchor2_x"] = new_pos.x()
        self.mechanism_data["params"]["anchor2_y"] = new_pos.y()
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_anchor2_x"] = mech[0]
            self.mechanism_data["params"]["m_anchor2_y"] = mech[1]

        self._update_dependent_handles("anchor2", new_pos)
        if mech is not None:
            self._reproject_handle("anchor2", mech)
        self._trigger_mechanism_update()

    def _on_crank_moved(self, handle_id: str, new_pos: QPointF):
        """Handle crank joint movement."""
        anchor1 = self.handles["anchor1"].scenePos()
        dx = new_pos.x() - anchor1.x()
        dy = new_pos.y() - anchor1.y()

        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx * dx + dy * dy)

        self.mechanism_data["params"]["crank_angle"] = angle
        self.mechanism_data["params"]["l2"] = length

        self._update_dependent_handles("crank", new_pos)
        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_crank_x"] = mech[0]
            self.mechanism_data["params"]["m_crank_y"] = mech[1]
            self._reproject_handle("crank", mech)
        self._trigger_mechanism_update()

    def _on_rocker_moved(self, handle_id: str, new_pos: QPointF):
        """Handle rocker joint movement."""
        anchor2 = self.handles["anchor2"].scenePos()
        dx = new_pos.x() - anchor2.x()
        dy = new_pos.y() - anchor2.y()

        angle = math.degrees(math.atan2(dy, dx))
        length = math.sqrt(dx * dx + dy * dy)

        self.mechanism_data["params"]["rocker_angle"] = angle
        self.mechanism_data["params"]["l4"] = length

        mech = self._to_mech(new_pos)
        if mech is not None:
            self.mechanism_data["params"]["m_rocker_x"] = mech[0]
            self.mechanism_data["params"]["m_rocker_y"] = mech[1]
            self._reproject_handle("rocker", mech)
        self._trigger_mechanism_update()

    def _on_coupler_moved(self, handle_id: str, new_pos: QPointF):
        """Handle coupler point movement."""
        params = self.mechanism_data.get("params", {})
        params["coupler_x"] = new_pos.x()
        params["coupler_y"] = new_pos.y()

        try:
            if self.to_mech_coords and "crank" in self.handles and "rocker" in self.handles:
                p3_scene = self.handles["crank"].scenePos()
                p4_scene = self.handles["rocker"].scenePos()

                p3_mech = self._to_mech(p3_scene)
                p4_mech = self._to_mech(p4_scene)
                p_c_mech = self._to_mech(new_pos)

                if p3_mech is not None and p4_mech is not None and p_c_mech is not None:
                    v = np.array([p4_mech[0] - p3_mech[0], p4_mech[1] - p3_mech[1]], dtype=float)
                    L = float(np.hypot(v[0], v[1]))
                    if L > 1e-9:
                        u = v / L
                        n = np.array([-u[1], u[0]], dtype=float)
                        rel = np.array(
                            [p_c_mech[0] - p3_mech[0], p_c_mech[1] - p3_mech[1]], dtype=float
                        )
                        params["coupler_point_x"] = float(rel.dot(u))
                        params["coupler_point_y"] = float(rel.dot(n))
        except Exception:
            pass

        self._trigger_mechanism_update()

    def _on_crank_length_changed(self, handle_id: str, new_pos: QPointF):
        """Handle crank length adjustment."""
        anchor1 = self.handles["anchor1"].scenePos()
        crank = self.handles["crank"].scenePos()

        v = crank - anchor1
        u = new_pos - anchor1

        if v.x() != 0 or v.y() != 0:
            t = (u.x() * v.x() + u.y() * v.y()) / (v.x() * v.x() + v.y() * v.y())
            t = max(0.3, min(2.0, t))

            new_length = math.sqrt(v.x() * v.x() + v.y() * v.y()) * t
            self.mechanism_data["params"]["l2"] = new_length

            angle = math.degrees(math.atan2(v.y(), v.x()))
            new_crank_pos = QPointF(
                anchor1.x() + new_length * math.cos(math.radians(angle)),
                anchor1.y() + new_length * math.sin(math.radians(angle)),
            )

            self.handles["crank"].setPos(new_crank_pos)
            self._trigger_mechanism_update()

    def _update_dependent_handles(self, changed_handle: str, new_pos: QPointF):
        """Update handles that depend on the changed handle."""
        if self._updating:
            return

        self._updating = True
        try:
            if changed_handle in ["anchor1", "crank"] and "crank_length" in self.handles:
                p1 = self.handles["anchor1"].scenePos()
                p_crank = self.handles["crank"].scenePos()
                midpoint = (p1 + p_crank) / 2
                self.handles["crank_length"].setPos(midpoint)
        finally:
            self._updating = False

    def _trigger_mechanism_update(self):
        """Trigger mechanism simulation update."""
        if self._updating:
            return

        param_changes = {
            "anchor1_x": self.mechanism_data["params"]["anchor1_x"],
            "anchor1_y": self.mechanism_data["params"]["anchor1_y"],
            "anchor2_x": self.mechanism_data["params"]["anchor2_x"],
            "anchor2_y": self.mechanism_data["params"]["anchor2_y"],
            "l2": self.mechanism_data["params"].get("l2", 60),
            "l3": self.mechanism_data["params"].get("l3", 80),
            "l4": self.mechanism_data["params"].get("l4", 70),
        }

        self.mechanism_data["params"].update(param_changes)
        logging.debug("[4BAR-EDITOR] Updated mechanism parameters")

    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update mechanism and return new simulation data."""
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value

        simulation_data = self._simulate_4bar_motion()
        return simulation_data

    def _simulate_4bar_motion(self) -> dict[str, Any]:
        """Simulate 4-bar linkage motion."""
        params = self.mechanism_data["params"]

        p1 = np.array([params["anchor1_x"], params["anchor1_y"]])
        p2 = np.array([params["anchor2_x"], params["anchor2_y"]])
        l2 = params["l2"]
        l3 = params.get("l3", 80)
        l4 = params["l4"]

        angles = np.linspace(0, 360, 100)
        path_points = []

        for angle in angles:
            theta2 = np.radians(angle)
            p3 = p1 + l2 * np.array([np.cos(theta2), np.sin(theta2)])
            d = np.linalg.norm(p3 - p2)

            if d > l3 + l4 or d < abs(l3 - l4):
                continue

            a = (d * d + l4 * l4 - l3 * l3) / (2 * d * l4)
            a = np.clip(a, -1, 1)
            theta4_offset = np.arccos(a)

            base_angle = np.arctan2(p3[1] - p2[1], p3[0] - p2[0])
            theta4 = base_angle + theta4_offset
            p4 = p2 + l4 * np.array([np.cos(theta4), np.sin(theta4)])

            t = 0.5
            coupler = p3 * (1 - t) + p4 * t

            path_points.append(
                {"angle": angle, "crank": p3.tolist(), "rocker": p4.tolist(), "coupler": coupler.tolist()}
            )

        return {"type": "4bar", "path": path_points, "params": params}

    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update mechanism visuals based on simulation."""
        pass
