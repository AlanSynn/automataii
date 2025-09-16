import logging
import math
from typing import Any

from PyQt6.QtCore import QPointF, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from automataii.core.models import PartInfo
from automataii.gui.graphics_items.part_item import CharacterPartItem
from automataii.gui.views.editor_view import EditorView


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

        # Connect joint bend direction change signal
        self.editor_view.joint_bend_direction_changed.connect(
            self._handle_joint_bend_direction_changed
        )

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
                font-weight: bold;
                color: #ffffff;
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

        self.clear_motion_path_btn = QPushButton("Clear")
        self.clear_motion_path_btn.setToolTip(
            "Clear the motion path for the selected part."
        )
        self.clear_motion_path_btn.setEnabled(False)
        self.clear_motion_path_btn.setStyleSheet(motion_path_button_style.replace("#a7c7e7", "#e7a7a7"))

        # Path type selection (Open/Closed)
        from PyQt6.QtWidgets import QButtonGroup, QRadioButton

        path_type_layout = QHBoxLayout()
        path_type_layout.setSpacing(10)

        path_type_label = QLabel("Path Type:")
        path_type_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        path_type_layout.addWidget(path_type_label)

        self.path_type_group = QButtonGroup()

        self.closed_path_radio = QRadioButton("Closed")
        self.closed_path_radio.setToolTip("Create a closed loop path")
        self.closed_path_radio.setChecked(True)  # Default to closed
        self.path_type_group.addButton(self.closed_path_radio, 0)
        path_type_layout.addWidget(self.closed_path_radio)

        self.open_path_radio = QRadioButton("Open")
        self.open_path_radio.setToolTip("Create an open path")
        self.path_type_group.addButton(self.open_path_radio, 1)
        path_type_layout.addWidget(self.open_path_radio)

        path_type_layout.addStretch()
        motion_path_layout.addLayout(path_type_layout)

        motion_path_buttons_layout.addStretch()
        motion_path_buttons_layout.addWidget(self.define_motion_path_btn)
        motion_path_buttons_layout.addWidget(self.clear_motion_path_btn)
        motion_path_buttons_layout.addStretch()
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

        # Smoothness control
        smoothness_layout = QHBoxLayout()
        smoothness_layout.setSpacing(8)

        smoothness_label = QLabel("Smoothness:")
        smoothness_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #495057;")
        smoothness_layout.addWidget(smoothness_label)

        self.smoothness_slider = QSlider(Qt.Orientation.Horizontal)
        self.smoothness_slider.setMinimum(0)  # 0% = original raw points
        self.smoothness_slider.setMaximum(100)  # 100% = perfect ellipse
        self.smoothness_slider.setValue(50)  # Default 50%
        self.smoothness_slider.setEnabled(False)  # Initially disabled
        self.smoothness_slider.setToolTip("Adjust path smoothness (0% = raw points, 100% = perfect ellipse)")
        self.smoothness_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #c5d9f0;
                background: white;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e8f2ff, stop:1 #b8d4f0);
                border: 1px solid #7ba7d1;
                width: 15px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f7ff, stop:1 #d0e4f5);
                border: 1px solid #5a8bb5;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #a7c7e7, stop: 1 #d4e7f7);
                border: 1px solid #7ba7d1;
                height: 6px;
                border-radius: 3px;
            }
        """)
        smoothness_layout.addWidget(self.smoothness_slider)

        self.smoothness_value_label = QLabel("50%")
        self.smoothness_value_label.setMinimumWidth(30)
        self.smoothness_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.smoothness_value_label.setStyleSheet("font-size: 11px; color: #666;")
        smoothness_layout.addWidget(self.smoothness_value_label)

        motion_path_layout.addLayout(smoothness_layout)

        # Note: Feasibility is now auto-applied on Play. Button removed per request.

        panel_layout.addWidget(motion_path_group)
        panel_layout.setStretchFactor(motion_path_group, 0)

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
                padding: 4px 6px;
                font-weight: bold;
                color: #ffffff;
                min-height: 24px;
                min-width: 30px;
                max-width: 35px;
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
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), ""
        )
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setStyleSheet(animation_button_style)

        # Stop button
        self.stop_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), ""
        )
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(animation_button_style)

        # Reset button
        self.reset_sim_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), ""
        )
        self.reset_sim_btn.setToolTip("Reset Animation")
        self.reset_sim_btn.setEnabled(False)
        self.reset_sim_btn.setStyleSheet(animation_button_style)

        anim_button_layout.addStretch()
        anim_button_layout.addWidget(self.play_btn)
        anim_button_layout.addWidget(self.stop_btn)
        anim_button_layout.addWidget(self.reset_sim_btn)
        anim_button_layout.addStretch()
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

        # Center on Character button
        self.center_character_btn = QPushButton("⎈")
        self.center_character_btn.setToolTip("Center on Character")
        self.center_character_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.center_character_btn)

        # Removed 1:1 zoom reset button as requested (Issue #4)

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

        # Connect smoothness slider
        self.smoothness_slider.valueChanged.connect(self._on_smoothness_changed)

        # Connect zoom controls
        self.zoom_in_btn.clicked.connect(lambda: self.editor_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.editor_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.editor_view.zoom_to_fit)
        self.center_character_btn.clicked.connect(self.center_on_character)
        # Removed zoom_reset_btn connection (1:1 button removed)

    def _handle_part_selection_change(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
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


    def _toggle_define_motion_path_mode(self, checked: bool):
        """Handle the 'Start/Stop Drawing' button toggle."""
        part_name = self.selected_part_name
        if not part_name or not checked:
            self.editor_view.set_mode("select")
            self.define_motion_path_btn.setText("Start Drawing")
            self.motion_path_info_label.setVisible(False)
            if checked:
                self.define_motion_path_btn.setChecked(False)
            return

        logging.debug(f"Toggling drawing mode for part: {part_name}")

        # CRITICAL FIX: Clear any existing mechanism visuals AND motion path for this part before starting new path
        if hasattr(self.main_window, 'mechanism_design_tab'):
            mechanism_tab = self.main_window.mechanism_design_tab
            if hasattr(mechanism_tab, '_clear_mechanism_for_part'):
                mechanism_tab._clear_mechanism_for_part(part_name)
                logging.info(f"🔄 EDITOR TAB: Cleared mechanism visuals for part '{part_name}' before new path drawing")

        # ALSO CLEAR existing motion path visuals from editor view
        if hasattr(self.editor_view, 'clear_visual_path_for_component'):
            self.editor_view.clear_visual_path_for_component(part_name)
            logging.info(f"🔄 EDITOR TAB: Cleared motion path visuals for part '{part_name}' before new drawing")

        # Clear from path data (check if exists first)
        if hasattr(self, 'path_data') and part_name in self.path_data:
            del self.path_data[part_name]
            logging.info(f"🔄 EDITOR TAB: Removed path data for part '{part_name}'")

        # Also clear from project data manager if available
        if hasattr(self.main_window, 'project_data_manager'):
            parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if parts_data and part_name in parts_data:
                parts_data[part_name].motion_path_data = None
                logging.info(f"🔄 EDITOR TAB: Cleared motion_path_data for part '{part_name}' in project data")

        # Set the drawing mode and start motion path definition
        self.editor_view.set_mode("define_motion_path")
        # Find the target part item for path drawing
        if part_name in self.current_editor_items:
            target_item = self.current_editor_items[part_name]
            # Pass path type information to editor view
            is_closed = self.closed_path_radio.isChecked()
            self.editor_view.start_define_motion_path(target_item, is_closed=is_closed)

        self.define_motion_path_btn.setText("Stop Drawing")
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

            # Clear original path points for smoothness adjustment
            if hasattr(part_item, 'original_path_points'):
                part_item.original_path_points = []

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
            logging.info(
                "EditorTab: Skeleton and parts reset to cached initial state."
            )
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
            'torso',
            'left_arm_upper', 'right_arm_upper',
            'left_leg_upper', 'right_leg_upper'
        }

        for part_name in part_names:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name)

            # 🔧 upper 파츠들과 torso 비활성화
            if any(disabled_part in part_name.lower() for disabled_part in disabled_parts):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)  # 선택 불가
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)     # 비활성화

                # 시각적으로 비활성화 표시
                item.setForeground(QBrush(QColor(150, 150, 150)))  # 회색 텍스트
                item.setBackground(QBrush(QColor(240, 240, 240)))   # 연한 회색 배경
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

        logging.debug(f"EditorTab: Updating button states - selected: {selected}, selected_part: {self.selected_part_name}, has_path: {selected_part_has_path}")

        # Motion Path section
        self.define_motion_path_btn.setEnabled(selected)
        self.clear_motion_path_btn.setEnabled(selected_part_has_path)

        # Smoothness slider - enable only when a part with path is selected
        if self.smoothness_slider:
            self.smoothness_slider.setEnabled(selected_part_has_path)

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
    def on_skeleton_updated(self, skeleton_data: dict | None):
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
                                "bend_direction": joint_model_dict.get("bend_direction", 1.0),  # Add bend direction
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
    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
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

                            # 🔧 CRITICAL FIX: Validate skeleton length preservation before applying position
                            position_valid = self._validate_skeleton_length_preservation_reset(
                                part_item, scene_pos, joints_dict
                            )

                            if position_valid:
                                # Use bypass for legitimate reset - the validation was done above
                                part_item.set_scene_position_from_anchor(scene_pos, bypass_validation=True)
                                logging.info(
                                    f"EditorTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})"
                                )
                            else:
                                logging.debug(
                                    f"EditorTab: Skeleton length constraint violation prevented for part '{part_name}' during reset"
                                )
                    else:
                        # Log if we couldn't find the anchor joint
                        logging.warning(
                            f"EditorTab (_position_parts_at_anchor_joints): Could not find anchor joint for part '{part_name}'. "
                            f"anchor_joint_id='{anchor_joint_id}', std_joint_id='{std_joint_id}', "
                            f"Available joints: {list(joints_dict.keys())}"
                        )

    def _validate_skeleton_length_preservation_reset(
        self,
        part_item: 'CharacterPartItem',
        new_anchor_pos: QPointF,
        joint_data: dict[str, dict[str, Any]]
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
        self,
        part_item: 'CharacterPartItem',
        joint_data: dict[str, dict[str, Any]]
    ) -> list[tuple[str, str, float]]:
        """
        Get the bone connections for reset validation.

        Returns:
            List of tuples: (parent_joint_id, child_joint_id, expected_bone_length)
        """
        connections = []

        # For reset operations, we use a simplified approach
        # In a full implementation, this would use the original bone lengths from skeleton initialization

        part_anchor_joint = part_item.anchor_joint_id
        if not part_anchor_joint:
            return connections

        # For now, we'll apply basic validation to prevent extreme violations
        # This is a simplified implementation that could be enhanced with proper bone hierarchy

        return connections  # Return empty for now to allow reset operations

    # Slot for freehandPathCompleted signal from EditorView
    @pyqtSlot(list)  # Changed to match signal: list of QPointF
    def _handle_freehand_path_completed(self, path_points: list[QPointF]):
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

            # Store the original path points for smoothness adjustment
            if not hasattr(char_part_item, 'original_path_points'):
                char_part_item.original_path_points = path_points.copy()
            else:
                char_part_item.original_path_points = path_points.copy()
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

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
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



    def _collect_path_data(self) -> dict[str, QPainterPath]:
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

    def get_current_path_data(self) -> dict[str, QPainterPath]:
        """Get current motion path data for all parts. Public interface for other tabs."""
        return self._collect_path_data()

    def _emit_path_data(self):
        """Emit current path data to other tabs."""
        path_data = self._collect_path_data()
        self.path_data_changed.emit(path_data)
        logging.info(f"EditorTab: Emitted path data for {len(path_data)} parts")

    def _on_smoothness_changed(self, value: int):
        """Handle smoothness slider value change."""
        # Update the value label
        if self.smoothness_value_label:
            self.smoothness_value_label.setText(f"{value}%")

        # If a part is selected and has a path, regenerate it with new smoothness
        if self.selected_part_name and self._has_motion_path(self.selected_part_name):
            self._regenerate_path_with_smoothness(self.selected_part_name, value)

    def _regenerate_path_with_smoothness(self, part_name: str, smoothness_percentage: int):
        """Regenerate motion path using tolerance-based smoothing that preserves extremes.

        Shows dual-track overlay: raw (dashed green) vs smoothed (solid).
        """
        # 1) Gather original points
        original_points = self._get_original_path_points(part_name)
        if not original_points or len(original_points) < 3:
            logging.warning(f"Cannot regenerate path for {part_name}: insufficient original points")
            return

        # If smoothness is 0: commit completely raw path and show purple dashed raw overlay
        if smoothness_percentage == 0:
            raw_path = self._create_raw_path(original_points)
            if hasattr(self.editor_view, 'set_raw_overlay_path'):
                # Purple dashed pen for raw overlay
                raw_pen = QPen(QColor("#6a4c93"), 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
                self.editor_view.set_raw_overlay_path(part_name, raw_path, raw_pen)
            # Compute feasibility-corrected overlay (if available)
            try:
                corrected = self._apply_feasibility_snapping_if_needed(part_name, raw_path)
                if corrected is not None and hasattr(self.editor_view, 'set_corrected_overlay_path'):
                    self.editor_view.set_corrected_overlay_path(part_name, corrected)
                    self._corrected_paths[part_name] = corrected
            except Exception as e:
                logging.debug(f"Feasibility snapping skipped: {e}")
            self._update_part_path(part_name, raw_path)
            logging.info(f"Regenerated path (RAW) for {part_name} with smoothness 0%")
            return

        # 2) Map slider 0..100 to geometric tolerance based on path size
        bbox_min_x = min(p.x() for p in original_points)
        bbox_max_x = max(p.x() for p in original_points)
        bbox_min_y = min(p.y() for p in original_points)
        bbox_max_y = max(p.y() for p in original_points)
        diag = ((bbox_max_x - bbox_min_x) ** 2 + (bbox_max_y - bbox_min_y) ** 2) ** 0.5
        # Use up to 5% of diagonal as max tolerance; avoid negative/lower than minimal float jitter
        epsilon = max(0.1, 0.05 * diag * (smoothness_percentage / 100.0))

        # 3) Compute extreme indices to preserve (endpoints + local extrema along principal axis)
        keep_indices = self._compute_extreme_indices(original_points)

        # 4) RDP simplify while preserving extremes
        simplified = self._rdp_preserve(original_points, epsilon, keep_indices)
        if len(simplified) < 3:
            simplified = original_points

        # 5) Build smoothed path via spline
        try:
            tension = 0.5
            new_path = self.editor_view._create_spline_path(simplified, closed_loop=True, tension=tension)
        except Exception:
            new_path = self._create_raw_path(simplified)

        # 6) Show dual-track overlays: raw vs smoothed
        raw_overlay = self._create_raw_path(original_points)
        if hasattr(self.editor_view, 'set_raw_overlay_path'):
            raw_pen = QPen(QColor("#6a4c93"), 3.0, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap)
            self.editor_view.set_raw_overlay_path(part_name, raw_overlay, raw_pen)

        # 7) Optional: feasibility snapping (overlay corrected if needed)
        try:
            corrected = self._apply_feasibility_snapping_if_needed(part_name, new_path)
            if corrected is not None and hasattr(self.editor_view, 'set_corrected_overlay_path'):
                self.editor_view.set_corrected_overlay_path(part_name, corrected)
                self._corrected_paths[part_name] = corrected
        except Exception as e:
            logging.debug(f"Feasibility snapping skipped: {e}")

        # 8) Commit smoothed path
        self._update_part_path(part_name, new_path)
        logging.info(f"Regenerated path (RDP) for {part_name} with epsilon={epsilon:.2f}")

    # ---- Geometry helpers for Stage 1 smoothing ----
    def _compute_extreme_indices(self, points: list[QPointF]) -> set[int]:
        """Detect indices of extremes along principal axis, including endpoints.

        Uses PCA to find major axis, projects points, and picks local maxima/minima.
        """
        try:
            import numpy as np
        except Exception:
            # Fallback: use x-axis projection
            vals = [p.x() for p in points]
            return self._local_extrema_indices(vals)

        arr = np.array([[p.x(), p.y()] for p in points], dtype=float)
        arr_centered = arr - np.mean(arr, axis=0)
        cov = np.cov(arr_centered.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        major = eigvecs[:, np.argmax(eigvals)]
        proj = arr_centered @ major
        idxs = self._local_extrema_indices(proj.tolist())
        # Always include endpoints
        idxs.update({0, len(points) - 1})
        return idxs

    def _local_extrema_indices(self, values: list[float]) -> set[int]:
        """Return indices that are local minima or maxima in a 1D sequence."""
        idxs: set[int] = set()
        n = len(values)
        for i in range(1, n - 1):
            if (values[i] >= values[i - 1] and values[i] >= values[i + 1]) or \
               (values[i] <= values[i - 1] and values[i] <= values[i + 1]):
                idxs.add(i)
        return idxs

    def _rdp_preserve(self, points: list[QPointF], epsilon: float, keep_indices: set[int]) -> list[QPointF]:
        """Ramer–Douglas–Peucker simplification while forcing certain indices to be kept."""
        # Convert to tuples for distance calc
        import math

        def point_line_distance(p, a, b):
            # p, a, b are QPointF
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

        def rdp_segment(start_idx, end_idx) -> list[int]:
            if end_idx <= start_idx + 1:
                return [start_idx, end_idx]
            # Find furthest point
            a, b = points[start_idx], points[end_idx]
            max_dist = -1.0
            index = -1
            for i in range(start_idx + 1, end_idx):
                d = point_line_distance(points[i], a, b)
                if d > max_dist:
                    max_dist = d
                    index = i
            if max_dist > epsilon or any((start_idx < k < end_idx) for k in keep_indices):
                # Split
                left = rdp_segment(start_idx, index)
                right = rdp_segment(index, end_idx)
                return left[:-1] + right
            else:
                return [start_idx, end_idx]

        n = len(points)
        # Ensure keep points are included by forcing splits at those indices
        selected = set()
        # Sort keep indices inside (0,n-1)
        internal_keeps = sorted([k for k in keep_indices if 0 < k < n - 1])
        segments = []
        prev = 0
        for k in internal_keeps:
            segments.append((prev, k))
            prev = k
        segments.append((prev, n - 1))
        idx_list: list[int] = []
        for s, e in segments:
            seg_idxs = rdp_segment(s, e)
            for i in seg_idxs:
                selected.add(i)
        final_indices = sorted(selected)
        return [points[i] for i in final_indices]

    # ---- Feasibility stub (Stage 1) ----
    def _apply_feasibility_snapping_if_needed(self, part_name: str, path: QPainterPath) -> QPainterPath | None:
        """Attempt to compute a nearest-feasible path based on end-effector reach.

        Uses a two-bone (root->mid->effector) annulus model when available from IKManager:
        feasible radii from root = [abs(l1-l2), l1+l2] (± small tolerance). Points are
        projected onto this annulus. Falls back to single-bone model otherwise.
        """
        try:
            ik = getattr(self.main_window, 'ik_manager', None)
            if not ik or not hasattr(ik, 'sim_joints_config'):
                return None

            # Find end-effector joint (abstract) for this part
            eff_abs = None
            try:
                for comp in getattr(ik, 'sim_selectable_components', []) or []:
                    if comp.get('partName') == part_name:
                        eff_abs = comp.get('targetJointId')
                        break
            except Exception:
                eff_abs = None
            if not eff_abs:
                return None

            # Resolve parent (mid) and root anchors via sim_limb_configs
            mid_abs = None
            root_abs = None
            try:
                mid_abs = ik.sim_limb_configs.get(eff_abs, {}).get('parentAnchor')
                if mid_abs:
                    root_abs = ik.sim_limb_configs.get(mid_abs, {}).get('parentAnchor') or mid_abs
            except Exception:
                pass
            if not mid_abs or not root_abs:
                return None

            # Map abstract names to standardized joint IDs
            def std_id_of(abs_name: str) -> str | None:
                try:
                    return ik._get_standardized_joint_id(abs_name)  # type: ignore[attr-defined]
                except Exception:
                    return None

            eff_id = std_id_of(eff_abs) or eff_abs
            mid_id = std_id_of(mid_abs) or mid_abs
            root_id = std_id_of(root_abs) or root_abs
            for jid in (eff_id, mid_id, root_id):
                if jid not in ik.sim_joints_config:
                    return None

            root_pos = ik.sim_joints_config[root_id]['position']
            mid_pos = ik.sim_joints_config[mid_id]['position']
            eff_pos = ik.sim_joints_config[eff_id]['position']

            # Bone lengths
            def dist(a, b):
                dx = a.x() - b.x(); dy = a.y() - b.y()
                return (dx*dx + dy*dy) ** 0.5

            l1 = dist(root_pos, mid_pos)
            l2 = dist(mid_pos, eff_pos)
            if l1 <= 1e-6 or l2 <= 1e-6:
                return None

            tol = 0.05  # small tolerance 5%
            r_min = max(0.0, abs(l1 - l2) * (1.0 - tol))
            r_max = (l1 + l2) * (1.0 + tol)

            # Project sampled points
            corrected = QPainterPath()
            any_change = False
            samples = 100
            for i in range(samples):
                t = i / (samples - 1) if samples > 1 else 0.0
                p = path.pointAtPercent(t)
                dx = p.x() - root_pos.x()
                dy = p.y() - root_pos.y()
                d = (dx * dx + dy * dy) ** 0.5
                if d < 1e-6:
                    nx, ny = r_min, 0.0
                    any_change = True
                else:
                    if d < r_min:
                        s = r_min / d; nx, ny = dx * s, dy * s; any_change = True
                    elif d > r_max:
                        s = r_max / d; nx, ny = dx * s, dy * s; any_change = True
                    else:
                        nx, ny = dx, dy
                cx = root_pos.x() + nx
                cy = root_pos.y() + ny
                if i == 0:
                    corrected.moveTo(cx, cy)
                else:
                    corrected.lineTo(cx, cy)
            corrected.closeSubpath()
            return corrected if any_change else None
        except Exception as e:
            logging.debug(f"Feasibility snapping error: {e}")
            return None

    def _apply_corrections_for_all_parts(self):
        """Auto-apply feasibility-corrected paths for all parts that have them."""
        if not hasattr(self, '_corrected_paths') or not self._corrected_paths:
            return
        for part, corrected in list(self._corrected_paths.items()):
            try:
                if corrected is None:
                    continue
                self._update_part_path(part, corrected)
                if hasattr(self.editor_view, 'clear_corrected_overlay_for'):
                    self.editor_view.clear_corrected_overlay_for(part)
                self._corrected_paths.pop(part, None)
            except Exception as e:
                logging.debug(f"Failed to auto-apply correction for {part}: {e}")

    def _get_original_path_points(self, part_name: str) -> list[QPointF]:
        """Get the original drawn points for a part (before spline interpolation)."""
        # Try to get from the part item first
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, 'original_path_points') and part_item.original_path_points:
                return part_item.original_path_points

        # If not available, try to extract from the current path (approximation)
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, 'motion_path') and part_item.motion_path:
                return self._extract_points_from_path(part_item.motion_path)

        return []

    def _extract_points_from_path(self, path: QPainterPath) -> list[QPointF]:
        """Extract points from a QPainterPath (approximation for existing paths)."""
        points = []
        # Sample the path at regular intervals
        length = path.length()
        if length > 0:
            num_samples = min(12, max(6, int(length / 20)))  # Adaptive sampling
            for i in range(num_samples):
                percent = i / (num_samples - 1) if num_samples > 1 else 0
                point = path.pointAtPercent(percent)
                points.append(point)
        return points

    def _create_raw_path(self, points: list[QPointF]) -> QPainterPath:
        """Create a path using raw points connected by straight lines."""
        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            if len(points) > 2:
                path.lineTo(points[0])  # Close the path
        return path

    def _create_perfect_ellipse_path(self, points: list[QPointF]) -> QPainterPath:
        """Create a perfect ellipse optimized for the original points' distribution and orientation."""
        if not points:
            return QPainterPath()

        import math

        import numpy as np

        # Convert points to numpy array for easier calculation
        coords = np.array([[p.x(), p.y()] for p in points])

        # Calculate center (centroid)
        center = np.mean(coords, axis=0)
        center_x, center_y = center[0], center[1]

        # Center the points
        centered_coords = coords - center

        # Calculate covariance matrix to find principal axes
        cov_matrix = np.cov(centered_coords.T)

        # Find eigenvalues and eigenvectors (principal components)
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        # Sort eigenvalues and eigenvectors by eigenvalue magnitude (largest first)
        sorted_indices = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_indices]
        eigenvectors = eigenvectors[:, sorted_indices]

        # Principal axes
        major_axis = eigenvectors[:, 0]  # Direction of largest variance
        minor_axis = eigenvectors[:, 1]  # Direction of smallest variance

        # Calculate ellipse radii based on the spread of data along principal axes
        # Project points onto principal axes and find the range
        major_projections = np.dot(centered_coords, major_axis)
        minor_projections = np.dot(centered_coords, minor_axis)

        # Use smaller multiplier to keep ellipse size closer to original (Issue #3)
        # Original used 2 std devs which made ellipse too large
        major_radius = 1.2 * np.std(major_projections)  # Reduced from 2.0 to 1.2
        minor_radius = 1.2 * np.std(minor_projections)  # Reduced from 2.0 to 1.2

        # Ensure minimum radius to avoid degenerate ellipse
        min_radius = 10.0  # Minimum radius in pixels
        major_radius = max(major_radius, min_radius)
        minor_radius = max(minor_radius, min_radius)

        # Calculate rotation angle of the major axis
        rotation_angle = math.atan2(major_axis[1], major_axis[0])

        # Create ellipse path
        path = QPainterPath()
        num_points = max(36, len(points) * 3)  # Smooth ellipse with enough points

        for i in range(num_points + 1):  # +1 to close the ellipse
            # Parametric angle
            t = 2 * math.pi * i / num_points

            # Ellipse in local coordinates (before rotation)
            local_x = major_radius * math.cos(t)
            local_y = minor_radius * math.sin(t)

            # Rotate by the principal axis angle
            cos_rot = math.cos(rotation_angle)
            sin_rot = math.sin(rotation_angle)

            rotated_x = local_x * cos_rot - local_y * sin_rot
            rotated_y = local_x * sin_rot + local_y * cos_rot

            # Translate to center
            x = center_x + rotated_x
            y = center_y + rotated_y

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        return path

    def _create_interpolated_path(self, points: list[QPointF], smoothness_percentage: int) -> QPainterPath:
        """Create a path interpolated between raw points and perfect ellipse with optimal point correspondence."""
        if not points:
            return QPainterPath()

        import math

        import numpy as np

        # Get raw path points
        raw_path_points = points

        # Get ellipse path and center
        ellipse_path = self._create_perfect_ellipse_path(points)

        # Calculate center for angle-based correspondence
        coords = np.array([[p.x(), p.y()] for p in points])
        center = np.mean(coords, axis=0)
        center_x, center_y = center[0], center[1]

        # Find corresponding ellipse points using angular alignment
        ellipse_points = []

        for raw_point in raw_path_points:
            # Calculate angle of raw point relative to center
            raw_angle = math.atan2(raw_point.y() - center_y, raw_point.x() - center_x)

            # Find corresponding point on ellipse using the same angle
            # Convert angle to path parameter (0 to 1)
            # Normalize angle to [0, 2π]
            normalized_angle = (raw_angle + 2 * math.pi) % (2 * math.pi)
            percent = normalized_angle / (2 * math.pi)

            # Get point on ellipse at this parameter
            ellipse_point = ellipse_path.pointAtPercent(percent)
            ellipse_points.append(ellipse_point)

        # Interpolation factor (0.0 = raw, 1.0 = ellipse)
        factor = smoothness_percentage / 100.0

        # Interpolate between raw points and corresponding ellipse points
        interpolated_points = []
        for i in range(len(raw_path_points)):
            raw_p = raw_path_points[i]
            ellipse_p = ellipse_points[i]

            # Linear interpolation
            x = raw_p.x() * (1 - factor) + ellipse_p.x() * factor
            y = raw_p.y() * (1 - factor) + ellipse_p.y() * factor
            interpolated_points.append(QPointF(x, y))

        # Create spline path from interpolated points for additional smoothness
        if hasattr(self.editor_view, '_create_spline_path'):
            # Use lower tension for smoother interpolation
            tension = 0.3 + 0.4 * (factor)  # Tension increases with smoothness
            return self.editor_view._create_spline_path(interpolated_points, closed_loop=True, tension=tension)
        else:
            return self._create_raw_path(interpolated_points)


    def _update_part_path(self, part_name: str, new_path: QPainterPath):
        """Update the motion path for a part in all relevant data structures."""
        # Update the CharacterPartItem
        if part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            part_item.set_motion_path(new_path)

        # Update the project data
        if hasattr(self.main_window, 'project_data_manager') and self.main_window.project_data_manager:
            current_parts = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts and part_name in current_parts:
                current_parts[part_name].motion_path = new_path

        # Update the visual path in EditorView if it exists
        if hasattr(self.editor_view, 'final_paths_map') and part_name in self.editor_view.final_paths_map:
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
        if hasattr(main_window, 'project_data_manager') and main_window.project_data_manager:
            parts_data_to_use = main_window.project_data_manager.get_current_parts_data()

        # Fallback to local parts data if project data manager doesn't have it
        if not parts_data_to_use and hasattr(self, 'current_parts_info') and self.current_parts_info:
            parts_data_to_use = self.current_parts_info

        # Set the parts data in IKManager
        if parts_data_to_use and hasattr(main_window, 'ik_manager') and main_window.ik_manager:
            if hasattr(main_window.ik_manager, 'set_project_parts_data'):
                main_window.ik_manager.set_project_parts_data(parts_data_to_use)
                logging.info(f"[EditorTab] Re-set project parts data in IKManager on tab activation ({len(parts_data_to_use)} parts)")

        # CRITICAL: Re-send skeleton data to IKManager to ensure proper initialization
        if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
            if hasattr(main_window, 'ik_manager') and main_window.ik_manager:
                if hasattr(main_window.ik_manager, 'on_skeleton_data_updated_from_manager'):
                    main_window.ik_manager.on_skeleton_data_updated_from_manager(self._initial_skeleton_data_cache)
                    logging.info("[EditorTab] Re-sent skeleton data to IKManager on tab activation")

        # CRITICAL: Also send current motion paths to IKManager to ensure they're not lost
        current_paths = self._collect_path_data()
        if current_paths and hasattr(main_window, 'ik_manager') and main_window.ik_manager:
            for part_name, motion_path in current_paths.items():
                if hasattr(main_window.ik_manager, 'update_part_motion_path'):
                    main_window.ik_manager.update_part_motion_path(part_name, motion_path)
                    logging.info(f"[EditorTab] Re-sent motion path for {part_name} to IKManager on tab activation")

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
                if hasattr(item, 'motion_path') and item.motion_path and not item.motion_path.isEmpty():
                    return True
        return False
    
    def center_on_character(self):
        """Center the view on the character (all parts)."""
        if not self.editor_scene or not self.current_editor_items:
            return
        
        # Calculate bounding box of all parts
        combined_rect = None
        for part_info in self.current_editor_items.values():
            part_item = part_info.get("graphics_item")
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
        """Handle joint bend direction change from EditorView."""
        logging.info(f"EditorTab: Joint '{joint_id}' bend direction changed to {new_direction}")

        # More detailed debug logging
        if not hasattr(self, 'main_window'):
            logging.error("EditorTab: No main_window attribute!")
            return

        logging.info(f"EditorTab: main_window exists: {self.main_window}")

        if not hasattr(self.main_window, 'skeleton_manager'):
            logging.warning("EditorTab: main_window has no skeleton_manager attribute")
            # List all attributes containing 'skeleton' for debugging
            skeleton_attrs = [attr for attr in dir(self.main_window) if 'skeleton' in attr.lower()]
            logging.info(f"EditorTab: main_window skeleton-related attributes: {skeleton_attrs}")
            return

        sm = self.main_window.skeleton_manager
        logging.info(f"EditorTab: skeleton_manager = {sm}")

        if sm is None:
            logging.warning("EditorTab: skeleton_manager is None")
            return

        # Call set_joint_bend_direction
        logging.info(f"EditorTab: Calling skeleton_manager.set_joint_bend_direction('{joint_id}', {new_direction})")
        try:
            sm.set_joint_bend_direction(joint_id, new_direction)
            logging.info("EditorTab: Successfully called set_joint_bend_direction")
        except Exception as e:
            logging.error(f"EditorTab: Error calling set_joint_bend_direction: {e}", exc_info=True)

        # Store in cached skeleton data if available
        if self._initial_skeleton_data_cache and 'joints' in self._initial_skeleton_data_cache:
            joints = self._initial_skeleton_data_cache['joints']
            if joint_id in joints:
                joints[joint_id]['bend_direction'] = new_direction
                logging.info(f"EditorTab: Updated bend_direction in cached skeleton data for joint '{joint_id}'")
