import logging
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
import math

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QFormLayout,
    QListWidget,
    QScrollArea,
    QSizePolicy,
    QApplication,
    QStyle,
    QListWidgetItem,
    QMessageBox,
    QGraphicsLineItem,
    QGraphicsEllipseItem,
    QDialog,
    QGraphicsPathItem,
    QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QTimer, QRectF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPixmap, QPen, QBrush, QPainterPath, QColor

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene
from ..graphics_items.part_item import CharacterPartItem
from automataii.core.models import PartInfo

from PyQt6.QtGui import QPainterPath
from .utils import get_project_root


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
    parts_cleared = (
        pyqtSignal()
    )  # Emitted when parts are cleared from this tab's perspective
    parts_loaded = pyqtSignal(
        bool
    )  # Emitted when parts are loaded/cleared (True if loaded)
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
        self.parts_list: Optional[QListWidget] = None
        self.define_motion_path_btn: Optional[QPushButton] = None
        self.clear_motion_path_btn: Optional[QPushButton] = None
        self.motion_path_status_label: Optional[QLabel] = None
        self.motion_path_info_label: Optional[QLabel] = None
        self.animation_status_label: Optional[QLabel] = None
        self.generate_mechanisms_btn: Optional[QPushButton] = None

        self.play_btn: Optional[QPushButton] = None
        self.stop_btn: Optional[QPushButton] = None
        self.reset_sim_btn: Optional[QPushButton] = None

        # Data specific to this tab
        self.selected_part_name: Optional[str] = None
        self.current_parts_info: Dict[str, PartInfo] = {}
        self.current_editor_items: Dict[str, CharacterPartItem] = {}

        # Store for defined joints within this tab
        self.joints: List[Dict] = []  # List of joint data dictionaries

        # Cache for initial skeleton data, to be set by MainWindow
        self._initial_skeleton_data_cache: Optional[Dict] = None

        self.current_simulation_state: str = "stopped"  # For logging IK updates
        self.ik_log_counter: Dict[str, int] = {}  # To limit logs per part/state

        self._init_ui()

        # Connect signals from self.editor_view now that it exists
        self._connect_editor_view_signals()

    def _connect_editor_view_signals(self):
        """Connect signals from this tab's EditorView instance."""
        self.editor_view.freehandPathCompleted.connect(
            self._handle_freehand_path_completed
        )
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        self.editor_view.joint_defined.connect(self.handle_joint_defined)
        self.editor_view.zoom_changed.connect(self._update_zoom_combo_from_view)

        # Connect to new EditorView signals for item interactions
        self.editor_view.part_item_clicked.connect(
            self._handle_part_item_clicked_from_view
        )
        self.editor_view.part_item_double_clicked.connect(
            self._handle_part_item_double_clicked_from_view
        )
        # self.editor_view.part_item_moved.connect(self._handle_part_item_moved_from_view) # Deferred

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left Control Panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Parts List Group
        parts_group = QGroupBox("1 Parts")
        parts_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        parts_layout = QVBoxLayout(parts_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("List of loaded character parts")
        self.parts_list.setMinimumHeight(180)  # Increased height
        self.parts_list.setStyleSheet(
            """
            QListWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:selected:!active {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078D7, stop: 1 #005a9e);
                color: white;
                border: 1px solid #004578;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
            }
        """
        )
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # 2. Motion Path Definition Group
        motion_path_group = QGroupBox("2 Motion Path")
        motion_path_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        motion_path_layout = QVBoxLayout(motion_path_group)

        self.motion_path_status_label = QLabel("Select a part")
        self.motion_path_status_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #495057;
            padding: 8px;
            text-align: center;
        """)
        self.motion_path_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        motion_path_layout.addWidget(self.motion_path_status_label)

        motion_path_buttons_layout = QHBoxLayout()
        motion_path_buttons_layout.setSpacing(8)  # Spacing between buttons

        # Compact button styles for motion path buttons
        motion_path_button_style = """
            QPushButton {
                background-color: #a7c7e7;
                border: 1px solid #96b6d6;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                color: #ffffff;
                min-height: 28px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #96b6d6;
                border-color: #85a5c5;
            }
            QPushButton:pressed {
                background-color: #85a5c5;
                border-color: #7494b4;
            }
            QPushButton:disabled {
                background-color: #e0e6ed;
                color: #a0aab5;
                border-color: #dbe4f0;
            }
        """

        motion_path_button_checked_style = motion_path_button_style + """
            QPushButton:checked {
                background-color: #5c85d6;
                border-color: #4b74c5;
                color: white;
            }
        """

        self.define_motion_path_btn = QPushButton("Start Drawing")
        self.define_motion_path_btn.setCheckable(True)
        self.define_motion_path_btn.setToolTip(
            "Toggle mode to draw a motion path for the selected part."
        )
        self.define_motion_path_btn.setEnabled(False)
        self.define_motion_path_btn.setStyleSheet(motion_path_button_checked_style)
        self.define_motion_path_btn.setMinimumWidth(110)
        motion_path_buttons_layout.addWidget(self.define_motion_path_btn)

        self.clear_motion_path_btn = QPushButton("Clear")
        self.clear_motion_path_btn.setToolTip(
            "Clear the motion path for the selected part."
        )
        self.clear_motion_path_btn.setEnabled(False)
        self.clear_motion_path_btn.setStyleSheet(motion_path_button_style)
        self.clear_motion_path_btn.setMinimumWidth(65)
        motion_path_buttons_layout.addWidget(self.clear_motion_path_btn)
        motion_path_layout.addLayout(motion_path_buttons_layout)

        self.motion_path_info_label = QLabel(
            "Click points in the view to draw path. Click 'Stop Drawing' when done."
        )
        self.motion_path_info_label.setWordWrap(True)
        self.motion_path_info_label.setStyleSheet(
            "background-color: #E6F7FF; border: 1px solid #BCE0FF; padding: 5px; border-radius: 3px;"
        )
        self.motion_path_info_label.setVisible(False)
        motion_path_layout.addWidget(self.motion_path_info_label)

        panel_layout.addWidget(motion_path_group)

        # 3. Animation Group
        animation_group = QGroupBox("3 Animation")
        animation_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        animation_layout = QVBoxLayout(animation_group)

        self.animation_status_label = QLabel("No motion paths defined")
        animation_layout.addWidget(self.animation_status_label)

        # TODO: Add slider here if needed in future. For now, skipping.

        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)  # More spacing between compact buttons
        style = self.style()

        # Compact styling for animation buttons
        animation_button_style = """
            QPushButton {
                background-color: #a7c7e7;
                border: 1px solid #96b6d6;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
                color: #ffffff;
                min-height: 24px;
                min-width: 55px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #96b6d6;
                border-color: #85a5c5;
            }
            QPushButton:pressed {
                background-color: #85a5c5;
                border-color: #7494b4;
            }
            QPushButton:disabled {
                background-color: #e0e6ed;
                color: #a0aab5;
                border-color: #dbe4f0;
            }
        """

        # Play button
        self.play_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), " Play"
        )
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setStyleSheet(animation_button_style)

        # Stop button
        self.stop_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), " Stop"
        )
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(animation_button_style)

        # Reset button
        self.reset_sim_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), " Reset"
        )
        self.reset_sim_btn.setToolTip("Reset Animation")
        self.reset_sim_btn.setEnabled(False)
        self.reset_sim_btn.setStyleSheet(animation_button_style)

        anim_button_layout.addWidget(self.play_btn)
        anim_button_layout.addWidget(self.stop_btn)
        anim_button_layout.addWidget(self.reset_sim_btn)
        animation_layout.addLayout(anim_button_layout)

        panel_layout.addWidget(animation_group)

        # 4. View Controls Group
        view_controls_group = QGroupBox("4 View Controls")
        view_controls_group.setStyleSheet("""
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e9f0;
                border-radius: 9px;
                padding: 18px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                margin-left: 15px;
                font-size: 12pt;
                font-weight: bold;
                color: #5c85d6;
                background-color: #ffffff;
            }
        """)
        view_controls_layout = QVBoxLayout(view_controls_group)

        # Zoom controls
        zoom_controls_layout = QHBoxLayout()
        zoom_controls_layout.setSpacing(6)

        zoom_button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: bold;
                color: #495057;
                min-height: 22px;
                min-width: 30px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #6c757d;
            }
        """

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setToolTip("Zoom In")
        self.zoom_in_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_in_btn)

        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setToolTip("Zoom Out")
        self.zoom_out_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_out_btn)

        self.zoom_fit_btn = QPushButton("⌖")
        self.zoom_fit_btn.setToolTip("Zoom to Fit")
        self.zoom_fit_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.zoom_fit_btn)

        self.zoom_reset_btn = QPushButton("1:1")
        self.zoom_reset_btn.setToolTip("Reset Zoom (100%)")
        self.zoom_reset_btn.setStyleSheet(zoom_button_style)
        self.zoom_reset_btn.setMinimumWidth(35)
        zoom_controls_layout.addWidget(self.zoom_reset_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        panel_layout.addWidget(view_controls_group)

        panel_layout.addStretch(1)

        control_panel.setMinimumWidth(280)

        scroll_area.setWidget(control_panel)
        layout.addWidget(scroll_area)
        layout.addWidget(self.editor_view, 1)

        # Connect signals
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.define_motion_path_btn.toggled.connect(
            self._toggle_define_motion_path_mode
        )
        self.clear_motion_path_btn.clicked.connect(
            self._clear_selected_item_motion_path
        )
        self.play_btn.clicked.connect(self._play_simulation_clicked)
        self.stop_btn.clicked.connect(self._stop_simulation_clicked)
        self.reset_sim_btn.clicked.connect(self._reset_simulation_clicked)

        # Connect zoom controls
        self.zoom_in_btn.clicked.connect(lambda: self.editor_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.editor_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.editor_view.zoom_to_fit)
        self.zoom_reset_btn.clicked.connect(self.editor_view.reset_view)

    def _handle_part_selection_change(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
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
                    logging.info(f"EditorTab: Part '{part_name}' selected and highlighted in scene.")
                else:
                    self.editor_scene.clearSelection()
                    logging.debug(f"EditorTab: Part '{part_name}' selected but not yet loaded in scene.")
            else:
                self.selected_part_name = None
                self.editor_scene.clearSelection()
                logging.warning(f"EditorTab: No part name found in UserRole data")
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

    def _handle_part_list_click(self, item: QListWidgetItem):
        # Currently, currentItemChanged handles selection. This could be for other interactions.
        logging.info(f"Part list item clicked: {item.text()}")

    def _toggle_define_motion_path_mode(self, checked: bool):
        """Handle the 'Start/Stop Drawing' button toggle."""
        part_name = self.selected_part_name
        if not part_name or not checked:
            self.editor_view.set_mode("select")
            self.define_motion_path_btn.setText("Start Drawing")
            self.define_motion_path_btn.setStyleSheet("")
            self.motion_path_info_label.setVisible(False)
            if checked:
                self.define_motion_path_btn.setChecked(False)
            return

        logging.debug(f"Toggling drawing mode for part: {part_name}")
        # Set the drawing mode and start motion path definition
        self.editor_view.set_mode("define_motion_path")
        # Find the target part item for path drawing
        if part_name in self.current_editor_items:
            target_item = self.current_editor_items[part_name]
            self.editor_view.start_define_motion_path(target_item)

        self.define_motion_path_btn.setText("Stop Drawing")
        self.define_motion_path_btn.setStyleSheet("background-color: #0078D7; color: white;")
        self.motion_path_info_label.setVisible(True)

        # Uncheck button if drawing is completed/cancelled from the view
        # This is handled by connecting the view's signals to this button's slot/lambda

    def _clear_selected_item_motion_path(self):
        if not self.selected_part_name:
            logging.warning("No part selected for motion path clearing")
            return

        logging.info(f"Clearing motion path for selected part: {self.selected_part_name}")

        # Clear motion path from CharacterPartItem if it exists
        if self.selected_part_name in self.current_editor_items:
            part_item = self.current_editor_items[self.selected_part_name]

            # Clear motion path data
            part_item.motion_path = None

            # Clear motion path visual if it exists
            if hasattr(part_item, 'motion_path_item') and part_item.motion_path_item:
                if part_item.motion_path_item.scene():
                    self.editor_scene.removeItem(part_item.motion_path_item)
                part_item.motion_path_item = None

            # Clear motion path points if they exist
            if hasattr(part_item, 'motion_path_points'):
                part_item.motion_path_points = []

        # Clear from current_parts_info (ProjectDataManager data)
        if self.selected_part_name in self.current_parts_info:
            self.current_parts_info[self.selected_part_name].motion_path = None

        # Clear visual path from EditorView's final paths map (green paths)
        if hasattr(self.editor_view, 'final_paths_map') and self.selected_part_name in self.editor_view.final_paths_map:
            path_item = self.editor_view.final_paths_map.pop(self.selected_part_name)
            if path_item and path_item.scene():
                self.editor_scene.removeItem(path_item)
                logging.info(f"Removed green path visual for {self.selected_part_name}")

        # Also try to clear using EditorView's method if it exists
        if hasattr(self.editor_view, 'clear_visual_path_for_component'):
            self.editor_view.clear_visual_path_for_component(self.selected_part_name)

        # Clear from main window's project data manager if it exists
        if hasattr(self.main_window, 'project_data_manager'):
            current_parts = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts and self.selected_part_name in current_parts:
                current_parts[self.selected_part_name].motion_path = None

        # Emit signal to notify other components that path was cleared
        if hasattr(self, 'motion_path_updated'):
            from PyQt6.QtGui import QPainterPath
            empty_path = QPainterPath()
            self.motion_path_updated.emit(self.selected_part_name, empty_path)

        logging.info(f"Motion path cleared for {self.selected_part_name}")
        self.main_window.statusBar().showMessage(
            f"Motion path cleared for {self.selected_part_name}"
        )

        # Update UI states
        self._update_button_states()
        self._update_part_list_styles()

        # Force scene update to ensure visuals are refreshed
        self.editor_scene.update()
        self.editor_view.viewport().update()

        # Emit updated path data to other tabs
        self._emit_path_data()

    def _play_simulation_clicked(self):
        # Always emit the signal so IK manager knows we're playing
        self.request_play_simulation.emit()

    def _stop_simulation_clicked(self):
        logging.info("Stop button clicked")
        self.request_stop_simulation.emit()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(True)

    def _reset_simulation_clicked(self):
        self.request_reset_simulation.emit()

        # Reset parts to original positions
        for part_name, part_item in self.current_editor_items.items():
            if hasattr(part_item, "_original_anchor_pos"):
                part_item.set_scene_position_from_anchor(part_item._original_anchor_pos)
                del part_item._original_anchor_pos

        # Reset skeleton visualization to its cached initial state
        if self._initial_skeleton_data_cache:
            self.on_skeleton_updated(self._initial_skeleton_data_cache.copy())
            logging.info(
                "EditorTab: Skeleton visualization reset to cached initial state."
            )
        else:
            self.on_skeleton_updated(None)
            logging.warning("EditorTab: No cached initial skeleton data for reset.")

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(False)
        self._update_button_states()

        self.editor_scene.update()


    def _handle_zoom_change(self, zoom_text: str):
        # This functionality is removed from the UI, but we keep the method
        # in case it's called from somewhere else (e.g., main window menu).
        try:
            if zoom_text.lower() == "fit":
                self.editor_view.zoom_to_fit()
                return
            if zoom_text.endswith("%"):
                zoom_value = float(zoom_text[:-1]) / 100.0
            else:
                zoom_value = float(zoom_text)
            self.editor_view.set_zoom_level(zoom_value)
        except ValueError:
            current_scale = self.editor_view.transform().m11()
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText(f"{int(current_scale * 100)}%")
            self.zoom_combo.blockSignals(False)

    def _handle_zoom_change_fit(self):
        # This functionality is removed from the UI
        self.editor_view.zoom_to_fit()

    def _update_zoom_combo_from_view(self, scale_factor: float):
        # This functionality is removed from the UI
        pass

    def populate_parts_list(self, part_names: List[str]):
        """Populate the parts list widget with given names."""
        self.parts_list.clear()
        for part_name in part_names:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)  # Store part name in UserRole
            self.parts_list.addItem(item)
        self._update_button_states()
        self._update_part_list_styles()
        self._update_active_part_visuals()

    def update_part_properties_panel(self, part_name: Optional[str]):
        # This panel is now removed. This function can be kept as a no-op for now.
        pass

    def _update_button_states(self):
        """Update the enabled/disabled state of all buttons based on current state."""
        selected = self.selected_part_name is not None
        has_any_path = self._has_any_motion_path()
        selected_part_has_path = selected and self._has_motion_path(self.selected_part_name)

        logging.debug(f"EditorTab: Updating button states - selected: {selected}, selected_part: {self.selected_part_name}, has_path: {selected_part_has_path}")

        # Motion Path section
        self.define_motion_path_btn.setEnabled(selected)
        self.clear_motion_path_btn.setEnabled(selected_part_has_path)

        logging.debug(f"EditorTab: Start Drawing button enabled: {selected}, Clear button enabled: {selected_part_has_path}")

        # Animation section
        self.play_btn.setEnabled(has_any_path)
        self.stop_btn.setEnabled(
            has_any_path and self.current_simulation_state == "playing"
        )
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
            if hasattr(part_item, 'motion_path') and part_item.motion_path and not part_item.motion_path.isEmpty():
                return True
        return False

    def _has_motion_path(self, part_name: str) -> bool:
        """Check if a specific part has a motion path defined."""
        if not part_name:
            return False

        # Check in EditorView's final paths map first (green paths)
        if hasattr(self.editor_view, 'final_paths_map') and part_name in self.editor_view.final_paths_map:
            path_item = self.editor_view.final_paths_map[part_name]
            if path_item and path_item.scene():
                return True

        # Check in current_editor_items
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, 'motion_path') and part_item.motion_path and not part_item.motion_path.isEmpty():
                return True

        # Also check in current_parts_info (project data)
        if part_name in self.current_parts_info:
            part_info = self.current_parts_info[part_name]
            if hasattr(part_info, 'motion_path') and part_info.motion_path:
                if hasattr(part_info.motion_path, 'isEmpty'):
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
            if hasattr(part_item, 'motion_path') and part_item.motion_path and not part_item.motion_path.isEmpty():
                count += 1
        return count

    def _get_selected_part_has_motion_path(self) -> bool:
        if (
            self.selected_part_name
            and self.selected_part_name in self.current_editor_items
        ):
            part_item = self.current_editor_items[self.selected_part_name]
            return bool(part_item.motion_path and not part_item.motion_path.isEmpty())
        return False

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

    def set_parts_data(self, parts_info: Dict[str, PartInfo]):
        """Receives parts data and populates the editor."""
        self.clear_editor_content()  # Clear previous content first

        self.current_parts_info = parts_info if parts_info else {}
        created_editor_items: Dict[str, CharacterPartItem] = {}

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
        else:
            logging.error(
                "EditorTab: Project directory not available from ProjectDataManager. Part items may not load correctly."
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
                    from automataii.animate.part_definitions import BODY_PARTS

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
                        item.set_scene_position_from_anchor(scene_pos)
                        logging.info(
                            f"EditorTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})"
                        )

                    # Check if joint is locked and update the part item
                    is_locked = joint_data.get("is_locked", False)
                    item.set_joint_locked(is_locked)
                    if is_locked:
                        logging.info(f"EditorTab: Joint '{std_joint_id}' for part '{part_name}' is locked")
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
            can_reset = False  # After reset, usually cannot reset again immediately unless new state allows
            # Let's assume reset means back to initial, can play, cannot reset further.
            # Or, if reset clears data, then can_reset would be false.
            # For now, if state is "reset", assume it's ready to play again if data exists.
            can_reset = bool(
                self.current_editor_items
            )  # Can reset if there's something to reset
        else:
            logging.warning(
                f"EditorTab: Unknown simulation state string: {state_string}"
            )
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
    def on_skeleton_updated(self, skeleton_data: Optional[Dict]):
        """Called by MainWindow when the skeleton is updated.
        This method is for *displaying* the skeleton.
        Initial skeleton caching is handled by `cache_initial_skeleton`.
        """
        logging.info(
            f"EditorTab received skeleton update for display: {'Exists' if skeleton_data else 'None'}"
        )

        # Caching logic removed from here, will be handled by a dedicated method.

        if self.editor_view:
            if skeleton_data:  # This is the data to display *now*
                # skeleton_data is likely from StandardizedSkeletonModel.model_dump()
                # So, skeleton_data.get('joints') will be Dict[str, Dict] where the inner dict is the dumped joint model.
                standardized_joints_dict = skeleton_data.get(
                    "joints", {}
                )  # Dict[std_id, Dict]
                hierarchy = skeleton_data.get(
                    "hierarchy", {}
                )  # Dict[std_id, List[std_child_id]]

                skeleton_for_view = []
                if isinstance(standardized_joints_dict, dict):
                    for (
                        joint_id,
                        joint_model_dict,
                    ) in (
                        standardized_joints_dict.items()
                    ):  # Iterate through the dictionary of dictionaries
                        pos_list = joint_model_dict.get("position")
                        pos = (
                            QPointF(pos_list[0], pos_list[1])
                            if pos_list and len(pos_list) == 2
                            else QPointF()
                        )

                        skeleton_for_view.append(
                            {
                                "id": joint_model_dict.get(
                                    "id", joint_id
                                ),  # Use key as fallback for id
                                "name": joint_model_dict.get("name"),
                                "position": pos,
                                "parent": joint_model_dict.get("parent_id"),
                                "color": joint_model_dict.get("color", "blue"),
                                "label": joint_model_dict.get("label"),
                            }
                        )

                        # Update joint lock status for any parts that have this joint as anchor
                        is_locked = joint_model_dict.get("is_locked", False)
                        joint_name = joint_model_dict.get("name")

                        # Find parts that use this joint
                        for part_name, part_item in self.current_editor_items.items():
                            if part_item.anchor_joint_id == joint_name or part_item.anchor_joint_id == joint_id:
                                part_item.set_joint_locked(is_locked)
                                if is_locked:
                                    logging.debug(f"EditorTab: Updated part '{part_name}' - joint locked")
                                else:
                                    logging.debug(f"EditorTab: Updated part '{part_name}' - joint unlocked")

                logging.debug(
                    f"EditorTab: Visualizing skeleton with {len(skeleton_for_view)} joints and hierarchy keys: {list(hierarchy.keys())}"
                )
                self.editor_view.visualize_skeleton(skeleton_for_view, hierarchy)
            else:
                logging.info(
                    "EditorTab: Clearing skeleton visualization because skeleton_data is None."
                )
                self.editor_view.visualize_skeleton([], {})

        self._update_button_states()

    # New method to cache initial skeleton data
    def cache_initial_skeleton(self, skeleton_data_dict: Optional[Dict]):
        """Caches the initial skeleton data dictionary provided by MainWindow."""
        if skeleton_data_dict:
            self._initial_skeleton_data_cache = (
                skeleton_data_dict.copy()
            )  # Store a copy
            logging.info("EditorTab: Initial skeleton data has been cached.")
            # Pass the joint_map to the editor_view
            if self.editor_view and hasattr(
                self.editor_view, "set_joint_map"
            ):  # Check if method exists
                joint_map = self._initial_skeleton_data_cache.get("joint_map")
                self.editor_view.set_joint_map(joint_map)

            # Parts should remain at 0° rotation as they are cropped images
            # The skeleton angles are used for IK calculations, not initial part display

            # Position parts at their anchor joints if parts are already loaded
            if self.current_editor_items:
                self._position_parts_at_anchor_joints()
        else:
            self._initial_skeleton_data_cache = None
            logging.info(
                "EditorTab: Initial skeleton data cache has been cleared (set to None)."
            )
            if self.editor_view and hasattr(
                self.editor_view, "set_joint_map"
            ):  # Check if method exists
                self.editor_view.set_joint_map(None)  # Clear map in view as well

        # Refresh visuals in case this is a reload
        self._update_part_list_styles()
        self._update_active_part_visuals()
        self._update_button_states()

    def _position_parts_at_anchor_joints(self):
        """Positions parts at their anchor joint locations based on skeleton data."""
        if (
            not self._initial_skeleton_data_cache
            or "joints" not in self._initial_skeleton_data_cache
        ):
            return

        joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
        joints_dict = self._initial_skeleton_data_cache.get("joints", {})

        # Import BODY_PARTS for fallback anchor joint lookup
        try:
            from automataii.animate.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}
            logging.warning(
                "EditorTab: Could not import BODY_PARTS for fallback anchor joint lookup"
            )

        for part_name, part_item in self.current_editor_items.items():
            if part_name in self.current_parts_info:
                p_info = self.current_parts_info[part_name]

                # Get anchor_joint_id, with fallback to BODY_PARTS
                anchor_joint_id = p_info.anchor_joint_id
                if not anchor_joint_id and BODY_PARTS:
                    part_def = BODY_PARTS.get(part_name, {})
                    anchor_joint_id = part_def.get("anchor_joint")
                    if anchor_joint_id:
                        logging.info(
                            f"EditorTab: Using fallback anchor_joint '{anchor_joint_id}' for part '{part_name}' from BODY_PARTS"
                        )

                if anchor_joint_id:
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
                            part_item.set_scene_position_from_anchor(scene_pos)
                            logging.info(
                                f"EditorTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})"
                            )
                    else:
                        # Log if we couldn't find the anchor joint
                        logging.warning(
                            f"EditorTab (_position_parts_at_anchor_joints): Could not find anchor joint for part '{part_name}'. "
                            f"anchor_joint_id='{anchor_joint_id}', std_joint_id='{std_joint_id}', "
                            f"Available joints: {list(joints_dict.keys())}"
                        )

    # Slot for freehandPathCompleted signal from EditorView
    @pyqtSlot(list)  # Changed to match signal: list of QPointF
    def _handle_freehand_path_completed(self, path_points: List[QPointF]):
        """
        Handles the completion of a freehand drawing path from the view.
        The view is responsible for creating the final spline path. This method
        retrieves that path and updates the data models.
        """
        if not self.selected_part_name:
            logging.warning("_handle_freehand_path_completed: No part selected.")
            return

        part_name = self.selected_part_name

        # Retrieve the final spline path created by the EditorView
        final_path_item = self.editor_view.final_paths_map.get(part_name)

        if not final_path_item:
            logging.error(f"Could not find final spline path for {part_name} in EditorView's final_paths_map.")
            # As a fallback, create a linear path from the raw points. This should not happen in normal operation.
            motion_qpath = QPainterPath()
            if path_points:
                motion_qpath.moveTo(path_points[0])
                for point in path_points[1:]:
                    motion_qpath.lineTo(point)
        else:
            motion_qpath = final_path_item.path()
            logging.info(f"Retrieved final spline path for '{part_name}' from EditorView.")

        # Update the PartInfo model in the ProjectDataManager
        current_parts_info = self.main_window.project_data_manager.parts
        if part_name in current_parts_info:
            current_parts_info[part_name].motion_path = motion_qpath
            logging.debug(f"EditorTab: Updated motion_path in ProjectDataManager for '{part_name}'.")
        else:
            logging.warning(f"_handle_freehand_path_completed: Part '{part_name}' not found in ProjectDataManager.")

        # Update the CharacterPartItem in the scene
        if part_name in self.current_editor_items:
            char_part_item = self.current_editor_items[part_name]
            char_part_item.set_motion_path(motion_qpath)
        else:
            logging.warning(f"_handle_freehand_path_completed: Item '{part_name}' not in current_editor_items.")

        # Emit signals to notify other parts of the application
        self.motion_path_updated.emit(part_name, motion_qpath)
        self._emit_path_data()

        self.main_window.statusBar().showMessage(f"Motion path completed for part: {part_name}")
        self._update_button_states()
        logging.info(f"Completed and stored spline motion path for part: {part_name}")

    # Slot for drawing_cancelled signal from EditorView
    def _handle_drawing_cancelled(self):
        """Handles cancellation of drawing mode from the view."""
        logging.debug("Drawing mode cancelled from view.")
        self.define_motion_path_btn.setChecked(False)
        self.define_motion_path_btn.setText("Start Drawing")
        self.define_motion_path_btn.setStyleSheet("")
        self.motion_path_info_label.setVisible(False)

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
        """Handles the joint_defined signal from EditorView.
        Stores the joint data and potentially updates UI or triggers further processing.
        """
        logging.info(f"EditorTab: Joint defined: {joint_data}")
        # joint_data is a dict from the view as per its signal
        self.joints.append(joint_data)
        self.main_window.statusBar().showMessage(
            f"Joint defined between {joint_data['part1_name']} and {joint_data['part2_name']}"
        )
        self._update_button_states()

    def handle_ik_update(self, ik_results: Dict[str, Dict[str, Any]]):
        """Receives IK results and updates the EditorView."""
        logging.debug(
            f"[IK_ENTRY_TRACE] EditorTab.handle_ik_update entered. Current state: {self.current_simulation_state}. IK Results count: {len(ik_results)}"
        )
        if not self.editor_view:
            logging.warning("EditorTab: EditorView not available to handle IK update.")
            return

        if not ik_results:
            return

        if ik_results:
            self.editor_view.update_visuals_from_animation_data(ik_results)
        else:
            logging.info(
                "EditorTab.handle_ik_update: No valid joint-centric data generated from ik_results to update visuals."
            )

        self.editor_view.scene().update()

    def _handle_part_item_clicked_from_view(self, clicked_item: CharacterPartItem):
        """Handles a CharacterPartItem being clicked in the EditorView."""
        part_name = clicked_item.name()
        logging.debug(f"EditorTab: Part '{part_name}' clicked in view. Selected.")

        # Update the QListWidget selection to match the view
        for i in range(self.parts_list.count()):
            list_item = self.parts_list.item(i)
            if list_item.text() == part_name:
                self.parts_list.setCurrentItem(
                    list_item, Qt.ItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                break

    def _handle_part_item_double_clicked_from_view(
        self, double_clicked_item: CharacterPartItem
    ):
        """Handles a CharacterPartItem being double-clicked in the EditorView."""
        part_name = double_clicked_item.name()
        logging.debug(f"EditorTab: Part '{part_name}' double-clicked in view.")
        QMessageBox.information(
            self, "Part Double-Clicked", f"Part '{part_name}' was double-clicked."
        )

    def _solve_four_bar_kinematics(
        self,
        P0: QPointF,
        P3: QPointF,
        L1: float,
        L2: float,
        L3: float,
        input_angle_L1_rad: float,
    ) -> Optional[Tuple[QPointF, QPointF, float, float, float]]:
        """
        Solves the forward kinematics for a four-bar linkage for a given input angle of L1.
        P0 and P3 are fixed pivots. L1 is the crank, L2 the coupler, L3 the rocker.
        Lengths are assumed to be already scaled for display.
        """
        P1 = QPointF(
            P0.x() + L1 * math.cos(input_angle_L1_rad),
            P0.y() + L1 * math.sin(input_angle_L1_rad),
        )

        d_sq = (P3.x() - P1.x()) ** 2 + (P3.y() - P1.y()) ** 2
        d = math.sqrt(d_sq)

        if d > L2 + L3 or d < abs(L2 - L3):
            return None
        if d == 0 and L2 != L3:
            return None

        val_for_acos_gamma1 = (d_sq + L2**2 - L3**2) / (2 * d * L2)
        if not (-1 <= val_for_acos_gamma1 <= 1):
            return None
        gamma1 = math.acos(val_for_acos_gamma1)
        phi_P1P3 = math.atan2(P3.y() - P1.y(), P3.x() - P1.x())

        solutions = []
        for sign in [-1, 1]:
            l2_angle_rad = phi_P1P3 + sign * gamma1
            P2_test = QPointF(
                P1.x() + L2 * math.cos(l2_angle_rad),
                P1.y() + L2 * math.sin(l2_angle_rad),
            )
            dist_P2_P3 = math.sqrt(
                (P2_test.x() - P3.x()) ** 2 + (P2_test.y() - P3.y()) ** 2
            )
            if abs(dist_P2_P3 - L3) < 0.001:
                solutions.append((P2_test, l2_angle_rad))

        if not solutions:
            return None

        P2, l2_angle_rad = solutions[0]
        l3_angle_rad = math.atan2(P2.y() - P3.y(), P2.x() - P3.x())
        l1_angle_rad = input_angle_L1_rad

        return P1, P2, l1_angle_rad, l2_angle_rad, l3_angle_rad

    def _clear_preview_paths(self):
        """Clear any preview path visualizations."""
        if hasattr(self, "_preview_path_items"):
            for item in self._preview_path_items:
                if item.scene() == self.editor_scene:
                    self.editor_scene.removeItem(item)
            self._preview_path_items.clear()

    def _collect_path_data(self) -> Dict[str, QPainterPath]:
        """Collect all motion paths from parts."""
        path_data = {}

        # First check in current_parts_info (project data)
        if self.current_parts_info:
            for part_name, part_info in self.current_parts_info.items():
                if hasattr(part_info, 'motion_path') and part_info.motion_path:
                    if isinstance(part_info.motion_path, QPainterPath) and not part_info.motion_path.isEmpty():
                        path_data[part_name] = part_info.motion_path

        # Also check in current_editor_items as backup
        for part_name, part_item in self.current_editor_items.items():
            if part_name not in path_data:  # Don't override if already found
                if hasattr(part_item, 'motion_path') and part_item.motion_path:
                    if isinstance(part_item.motion_path, QPainterPath) and not part_item.motion_path.isEmpty():
                        path_data[part_name] = part_item.motion_path

        logging.debug(f"EditorTab: Collected {len(path_data)} motion paths: {list(path_data.keys())}")
        return path_data

    def _emit_path_data(self):
        """Emit current path data to other tabs."""
        path_data = self._collect_path_data()
        self.path_data_changed.emit(path_data)
        logging.info(f"EditorTab: Emitted path data for {len(path_data)} parts")
