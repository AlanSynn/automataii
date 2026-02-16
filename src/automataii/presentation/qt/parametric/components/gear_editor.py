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
        key_points = mechanism_data.get("key_points", {})

        # Normalize aliases used across Foundry/Design/editor code paths.
        params.setdefault("gear1_radius", float(params.get("r1", 40.0)))
        params.setdefault("gear2_radius", float(params.get("r2", 60.0)))
        params["r1"] = float(params["gear1_radius"])
        params["r2"] = float(params["gear2_radius"])

        if "gear1_x" not in params or "gear1_y" not in params:
            g1 = key_points.get("gear1_center")
            if isinstance(g1, list | tuple) and len(g1) >= 2:
                scene = self._to_scene((float(g1[0]), float(g1[1])))
                if scene is not None:
                    params["gear1_x"] = float(scene.x())
                    params["gear1_y"] = float(scene.y())
                else:
                    params["gear1_x"] = float(g1[0])
                    params["gear1_y"] = float(g1[1])
        if "gear2_x" not in params or "gear2_y" not in params:
            g2 = key_points.get("gear2_center")
            if isinstance(g2, list | tuple) and len(g2) >= 2:
                scene = self._to_scene((float(g2[0]), float(g2[1])))
                if scene is not None:
                    params["gear2_x"] = float(scene.x())
                    params["gear2_y"] = float(scene.y())
                else:
                    params["gear2_x"] = float(g2[0])
                    params["gear2_y"] = float(g2[1])

        params.setdefault("gear1_x", 0.0)
        params.setdefault("gear1_y", 0.0)
        params.setdefault("gear2_x", 100.0)
        params.setdefault("gear2_y", 0.0)

        # Gear 1 (driver) handles
        self._create_gear_handles(
            gear_id="gear1",
            center=QPointF(params.get("gear1_x", 0), params.get("gear1_y", 0)),
            radius=params.get("gear1_radius", params.get("r1", 40)),
            is_driver=True,
        )

        # Gear 2 (driven) handles
        self._create_gear_handles(
            gear_id="gear2",
            center=QPointF(params.get("gear2_x", 100), params.get("gear2_y", 0)),
            radius=params.get("gear2_radius", params.get("r2", 60)),
            is_driver=False,
        )

        self._create_mesh_handle()
        self._sync_gear_handle_positions()

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
        self._update_gear_key_point(gear_id, new_pos)
        self._auto_adjust_gear_mesh()
        self._sync_gear_handle_positions()
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
        self.mechanism_data["params"]["r1" if gear_id == "gear1" else "r2"] = new_radius
        self._auto_adjust_gear_mesh()
        self._sync_gear_handle_positions()
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
            self._update_gear_key_point("gear2", new_center2)
            self._auto_adjust_gear_mesh()
            self._sync_gear_handle_positions()
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
        handle.setPos(midpoint)

    def _update_gear_key_point(self, gear_id: str, center_scene: QPointF) -> None:
        """Persist center point with mechanism-space preference when available."""
        mech = self._to_mech(center_scene)
        if mech is not None:
            self.mechanism_data.setdefault("key_points", {})[f"{gear_id}_center"] = [
                float(mech[0]),
                float(mech[1]),
            ]
        else:
            self.mechanism_data.setdefault("key_points", {})[f"{gear_id}_center"] = [
                float(center_scene.x()),
                float(center_scene.y()),
            ]

    def _sync_gear_handle_positions(self) -> None:
        """Keep all center/radius/mesh handles aligned with current params."""
        params = self.mechanism_data.get("params", {})
        for gear_id in ("gear1", "gear2"):
            cx = float(params.get(f"{gear_id}_x", 0.0))
            cy = float(params.get(f"{gear_id}_y", 0.0))
            radius = float(params.get(f"{gear_id}_radius", 40.0))
            center = QPointF(cx, cy)

            center_handle = self.handles.get(f"{gear_id}_center")
            if center_handle is not None:
                center_handle.setPos(center)

            radius_handle = self.handles.get(f"{gear_id}_radius")
            if radius_handle is not None:
                radius_handle.setPos(QPointF(cx + radius, cy))
                radius_handle.constraints["center"] = center

        self._update_mesh_handle()

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
            self._update_gear_key_point(
                "gear2", QPointF(float(new_center2[0]), float(new_center2[1]))
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
        key_points = mechanism_data.get("key_points", {})

        center = self._extract_initial_sun_center(params, key_points)
        r_sun = float(params.get("r_sun", params.get("gear1_radius", 20.0)))
        r_planet = float(params.get("r_planet", params.get("gear2_radius", 30.0)))
        arm_length = float(params.get("arm_length", params.get("carrier_length", 15.0)))

        params["sun_x"], params["sun_y"] = float(center.x()), float(center.y())
        params["r_sun"], params["r_planet"], params["arm_length"] = (
            float(r_sun),
            float(max(1.0, r_planet)),
            float(max(0.0, arm_length)),
        )
        params["gear1_radius"] = float(params["r_sun"])
        params["gear2_radius"] = float(params["r_planet"])

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
            center,
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
        arm_handle = ParametricHandle(
            center,
            f"{self.mechanism_id}_arm_length",
            "arm_length",
            self._on_arm_length_changed,
            style=HandleStyle(size=8, color=QColor(255, 255, 100)),
        )
        arm_handle.setToolTip("Arm Length - Drag radially to adjust")
        arm_handle.constraints = {
            "center": center,
            "min_radius": 0.0,
            "max_radius": 300.0,
        }
        self.scene.addItem(arm_handle)
        self.handles["arm_length"] = arm_handle
        self._sync_planetary_key_points_and_aliases()
        self._sync_handle_positions()

    def _extract_initial_sun_center(
        self,
        params: dict[str, Any],
        key_points: dict[str, Any],
    ) -> QPointF:
        """Resolve initial sun center in scene coordinates."""
        if "sun_x" in params and "sun_y" in params:
            return QPointF(float(params.get("sun_x", 0.0)), float(params.get("sun_y", 0.0)))
        if "gear1_x" in params and "gear1_y" in params:
            return QPointF(float(params.get("gear1_x", 0.0)), float(params.get("gear1_y", 0.0)))

        kp = key_points.get("sun_center")
        if isinstance(kp, (list, tuple)) and len(kp) >= 2:
            scene = self._to_scene((float(kp[0]), float(kp[1])))
            if scene is not None:
                return scene
            return QPointF(float(kp[0]), float(kp[1]))

        return QPointF(0.0, 0.0)

    def _scene_length_from_mech(
        self,
        center_scene: QPointF,
        mech_length: float,
    ) -> float:
        """Convert a mechanism-space length to scene-space around a center point."""
        if mech_length <= 0:
            return 0.0
        center_mech = self._to_mech(center_scene)
        if center_mech is not None:
            edge_scene = self._to_scene((center_mech[0] + mech_length, center_mech[1]))
            if edge_scene is not None:
                return float(
                    math.hypot(
                        edge_scene.x() - center_scene.x(),
                        edge_scene.y() - center_scene.y(),
                    )
                )
        return float(mech_length)

    def _sync_planetary_key_points_and_aliases(self) -> None:
        """Keep compatibility aliases and key points synchronized with params."""
        params = self.mechanism_data.setdefault("params", {})
        key_points = self.mechanism_data.setdefault("key_points", {})

        center_scene = QPointF(
            float(params.get("sun_x", 0.0)),
            float(params.get("sun_y", 0.0)),
        )
        center_mech = self._to_mech(center_scene)
        if center_mech is None:
            center_mech = (float(center_scene.x()), float(center_scene.y()))

        r_sun = float(params.get("r_sun", params.get("gear1_radius", 20.0)))
        r_planet = float(max(1.0, params.get("r_planet", params.get("gear2_radius", 30.0))))
        arm_length = float(max(0.0, params.get("arm_length", 15.0)))

        params["sun_x"] = float(center_scene.x())
        params["sun_y"] = float(center_scene.y())
        params["gear1_x"] = float(center_scene.x())
        params["gear1_y"] = float(center_scene.y())
        params["r_sun"] = float(r_sun)
        params["r_planet"] = float(r_planet)
        params["arm_length"] = float(arm_length)
        params["gear1_radius"] = float(r_sun)
        params["gear2_radius"] = float(r_planet)
        params["sun_radius"] = float(r_sun)
        params["planet_radius"] = float(r_planet)
        params["m_sun_x"] = float(center_mech[0])
        params["m_sun_y"] = float(center_mech[1])

        planet_mech = np.array([center_mech[0] + r_sun + r_planet, center_mech[1]], dtype=float)
        tracking_mech = np.array([planet_mech[0] + arm_length, planet_mech[1]], dtype=float)
        key_points["sun_center"] = [float(center_mech[0]), float(center_mech[1])]
        key_points["planet_center"] = [float(planet_mech[0]), float(planet_mech[1])]
        key_points["tracking_point"] = [float(tracking_mech[0]), float(tracking_mech[1])]

        planet_scene = self._to_scene((float(planet_mech[0]), float(planet_mech[1])))
        if planet_scene is None:
            planet_scene = QPointF(float(planet_mech[0]), float(planet_mech[1]))
        params["planet_x"] = float(planet_scene.x())
        params["planet_y"] = float(planet_scene.y())
        params["gear2_x"] = float(planet_scene.x())
        params["gear2_y"] = float(planet_scene.y())

    def _sync_handle_positions(self) -> None:
        """Update planetary handle positions/constraints from current parameters."""
        params = self.mechanism_data.get("params", {})
        center_scene = QPointF(
            float(params.get("sun_x", 0.0)),
            float(params.get("sun_y", 0.0)),
        )
        center_mech = self._to_mech(center_scene)
        if center_mech is None:
            center_mech = (float(center_scene.x()), float(center_scene.y()))

        r_sun = float(params.get("r_sun", 20.0))
        r_planet = float(params.get("r_planet", 30.0))
        arm_length = float(params.get("arm_length", 15.0))

        planet_radius_scene = self._to_scene((center_mech[0] + r_planet, center_mech[1]))
        if planet_radius_scene is None:
            planet_radius_scene = QPointF(center_scene.x() + r_planet, center_scene.y())

        arm_center_scene = self._to_scene((center_mech[0] + r_sun + r_planet, center_mech[1]))
        if arm_center_scene is None:
            arm_center_scene = QPointF(center_scene.x() + r_sun + r_planet, center_scene.y())

        arm_handle_scene = self._to_scene(
            (center_mech[0] + r_sun + r_planet + arm_length, center_mech[1])
        )
        if arm_handle_scene is None:
            arm_handle_scene = QPointF(arm_center_scene.x() + arm_length, arm_center_scene.y())

        if "sun_center" in self.handles:
            self.handles["sun_center"].setPos(center_scene)

        if "planet_radius" in self.handles:
            handle = self.handles["planet_radius"]
            handle.setPos(planet_radius_scene)
            handle.constraints["center"] = center_scene
            handle.constraints["min_radius"] = self._scene_length_from_mech(center_scene, 5.0)
            handle.constraints["max_radius"] = self._scene_length_from_mech(center_scene, 200.0)

        if "arm_length" in self.handles:
            handle = self.handles["arm_length"]
            handle.setPos(arm_handle_scene)
            handle.constraints["center"] = arm_center_scene
            handle.constraints["min_radius"] = self._scene_length_from_mech(arm_center_scene, 0.0)
            handle.constraints["max_radius"] = self._scene_length_from_mech(arm_center_scene, 300.0)

    def _on_sun_center_moved(self, handle_id: str, new_pos: QPointF):
        """Handle sun center movement."""
        self.mechanism_data["params"]["sun_x"] = float(new_pos.x())
        self.mechanism_data["params"]["sun_y"] = float(new_pos.y())
        self._sync_planetary_key_points_and_aliases()
        self._sync_handle_positions()
        self._trigger_update()

    def _on_planet_radius_changed(self, handle_id: str, new_pos: QPointF):
        """Handle planet radius change."""
        c = QPointF(
            float(self.mechanism_data["params"].get("sun_x", 0.0)),
            float(self.mechanism_data["params"].get("sun_y", 0.0)),
        )
        c_mech = self._to_mech(c)
        p_mech = self._to_mech(new_pos)
        if c_mech is not None and p_mech is not None:
            r = float(math.hypot(p_mech[0] - c_mech[0], p_mech[1] - c_mech[1]))
        else:
            r = float(math.hypot(new_pos.x() - c.x(), new_pos.y() - c.y()))
        self.mechanism_data["params"]["r_planet"] = float(max(1.0, r))

        self._sync_planetary_key_points_and_aliases()
        self._sync_handle_positions()
        self._trigger_update()

    def _on_arm_length_changed(self, handle_id: str, new_pos: QPointF):
        """Handle arm length change."""
        c = QPointF(
            float(self.mechanism_data["params"].get("sun_x", 0.0)),
            float(self.mechanism_data["params"].get("sun_y", 0.0)),
        )
        r_sun = float(self.mechanism_data["params"].get("r_sun", 20.0))
        r_planet = float(self.mechanism_data["params"].get("r_planet", 30.0))
        c_mech = self._to_mech(c)

        arm_center = QPointF(c.x() + r_sun + r_planet, c.y())
        arm_center_mech = None
        if c_mech is not None:
            arm_center = self._to_scene((c_mech[0] + r_sun + r_planet, c_mech[1])) or arm_center
            arm_center_mech = (c_mech[0] + r_sun + r_planet, c_mech[1])

        new_mech = self._to_mech(new_pos)
        if arm_center_mech is not None and new_mech is not None:
            arm_len = max(
                0.0,
                float(math.hypot(new_mech[0] - arm_center_mech[0], new_mech[1] - arm_center_mech[1])),
            )
        else:
            arm_len = max(0.0, float(math.hypot(new_pos.x() - arm_center.x(), new_pos.y() - arm_center.y())))
        self.mechanism_data["params"]["arm_length"] = float(arm_len)
        self._sync_planetary_key_points_and_aliases()
        self._sync_handle_positions()
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
