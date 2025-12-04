"""
Parametric editor for interactive mechanism manipulation.

This module provides the main ParametricEditor controller.
Individual mechanism editors are in parametric/components/.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QPointF, QTimer, pyqtSignal
from PyQt6.QtWidgets import QGraphicsScene

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
            handle.on_moved = lambda hid, pos, cb=original_callback, mid=mechanism_id: (
                cb(hid, pos) if cb else None,
                self._queue_update(mid),
            )

        logging.info(
            f"[PARAMETRIC-EDITOR] Created {mechanism_type} editor for {mechanism_id}"
        )

        return editor

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
                part_name = self.active_editor.original_mechanism_data.get(
                    "part_name", "unknown"
                )
            logging.info(
                f"[PARAMETRIC-EDITOR] Activated editor {mechanism_id} "
                f"(part: {part_name}, type: {editor_type})"
            )
        else:
            self.active_editor = None
            if mechanism_id:
                logging.warning(
                    f"[PARAMETRIC-EDITOR] No editor found for mechanism {mechanism_id}"
                )

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

    def update_mechanism_visuals(
        self, mechanism_id: str, simulation_data: dict[str, Any]
    ) -> None:
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
                mech_data = editor.mechanism_data
                cam_center = QPointF(
                    mech_data.get("cam_center_x", 0), mech_data.get("cam_center_y", 0)
                )
                follower_pos = QPointF(
                    mech_data.get("follower_x", 0),
                    mech_data.get("follower_y", cam_center.y() - 100),
                )

                if follower_pos.y() >= cam_center.y():
                    error_msg = (
                        "CAM mechanism physics constraint violated: "
                        "Follower must be above cam center (gravity constraint)"
                    )
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")
                    return False, error_msg

            elif isinstance(editor, FourBarEditor):
                mech_data = editor.mechanism_data
                anchor1 = QPointF(
                    mech_data.get("anchor1_x", 0), mech_data.get("anchor1_y", 0)
                )
                anchor2 = QPointF(
                    mech_data.get("anchor2_x", 200), mech_data.get("anchor2_y", 0)
                )
                joint1 = QPointF(
                    mech_data.get("joint1_x", 50), mech_data.get("joint1_y", 100)
                )
                joint2 = QPointF(
                    mech_data.get("joint2_x", 150), mech_data.get("joint2_y", 100)
                )

                ground_link = (
                    (anchor2.x() - anchor1.x()) ** 2 + (anchor2.y() - anchor1.y()) ** 2
                ) ** 0.5
                link1 = (
                    (joint1.x() - anchor1.x()) ** 2 + (joint1.y() - anchor1.y()) ** 2
                ) ** 0.5
                link2 = (
                    (joint2.x() - anchor2.x()) ** 2 + (joint2.y() - anchor2.y()) ** 2
                ) ** 0.5
                coupler = (
                    (joint2.x() - joint1.x()) ** 2 + (joint2.y() - joint1.y()) ** 2
                ) ** 0.5

                lengths = [ground_link, link1, link2, coupler]
                s = min(lengths)
                l_max = max(lengths)
                p, q = sorted(
                    [length for length in lengths if length != s and length != l_max]
                )

                if s + l_max > p + q:
                    error_msg = (
                        "4-bar linkage Grashof condition violated: "
                        "shortest + longest > sum of other two links"
                    )
                    logging.warning(f"[PHYSICS-VALIDATION] {error_msg}")

            elif isinstance(editor, GearEditor):
                pass

        logging.info(
            "[PARAMETRIC-EDITOR] Physics constraints validation completed successfully"
        )
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
