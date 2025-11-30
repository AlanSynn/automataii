"""
Gear Editors - Editors for gear and planetary gear mechanisms.

Extracted from parametric_editor.py.

Design Pattern: Concrete Strategy (mechanism-specific editing)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor

from .base_editor import HandleStyle, MechanismEditor, ParametricHandle


class GearEditor(MechanismEditor):
    """Editor for gear mechanisms with position and size control."""

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for gear position and size."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})

        # Gear 1 (driver) handles
        self._create_gear_handles(
            gear_id="gear1",
            center=QPointF(params.get("gear1_x", 0), params.get("gear1_y", 0)),
            radius=params.get("gear1_radius", 40),
            is_driver=True,
        )

        # Gear 2 (driven) handles
        self._create_gear_handles(
            gear_id="gear2",
            center=QPointF(params.get("gear2_x", 100), params.get("gear2_y", 0)),
            radius=params.get("gear2_radius", 60),
            is_driver=False,
        )

        self._create_mesh_handle()

    def _create_gear_handles(
        self, gear_id: str, center: QPointF, radius: float, is_driver: bool
    ):
        """Create handles for a single gear."""
        center_handle = ParametricHandle(
            center,
            f"{self.mechanism_id}_{gear_id}_center",
            f"{gear_id}_center",
            lambda hid, pos, gid=gear_id: self._on_gear_center_moved(gid, pos),
            style=HandleStyle(
                size=14,
                color=QColor(100, 200, 100) if is_driver else QColor(100, 100, 200),
            ),
        )
        center_handle.setToolTip(f"{gear_id.title()} Center - Drag to move")
        self.scene.addItem(center_handle)
        self.handles[f"{gear_id}_center"] = center_handle

        radius_pos = QPointF(center.x() + radius, center.y())
        radius_handle = ParametricHandle(
            radius_pos,
            f"{self.mechanism_id}_{gear_id}_radius",
            f"{gear_id}_radius",
            lambda hid, pos, gid=gear_id: self._on_gear_radius_changed(gid, pos),
            style=HandleStyle(size=10, color=QColor(255, 200, 100)),
        )
        radius_handle.setToolTip(f"{gear_id.title()} Radius - Drag to resize")
        radius_handle.constraints = {"center": center, "min_radius": 20, "max_radius": 150}

        self.scene.addItem(radius_handle)
        self.handles[f"{gear_id}_radius"] = radius_handle

    def _create_mesh_handle(self):
        """Create handle for adjusting gear meshing."""
        params = self.mechanism_data["params"]
        center1 = QPointF(params.get("gear1_x", 0), params.get("gear1_y", 0))
        center2 = QPointF(params.get("gear2_x", 100), params.get("gear2_y", 0))
        midpoint = (center1 + center2) / 2

        mesh_handle = ParametricHandle(
            midpoint,
            f"{self.mechanism_id}_mesh",
            "mesh",
            self._on_mesh_adjusted,
            style=HandleStyle(size=8, color=QColor(255, 255, 100), opacity=0.6),
        )
        mesh_handle.setToolTip("Gear Mesh - Drag to adjust spacing")

        self.scene.addItem(mesh_handle)
        self.handles["mesh"] = mesh_handle

    def _on_gear_center_moved(self, gear_id: str, new_pos: QPointF):
        """Handle gear center movement."""
        self.mechanism_data["params"][f"{gear_id}_x"] = new_pos.x()
        self.mechanism_data["params"][f"{gear_id}_y"] = new_pos.y()

        radius_handle_key = f"{gear_id}_radius"
        if radius_handle_key in self.handles:
            radius = self.mechanism_data["params"][f"{gear_id}_radius"]
            radius_handle = self.handles[radius_handle_key]
            radius_handle.setPos(
                QPointF(new_pos.x() + radius, new_pos.y())
                - QPointF(radius_handle.style.size / 2, radius_handle.style.size / 2)
            )
            radius_handle.constraints["center"] = new_pos

        self._update_mesh_handle()
        self._auto_adjust_gear_mesh()
        self._trigger_gear_update()

    def _on_gear_radius_changed(self, gear_id: str, new_pos: QPointF):
        """Handle gear radius change."""
        center = QPointF(
            self.mechanism_data["params"][f"{gear_id}_x"],
            self.mechanism_data["params"][f"{gear_id}_y"],
        )

        dx = new_pos.x() - center.x()
        dy = new_pos.y() - center.y()
        new_radius = math.sqrt(dx * dx + dy * dy)

        self.mechanism_data["params"][f"{gear_id}_radius"] = new_radius
        self._auto_adjust_gear_mesh()
        self._trigger_gear_update()

    def _on_mesh_adjusted(self, handle_id: str, new_pos: QPointF):
        """Handle mesh adjustment."""
        center1 = QPointF(
            self.mechanism_data["params"]["gear1_x"],
            self.mechanism_data["params"]["gear1_y"],
        )
        center2 = QPointF(
            self.mechanism_data["params"]["gear2_x"],
            self.mechanism_data["params"]["gear2_y"],
        )

        v = center2 - center1
        u = new_pos - center1

        if v.x() != 0 or v.y() != 0:
            t = (u.x() * v.x() + u.y() * v.y()) / (v.x() * v.x() + v.y() * v.y())
            t = max(0.3, min(0.7, t))

            new_center2 = center1 + v * (2 * t)
            self.mechanism_data["params"]["gear2_x"] = new_center2.x()
            self.mechanism_data["params"]["gear2_y"] = new_center2.y()

            if "gear2_center" in self.handles:
                handle = self.handles["gear2_center"]
                handle.setPos(
                    new_center2 - QPointF(handle.style.size / 2, handle.style.size / 2)
                )

            self._trigger_gear_update()

    def _update_mesh_handle(self):
        """Update mesh handle position."""
        if "mesh" not in self.handles:
            return

        center1 = QPointF(
            self.mechanism_data["params"]["gear1_x"],
            self.mechanism_data["params"]["gear1_y"],
        )
        center2 = QPointF(
            self.mechanism_data["params"]["gear2_x"],
            self.mechanism_data["params"]["gear2_y"],
        )

        midpoint = (center1 + center2) / 2
        handle = self.handles["mesh"]
        handle.setPos(midpoint - QPointF(handle.style.size / 2, handle.style.size / 2))

    def _auto_adjust_gear_mesh(self):
        """Automatically adjust gear positions for proper meshing."""
        params = self.mechanism_data["params"]

        center1 = np.array([params["gear1_x"], params["gear1_y"]])
        center2 = np.array([params["gear2_x"], params["gear2_y"]])
        r1 = params["gear1_radius"]
        r2 = params["gear2_radius"]

        current_distance = np.linalg.norm(center2 - center1)
        ideal_distance = r1 + r2 + 2

        if abs(current_distance - ideal_distance) > 0.1:
            direction = (
                (center2 - center1) / current_distance
                if current_distance > 0
                else np.array([1, 0])
            )
            new_center2 = center1 + direction * ideal_distance

            params["gear2_x"] = new_center2[0]
            params["gear2_y"] = new_center2[1]

            if "gear2_center" in self.handles:
                handle = self.handles["gear2_center"]
                handle.setPos(
                    QPointF(new_center2[0], new_center2[1])
                    - QPointF(handle.style.size / 2, handle.style.size / 2)
                )

    def _trigger_gear_update(self):
        """Trigger gear mechanism update."""
        simulation_data = self._simulate_gear_motion()
        self.update_visuals(simulation_data)

    def _simulate_gear_motion(self) -> dict[str, Any]:
        """Simulate gear motion."""
        params = self.mechanism_data["params"]

        r1 = params["gear1_radius"]
        r2 = params["gear2_radius"]
        gear_ratio = r2 / r1

        angles = np.linspace(0, 360, 100)
        gear1_angles = angles
        gear2_angles = -angles / gear_ratio

        return {
            "type": "gear",
            "gear1_angles": gear1_angles.tolist(),
            "gear2_angles": gear2_angles.tolist(),
            "params": params,
        }

    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update gear mechanism."""
        for key, value in param_changes.items():
            if key in self.mechanism_data["params"]:
                self.mechanism_data["params"][key] = value
        return self._simulate_gear_motion()

    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update gear visuals."""
        pass


class PlanetaryGearEditor(MechanismEditor):
    """Editor for planetary gears with basic controls."""

    def create_handles(self, mechanism_data: dict[str, Any]) -> None:
        """Create handles for planetary gear control."""
        self.mechanism_data = mechanism_data
        params = mechanism_data.get("params", {})

        cx = float(params.get("sun_x", 0.0))
        cy = float(params.get("sun_y", 0.0))
        r_sun = float(params.get("r_sun", 20.0))
        r_planet = float(params.get("r_planet", 30.0))
        arm_length = float(params.get("arm_length", 15.0))

        params["sun_x"], params["sun_y"] = cx, cy
        params["r_sun"], params["r_planet"], params["arm_length"] = r_sun, r_planet, arm_length
        center = QPointF(cx, cy)

        # Sun center handle
        sun_center = ParametricHandle(
            center,
            f"{self.mechanism_id}_sun_center",
            "sun_center",
            self._on_sun_center_moved,
            style=HandleStyle(size=14, color=QColor(200, 200, 80)),
        )
        sun_center.setToolTip("Sun Center - Drag to move")
        self.scene.addItem(sun_center)
        self.handles["sun_center"] = sun_center

        # Planet radius handle
        pr_handle = ParametricHandle(
            QPointF(cx + r_planet, cy),
            f"{self.mechanism_id}_planet_radius",
            "planet_radius",
            self._on_planet_radius_changed,
            style=HandleStyle(size=10, color=QColor(255, 200, 100)),
        )
        pr_handle.setToolTip("Planet Radius - Drag to resize")
        pr_handle.constraints = {"center": center, "min_radius": 5.0, "max_radius": 200.0}
        self.scene.addItem(pr_handle)
        self.handles["planet_radius"] = pr_handle

        # Arm length handle
        arm_pos = QPointF(cx + r_sun + r_planet + arm_length, cy)
        arm_handle = ParametricHandle(
            arm_pos,
            f"{self.mechanism_id}_arm_length",
            "arm_length",
            self._on_arm_length_changed,
            style=HandleStyle(size=8, color=QColor(255, 255, 100)),
        )
        arm_handle.setToolTip("Arm Length - Drag radially to adjust")
        arm_handle.constraints = {
            "center": QPointF(cx + r_sun + r_planet, cy),
            "min_radius": 0.0,
            "max_radius": 300.0,
        }
        self.scene.addItem(arm_handle)
        self.handles["arm_length"] = arm_handle

    def _on_sun_center_moved(self, handle_id: str, new_pos: QPointF):
        """Handle sun center movement."""
        self.mechanism_data["params"]["sun_x"] = float(new_pos.x())
        self.mechanism_data["params"]["sun_y"] = float(new_pos.y())

        if "planet_radius" in self.handles:
            self.handles["planet_radius"].constraints["center"] = new_pos
        if "arm_length" in self.handles:
            r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
            r_planet = float(self.mechanism_data["params"].get("r_planet", 30.0))
            self.handles["arm_length"].constraints["center"] = QPointF(
                new_pos.x() + r_sun + r_planet, new_pos.y()
            )
        self._trigger_update()

    def _on_planet_radius_changed(self, handle_id: str, new_pos: QPointF):
        """Handle planet radius change."""
        c = QPointF(
            self.mechanism_data["params"].get("sun_x", 0.0),
            self.mechanism_data["params"].get("sun_y", 0.0),
        )
        dx, dy = new_pos.x() - c.x(), new_pos.y() - c.y()
        r = (dx * dx + dy * dy) ** 0.5
        self.mechanism_data["params"]["r_planet"] = float(max(1.0, r))

        if "arm_length" in self.handles:
            r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
            self.handles["arm_length"].constraints["center"] = QPointF(c.x() + r_sun + r, c.y())
        self._trigger_update()

    def _on_arm_length_changed(self, handle_id: str, new_pos: QPointF):
        """Handle arm length change."""
        c = QPointF(
            self.mechanism_data["params"].get("sun_x", 0.0),
            self.mechanism_data["params"].get("sun_y", 0.0),
        )
        r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
        r_planet = float(self.mechanism_data["params"].get("r_planet", 30.0))
        arm_center = QPointF(c.x() + r_sun + r_planet, c.y())
        dx, dy = new_pos.x() - arm_center.x(), new_pos.y() - arm_center.y()
        arm_len = max(0.0, (dx * dx + dy * dy) ** 0.5)
        self.mechanism_data["params"]["arm_length"] = float(arm_len)
        self._trigger_update()

    def _trigger_update(self):
        """Trigger update (no local simulation)."""
        pass

    def update_mechanism(self, param_changes: dict[str, Any]) -> dict[str, Any]:
        """Update planetary gear mechanism."""
        for k, v in param_changes.items():
            if k in self.mechanism_data.get("params", {}):
                self.mechanism_data["params"][k] = v
        return {"type": "planetary_gear", "params": self.mechanism_data.get("params", {})}

    def update_visuals(self, simulation_data: dict[str, Any]) -> None:
        """Update planetary gear visuals."""
        pass
