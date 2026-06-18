"""
Motion Path Manager - Drawing, smoothing, and path manipulation.

Extracted from EditorTab god class. Handles all motion path operations
including freehand drawing, smoothness adjustment, RDP simplification,
ellipse fitting, and feasibility snapping.

Design Pattern: Manager (coordinates path operations)
Time Complexity: O(n) for path operations, O(n²) for RDP simplification
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import QObject, QPointF, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainterPath, QPen

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene, QLabel, QPushButton, QRadioButton, QSlider

    from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
    from automataii.presentation.qt.views.editor_view import EditorView


class MotionPathManager(QObject):
    """
    Manages motion path drawing, smoothing, and manipulation.

    Responsibilities:
    - Toggle drawing mode on/off
    - Handle freehand path completion
    - Smooth paths using RDP algorithm
    - Fit ellipses to paths
    - Apply feasibility corrections based on IK constraints
    - Update paths across data structures
    - Handle vertex-based path editing

    Signals:
        motion_path_updated: Emitted when a path is updated (part_name, path)
        path_data_changed: Emitted when any path data changes (dict of paths)
        drawing_mode_changed: Emitted when drawing mode toggles (is_drawing)
        vertex_editing_changed: Emitted when vertex editing mode toggles (is_editing)
    """

    motion_path_updated = pyqtSignal(str, QPainterPath)
    path_data_changed = pyqtSignal(dict)
    drawing_mode_changed = pyqtSignal(bool)
    vertex_editing_changed = pyqtSignal(bool)

    def __init__(
        self,
        editor_view: EditorView,
        editor_scene: QGraphicsScene,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize motion path manager.

        Args:
            editor_view: The EditorView for path visualization
            editor_scene: The graphics scene
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._editor_view = editor_view
        self._editor_scene = editor_scene

        # Corrected paths cache (feasibility-adjusted)
        self._corrected_paths: dict[str, QPainterPath] = {}
        self._path_closed_intent: dict[str, bool] = {}

        # UI references (set via configure_ui)
        self._define_btn: QPushButton | None = None
        self._clear_btn: QPushButton | None = None
        self._edit_vertices_btn: QPushButton | None = None
        self._status_label: QLabel | None = None
        self._info_label: QLabel | None = None
        self._smoothness_slider: QSlider | None = None
        self._smoothness_label: QLabel | None = None
        self._closed_path_radio: QRadioButton | None = None

        # Callbacks for external state/operations
        self._get_selected_part: Callable[[], str | None] = lambda: None
        self._get_editor_items: Callable[[], dict[str, CharacterPartItem]] = lambda: {}
        self._get_parts_info: Callable[[], dict[str, Any]] = lambda: {}
        self._get_main_window: Callable[[], Any] = lambda: None
        self._update_button_states: Callable[[], None] = lambda: None
        self._has_motion_path: Callable[[str], bool] = lambda x: False
        self._emit_path_data: Callable[[], None] = lambda: None

    def configure_ui(
        self,
        define_btn: QPushButton,
        clear_btn: QPushButton,
        status_label: QLabel,
        info_label: QLabel,
        smoothness_slider: QSlider,
        smoothness_label: QLabel,
        closed_path_radio: QRadioButton,
        edit_vertices_btn: QPushButton | None = None,
    ) -> None:
        """Configure UI element references."""
        self._define_btn = define_btn
        self._clear_btn = clear_btn
        self._edit_vertices_btn = edit_vertices_btn
        self._status_label = status_label
        self._info_label = info_label
        self._smoothness_slider = smoothness_slider
        self._smoothness_label = smoothness_label
        self._closed_path_radio = closed_path_radio

    def configure_callbacks(
        self,
        get_selected_part: Callable[[], str | None],
        get_editor_items: Callable[[], dict[str, CharacterPartItem]],
        get_parts_info: Callable[[], dict[str, Any]],
        get_main_window: Callable[[], Any],
        update_button_states: Callable[[], None],
        has_motion_path: Callable[[str], bool],
        emit_path_data: Callable[[], None],
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_selected_part = get_selected_part
        self._get_editor_items = get_editor_items
        self._get_parts_info = get_parts_info
        self._get_main_window = get_main_window
        self._update_button_states = update_button_states
        self._has_motion_path = has_motion_path
        self._emit_path_data = emit_path_data

    def clear_corrected_paths_cache(self) -> None:
        """Clear feasibility-corrected paths that should not survive editor reset."""
        self._corrected_paths.clear()
        self._path_closed_intent.clear()

    def _show_status_message(self, message: str) -> None:
        """Best-effort status message that cannot crash Qt signal handlers.

        Editor actions are usually invoked from Qt slots.  An uncaught Python
        exception in a PyQt slot can abort the whole process, so status-bar
        access must tolerate partially constructed windows and teardown.
        """
        main_window = self._get_main_window()
        if not main_window or not hasattr(main_window, "statusBar"):
            logging.info("Status: %s", message)
            return

        try:
            status_bar = main_window.statusBar()
        except Exception:
            logging.debug("Status bar lookup failed", exc_info=True)
            status_bar = None

        if status_bar and hasattr(status_bar, "showMessage"):
            status_bar.showMessage(message)
        else:
            logging.info("Status: %s", message)

    @staticmethod
    def _parts_data_from_project_manager(project_data_manager: Any) -> Any:
        """Return project parts from either the SSOT manager API or lightweight test doubles."""
        get_current_parts_data = getattr(project_data_manager, "get_current_parts_data", None)
        if callable(get_current_parts_data):
            try:
                return get_current_parts_data()
            except Exception:
                logging.debug("Project parts lookup failed", exc_info=True)
                return None
        return getattr(project_data_manager, "parts", None)

    @property
    def corrected_paths(self) -> dict[str, QPainterPath]:
        """Get the corrected paths cache."""
        return self._corrected_paths

    # --- Drawing Mode Control ---

    def toggle_define_mode(self, checked: bool) -> None:
        """
        Handle the 'Start/Stop Drawing' button toggle.

        Args:
            checked: Whether drawing mode is being enabled
        """
        part_name = self._get_selected_part()
        if not part_name or not checked:
            self._editor_view.set_mode("select")
            if self._define_btn:
                self._define_btn.setText("✏️ Start Drawing Path")
            if self._info_label:
                self._info_label.setVisible(False)
            if checked and self._define_btn:
                self._define_btn.setChecked(False)
            self.drawing_mode_changed.emit(False)
            return

        logging.debug(f"Toggling drawing mode for part: {part_name}")

        # Clear existing mechanism visuals and motion path before new drawing
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, "mechanism_design_tab"):
            mechanism_tab = main_window.mechanism_design_tab
            if hasattr(mechanism_tab, "_clear_mechanism_for_part"):
                mechanism_tab._clear_mechanism_for_part(part_name)
                logging.info(f"🔄 MotionPathManager: Cleared mechanism visuals for '{part_name}'")

        # Clear existing motion path visuals
        if hasattr(self._editor_view, "clear_visual_path_for_component"):
            self._editor_view.clear_visual_path_for_component(part_name)
            logging.info(f"🔄 MotionPathManager: Cleared motion path visuals for '{part_name}'")

        # Clear from project data manager
        if main_window and hasattr(main_window, "project_data_manager"):
            parts_data = self._parts_data_from_project_manager(main_window.project_data_manager)
            if parts_data and part_name in parts_data:
                parts_data[part_name].motion_path_data = None
                logging.info(f"🔄 MotionPathManager: Cleared motion_path_data for '{part_name}'")

        editor_items = self._get_editor_items()
        if part_name in editor_items:
            target_item = editor_items[part_name]
            is_closed = self._closed_path_radio.isChecked() if self._closed_path_radio else True
            self._path_closed_intent[part_name] = is_closed
            self._editor_view.start_define_motion_path(target_item, is_closed=is_closed)
        else:
            # Keep the view mode consistent even if the selected list item is
            # stale or its scene item is not available yet.  This path should
            # be rare, but it must not crash the toggle slot.
            self._editor_view.set_mode("define_motion_path")

        if self._define_btn:
            self._define_btn.setText("■ Stop Drawing")
        if self._info_label:
            self._info_label.setVisible(True)

        self.drawing_mode_changed.emit(True)

    # --- Vertex Editing Mode Control ---

    def toggle_vertex_edit_mode(self, checked: bool) -> None:
        """
        Handle the 'Edit Vertices' button toggle.

        Args:
            checked: Whether vertex editing mode is being enabled
        """
        part_name = self._get_selected_part()

        if not checked:
            # Stop vertex editing
            if self._editor_view.is_editing_vertices():
                final_path = self._editor_view.stop_vertex_editing()
                if final_path and part_name:
                    self._update_part_path(part_name, final_path)

            if self._edit_vertices_btn:
                self._edit_vertices_btn.setText("Edit Vertices")

            self.vertex_editing_changed.emit(False)
            return

        if not part_name:
            logging.warning("No part selected for vertex editing")
            if self._edit_vertices_btn:
                self._edit_vertices_btn.setChecked(False)
            return

        # Check if part has a motion path
        if not self._has_motion_path(part_name):
            logging.warning(f"Part '{part_name}' has no motion path to edit")
            if self._edit_vertices_btn:
                self._edit_vertices_btn.setChecked(False)
            return

        # Get the current path
        editor_items = self._get_editor_items()
        path: QPainterPath | None = None

        if part_name in editor_items:
            part_item = editor_items[part_name]
            if hasattr(part_item, "motion_path") and part_item.motion_path:
                path = part_item.motion_path

        if not path or path.isEmpty():
            # Try from final_paths_map
            if hasattr(self._editor_view, "final_paths_map"):
                path_item = self._editor_view.final_paths_map.get(part_name)
                if path_item:
                    path = path_item.path()

        if not path or path.isEmpty():
            logging.warning(f"Could not find path for '{part_name}'")
            if self._edit_vertices_btn:
                self._edit_vertices_btn.setChecked(False)
            return

        # Start vertex editing
        is_closed = self._closed_intent_for_part(part_name)
        success = self._editor_view.start_vertex_editing(part_name, path, is_closed)

        if success:
            if self._edit_vertices_btn:
                self._edit_vertices_btn.setText("Done Editing")
            self.vertex_editing_changed.emit(True)
            logging.info(f"Started vertex editing for '{part_name}'")
        else:
            if self._edit_vertices_btn:
                self._edit_vertices_btn.setChecked(False)

    def on_vertex_path_modified(self, part_name: str, new_path: QPainterPath) -> None:
        """
        Handle path modification from vertex editing.

        This is called in real-time as vertices are dragged.

        Args:
            part_name: Name of the part being edited
            new_path: The modified path
        """
        # Update the visual path in EditorView's final_paths_map
        if hasattr(self._editor_view, "final_paths_map"):
            path_item = self._editor_view.final_paths_map.get(part_name)
            if path_item:
                path_item.setPath(new_path)

        # Emit signal for live preview in other tabs
        self.motion_path_updated.emit(part_name, new_path)

    def on_vertex_editing_finished(self, part_name: str, final_path: QPainterPath) -> None:
        """
        Handle completion of vertex editing.

        Args:
            part_name: Name of the part that was edited
            final_path: The final edited path
        """
        is_closed = self._closed_intent_for_part(part_name)
        snapped_path = self._snap_path_if_needed(part_name, final_path, is_closed)
        # Update all data structures with the final path
        self._update_part_path(part_name, snapped_path)

        # Reset button state
        if self._edit_vertices_btn:
            self._edit_vertices_btn.setChecked(False)
            self._edit_vertices_btn.setText("Edit Vertices")

        self.vertex_editing_changed.emit(False)
        self._update_button_states()

        self._show_status_message(f"Path vertices updated for part: {part_name}")

        logging.info(f"Completed vertex editing for '{part_name}'")

    def clear_selected_motion_path(self) -> None:
        """Clear motion path for the currently selected part."""
        part_name = self._get_selected_part()
        if not part_name:
            logging.warning("No part selected for motion path clearing")
            return

        logging.info(f"Clearing motion path for selected part: {part_name}")

        editor_items = self._get_editor_items()
        parts_info = self._get_parts_info()

        # Clear from CharacterPartItem
        if part_name in editor_items:
            part_item = editor_items[part_name]
            part_item.motion_path = None

            if hasattr(part_item, "motion_path_item") and part_item.motion_path_item:
                if part_item.motion_path_item.scene():
                    self._editor_scene.removeItem(part_item.motion_path_item)
                part_item.motion_path_item = None

            if hasattr(part_item, "motion_path_points"):
                part_item.motion_path_points = []

            if hasattr(part_item, "original_path_points"):
                part_item.original_path_points = []

        # Clear from parts_info
        if part_name in parts_info:
            parts_info[part_name].motion_path = None

        # Clear from EditorView's final paths map
        if hasattr(self._editor_view, "final_paths_map"):
            if part_name in self._editor_view.final_paths_map:
                path_item = self._editor_view.final_paths_map[part_name]
                if path_item and path_item.scene():
                    self._editor_scene.removeItem(path_item)
                del self._editor_view.final_paths_map[part_name]

        # Clear from corrected paths cache
        self._corrected_paths.pop(part_name, None)
        self._path_closed_intent.pop(part_name, None)

        # Clear overlays
        if hasattr(self._editor_view, "clear_raw_overlay_for"):
            self._editor_view.clear_raw_overlay_for(part_name)
        if hasattr(self._editor_view, "clear_corrected_overlay_for"):
            self._editor_view.clear_corrected_overlay_for(part_name)

        self._show_status_message(f"Motion path cleared for part: {part_name}")

        self._update_button_states()
        self._editor_view.viewport().update()
        self._emit_path_data()

    # --- Path Completion Handling ---

    @pyqtSlot(list, list, float)
    def handle_freehand_path_completed(
        self,
        path_points: list[QPointF],
        timed_points: list,
        duration: float,
    ) -> None:
        """
        Handle completion of freehand drawing from EditorView.

        Args:
            path_points: List of QPointF points from the drawing (resampled for visual)
            timed_points: List of TimedPoint with timestamps (for velocity-aware animation)
            duration: Total drawing duration in seconds
        """
        part_name = self._get_selected_part()
        if not part_name:
            logging.warning("handle_freehand_path_completed: No part selected.")
            return

        # Get final spline path from EditorView
        final_path_item = self._editor_view.final_paths_map.get(part_name)

        if not final_path_item:
            logging.error(f"Could not find final spline path for {part_name} in final_paths_map.")
            motion_qpath = QPainterPath()
            if path_points:
                motion_qpath.moveTo(path_points[0])
                for point in path_points[1:]:
                    motion_qpath.lineTo(point)
        else:
            motion_qpath = final_path_item.path()
            logging.info(f"Retrieved final spline path for '{part_name}'")

        is_closed = self._closed_path_radio.isChecked() if self._closed_path_radio else True
        self._path_closed_intent[part_name] = is_closed
        motion_qpath = self._snap_path_if_needed(part_name, motion_qpath, is_closed)
        if final_path_item:
            final_path_item.setPath(motion_qpath)

        # Update project data manager
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, "project_data_manager"):
            current_parts_info = getattr(main_window.project_data_manager, "parts", {})
            if part_name in current_parts_info:
                current_parts_info[part_name].motion_path = motion_qpath

        # Update CharacterPartItem
        editor_items = self._get_editor_items()
        if part_name in editor_items:
            char_part_item = editor_items[part_name]
            char_part_item.set_motion_path(motion_qpath)
            char_part_item.original_path_points = path_points.copy()
            # Store timing data for velocity-aware animation
            char_part_item.timed_path_points = list(timed_points)
            char_part_item.path_duration = duration

        # Log timing info if available
        if timed_points and duration > 0:
            logging.info(
                f"Path for '{part_name}': {len(timed_points)} timed points, "
                f"duration={duration:.2f}s"
            )

        # Emit signals
        self.motion_path_updated.emit(part_name, motion_qpath)
        self._emit_path_data()

        self._show_status_message(f"Motion path completed for part: {part_name}")

        self._update_button_states()
        logging.info(f"Completed spline motion path for part: {part_name}")

        # Reset the Start/Stop Drawing button after successful completion without
        # routing through a false cancellation signal that could clear vertex
        # handles or re-enter drawing toggles.
        self.handle_drawing_cancelled()

        # Automatically show vertex handles for the completed path
        self._show_vertex_handles(part_name, motion_qpath, is_closed)

    def handle_drawing_cancelled(self) -> None:
        """Handle cancellation of drawing mode."""
        logging.debug("Drawing mode cancelled")
        if self._define_btn:
            # Block signals to prevent triggering toggle_define_mode
            # which would call set_mode("select") and clear vertex handles
            self._define_btn.blockSignals(True)
            self._define_btn.setChecked(False)
            self._define_btn.setText("✏️ Start Drawing Path")
            self._define_btn.blockSignals(False)
        if self._info_label:
            self._info_label.setVisible(False)
        self.drawing_mode_changed.emit(False)

    # --- Smoothness Control ---

    def on_smoothness_changed(self, value: int) -> None:
        """
        Handle smoothness slider value change.

        Uses current vertex positions if vertex editing is active,
        otherwise falls back to original points.

        Args:
            value: Smoothness percentage (0-100)
        """
        if self._smoothness_label:
            self._smoothness_label.setText(f"{value}%")

        part_name = self._get_selected_part()
        if not part_name or not self._has_motion_path(part_name):
            return

        # If vertex editing is active, use vertex positions
        if self._editor_view.is_editing_vertices():
            current_path = self._editor_view._path_vertex_editor.get_current_path()
            if current_path and not current_path.isEmpty():
                # Apply smoothness to the vertex-based path
                self._apply_smoothness_to_path(part_name, current_path, value)
                return

        # Fallback to original points
        self._regenerate_path_with_smoothness(part_name, value)

    def _regenerate_path_with_smoothness(self, part_name: str, smoothness_percentage: int) -> None:
        """
        Regenerate motion path using tolerance-based smoothing.

        Uses RDP algorithm to simplify while preserving extremes.

        Args:
            part_name: Name of the part
            smoothness_percentage: Smoothness level (0=raw, 100=smooth)
        """
        original_points = self._get_original_path_points(part_name)
        if not original_points or len(original_points) < 3:
            logging.warning(f"Cannot regenerate path for {part_name}: insufficient points")
            return
        is_closed = self._closed_intent_for_part(part_name)

        # Smoothness 0: raw path
        if smoothness_percentage == 0:
            raw_path = self._create_raw_path(original_points, closed=is_closed)
            if hasattr(self._editor_view, "set_raw_overlay_path"):
                raw_pen = QPen(
                    QColor("#6a4c93"),
                    3.0,
                    Qt.PenStyle.DashLine,
                    Qt.PenCapStyle.RoundCap,
                )
                self._editor_view.set_raw_overlay_path(part_name, raw_path, raw_pen)

            # Try feasibility correction
            corrected = None
            try:
                corrected = self._apply_feasibility_snapping(part_name, raw_path, is_closed)
                if corrected and hasattr(self._editor_view, "set_corrected_overlay_path"):
                    self._editor_view.set_corrected_overlay_path(part_name, corrected)
                    self._corrected_paths[part_name] = corrected
            except Exception as e:
                logging.debug(f"Feasibility snapping skipped: {e}")

            # Use corrected path if available, otherwise raw path
            # This ensures the feasibility-adjusted path is the final output
            final_path = corrected if corrected else raw_path
            self._update_part_path(part_name, final_path)
            logging.info(f"Regenerated path (RAW) for {part_name}")
            return

        # Calculate tolerance based on path size
        bbox_min_x = min(p.x() for p in original_points)
        bbox_max_x = max(p.x() for p in original_points)
        bbox_min_y = min(p.y() for p in original_points)
        bbox_max_y = max(p.y() for p in original_points)
        diag = math.hypot(bbox_max_x - bbox_min_x, bbox_max_y - bbox_min_y)
        epsilon = max(0.1, 0.05 * diag * (smoothness_percentage / 100.0))

        # Compute extreme indices to preserve
        keep_indices = self._compute_extreme_indices(original_points)

        # RDP simplify while preserving extremes
        simplified = self._rdp_preserve(original_points, epsilon, keep_indices)
        if len(simplified) < 3:
            simplified = original_points

        # Build smoothed path via spline
        try:
            tension = 0.5
            new_path = self._editor_view._create_spline_path(
                simplified, closed_loop=is_closed, tension=tension
            )
        except Exception:
            new_path = self._create_raw_path(simplified, closed=is_closed)

        # Show dual-track overlays
        raw_overlay = self._create_raw_path(original_points, closed=is_closed)
        if hasattr(self._editor_view, "set_raw_overlay_path"):
            raw_pen = QPen(QColor("#6a4c93"), 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            self._editor_view.set_raw_overlay_path(part_name, raw_overlay, raw_pen)

        # Feasibility snapping
        corrected = None
        try:
            corrected = self._apply_feasibility_snapping(part_name, new_path, is_closed)
            if corrected and hasattr(self._editor_view, "set_corrected_overlay_path"):
                self._editor_view.set_corrected_overlay_path(part_name, corrected)
                self._corrected_paths[part_name] = corrected
        except Exception as e:
            logging.debug(f"Feasibility snapping skipped: {e}")

        # Use corrected path if available, otherwise the RDP-smoothed path
        # This ensures the feasibility-adjusted path is the final output
        final_path = corrected if corrected else new_path
        self._update_part_path(part_name, final_path)
        logging.info(f"Regenerated path (RDP) for {part_name} with epsilon={epsilon:.2f}")

    def _apply_smoothness_to_path(
        self, part_name: str, base_path: QPainterPath, smoothness_percentage: int
    ) -> None:
        """
        Apply smoothness to a path (typically from vertex editor).

        Maps smoothness percentage to Catmull-Rom tension:
        - 0% -> tension 0.2 (more angular)
        - 100% -> tension 0.8 (very smooth)

        Args:
            part_name: Name of the part
            base_path: The base path from vertex positions
            smoothness_percentage: Smoothness level (0=angular, 100=smooth)
        """
        # Map smoothness (0-100) to tension (0.2-0.8)
        # Lower tension = more angular, higher tension = smoother
        tension = 0.2 + (smoothness_percentage / 100.0) * 0.6

        # Update vertex editor tension - this rebuilds the path and emits path_modified
        if self._editor_view.is_editing_vertices():
            self._editor_view._path_vertex_editor.set_tension(tension)
            # Get the updated path after tension change
            updated_path = self._editor_view._path_vertex_editor.get_current_path()
            if updated_path:
                is_closed = self._closed_intent_for_part(part_name)
                corrected = self._apply_feasibility_snapping(part_name, updated_path, is_closed)
                self._update_part_path(part_name, corrected or updated_path)
        else:
            # Fallback - just use base path
            is_closed = self._closed_intent_for_part(part_name)
            corrected = self._apply_feasibility_snapping(part_name, base_path, is_closed)
            self._update_part_path(part_name, corrected or base_path)

        # Clear overlays since we're using vertex-based path
        if hasattr(self._editor_view, "clear_overlays_for"):
            self._editor_view.clear_overlays_for(part_name)

        logging.debug(
            f"Applied smoothness {smoothness_percentage}% (tension={tension:.2f}) "
            f"to vertex-based path for {part_name}"
        )

    # --- Geometry Helpers ---

    def _compute_extreme_indices(self, points: list[QPointF]) -> set[int]:
        """
        Detect indices of extremes along principal axis.

        Uses PCA to find major axis and picks local maxima/minima.

        Time Complexity: O(n) for projection, O(n) for extrema detection
        """
        try:
            import numpy as np

            arr = np.array([[p.x(), p.y()] for p in points], dtype=float)
            arr_centered = arr - np.mean(arr, axis=0)
            cov = np.cov(arr_centered.T)
            eigvals, eigvecs = np.linalg.eigh(cov)
            major = eigvecs[:, np.argmax(eigvals)]
            proj = arr_centered @ major
            idxs = self._local_extrema_indices(proj.tolist())
        except Exception:
            # Fallback: use x-axis projection
            vals = [p.x() for p in points]
            idxs = self._local_extrema_indices(vals)

        # Always include endpoints
        idxs.update({0, len(points) - 1})
        return idxs

    @staticmethod
    def _local_extrema_indices(values: list[float]) -> set[int]:
        """Return indices that are local minima or maxima."""
        idxs: set[int] = set()
        n = len(values)
        for i in range(1, n - 1):
            if (values[i] >= values[i - 1] and values[i] >= values[i + 1]) or (
                values[i] <= values[i - 1] and values[i] <= values[i + 1]
            ):
                idxs.add(i)
        return idxs

    def _rdp_preserve(
        self, points: list[QPointF], epsilon: float, keep_indices: set[int]
    ) -> list[QPointF]:
        """
        Ramer-Douglas-Peucker simplification preserving specific indices.

        Time Complexity: O(n²) worst case, O(n log n) average
        """

        def point_line_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
            ax, ay = a.x(), a.y()
            bx, by = b.x(), b.y()
            px, py = p.x(), p.y()
            dx, dy = bx - ax, by - ay
            if dx == 0 and dy == 0:
                return math.hypot(px - ax, py - ay)
            t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            projx, projy = ax + t * dx, ay + t * dy
            return math.hypot(px - projx, py - projy)

        def rdp_segment(start_idx: int, end_idx: int) -> list[int]:
            if end_idx <= start_idx + 1:
                return [start_idx, end_idx]

            a, b = points[start_idx], points[end_idx]
            max_dist = -1.0
            index = -1
            for i in range(start_idx + 1, end_idx):
                d = point_line_distance(points[i], a, b)
                if d > max_dist:
                    max_dist = d
                    index = i

            if max_dist > epsilon or any((start_idx < k < end_idx) for k in keep_indices):
                left = rdp_segment(start_idx, index)
                right = rdp_segment(index, end_idx)
                return left[:-1] + right
            else:
                return [start_idx, end_idx]

        n = len(points)
        internal_keeps = sorted([k for k in keep_indices if 0 < k < n - 1])
        segments = []
        prev = 0
        for k in internal_keeps:
            segments.append((prev, k))
            prev = k
        segments.append((prev, n - 1))

        selected: set[int] = set()
        for s, e in segments:
            seg_idxs = rdp_segment(s, e)
            selected.update(seg_idxs)

        final_indices = sorted(selected)
        return [points[i] for i in final_indices]

    def _apply_feasibility_snapping(
        self, part_name: str, path: QPainterPath, is_closed: bool = True
    ) -> QPainterPath | None:
        """
        Apply feasibility correction based on IK constraints.

        Projects path points onto the reachable annulus defined by
        the two-bone IK chain (root->mid->effector).
        """
        try:
            main_window = self._get_main_window()
            ik = getattr(main_window, "ik_manager", None) if main_window else None
            if not ik or not hasattr(ik, "sim_joints_config"):
                return None

            # Find end-effector joint for this part
            eff_abs = None
            for comp in getattr(ik, "sim_selectable_components", []) or []:
                if comp.get("partName") == part_name:
                    eff_abs = comp.get("targetJointId")
                    break

            if not eff_abs:
                return None

            # Resolve parent and root anchors
            mid_abs = ik.sim_limb_configs.get(eff_abs, {}).get("parentAnchor")
            if not mid_abs:
                return None
            root_abs = ik.sim_limb_configs.get(mid_abs, {}).get("parentAnchor") or mid_abs

            # Get standardized joint IDs
            def std_id_of(abs_name: str) -> str:
                try:
                    return str(ik._get_standardized_joint_id(abs_name))
                except Exception:
                    return abs_name

            eff_id = std_id_of(eff_abs)
            mid_id = std_id_of(mid_abs)
            root_id = std_id_of(root_abs)

            for jid in (eff_id, mid_id, root_id):
                if jid not in ik.sim_joints_config:
                    return None

            root_pos = ik.sim_joints_config[root_id]["position"]
            mid_pos = ik.sim_joints_config[mid_id]["position"]
            eff_pos = ik.sim_joints_config[eff_id]["position"]

            # Calculate bone lengths
            l1 = math.hypot(root_pos.x() - mid_pos.x(), root_pos.y() - mid_pos.y())
            l2 = math.hypot(mid_pos.x() - eff_pos.x(), mid_pos.y() - eff_pos.y())

            if l1 <= 1e-6 or l2 <= 1e-6:
                return None

            # Feasible radii with tolerance
            tol = 0.05
            r_min = max(0.0, abs(l1 - l2) * (1.0 - tol))
            r_max = (l1 + l2) * (1.0 + tol)

            # Project sampled points onto annulus
            corrected = QPainterPath()
            any_change = False
            samples = max(24, min(240, int(max(path.length(), 1.0) / 4.0)))

            for i in range(samples):
                t = i / (samples - 1) if samples > 1 else 0.0
                p = path.pointAtPercent(t)
                dx = p.x() - root_pos.x()
                dy = p.y() - root_pos.y()
                d = math.hypot(dx, dy)

                if d < 1e-6:
                    nx, ny = r_min, 0.0
                    any_change = True
                elif d < r_min:
                    s = r_min / d
                    nx, ny = dx * s, dy * s
                    any_change = True
                elif d > r_max:
                    s = r_max / d
                    nx, ny = dx * s, dy * s
                    any_change = True
                else:
                    nx, ny = dx, dy

                cx = root_pos.x() + nx
                cy = root_pos.y() + ny

                if i == 0:
                    corrected.moveTo(cx, cy)
                else:
                    corrected.lineTo(cx, cy)

            if is_closed:
                corrected.closeSubpath()
            return corrected if any_change else None

        except Exception as e:
            logging.debug(f"Feasibility snapping error: {e}")
            return None

    def apply_corrections_for_all_parts(self) -> None:
        """Auto-apply feasibility-corrected paths for all cached parts."""
        if not self._corrected_paths:
            return

        for part, corrected in list(self._corrected_paths.items()):
            try:
                if corrected is None:
                    continue
                self._update_part_path(part, corrected)
                if hasattr(self._editor_view, "clear_corrected_overlay_for"):
                    self._editor_view.clear_corrected_overlay_for(part)
                self._corrected_paths.pop(part, None)
            except Exception as e:
                logging.debug(f"Failed to apply correction for {part}: {e}")

    # --- Path Data Access ---

    def _get_original_path_points(self, part_name: str) -> list[QPointF]:
        """Get original drawn points for a part."""
        editor_items = self._get_editor_items()

        if part_name in editor_items:
            part_item = editor_items[part_name]
            if hasattr(part_item, "original_path_points") and part_item.original_path_points:
                return cast("list[QPointF]", part_item.original_path_points)

            if hasattr(part_item, "motion_path") and part_item.motion_path:
                return self._extract_points_from_path(part_item.motion_path)

        return []

    @staticmethod
    def _extract_points_from_path(path: QPainterPath) -> list[QPointF]:
        """Extract points from a QPainterPath by sampling."""
        points = []
        length = path.length()
        if length > 0:
            num_samples = min(12, max(6, int(length / 20)))
            for i in range(num_samples):
                percent = i / (num_samples - 1) if num_samples > 1 else 0
                points.append(path.pointAtPercent(percent))
        return points

    @staticmethod
    def _create_raw_path(points: list[QPointF], closed: bool = True) -> QPainterPath:
        """Create a path from raw points connected by lines."""
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if closed and len(points) > 2:
                path.lineTo(points[0])
        return path

    def _closed_intent_for_part(self, part_name: str) -> bool:
        if part_name in self._path_closed_intent:
            return self._path_closed_intent[part_name]
        return self._closed_path_radio.isChecked() if self._closed_path_radio else True

    def _snap_path_if_needed(
        self, part_name: str, path: QPainterPath, is_closed: bool
    ) -> QPainterPath:
        try:
            corrected = self._apply_feasibility_snapping(part_name, path, is_closed)
        except Exception as e:
            logging.debug(f"Feasibility snapping skipped: {e}")
            return path
        if corrected and not corrected.isEmpty():
            self._corrected_paths[part_name] = corrected
            if hasattr(self._editor_view, "set_corrected_overlay_path"):
                self._editor_view.set_corrected_overlay_path(part_name, corrected)
            return corrected
        return path

    def _create_perfect_ellipse_path(self, points: list[QPointF]) -> QPainterPath:
        """Create a perfect ellipse fitted to points using PCA."""
        if not points:
            return QPainterPath()

        import numpy as np

        coords = np.array([[p.x(), p.y()] for p in points])
        center = np.mean(coords, axis=0)
        center_x, center_y = center[0], center[1]

        centered_coords = coords - center
        cov_matrix = np.cov(centered_coords.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        sorted_indices = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_indices]
        eigenvectors = eigenvectors[:, sorted_indices]

        major_axis = eigenvectors[:, 0]

        major_projections = np.dot(centered_coords, major_axis)
        minor_projections = np.dot(centered_coords, eigenvectors[:, 1])

        major_radius = max(10.0, 1.2 * np.std(major_projections))
        minor_radius = max(10.0, 1.2 * np.std(minor_projections))

        rotation_angle = math.atan2(major_axis[1], major_axis[0])

        path = QPainterPath()
        num_points = max(36, len(points) * 3)

        for i in range(num_points + 1):
            t = 2 * math.pi * i / num_points
            local_x = major_radius * math.cos(t)
            local_y = minor_radius * math.sin(t)

            cos_rot = math.cos(rotation_angle)
            sin_rot = math.sin(rotation_angle)
            rotated_x = local_x * cos_rot - local_y * sin_rot
            rotated_y = local_x * sin_rot + local_y * cos_rot

            x = center_x + rotated_x
            y = center_y + rotated_y

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        return path

    def _update_part_path(self, part_name: str, new_path: QPainterPath) -> None:
        """
        Update motion path across all data structures and emit signals.

        This is the central method for path updates. It ensures:
        1. CharacterPartItem is updated
        2. Project data manager is updated
        3. Visual path in EditorView is updated
        4. Signals are emitted to notify mechanism design tab
        """
        editor_items = self._get_editor_items()

        # Update CharacterPartItem
        if part_name in editor_items:
            editor_items[part_name].set_motion_path(new_path)

        # Update project data
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, "project_data_manager"):
            current_parts = self._parts_data_from_project_manager(main_window.project_data_manager)
            if current_parts and part_name in current_parts:
                current_parts[part_name].motion_path = new_path

        # Update visual path in EditorView
        if (
            hasattr(self._editor_view, "final_paths_map")
            and part_name in self._editor_view.final_paths_map
        ):
            path_item = self._editor_view.final_paths_map[part_name]
            if path_item:
                path_item.setPath(new_path)

        # Emit signals to notify mechanism design tab and other listeners
        self.motion_path_updated.emit(part_name, new_path)
        self._emit_path_data()

    # --- Vertex Handles ---

    def _show_vertex_handles(
        self, part_name: str, path: QPainterPath, is_closed: bool = True
    ) -> None:
        """
        Show draggable vertex handles for a motion path.

        Args:
            part_name: Name of the part whose path is being edited
            path: The QPainterPath to show handles for
            is_closed: Whether the path is closed
        """
        if path.isEmpty():
            logging.warning(f"_show_vertex_handles: Path is empty for '{part_name}'")
            return

        logging.debug(
            f"_show_vertex_handles: Starting for '{part_name}', path length={path.length():.1f}"
        )

        # Start vertex editing via EditorView
        result = self._editor_view.start_vertex_editing(part_name, path, is_closed)
        logging.debug(f"_show_vertex_handles: Vertex editing started: {result}")

        # Apply current smoothness slider value as initial tension
        if result and self._smoothness_slider:
            smoothness = self._smoothness_slider.value()
            tension = 0.2 + (smoothness / 100.0) * 0.6
            self._editor_view._path_vertex_editor.set_tension(tension)
            logging.debug(f"Applied initial tension {tension:.2f} from smoothness {smoothness}%")

    def hide_vertex_handles(self, save_changes: bool = False) -> None:
        """Hide all vertex handles.

        Args:
            save_changes: Whether to save path changes before hiding
        """
        if self._editor_view.is_editing_vertices():
            if save_changes:
                # Get final path before stopping
                part_name = self._editor_view.get_vertex_edit_part_name()
                final_path = self._editor_view.stop_vertex_editing()
                if final_path and part_name:
                    self._update_part_path(part_name, final_path)
            else:
                # Just clear without saving/emitting
                self._editor_view._path_vertex_editor.stop_editing(emit_signal=False)
                self._editor_view._current_vertex_edit_part = None

    def show_vertex_handles_for_selected_part(self) -> None:
        """Show vertex handles for the currently selected part if it has a path."""
        part_name = self._get_selected_part()
        if not part_name:
            logging.debug("show_vertex_handles: No part selected")
            return

        # Hide any existing handles first
        self.hide_vertex_handles()

        # Check if part has a motion path
        if not self._has_motion_path(part_name):
            logging.debug(f"show_vertex_handles: Part '{part_name}' has no motion path")
            return

        # Get the path
        path: QPainterPath | None = None
        editor_items = self._get_editor_items()

        if part_name in editor_items:
            part_item = editor_items[part_name]
            if hasattr(part_item, "motion_path") and part_item.motion_path:
                path = part_item.motion_path
                logging.debug("show_vertex_handles: Got path from part_item.motion_path")

        if not path or path.isEmpty():
            if hasattr(self._editor_view, "final_paths_map"):
                path_item = self._editor_view.final_paths_map.get(part_name)
                if path_item:
                    path = path_item.path()
                    logging.debug("show_vertex_handles: Got path from final_paths_map")

        if path and not path.isEmpty():
            is_closed = self._closed_intent_for_part(part_name)
            logging.info(
                f"show_vertex_handles: Showing handles for '{part_name}', path length={path.length():.1f}"
            )
            self._show_vertex_handles(part_name, path, is_closed)
        else:
            logging.debug(f"show_vertex_handles: No valid path found for '{part_name}'")
