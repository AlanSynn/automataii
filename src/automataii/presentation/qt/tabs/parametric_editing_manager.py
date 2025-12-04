"""
Parametric Editing Manager for Mechanism Design Tab

This module provides the main facade for parametric editing functionality.
It delegates to specialized components for different responsibilities:
- ParameterMapper: Parameter setup and coordinate transformation
- PhysicsSnapper: Physics constraint enforcement
- SimulationRegenerator: Mechanism simulation regeneration
- VisualUpdater: Real-time visual updates
- AnimationCoordinator: Animation control coordination

The manager maintains the same public API while internally composing
these specialized components.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSlot

from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.tabs.parametric.components import (
    AnimationCoordinator,
    ParameterMapper,
    VisualUpdater,
)

if TYPE_CHECKING:
    pass


class ParametricEditingManager:
    """
    Manages parametric editing functionality for mechanism design.

    This class is a facade that coordinates specialized components
    for different aspects of parametric editing:
    - Parameter mapping and coordinate transformation
    - Physics constraint enforcement
    - Simulation regeneration
    - Visual updates
    - Animation coordination

    Public API:
    - toggle_parametric_mode(enabled): Toggle parametric editing on/off
    - set_physics_snap_mode(mode): Set physics snapping behavior
    - is_parametric_mode_enabled(): Check if parametric mode is active
    - cleanup(): Clean up resources
    """

    def __init__(self, parent_tab) -> None:
        """
        Initialize the parametric editing manager.

        Args:
            parent_tab: Reference to MechanismDesignTab instance for accessing
                       shared resources like mechanism_layers, mechanism_scene, etc.
        """
        self.parent_tab = parent_tab
        logging.info(f"[PARAMETRIC-INIT] ParametricEditingManager created with parent_tab_id={id(parent_tab)}")
        self.parametric_mode_enabled = False
        self.physics_snap_mode = "balanced"

        # Initialize components
        self._parameter_mapper = ParameterMapper()
        self._animation_coordinator = AnimationCoordinator()
        self._visual_updater = VisualUpdater()

        # Logger
        self._logger = logging.getLogger(__name__)

    def _initialize_parametric_system(self) -> None:
        """Initialize the parametric editing system."""
        try:
            import sys

            parent_module = sys.modules[self.parent_tab.__class__.__module__]
            PARAMETRIC_AVAILABLE = getattr(parent_module, "PARAMETRIC_AVAILABLE", False)
            if not PARAMETRIC_AVAILABLE:
                return
        except Exception:
            return

        try:
            ParametricEditor = getattr(parent_module, "ParametricEditor", None)
            if not ParametricEditor:
                return

            has_scene = hasattr(self.parent_tab, "mechanism_scene")
            scene_exists = has_scene and self.parent_tab.mechanism_scene is not None

            if scene_exists:
                self.parent_tab.parametric_editor = ParametricEditor(
                    self.parent_tab.mechanism_scene
                )

                if hasattr(self.parent_tab.parametric_editor, "mechanism_updated"):
                    self.parent_tab.parametric_editor.mechanism_updated.connect(
                        self.parent_tab._on_parametric_mechanism_update
                    )

                if hasattr(
                    self.parent_tab.parametric_editor, "visual_refresh_requested"
                ):
                    self.parent_tab.parametric_editor.visual_refresh_requested.connect(
                        self.parent_tab._on_parametric_visual_refresh
                    )

                # Configure visual updater with scene
                self._visual_updater.set_scene(self.parent_tab.mechanism_scene)
                if hasattr(self.parent_tab, "mechanism_view"):
                    self._visual_updater.set_view(self.parent_tab.mechanism_view)
                if hasattr(self.parent_tab, "visuals_factory"):
                    self._visual_updater.set_visuals_factory(
                        self.parent_tab.visuals_factory
                    )

        except Exception:
            self.parent_tab.parametric_editor = None

    def _check_parametric_availability(self) -> bool:
        """Check if parametric functionality is available in parent module."""
        try:
            import sys
            parent_module = sys.modules[self.parent_tab.__class__.__module__]
            return getattr(parent_module, "PARAMETRIC_AVAILABLE", False)
        except Exception as e:
            self._logger.error("Error checking parametric availability: %s", e)
            return False

    def _ensure_parametric_editor_initialized(self) -> bool:
        """Ensure parametric editor is initialized, return success status."""
        if self.parent_tab.parametric_editor:
            return True

        try:
            self._initialize_parametric_system()
        except Exception as e:
            self._logger.error("Lazy init failed: %s", e)

        if not self.parent_tab.parametric_editor:
            self._logger.warning("No parametric editor available after init")
            self._show_info_message("Parametric Edit", "Parametric system not available.")
            return False
        return True

    def _show_info_message(self, title: str, message: str) -> None:
        """Show information message dialog."""
        try:
            from PyQt6.QtWidgets import QMessageBox
            parent = getattr(self.parent_tab, "main_window", self.parent_tab)
            QMessageBox.information(parent, title, message)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _manage_animation_state_on_enable(self) -> None:
        """Handle animation state when enabling parametric mode."""
        animation_was_running = self.parent_tab._is_animation_running()
        if animation_was_running:
            self.parent_tab._on_stop_animation()
        if not hasattr(self, "_animation_state_before_parametric"):
            self._animation_state_before_parametric = animation_was_running

    def _manage_animation_state_on_disable(self) -> bool:
        """Handle animation state when disabling parametric mode. Returns should_restore."""
        should_restore = getattr(self, "_animation_state_before_parametric", False)
        if hasattr(self, "_animation_state_before_parametric"):
            delattr(self, "_animation_state_before_parametric")
        return should_restore

    def toggle_parametric_mode(self, enabled: bool | None = None) -> None:
        """
        Toggle parametric editing mode on/off.

        Args:
            enabled: Explicit enable/disable, or None to toggle current state
        """
        self._logger.debug(
            "ParametricEditingManager: toggle_parametric_mode called with enabled=%s", enabled
        )

        if not self._check_parametric_availability():
            self._logger.warning("Parametric functionality not available")
            return

        self._logger.debug(
            "parametric_editor exists: %s", self.parent_tab.parametric_editor is not None
        )
        if not self._ensure_parametric_editor_initialized():
            return

        if enabled is None:
            enabled = not self.parametric_mode_enabled

        self._logger.debug("Current parametric_mode_enabled: %s", self.parametric_mode_enabled)
        self._logger.debug("Setting parametric mode to: %s", enabled)
        self._logger.debug("Mechanism layers count: %s", len(self.parent_tab.mechanism_layers))

        if enabled and not self.parent_tab.mechanism_layers:
            self._logger.info("No mechanisms available for parametric editing")
            self._show_info_message(
                "Parametric Edit",
                "Please generate mechanisms first using 'Get Mechanism' button.\n\n"
                "Parametric editing allows you to interactively adjust mechanism "
                "parameters by dragging anchor points.",
            )
            return

        # Handle animation state
        should_restore_animation = False
        if enabled:
            self._manage_animation_state_on_enable()
        else:
            should_restore_animation = self._manage_animation_state_on_disable()

        self._logger.debug("Setting parametric_mode_enabled to: %s", enabled)
        self.parametric_mode_enabled = enabled

        if enabled:
            self._logger.debug("Enabling parametric mode...")
            self._enable_parametric_mode()
        else:
            self._logger.debug("Disabling parametric mode...")
            self._disable_parametric_mode()

            if should_restore_animation:
                logging.info(f"[PARAMETRIC] Restoring animation via QTimer, parent_tab_id={id(self.parent_tab)}")
                QTimer.singleShot(100, self.parent_tab._on_start_animation)

        self._logger.debug("Updating UI state...")
        self.parent_tab.ui_state_manager.set_parametric_mode(enabled)
        self.parent_tab._update_all_ui_states()
        self._logger.debug("toggle_parametric_mode completed")

    def _enable_parametric_mode(self) -> None:
        """Enable parametric editing mode - show interactive handles."""
        if not self.parent_tab.parametric_editor:
            return

        try:
            for mechanism_id in self.parent_tab.mechanism_layers.keys():
                self.parent_tab.mechanism_layers[mechanism_id]["parametric_mode"] = True

            for mechanism_id in list(self.parent_tab.mechanism_layers.keys()):
                self.parent_tab._clear_mechanism_trace(mechanism_id)

            for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                mechanism_type = layer_data.get("type")

                try:
                    if "params" not in layer_data:
                        layer_data["params"] = {}

                    to_scene = self.parent_tab._get_scene_transform_function(layer_data)
                    to_mech = self.parent_tab._get_inverse_scene_transform_function(layer_data)

                    self._parameter_mapper.ensure_mechanism_parameters(
                        layer_data, mechanism_type, to_scene
                    )

                    # Pass transforms to create_editor so handles are positioned correctly
                    editor = self.parent_tab.parametric_editor.create_editor(
                        mechanism_id,
                        layer_data,
                        to_scene_coords=to_scene,
                        to_mech_coords=to_mech,
                    )
                except Exception as e:
                    import traceback

                    self._logger.error("Error creating parametric editor for %s: %s", mechanism_id, e)
                    self._logger.debug(traceback.format_exc())

            self.parent_tab.parametric_editor.enable_editing()
            self._set_active_editor_from_selection()

            # Use animation coordinator for button state
            self._animation_coordinator.set_buttons(
                play_btn=getattr(self.parent_tab, "play_btn", None),
                stop_btn=getattr(self.parent_tab, "stop_btn", None),
                reset_btn=getattr(self.parent_tab, "reset_btn", None),
            )
            self._animation_coordinator._disable_animation_controls()

            self._disable_mechanism_visual_interaction()

        except Exception as e:
            import traceback

            self._logger.error("Error enabling parametric mode: %s", e)
            self._logger.debug(traceback.format_exc())

    def _set_active_editor_from_selection(self) -> None:
        """Set active editor based on currently selected part in the UI."""
        selected_items = self.parent_tab.ui_widgets["mechanism_layers_list"].selectedItems()
        if selected_items:
            selected_part = selected_items[0].data(Qt.ItemDataRole.UserRole)

            found = False
            for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                part_name = layer_data.get("part_name")
                if part_name == selected_part:
                    self.parent_tab.parametric_editor.set_active_editor(mechanism_id)
                    found = True
                    break

            if not found and self.parent_tab.mechanism_layers:
                first_id = list(self.parent_tab.mechanism_layers.keys())[0]
                self.parent_tab.parametric_editor.set_active_editor(first_id)
        else:
            if self.parent_tab.selected_part_name:
                for mechanism_id, layer_data in self.parent_tab.mechanism_layers.items():
                    if layer_data.get("part_name") == self.parent_tab.selected_part_name:
                        self.parent_tab.parametric_editor.set_active_editor(mechanism_id)
                        break

    def _disable_parametric_mode(self) -> None:
        """Disable parametric editing mode."""
        if not self.parent_tab.parametric_editor:
            return

        try:
            self.parent_tab.parametric_editor.disable_editing()
            self._animation_coordinator._enable_animation_controls()
            self._enable_mechanism_visual_interaction()

            for mechanism_id in self.parent_tab.mechanism_layers.keys():
                self.parent_tab.mechanism_layers[mechanism_id]["parametric_mode"] = False

        except Exception as e:
            import traceback

            self._logger.error("Error disabling parametric mode: %s", e)
            self._logger.debug(traceback.format_exc())

    def _disable_mechanism_visual_interaction(self) -> None:
        """Disable mechanism visual interaction to allow handle interaction."""
        try:
            for mechanism_id in self.parent_tab.mechanism_layers:
                for item_list in [
                    self.parent_tab.mechanism_path_items.get(mechanism_id, []),
                    self.parent_tab.path_visual_items.get(mechanism_id, []),
                ]:
                    for item in item_list:
                        if hasattr(item, "setFlag"):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
        except Exception as e:
            self._logger.error("Error disabling mechanism visual interaction: %s", e)

    def _enable_mechanism_visual_interaction(self) -> None:
        """Re-enable mechanism visual interaction."""
        try:
            for mechanism_id in self.parent_tab.mechanism_layers:
                for item_list in [
                    self.parent_tab.mechanism_path_items.get(mechanism_id, []),
                    self.parent_tab.path_visual_items.get(mechanism_id, []),
                ]:
                    for item in item_list:
                        if hasattr(item, "setFlag"):
                            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                            item.setFlag(item.GraphicsItemFlag.ItemIsMovable, True)
        except Exception as e:
            self._logger.error("Error enabling mechanism visual interaction: %s", e)

    @pyqtSlot(str, dict)
    def _on_parametric_mechanism_update(
        self, mechanism_id: str, params: dict[str, Any]
    ) -> None:
        """Handle mechanism parameter updates from parametric editor."""
        try:
            if mechanism_id not in self.parent_tab.mechanism_layers:
                return

            layer_data = self.parent_tab.mechanism_layers[mechanism_id]

            if "params" not in layer_data:
                layer_data["params"] = {}
            layer_data["params"].update(params)

            mech_type = layer_data.get("type")
            try:
                if mech_type == "4_bar_linkage":
                    self._enforce_grashof_and_snap(layer_data)
                elif mech_type in ("gear", "simple_gear"):
                    self._enforce_gear_meshing_and_snap(layer_data)
                elif mech_type == "cam":
                    self._enforce_cam_follower_snap(layer_data)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

            self._regenerate_mechanism_simulation(mechanism_id, layer_data)
            self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

            # Emit signal to propagate changes to StateManager (for undo/redo)
            if hasattr(self.parent_tab, 'mechanism_parameters_changed'):
                self.parent_tab.mechanism_parameters_changed.emit(
                    mechanism_id, dict(layer_data.get("params", {}))
                )

        except Exception as e:
            import traceback

            self._logger.error("Error handling parametric mechanism update: %s", e)
            self._logger.debug(traceback.format_exc())

    @pyqtSlot(str)
    def _on_parametric_visual_refresh(self, mechanism_id: str) -> None:
        """Handle visual refresh requests from parametric editor."""
        try:
            if mechanism_id not in self.parent_tab.mechanism_layers:
                return

            layer_data = self.parent_tab.mechanism_layers[mechanism_id]
            self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

        except Exception as e:
            import traceback

            self._logger.error("Error handling parametric visual refresh: %s", e)
            self._logger.debug(traceback.format_exc())

    def _regenerate_mechanism_simulation(
        self, mechanism_id: str, layer_data: dict[str, Any]
    ) -> None:
        """Regenerate simulation data for a mechanism after parameters changed."""
        try:
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})

            self.parent_tab._clear_mechanism_trace(mechanism_id)

            if mech_type == "4_bar_linkage":
                self._regenerate_4bar_simulation(layer_data, params)
            elif mech_type == "5_bar_linkage":
                self._regenerate_5bar_simulation(layer_data, params)
            elif mech_type == "6_bar_linkage":
                self._regenerate_6bar_simulation(layer_data, params)
            elif mech_type == "cam":
                self._regenerate_cam_simulation(layer_data, params)
            elif mech_type == "gear":
                self._regenerate_gear_simulation(layer_data, params)
            elif mech_type == "planetary_gear":
                self._regenerate_planetary_gear_simulation(layer_data, params)

        except Exception as e:
            self._logger.error("Error regenerating mechanism simulation: %s", e)

    def _enforce_grashof_and_snap(self, layer_data: dict[str, Any]) -> bool:
        """Enforce Grashof condition with minimal snapping."""
        params = layer_data.get("params", {})
        to_mech = self.parent_tab._get_inverse_scene_transform_function(layer_data)
        if not to_mech:
            return False

        a1 = QPointF(params.get("anchor1_x", 0.0), params.get("anchor1_y", 0.0))
        a2 = QPointF(params.get("anchor2_x", 100.0), params.get("anchor2_y", 0.0))
        p1 = to_mech(a1)
        p2 = to_mech(a2)
        p1 = np.array([float(p1[0]), float(p1[1])])
        p2 = np.array([float(p2[0]), float(p2[1])])
        L1 = float(np.linalg.norm(p2 - p1))

        transform_config = self._parameter_mapper.get_transform_config(
            layer_data, utils_qpainterpath_to_numpy_array
        )

        def scene_to_mech_len(val: float) -> float:
            return self._parameter_mapper.scene_to_mech_length(val, transform_config)

        def mech_to_scene_len(val: float) -> float:
            return self._parameter_mapper.mech_to_scene_length(val, transform_config)

        L2 = scene_to_mech_len(params.get("l2", 40.0))
        L3 = scene_to_mech_len(params.get("l3", 60.0))
        L4 = scene_to_mech_len(params.get("l4", 50.0))

        items = [("L1", L1), ("L2", L2), ("L3", L3), ("L4", L4)]
        items_sorted = sorted(items, key=lambda x: x[1])
        s_name, shortest = items_sorted[0]
        m1_name, m1 = items_sorted[1]
        m2_name, m2 = items_sorted[2]
        longest_name, longest = items_sorted[3]

        if shortest + longest <= m1 + m2 + 1e-9:
            return False
        delta = (shortest + longest) - (m1 + m2) + 1e-6

        target = None
        if "L3" in (m1_name, m2_name):
            target = "L3"
        else:
            target = m1_name

        if target == "L2":
            L2 += delta
        elif target == "L4":
            L4 += delta
        else:
            L3 += delta

        params["l2"] = mech_to_scene_len(L2)
        params["l3"] = mech_to_scene_len(L3)
        params["l4"] = mech_to_scene_len(L4)

        if self.physics_snap_mode == "high":
            self._logger.warning(
                "[PHYSICS-SNAP] Grashof violated; alert-only mode; target=%s needs +%.3f (mech)",
                target,
                delta,
            )
            return False

        self._logger.warning(
            "[PHYSICS-SNAP] Grashof violated; snapped %s by +%.3f (mech units)",
            target,
            delta,
        )
        return True

    def _enforce_gear_meshing_and_snap(self, layer_data: dict[str, Any]) -> bool:
        """Ensure gear centers are properly separated for meshing."""
        params = layer_data.get("params", {})
        try:
            g1x = float(params.get("gear1_x"))
            g1y = float(params.get("gear1_y"))
            g2x = float(params.get("gear2_x"))
            g2y = float(params.get("gear2_y"))
        except Exception:
            return False

        r1 = params.get("gear1_radius", params.get("r1"))
        r2 = params.get("gear2_radius", params.get("r2"))
        try:
            r1 = float(r1)
            r2 = float(r2)
        except Exception:
            return False

        g1 = np.array([g1x, g1y], dtype=float)
        g2 = np.array([g2x, g2y], dtype=float)
        d = float(np.linalg.norm(g2 - g1))
        if not np.isfinite(d) or d < 1e-9:
            return False

        clearance = 2.0 if self.physics_snap_mode in ("fast", "balanced") else 0.0
        desired = max(0.0, r1 + r2 + clearance)

        if abs(d - desired) <= 0.25:
            return False

        if self.physics_snap_mode == "high":
            self._logger.warning(
                "[PHYSICS-SNAP] Gear mesh off by %.3f; alert-only (no snap)", d - desired
            )
            return False

        dir_vec = (g2 - g1) / d
        new_g2 = g1 + dir_vec * desired
        params["gear2_x"] = float(new_g2[0])
        params["gear2_y"] = float(new_g2[1])
        self._logger.warning(
            "[PHYSICS-SNAP] Adjusted gear2 to maintain mesh (Δ=%.3f)", desired - d
        )
        return True

    def _enforce_cam_follower_snap(self, layer_data: dict[str, Any]) -> bool:
        """Keep cam follower within simple physical bounds."""
        params = layer_data.get("params", {})
        changed = False

        if self.physics_snap_mode == "high":
            rod_len = float(params.get("follower_rod_length", 40.0))
            if rod_len < 20.0:
                self._logger.warning(
                    "[PHYSICS-SNAP] CAM rod length too short (%.2f) — alert-only", rod_len
                )
            base_r = float(params.get("base_radius", 25.0))
            if base_r < 0.0:
                self._logger.warning(
                    "[PHYSICS-SNAP] CAM base radius negative (%.2f) — alert-only", base_r
                )
            return False

        try:
            rod_len = float(params.get("follower_rod_length", 40.0))
            min_len = 20.0 if self.physics_snap_mode == "fast" else 15.0
            if rod_len < min_len:
                params["follower_rod_length"] = float(min_len)
                self._logger.warning(
                    "[PHYSICS-SNAP] CAM: clamped follower_rod_length to %.1f", min_len
                )
                changed = True
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        try:
            base_r = float(params.get("base_radius", 25.0))
            if base_r < 1.0:
                params["base_radius"] = 1.0
                self._logger.warning("[PHYSICS-SNAP] CAM: clamped base_radius to 1.0")
                changed = True
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

        return changed

    def set_physics_snap_mode(self, mode: str) -> None:
        """Set physics snapping mode."""
        mode = (mode or "").strip().lower()
        if mode in ("fast", "balanced", "high"):
            self.physics_snap_mode = mode
        else:
            self._logger.warning(
                "[PHYSICS-SNAP] Unknown mode '%s'; keeping '%s'",
                mode,
                self.physics_snap_mode,
            )

    def _regenerate_4bar_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate new simulation data for 4-bar linkage."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": [],
        }

        to_mech = self.parent_tab._get_inverse_scene_transform_function(layer_data)
        transform_config = self._parameter_mapper.get_transform_config(
            layer_data, utils_qpainterpath_to_numpy_array
        )

        def scene_len_to_mech(val: float) -> float:
            return self._parameter_mapper.scene_to_mech_length(val, transform_config)

        if to_mech and ("anchor1_x" in params and "anchor1_y" in params):
            p1 = to_mech(QPointF(params["anchor1_x"], params["anchor1_y"]))
        else:
            p1 = np.array(params.get("ground_pivot_1", [0.0, 0.0]))
        if to_mech and ("anchor2_x" in params and "anchor2_y" in params):
            p2 = to_mech(QPointF(params["anchor2_x"], params["anchor2_y"]))
        else:
            p2 = np.array(params.get("ground_pivot_2", [100.0, 0.0]))

        p1 = np.array([float(p1[0]), float(p1[1])])
        p2 = np.array([float(p2[0]), float(p2[1])])

        L2 = params.get("L2")
        L3 = params.get("L3")
        L4 = params.get("L4")
        if L2 is None:
            L2 = scene_len_to_mech(params.get("l2", 40))
        if L3 is None:
            L3 = scene_len_to_mech(params.get("l3", 60))
        if L4 is None:
            L4 = scene_len_to_mech(params.get("l4", 50))
        L2, L3, L4 = float(L2), float(L3), float(L4)

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])
            p4 = self._solve_circle_intersection(p3, L3, p2, L4)

            if p4 is not None:
                joint_positions["p1_positions"].append(p1.tolist())
                joint_positions["p2_positions"].append(p2.tolist())
                joint_positions["p3_positions"].append(p3.tolist())
                joint_positions["p4_positions"].append(p4.tolist())

        layer_data["full_simulation_data"] = {"joint_positions": joint_positions}

    def _regenerate_5bar_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate new simulation data for 5-bar linkage."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": [],
            "p5_positions": [],
        }

        key_points = layer_data.get("key_points", {})
        p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
        p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))

        if (
            "joint_3" in key_points
            and "joint_4" in key_points
            and "joint_5" in key_points
        ):
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])

            L2 = np.linalg.norm(p3 - p1)
            L3 = np.linalg.norm(p4 - p3)
            L4 = np.linalg.norm(p5 - p4)
            L5 = np.linalg.norm(p5 - p2)

            params["L2"] = float(L2)
            params["L3"] = float(L3)
            params["L4"] = float(L4)
            params["L5"] = float(L5)
        else:
            L2 = params.get("L2", 40)
            L3 = params.get("L3", 50)
            L4 = params.get("L4", 45)
            L5 = params.get("L5", 55)

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])
            p4 = p3 + L3 * np.array([np.cos(theta + 0.5), np.sin(theta + 0.5)])
            p5 = self._solve_circle_intersection(p4, L4, p2, L5)

            if p5 is not None:
                joint_positions["p1_positions"].append(p1.tolist())
                joint_positions["p2_positions"].append(p2.tolist())
                joint_positions["p3_positions"].append(p3.tolist())
                joint_positions["p4_positions"].append(p4.tolist())
                joint_positions["p5_positions"].append(p5.tolist())

        layer_data["full_simulation_data"] = {"joint_positions": joint_positions}

    def _regenerate_6bar_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate new simulation data for 6-bar linkage."""
        num_frames = 100
        joint_positions = {
            "p1_positions": [],
            "p2_positions": [],
            "p3_positions": [],
            "p4_positions": [],
            "p5_positions": [],
            "p6_positions": [],
        }

        key_points = layer_data.get("key_points", {})
        p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
        p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))
        p6 = np.array(key_points.get("ground_pivot_3", [50, -30]))

        if all(k in key_points for k in ["joint_3", "joint_4", "joint_5"]):
            p3 = np.array(key_points["joint_3"])
            p4 = np.array(key_points["joint_4"])
            p5 = np.array(key_points["joint_5"])

            L2 = np.linalg.norm(p3 - p1)
            L3 = np.linalg.norm(p4 - p3)
            L4 = np.linalg.norm(p4 - p2)
            L5 = np.linalg.norm(p5 - p4)
            L6 = np.linalg.norm(p5 - p6)

            params.update(
                {
                    "L2": float(L2),
                    "L3": float(L3),
                    "L4": float(L4),
                    "L5": float(L5),
                    "L6": float(L6),
                }
            )
        else:
            L2 = params.get("L2", 40)
            L3 = params.get("L3", 60)
            L4 = params.get("L4", 50)
            L5 = params.get("L5", 45)
            L6 = params.get("L6", 55)

        for i in range(num_frames):
            theta = (i / num_frames) * 2 * np.pi
            p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])
            p4 = self._solve_circle_intersection(p3, L3, p2, L4)

            if p4 is not None:
                p5 = self._solve_circle_intersection(p4, L5, p6, L6)
                if p5 is not None:
                    joint_positions["p1_positions"].append(p1.tolist())
                    joint_positions["p2_positions"].append(p2.tolist())
                    joint_positions["p3_positions"].append(p3.tolist())
                    joint_positions["p4_positions"].append(p4.tolist())
                    joint_positions["p5_positions"].append(p5.tolist())
                    joint_positions["p6_positions"].append(p6.tolist())

        layer_data["full_simulation_data"] = {"joint_positions": joint_positions}

    def _regenerate_cam_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate cam mechanism data with correct physics."""
        num_frames = 100
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        rod_length = params.get("follower_rod_length", 40.0)

        key_points = layer_data.get("key_points", {})
        if "cam_center" in key_points:
            cam_center_base = np.array(key_points["cam_center"])
        else:
            cam_center_base = np.array([0, 0])

        cam_data = {"cam_centers": [], "follower_y_positions": []}

        for i in range(num_frames):
            angle = (i / num_frames) * 2 * np.pi
            lift = eccentricity * (1 + np.cos(angle + np.pi / 2)) / 2
            cam_radius_at_angle = base_radius + lift
            current_cam_center = cam_center_base
            follower_y = current_cam_center[1] - cam_radius_at_angle - rod_length

            cam_data["cam_centers"].append(current_cam_center.tolist())
            cam_data["follower_y_positions"].append(follower_y)

        layer_data["full_simulation_data"] = {"cam_data": cam_data}

    def _regenerate_gear_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate gear rotation data."""
        num_frames = 100
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        key_points = layer_data.get("key_points", {})
        if "gear1_center" in key_points and "gear2_center" in key_points:
            g1 = np.array(key_points["gear1_center"])
            g2 = np.array(key_points["gear2_center"])
            distance = np.linalg.norm(g2 - g1)

            ratio = r2 / r1
            r1 = distance / (1 + ratio)
            r2 = r1 * ratio
            params["r1"] = float(r1)
            params["r2"] = float(r2)

        gear_data = {"gear1_angles": [], "gear2_angles": []}

        for i in range(num_frames):
            theta1 = (i / num_frames) * 2 * np.pi
            theta2 = -theta1 * (r1 / r2)

            gear_data["gear1_angles"].append(theta1)
            gear_data["gear2_angles"].append(theta2)

        layer_data["full_simulation_data"] = {"gear_data": gear_data}

    def _regenerate_planetary_gear_simulation(
        self, layer_data: dict[str, Any], params: dict[str, Any]
    ) -> None:
        """Generate planetary gear data."""
        num_frames = 100
        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        key_points = layer_data.get("key_points", {})
        if "sun_center" in key_points:
            sun_center_base = np.array(key_points["sun_center"])
        else:
            sun_center_base = np.array([0, 0])

        gear_positions = {
            "sun_centers": [],
            "planet_centers": [],
            "tracking_points": [],
        }

        for i in range(num_frames):
            angle = (i / num_frames) * 2 * np.pi
            planet_orbital_angle = angle
            planet_rotation_angle = -angle * (r_sun / r_planet)

            sun_center = sun_center_base
            planet_center = sun_center + (r_sun + r_planet) * np.array(
                [np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)]
            )
            tracking_point = planet_center + arm_length * np.array(
                [np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)]
            )

            gear_positions["sun_centers"].append(sun_center.tolist())
            gear_positions["planet_centers"].append(planet_center.tolist())
            gear_positions["tracking_points"].append(tracking_point.tolist())

        layer_data["full_simulation_data"] = {"gear_positions": gear_positions}

    def _solve_circle_intersection(
        self,
        center1: np.ndarray,
        radius1: float,
        center2: np.ndarray,
        radius2: float,
    ) -> np.ndarray | None:
        """Find the intersection point of two circles."""
        try:
            d = np.linalg.norm(center2 - center1)

            if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
                direction = (center2 - center1) / d if d > 0 else np.array([1, 0])
                return center1 + direction * radius1

            a = (radius1**2 - radius2**2 + d**2) / (2 * d)
            h = np.sqrt(radius1**2 - a**2)
            p = center1 + a * (center2 - center1) / d
            offset = (
                h
                * np.array([-(center2[1] - center1[1]), center2[0] - center1[0]])
                / d
            )

            intersection1 = p + offset
            intersection2 = p - offset

            if intersection1[1] >= intersection2[1]:
                return intersection1
            else:
                return intersection2

        except Exception:
            return center1 + np.array([radius1, 0])

    def _try_visualization_adapter_update(
        self, mechanism_id: str, mechanism_data: dict[str, Any]
    ) -> bool:
        """Try to update via visualization adapter. Returns True if handled."""
        if not (hasattr(self.parent_tab, "visualization_adapter")
                and self.parent_tab.visualization_adapter):
            return False

        try:
            from ..visualization import VISUALIZATION_AVAILABLE
            if not VISUALIZATION_AVAILABLE:
                return False

            transform_func = self.parent_tab._get_scene_transform_function(mechanism_data)
            if transform_func:
                mechanism_data["transform_function"] = transform_func

            self.parent_tab.visualization_adapter.update_mechanism_visuals(
                mechanism_id, mechanism_data
            )

            if hasattr(self.parent_tab, "mechanism_view"):
                self.parent_tab.mechanism_view.update()
            return True
        except ImportError:
            return False

    def _capture_visual_properties(self, visual_items: list) -> list[dict[str, Any]]:
        """Capture properties from visual items for later restoration."""
        properties = []
        for item in visual_items:
            if item and self._is_item_valid(item):
                try:
                    props = {
                        "pen": item.pen() if hasattr(item, "pen") else None,
                        "brush": item.brush() if hasattr(item, "brush") else None,
                        "z_value": item.zValue(),
                        "visible": item.isVisible(),
                        "enabled": item.isEnabled(),
                    }
                    properties.append(props)
                except RuntimeError:
                    properties.append({})
        return properties

    def _remove_visual_items_from_scene(self, visual_items: list) -> None:
        """Remove visual items from the mechanism scene."""
        for item in visual_items:
            if item and self._is_item_valid(item):
                try:
                    if (hasattr(self.parent_tab, "mechanism_scene")
                            and item.scene() == self.parent_tab.mechanism_scene):
                        self.parent_tab.mechanism_scene.removeItem(item)
                except RuntimeError:
                    pass

    def _restore_visual_properties(
        self, new_items: list, original_properties: list[dict[str, Any]]
    ) -> None:
        """Restore visual properties to new items."""
        for i, item in enumerate(new_items):
            if i >= len(original_properties) or not item:
                continue
            try:
                props = original_properties[i]
                if props.get("pen") and hasattr(item, "setPen"):
                    item.setPen(props["pen"])
                if props.get("brush") and hasattr(item, "setBrush"):
                    item.setBrush(props["brush"])
                if props.get("z_value"):
                    item.setZValue(props["z_value"])
                if props.get("visible") is not None:
                    item.setVisible(props["visible"])
                if props.get("enabled") is not None:
                    item.setEnabled(props["enabled"])
            except (RuntimeError, KeyError):
                continue

    def _should_update_handles(self, mechanism_id: str) -> bool:
        """Check if handle positions should be updated for mechanism."""
        return (
            hasattr(self.parent_tab, "parametric_handles")
            and mechanism_id in self.parent_tab.parametric_handles
            and self.parametric_mode_enabled
        )

    def _update_mechanism_visuals_realtime(
        self, mechanism_id: str, mechanism_data: dict[str, Any]
    ) -> None:
        """Update mechanism visuals in real-time during parametric editing."""
        try:
            # Try visualization adapter first
            if self._try_visualization_adapter_update(mechanism_id, mechanism_data):
                return

            layer_data = self.parent_tab.mechanism_layers.get(
                mechanism_id, mechanism_data
            )

            # Handle animation state
            animation_was_running = (
                hasattr(self.parent_tab, "animation_timer")
                and self.parent_tab.animation_timer.isActive()
            )
            if animation_was_running:
                self.parent_tab._on_stop_animation()

            # Capture, remove, recreate, restore visual items
            visual_items = layer_data.get("visual_items", [])
            original_properties = self._capture_visual_properties(visual_items)
            self._remove_visual_items_from_scene(visual_items)

            mechanism_type = layer_data.get("type")
            new_items = self._create_mechanism_visuals(layer_data, mechanism_type)
            self._restore_visual_properties(new_items, original_properties)

            layer_data["visual_items"] = new_items

            # Update handles if needed
            if self._should_update_handles(mechanism_id):
                self._update_handle_positions_for_mechanism(mechanism_id, layer_data)

            # Update view
            if hasattr(self.parent_tab, "mechanism_view"):
                self.parent_tab.mechanism_view.update()

            # Restore animation if needed
            if animation_was_running and not self.parametric_mode_enabled:
                logging.info(f"[PARAMETRIC] Restoring animation after update, parent_tab_id={id(self.parent_tab)}")
                self.parent_tab._on_start_animation()

        except Exception as e:
            self._logger.error("Error updating mechanism visuals: %s", e)

    def _is_item_valid(self, item: Any) -> bool:
        """Check if a graphics item is valid and not deleted."""
        try:
            _ = item.zValue()
            return True
        except (RuntimeError, AttributeError):
            return False

    def _create_mechanism_visuals(
        self, layer_data: dict[str, Any], mechanism_type: str
    ) -> list:
        """Create visual items for a mechanism based on its type."""
        vf = getattr(self.parent_tab, "visuals_factory", None)
        if not vf:
            return []

        transform_func = self.parent_tab._get_scene_transform_function(layer_data)

        # Strategy mapping: mechanism_type -> (method_name, extra_args_getter)
        visual_strategies: dict[str, tuple[str, Any]] = {
            "4_bar_linkage": ("create_4bar_linkage_visuals", None),
            "cam": ("create_cam_visuals", lambda: self._get_character_position_safe()),
            "gear": ("create_gear_visuals", None),
            "planetary_gear": ("create_planetary_gear_visuals", None),
        }

        try:
            strategy = visual_strategies.get(mechanism_type)
            if not strategy:
                return []

            method_name, extra_args_getter = strategy
            method = getattr(vf, method_name, None)
            if not method:
                return []

            if extra_args_getter:
                return method(layer_data, transform_func, extra_args_getter())
            return method(layer_data, transform_func)
        except Exception as e:
            self._logger.error("Error creating visuals for %s: %s", mechanism_type, e)
            return []

    def _get_character_position_safe(self) -> Any:
        """Safely get character position from parent tab."""
        if hasattr(self.parent_tab, "_get_character_position"):
            return self.parent_tab._get_character_position()
        return None

    def _update_handle_positions_for_mechanism(
        self, mechanism_id: str, layer_data: dict[str, Any]
    ) -> None:
        """Update handle positions for a specific mechanism."""
        try:
            if hasattr(self.parent_tab, "_update_handle_positions_for_mechanism"):
                self.parent_tab._update_handle_positions_for_mechanism(
                    mechanism_id, layer_data
                )
        except Exception as e:
            self._logger.error("Error updating handle positions for mechanism %s: %s", mechanism_id, e)

    def is_parametric_mode_enabled(self) -> bool:
        """Check if parametric mode is currently enabled."""
        return self.parametric_mode_enabled

    def cleanup(self) -> None:
        """Clean up resources used by the parametric editing manager."""
        try:
            if self.parametric_mode_enabled:
                self.toggle_parametric_mode(False)

            if hasattr(self, "_animation_state_before_parametric"):
                delattr(self, "_animation_state_before_parametric")

        except Exception as e:
            self._logger.error("Error during parametric editing manager cleanup: %s", e)
