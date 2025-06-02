import logging
from typing import Optional, Dict, List, Any
from pathlib import Path

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
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QGraphicsItem # Added for type hinting
from PyQt6.QtGui import QPixmap # Added QPixmap

# Import EditorScene and EditorView
from ..editor_view import EditorView # Assuming editor_view.py is in the same parent directory (gui)
from PyQt6.QtWidgets import QGraphicsScene
from ..graphics_items.part_item import CharacterPartItem # UPDATED
from automataii.core.models import PartInfo # Added PartInfo

from PyQt6.QtGui import QPainterPath
from ..dialogs.recommendation_dialog import MechanismRecommendationDialog # ADDED
from .utils import get_project_root # Assuming a utility to get project root

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
        self._update_gizmo_visibility()

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

    def _stop_simulation_clicked(self):
        self.request_stop_simulation.emit()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(True)

    def _reset_simulation_clicked(self):
        self.request_reset_simulation.emit()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_sim_btn.setEnabled(
            False
        )  # Should be true after reset if parts exist
        self._update_button_states()  # Re-evaluate button states after reset

    def _reset_all_animations_paths_poses(self):
        # This will call a method on MainWindow
        logging.info("EditorTab: Requesting reset of all animation paths and poses.")
        self.request_reset_all_animations.emit()
        self._update_button_states()

    def _toggle_test_anchors_visibility_in_view(self, checked: bool):
        if hasattr(self.main_window, "_toggle_test_anchors_visibility"):
            if checked:
                self.editor_view.show_test_anchors()
            else:
                self.editor_view.hide_test_anchors()

    def _update_mechanism_inputs_ui(self, mechanism_type: str):
        self.cam_inputs_group.setVisible(mechanism_type == "Cam & Follower")
        self.three_bar_inputs_group.setVisible(mechanism_type == "3-Bar Linkage")
        self.four_bar_inputs_group.setVisible(mechanism_type == "4-Bar Linkage")
        self.gear_inputs_group.setVisible(mechanism_type == "Gears (Simple Pair)")
        self._update_generate_mechanism_button_state()

    def _update_generate_mechanism_button_state(self):
        # Simple check, can be made more robust based on selected points for each mechanism
        can_generate = (
            self.selected_part_name is not None
            and self._get_selected_part_has_motion_path()
        )

        # Add specific checks for each mechanism type if needed
        # e.g., for cam, ensure cam center is selected if it's a requirement not based on motion path target
        self.generate_mechanism_btn.setEnabled(can_generate)

    def _select_mechanism_point(self, point_type: str):
        # This method will instruct main_window.editor_view to enter a point selection mode
        # Point_type could be 'cam_center', 'pivot_a_3bar', 'pivot_a_4bar', 'pivot_d_4bar', 'driver_center', 'driven_center'
        self.editor_view.start_mechanism_point_selection(point_type)
        self.main_window.statusBar().showMessage(
            f"Click in the scene to define {point_type.replace('_', ' ')}."
        )

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
            QMessageBox.information(self, "Mechanism Selected",
                                    f"Selected: {selected_mechanism.get('name')}\\nType: {selected_mechanism.get('type')}\\nScore (Hausdorff): {selected_mechanism.get('overall_score'):.4f}")

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
        has_parts = self.parts_list.count() > 0
        has_selection = self.selected_part_name is not None
        is_sim_playing = self.stop_btn.isEnabled()  # If stop is enabled, sim is playing

        self.define_motion_path_btn.setEnabled(has_selection and not is_sim_playing)
        self.clear_motion_path_btn.setEnabled(
            has_selection
            and not is_sim_playing
            and self._get_selected_part_has_motion_path()
        )

        self.play_btn.setEnabled(has_parts and not is_sim_playing)
        # stop_btn state handled by play/stop clicks
        self.reset_sim_btn.setEnabled(
            has_parts and not is_sim_playing
        )  # General sim reset
        self.generate_mechanism_btn.setEnabled(
            has_selection
            and not is_sim_playing
            and self._get_selected_part_has_motion_path()
        )
        self.blueprint_btn.setEnabled(has_parts)
        self.save_alignment_btn.setEnabled(has_parts)
        self._update_generate_mechanism_button_state()  # Re-check this specifically

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
            item = CharacterPartItem(part_info=p_info, project_dir=project_dir)

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

    def on_parts_loaded_or_cleared(self, parts_exist: bool):
        """Called by MainWindow when parts are loaded or cleared."""
        # This method is now largely superseded by set_parts_data and clear_editor_content
        # If MainWindow calls this, it should probably just forward to the new methods
        # or this connection should be removed and MainWindow should call set_parts_data/clear_editor_content directly.
        logging.debug(f"EditorTab.on_parts_loaded_or_cleared called with: {parts_exist}. Consider refactoring.")
        if parts_exist:
            # Assuming parts_data is now sourced from project_data_manager by MainWindow
            # This direct access is what we are trying to remove.
            # self.set_parts_data(self.main_window.project_data_manager.parts, self.main_window.project_data_manager.editor_items)
            pass # MainWindow should call set_parts_data directly
        else:
            self.clear_editor_content() # This is correct
        # self._update_button_states() # set_parts_data and clear_editor_content handle this

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

    def _update_mechanism_controls_based_on_simulation(self, is_simulating: bool):
        # Implementation of this method is not provided in the original file or the code block
        # This method should be implemented to update other UI elements based on the simulation state
        pass

    def on_skeleton_updated(self, skeleton_data: Optional[Dict]):
        """Called by MainWindow when the skeleton is updated."""
        logging.info(
            f"EditorTab received skeleton update: {'Exists' if skeleton_data else 'None'}"
        )

        if self.editor_view:
            if skeleton_data:
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

    def set_part_properties_visibility(self, visible: bool):
        """Slot to control visibility of the part properties group."""
        self.part_properties_group.setVisible(visible)
        logging.info(f"EditorTab: Part properties visibility set to {visible}")

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
        if not self.editor_view:
            logging.warning("EditorTab: EditorView not available to handle IK update.")
            return

        # logging.debug(f"EditorTab: Received IK update: {ik_results}")
        if not ik_results:
            # logging.debug("EditorTab: IK results are empty, nothing to update in view.")
            return

        for part_name, transform_data in ik_results.items():
            position_data = transform_data.get('position')
            rotation_degrees = transform_data.get('rotation_degrees')

            if position_data and isinstance(position_data, (list, tuple)) and len(position_data) >= 2:
                new_pos = QPointF(float(position_data[0]), float(position_data[1]))
                if rotation_degrees is not None:
                    self.editor_view.update_part_visuals_from_ik(part_name, new_pos, float(rotation_degrees))
                else:
                    logging.warning(f"EditorTab: Missing rotation for part {part_name} in IK update.")
            else:
                logging.warning(f"EditorTab: Invalid or missing position for part {part_name} in IK update.")

        self.editor_view.scene().update() # Update once after all parts are processed

    def _update_gizmo_visibility(self):
        # Implementation of this method is not provided in the original file or the code block
        # This method should be implemented to update other UI elements based on the simulation state
        pass

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

    # def _handle_part_item_moved_from_view(self, moved_item: CharacterPartItem, scene_pos: QPointF):
    #     """Handles a CharacterPartItem being moved in the EditorView."""
    #     part_name = moved_item.name()
    #     logging.debug(f"EditorTab: Part '{part_name}' moved in view to {scene_pos}.")
    #     # Update any model data if necessary, though direct manipulation might be handled by IK later
    #     # self.current_parts_info[part_name].scene_position = scene_pos # Example
    #     self.main_window.project_data_manager.update_part_position(part_name, scene_pos) # Example call
