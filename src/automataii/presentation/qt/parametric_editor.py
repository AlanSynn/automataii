"""
Parametric editor for interactive mechanism manipulation.

This module provides the main ParametricEditor controller.
Individual mechanism editors are in parametric/components/.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene

from automataii.presentation.qt.mechanism_parameter_utils import finite_float

# Import from extracted components
from automataii.presentation.qt.parametric.components import (
    CamEditor,
    FourBarEditor,
    GearEditor,
    HandleStyle,
    MechanismEditor,
    ParametricHandle,
    PlanetaryGearEditor,
)

# Re-export for backwards compatibility
__all__ = [
    "HandleStyle",
    "ParametricHandle",
    "MechanismEditor",
    "FourBarEditor",
    "CamEditor",
    "GearEditor",
    "PlanetaryGearEditor",
    "ParametricEditor",
]


def _point_from_editor_handle_or_params(
    editor: MechanismEditor,
    params: dict[str, Any],
    handle_name: str,
    x_key: str,
    y_key: str,
    default: QPointF,
) -> QPointF:
    """Read the live handle point when available, otherwise fall back to params."""
    handle = editor.handles.get(handle_name)
    if handle is not None:
        position = handle.scenePos()
        return QPointF(float(position.x()), float(position.y()))
    return QPointF(
        finite_float(params.get(x_key), default.x()),
        finite_float(params.get(y_key), default.y()),
    )


class ParametricEditor(QObject):
    """Main parametric editor controller."""

    mechanism_updated = pyqtSignal(str, dict)  # mechanism_id, params
    visual_refresh_requested = pyqtSignal(str)  # mechanism_id

    def __init__(self, scene: QGraphicsScene):
        """
        Initialize parametric editor.

        Args:
            scene: Graphics scene for handles
        """
        super().__init__()
        self.scene = scene
        self.editors: dict[str, MechanismEditor] = {}
        self.active_editor: MechanismEditor | None = None
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._process_updates)
        self._update_timer.setInterval(16)  # ~60 FPS
        self._pending_updates: set[str] = set()

    def create_editor(
        self,
        mechanism_id: str,
        mechanism_data: dict[str, Any],
        to_scene_coords: Callable | None = None,
        to_mech_coords: Callable | None = None,
    ) -> MechanismEditor | None:
        """
        Create appropriate editor for mechanism type.

        Args:
            mechanism_id: Unique mechanism identifier
            mechanism_data: Mechanism configuration data
            to_scene_coords: Optional transform function from mechanism to scene coordinates
            to_mech_coords: Optional transform function from scene to mechanism coordinates

        Returns:
            Created mechanism editor or None
        """
        mechanism_type = mechanism_data.get("type")

        if mechanism_id in self.editors:
            self.remove_editor(mechanism_id)

        editor: MechanismEditor | None = None
        if mechanism_type == "4_bar_linkage":
            editor = FourBarEditor(mechanism_id, self.scene)
        elif mechanism_type == "cam":
            editor = CamEditor(mechanism_id, self.scene)
        elif mechanism_type in ["gear", "simple_gear"]:
            editor = GearEditor(mechanism_id, self.scene)
        elif mechanism_type == "planetary_gear":
            editor = PlanetaryGearEditor(mechanism_id, self.scene)
        else:
            logging.warning(f"Unknown mechanism type: {mechanism_type}")
            return None

        # Set coordinate transforms BEFORE creating handles so reprojection works
        editor.to_scene_coords = to_scene_coords
        editor.to_mech_coords = to_mech_coords

        editor.create_handles(mechanism_data)
        editor.original_mechanism_data = mechanism_data
        self.editors[mechanism_id] = editor

        # Connect update callback
        for handle in editor.handles.values():
            original_callback = handle.on_moved
            handle.on_moved = self._wrap_handle_callback(
                original_callback,
                mechanism_id,
            )

        logging.info(f"[PARAMETRIC-EDITOR] Created {mechanism_type} editor for {mechanism_id}")

        return editor

    def _wrap_handle_callback(
        self,
        callback: Callable[[str, QPointF], None] | None,
        mechanism_id: str,
    ) -> Callable[[str, QPointF], None]:
        """Wrap a handle callback so GUI drags always queue a mechanism update."""

        def wrapped(handle_id: str, position: QPointF) -> None:
            try:
                if callback is not None:
                    callback(handle_id, position)
            finally:
                self._queue_update(mechanism_id)

        return wrapped

    def remove_editor(self, mechanism_id: str) -> None:
        """Remove editor and its handles."""
        if mechanism_id in self.editors:
            editor = self.editors[mechanism_id]
            editor.remove_handles()
            del self.editors[mechanism_id]

            if self.active_editor == editor:
                self.active_editor = None

    def set_active_editor(self, mechanism_id: str | None) -> None:
        """Set the active editor for the selected mechanism."""
        logging.info(f"[PARAMETRIC-EDITOR] Setting active editor to: {mechanism_id}")
        logging.info(f"[PARAMETRIC-EDITOR] Available editors: {list(self.editors.keys())}")

        for editor_id, editor in self.editors.items():
            editor.set_handles_visible(False)
            logging.debug(f"[PARAMETRIC-EDITOR] Hidden editor {editor_id}")

        if mechanism_id and mechanism_id in self.editors:
            self.active_editor = self.editors[mechanism_id]
            self.active_editor.set_handles_visible(True)
            editor_type = self.active_editor.__class__.__name__
            part_name = "unknown"
            if hasattr(self.active_editor, "original_mechanism_data"):
                part_name = self.active_editor.original_mechanism_data.get("part_name", "unknown")
            logging.info(
                f"[PARAMETRIC-EDITOR] Activated editor {mechanism_id} "
                f"(part: {part_name}, type: {editor_type})"
            )
        else:
            self.active_editor = None
            if mechanism_id:
                logging.warning(f"[PARAMETRIC-EDITOR] No editor found for mechanism {mechanism_id}")

    def _queue_update(self, mechanism_id: str) -> None:
        """Queue mechanism update for batching."""
        self._pending_updates.add(mechanism_id)
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _process_updates(self) -> None:
        """Process pending mechanism updates."""
        if not self._pending_updates:
            self._update_timer.stop()
            return

        for mechanism_id in self._pending_updates:
            if mechanism_id in self.editors:
                editor = self.editors[mechanism_id]
                params = editor.get_current_parameters()
                self.mechanism_updated.emit(mechanism_id, params)

        self._pending_updates.clear()

    def update_mechanism_visuals(self, mechanism_id: str, simulation_data: dict[str, Any]) -> None:
        """Update visuals for a mechanism."""
        if mechanism_id in self.editors:
            self.editors[mechanism_id].update_visuals(simulation_data)

    def enable_editing(self) -> None:
        """Enable parametric editing mode."""
        logging.info("[PARAMETRIC-EDITOR] Editing mode enabled")
        if self.active_editor:
            self.active_editor.set_handles_visible(True)

    def validate_physics_constraints(self) -> tuple[bool, str]:
        """
        Validate physics constraints for all active mechanisms.

        Returns:
            tuple: (is_valid, error_message)
        """
        logging.info("[PARAMETRIC-EDITOR] Validating physics constraints...")

        for _mech_id, editor in self.editors.items():
            if isinstance(editor, CamEditor):
                params = editor.mechanism_data.get("params", {})
                center_handle = editor.handles.get("center")
                cam_center = (
                    center_handle.scenePos()
                    if center_handle is not None
                    else QPointF(
                        finite_float(
                            params.get("center_x", params.get("cam_center_x")),
                            0.0,
                        ),
                        finite_float(
                            params.get("center_y", params.get("cam_center_y")),
                            0.0,
                        ),
                    )
                )
                follower_handle = editor.handles.get("follower")
                follower_pos = (
                    follower_handle.scenePos()
                    if follower_handle is not None
                    else QPointF(
                        finite_float(params.get("follower_x"), cam_center.x()),
                        finite_float(params.get("follower_y"), cam_center.y() - 100.0),
                    )
                )

                if follower_pos.y() >= cam_center.y():
                    error_msg = (
                        "CAM mechanism physics constraint violated: "
                        "Follower must be above cam center (gravity constraint)"
                    )
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")
                    return False, error_msg

            elif isinstance(editor, FourBarEditor):
                params = editor.mechanism_data.get("params", {})

                anchor1 = _point_from_editor_handle_or_params(
                    editor, params, "anchor1", "anchor1_x", "anchor1_y", QPointF(0.0, 0.0)
                )
                anchor2 = _point_from_editor_handle_or_params(
                    editor, params, "anchor2", "anchor2_x", "anchor2_y", QPointF(200.0, 0.0)
                )
                joint1 = _point_from_editor_handle_or_params(
                    editor, params, "crank", "crank_x", "crank_y", QPointF(50.0, 100.0)
                )
                joint2 = _point_from_editor_handle_or_params(
                    editor, params, "rocker", "rocker_x", "rocker_y", QPointF(150.0, 100.0)
                )

                ground_link = math.hypot(anchor2.x() - anchor1.x(), anchor2.y() - anchor1.y())
                link1 = math.hypot(joint1.x() - anchor1.x(), joint1.y() - anchor1.y())
                link2 = math.hypot(joint2.x() - anchor2.x(), joint2.y() - anchor2.y())
                coupler = math.hypot(joint2.x() - joint1.x(), joint2.y() - joint1.y())

                lengths = (ground_link, link1, link2, coupler)
                if not all(math.isfinite(length) and length > 1e-9 for length in lengths):
                    error_msg = "4-bar linkage geometry invalid: link lengths must be positive"
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")
                    return False, error_msg

            elif isinstance(editor, GearEditor):
                pass

        logging.info("[PARAMETRIC-EDITOR] Physics constraints validation completed successfully")
        return True, ""

    def disable_editing(self) -> None:
        """Disable parametric editing mode and validate physics constraints."""
        logging.info("[PARAMETRIC-EDITOR] Editing mode disabled")

        is_valid, error_msg = self.validate_physics_constraints()
        if not is_valid:
            logging.warning(f"[PARAMETRIC-EDITOR] Physics validation failed: {error_msg}")

        for editor in self.editors.values():
            editor.set_handles_visible(False)

        if self._update_timer.isActive():
            self._update_timer.stop()
            self._process_updates()
