import logging
from typing import Optional, Dict, List, Any, Tuple
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
    QListWidgetItem,
    QMessageBox,
    QGraphicsLineItem,
    QGraphicsEllipseItem,
    QDialog,
    QGraphicsPathItem,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QPen, QBrush, QPainterPath, QColor

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsItem
from ..graphics_items.part_item import CharacterPartItem
from automataii.core.models import PartInfo

from ..dialogs.recommendation_dialog import (
    MechanismRecommendationDialog,
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
)
from .utils import get_project_root


class MechanismGenerationTab(QWidget):
    # Signals this tab might emit
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
    request_generate_blueprint = pyqtSignal()
    request_play_simulation = pyqtSignal()
    request_stop_simulation = pyqtSignal()
    request_reset_simulation = pyqtSignal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)

        # Scene and view for mechanism visualization
        self.mechanism_scene = QGraphicsScene(self)
        self.mechanism_view = EditorView(self.mechanism_scene, self)

        # State variables
        self.selected_part_name: Optional[str] = None
        self.selected_cam_center: Optional[QPointF] = None
        self.selected_pivot_a: Optional[QPointF] = None
        self.selected_pivot_d: Optional[QPointF] = None
        self.mechanism_selecting_mode: Optional[str] = None
        
        # Visual markers
        self.cam_center_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_a_marker: Optional[QGraphicsEllipseItem] = None
        self.pivot_d_marker: Optional[QGraphicsEllipseItem] = None
        
        # Mechanism visual items
        self.mechanism_visual_items: List[QGraphicsItem] = []
        self.current_mechanisms: List[Dict] = []
        
        # Character and path data (to be received from Path Drawing tab)
        self.character_parts: Dict[str, CharacterPartItem] = {}
        self.motion_paths: Dict[str, QPainterPath] = {}
        
        # Track simulation state
        self.is_mechanism_simulating = False
        self.current_simulation_state = "stopped"

        # UI elements
        self.parts_list: Optional[QListWidget] = None
        self.mechanism_type_combo: Optional[QComboBox] = None
        self.cam_inputs_group: Optional[QGroupBox] = None
        self.three_bar_inputs_group: Optional[QGroupBox] = None
        self.four_bar_inputs_group: Optional[QGroupBox] = None
        self.gear_inputs_group: Optional[QGroupBox] = None
        self.generate_mechanism_btn: Optional[QPushButton] = None
        self.mechanisms_list: Optional[QListWidget] = None
        self.show_mechanism_btn: Optional[QPushButton] = None
        self.hide_mechanism_btn: Optional[QPushButton] = None
        self.delete_mechanism_btn: Optional[QPushButton] = None
        self.blueprint_btn: Optional[QPushButton] = None
        self.play_btn: Optional[QPushButton] = None
        self.stop_btn: Optional[QPushButton] = None
        self.reset_sim_btn: Optional[QPushButton] = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left Control Panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedWidth(320)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(10)

        # Part Selection Group
        part_group = QGroupBox("Part Selection")
        part_layout = QVBoxLayout(part_group)
        self.parts_list = QListWidget()
        self.parts_list.setToolTip("Select a part to generate a mechanism for its motion")
        part_layout.addWidget(self.parts_list)
        panel_layout.addWidget(part_group)

        # Mechanism Generation Group
        mech_group = QGroupBox("Mechanism Generation")
        mech_layout = QVBoxLayout(mech_group)

        # Mechanism Type Selection
        mech_type_layout = QFormLayout()
        self.mechanism_type_combo = QComboBox()
        self.mechanism_type_combo.addItems([
            MECHANISM_TYPE_USER_DISPLAY_CAM,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MECHANISM_TYPE_USER_DISPLAY_4_BAR,
        ])
        self.mechanism_type_combo.setToolTip("Select the type of mechanism to generate")
        mech_type_layout.addRow("Type:", self.mechanism_type_combo)
        mech_layout.addLayout(mech_type_layout)

        # Stacked inputs for different mechanism types
        self.mech_inputs_layout = QVBoxLayout()

        # Cam Inputs
        self.cam_inputs_group = QGroupBox("Cam Settings")
        cam_inputs_layout = QVBoxLayout(self.cam_inputs_group)
        self.select_cam_center_btn = QPushButton("Select Cam Center")
        self.select_cam_center_btn.setToolTip(
            "Click on the view to set the cam rotation center"
        )
        cam_inputs_layout.addWidget(self.select_cam_center_btn)
        self.mech_inputs_layout.addWidget(self.cam_inputs_group)

        # 3-Bar Linkage Inputs
        self.three_bar_inputs_group = QGroupBox("3-Bar Linkage Settings")
        three_bar_layout = QVBoxLayout(self.three_bar_inputs_group)
        self.select_pivot_a_3bar_btn = QPushButton("Select Fixed Pivot A")
        self.select_pivot_a_3bar_btn.setToolTip(
            "Click on the view to set the fixed pivot point"
        )
        three_bar_layout.addWidget(self.select_pivot_a_3bar_btn)
        self.mech_inputs_layout.addWidget(self.three_bar_inputs_group)

        # 4-Bar Linkage Inputs
        self.four_bar_inputs_group = QGroupBox("4-Bar Linkage Settings")
        four_bar_layout = QVBoxLayout(self.four_bar_inputs_group)
        self.select_pivot_a_4bar_btn = QPushButton("Select Fixed Pivot A")
        self.select_pivot_a_4bar_btn.setToolTip(
            "Click on the view to set the first fixed pivot"
        )
        four_bar_layout.addWidget(self.select_pivot_a_4bar_btn)
        self.select_pivot_d_4bar_btn = QPushButton("Select Fixed Pivot D")
        self.select_pivot_d_4bar_btn.setToolTip(
            "Click on the view to set the second fixed pivot"
        )
        four_bar_layout.addWidget(self.select_pivot_d_4bar_btn)
        self.mech_inputs_layout.addWidget(self.four_bar_inputs_group)

        # Gear Inputs
        self.gear_inputs_group = QGroupBox("Gear Settings")
        gear_inputs_layout = QFormLayout(self.gear_inputs_group)
        gear_button_layout = QHBoxLayout()
        self.select_driver_center_btn = QPushButton("Driver Center")
        self.select_driver_center_btn.setToolTip("Click to set driver gear center")
        self.select_driven_center_btn = QPushButton("Driven Center")
        self.select_driven_center_btn.setToolTip("Click to set driven gear center")
        gear_button_layout.addWidget(self.select_driver_center_btn)
        gear_button_layout.addWidget(self.select_driven_center_btn)
        gear_inputs_layout.addRow("Select Centers:", gear_button_layout)
        self.gear_ratio_spin = QDoubleSpinBox()
        self.gear_ratio_spin.setRange(0.01, 100.0)
        self.gear_ratio_spin.setSingleStep(0.1)
        self.gear_ratio_spin.setValue(1.0)
        self.gear_ratio_spin.setToolTip(
            "Set gear ratio (Driven Radius / Driver Radius)"
        )
        gear_inputs_layout.addRow("Gear Ratio:", self.gear_ratio_spin)
        self.mech_inputs_layout.addWidget(self.gear_inputs_group)

        mech_layout.addLayout(self.mech_inputs_layout)

        # Generate button
        self.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.generate_mechanism_btn.setToolTip(
            "Generate mechanism for the selected part's motion"
        )
        mech_layout.addWidget(self.generate_mechanism_btn)

        # Recommend Mechanism button
        self.recommend_mechanism_btn = QPushButton("🤖 Recommend Mechanism")
        self.recommend_mechanism_btn.setToolTip(
            "Get AI recommendation for the best mechanism type"
        )
        self.recommend_mechanism_btn.setEnabled(False)
        mech_layout.addWidget(self.recommend_mechanism_btn)

        panel_layout.addWidget(mech_group)

        # Simulation Controls Group
        sim_group = QGroupBox("Simulation Controls")
        sim_layout = QHBoxLayout(sim_group)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Play mechanism simulation")
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setToolTip("Stop mechanism simulation")
        self.reset_sim_btn = QPushButton("↺ Reset")
        self.reset_sim_btn.setToolTip("Reset mechanism to initial state")
        
        sim_layout.addWidget(self.play_btn)
        sim_layout.addWidget(self.stop_btn)
        sim_layout.addWidget(self.reset_sim_btn)
        panel_layout.addWidget(sim_group)

        # Generated Mechanisms List
        layer_group = QGroupBox("Generated Mechanisms")
        self.layer_layout = QVBoxLayout(layer_group)
        self.mechanisms_list = QListWidget()
        self.mechanisms_list.setToolTip("List of generated mechanisms")
        self.layer_layout.addWidget(self.mechanisms_list)

        # Buttons for mechanism management
        mech_buttons_layout = QHBoxLayout()
        self.show_mechanism_btn = QPushButton("Show")
        self.hide_mechanism_btn = QPushButton("Hide")
        self.delete_mechanism_btn = QPushButton("Delete")
        self.show_mechanism_btn.setEnabled(False)
        self.hide_mechanism_btn.setEnabled(False)
        self.delete_mechanism_btn.setEnabled(False)

        mech_buttons_layout.addWidget(self.show_mechanism_btn)
        mech_buttons_layout.addWidget(self.hide_mechanism_btn)
        mech_buttons_layout.addWidget(self.delete_mechanism_btn)
        self.layer_layout.addLayout(mech_buttons_layout)

        panel_layout.addWidget(layer_group)

        # Export Group
        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout(export_group)
        self.blueprint_btn = QPushButton("Generate Blueprint (SVG)")
        self.blueprint_btn.setToolTip(
            "Generate an SVG blueprint of all parts for fabrication"
        )
        export_layout.addWidget(self.blueprint_btn)
        panel_layout.addWidget(export_group)

        panel_layout.addStretch()
        scroll_area.setWidget(control_panel)

        # Right View Area
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)

        # Add zoom toolbar (similar to editor_tab)
        zoom_toolbar = QWidget()
        zoom_layout = QHBoxLayout(zoom_toolbar)
        zoom_layout.setContentsMargins(10, 8, 10, 8)
        zoom_layout.setSpacing(8)
        zoom_layout.addStretch()

        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setFixedSize(70, 28)
        self.zoom_combo.setStyleSheet(
            """
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
        """
        )
        zoom_levels = ["50%", "75%", "90%", "100%", "125%", "150%", "200%"]
        self.zoom_combo.addItems(zoom_levels)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom level for mechanism view")

        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setFixedSize(45, 28)
        self.fit_btn.setStyleSheet(
            """
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
        """
        )
        self.fit_btn.setToolTip("Zoom to fit all items in mechanism view")

        zoom_layout.addWidget(self.zoom_combo)
        zoom_layout.addWidget(self.fit_btn)

        right_layout.addWidget(self.mechanism_view, 1)

        # Position zoom toolbar
        zoom_toolbar.setParent(right_panel)
        zoom_toolbar.setStyleSheet(
            """
            QWidget {
                background-color: rgba(248, 249, 250, 0.9);
                border: 1px solid rgba(208, 215, 222, 0.8);
                border-radius: 1px;
            }
        """
        )
        zoom_toolbar.show()

        def position_zoom_toolbar():
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
            position_zoom_toolbar()
        right_panel.showEvent = new_show_event

        original_resize_event = right_panel.resizeEvent
        def new_resize_event(event):
            original_resize_event(event)
            position_zoom_toolbar()
        right_panel.resizeEvent = new_resize_event

        layout.addWidget(scroll_area)
        layout.addWidget(right_panel, 1)
        self.setLayout(layout)

        # Update initial UI state
        self._update_mechanism_inputs_ui()
        self._update_button_states()

    def _connect_signals(self):
        """Connect all signals to their handlers."""
        # Part selection
        self.parts_list.currentItemChanged.connect(self._handle_part_selection_change)
        
        # Mechanism type selection
        self.mechanism_type_combo.currentTextChanged.connect(self._update_mechanism_inputs_ui)
        self.mechanism_type_combo.currentTextChanged.connect(self._update_generate_mechanism_button_state)
        
        # Mechanism point selection buttons
        self.select_cam_center_btn.clicked.connect(
            lambda: self._select_mechanism_point("cam_center")
        )
        self.select_pivot_a_3bar_btn.clicked.connect(
            lambda: self._select_mechanism_point("pivot_a_3bar")
        )
        self.select_pivot_a_4bar_btn.clicked.connect(
            lambda: self._select_mechanism_point("pivot_a_4bar")
        )
        self.select_pivot_d_4bar_btn.clicked.connect(
            lambda: self._select_mechanism_point("pivot_d_4bar")
        )
        self.select_driver_center_btn.clicked.connect(
            lambda: self._select_mechanism_point("driver_center")
        )
        self.select_driven_center_btn.clicked.connect(
            lambda: self._select_mechanism_point("driven_center")
        )
        
        # View signals for point selection
        self.mechanism_view.cam_center_selected.connect(self._handle_cam_center_set)
        self.mechanism_view.pivot_a_selected.connect(self._handle_pivot_a_set)
        self.mechanism_view.pivot_d_selected.connect(self._handle_pivot_d_set)
        
        # Mechanism generation and recommendation
        self.generate_mechanism_btn.clicked.connect(self._generate_mechanism_clicked)
        self.recommend_mechanism_btn.clicked.connect(self._recommend_mechanism_clicked)
        
        # Mechanism list management
        self.mechanisms_list.itemClicked.connect(self._on_mechanism_selected)
        self.show_mechanism_btn.clicked.connect(self._show_selected_mechanism)
        self.hide_mechanism_btn.clicked.connect(self._hide_selected_mechanism)
        self.delete_mechanism_btn.clicked.connect(self._delete_selected_mechanism)
        
        # Simulation controls
        self.play_btn.clicked.connect(self._play_simulation_clicked)
        self.stop_btn.clicked.connect(self._stop_simulation_clicked)
        self.reset_sim_btn.clicked.connect(self._reset_simulation_clicked)
        
        # Export
        self.blueprint_btn.clicked.connect(lambda: self.request_generate_blueprint.emit())
        
        # Zoom controls
        self.zoom_combo.currentTextChanged.connect(self._handle_zoom_changed)
        self.fit_btn.clicked.connect(lambda: self.mechanism_view.zoom_to_fit())

    def receive_character_and_paths(self, character_parts: Dict[str, CharacterPartItem], 
                                   motion_paths: Dict[str, QPainterPath], 
                                   skeleton_data: Optional[Dict] = None):
        """Receive character parts and motion paths from Path Drawing tab."""
        logging.info(f"MechanismGenerationTab: Received {len(character_parts)} parts and {len(motion_paths)} paths")
        
        # Clear existing data
        self.character_parts = character_parts.copy()
        self.motion_paths = motion_paths.copy()
        
        # Update parts list
        self.parts_list.clear()
        for part_name in sorted(character_parts.keys()):
            if part_name in motion_paths and not motion_paths[part_name].isEmpty():
                item = QListWidgetItem(f"{part_name} (path defined)")
                item.setData(Qt.ItemDataRole.UserRole, part_name)
                self.parts_list.addItem(item)
        
        # Add character parts to the scene
        self.mechanism_scene.clear()
        self.mechanism_visual_items.clear()
        
        for part_name, part_item in character_parts.items():
            # Create a copy of the part item for this tab
            pixmap = part_item.pixmap()
            new_part_item = CharacterPartItem(pixmap, part_name, part_item.part_info)
            new_part_item.setPos(part_item.scenePos())
            new_part_item.setRotation(part_item.rotation())
            new_part_item.setZValue(part_item.zValue())
            self.mechanism_scene.addItem(new_part_item)
        
        # Visualize skeleton if provided
        if skeleton_data:
            self._visualize_skeleton(skeleton_data)
        
        # Update UI state
        self._update_button_states()
        self.mechanism_view.zoom_to_fit()

    def _visualize_skeleton(self, skeleton_data: Dict):
        """Visualize skeleton in the mechanism view."""
        # Implementation would be similar to editor_tab's skeleton visualization
        pass

    def _update_mechanism_inputs_ui(self):
        """Show/hide input groups based on selected mechanism type."""
        mechanism_type = self.mechanism_type_combo.currentText()
        
        # Hide all input groups
        self.cam_inputs_group.hide()
        self.three_bar_inputs_group.hide()
        self.four_bar_inputs_group.hide()
        self.gear_inputs_group.hide()
        
        # Show relevant input group
        if mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            self.cam_inputs_group.show()
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            self.three_bar_inputs_group.show()
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            self.four_bar_inputs_group.show()

    def _update_button_states(self):
        """Update button enabled states based on current state."""
        has_parts = bool(self.character_parts)
        has_selected_part = self.selected_part_name is not None
        has_motion_path = (
            has_selected_part and 
            self.selected_part_name in self.motion_paths and 
            not self.motion_paths[self.selected_part_name].isEmpty()
        )
        
        # Mechanism generation controls
        self.generate_mechanism_btn.setEnabled(has_motion_path)
        self.recommend_mechanism_btn.setEnabled(has_motion_path)
        
        # Simulation controls
        has_mechanisms = bool(self.current_mechanisms)
        self.play_btn.setEnabled(has_mechanisms and not self.is_mechanism_simulating)
        self.stop_btn.setEnabled(self.is_mechanism_simulating)
        self.reset_sim_btn.setEnabled(has_mechanisms and not self.is_mechanism_simulating)
        
        # Export controls
        self.blueprint_btn.setEnabled(has_mechanisms)

    def _update_generate_mechanism_button_state(self):
        """Update generate mechanism button state based on inputs."""
        self._update_button_states()

    def _handle_part_selection_change(self, current, previous):
        """Handle part selection change in the list."""
        if current:
            part_name = current.data(Qt.ItemDataRole.UserRole)
            self.selected_part_name = part_name
            logging.info(f"MechanismGenerationTab: Selected part '{part_name}'")
            
            # Highlight selected part in view
            for item in self.mechanism_scene.items():
                if isinstance(item, CharacterPartItem):
                    item.setSelected(item.part_name == part_name)
        else:
            self.selected_part_name = None
        
        self._update_button_states()

    def _select_mechanism_point(self, point_type: str):
        """Start selecting a mechanism point in the view."""
        self.mechanism_selecting_mode = point_type
        if point_type in ["cam_center", "pivot_a_3bar", "pivot_a_4bar"]:
            self.mechanism_view.set_mode("select_pivot_a")
        elif point_type == "pivot_d_4bar":
            self.mechanism_view.set_mode("select_pivot_d")
        elif point_type == "driver_center":
            self.mechanism_view.set_mode("select_pivot_a")  # Reuse pivot selection
        elif point_type == "driven_center":
            self.mechanism_view.set_mode("select_pivot_d")  # Reuse pivot selection

    def _handle_cam_center_set(self, point: QPointF):
        """Handle cam center point selection."""
        if self.mechanism_selecting_mode == "cam_center":
            self.selected_cam_center = point
            self._add_point_marker(point, self.cam_center_marker, QColor(255, 0, 0))
            self.mechanism_view.set_mode("select")
            self.mechanism_selecting_mode = None
            logging.info(f"MechanismGenerationTab: Cam center set at {point}")

    def _handle_pivot_a_set(self, point: QPointF):
        """Handle pivot A point selection."""
        if self.mechanism_selecting_mode in ["pivot_a_3bar", "pivot_a_4bar", "driver_center"]:
            self.selected_pivot_a = point
            self._add_point_marker(point, self.pivot_a_marker, QColor(0, 255, 0))
            self.mechanism_view.set_mode("select")
            self.mechanism_selecting_mode = None
            logging.info(f"MechanismGenerationTab: Pivot A set at {point}")

    def _handle_pivot_d_set(self, point: QPointF):
        """Handle pivot D point selection."""
        if self.mechanism_selecting_mode in ["pivot_d_4bar", "driven_center"]:
            self.selected_pivot_d = point
            self._add_point_marker(point, self.pivot_d_marker, QColor(0, 0, 255))
            self.mechanism_view.set_mode("select")
            self.mechanism_selecting_mode = None
            logging.info(f"MechanismGenerationTab: Pivot D set at {point}")

    def _add_point_marker(self, point: QPointF, marker_var_name: str, color: QColor):
        """Add a visual marker for a selected point."""
        # Remove existing marker if any
        if marker_var_name == "cam_center_marker" and self.cam_center_marker:
            self.mechanism_scene.removeItem(self.cam_center_marker)
        elif marker_var_name == "pivot_a_marker" and self.pivot_a_marker:
            self.mechanism_scene.removeItem(self.pivot_a_marker)
        elif marker_var_name == "pivot_d_marker" and self.pivot_d_marker:
            self.mechanism_scene.removeItem(self.pivot_d_marker)
        
        # Create new marker
        marker = QGraphicsEllipseItem(-5, -5, 10, 10)
        marker.setPos(point)
        marker.setPen(QPen(color, 2))
        marker.setBrush(QBrush(color))
        marker.setZValue(1000)  # High z-value to be on top
        self.mechanism_scene.addItem(marker)
        
        # Store marker reference
        if marker_var_name == "cam_center_marker":
            self.cam_center_marker = marker
        elif marker_var_name == "pivot_a_marker":
            self.pivot_a_marker = marker
        elif marker_var_name == "pivot_d_marker":
            self.pivot_d_marker = marker

    def _generate_mechanism_clicked(self):
        """Handle generate mechanism button click."""
        if not self.selected_part_name or self.selected_part_name not in self.motion_paths:
            return
        
        mechanism_type = self.mechanism_type_combo.currentText()
        motion_path = self.motion_paths[self.selected_part_name]
        
        # Prepare parameters based on mechanism type
        params = {
            "part_name": self.selected_part_name,
            "motion_path": motion_path,
        }
        
        if mechanism_type == MECHANISM_TYPE_USER_DISPLAY_CAM:
            if not self.selected_cam_center:
                QMessageBox.warning(self, "Missing Input", "Please select the cam center point.")
                return
            params["cam_center"] = self.selected_cam_center
            
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_3_BAR:
            if not self.selected_pivot_a:
                QMessageBox.warning(self, "Missing Input", "Please select the fixed pivot point.")
                return
            params["pivot_a"] = self.selected_pivot_a
            
        elif mechanism_type == MECHANISM_TYPE_USER_DISPLAY_4_BAR:
            if not self.selected_pivot_a or not self.selected_pivot_d:
                QMessageBox.warning(self, "Missing Input", "Please select both fixed pivot points.")
                return
            params["pivot_a"] = self.selected_pivot_a
            params["pivot_d"] = self.selected_pivot_d
        
        # Emit signal to main window
        self.request_generate_mechanism.emit(mechanism_type, params)

    def _recommend_mechanism_clicked(self):
        """Handle recommend mechanism button click."""
        if not self.selected_part_name or self.selected_part_name not in self.motion_paths:
            return
        
        motion_path = self.motion_paths[self.selected_part_name]
        
        # Show recommendation dialog
        dialog = MechanismRecommendationDialog(motion_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            recommended_type = dialog.get_selected_mechanism()
            if recommended_type:
                # Set the mechanism type combo to the recommended type
                index = self.mechanism_type_combo.findText(recommended_type)
                if index >= 0:
                    self.mechanism_type_combo.setCurrentIndex(index)

    def _on_mechanism_selected(self, item):
        """Handle mechanism selection in the list."""
        if item:
            self.show_mechanism_btn.setEnabled(True)
            self.hide_mechanism_btn.setEnabled(True)
            self.delete_mechanism_btn.setEnabled(True)
        else:
            self.show_mechanism_btn.setEnabled(False)
            self.hide_mechanism_btn.setEnabled(False)
            self.delete_mechanism_btn.setEnabled(False)

    def _show_selected_mechanism(self):
        """Show the selected mechanism."""
        # Implementation would show mechanism visual items
        pass

    def _hide_selected_mechanism(self):
        """Hide the selected mechanism."""
        # Implementation would hide mechanism visual items
        pass

    def _delete_selected_mechanism(self):
        """Delete the selected mechanism."""
        # Implementation would remove mechanism from list and scene
        pass

    def _play_simulation_clicked(self):
        """Handle play simulation button click."""
        self.is_mechanism_simulating = True
        self.request_play_simulation.emit()
        self._update_button_states()

    def _stop_simulation_clicked(self):
        """Handle stop simulation button click."""
        self.is_mechanism_simulating = False
        self.request_stop_simulation.emit()
        self._update_button_states()

    def _reset_simulation_clicked(self):
        """Handle reset simulation button click."""
        self.is_mechanism_simulating = False
        self.request_reset_simulation.emit()
        self._update_button_states()

    def _handle_zoom_changed(self, zoom_text: str):
        """Handle zoom combo box value change."""
        if not zoom_text:
            return
        
        # Remove % sign and convert to float
        try:
            zoom_value = float(zoom_text.strip('%'))
            self.mechanism_view.set_zoom(zoom_value / 100.0)
        except ValueError:
            pass

    def on_mechanism_generated(self, mechanism_data: Dict):
        """Handle mechanism generation completion."""
        # Add mechanism to list
        mechanism_type = mechanism_data.get("type", "Unknown")
        part_name = mechanism_data.get("part_name", "Unknown")
        item_text = f"{mechanism_type} - {part_name}"
        
        list_item = QListWidgetItem(item_text)
        list_item.setData(Qt.ItemDataRole.UserRole, mechanism_data)
        self.mechanisms_list.addItem(list_item)
        
        # Store mechanism data
        self.current_mechanisms.append(mechanism_data)
        
        # Visualize mechanism
        self._visualize_mechanism(mechanism_data)
        
        # Update UI state
        self._update_button_states()

    def _visualize_mechanism(self, mechanism_data: Dict):
        """Visualize a generated mechanism."""
        # Implementation would create visual items for the mechanism
        # This would be moved from editor_tab's mechanism visualization code
        pass

    def on_simulation_state_changed(self, state_string: str):
        """Handle simulation state changes."""
        self.current_simulation_state = state_string
        
        if state_string == "playing":
            self.is_mechanism_simulating = True
        else:
            self.is_mechanism_simulating = False
        
        self._update_button_states()

    def clear_all(self):
        """Clear all data and reset the tab."""
        self.character_parts.clear()
        self.motion_paths.clear()
        self.current_mechanisms.clear()
        self.mechanism_visual_items.clear()
        
        self.parts_list.clear()
        self.mechanisms_list.clear()
        self.mechanism_scene.clear()
        
        self.selected_part_name = None
        self.selected_cam_center = None
        self.selected_pivot_a = None
        self.selected_pivot_d = None
        
        self._update_button_states()