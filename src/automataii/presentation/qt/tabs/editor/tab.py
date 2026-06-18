import logging
from typing import Any

from PyQt6.QtCore import QItemSelectionModel, QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QWidget,
)

from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.models import PartInfo

# Extracted components (god class decomposition)
from automataii.presentation.qt.tabs.editor.components.motion_path_manager import (
    MotionPathManager,
)
from automataii.presentation.qt.tabs.editor.components.parts_data_manager import (
    PartsDataManager,
)
from automataii.presentation.qt.tabs.editor.components.path_geometry import (
    create_interpolated_path,
    create_perfect_ellipse_path,
    create_raw_path,
    extract_points_from_path,
)
from automataii.presentation.qt.tabs.editor.components.path_query_service import (
    PathQueryService,
)
from automataii.presentation.qt.tabs.editor.components.simulation_controller import (
    SimulationController,
)
from automataii.presentation.qt.tabs.editor.components.skeleton_ik_handler import (
    SkeletonIKHandler,
)
from automataii.presentation.qt.tabs.editor.components.ui_builder import (
    EditorTabUIBuilder,
)
from automataii.presentation.qt.tabs.editor.components.view_controls import ViewControls
from automataii.presentation.qt.views.editor_view import EditorView


class EditorTab(QWidget):
    # Signals this tab might emit
    request_define_joint = pyqtSignal(
        str, str
    )  # part1_name, part2_name (or use view's signal directly in MW)
    request_save_alignment = pyqtSignal()
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()
    request_generate_blueprint = pyqtSignal()
    parts_cleared = pyqtSignal()  # Emitted when parts are cleared from this tab's perspective
    parts_loaded = pyqtSignal(bool)  # Emitted when parts are loaded/cleared (True if loaded)
    request_reset_all_animations = pyqtSignal()  # New signal
    motion_path_updated = pyqtSignal(str, QPainterPath)  # part_name, path
    path_data_changed = pyqtSignal(dict)  # Dict[str, QPainterPath] for cross-tab communication

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = (
            main_window  # Reference to MainWindow for global actions, data, status bar
        )
        self.debug_mode = getattr(
            main_window, "debug_mode", False
        )  # Get debug_mode from main_window

        # Instantiate scene and view here
        self.editor_scene = QGraphicsScene(self)
        self.editor_view = EditorView(
            self.editor_scene, self
        )  # Pass self (EditorTab) as parent to EditorView

        # --- UI Elements owned by this tab ---
        self.parts_list: QListWidget | None = None
        self.define_motion_path_btn: QPushButton | None = None
        self.clear_motion_path_btn: QPushButton | None = None
        self.motion_path_status_label: QLabel | None = None
        self.motion_path_info_label: QLabel | None = None
        self.animation_status_label: QLabel | None = None
        self.generate_mechanisms_btn: QPushButton | None = None
        self.smoothness_slider: QSlider | None = None
        self.smoothness_value_label: QLabel | None = None

        self.play_btn: QPushButton | None = None
        self.stop_btn: QPushButton | None = None
        self.reset_sim_btn: QPushButton | None = None

        # Data specific to this tab
        self.selected_part_name: str | None = None
        self.current_parts_info: dict[str, PartInfo] = {}
        self.current_editor_items: dict[str, CharacterPartItem] = {}

        # Store for defined joints within this tab
        self.joints: list[dict] = []  # List of joint data dictionaries

        # Cache for initial skeleton data, to be set by MainWindow
        self._initial_skeleton_data_cache: dict | None = None

        self.current_simulation_state: str = "stopped"  # For logging IK updates
        self.ik_log_counter: dict[str, int] = {}  # To limit logs per part/state

        self._init_ui()

        # Connect signals from self.editor_view now that it exists
        self._connect_editor_view_signals()

        # Storage for feasibility-corrected candidate paths (per part)
        self._corrected_paths: dict[str, QPainterPath] = {}

        # Initialize extracted components
        self._init_extracted_components()

        # Configure extracted components (must be after both _init_ui and _init_extracted_components)
        self._configure_simulation_controller()
        self._configure_motion_path_manager()
        self._configure_parts_data_manager()
        self._configure_skeleton_ik_handler()

    def _connect_editor_view_signals(self):
        """Connect signals from this tab's EditorView instance."""
        self.editor_view.freehandPathCompleted.connect(self._handle_freehand_path_completed)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        self.editor_view.joint_defined.connect(self.handle_joint_defined)
        self.editor_view.zoom_changed.connect(self._update_zoom_combo_from_view)

        # Connect to new EditorView signals for item interactions
        self.editor_view.part_item_clicked.connect(self._handle_part_item_clicked_from_view)
        self.editor_view.part_item_double_clicked.connect(
            self._handle_part_item_double_clicked_from_view
        )
        # self.editor_view.part_item_moved.connect(self._handle_part_item_moved_from_view) # Deferred

        # Connect joint bend direction change signal
        self.editor_view.joint_bend_direction_changed.connect(
            self._handle_joint_bend_direction_changed
        )

        # Connect vertex editing signals
        self.editor_view.path_vertices_modified.connect(self._handle_vertex_path_modified)
        self.editor_view.vertex_editing_finished.connect(self._handle_vertex_editing_finished)

    def _init_extracted_components(self):
        """Initialize extracted components from god class decomposition."""
        # Path Query Service - pure query functions
        self._path_query_service = PathQueryService(
            editor_items=self.current_editor_items,
            parts_info=self.current_parts_info,
            editor_view=self.editor_view,
        )

        # View Controls - zoom, pan, reset operations
        self._view_controls = ViewControls(
            editor_view=self.editor_view,
            editor_scene=self.editor_scene,
            parent=self,
        )

        # Simulation Controller - play/stop/reset animation
        self._simulation_controller = SimulationController(
            editor_view=self.editor_view,
            editor_scene=self.editor_scene,
            parent=self,
        )

        # Wire simulation controller signals to EditorTab signals
        self._simulation_controller.request_play.connect(self.request_play_simulation.emit)
        self._simulation_controller.request_stop.connect(self.request_stop_simulation.emit)
        self._simulation_controller.request_reset.connect(self.request_reset_simulation.emit)

        # Motion Path Manager - path drawing, smoothing, and manipulation
        self._motion_path_manager = MotionPathManager(
            editor_view=self.editor_view,
            editor_scene=self.editor_scene,
            parent=self,
        )

        # Wire motion path manager signals to EditorTab signals
        self._motion_path_manager.motion_path_updated.connect(self.motion_path_updated.emit)
        self._motion_path_manager.path_data_changed.connect(self.path_data_changed.emit)

        # Parts Data Manager - parts list and data management
        self._parts_data_manager = PartsDataManager(
            editor_view=self.editor_view,
            editor_scene=self.editor_scene,
            parent=self,
        )

        # Wire parts data manager signals to EditorTab signals
        self._parts_data_manager.parts_loaded.connect(self.parts_loaded.emit)
        self._parts_data_manager.parts_cleared.connect(self.parts_cleared.emit)

        # Skeleton IK Handler - skeleton updates, IK results, joint management
        self._skeleton_ik_handler = SkeletonIKHandler(
            editor_view=self.editor_view,
            editor_scene=self.editor_scene,
            parent=self,
        )

        # Wire skeleton handler signals (skeleton_updated used internally)
        self._skeleton_ik_handler.skeleton_updated.connect(self._update_button_states)

    def _configure_simulation_controller(self):
        """Configure simulation controller after UI is built."""
        if not hasattr(self, "_simulation_controller"):
            return

        self._simulation_controller.configure_ui(
            play_btn=self.play_btn,
            stop_btn=self.stop_btn,
            reset_btn=self.reset_sim_btn,
            status_label=self.animation_status_label,
            smoothness_slider=self.smoothness_slider,
        )

        self._simulation_controller.configure_callbacks(
            has_editor_items=lambda: bool(self.current_editor_items),
            has_any_path=self._has_any_motion_path,
            get_path_count=self._get_path_count,
            apply_corrections=lambda: self._motion_path_manager.apply_corrections_for_all_parts()
            if hasattr(self, "_motion_path_manager")
            else None,
            position_parts_at_anchor=self._position_parts_at_anchor_joints,
            on_skeleton_updated=self.on_skeleton_updated,
            update_part_list_styles=self._update_part_list_styles,
            initial_skeleton_cache_getter=lambda: self._initial_skeleton_data_cache,
        )

    def _configure_motion_path_manager(self):
        """Configure motion path manager after UI is built."""
        if not hasattr(self, "_motion_path_manager"):
            return

        self._motion_path_manager.configure_ui(
            define_btn=self.define_motion_path_btn,
            clear_btn=self.clear_motion_path_btn,
            status_label=self.motion_path_status_label,
            info_label=self.motion_path_info_label,
            smoothness_slider=self.smoothness_slider,
            smoothness_label=self.smoothness_value_label,
            closed_path_radio=self.closed_path_radio,
            edit_vertices_btn=getattr(self, "edit_vertices_btn", None),
        )

        self._motion_path_manager.configure_callbacks(
            get_selected_part=lambda: self.selected_part_name,
            get_editor_items=lambda: self.current_editor_items,
            get_parts_info=lambda: self.current_parts_info,
            get_main_window=lambda: self.main_window,
            update_button_states=self._update_button_states,
            has_motion_path=self._has_motion_path,
            emit_path_data=self._emit_path_data,
        )

    def _configure_parts_data_manager(self):
        """Configure parts data manager after UI is built."""
        if not hasattr(self, "_parts_data_manager"):
            return

        self._parts_data_manager.configure_ui(parts_list=self.parts_list)

        self._parts_data_manager.configure_callbacks(
            get_main_window=lambda: self.main_window,
            get_debug_mode=lambda: self.debug_mode,
            get_skeleton_cache=lambda: self._initial_skeleton_data_cache,
            set_skeleton_cache=lambda x: setattr(self, "_initial_skeleton_data_cache", x),
            update_button_states=self._update_button_states,
            update_part_list_styles=self._update_part_list_styles,
            update_active_part_visuals=self._update_active_part_visuals,
            emit_path_data=self._emit_path_data,
            validate_position=self._validate_part_position,
        )

    def _configure_skeleton_ik_handler(self):
        """Configure skeleton IK handler after UI is built."""
        if not hasattr(self, "_skeleton_ik_handler"):
            return

        self._skeleton_ik_handler.configure_callbacks(
            get_editor_items=lambda: self.current_editor_items,
            get_parts_info=lambda: self.current_parts_info,
            get_main_window=lambda: self.main_window,
            update_button_states=self._update_button_states,
            update_part_list_styles=self._update_part_list_styles,
            update_active_part_visuals=self._update_active_part_visuals,
        )

    def _init_ui(self):
        """Initialize the EditorTab UI using the UI builder."""
        # Build UI using extracted builder
        builder = EditorTabUIBuilder(self, self.editor_view)
        refs = builder.build()

        # Store widget references from builder
        self.parts_list = refs.parts_list
        self.define_motion_path_btn = refs.define_motion_path_btn
        self.clear_motion_path_btn = refs.clear_motion_path_btn
        self.edit_vertices_btn = getattr(refs, "edit_vertices_btn", None)
        self.motion_path_status_label = refs.motion_path_status_label
        self.motion_path_info_label = refs.motion_path_info_label
        self.smoothness_slider = refs.smoothness_slider
        self.smoothness_value_label = refs.smoothness_value_label
        self.closed_path_radio = refs.closed_path_radio
        self.open_path_radio = refs.open_path_radio
        self.path_type_group = refs.path_type_group
        self.animation_status_label = refs.animation_status_label
        self.play_btn = refs.play_btn
        self.stop_btn = refs.stop_btn
        self.reset_sim_btn = refs.reset_sim_btn
        self.zoom_in_btn = refs.zoom_in_btn
        self.zoom_out_btn = refs.zoom_out_btn
        self.zoom_fit_btn = refs.zoom_fit_btn
        self.center_character_btn = refs.center_character_btn

        # Connect signals
        self._connect_ui_signals()

    def _connect_ui_signals(self):
        """Connect UI widget signals to handlers."""
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.define_motion_path_btn.toggled.connect(self._toggle_define_motion_path_mode)
        self.clear_motion_path_btn.clicked.connect(self._clear_selected_item_motion_path)
        if self.edit_vertices_btn:
            self.edit_vertices_btn.toggled.connect(self._toggle_vertex_edit_mode)
        self.play_btn.clicked.connect(self._play_simulation_clicked)
        self.stop_btn.clicked.connect(self._stop_simulation_clicked)
        self.reset_sim_btn.clicked.connect(self._reset_simulation_clicked)

        # Connect smoothness slider with debounce (100ms) to avoid expensive RDP on every tick
        self._smoothness_debounce_timer = QTimer()
        self._smoothness_debounce_timer.setSingleShot(True)
        self._smoothness_debounce_timer.setInterval(100)
        self._smoothness_debounce_timer.timeout.connect(self._on_smoothness_changed_debounced)
        self._pending_smoothness_value: int = 0
        self.smoothness_slider.valueChanged.connect(self._on_smoothness_value_changed)

        # Connect zoom controls
        self.zoom_in_btn.clicked.connect(lambda: self.editor_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.editor_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.editor_view.zoom_to_fit)
        self.center_character_btn.clicked.connect(self.center_on_character)

    def _handle_part_selection_change(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ):
        """Handles selection changes from the parts_list QListWidget."""
        logging.debug(f"EditorTab: Part selection changed. Current item: {current}")
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)  # Get part name from item data
            logging.debug(f"EditorTab: Part name from UserRole: {part_name}")
            logging.debug(f"EditorTab: Available parts: {list(self.current_editor_items.keys())}")

            if part_name:
                self.selected_part_name = part_name

                # If the part exists in editor items, highlight it in the scene
                if part_name in self.current_editor_items:
                    item_to_select = self.current_editor_items[part_name]
                    self.editor_scene.clearSelection()  # Clear previous scene selection
                    item_to_select.setSelected(True)  # Select the item in the scene
                    logging.info(
                        f"EditorTab: Part '{part_name}' selected and highlighted in scene."
                    )
                else:
                    self.editor_scene.clearSelection()
                    logging.debug(
                        f"EditorTab: Part '{part_name}' selected but not yet loaded in scene."
                    )
            else:
                self.selected_part_name = None
                self.editor_scene.clearSelection()
                logging.warning("EditorTab: No part name found in UserRole data")
        else:
            self.selected_part_name = None
            self.editor_scene.clearSelection()
            logging.debug("EditorTab: No part selected")

        self.update_part_properties_panel(self.selected_part_name)
        self._update_button_states()

        if self.selected_part_name:
            self.motion_path_status_label.setText(self.selected_part_name)
        else:
            self.motion_path_status_label.setText("Select a part")

        # Update part list styles whenever selection changes
        self._update_part_list_styles()

        # Show vertex handles for selected part if it has a motion path
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.show_vertex_handles_for_selected_part()

    def _toggle_define_motion_path_mode(self, checked: bool):
        """Handle the 'Start/Stop Drawing' button toggle. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.toggle_define_mode(checked)
        else:
            # Fallback for initialization order edge cases
            logging.warning("MotionPathManager not initialized, cannot toggle define mode")

    def _clear_selected_item_motion_path(self):
        """Clear motion path for selected item. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.clear_selected_motion_path()
        else:
            logging.warning("MotionPathManager not initialized, cannot clear motion path")

    def _toggle_vertex_edit_mode(self, checked: bool):
        """Handle vertex edit mode toggle. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.toggle_vertex_edit_mode(checked)

    def _handle_vertex_path_modified(self, part_name: str, new_path: QPainterPath):
        """Handle real-time path modification from vertex dragging."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.on_vertex_path_modified(part_name, new_path)

    def _handle_vertex_editing_finished(self, part_name: str, final_path: QPainterPath):
        """Handle completion of vertex editing."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.on_vertex_editing_finished(part_name, final_path)

    def _play_simulation_clicked(self):
        # 🔧 PART MOVEMENT LOCK: Lock part movement during animation
        self._lock_part_movement(True)

        # Auto-apply feasibility snapping for all parts before playing
        try:
            self._apply_corrections_for_all_parts()
        except Exception as e:
            logging.debug(f"Auto-apply feasibility corrections failed: {e}")

        # Always emit the signal so IK manager knows we're playing
        self.request_play_simulation.emit()

    def _stop_simulation_clicked(self):
        logging.info("Stop button clicked")

        # 🔧 PART MOVEMENT UNLOCK: Unlock part movement when animation stops
        self._lock_part_movement(False)

        self.request_stop_simulation.emit()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(True)

    def _reset_simulation_clicked(self):
        # 🔧 PART MOVEMENT UNLOCK: Unlock part movement when animation resets
        self._lock_part_movement(False)

        self.request_reset_simulation.emit()

        # Reset parts to original positions
        if self._initial_skeleton_data_cache:
            self._position_parts_at_anchor_joints()
            self.on_skeleton_updated(self._initial_skeleton_data_cache.copy())
            logging.info("EditorTab: Skeleton and parts reset to cached initial state.")
        else:
            logging.warning("EditorTab: No cached initial skeleton data for reset.")

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False)
        self._update_button_states()

        self.editor_scene.update()

    def _lock_part_movement(self, lock: bool):
        """Lock or unlock part movement by disabling view interactions."""
        if lock:
            # 🔒 LOCK: Disable part movement during animation
            self.editor_view.setInteractive(False)
            self.editor_view.setDragMode(self.editor_view.DragMode.NoDrag)
            self.editor_view.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
            logging.info("EditorTab: Part movement LOCKED during animation")
        else:
            # 🔓 UNLOCK: Enable part movement when animation stops
            self.editor_view.setInteractive(True)
            self.editor_view.setDragMode(self.editor_view.DragMode.RubberBandDrag)
            self.editor_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            logging.info("EditorTab: Part movement UNLOCKED")

    def _update_zoom_combo_from_view(self, scale_factor: float):
        # This functionality is removed from the UI
        pass

    def populate_parts_list(self, part_names: list[str]):
        """Populate the parts list widget with given names."""
        self.parts_list.clear()
        disabled_parts = {
            "torso",
            "left_arm_upper",
            "right_arm_upper",
            "left_leg_upper",
            "right_leg_upper",
        }

        for part_name in part_names:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)

            # 🔧 upper 파츠들과 torso 비활성화
            if any(disabled_part in part_name.lower() for disabled_part in disabled_parts):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # 선택 불가
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)  # 비활성화

                # 시각적으로 비활성화 표시
                item.setForeground(QBrush(QColor(150, 150, 150)))  # 회색 텍스트
                item.setBackground(QBrush(QColor(240, 240, 240)))  # 연한 회색 배경
            else:
                self.parts_list.addItem(item)
        self._update_button_states()
        self._update_part_list_styles()
        self._update_active_part_visuals()

    def update_part_properties_panel(self, part_name: str | None):
        # This panel is now removed. This function can be kept as a no-op for now.
        pass

    def _update_button_states(self):
        """Update the enabled/disabled state of all buttons based on current state."""
        selected = self.selected_part_name is not None
        has_any_path = self._has_any_motion_path()
        selected_part_has_path = selected and self._has_motion_path(self.selected_part_name)

        logging.debug(
            f"EditorTab: Updating button states - selected: {selected}, selected_part: {self.selected_part_name}, has_path: {selected_part_has_path}"
        )

        # Motion Path section
        self.define_motion_path_btn.setEnabled(selected)
        self.clear_motion_path_btn.setEnabled(selected_part_has_path)

        # Smoothness slider - enable only when a part with path is selected
        if self.smoothness_slider:
            self.smoothness_slider.setEnabled(selected_part_has_path)

        logging.debug(
            f"EditorTab: Start Drawing button enabled: {selected}, Clear button enabled: {selected_part_has_path}"
        )

        # Animation section
        self.play_btn.setEnabled(has_any_path)
        self.stop_btn.setEnabled(has_any_path and self.current_simulation_state == "playing")
        self.reset_sim_btn.setEnabled(has_any_path)

        # Update animation status label
        if has_any_path:
            path_count = self._get_path_count()
            self.animation_status_label.setText(f"{path_count} motion path(s) defined")
        else:
            self.animation_status_label.setText("No motion paths defined")

        # Update part list styles to show orange background for parts with paths
        self._update_part_list_styles()

    def _has_any_motion_path(self) -> bool:
        """Check if any part has a motion path defined."""
        for part_item in self.current_editor_items.values():
            if (
                hasattr(part_item, "motion_path")
                and part_item.motion_path
                and not part_item.motion_path.isEmpty()
            ):
                return True
        return False

    def _has_motion_path(self, part_name: str) -> bool:
        """Check if a specific part has a motion path defined."""
        if not part_name:
            return False

        # Check in EditorView's final paths map first (green paths)
        if (
            hasattr(self.editor_view, "final_paths_map")
            and part_name in self.editor_view.final_paths_map
        ):
            path_item = self.editor_view.final_paths_map[part_name]
            if path_item and path_item.scene():
                return True

        # Check in current_editor_items
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if (
                hasattr(part_item, "motion_path")
                and part_item.motion_path
                and not part_item.motion_path.isEmpty()
            ):
                return True

        # Also check in current_parts_info (project data)
        if part_name in self.current_parts_info:
            part_info = self.current_parts_info[part_name]
            if hasattr(part_info, "motion_path") and part_info.motion_path:
                if hasattr(part_info.motion_path, "isEmpty"):
                    return not part_info.motion_path.isEmpty()
                elif isinstance(part_info.motion_path, list):
                    return len(part_info.motion_path) > 0
                else:
                    return part_info.motion_path is not None

        return False

    def _get_path_count(self) -> int:
        """Get the total number of motion paths defined."""
        count = 0
        for part_item in self.current_editor_items.values():
            if (
                hasattr(part_item, "motion_path")
                and part_item.motion_path
                and not part_item.motion_path.isEmpty()
            ):
                count += 1
        return count

    @staticmethod
    def _parts_data_from_project_manager(project_data_manager: Any) -> Any:
        """Return project parts from the full SSOT manager or a lightweight fallback.

        Several Editor operations run during startup, tests, or teardown when
        the parent window may expose only a minimal project-data object. This
        lookup must not raise inside UI callbacks.
        """
        get_current_parts_data = getattr(project_data_manager, "get_current_parts_data", None)
        if callable(get_current_parts_data):
            try:
                return get_current_parts_data()
            except Exception:
                logging.debug("Project parts lookup failed", exc_info=True)
                return None
        return getattr(project_data_manager, "parts", None)

    def _update_part_list_styles(self):
        """Update item backgrounds to show which parts have paths."""
        # Create sophisticated brushes for parts with and without paths
        orange_brush = QBrush(QColor(255, 165, 0, 100))  # Semi-transparent orange background
        transparent_brush = QBrush(QColor(Qt.GlobalColor.transparent))

        for i in range(self.parts_list.count()):
            item = self.parts_list.item(i)
            # Get the actual part name from UserRole data (stored in populate_parts_list)
            part_name = item.data(Qt.ItemDataRole.UserRole)
            if not part_name:  # Fallback if UserRole data not set
                part_name = item.text().replace(" ●", "")  # Remove indicator if present

            has_path = self._has_motion_path(part_name)

            if has_path:
                # Set orange background for parts with paths
                item.setBackground(orange_brush)
                # Add visual indicator
                if not item.text().endswith(" ●"):
                    item.setText(f"{part_name} ●")  # Add bullet point to indicate path
            else:
                # Reset to transparent background
                item.setBackground(transparent_brush)
                # Remove indicator if it exists
                if item.text().endswith(" ●"):
                    item.setText(part_name)

    def _update_active_part_visuals(self):
        """Update the visual state of CharacterPartItems in the scene."""
        for name, item in self.current_editor_items.items():
            has_path = self._has_motion_path(name)
            item.set_active(has_path)

    def set_parts_data(self, parts_info: dict[str, PartInfo]):
        """Receives parts data and populates the editor."""
        self.clear_editor_content()  # Clear previous content first

        self.current_parts_info = parts_info if parts_info else {}
        created_editor_items: dict[str, CharacterPartItem] = {}

        if not self.current_parts_info:
            logging.info("EditorTab: No parts data to set.")
            self.parts_loaded.emit(False)
            self.populate_parts_list(list(self.current_parts_info.keys()))
            self._update_button_states()
            return

        project_dir = None
        if (
            self.main_window
            and hasattr(self.main_window, "project_data_manager")
            and self.main_window.project_data_manager.project_dir
        ):
            project_dir = self.main_window.project_data_manager.project_dir
        elif (
            self.main_window
            and hasattr(self.main_window, "project_state_manager")
            and self.main_window.project_state_manager.state.project_dir
        ):
            project_dir = self.main_window.project_state_manager.state.project_dir
        else:
            logging.error(
                "EditorTab: Project directory not available from ProjectDataManager or ProjectStateManager. Part items may not load correctly."
            )
            # Show a message to the user, as this is critical
            QMessageBox.critical(
                self,
                "Error",
                "Project directory is missing. Cannot load part textures.",
            )
            self.parts_loaded.emit(False)
            self.populate_parts_list(list(self.current_parts_info.keys()))
            self._update_button_states()
            return

        for part_name, p_info in self.current_parts_info.items():
            # CharacterPartItem now loads its own texture using project_dir and p_info.name
            item = CharacterPartItem(
                part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode
            )  # Pass debug_mode
            item.set_user_movable(False)
            item.setToolTip("Select this part, then use Start Drawing Path to animate it.")

            # Parts are cropped images that should start at 0° rotation
            # The skeleton joint angles are for the bones, not the visual parts
            # Keep the default rotation of 0° as set in CharacterPartItem.__init__

            self.editor_scene.addItem(item)
            created_editor_items[part_name] = item

            # Position parts at their anchor joints if skeleton data is available
            # If anchor_joint_id is not set, try to get it from BODY_PARTS definitions
            anchor_joint_id = p_info.anchor_joint_id
            if not anchor_joint_id:
                # Import BODY_PARTS as a fallback
                try:
                    from automataii.domain.animation.part_definitions import BODY_PARTS

                    part_def = BODY_PARTS.get(part_name, {})
                    anchor_joint_id = part_def.get("anchor_joint")
                    if anchor_joint_id:
                        logging.info(
                            f"EditorTab: Using fallback anchor_joint '{anchor_joint_id}' for part '{part_name}' from BODY_PARTS"
                        )
                except ImportError:
                    logging.warning(
                        "EditorTab: Could not import BODY_PARTS for fallback anchor joint lookup"
                    )

            if anchor_joint_id and self._initial_skeleton_data_cache:
                joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
                joints_dict = self._initial_skeleton_data_cache.get("joints", {})

                # Find standardized joint ID from original anchor_joint_id
                std_joint_id = None
                for orig_name, std_id in joint_map.items():
                    if orig_name == anchor_joint_id:
                        std_joint_id = std_id
                        break

                if std_joint_id and std_joint_id in joints_dict:
                    joint_data = joints_dict[std_joint_id]
                    joint_pos = joint_data.get("position", [0, 0])
                    if len(joint_pos) >= 2:
                        scene_pos = QPointF(joint_pos[0], joint_pos[1])

                        # 🔧 CRITICAL FIX: Validate skeleton length preservation before applying position
                        position_valid = self._validate_skeleton_length_preservation_reset(
                            item, scene_pos, joints_dict
                        )

                        if position_valid:
                            # Use bypass for legitimate initialization - the validation was done above
                            item.set_scene_position_from_anchor(scene_pos, bypass_validation=True)
                            logging.info(
                                f"EditorTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})"
                            )
                        else:
                            logging.debug(
                                f"EditorTab: Skeleton length constraint violation prevented for part '{part_name}' during initialization"
                            )

                    # Check if joint is locked and update the part item
                    is_locked = joint_data.get("is_locked", False)
                    item.set_joint_locked(is_locked)
                    if is_locked:
                        logging.info(
                            f"EditorTab: Joint '{std_joint_id}' for part '{part_name}' is locked"
                        )
                else:
                    # Log if we couldn't find the anchor joint
                    logging.warning(
                        f"EditorTab: Could not find anchor joint for part '{part_name}'. "
                        f"anchor_joint_id='{anchor_joint_id}', std_joint_id='{std_joint_id}', "
                        f"Available joints: {list(joints_dict.keys())}"
                    )

        self.current_editor_items = created_editor_items

        self.populate_parts_list(list(self.current_parts_info.keys()))
        self._update_button_states()
        self.editor_view.reset_view()  # Set view to 100% zoom and center
        logging.info(
            f"EditorTab: Added {len(self.current_editor_items)} items to the scene and reset view to 100%."
        )

        self.parts_loaded.emit(True)
        logging.info(f"Loaded {len(self.current_parts_info)} parts into the editor.")

        # Emit path data in case any parts have existing paths
        self._emit_path_data()

    def clear_editor_content(self):
        """Clears all parts and joints from the editor scene."""
        logging.info("EditorTab: Content cleared.")
        if not self.editor_scene:
            logging.warning("EditorTab: Scene not available to clear content.")
            return

        # Clear CharacterPartItems
        for item in list(self.current_editor_items.values()):  # Iterate over a copy
            if item.scene() == self.editor_scene:  # Check if item is in this scene
                self.editor_scene.removeItem(item)
            # Optionally, explicitly delete the Python object if it's not managed by Qt's parent/child
            # For QObject/QGraphicsItem, removeItem and no Python references should be enough for GC
            # However, if issues persist, explicit deletion can be tried.
            # For now, assume Qt handles it once removed from scene and Python GC kicks in.
        self.current_editor_items.clear()

        # Clear visual joints (if any are directly managed as QGraphicsItems)
        # Assuming joints are just data for now, but if they have visual items:
        # for joint_item in self.visual_joint_items:
        # self.editor_scene.removeItem(joint_item)
        # self.visual_joint_items.clear()
        self.joints.clear()  # Clear the joint data list

        self.selected_part_name = None
        self.populate_parts_list([])  # Update list (will be empty)
        self.update_part_properties_panel(None)
        self._update_button_states()
        self.editor_view.reset_temp_visuals()  # Clear any temporary drawing items in view
        self.editor_view.clear_all_motion_path_visuals()
        self._motion_path_manager.clear_corrected_paths_cache()
        self.editor_view.set_mode("select")

        self.parts_cleared.emit()
        self.parts_loaded.emit(False)
        self._initial_skeleton_data_cache = (
            None  # Clear cached skeleton data when editor content is cleared
        )
        logging.info("EditorTab: Cleared cached initial skeleton data.")
        if self.editor_view and hasattr(
            self.editor_view, "set_joint_map"
        ):  # Also clear map in view
            self.editor_view.set_joint_map(None)

    def clear_all_visual_motion_paths(self) -> None:
        """Clear all visual motion paths from the editor without clearing parts.

        Used when resetting animations or clearing motion path data while
        preserving the character parts in the scene.
        """
        logging.info("EditorTab: Clearing all visual motion paths")

        # Clear motion paths from each CharacterPartItem
        for _part_name, part_item in self.current_editor_items.items():
            # Clear the motion path data
            if hasattr(part_item, "motion_path"):
                part_item.motion_path = None

            # Remove motion path visual item from scene
            if hasattr(part_item, "motion_path_item") and part_item.motion_path_item:
                if part_item.motion_path_item.scene() == self.editor_scene:
                    self.editor_scene.removeItem(part_item.motion_path_item)
                part_item.motion_path_item = None

            # Clear path points
            if hasattr(part_item, "motion_path_points"):
                part_item.motion_path_points = []

            if hasattr(part_item, "original_path_points"):
                part_item.original_path_points = []

        self.editor_view.clear_all_motion_path_visuals()

        # Clear corrected paths from motion path manager
        self._motion_path_manager.clear_corrected_paths_cache()

        # Update UI
        self._update_button_states()
        if self.editor_view:
            self.editor_view.viewport().update()
        self._emit_path_data()

    @pyqtSlot(str)
    def on_simulation_state_changed(self, state_string: str):
        """
        Slot to handle animation_state_changed signal from IKManager.
        Updates the enabled state of simulation control buttons.
        Args:
            state_string (str): The new animation state (e.g., "playing", "stopped", "reset").
        """
        logging.info(f"EditorTab: Simulation state changed to: {state_string}")

        is_playing = False
        can_play = False
        can_stop = False
        can_reset = False  # Default can_reset to False, enable if data exists

        if state_string == "playing":
            is_playing = True
            can_play = False
            can_stop = True
            can_reset = False  # Cannot reset while playing
        elif state_string == "stopped":
            is_playing = False
            # Check if there's data to play/reset
            # This depends on whether skeleton/parts are loaded, which IKManager might know
            # For now, assume if stopped, can play if data exists.
            can_play = bool(
                self.current_editor_items
            )  # Or check ProjectDataManager via MainWindow if needed
            can_stop = False
            can_reset = bool(self.current_editor_items)
        elif state_string == "reset":
            is_playing = False
            can_play = bool(self.current_editor_items)
            can_stop = False
            can_reset = (
                False  # After reset, usually cannot reset again immediately unless new state allows
            )
            # Let's assume reset means back to initial, can play, cannot reset further.
            # Or, if reset clears data, then can_reset would be false.
            # For now, if state is "reset", assume it's ready to play again if data exists.
            can_reset = bool(self.current_editor_items)  # Can reset if there's something to reset
        else:
            logging.warning(f"EditorTab: Unknown simulation state string: {state_string}")
            # Default to a safe state (e.g., not playing, can play if items exist)
            is_playing = False
            can_play = bool(self.current_editor_items)
            can_stop = False
            can_reset = bool(self.current_editor_items)

        # Update button states
        if self.play_btn:
            self.play_btn.setEnabled(can_play and not is_playing)
            self.play_btn.setChecked(is_playing)  # Reflects if it's actively playing
        if self.stop_btn:
            self.stop_btn.setEnabled(can_stop and is_playing)
        if self.reset_sim_btn:
            self.reset_sim_btn.setEnabled(can_reset and not is_playing)

        # Update other UI elements if necessary

        self.current_simulation_state = state_string  # Update current state
        self.ik_log_counter.clear()  # Reset log counter when simulation state changes

    @pyqtSlot(dict)
    def on_skeleton_updated(self, skeleton_data: dict | None):
        """Called by MainWindow when skeleton is updated. Delegates to SkeletonIKHandler."""
        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler.on_skeleton_updated(skeleton_data)
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot update skeleton")

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
        """Caches initial skeleton data. Delegates to SkeletonIKHandler."""
        # Keep local cache for backwards compatibility with existing lambdas
        if skeleton_data_dict:
            self._initial_skeleton_data_cache = skeleton_data_dict.copy()
        else:
            self._initial_skeleton_data_cache = None

        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler.cache_initial_skeleton(skeleton_data_dict)
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot cache skeleton")

    def _position_parts_at_anchor_joints(self):
        """Positions parts at anchor joints. Delegates to SkeletonIKHandler."""
        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler._position_parts_at_anchor_joints()
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot position parts")

    def _validate_part_position(
        self,
        part_item: Any,
        position: QPointF,
        joints_dict: dict[str, Any],
    ) -> bool:
        """Validate part position before placement. Used by PartsDataManager."""
        return self._validate_skeleton_length_preservation_reset(part_item, position, joints_dict)

    def _validate_skeleton_length_preservation_reset(
        self,
        part_item: "CharacterPartItem",
        new_anchor_pos: QPointF,
        joint_data: dict[str, dict[str, Any]],
    ) -> bool:
        """
        Validate that positioning a part at new_anchor_pos would preserve skeleton length constraints.

        This method is used specifically for reset operations to prevent skeleton length violations.
        """
        # Define bone length tolerance (matching FABRIK solver constraint)
        MAX_BONE_LENGTH_DEVIATION = 0.01  # 1% tolerance for floating point precision

        # For reset operations, we need to be more lenient as we're restoring initial positions
        # However, we still want to prevent extreme violations that could break the skeleton

        # Get connections this part participates in
        connections = self._get_connected_joints_for_part_reset(part_item, joint_data)

        # Check if positioning at new_anchor_pos would violate bone length constraints
        for parent_joint_id, child_joint_id, expected_length in connections:
            if parent_joint_id in joint_data and child_joint_id in joint_data:
                parent_pos = joint_data[parent_joint_id].get("position", [0, 0])
                child_pos = joint_data[child_joint_id].get("position", [0, 0])

                if len(parent_pos) >= 2 and len(child_pos) >= 2:
                    # Calculate current bone length
                    parent_point = QPointF(parent_pos[0], parent_pos[1])
                    child_point = QPointF(child_pos[0], child_pos[1])

                    dx = child_point.x() - parent_point.x()
                    dy = child_point.y() - parent_point.y()
                    current_length = (dx * dx + dy * dy) ** 0.5

                    # Check deviation from expected length
                    if expected_length > 0:
                        length_deviation = abs(current_length - expected_length) / expected_length
                        if length_deviation > MAX_BONE_LENGTH_DEVIATION:
                            logging.debug(
                                f"Reset skeleton length violation: {parent_joint_id}->{child_joint_id} "
                                f"expected={expected_length:.1f}, current={current_length:.1f}, "
                                f"deviation={length_deviation:.3f} > {MAX_BONE_LENGTH_DEVIATION}"
                            )
                            return False

        # If we reach here, all bone lengths are within tolerance
        return True

    def _get_connected_joints_for_part_reset(
        self, part_item: "CharacterPartItem", joint_data: dict[str, dict[str, Any]]
    ) -> list[tuple[str, str, float]]:
        """
        Get the bone connections for reset validation.

        Uses the initial skeleton cache to retrieve expected bone lengths,
        ensuring skeleton integrity is preserved during reset operations.

        Returns:
            List of tuples: (parent_joint_id, child_joint_id, expected_bone_length)
        """
        connections: list[tuple[str, str, float]] = []

        part_anchor_joint = part_item.anchor_joint_id
        if not part_anchor_joint:
            return connections

        # Use cached initial skeleton data to get expected bone lengths
        if (
            not hasattr(self, "_initial_skeleton_data_cache")
            or not self._initial_skeleton_data_cache
        ):
            logging.debug("No initial skeleton cache - skipping bone validation")
            return connections

        cached_joints = self._initial_skeleton_data_cache.get("joints", {})
        if not cached_joints:
            logging.debug("No joints in skeleton cache - skipping bone validation")
            return connections

        # Get the anchor joint data from cache
        anchor_joint_data = cached_joints.get(part_anchor_joint)
        if not anchor_joint_data:
            logging.debug(f"Anchor joint {part_anchor_joint} not in cache - skipping validation")
            return connections

        # Calculate bone length to parent (if parent exists)
        parent_id = anchor_joint_data.get("parent_id")
        if parent_id and parent_id in cached_joints:
            parent_data = cached_joints[parent_id]
            expected_length = self._calculate_bone_length_from_cache(parent_data, anchor_joint_data)
            if expected_length > 0:
                connections.append((parent_id, part_anchor_joint, expected_length))

        # Also check children bones (hierarchy traversal)
        hierarchy = self._initial_skeleton_data_cache.get("hierarchy", {})
        children_ids = hierarchy.get(part_anchor_joint, [])
        for child_id in children_ids:
            if child_id in cached_joints:
                child_data = cached_joints[child_id]
                expected_length = self._calculate_bone_length_from_cache(
                    anchor_joint_data, child_data
                )
                if expected_length > 0:
                    connections.append((part_anchor_joint, child_id, expected_length))

        return connections

    def _calculate_bone_length_from_cache(
        self, parent_joint_data: dict[str, Any], child_joint_data: dict[str, Any]
    ) -> float:
        """Calculate bone length between two joints from cached data.

        Args:
            parent_joint_data: Parent joint dict with 'position' key
            child_joint_data: Child joint dict with 'position' key

        Returns:
            Euclidean distance between joints, or 0.0 if positions invalid
        """
        parent_pos = parent_joint_data.get("position")
        child_pos = child_joint_data.get("position")

        if not parent_pos or not child_pos:
            return 0.0

        try:
            # Handle both tuple/list and dict formats
            if isinstance(parent_pos, list | tuple) and len(parent_pos) >= 2:
                px, py = float(parent_pos[0]), float(parent_pos[1])
            elif isinstance(parent_pos, dict):
                px, py = float(parent_pos.get("x", 0)), float(parent_pos.get("y", 0))
            else:
                return 0.0

            if isinstance(child_pos, list | tuple) and len(child_pos) >= 2:
                cx, cy = float(child_pos[0]), float(child_pos[1])
            elif isinstance(child_pos, dict):
                cx, cy = float(child_pos.get("x", 0)), float(child_pos.get("y", 0))
            else:
                return 0.0

            dx = cx - px
            dy = cy - py
            return (dx * dx + dy * dy) ** 0.5

        except (TypeError, ValueError, KeyError) as e:
            logging.debug(f"Error calculating bone length: {e}")
            return 0.0

    # Slot for freehandPathCompleted signal from EditorView
    @pyqtSlot(list, list, float)  # (path_points, timed_points, duration)
    def _handle_freehand_path_completed(
        self,
        path_points: list[QPointF],
        timed_points: list,
        duration: float,
    ):
        """
        Handles freehand path completion. Delegates to MotionPathManager.

        Args:
            path_points: List of QPointF (resampled points for visual spline)
            timed_points: List of TimedPoint with timestamps (for velocity-aware animation)
            duration: Total drawing duration in seconds
        """
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.handle_freehand_path_completed(
                path_points, timed_points, duration
            )
        else:
            logging.warning("MotionPathManager not initialized, cannot handle path completion")

    def _handle_drawing_cancelled(self):
        """Handles drawing cancellation. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.handle_drawing_cancelled()
        else:
            logging.warning("MotionPathManager not initialized, cannot handle drawing cancelled")

    # --- Public slots for view actions (for MainWindow connection) ---
    @pyqtSlot()
    def zoom_in(self):
        if self.editor_view:
            self.editor_view.zoom_in()

    @pyqtSlot()
    def zoom_out(self):
        if self.editor_view:
            self.editor_view.zoom_out()

    @pyqtSlot()
    def zoom_to_fit(self):
        if self.editor_view:
            self.editor_view.zoom_to_fit()

    @pyqtSlot()
    def reset_view(self):
        if self.editor_view:
            self.editor_view.reset_view()

    @pyqtSlot()
    def undo(self):
        if self.editor_view:
            self.editor_view.undo()

    @pyqtSlot()
    def redo(self):
        if self.editor_view:
            self.editor_view.redo()

    @pyqtSlot(bool)
    def toggle_part_properties_panel_visibility(self, visible: bool):
        # This panel is removed, so this slot is now a no-op.
        pass

    def handle_joint_defined(self, joint_data: dict):
        """Handles joint_defined signal. Delegates to SkeletonIKHandler."""
        # Keep local joints list for backwards compatibility
        self.joints.append(joint_data)

        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler.handle_joint_defined(joint_data)
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot handle joint defined")

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
        """Receives IK results. Delegates to SkeletonIKHandler."""
        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler.handle_ik_update(ik_results)
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot handle IK update")

    def _handle_part_item_clicked_from_view(self, clicked_item: CharacterPartItem):
        """Handles a CharacterPartItem being clicked in the EditorView."""
        part_name = clicked_item.name()
        logging.debug(f"EditorTab: Part '{part_name}' clicked in view. Selected.")

        # Update the QListWidget selection to match the view
        for i in range(self.parts_list.count()):
            list_item = self.parts_list.item(i)
            if list_item.data(Qt.ItemDataRole.UserRole) == part_name:
                self.parts_list.setCurrentItem(
                    list_item, QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                break

    def _handle_part_item_double_clicked_from_view(self, double_clicked_item: CharacterPartItem):
        """Handles a CharacterPartItem being double-clicked in the EditorView."""
        part_name = double_clicked_item.name()
        logging.debug(f"EditorTab: Part '{part_name}' double-clicked in view.")
        QMessageBox.information(
            self, "Part Double-Clicked", f"Part '{part_name}' was double-clicked."
        )

    def _collect_path_data(self) -> dict[str, QPainterPath]:
        """Collect all motion paths from parts."""
        path_data = {}

        # First check in current_parts_info (project data)
        if self.current_parts_info:
            for part_name, part_info in self.current_parts_info.items():
                if hasattr(part_info, "motion_path") and part_info.motion_path:
                    if (
                        isinstance(part_info.motion_path, QPainterPath)
                        and not part_info.motion_path.isEmpty()
                    ):
                        path_data[part_name] = part_info.motion_path

        # Also check in current_editor_items as backup
        for part_name, part_item in self.current_editor_items.items():
            if part_name not in path_data:  # Don't override if already found
                if hasattr(part_item, "motion_path") and part_item.motion_path:
                    if (
                        isinstance(part_item.motion_path, QPainterPath)
                        and not part_item.motion_path.isEmpty()
                    ):
                        path_data[part_name] = part_item.motion_path

        logging.debug(
            f"EditorTab: Collected {len(path_data)} motion paths: {list(path_data.keys())}"
        )
        return path_data

    def get_current_path_data(self) -> dict[str, QPainterPath]:
        """Get current motion path data for all parts. Public interface for other tabs."""
        return self._collect_path_data()

    def _emit_path_data(self):
        """Emit current path data to other tabs."""
        path_data = self._collect_path_data()
        self.path_data_changed.emit(path_data)
        logging.info(f"EditorTab: Emitted path data for {len(path_data)} parts")

    def _on_smoothness_value_changed(self, value: int):
        """Capture slider value and start debounce timer. Updates label immediately."""
        self._pending_smoothness_value = value
        if self.smoothness_value_label:
            self.smoothness_value_label.setText(f"{value}%")
        self._smoothness_debounce_timer.start()

    def _on_smoothness_changed_debounced(self):
        """Handle smoothness slider after debounce. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.on_smoothness_changed(self._pending_smoothness_value)

    def _on_smoothness_changed(self, value: int):
        """Handle smoothness slider value change. Delegates to MotionPathManager."""
        if hasattr(self, "_motion_path_manager"):
            self._motion_path_manager.on_smoothness_changed(value)
        else:
            # Fallback: just update the label
            if self.smoothness_value_label:
                self.smoothness_value_label.setText(f"{value}%")

    # NOTE: Path smoothing methods (_regenerate_path_with_smoothness, _compute_extreme_indices,
    # _local_extrema_indices, _rdp_preserve, _apply_feasibility_snapping_if_needed,
    # _apply_corrections_for_all_parts) have been moved to MotionPathManager component.

    def _get_original_path_points(self, part_name: str) -> list[QPointF]:
        """Get the original drawn points for a part (before spline interpolation)."""
        # Try to get from the part item first
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, "original_path_points") and part_item.original_path_points:
                return part_item.original_path_points

        # If not available, try to extract from the current path (approximation)
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, "motion_path") and part_item.motion_path:
                return self._extract_points_from_path(part_item.motion_path)

        return []

    def _extract_points_from_path(self, path: QPainterPath) -> list[QPointF]:
        """Extract points from a QPainterPath (approximation for existing paths)."""
        return extract_points_from_path(path)

    def _create_raw_path(self, points: list[QPointF]) -> QPainterPath:
        """Create a path using raw points connected by straight lines."""
        return create_raw_path(points, closed=True)

    def _create_perfect_ellipse_path(self, points: list[QPointF]) -> QPainterPath:
        """Create a perfect ellipse optimized for the original points' distribution and orientation."""
        return create_perfect_ellipse_path(points)

    def _create_interpolated_path(
        self, points: list[QPointF], smoothness_percentage: int
    ) -> QPainterPath:
        """Create a path interpolated between raw points and perfect ellipse with optimal point correspondence."""
        # Use spline creator from editor_view if available
        spline_creator = None
        if hasattr(self.editor_view, "_create_spline_path"):
            spline_creator = self.editor_view._create_spline_path
        return create_interpolated_path(points, smoothness_percentage, spline_creator)

    def _update_part_path(self, part_name: str, new_path: QPainterPath):
        """Update the motion path for a part in all relevant data structures."""
        # Update the CharacterPartItem
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            part_item.set_motion_path(new_path)

        # Update the project data
        if (
            hasattr(self.main_window, "project_data_manager")
            and self.main_window.project_data_manager
        ):
            current_parts = self._parts_data_from_project_manager(
                self.main_window.project_data_manager
            )
            if current_parts and part_name in current_parts:
                current_parts[part_name].motion_path = new_path

        # Update the visual path in EditorView if it exists
        if (
            hasattr(self.editor_view, "final_paths_map")
            and part_name in self.editor_view.final_paths_map
        ):
            path_item = self.editor_view.final_paths_map[part_name]
            if path_item:
                path_item.setPath(new_path)

        # Emit the updated path data
        self.motion_path_updated.emit(part_name, new_path)
        self._emit_path_data()

        # Update the scene
        self.editor_scene.update()

    def activate_tab(self):
        """Called when the tab becomes active. Re-enable animation controls if needed."""
        # Ensure IKManager has the current parts data
        main_window = self.window()

        # Try to get the most up-to-date parts data
        parts_data_to_use = None
        if hasattr(main_window, "project_data_manager") and main_window.project_data_manager:
            parts_data_to_use = self._parts_data_from_project_manager(
                main_window.project_data_manager
            )

        # Fallback to local parts data if project data manager doesn't have it
        if (
            not parts_data_to_use
            and hasattr(self, "current_parts_info")
            and self.current_parts_info
        ):
            parts_data_to_use = self.current_parts_info

        # Set the parts data in IKManager
        if parts_data_to_use and hasattr(main_window, "ik_manager") and main_window.ik_manager:
            if hasattr(main_window.ik_manager, "set_project_parts_data"):
                main_window.ik_manager.set_project_parts_data(parts_data_to_use)
                logging.info(
                    f"[EditorTab] Re-set project parts data in IKManager on tab activation ({len(parts_data_to_use)} parts)"
                )

        # CRITICAL: Re-send skeleton data to IKManager to ensure proper initialization
        if hasattr(self, "_initial_skeleton_data_cache") and self._initial_skeleton_data_cache:
            if hasattr(main_window, "ik_manager") and main_window.ik_manager:
                if hasattr(main_window.ik_manager, "on_skeleton_data_updated_from_manager"):
                    main_window.ik_manager.on_skeleton_data_updated_from_manager(
                        self._initial_skeleton_data_cache
                    )
                    logging.info("[EditorTab] Re-sent skeleton data to IKManager on tab activation")

        # CRITICAL: Also send current motion paths to IKManager to ensure they're not lost
        current_paths = self._collect_path_data()
        if current_paths and hasattr(main_window, "ik_manager") and main_window.ik_manager:
            for part_name, motion_path in current_paths.items():
                if hasattr(main_window.ik_manager, "update_part_motion_path"):
                    main_window.ik_manager.update_part_motion_path(part_name, motion_path)
                    logging.info(
                        f"[EditorTab] Re-sent motion path for {part_name} to IKManager on tab activation"
                    )

        # Re-enable animation controls based on current state
        if self._has_motion_paths():
            self.play_btn.setEnabled(True)
            self.reset_sim_btn.setEnabled(True)

            # Update animation status
            path_count = len(self._collect_path_data())
            self.animation_status_label.setText(f"{path_count} motion path(s) defined")

            # Emit path data to ensure all tabs and systems are synchronized
            self._emit_path_data()

            logging.info("[EditorTab] Tab activated - animation controls re-enabled")
        else:
            # Update button states to ensure correct state
            self._update_button_states()

    def deactivate_tab(self):
        """Called when leaving the tab. Stop any running animations."""
        # Check if animation is running and stop it
        if self.stop_btn.isEnabled():
            self._stop_simulation_clicked()
            logging.info("[EditorTab] Tab deactivated - animation stopped")

    def _has_motion_paths(self) -> bool:
        """Check if any items have motion paths defined."""
        for item in self.editor_scene.items():
            if isinstance(item, CharacterPartItem):
                if (
                    hasattr(item, "motion_path")
                    and item.motion_path
                    and not item.motion_path.isEmpty()
                ):
                    return True
        return False

    def center_on_character(self):
        """Center the view on the character (all parts)."""
        if not self.editor_scene or not self.current_editor_items:
            return

        # Calculate bounding box of all parts
        combined_rect = None
        for part_item in self.current_editor_items.values():
            if part_item and part_item.scene():
                part_rect = part_item.sceneBoundingRect()
                if combined_rect is None:
                    combined_rect = part_rect
                else:
                    combined_rect = combined_rect.united(part_rect)

        if combined_rect:
            # Add some padding
            padding = 50
            combined_rect.adjust(-padding, -padding, padding, padding)

            # Center on the character without changing zoom
            center = combined_rect.center()
            self.editor_view.centerOn(center)

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change. Delegates to SkeletonIKHandler."""
        # Update local cache for backwards compatibility
        if self._initial_skeleton_data_cache and "joints" in self._initial_skeleton_data_cache:
            joints = self._initial_skeleton_data_cache["joints"]
            if joint_id in joints:
                joints[joint_id]["bend_direction"] = new_direction

        if hasattr(self, "_skeleton_ik_handler"):
            self._skeleton_ik_handler.handle_joint_bend_direction_changed(joint_id, new_direction)
        else:
            logging.warning("SkeletonIKHandler not initialized, cannot handle bend direction")

    # --- Cleanup ---

    def closeEvent(self, event) -> None:
        """
        Handle tab close event - cleanup signals and resources.

        Disconnects all signal connections to prevent memory leaks
        and dangling references when the tab is closed.
        """
        logging.info("EditorTab: closeEvent - cleaning up signals")

        # Disconnect editor_view signals
        try:
            if self.editor_view:
                self.editor_view.freehandPathCompleted.disconnect()
                self.editor_view.drawing_cancelled.disconnect()
                self.editor_view.joint_defined.disconnect()
                self.editor_view.zoom_changed.disconnect()
                self.editor_view.part_item_clicked.disconnect()
                self.editor_view.part_item_double_clicked.disconnect()
                self.editor_view.joint_bend_direction_changed.disconnect()
        except (TypeError, RuntimeError) as e:
            logging.debug(f"EditorTab: Signal disconnect (editor_view): {e}")

        # Disconnect simulation controller signals
        try:
            if hasattr(self, "_simulation_controller") and self._simulation_controller:
                self._simulation_controller.request_play.disconnect()
                self._simulation_controller.request_stop.disconnect()
                self._simulation_controller.request_reset.disconnect()
        except (TypeError, RuntimeError) as e:
            logging.debug(f"EditorTab: Signal disconnect (simulation_controller): {e}")

        # Disconnect UI widget signals
        try:
            if self.parts_list:
                self.parts_list.currentItemChanged.disconnect()
            if self.define_motion_path_btn:
                self.define_motion_path_btn.toggled.disconnect()
            if self.clear_motion_path_btn:
                self.clear_motion_path_btn.clicked.disconnect()
            if self.play_btn:
                self.play_btn.clicked.disconnect()
            if self.stop_btn:
                self.stop_btn.clicked.disconnect()
            if self.reset_sim_btn:
                self.reset_sim_btn.clicked.disconnect()
            if self.smoothness_slider:
                self.smoothness_slider.valueChanged.disconnect()
            if self.zoom_in_btn:
                self.zoom_in_btn.clicked.disconnect()
            if self.zoom_out_btn:
                self.zoom_out_btn.clicked.disconnect()
            if self.zoom_fit_btn:
                self.zoom_fit_btn.clicked.disconnect()
            if self.center_character_btn:
                self.center_character_btn.clicked.disconnect()
        except (TypeError, RuntimeError, AttributeError) as e:
            logging.debug(f"EditorTab: Signal disconnect (UI widgets): {e}")

        # Clear references
        self.current_parts_info.clear()
        self.current_editor_items.clear()
        self.joints.clear()
        self._initial_skeleton_data_cache = None

        logging.info("EditorTab: closeEvent - cleanup complete")
        super().closeEvent(event)
