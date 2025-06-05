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
    QGraphicsEllipseItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QTimer
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPixmap, QPen, QBrush

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene
from ..graphics_items.part_item import CharacterPartItem
from automataii.core.models import PartInfo

from PyQt6.QtGui import QPainterPath
from ..dialogs.recommendation_dialog import MechanismRecommendationDialog, MECHANISM_TYPE_USER_DISPLAY_4_BAR, MECHANISM_TYPE_USER_DISPLAY_3_BAR, MECHANISM_TYPE_USER_DISPLAY_CAM
from .utils import get_project_root

class EditorTab(QWidget):
    # Signals this tab might emit
    request_define_joint = pyqtSignal(
        str, str
    )  # part1_name, part2_name (or use view's signal directly in MW)
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
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
    request_reset_all_animations = pyqtSignal() # New signal
    motion_path_updated = pyqtSignal(str, QPainterPath) # part_name, path

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = (
            main_window  # Reference to MainWindow for global actions, data, status bar
        )
        self.debug_mode = getattr(main_window, 'debug_mode', False) # Get debug_mode from main_window

        # Instantiate scene and view here
        self.editor_scene = QGraphicsScene(self)
        self.editor_view = EditorView(self.editor_scene, self) # Pass self (EditorTab) as parent to EditorView

        # --- UI Elements owned by this tab ---
        self.parts_list: Optional[QListWidget] = None
        self.part_properties_group: Optional[QGroupBox] = None
        self.z_value_spin: Optional[QDoubleSpinBox] = None
        self.fixed_part_check: Optional[QCheckBox] = None

        self.define_motion_path_btn: Optional[QPushButton] = None
        self.clear_motion_path_btn: Optional[QPushButton] = None

        self.play_btn: Optional[QPushButton] = None
        self.stop_btn: Optional[QPushButton] = None
        self.reset_sim_btn: Optional[QPushButton] = (
            None  # This is the general simulation reset
        )
        self.reset_all_animations_btn: Optional[QPushButton] = (
            None  # This is for paths/poses
        )

        self.toggle_anchors_btn: Optional[QCheckBox] = None
        self.mechanism_type_combo: Optional[QComboBox] = None
        self.mech_inputs_container: Optional[QWidget] = None
        self.mech_inputs_layout: Optional[QVBoxLayout] = (
            None  # Keep if needed for dynamic add/remove
        )

        self.cam_inputs_group: Optional[QGroupBox] = None
        self.select_cam_center_btn: Optional[QPushButton] = None
        self.three_bar_inputs_group: Optional[QGroupBox] = None
        self.select_pivot_a_3bar_btn: Optional[QPushButton] = None
        self.four_bar_inputs_group: Optional[QGroupBox] = None
        self.select_pivot_a_4bar_btn: Optional[QPushButton] = None
        self.select_pivot_d_4bar_btn: Optional[QPushButton] = None
        self.gear_inputs_group: Optional[QGroupBox] = None
        self.select_driver_center_btn: Optional[QPushButton] = None
        self.select_driven_center_btn: Optional[QPushButton] = None
        self.gear_ratio_spin: Optional[QDoubleSpinBox] = None
        self.generate_mechanism_btn: Optional[QPushButton] = None

        self.layer_group: Optional[QGroupBox] = None  # For mechanism layers
        self.layer_layout: Optional[QVBoxLayout] = None  # For mechanism layers

        self.blueprint_btn: Optional[QPushButton] = None
        self.save_alignment_btn: Optional[QPushButton] = None

        self.zoom_combo: Optional[QComboBox] = None
        self.fit_btn: Optional[QPushButton] = None

        # Data specific to this tab
        self.selected_part_name: Optional[str] = None
        self.current_parts_info: Dict[str, PartInfo] = {}
        self.current_editor_items: Dict[str, CharacterPartItem] = {}

        # Store for generated mechanism visuals
        self.mechanism_visual_items: List[QGraphicsItem] = []

        # Store for defined joints within this tab
        self.joints: List[Dict] = [] # List of joint data dictionaries

        # Cache for initial skeleton data, to be set by MainWindow
        self._initial_skeleton_data_cache: Optional[Dict] = None

        # Mechanism selection points - moved from MainWindow
        self.selected_cam_center: Optional[QPointF] = None
        self.selected_pivot_a: Optional[QPointF] = None
        self.selected_pivot_d: Optional[QPointF] = None
        self.selected_driver_center: Optional[QPointF] = None
        self.selected_driven_center: Optional[QPointF] = None
        # Markers for selected points - these will be drawn by EditorView, state can be here
        self.cam_center_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_a_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_d_marker: Optional[QGraphicsEllipseItem] = None
        self.driver_center_marker: Optional[QGraphicsEllipseItem] = None
        self.driven_center_marker: Optional[QGraphicsEllipseItem] = None

        # Mechanism Simulation Timer and state
        self.mechanism_simulation_timer = QTimer(self)
        self.mechanism_simulation_timer.timeout.connect(self._update_mechanism_simulation)
        self.current_mechanism_crank_angle_rad = 0.0 # For the loaded mechanism
        self.mechanism_simulation_angular_step = math.radians(2.0) # Degrees per step
        self.is_mechanism_simulating = False
        self._initial_mechanism_crank_angle_rad = 0.0 # Store initial angle for reset

        self.current_simulation_state: str = "stopped" # For logging IK updates
        self.ik_log_counter: Dict[str, int] = {} # To limit logs per part/state

        self._init_ui()

        # Connect signals from self.editor_view now that it exists
        self._connect_editor_view_signals()

    def _connect_editor_view_signals(self):
        """Connect signals from this tab's EditorView instance."""
        self.editor_view.freehandPathCompleted.connect(self._handle_freehand_path_completed)
        self.editor_view.drawing_cancelled.connect(self._handle_drawing_cancelled)
        self.editor_view.joint_defined.connect(self.handle_joint_defined)
        # Mechanism point selection signals from EditorView connected to EditorTab slots
        self.editor_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.editor_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        self.editor_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        self.editor_view.driver_center_selected.connect(self._handle_driver_center_set)
        self.editor_view.driven_center_selected.connect(self._handle_driven_center_set)
        self.editor_view.zoom_changed.connect(self._update_zoom_combo_from_view)

        # Connect to new EditorView signals for item interactions
        self.editor_view.part_item_clicked.connect(self._handle_part_item_clicked_from_view)
        self.editor_view.part_item_double_clicked.connect(self._handle_part_item_double_clicked_from_view)
        # self.editor_view.part_item_moved.connect(self._handle_part_item_moved_from_view) # Deferred

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left Control Panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(280)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        # control_panel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred) #This can cause issues
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(12)

        # Parts List Group
        parts_group = QGroupBox("Character Parts")
        parts_layout = QVBoxLayout(parts_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("List of loaded character parts")
        self.parts_list.setMinimumHeight(100)
        parts_layout.addWidget(self.parts_list)
        panel_layout.addWidget(parts_group)

        # Selected Part Properties Group
        self.part_properties_group = QGroupBox("Selected Part Properties")
        part_props_layout = QFormLayout(
            self.part_properties_group
        )  # Changed from self.main_window.part_props
        part_props_layout.setSpacing(8)
        self.z_value_spin = QDoubleSpinBox()
        self.z_value_spin.setRange(-100, 100)
        self.z_value_spin.setSingleStep(0.1)
        self.z_value_spin.setToolTip("Adjust Z-depth (layering)")
        self.z_value_spin.setEnabled(False)
        self.fixed_part_check = QCheckBox("Fixed in Place")
        self.fixed_part_check.setToolTip(
            "If checked, this part will not move during simulation (unless it is the root of a chain being driven by IK)."
        )
        self.fixed_part_check.setEnabled(False)
        part_props_layout.addRow("Z-Value:", self.z_value_spin)
        part_props_layout.addRow(self.fixed_part_check)
        self.part_properties_group.setEnabled(False)
        self.part_properties_group.setVisible(
            False
        )  # Visibility controlled by OptionsTab signal now
        panel_layout.addWidget(self.part_properties_group)

        # Motion Path Definition Group
        motion_path_group = QGroupBox("Motion Path")
        motion_path_layout = QVBoxLayout(motion_path_group)
        self.define_motion_path_btn = QPushButton("Draw Motion Path")
        self.define_motion_path_btn.setCheckable(True)
        self.define_motion_path_btn.setToolTip(
            "Toggle mode to draw a motion path for the selected part."
        )
        self.define_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.define_motion_path_btn)
        self.clear_motion_path_btn = QPushButton("Clear Motion Path")
        self.clear_motion_path_btn.setToolTip(
            "Clear the motion path for the selected part."
        )
        self.clear_motion_path_btn.setEnabled(False)
        motion_path_layout.addWidget(self.clear_motion_path_btn)
        panel_layout.addWidget(motion_path_group)

        # Motion & Simulation Group
        motion_sim_group = QGroupBox("Motion & Simulation")
        motion_sim_layout = QFormLayout(motion_sim_group)
        motion_sim_layout.setSpacing(10)
        sim_button_layout = QHBoxLayout()
        sim_button_layout.setSpacing(6)
        style = self.style()  # Use self.style()
        self.play_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), ""
        )
        self.play_btn.setToolTip("Play Simulation")
        self.stop_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), ""
        )
        self.stop_btn.setToolTip("Stop Simulation")
        self.stop_btn.setEnabled(False)
        # self.reset_sim_btn below is the one for the general simulation reset.
        # The one in Animation Controls group is specific to Animation Paths/Poses.
        self.reset_sim_btn = QPushButton(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), ""
        )
        self.reset_sim_btn.setToolTip("Restart Simulation from initial state")
        self.reset_sim_btn.setEnabled(False)
        sim_button_layout.addWidget(self.play_btn)
        sim_button_layout.addWidget(self.stop_btn)
        sim_button_layout.addWidget(self.reset_sim_btn)
        motion_sim_layout.addRow(sim_button_layout)
        panel_layout.addWidget(motion_sim_group)

        # Mechanism Design Group
        mech_design_group = QGroupBox("Mechanism Design")
        mech_design_layout = QVBoxLayout(mech_design_group)
        mech_design_layout.setSpacing(10)
        # self.toggle_anchors_btn = QCheckBox("Show Test Anchors")
        # self.toggle_anchors_btn.setToolTip(
        #     "Show/hide draggable test anchor points in the scene."
        # )
        # mech_design_layout.addWidget(self.toggle_anchors_btn)
        # mech_type_layout = QFormLayout()
        # self.mechanism_type_combo = QComboBox()
        # self.mechanism_type_combo.addItems(
        #     ["Cam & Follower", "3-Bar Linkage", "4-Bar Linkage", "Gears (Simple Pair)"]
        # )
        # self.mechanism_type_combo.setToolTip("Select the type of mechanism to generate")
        # mech_type_layout.addRow("Type:", self.mechanism_type_combo)
        # mech_design_layout.addLayout(mech_type_layout)
        # self.mech_inputs_container = QWidget()
        # self.mech_inputs_layout = QVBoxLayout(
        #     self.mech_inputs_container
        # )  # Layout to hold dynamic groups
        # self.mech_inputs_layout.setContentsMargins(0, 5, 0, 0)
        # self.mech_inputs_layout.setSpacing(8)
        # mech_design_layout.addWidget(self.mech_inputs_container)

        # self.cam_inputs_group = QGroupBox("Cam Settings")
        # cam_inputs_layout = QVBoxLayout(self.cam_inputs_group)
        # self.select_cam_center_btn = QPushButton("Select Cam Center")
        # self.select_cam_center_btn.setToolTip(
        #     "Click in the scene to set the cam rotation center (default: torso center)"
        # )
        # cam_inputs_layout.addWidget(self.select_cam_center_btn)
        # self.mech_inputs_layout.addWidget(self.cam_inputs_group)

        # self.three_bar_inputs_group = QGroupBox("3-Bar Linkage Settings")
        # three_bar_layout = QVBoxLayout(self.three_bar_inputs_group)
        # self.select_pivot_a_3bar_btn = QPushButton("Select Fixed Pivot A")
        # self.select_pivot_a_3bar_btn.setToolTip(
        #     "Click in the scene to set the first fixed pivot"
        # )
        # three_bar_layout.addWidget(self.select_pivot_a_3bar_btn)
        # self.mech_inputs_layout.addWidget(self.three_bar_inputs_group)

        # self.four_bar_inputs_group = QGroupBox("4-Bar Linkage Settings")
        # four_bar_layout = QVBoxLayout(self.four_bar_inputs_group)
        # self.select_pivot_a_4bar_btn = QPushButton("Select Fixed Pivot A")
        # self.select_pivot_a_4bar_btn.setToolTip(
        #     "Click in the scene to set the first fixed pivot"
        # )
        # four_bar_layout.addWidget(self.select_pivot_a_4bar_btn)
        # self.select_pivot_d_4bar_btn = QPushButton("Select Fixed Pivot D")
        # self.select_pivot_d_4bar_btn.setToolTip(
        #     "Click in the scene to set the second fixed pivot"
        # )
        # four_bar_layout.addWidget(self.select_pivot_d_4bar_btn)
        # self.mech_inputs_layout.addWidget(self.four_bar_inputs_group)

        # self.gear_inputs_group = QGroupBox("Gear Settings")
        # gear_inputs_layout = QFormLayout(self.gear_inputs_group)
        # gear_button_layout = QHBoxLayout()
        # self.select_driver_center_btn = QPushButton("Driver Center")
        # self.select_driver_center_btn.setToolTip("Click to set driver gear center")
        # self.select_driven_center_btn = QPushButton("Driven Center")
        # self.select_driven_center_btn.setToolTip("Click to set driven gear center")
        # gear_button_layout.addWidget(self.select_driver_center_btn)
        # gear_button_layout.addWidget(self.select_driven_center_btn)
        # gear_inputs_layout.addRow("Select Centers:", gear_button_layout)
        # self.gear_ratio_spin = QDoubleSpinBox()
        # self.gear_ratio_spin.setRange(0.01, 100.0)
        # self.gear_ratio_spin.setSingleStep(0.1)
        # self.gear_ratio_spin.setValue(1.0)
        # self.gear_ratio_spin.setToolTip(
        #     "Set gear ratio (Driven Radius / Driver Radius)"
        # )
        # gear_inputs_layout.addRow("Gear Ratio:", self.gear_ratio_spin)
        # self.mech_inputs_layout.addWidget(self.gear_inputs_group)

        self.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.generate_mechanism_btn.setToolTip(
            "Generate the selected mechanism based on the current setup"
        )
        self.generate_mechanism_btn.setEnabled(False)
        mech_design_layout.addWidget(self.generate_mechanism_btn)
        # mech_design_layout.addStretch() # Removed to allow layer group to be below
        panel_layout.addWidget(mech_design_group)

        # self._update_mechanism_inputs_ui(
        #     self.mechanism_type_combo.currentText()
        # )  # Call local method

        # Mechanism Layers Group
        self.layer_group = QGroupBox("Mechanism Layers")
        self.layer_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )  # Keep preferred
        self.layer_layout = QVBoxLayout(self.layer_group)
        self.layer_layout.setSpacing(6)
        panel_layout.addWidget(self.layer_group)

        # Export Group
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)
        self.blueprint_btn = QPushButton("Generate Blueprint (SVG)")
        self.blueprint_btn.setToolTip(
            "Generate an SVG blueprint of all parts for fabrication"
        )
        export_layout.addWidget(self.blueprint_btn)
        panel_layout.addWidget(export_group)

        # Character Alignment Group
        alignment_group = QGroupBox("Character Alignment")
        alignment_layout = QVBoxLayout(alignment_group)
        self.save_alignment_btn = QPushButton("Save Current Alignment")
        self.save_alignment_btn.setToolTip(
            "Save the current character position as the default alignment for this character."
        )
        self.save_alignment_btn.setEnabled(False)
        alignment_layout.addWidget(self.save_alignment_btn)
        panel_layout.addWidget(alignment_group)

        # Animation Controls Group (for motion paths / IK pose reset)

        panel_layout.addStretch()
        control_panel.adjustSize()  # Adjust size before setting to scroll area
        scroll_area.setWidget(control_panel)

        # Right View Area (EditorView is owned by MainWindow)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        # Zoom Toolbar (for EditorView)
        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedSize(70, 28)
        self.zoom_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: white;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #586069;
            }
        """)
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.zoom_combo.addItems(zoom_levels)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom level for editor view")

        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setFixedSize(45, 28)
        self.fit_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 4px 4px;
                background-color: white;
                font-size: 13px;
                color: #24292f;
            }
            QPushButton:hover {
                background-color: #f6f8fa;
                border-color: #586069;
            }
            QPushButton:pressed {
                background-color: #e9ecef;
            }
        """)
        self.fit_btn.setToolTip("Zoom to fit all items in editor view")

        zoom_layout.addWidget(self.zoom_combo)
        zoom_layout.addWidget(self.fit_btn)

        right_layout.addWidget(self.editor_view, 1)

        zoom_toolbar.setParent(right_panel)  # Attach to right_panel for positioning
        zoom_toolbar.setStyleSheet("""
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """)
        zoom_toolbar.show()

        def position_editor_zoom_toolbar():
            if not right_panel.isVisible() or not zoom_toolbar.isVisible():
                return
            toolbar_width = zoom_toolbar.sizeHint().width()
            toolbar_height = zoom_toolbar.sizeHint().height()
            x = right_panel.width() - toolbar_width - 10
            y = right_panel.height() - toolbar_height - 10
            zoom_toolbar.setGeometry(x, y, toolbar_width, toolbar_height)

        original_show_event = right_panel.showEvent

        def new_show_event(event):
            original_show_event(event)
            QApplication.instance().processEvents()
            position_editor_zoom_toolbar()

        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent

        def new_resize_event(event):
            original_resize_event(event)
            position_editor_zoom_toolbar()

        right_panel.resizeEvent = new_resize_event
        if right_panel.isVisible():  # Initial position if already visible
            QApplication.instance().processEvents()
            position_editor_zoom_toolbar()

        layout.addWidget(scroll_area)
        layout.addWidget(right_panel, 1)
        self.setLayout(layout)

        # Connect signals to internal methods or emit signals
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        self.parts_list.itemClicked.connect(
            self._handle_part_list_click
        )  # Assuming this method will be added
        self.z_value_spin.valueChanged.connect(self._update_selected_part_z)
        self.fixed_part_check.stateChanged.connect(self._update_selected_part_fixed)

        self.define_motion_path_btn.toggled.connect(
            self._toggle_define_motion_path_mode
        )
        self.clear_motion_path_btn.clicked.connect(
            self._clear_selected_item_motion_path
        )

        self.play_btn.clicked.connect(self._play_simulation_clicked)
        self.stop_btn.clicked.connect(self._stop_simulation_clicked)
        self.reset_sim_btn.clicked.connect(
            self._reset_simulation_clicked
        )  # General sim reset

        # self.toggle_anchors_btn.toggled.connect(
        #     self._toggle_test_anchors_visibility_in_view
        # )
        # self.mechanism_type_combo.currentTextChanged.connect(
        #     self._update_mechanism_inputs_ui
        # )
        # self.mechanism_type_combo.currentTextChanged.connect(
        #     self._update_generate_mechanism_button_state
        # )

        # self.select_cam_center_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("cam_center")
        # )
        # self.select_pivot_a_3bar_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("pivot_a_3bar")
        # )
        # self.select_pivot_a_4bar_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("pivot_a_4bar")
        # )
        # self.select_pivot_d_4bar_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("pivot_d_4bar")
        # )
        # self.select_driver_center_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("driver_center")
        # )
        # self.select_driven_center_btn.clicked.connect(
        #     lambda: self._select_mechanism_point("driven_center")
        # )

        self.generate_mechanism_btn.clicked.connect(self._generate_mechanism_clicked)
        self.blueprint_btn.clicked.connect(self.request_generate_blueprint.emit)
        self.save_alignment_btn.clicked.connect(self.request_save_alignment.emit)

        self.zoom_combo.currentTextChanged.connect(self._handle_zoom_change)
        self.fit_btn.clicked.connect(self._handle_zoom_change_fit)

        self._update_button_states()  # Initial button states

    # --- Method Stubs/Implementations ---
    def _handle_part_selection_change(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ):
        """Handles selection changes from the parts_list QListWidget."""
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole) # Get part name from item data
            if part_name and part_name in self.current_editor_items:
                self.selected_part_name = part_name
                # Highlight in scene (EditorView handles visual selection based on QGraphicsScene selection model)
                # Ensure the scene's selection model is updated if list widget drives selection
                item_to_select = self.current_editor_items[part_name]
                self.editor_scene.clearSelection() # Clear previous scene selection
                item_to_select.setSelected(True)   # Select the item in the scene

                logging.debug(f"EditorTab: Part '{part_name}' selected via list.")
            else:
                self.selected_part_name = None
                self.editor_scene.clearSelection()
        else:
            self.selected_part_name = None
            self.editor_scene.clearSelection()

        self.update_part_properties_panel(self.selected_part_name)
        self._update_button_states()

    def _handle_part_list_click(self, item: QListWidgetItem):
        # Currently, currentItemChanged handles selection. This could be for other interactions.
        logging.info(f"Part list item clicked: {item.text()}")

    def _update_selected_part_z(self, z_value: float):
        if (
            self.selected_part_name
            and self.selected_part_name in self.current_editor_items
        ):
            part_item = self.current_editor_items[self.selected_part_name]
            part_item.setZValue(z_value)
            # Update stored PartInfo
            if self.selected_part_name in self.current_parts_info:
                self.current_parts_info[self.selected_part_name].z_value = z_value
            # self.main_window.editor_scene.update() # Scene is local now
            self.editor_scene.update() # Ensure scene redraws
            logging.info(f"Set Z-value for {self.selected_part_name} to {z_value}")

    def _update_selected_part_fixed(self, state_int: int):
        is_fixed = bool(state_int == Qt.CheckState.Checked.value)
        if (
            self.selected_part_name
            and self.selected_part_name in self.current_editor_items
        ):
            part_item = self.current_editor_items[self.selected_part_name]
            part_item.set_fixed(is_fixed)
            # Update stored PartInfo
            if self.selected_part_name in self.current_parts_info:
                self.current_parts_info[self.selected_part_name].fixed = is_fixed
            logging.info(f"Set fixed state for {self.selected_part_name} to {is_fixed}")

    def _toggle_define_motion_path_mode(self, checked: bool):
        if not self.selected_part_name:
            self.define_motion_path_btn.setChecked(False) # Ensure button is off if no selection
            self.editor_view.set_mode('select') # Ensure view is in select mode
            return

        selected_part_item = self.current_editor_items.get(self.selected_part_name)
        if not selected_part_item:
            self.define_motion_path_btn.setChecked(False)
            self.editor_view.set_mode('select')
            logging.warning(f"EditorTab: Selected part '{self.selected_part_name}' not found for motion path.")
            return

        if checked:
            # Entering mode
            self.editor_view.start_define_motion_path(selected_part_item)
            self.main_window.statusBar().showMessage(
                f"Draw motion path for {self.selected_part_name}. Click & drag. Esc or toggle button to exit."
            )
        else:
            # Exiting mode
            self.editor_view.finish_motion_path_drawing()
            self.main_window.statusBar().showMessage("Draw motion path mode ended.")

    def _clear_selected_item_motion_path(self):
        if (
            self.selected_part_name
            and self.selected_part_name in self.current_editor_items
        ):
            part_item = self.current_editor_items[self.selected_part_name]
            if part_item.motion_path_item:
                self.editor_scene.removeItem(part_item.motion_path_item)
                part_item.motion_path_item = None
                part_item.motion_path_points = []
                # Also clear from self.current_parts_info if stored there
                if self.selected_part_name in self.current_parts_info:
                    self.current_parts_info[self.selected_part_name].motion_path = []
                logging.info(f"Cleared motion path for {self.selected_part_name}")
                self.main_window.statusBar().showMessage(
                    f"Motion path cleared for {self.selected_part_name}"
                )
            else:
                self.main_window.statusBar().showMessage(
                    f"No motion path to clear for {self.selected_part_name}"
                )
        self._update_button_states()

    def _play_simulation_clicked(self):
        self.request_play_simulation.emit()
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reset_sim_btn.setEnabled(False)  # Can't reset while playing

        if self.mechanism_visual_items: # Only start if a mechanism is loaded
            self.is_mechanism_simulating = True
            self.mechanism_simulation_timer.start(30) # Approx 33 FPS
            logging.info("Mechanism simulation started.")

    def _stop_simulation_clicked(self):
        self.request_stop_simulation.emit()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(True)

        if self.is_mechanism_simulating:
            self.is_mechanism_simulating = False
            self.mechanism_simulation_timer.stop()
            logging.info("Mechanism simulation stopped.")

    def _reset_simulation_clicked(self):
        self.request_reset_simulation.emit()
        # Stop mechanism simulation and reset its state
        if self.is_mechanism_simulating:
            self.is_mechanism_simulating = False
            self.mechanism_simulation_timer.stop()

        self.current_mechanism_crank_angle_rad = self._initial_mechanism_crank_angle_rad

        # Re-display mechanism in its initial pose if it exists
        # This requires storing the data of the last loaded mechanism or re-fetching if necessary
        # For now, let's assume if mechanism_visual_items exist, we can re-evaluate its initial pose
        # This part might need refinement: if _load_and_display_mechanism clears and redraws,
        # it needs the original mechanism_data and user_path_center.
        # A simple approach: if items exist, clear and re-load the *last known* mechanism.
        # This implies storing `self.last_loaded_mechanism_data` and `self.last_user_path_center`.
        # For now, we will just reset the angle. A full redraw to initial state
        # would be more robust if _load_and_display_mechanism is called.
        # Let's simplify: if a mechanism is loaded (visual items exist), update it to initial angle.
        if self.mechanism_visual_items and hasattr(self, '_loaded_mechanism_params') and self._loaded_mechanism_params:
             # Re-solve for initial angle and update visuals
            mech_data_for_reset = self._loaded_mechanism_params.get("data")
            user_path_center_for_reset = self._loaded_mechanism_params.get("user_path_center")
            if mech_data_for_reset and user_path_center_for_reset:
                 # We call a specialized update, not full load, to avoid re-creating items, just update lines
                 self._update_displayed_mechanism_pose(self.current_mechanism_crank_angle_rad, mech_data_for_reset, user_path_center_for_reset)
            logging.info(f"Mechanism reset to initial angle: {math.degrees(self.current_mechanism_crank_angle_rad):.1f} deg")

        # Reset skeleton visualization to its cached initial state
        if self._initial_skeleton_data_cache:
            # Use a copy of the cached data to avoid modifying the cache if on_skeleton_updated does
            self.on_skeleton_updated(self._initial_skeleton_data_cache.copy())
            logging.info("EditorTab: Skeleton visualization reset to cached initial state.")
        else:
            # Fallback if no cached data (e.g., parts were never loaded or cleared by MainWindow)
            self.on_skeleton_updated(None)
            logging.warning("EditorTab: No cached initial skeleton data for reset. Skeleton will be cleared.")

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(
            False
        )
        self._update_button_states()

    def _generate_mechanism_clicked(self):
        # This method is called when the "Generate Mechanism" button is clicked.
        # It should:
        # 1. Get the motion path from the currently selected CharacterPartItem in EditorView.
        # 2. Open the MechanismRecommendationDialog with this path.
        # 3. Handle the selected mechanism from the dialog.

        if not self.selected_part_name:
            QMessageBox.warning(self, "No Part Selected", "Please select a character part first.")
            return

        part_item = self.current_editor_items.get(self.selected_part_name)
        if not part_item:
            QMessageBox.warning(self, "Part Not Found", f"Could not find the editor item for part: {self.selected_part_name}")
            return

        # Attempt to get QPainterPath from the part_item
        # This assumes CharacterPartItem has a method or attribute to access its QPainterPath
        # For example, if it stores the QGraphicsPathItem for its motion path:
        user_motion_path: Optional[QPainterPath] = None
        if hasattr(part_item, 'motion_path_item') and part_item.motion_path_item is not None:
            user_motion_path = part_item.motion_path_item.path()
        elif hasattr(part_item, 'part_info') and hasattr(part_item.part_info, 'motion_path_data') and isinstance(part_item.part_info.motion_path_data, QPainterPath):
            user_motion_path = part_item.part_info.motion_path_data

        if not user_motion_path or user_motion_path.isEmpty():
            QMessageBox.warning(self, "No Motion Path", f"No motion path defined for the selected part: {self.selected_part_name}. Please draw a path first.")
            return

        # Define the path to the generated mechanism paths JSON file
        # This should ideally be a more robust way to get the project path
        try:
            # Attempt to use a utility function if available
            project_root_str = get_project_root() # Assuming it might return str or Path
            project_root = Path(project_root_str) # Ensure it's a Path object
            generated_paths_filepath = str(project_root / "kinematics" / "generated_mechanism_paths.json")
        except NameError: # Fallback if get_project_root is not defined or fails
             # This relative path might be fragile depending on execution context
            logging.warning("get_project_root utility not found. Using potentially fragile relative path for JSON.")
            base_path = Path(__file__).resolve().parent.parent.parent # automataii directory
            generated_paths_filepath = str(base_path / "kinematics" / "generated_mechanism_paths.json")
            # For a more direct approach if this file is in automataii/gui/tabs
            # and json is in automataii/kinematics
            # Assumes structure: automataii/gui/tabs/editor_tab.py
            #                   automataii/kinematics/generated_mechanism_paths.json

        # Ensure the file exists before proceeding
        if not Path(generated_paths_filepath).exists():
            QMessageBox.critical(self, "Error", f"Mechanism data file not found at: {generated_paths_filepath}")
            logging.error(f"Mechanism data file not found: {generated_paths_filepath}")
            return

        logging.debug(f"EditorTab: Showing MechanismRecommendationDialog for part '{self.selected_part_name}' with path and JSON: {generated_paths_filepath}")

        selected_mechanism = MechanismRecommendationDialog.get_recommendation(
            user_motion_path=user_motion_path,
            generated_paths_filepath=generated_paths_filepath,
            parent=self
        )

        if selected_mechanism:
            # TODO: Implement loading and simulation of the selected mechanism
            # For now, just log the selection
            logging.info(f"Mechanism selected: {selected_mechanism.get('name')}, Type: {selected_mechanism.get('type')}")
            # QMessageBox.information(self, "Mechanism Selected",
            #                         f"Selected: {selected_mechanism.get('name')}\\nType: {selected_mechanism.get('type')}\\nScore (Hausdorff): {selected_mechanism.get('overall_score'):.4f}")

            # Calculate center of user path to pass for mechanism placement
            user_path_center = QPointF(0,0) # Default
            if user_motion_path and not user_motion_path.isEmpty():
                user_path_center = user_motion_path.boundingRect().center()

            # Store for potential reset
            self._loaded_mechanism_params = {"data": selected_mechanism, "user_path_center": user_path_center}
            self._load_and_display_mechanism(selected_mechanism, user_path_center)

            # Here, you would typically emit a signal or call a method to
            # load the mechanism definition into the EditorView,
            # set up its simulation parameters, etc.
            # Example: self.request_load_mechanism_into_scene.emit(selected_mechanism)

        else:
            logging.info("Mechanism recommendation dialog was cancelled or no mechanism selected.")
            # self.main_window.statusBar().showMessage("Mechanism selection cancelled.", 2000)

    def _handle_zoom_change(self, zoom_text: str):
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
        self.editor_view.zoom_to_fit()
        # _update_zoom_combo_from_view will be called by editor_view's signal

    def _update_zoom_combo_from_view(self, scale_factor: float):
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{int(scale_factor * 100)}%")
        self.zoom_combo.blockSignals(False)

    def populate_parts_list(self):
        self.parts_list.clear()
        if not self.current_parts_info: # Check if there's data to populate from
            self.update_part_properties_panel(None)
            self._update_button_states()
            self.parts_loaded.emit(False)
            return

        sorted_part_names = sorted(
            self.current_parts_info.keys(),
            key=lambda name: self.current_parts_info[name].z_value,
            reverse=True,
        )
        for part_name in sorted_part_names:
            item = QListWidgetItem(part_name)
            item.setData(Qt.ItemDataRole.UserRole, part_name) # Store part_name in UserRole
            self.parts_list.addItem(item)
        self.update_part_properties_panel(None)  # Clear properties panel initially
        self._update_button_states()
        self.parts_loaded.emit(self.parts_list.count() > 0)

    def update_part_properties_panel(self, part_name: Optional[str]):
        if part_name and part_name in self.current_parts_info:
            part_info = self.current_parts_info[part_name]
            self.z_value_spin.setValue(part_info.z_value)
            self.fixed_part_check.setChecked(part_info.fixed)
            self.part_properties_group.setEnabled(True)
            self.z_value_spin.setEnabled(True)
            self.fixed_part_check.setEnabled(True)
        else:
            self.part_properties_group.setEnabled(False)
            self.z_value_spin.setEnabled(False)
            self.fixed_part_check.setEnabled(False)
            self.z_value_spin.setValue(0)  # Reset
            self.fixed_part_check.setChecked(False)  # Reset

    def _update_button_states(self):
        has_parts = self.parts_list.count() > 0 if self.parts_list else False # Add check for self.parts_list
        has_selection = self.selected_part_name is not None
        is_sim_playing = self.stop_btn.isEnabled() if self.stop_btn else False # Add check for self.stop_btn

        if self.define_motion_path_btn: self.define_motion_path_btn.setEnabled(has_selection and not is_sim_playing)
        if self.clear_motion_path_btn:
            self.clear_motion_path_btn.setEnabled(
                has_selection
                and not is_sim_playing
                and self._get_selected_part_has_motion_path()
            )

        if self.play_btn: self.play_btn.setEnabled(has_parts and not is_sim_playing)
        # stop_btn state handled by play/stop clicks
        if self.reset_sim_btn:
            self.reset_sim_btn.setEnabled(
                has_parts and not is_sim_playing
            )  # General sim reset

        # self.generate_mechanism_btn is now handled by _update_generate_mechanism_button_state
        # Remove direct enabling/disabling from here if it exists, or ensure it's consistent.
        # For now, let's rely on the specific method.

        if self.blueprint_btn: self.blueprint_btn.setEnabled(has_parts)
        if self.save_alignment_btn: self.save_alignment_btn.setEnabled(has_parts)
        self._update_generate_mechanism_button_state()  # Ensure this is called to update the specific button

    def _get_selected_part_has_motion_path(self) -> bool:
        if (
            self.selected_part_name
            and self.selected_part_name in self.current_editor_items
        ):
            part_item = self.current_editor_items[self.selected_part_name]
            return bool(part_item.motion_path and not part_item.motion_path.isEmpty())
        return False

    # --- Slots for MainWindow signals / Data update methods ---
    def set_parts_data(self, parts_info: Dict[str, PartInfo]):
        """Sets parts data for the editor, creating CharacterPartItem instances."""
        self.clear_editor_content() # Clear previous content first

        self.current_parts_info = parts_info if parts_info else {}
        created_editor_items: Dict[str, CharacterPartItem] = {}

        if not self.current_parts_info:
            logging.info("EditorTab: No parts data to set.")
            self.parts_loaded.emit(False)
            self.populate_parts_list() # Update list (will be empty)
            self._update_button_states()
            return

        project_dir = None
        if self.main_window and hasattr(self.main_window, 'project_data_manager') and self.main_window.project_data_manager.project_dir:
            project_dir = self.main_window.project_data_manager.project_dir
        else:
            logging.error("EditorTab: Project directory not available from ProjectDataManager. Part items may not load correctly.")
            # Show a message to the user, as this is critical
            QMessageBox.critical(self, "Error", "Project directory is missing. Cannot load part textures.")
            self.parts_loaded.emit(False)
            self.populate_parts_list()
            self._update_button_states()
            return

        for part_name, p_info in self.current_parts_info.items():
            # CharacterPartItem now loads its own texture using project_dir and p_info.name
            item = CharacterPartItem(part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode) # Pass debug_mode

            self.editor_scene.addItem(item)
            created_editor_items[part_name] = item

        self.current_editor_items = created_editor_items

        self.parts_loaded.emit(True)
        self.populate_parts_list()
        self._update_button_states()
        self.editor_view.zoom_to_fit() # Adjust view after loading parts
        logging.info(f"EditorTab: Added {len(self.current_editor_items)} items to the scene.")

    def clear_editor_content(self):
        """Clears all parts, joints, and mechanism visuals from the editor scene."""
        logging.info("EditorTab: Content cleared.")
        if not self.editor_scene:
            logging.warning("EditorTab: Scene not available to clear content.")
            return

        # Clear CharacterPartItems
        for item in list(self.current_editor_items.values()): # Iterate over a copy
            if item.scene() == self.editor_scene: # Check if item is in this scene
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
        self.joints.clear() # Clear the joint data list

        # Clear Mechanism Visuals
        for item in self.mechanism_visual_items:
            if item.scene() == self.editor_scene:
                self.editor_scene.removeItem(item)
        self.mechanism_visual_items.clear()

        self.selected_part_name = None
        self.populate_parts_list()  # Update list (will be empty)
        self.update_part_properties_panel(None)
        self._update_button_states()
        self.editor_view.reset_temp_visuals() # Clear any temporary drawing items in view
        self.editor_view.set_mode("select")

        self.parts_cleared.emit()
        self.parts_loaded.emit(False)
        self._initial_skeleton_data_cache = None # Clear cached skeleton data when editor content is cleared
        logging.info("EditorTab: Cleared cached initial skeleton data.")
        if self.editor_view and hasattr(self.editor_view, 'set_joint_map'): # Also clear map in view
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
        can_reset = False # Default can_reset to False, enable if data exists

        if state_string == "playing":
            is_playing = True
            can_play = False
            can_stop = True
            can_reset = False # Cannot reset while playing
        elif state_string == "stopped":
            is_playing = False
            # Check if there's data to play/reset
            # This depends on whether skeleton/parts are loaded, which IKManager might know
            # For now, assume if stopped, can play if data exists.
            can_play = bool(self.current_editor_items) # Or check ProjectDataManager via MainWindow if needed
            can_stop = False
            can_reset = bool(self.current_editor_items)
        elif state_string == "reset":
            is_playing = False
            can_play = bool(self.current_editor_items)
            can_stop = False
            can_reset = False # After reset, usually cannot reset again immediately unless new state allows
                              # Let's assume reset means back to initial, can play, cannot reset further.
                              # Or, if reset clears data, then can_reset would be false.
                              # For now, if state is "reset", assume it's ready to play again if data exists.
            can_reset = bool(self.current_editor_items) # Can reset if there's something to reset
        else:
            logging.warning(f"EditorTab: Unknown simulation state string: {state_string}")
            # Default to a safe state (e.g., not playing, can play if items exist)
            is_playing = False
            can_play = bool(self.current_editor_items)
            can_stop = False
            can_reset = bool(self.current_editor_items)


        if self.play_btn:
            self.play_btn.setEnabled(can_play and not is_playing)
            self.play_btn.setChecked(is_playing) # Reflects if it's actively playing
        if self.stop_btn:
            self.stop_btn.setEnabled(can_stop and is_playing)
        if self.reset_sim_btn:
            self.reset_sim_btn.setEnabled(can_reset and not is_playing)

        # Update other UI elements if necessary
        self._update_mechanism_controls_based_on_simulation(is_playing)

        self.current_simulation_state = state_string # Update current state
        self.ik_log_counter.clear() # Reset log counter when simulation state changes

    def _update_mechanism_controls_based_on_simulation(self, is_simulating: bool):
        # Implementation of this method is not provided in the original file or the code block
        # This method should be implemented to update other UI elements based on the simulation state
        pass

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
            if skeleton_data: # This is the data to display *now*
                # skeleton_data is likely from StandardizedSkeletonModel.model_dump()
                # So, skeleton_data.get('joints') will be Dict[str, Dict] where the inner dict is the dumped joint model.
                standardized_joints_dict = skeleton_data.get('joints', {}) # Dict[std_id, Dict]
                hierarchy = skeleton_data.get('hierarchy', {})     # Dict[std_id, List[std_child_id]]

                skeleton_for_view = []
                if isinstance(standardized_joints_dict, dict):
                    for joint_id, joint_model_dict in standardized_joints_dict.items(): # Iterate through the dictionary of dictionaries
                        pos_list = joint_model_dict.get('position')
                        pos = QPointF(pos_list[0], pos_list[1]) if pos_list and len(pos_list) == 2 else QPointF()

                        skeleton_for_view.append({
                            'id': joint_model_dict.get('id', joint_id), # Use key as fallback for id
                            'name': joint_model_dict.get('name'),
                            'position': pos,
                            'parent': joint_model_dict.get('parent_id'),
                            'color': joint_model_dict.get('color', 'blue'),
                            'label': joint_model_dict.get('label')
                        })

                logging.debug(f"EditorTab: Visualizing skeleton with {len(skeleton_for_view)} joints and hierarchy keys: {list(hierarchy.keys())}")
                self.editor_view.visualize_skeleton(skeleton_for_view, hierarchy)
            else:
                logging.info("EditorTab: Clearing skeleton visualization because skeleton_data is None.")
                self.editor_view.visualize_skeleton([], {})

        self._update_button_states()

    # New method to cache initial skeleton data
    def cache_initial_skeleton(self, skeleton_data_dict: Optional[Dict]):
        """Caches the initial skeleton data dictionary provided by MainWindow."""
        if skeleton_data_dict:
            self._initial_skeleton_data_cache = skeleton_data_dict.copy() # Store a copy
            logging.info("EditorTab: Initial skeleton data has been cached.")
            # Pass the joint_map to the editor_view
            if self.editor_view and hasattr(self.editor_view, 'set_joint_map'): # Check if method exists
                joint_map = self._initial_skeleton_data_cache.get('joint_map')
                self.editor_view.set_joint_map(joint_map)
        else:
            self._initial_skeleton_data_cache = None
            logging.info("EditorTab: Initial skeleton data cache has been cleared (set to None).")
            if self.editor_view and hasattr(self.editor_view, 'set_joint_map'): # Check if method exists
                self.editor_view.set_joint_map(None) # Clear map in view as well

    # Slot for freehandPathCompleted signal from EditorView
    @pyqtSlot(list)  # Changed to match signal: list of QPointF
    def _handle_freehand_path_completed(self, path_points: List[QPointF]):
        if not self.selected_part_name:
            logging.warning("_handle_freehand_path_completed: No part selected.")
            # Do not toggle button here, mode is explicit
            return

        part_name = self.selected_part_name
        current_parts_info = self.main_window.project_data_manager.parts

        if not current_parts_info or part_name not in current_parts_info:
            logging.warning(f"_handle_freehand_path_completed: Part {part_name} not in PDM.parts.")
            return

        motion_qpath = QPainterPath()
        if path_points:
            motion_qpath.moveTo(path_points[0])
            for point in path_points[1:]:
                motion_qpath.lineTo(point)
        else:
            logging.info(f"Received empty path points for {part_name}. Clearing existing path.")

        current_parts_info[part_name].motion_path = motion_qpath
        logging.debug(f"EditorTab: Updated motion_path in PDM.parts for '{part_name}'.")

        if part_name in self.current_editor_items:
            char_part_item = self.current_editor_items[part_name]
            char_part_item.set_motion_path(motion_qpath)
        else:
            logging.warning(f"_handle_freehand_path_completed: Item {part_name} not in editor_items.")

        self.motion_path_updated.emit(part_name, motion_qpath)

        self.main_window.statusBar().showMessage(f"Motion path updated for {part_name}. Draw again or toggle mode off.")
        # DO NOT toggle button here: self.define_motion_path_btn.setChecked(False)
        self._update_button_states() # Update clear button state, etc.
        logging.info(f"Freehand motion path completed for {part_name} with {len(path_points)} points.")

    # Slot for drawing_cancelled signal from EditorView
    def _handle_drawing_cancelled(self):
        self.main_window.statusBar().showMessage("Path definition cancelled.")
        # Add any other cleanup if a specific point selection was cancelled
        self._update_generate_mechanism_button_state()
        logging.info("Drawing action cancelled by EditorView.")

    # Slots for mechanism point selections from EditorView
    def _handle_cam_center_set(self, point: QPointF):
        self.selected_cam_center = point
        if self.cam_center_marker:
            self.editor_scene.removeItem(self.cam_center_marker)
        self.cam_center_marker = self.editor_scene.addEllipse(
            point.x() - 4, point.y() - 4, 8, 8,
            QPen(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta),
            QBrush(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta)
        )
        self.cam_center_marker.setZValue(1000) # Ensure it's on top
        logging.info(f"EditorTab: Cam center set at: {point}")
        self._update_generate_mechanism_button_state()

    def _handle_pivot_a_set(self, point: QPointF):
        self.selected_pivot_a = point
        if self.pivot_a_marker:
            self.editor_scene.removeItem(self.pivot_a_marker)
        self.pivot_a_marker = self.editor_scene.addEllipse(
            point.x() - 4, point.y() - 4, 8, 8,
            QPen(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta),
            QBrush(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta)
        )
        self.pivot_a_marker.setZValue(1000)
        logging.info(f"EditorTab: Pivot A set at: {point}")
        self._update_generate_mechanism_button_state()

    def _handle_pivot_d_set(self, point: QPointF):
        self.selected_pivot_d = point
        if self.pivot_d_marker:
            self.editor_scene.removeItem(self.pivot_d_marker)
        self.pivot_d_marker = self.editor_scene.addEllipse(
            point.x() - 4, point.y() - 4, 8, 8,
            QPen(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta),
            QBrush(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta)
        )
        self.pivot_d_marker.setZValue(1000)
        logging.info(f"EditorTab: Pivot D set at: {point}")
        self._update_generate_mechanism_button_state()

    def _handle_driver_center_set(self, point: QPointF):
        self.selected_driver_center = point
        if self.driver_center_marker:
            self.editor_scene.removeItem(self.driver_center_marker)
        self.driver_center_marker = self.editor_scene.addEllipse(
            point.x() - 4, point.y() - 4, 8, 8,
            QPen(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta),
            QBrush(self.main_window.UIColors.DEBUG_HELPER_COLOR if hasattr(self.main_window, 'UIColors') else Qt.GlobalColor.magenta)
        )
        self.driver_center_marker.setZValue(1000)
        logging.info(f"EditorTab: Driver Gear center set at: {point}")
        self._update_generate_mechanism_button_state()

    def _handle_driven_center_set(self, point: QPointF):
        self.selected_driven_center = point
        self.editor_view.draw_selection_marker(point, 'driven_center') # Instruct view to draw
        self._update_generate_mechanism_button_state()

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
        """Shows or hides the part properties panel."""
        if self.part_properties_group:
            self.part_properties_group.setVisible(visible)
            logging.debug(f"Part properties panel visibility set to: {visible}")

    @pyqtSlot(list)
    def handle_mechanism_visuals(self, items: List[QGraphicsItem]):
        """Receives generated mechanism visual items and adds them to the scene."""
        logging.info(f"EditorTab: Received {len(items)} mechanism visual items.")

        # Clear previous mechanism visuals if any
        for old_item in self.mechanism_visual_items:
            if old_item.scene() == self.editor_scene:
                self.editor_scene.removeItem(old_item)
        self.mechanism_visual_items.clear()

        for item in items:
            if isinstance(item, QGraphicsItem):
                self.editor_scene.addItem(item)
                self.mechanism_visual_items.append(item)
                logging.debug(f"  Added item {type(item)} to editor scene.")
            else:
                logging.warning(f"  Skipping non-QGraphicsItem: {type(item)}")

        # Optionally, update the view or fit to new items if desired
        # self.editor_view.zoom_to_fit() # Example
        self.main_window.statusBar().showMessage(f"{len(self.mechanism_visual_items)} mechanism components generated.", 3000)

    @pyqtSlot(dict)
    def handle_joint_defined(self, joint_data: dict):
        """Handles the joint_defined signal from EditorView.
           Stores the joint data and potentially updates UI or triggers further processing.
        """
        logging.info(f"EditorTab: Received joint_defined signal: {joint_data}")
        # Expected joint_data: { 'parent_item_name': str, 'child_item_name': str, 'parent_pos': QPointF, 'child_pos': QPointF, 'parent_item': CharacterPartItem, 'child_item': CharacterPartItem }

        # Basic storage for now. In future, might create actual Joint objects or send to a manager.
        self.joints.append(joint_data)

        # TODO: Add visual representation of the joint in the scene if needed.
        # For example, draw a line or a specific marker between parent_pos and child_pos.
        # Ensure any visual items are added to self.editor_scene and potentially tracked.

        self.main_window.statusBar().showMessage(
            f"Joint defined between {joint_data.get('parent_item_name', 'N/A')} and {joint_data.get('child_item_name', 'N/A')}",
            3000
        )
        # Potentially update button states or other UI elements based on new joint
        self._update_button_states()

    def clear_all_visual_motion_paths(self):
        """Clears all visual motion path items from the scene and from CharacterPartItems."""
        if not self.current_editor_items:
            logging.info("EditorTab: No editor items to clear motion paths from.")
            return

        cleared_count = 0
        for item_name, item_widget in self.current_editor_items.items():
            path_cleared_on_item = False
            if hasattr(item_widget, 'motion_path_item') and item_widget.motion_path_item:
                if item_widget.motion_path_item.scene() == self.editor_scene:
                    self.editor_scene.removeItem(item_widget.motion_path_item)
                item_widget.motion_path_item = None
                path_cleared_on_item = True

            if hasattr(item_widget, 'motion_path_points') and item_widget.motion_path_points:
                item_widget.motion_path_points = []
                path_cleared_on_item = True

            if path_cleared_on_item:
                cleared_count += 1
                # Ensure the item repaints if its path was removed
                item_widget.update()

        if cleared_count > 0:
            logging.info(f"EditorTab: Cleared visual motion paths for {cleared_count} items.")
            self.editor_view.update() # Update the entire view to ensure all changes are reflected
        else:
            logging.info("EditorTab: No visual motion paths found to clear.")

    def handle_ik_update(self, ik_results: Dict[str, Dict[str, Any]]):
        """Receives IK results and updates the EditorView."""
        logging.debug(f"[IK_ENTRY_TRACE] EditorTab.handle_ik_update entered. Current state: {self.current_simulation_state}. IK Results count: {len(ik_results)}") # New entry log
        if not self.editor_view:
            logging.warning("EditorTab: EditorView not available to handle IK update.")
            return

        # logging.debug(f"EditorTab: Received IK update: {ik_results}")
        if not ik_results:
            # logging.debug("EditorTab: IK results are empty, nothing to update in view.")
            return

        # Corrected: ik_results is the joint_centric_data
        if ik_results:
            self.editor_view.update_visuals_from_animation_data(ik_results)
        else:
            logging.info("EditorTab.handle_ik_update: No valid joint-centric data generated from ik_results to update visuals.")

        self.editor_view.scene().update() # update_visuals_from_animation_data should handle scene update

    # New handlers for signals from EditorView
    def _handle_part_item_clicked_from_view(self, clicked_item: CharacterPartItem):
        """Handles a CharacterPartItem being clicked in the EditorView."""
        part_name = clicked_item.name()
        self.selected_part_name = part_name
        logging.debug(f"EditorTab: Part '{part_name}' clicked in view. Selected.")

        # Update the QListWidget selection to match the view
        for i in range(self.parts_list.count()):
            list_item = self.parts_list.item(i)
            if list_item.data(Qt.ItemDataRole.UserRole) == part_name:
                self.parts_list.setCurrentItem(list_item, Qt.ItemSelectionModel.SelectionFlag.ClearAndSelect)
                break

        # Ensure the item is also selected in the scene (QGraphicsView might do this, but be explicit)
        # View already emits this *after* super().mousePressEvent, so selection should be set.
        # clicked_item.setSelected(True) # This might be redundant

        self.update_part_properties_panel(self.selected_part_name)
        self._update_button_states()
        self._update_gizmo_visibility()

    def _handle_part_item_double_clicked_from_view(self, double_clicked_item: CharacterPartItem):
        """Handles a CharacterPartItem being double-clicked in the EditorView."""
        part_name = double_clicked_item.name()
        logging.debug(f"EditorTab: Part '{part_name}' double-clicked in view.")
        # Add logic for double-click action, e.g., open a detailed properties dialog
        QMessageBox.information(self, "Part Double-Clicked", f"Part '{part_name}' was double-clicked.")

    def _solve_four_bar_kinematics(self, P0: QPointF, P3: QPointF, L1: float, L2: float, L3: float, input_angle_L1_rad: float) -> Optional[Tuple[QPointF, QPointF, float, float, float]]:
        """
        Solves the forward kinematics for a four-bar linkage for a given input angle of L1.
        P0 and P3 are fixed pivots. L1 is the crank, L2 the coupler, L3 the rocker.
        Lengths are assumed to be already scaled for display.

        Args:
            P0: Position of the first fixed pivot (where L1 and L4 connect).
            P3: Position of the second fixed pivot (where L3 and L4 connect).
            L1: Length of the crank.
            L2: Length of the coupler.
            L3: Length of the rocker.
            input_angle_L1_rad: Input angle of L1 (crank) in radians, relative to the positive x-axis.

        Returns:
            A tuple (P1, P2, l1_angle_rad, l2_angle_rad, l3_angle_rad) if a solution exists,
            otherwise None. Angles are global (relative to positive x-axis).
            P1 is the pivot between L1 and L2.
            P2 is the pivot between L2 and L3.
        """
        # Calculate P1 based on P0, L1, and input_angle_L1_rad
        P1 = QPointF(P0.x() + L1 * math.cos(input_angle_L1_rad),
                    P0.y() + L1 * math.sin(input_angle_L1_rad))

        # Now, find P2. P2 is at the intersection of two circles:
        # Circle 1: center P1, radius L2
        # Circle 2: center P3, radius L3
        d_sq = (P3.x() - P1.x())**2 + (P3.y() - P1.y())**2
        d = math.sqrt(d_sq)

        # Check if solution is possible
        if d > L2 + L3 or d < abs(L2 - L3):
            logging.warning(f"4-Bar Kinematics: No solution. d={d}, L2+L3={L2+L3}, |L2-L3|={abs(L2-L3)}")
            return None
        if d == 0 and L2 != L3 : # P1 and P3 coincide, but L2 != L3
             logging.warning(f"4-Bar Kinematics: No solution. P1 and P3 coincide, L2!=L3")
             return None
        if d == 0 and L2 == L3: # P1, P3 coincide, L2=L3. Infinite solutions for P2. Ambiguous.
            # This case could be handled by choosing P2 to make L2 continue in L1's direction or other rule.
            # For now, let's treat it as ambiguous / non-deterministic for a single pose.
            logging.warning(f"4-Bar Kinematics: Ambiguous. P1,P3 coincide and L2=L3.")
            # For a default pose, let P2 be along the line of L1.
            # Angle of L2 = input_angle_L1_rad
            # P2 = QPointF(P1.x() + L2 * math.cos(input_angle_L1_rad), P1.y() + L2 * math.sin(input_angle_L1_rad))
            # But this might not satisfy the L3 constraint unless L3 is also 0.
            return None # Or a more sophisticated handling

        # Using law of cosines to find angles in triangle P1-P2-P3
        # Angle at P1 in triangle P1P3P2 (angle between P1P3 and P1P2)
        val_for_acos_gamma1 = (d_sq + L2**2 - L3**2) / (2 * d * L2)
        if not (-1 <= val_for_acos_gamma1 <= 1): # Check due to potential floating point issues
            logging.warning(f"4-Bar Kinematics: val_for_acos_gamma1 out of range: {val_for_acos_gamma1}. d={d}, L2={L2}, L3={L3}")
            return None
        gamma1 = math.acos(val_for_acos_gamma1)

        # Angle of line P1P3 relative to positive x-axis
        phi_P1P3 = math.atan2(P3.y() - P1.y(), P3.x() - P1.x())

        # Angle of L2 (P1P2) - two solutions for P2: (phi_P1P3 - gamma1) or (phi_P1P3 + gamma1)
        # We need a consistent way to choose. Let's choose one configuration.
        # The "elbow" direction depends on this choice.
        # For now, using (phi_P1P3 - gamma1) for l2_angle_rad. This is one of two configurations.
        # A common convention is to choose the one that results in a "crossed" or "open" configuration
        # based on the problem or an additional parameter. Let's pick one for now.
        l2_angle_rad = phi_P1P3 - gamma1 # First solution for L2 angle

        P2 = QPointF(P1.x() + L2 * math.cos(l2_angle_rad),
                    P1.y() + L2 * math.sin(l2_angle_rad))

        # Calculate angle of L3 (P3P2)
        l3_angle_rad = math.atan2(P2.y() - P3.y(), P2.x() - P3.x())

        # Actual angle of L1 is input_angle_L1_rad
        l1_angle_rad = input_angle_L1_rad

        return P1, P2, l1_angle_rad, l2_angle_rad, l3_angle_rad

    def _load_and_display_mechanism(self, mechanism_data: Dict[str, Any], user_path_center: QPointF):
        # Stop any ongoing simulation before clearing
        if self.is_mechanism_simulating:
            self.is_mechanism_simulating = False
            self.mechanism_simulation_timer.stop()
            logging.info("Stopped ongoing mechanism simulation before loading new one.")

        # Clear previous mechanism visuals
        for item in self.mechanism_visual_items:
            if item.scene() == self.editor_scene:
                self.editor_scene.removeItem(item)
        self.mechanism_visual_items.clear()

        mech_type = mechanism_data.get("type")
        params = mechanism_data.get("parameters")

        if not params:
            logging.warning("No parameters found in mechanism data.")
            return

        # --- Constants for Drawing ---
        SCALING_FACTOR = 50.0  # Pixels per unit length from JSON
        LINK_COLOR = Qt.GlobalColor.darkCyan
        LINK_THICKNESS = 10
        PIVOT_COLOR = Qt.GlobalColor.red
        PIVOT_RADIUS = 6
        GROUND_LINK_COLOR = Qt.GlobalColor.gray

        if mech_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR: # Matches constant from recommendation_dialog
            L1 = params.get("L1", 0.0) * SCALING_FACTOR
            L2 = params.get("L2", 0.0) * SCALING_FACTOR
            L3 = params.get("L3", 0.0) * SCALING_FACTOR
            L4_ground = params.get("L4_ground", 0.0) * SCALING_FACTOR

            if not all([L1 > 0, L2 > 0, L3 > 0, L4_ground > 0]):
                logging.error("Invalid link lengths for 4-bar linkage.")
                return

            # Placement: Place P0 (start of ground link) offset from user_path_center
            # P0 = QPointF(user_path_center.x() - L4_ground / 2, user_path_center.y() + max(L1,L2,L3) / 2) # Heuristic
            P0 = QPointF(user_path_center.x() - L4_ground / 2, user_path_center.y() + L1) # Simpler offset for now
            P3 = QPointF(P0.x() + L4_ground, P0.y()) # Horizontal ground link

            # Initial input angle for L1 (e.g., 30 degrees)
            initial_crank_angle_deg = 30.0
            initial_crank_angle_rad = math.radians(initial_crank_angle_deg)
            self.current_mechanism_crank_angle_rad = initial_crank_angle_rad # Store for simulation start
            self._initial_mechanism_crank_angle_rad = initial_crank_angle_rad # Store for reset

            kinematic_solution = self._solve_four_bar_kinematics(P0, P3, L1, L2, L3, initial_crank_angle_rad)

            if kinematic_solution:
                P1, P2, _, _, _ = kinematic_solution

                # Create QGraphicsItems
                link1_item = self.editor_scene.addLine(P0.x(), P0.y(), P1.x(), P1.y(), QPen(LINK_COLOR, LINK_THICKNESS))
                link2_item = self.editor_scene.addLine(P1.x(), P1.y(), P2.x(), P2.y(), QPen(LINK_COLOR, LINK_THICKNESS))
                link3_item = self.editor_scene.addLine(P2.x(), P2.y(), P3.x(), P3.y(), QPen(LINK_COLOR, LINK_THICKNESS))
                ground_link_item = self.editor_scene.addLine(P3.x(), P3.y(), P0.x(), P0.y(), QPen(GROUND_LINK_COLOR, LINK_THICKNESS, style=Qt.PenStyle.DashLine))

                pivot0_item = self.editor_scene.addEllipse(P0.x() - PIVOT_RADIUS, P0.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2, QPen(Qt.GlobalColor.black), QBrush(PIVOT_COLOR))
                pivot1_item = self.editor_scene.addEllipse(P1.x() - PIVOT_RADIUS, P1.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2, QPen(Qt.GlobalColor.black), QBrush(PIVOT_COLOR))
                pivot2_item = self.editor_scene.addEllipse(P2.x() - PIVOT_RADIUS, P2.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2, QPen(Qt.GlobalColor.black), QBrush(PIVOT_COLOR))
                pivot3_item = self.editor_scene.addEllipse(P3.x() - PIVOT_RADIUS, P3.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2, QPen(Qt.GlobalColor.black), QBrush(PIVOT_COLOR))

                self.mechanism_visual_items.extend([link1_item, link2_item, link3_item, ground_link_item, pivot0_item, pivot1_item, pivot2_item, pivot3_item])
                logging.info(f"Displayed 4-bar linkage: P0({P0.x():.1f},{P0.y():.1f}), P1({P1.x():.1f},{P1.y():.1f}), P2({P2.x():.1f},{P2.y():.1f}), P3({P3.x():.1f},{P3.y():.1f})")
            else:
                QMessageBox.warning(self, "Mechanism Error", "Could not solve kinematics for the selected 4-bar linkage with the given parameters and initial angle.")
                logging.error("Failed to display 4-bar linkage due to kinematic solution error.")

        elif mech_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            # TODO: Implement 3-bar linkage display
            logging.info("3-Bar linkage display not yet implemented.")
            pass
        elif mech_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            # TODO: Implement Cam display
            logging.info("Cam mechanism display not yet implemented.")
            pass
        else:
            logging.warning(f"Mechanism display not implemented for type: {mech_type}")

        self.editor_scene.update()

    def _update_mechanism_simulation(self):
        """Updates the mechanism pose based on the current crank angle."""
        if not self.is_mechanism_simulating or not self.mechanism_visual_items or \
           not hasattr(self, '_loaded_mechanism_params') or not self._loaded_mechanism_params:
            return

        self.current_mechanism_crank_angle_rad += self.mechanism_simulation_angular_step
        # Normalize angle to 0-2pi
        self.current_mechanism_crank_angle_rad %= (2 * math.pi)

        # Use stored parameters for the currently loaded mechanism
        mechanism_data = self._loaded_mechanism_params.get("data")
        user_path_center = self._loaded_mechanism_params.get("user_path_center") # Needed for P0, P3 re-calculation if not stored

        if not mechanism_data or not user_path_center:
            logging.warning("Missing loaded mechanism data for simulation update.")
            self.mechanism_simulation_timer.stop()
            self.is_mechanism_simulating = False
            return

        self._update_displayed_mechanism_pose(self.current_mechanism_crank_angle_rad, mechanism_data, user_path_center)

    def _update_displayed_mechanism_pose(self, crank_angle_rad: float, mechanism_data: Dict[str, Any], user_path_center: QPointF):
        """Helper function to update the visual items of a 4-bar linkage to a new pose."""
        params = mechanism_data.get("parameters")
        mech_type = mechanism_data.get("type")

        if not params or mech_type != MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            logging.warning(f"Cannot update pose for mechanism type {mech_type} or missing params.")
            return

        SCALING_FACTOR = 50.0
        L1 = params.get("L1", 0.0) * SCALING_FACTOR
        L2 = params.get("L2", 0.0) * SCALING_FACTOR
        L3 = params.get("L3", 0.0) * SCALING_FACTOR
        L4_ground = params.get("L4_ground", 0.0) * SCALING_FACTOR

        if not all([L1 > 0, L2 > 0, L3 > 0, L4_ground > 0]):
            return # Already logged in _load_and_display

        # Re-calculate P0, P3 based on user_path_center (consistent placement)
        # This assumes P0, P3 are not part of mechanism_visual_items that are being transformed directly.
        # If P0, P3 were visual items, we'd fetch their positions instead.
        P0 = QPointF(user_path_center.x() - L4_ground / 2, user_path_center.y() + L1)
        P3 = QPointF(P0.x() + L4_ground, P0.y())

        kinematic_solution = self._solve_four_bar_kinematics(P0, P3, L1, L2, L3, crank_angle_rad)

        if kinematic_solution:
            P1_new, P2_new, _, _, _ = kinematic_solution

            # Assuming visual items are stored in a specific order:
            # [link1, link2, link3, ground_link, pivot0, pivot1, pivot2, pivot3]
            if len(self.mechanism_visual_items) >= 8:
                # Update Links
                link1_item = self.mechanism_visual_items[0]
                link2_item = self.mechanism_visual_items[1]
                link3_item = self.mechanism_visual_items[2]
                # ground_link_item = self.mechanism_visual_items[3] # Stays static

                if isinstance(link1_item, QGraphicsLineItem): link1_item.setLine(P0.x(), P0.y(), P1_new.x(), P1_new.y())
                if isinstance(link2_item, QGraphicsLineItem): link2_item.setLine(P1_new.x(), P1_new.y(), P2_new.x(), P2_new.y())
                if isinstance(link3_item, QGraphicsLineItem): link3_item.setLine(P2_new.x(), P2_new.y(), P3.x(), P3.y())

                # Update Pivots (P0 and P3 are fixed, P1 and P2 move)
                pivot1_item = self.mechanism_visual_items[5]
                pivot2_item = self.mechanism_visual_items[6]
                PIVOT_RADIUS = 6 # Must match definition in _load_and_display

                if isinstance(pivot1_item, QGraphicsEllipseItem): pivot1_item.setRect(P1_new.x() - PIVOT_RADIUS, P1_new.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2)
                if isinstance(pivot2_item, QGraphicsEllipseItem): pivot2_item.setRect(P2_new.x() - PIVOT_RADIUS, P2_new.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2)

                # Ensure P0 and P3 pivots are correctly positioned if they were created (they are static though)
                # pivot0_item = self.mechanism_visual_items[4]
                # pivot3_item = self.mechanism_visual_items[7]
                # if isinstance(pivot0_item, QGraphicsEllipseItem): pivot0_item.setRect(P0.x() - PIVOT_RADIUS, P0.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2)
                # if isinstance(pivot3_item, QGraphicsEllipseItem): pivot3_item.setRect(P3.x() - PIVOT_RADIUS, P3.y() - PIVOT_RADIUS, PIVOT_RADIUS*2, PIVOT_RADIUS*2)
            else:
                logging.warning("Mechanism visual items not found or in unexpected quantity for simulation update.")
        else:
            logging.warning(f"No kinematic solution for crank angle {math.degrees(crank_angle_rad):.1f} deg. Stopping simulation.")
            self.mechanism_simulation_timer.stop()
            self.is_mechanism_simulating = False
            # Optionally inform user or revert to last good pose

        self.editor_scene.update() # Update scene after item changes

    def _update_generate_mechanism_button_state(self):
        """Updates the enabled state of the 'Generate Mechanism' button."""
        if not self.generate_mechanism_btn:
            return

        has_selection = self.selected_part_name is not None
        is_sim_playing = self.stop_btn.isEnabled() if self.stop_btn else False
        has_motion_path = self._get_selected_part_has_motion_path()

        # Enable conditions:
        # 1. A part is selected.
        # 2. Simulation is NOT playing.
        # 3. The selected part has a defined motion path.
        can_generate = has_selection and not is_sim_playing and has_motion_path
        self.generate_mechanism_btn.setEnabled(can_generate)
        # logging.debug(f"Generate mechanism button state: {can_generate} (sel:{has_selection}, sim_play:{is_sim_playing}, path:{has_motion_path})")
