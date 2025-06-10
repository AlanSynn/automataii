import logging
from typing import Optional, Dict, Any, List, Tuple
import math
import uuid
import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QDialog,
    QGraphicsView,
    QGraphicsItem,
    QCheckBox,
    QScrollArea,
    QStackedWidget,
    QGraphicsEllipseItem,
)
from PyQt6.QtCore import pyqtSignal, QPointF, Qt, QTimer, QRectF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem
from automataii.core.models import PartInfo
from automataii.kinematics.mechanism import (
    MechanismType,
    MechanismCandidate,
    MechanismTemplate,
    MechanismParameter,
)
from automataii.kinematics.motion_database import MotionDatabase
from automataii.kinematics.mechanism_simulator import MechanismSimulator
from ..graphics_items.part_item import CharacterPartItem

from ..dialogs.recommendation_dialog import (
    MECHANISM_TYPE_USER_DISPLAY_4_BAR,
    MECHANISM_TYPE_USER_DISPLAY_3_BAR,
    MECHANISM_TYPE_USER_DISPLAY_CAM,
    MechanismRecommendationDialog,
)


class MechanismDesignTab(QWidget):
    """Tab for mechanism design matching user-drawn paths from editor tab.

    Key features:
    - Receives motion paths from editor tab
    - Recommends mechanisms (3-bar, 4-bar, cam) that can reproduce the paths
    - Parts follow mechanism-generated paths (reverse of editor tab)
    - Interactive parametric design with drag-and-drop manipulation
    - Individual mechanism layer enable/disable
    """

    # Signals for mechanism-related operations
    request_generate_mechanism = pyqtSignal(str, dict)  # mechanism_type, params
    request_generate_blueprint = pyqtSignal()
    mechanism_selection_changed = pyqtSignal(str)  # mechanism_type
    mechanism_path_generated = pyqtSignal(str, QPainterPath)  # part_name, generated_path
    mechanism_parameters_changed = pyqtSignal(str, dict)  # mechanism_id, params

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)

        # Core components from the paper plan
        self.motion_database = MotionDatabase("motion_database.h5")
        self.mechanism_simulator = MechanismSimulator()
        self.candidates: List[MechanismCandidate] = []
        self.selected_mechanism: Optional[MechanismCandidate] = None

        # Path data from editor tab
        self.path_data: Dict[str, QPainterPath] = {}
        self.selected_part_name: Optional[str] = None
        self.parts_data: Dict[str, PartInfo] = {}  # Store parts data
        self.current_editor_items: Dict[str, CharacterPartItem] = {}

        # Mechanism generation state
        self.current_mechanism_type: Optional[str] = None
        self.mechanism_params: Dict[str, Any] = {}
        self.mechanism_layers: Dict[str, Any] = {}  # Store mechanism layers with enable/disable state
        self.path_visual_items: Dict[str, QGraphicsPathItem] = {}  # Store path visuals
        self.mechanism_paths: Dict[str, QPainterPath] = {}  # Generated mechanism paths
        self.mechanism_instances: Dict[str, Any] = {}  # Store actual mechanism objects
        self.mechanism_enabled_state: Dict[str, bool] = {}  # Track which mechanisms are enabled
        self.interactive_handles: Dict[str, List[QGraphicsItem]] = {}  # Drag handles for params

        # Graphics scene for mechanism preview
        self.mechanism_scene = QGraphicsScene(self)
        self.mechanism_view = EditorView(self.mechanism_scene, self)

        # Edit mode state
        self.edit_mode = False
        self.parametric_edit_mode = False  # For interactive parameter adjustment
        self.selected_mechanism_id: Optional[str] = None

        # Animation state
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_time = 0.0
        self.animation_speed = 1.0  # radians per second
        self.animating_mechanisms = {}  # Store original positions for animation

        # UI Elements
        self.mechanism_type_combo: Optional[QComboBox] = None
        self.generate_mechanism_btn: Optional[QPushButton] = None
        self.mechanism_preview_group: Optional[QGroupBox] = None
        self.mechanism_params_group: Optional[QGroupBox] = None
        self.parts_selection_combo: Optional[QComboBox] = None
        self.blueprint_btn: Optional[QPushButton] = None
        self.recommendation_btn: Optional[QPushButton] = None
        self.start_edit_btn: Optional[QPushButton] = None
        self.mechanism_layers_list: Optional[QListWidget] = None
        self.animate_btn: Optional[QPushButton] = None
        self.stop_animate_btn: Optional[QPushButton] = None

        # Mechanism parameters widgets (removed - will use interactive handles instead)
        self.enable_mechanisms_checkbox: Optional[QCheckBox] = None
        self.apply_params_btn: Optional[QPushButton] = None
        self.parametric_edit_btn: Optional[QPushButton] = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup UI - Similar to EditorTab but with mechanism layers instead of parts"""
        main_layout = QHBoxLayout(self)

        # Left Control Panel (similar to EditorTab)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFixedWidth(300)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        control_panel = QWidget()
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Mechanism Layers Group (similar to Parts in EditorTab)
        layers_group = QGroupBox("1 Mechanism Layers")
        layers_group.setStyleSheet("""
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
        layers_layout = QVBoxLayout(layers_group)
        self.mechanism_layers_list = QListWidget()
        self.mechanism_layers_list.setToolTip("List of generated mechanism layers")
        self.mechanism_layers_list.setMinimumHeight(180)
        self.mechanism_layers_list.setStyleSheet(
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
            QListWidget::item:disabled {
                color: #a0aab5;
                background-color: #f0f0f0;
            }
        """
        )
        layers_layout.addWidget(self.mechanism_layers_list)

        # Add checkbox for enabling/disabling mechanisms
        self.enable_mechanisms_checkbox = QCheckBox("Enable Selected Mechanism")
        self.enable_mechanisms_checkbox.setEnabled(False)
        self.enable_mechanisms_checkbox.setToolTip("Toggle to enable/disable the selected mechanism layer")
        layers_layout.addWidget(self.enable_mechanisms_checkbox)

        panel_layout.addWidget(layers_group)

        # 2. Mechanism Generation Group
        generation_group = QGroupBox("2 Mechanism Generation")
        generation_group.setStyleSheet("""
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
        generation_layout = QVBoxLayout(generation_group)

        # Target part selection
        part_selection_layout = QFormLayout()
        self.parts_selection_combo = QComboBox()
        part_selection_layout.addRow("Target Part:", self.parts_selection_combo)
        generation_layout.addLayout(part_selection_layout)

        # Mechanism type
        mechanism_type_layout = QFormLayout()
        self.mechanism_type_combo = QComboBox()
        self.mechanism_type_combo.addItems([
            MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MECHANISM_TYPE_USER_DISPLAY_CAM,
            "Gear System",
            "Custom Linkage"
        ])
        mechanism_type_layout.addRow("Type:", self.mechanism_type_combo)
        generation_layout.addLayout(mechanism_type_layout)

        # Buttons
        self.recommendation_btn = QPushButton("Get Recommendations")
        self.recommendation_btn.setEnabled(False)
        generation_layout.addWidget(self.recommendation_btn)

        self.generate_mechanism_btn = QPushButton("Generate Mechanism")
        self.generate_mechanism_btn.setEnabled(False)
        generation_layout.addWidget(self.generate_mechanism_btn)

        panel_layout.addWidget(generation_group)

        # 3. Parametric Design Group
        self.mechanism_params_group = QGroupBox("3 Parametric Design")
        self.mechanism_params_group.setStyleSheet("""
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
        params_layout = QVBoxLayout(self.mechanism_params_group)

        # Info label
        param_info_label = QLabel("Select a mechanism layer to adjust parameters")
        param_info_label.setWordWrap(True)
        param_info_label.setStyleSheet("""
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            color: #495057;
        """)
        params_layout.addWidget(param_info_label)

        # Parametric edit button
        self.parametric_edit_btn = QPushButton("Start Parametric Editing")
        self.parametric_edit_btn.setCheckable(True)
        self.parametric_edit_btn.setEnabled(False)
        self.parametric_edit_btn.setToolTip("Enable interactive parameter adjustment by dragging")
        self.parametric_edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                border: 1px solid #138496;
                border-radius: 7px;
                padding: 10px 18px;
                font-weight: bold;
                color: white;
                min-height: 30px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
            QPushButton:checked {
                background-color: #117a8b;
                border-color: #0c5460;
            }
            QPushButton:disabled {
                background-color: #e0e6ed;
                color: #a0aab5;
                border-color: #dbe4f0;
            }
        """)
        params_layout.addWidget(self.parametric_edit_btn)

        panel_layout.addWidget(self.mechanism_params_group)

        # 4. Animation Group
        animation_group = QGroupBox("4 Animation")
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

        # Part attachment mode
        self.start_edit_btn = QPushButton("Attach Parts to Mechanism")
        self.start_edit_btn.setCheckable(True)
        self.start_edit_btn.setEnabled(False)
        self.start_edit_btn.setToolTip("Enable mode to attach parts to mechanism points")
        animation_layout.addWidget(self.start_edit_btn)

        # Animation controls
        anim_button_layout = QHBoxLayout()
        self.animate_btn = QPushButton("Play")
        self.animate_btn.setEnabled(False)
        self.stop_animate_btn = QPushButton("Stop")
        self.stop_animate_btn.setEnabled(False)
        anim_button_layout.addWidget(self.animate_btn)
        anim_button_layout.addWidget(self.stop_animate_btn)
        animation_layout.addLayout(anim_button_layout)

        # Blueprint button
        self.blueprint_btn = QPushButton("Generate Blueprint")
        self.blueprint_btn.setEnabled(False)
        animation_layout.addWidget(self.blueprint_btn)

        panel_layout.addWidget(animation_group)

        # 5. View Controls Group
        view_controls_group = QGroupBox("5 View Controls")
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
        main_layout.addWidget(scroll_area)

        # Right side - Editor view (same as EditorTab)
        main_layout.addWidget(self.mechanism_view, 1)

    def _connect_signals(self):
        """Connect signals"""
        self.mechanism_type_combo.currentTextChanged.connect(self._on_mechanism_type_changed)
        self.parts_selection_combo.currentTextChanged.connect(self._on_part_selection_changed)
        self.generate_mechanism_btn.clicked.connect(self._on_generate_mechanism)
        self.blueprint_btn.clicked.connect(self._on_generate_blueprint)
        self.recommendation_btn.clicked.connect(self._on_get_recommendations)
        self.start_edit_btn.toggled.connect(self._on_edit_mode_toggled)
        self.animate_btn.clicked.connect(self._on_start_animation)
        self.stop_animate_btn.clicked.connect(self._on_stop_animation)
        self.mechanism_layers_list.itemSelectionChanged.connect(self._on_layer_selection_changed)
        self.enable_mechanisms_checkbox.stateChanged.connect(self._on_mechanism_enable_toggled)
        self.parametric_edit_btn.toggled.connect(self._on_parametric_edit_toggled)
        
        # Connect zoom controls
        self.zoom_in_btn.clicked.connect(lambda: self.mechanism_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.mechanism_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.mechanism_view.zoom_to_fit)
        self.zoom_reset_btn.clicked.connect(self.mechanism_view.reset_view)

    @pyqtSlot(str)
    def _on_mechanism_type_changed(self, mechanism_type: str):
        """Mechanism type changed"""
        self.current_mechanism_type = mechanism_type
        self.mechanism_selection_changed.emit(mechanism_type)
        self._update_ui_for_mechanism_type()

    def _update_ui_for_mechanism_type(self):
        """Update UI based on selected mechanism type"""
        if not self.current_mechanism_type:
            return

        # Update UI elements based on mechanism type
        self._check_generation_requirements()

    @pyqtSlot(str)
    def _on_part_selection_changed(self, part_name: str):
        """Target part selection changed"""
        self.selected_part_name = part_name
        self._check_generation_requirements()

    def _check_generation_requirements(self):
        """Check mechanism generation requirements"""
        if self.generate_mechanism_btn is None:
            return  # UI not initialized yet

        can_generate = bool(
            self.selected_part_name and
            self.current_mechanism_type and
            self.selected_part_name in self.path_data
        )
        self.generate_mechanism_btn.setEnabled(can_generate)
        self.recommendation_btn.setEnabled(bool(self.path_data))  # Enable if any paths exist

    @pyqtSlot(bool)
    def _on_parametric_edit_toggled(self, checked: bool):
        """Toggle parametric edit mode"""
        self.parametric_edit_mode = checked

        if checked:
            self.parametric_edit_btn.setText("Stop Parametric Editing")
            # Enable drag handles for selected mechanism
            if self.selected_mechanism_id and self.selected_mechanism_id in self.interactive_handles:
                for handle in self.interactive_handles[self.selected_mechanism_id]:
                    handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                    handle.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.parametric_edit_btn.setText("Start Parametric Editing")
            # Disable all drag handles
            for handles in self.interactive_handles.values():
                for handle in handles:
                    handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                    handle.setCursor(Qt.CursorShape.ArrowCursor)

    @pyqtSlot(int)
    def _on_mechanism_enable_toggled(self, state: int):
        """Toggle mechanism layer enable/disable"""
        if not self.selected_mechanism_id:
            return

        is_enabled = state == Qt.CheckState.Checked.value
        self.mechanism_enabled_state[self.selected_mechanism_id] = is_enabled

        # Update visual appearance
        if self.selected_mechanism_id in self.mechanism_layers:
            layer_data = self.mechanism_layers[self.selected_mechanism_id]
            visual_items = layer_data.get("visual_items", [])

            for item in visual_items:
                if item and item.scene():
                    # Make disabled items semi-transparent
                    item.setOpacity(1.0 if is_enabled else 0.3)

            # Update list item appearance
            for i in range(self.mechanism_layers_list.count()):
                item = self.mechanism_layers_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.selected_mechanism_id:
                    # Update item to show enabled/disabled state
                    font = item.font()
                    font.setItalic(not is_enabled)
                    item.setFont(font)
                    item.setForeground(QBrush(QColor(0, 0, 0) if is_enabled else QColor(160, 170, 181)))
                    break

        logging.info(f"Mechanism {self.selected_mechanism_id} {'enabled' if is_enabled else 'disabled'}")

    @pyqtSlot()
    def _on_generate_mechanism(self):
        """Request mechanism generation"""
        if not self.selected_part_name or not self.current_mechanism_type:
            QMessageBox.warning(self, "Warning", "Please select a part and mechanism type.")
            return

        # Convert display name to internal type
        mechanism_type_mapping = {
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: "4_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: "3_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_CAM: "cam",
            "Gear System": "gear",
            "Custom Linkage": "custom_linkage"
        }

        internal_type = mechanism_type_mapping.get(self.current_mechanism_type, "4_bar_linkage")

        logging.info(f"Generating mechanism: {internal_type} for part {self.selected_part_name}")

        # Generate unique ID for this mechanism
        mechanism_id = str(uuid.uuid4())[:8]
        layer_name = f"{self.current_mechanism_type} - {self.selected_part_name}"

        # Initialize mechanism parameters based on type
        initial_params = self._get_initial_mechanism_params(internal_type)

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": self.selected_part_name,
            "params": initial_params,
            "visual_items": [],  # Will be populated when mechanism is generated
            "generated_path": None  # Will store the path this mechanism generates
        }
        self._add_mechanism_layer(layer_name, layer_data)

        # Enable by default
        self.mechanism_enabled_state[mechanism_id] = True

        # Create interactive handles for parametric design
        self._create_interactive_handles_for_mechanism(mechanism_id, internal_type, initial_params)

        # Generate mechanism visualization immediately (since we don't have a complex mechanism manager)
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, initial_params)

        # Emit request to generate the actual mechanism (for any external processing)
        self.request_generate_mechanism.emit(internal_type, initial_params)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(True)

    @pyqtSlot()
    def _on_generate_blueprint(self):
        """Request blueprint generation"""
        self.request_generate_blueprint.emit()

    def set_path_data_from_editor(self, path_data: Dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        logging.info(f"MechanismDesignTab: Received path data for {len(path_data)} parts: {list(path_data.keys())}")
        self.path_data = path_data.copy()
        self._update_parts_selection()
        self._check_generation_requirements()
        self._display_paths_in_preview()  # Show paths in preview

    def _update_parts_selection(self):
        """Update parts selection combobox"""
        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
            if self.path_data:
                self.parts_selection_combo.addItems(list(self.path_data.keys()))

    def set_parts_data(self, parts_data: Dict[str, PartInfo]):
        """Set parts data (synchronized with editor tab)"""
        self.parts_data = parts_data.copy() if parts_data else {}

        # Create CharacterPartItems for visualization
        self.current_editor_items.clear()

        if parts_data:
            project_dir = None
            if (
                self.main_window
                and hasattr(self.main_window, "project_data_manager")
                and self.main_window.project_data_manager.project_dir
            ):
                project_dir = self.main_window.project_data_manager.project_dir

            for part_name, p_info in parts_data.items():
                if project_dir:
                    item = CharacterPartItem(
                        part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode
                    )
                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item

            part_names = list(parts_data.keys())
            self.parts_selection_combo.clear()
            self.parts_selection_combo.addItems(part_names)
            
            # Auto-fit view when parts are loaded
            self.mechanism_view.zoom_to_fit()

    def clear_mechanism_data(self):
        """Clear mechanism data"""
        self.path_data.clear()
        self.selected_part_name = None
        self.current_mechanism_type = None
        self.mechanism_params.clear()
        self.mechanism_layers.clear()
        self.path_visual_items.clear()
        self.mechanism_enabled_state.clear()
        self.interactive_handles.clear()

        if self.parts_selection_combo is not None:
            self.parts_selection_combo.clear()
        if self.mechanism_scene is not None:
            self.mechanism_scene.clear()
        if self.generate_mechanism_btn is not None:
            self.generate_mechanism_btn.setEnabled(False)
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(False)
        if self.recommendation_btn is not None:
            self.recommendation_btn.setEnabled(False)
        if self.start_edit_btn is not None:
            self.start_edit_btn.setEnabled(False)
            self.start_edit_btn.setChecked(False)
        if self.mechanism_layers_list is not None:
            self.mechanism_layers_list.clear()

    @pyqtSlot(dict)
    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """Handle mechanism visualization data"""
        if not mechanism_graphics_data:
            return

        logging.info(f"MechanismDesignTab: Received mechanism graphics data: {mechanism_graphics_data.keys()}")

        # Add mechanism graphics to preview (don't clear everything, just add the mechanism)
        mechanism_id = mechanism_graphics_data.get("mechanism_id")
        mechanism_type = mechanism_graphics_data.get("mechanism_type")

        if mechanism_id and mechanism_id in self.mechanism_layers:
            # Update the layer data with visual items
            layer_data = self.mechanism_layers[mechanism_id]
            visual_items = []

            # Create visual representation based on mechanism type
            if mechanism_type == "4_bar_linkage":
                visual_items.extend(self._create_4bar_linkage_visuals(mechanism_graphics_data))
            elif mechanism_type == "3_bar_linkage":
                visual_items.extend(self._create_3bar_linkage_visuals(mechanism_graphics_data))
            elif mechanism_type == "cam":
                visual_items.extend(self._create_cam_visuals(mechanism_graphics_data))
            else:
                # Generic mechanism visualization
                visual_items.extend(self._create_generic_mechanism_visuals(mechanism_graphics_data))

            # Store visual items in layer data
            layer_data["visual_items"] = visual_items

            # Add all visual items to scene
            for item in visual_items:
                self.mechanism_scene.addItem(item)

            logging.info(f"MechanismDesignTab: Added {len(visual_items)} visual items for mechanism {mechanism_id}")

        # Update view
        self.mechanism_view.zoom_to_fit()

    def get_selected_part_name(self) -> Optional[str]:
        """Return selected part name"""
        return self.selected_part_name

    def get_current_mechanism_type(self) -> Optional[str]:
        """Return current mechanism type"""
        return self.current_mechanism_type

    def _display_paths_in_preview(self):
        """Display motion paths from editor tab in the preview"""
        logging.info(f"MechanismDesignTab: Displaying {len(self.path_data)} paths in preview")

        # Clear existing path visuals
        for item in self.path_visual_items.values():
            if item.scene():
                self.mechanism_scene.removeItem(item)
        self.path_visual_items.clear()

        # Add new path visuals
        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                logging.debug(f"MechanismDesignTab: Adding path visual for {part_name}")
                path_item = QGraphicsPathItem(path)
                # Use green color similar to editor tab
                pen = QPen(QColor(0, 200, 0), 3.0)
                pen.setCosmetic(True)
                path_item.setPen(pen)
                path_item.setZValue(1)  # Draw above background

                self.mechanism_scene.addItem(path_item)
                self.path_visual_items[part_name] = path_item

        # Fit view to show all paths
        if self.path_visual_items:
            self.mechanism_view.zoom_to_fit()
            logging.info(f"MechanismDesignTab: Successfully displayed {len(self.path_visual_items)} path visuals")
        else:
            # Even if no paths, ensure view is properly fitted when parts are loaded
            if self.current_editor_items:
                self.mechanism_view.zoom_to_fit()

    @pyqtSlot()
    def _on_get_recommendations(self):
        """Show mechanism recommendation dialog"""
        if not self.path_data:
            return

        # Get the selected part's path or first available path
        target_path = None
        if self.selected_part_name and self.selected_part_name in self.path_data:
            target_path = self.path_data[self.selected_part_name]
        else:
            # Get first non-empty path
            for path in self.path_data.values():
                if not path.isEmpty():
                    target_path = path
                    break

        if not target_path:
            QMessageBox.warning(self, "Warning", "No valid motion path found.")
            return

        # Show recommendation dialog with generated paths file
        import os
        from automataii.utils.paths import get_project_root

        # Get the path to the generated mechanism paths JSON file
        generated_paths_file = os.path.join(
            get_project_root(),
            "src", "automataii", "kinematics", "generated_mechanism_paths.json"
        )

        if not os.path.exists(generated_paths_file):
            QMessageBox.warning(self, "Warning", "Generated mechanism paths file not found.")
            logging.error(f"Generated paths file not found at: {generated_paths_file}")
            return

        dialog = MechanismRecommendationDialog(target_path, generated_paths_file, parent=self)

        # Connect preview signal to handle mechanism preview clicks
        dialog.mechanism_preview_selected.connect(self._on_mechanism_preview_selected)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            if selected_mechanism:
                self._select_candidate(selected_mechanism)

    def _qpainterpath_to_numpy(self, path: QPainterPath) -> "np.ndarray":
        """Converts a QPainterPath to a numpy array of points."""
        points = []
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            points.append([element.x, element.y])
        return np.array(points)

    def _display_candidates(self):
        """Displays the recommended mechanism candidates in the UI."""
        # This would typically populate a list widget where users can select a candidate.
        # For now, we'll just log them and auto-select the best one.
        logging.info(f"Found {len(self.candidates)} candidates.")
        for i, candidate in enumerate(self.candidates):
            logging.info(
                f"  {i+1}: {candidate.mechanism_type.value} "
                f"(Score: {candidate.similarity_score:.3f})"
            )

        # For demonstration, let's automatically select the top candidate
        if self.candidates:
            self._select_candidate(self.candidates[0])

    def _select_candidate(self, candidate: MechanismCandidate):
        """Handles the selection of a mechanism candidate."""
        self.selected_mechanism = candidate
        logging.info(f"Selected candidate: {candidate.mechanism_type.value}")

        # Update the UI to reflect the selected mechanism's type and parameters
        # For example, update the mechanism type combo box
        display_name = {
            MechanismType.FOUR_BAR: MECHANISM_TYPE_USER_DISPLAY_4_BAR,
            MechanismType.THREE_BAR: MECHANISM_TYPE_USER_DISPLAY_3_BAR,
            MechanismType.CAM: MECHANISM_TYPE_USER_DISPLAY_CAM,
        }.get(candidate.mechanism_type, "Custom Linkage")

        index = self.mechanism_type_combo.findText(display_name)
        if index >= 0:
            self.mechanism_type_combo.setCurrentIndex(index)

        # Now, generate the mechanism visuals based on this candidate
        self._generate_mechanism_from_candidate(candidate)

    def _generate_mechanism_from_candidate(self, candidate: MechanismCandidate):
        """Generates a mechanism layer and visuals from a selected candidate."""
        mechanism_id = str(uuid.uuid4())[:8]
        layer_name = f"{candidate.mechanism_type.value} - {self.selected_part_name}"

        # The parameters are already in the candidate
        params = candidate.parameters

        layer_data = {
            "id": mechanism_id,
            "type": candidate.mechanism_type.value,
            "part_name": self.selected_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": None,
        }
        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True

        # Create visuals and interactive handles
        self._generate_mechanism_visuals_directly(
            mechanism_id, candidate.mechanism_type.value, params
        )
        self._create_interactive_handles_for_mechanism(
            mechanism_id, candidate.mechanism_type.value, params
        )
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(True)

    @pyqtSlot(bool)
    def _on_edit_mode_toggled(self, checked: bool):
        """Toggle part attachment mode"""
        self.edit_mode = checked

        if checked:
            self.start_edit_btn.setText("Stop Attaching Parts")
            # Show attachment points on mechanisms
            self._show_attachment_points()
        else:
            self.start_edit_btn.setText("Attach Parts to Mechanism")
            # Hide attachment points
            self._hide_attachment_points()

    def _show_attachment_points(self):
        """Show available attachment points on mechanisms"""
        # For each enabled mechanism, show points where parts can attach
        for mechanism_id, is_enabled in self.mechanism_enabled_state.items():
            if is_enabled and mechanism_id in self.mechanism_layers:
                layer_data = self.mechanism_layers[mechanism_id]
                mechanism_type = layer_data.get("type")

                # Create visual indicators for attachment points
                if mechanism_type == "4_bar_linkage":
                    # Show coupler point, rocker endpoint, etc.
                    pass
                elif mechanism_type == "cam":
                    # Show follower attachment point
                    pass

    def _hide_attachment_points(self):
        """Hide attachment point indicators"""
        # Remove attachment point visuals
        pass

    @pyqtSlot()
    def _on_start_animation(self):
        """Start mechanism animation"""
        self.animate_btn.setEnabled(False)
        self.stop_animate_btn.setEnabled(True)

        # Store original positions for all mechanism items
        self.animating_mechanisms.clear()
        for mechanism_id, layer_data in self.mechanism_layers.items():
            visual_items = layer_data.get("visual_items", [])
            if visual_items:
                self.animating_mechanisms[mechanism_id] = {
                    "type": layer_data.get("type"),
                    "params": layer_data.get("params", {}),
                    "items": visual_items,
                    "original_transforms": {}
                }
                # Store original transforms
                for item in visual_items:
                    if item and item.scene():
                        self.animating_mechanisms[mechanism_id]["original_transforms"][item] = item.transform()

        # Start animation timer
        self.animation_time = 0.0
        self.animation_timer.start(33)  # ~30 FPS
        logging.info("Started mechanism animation")

    @pyqtSlot()
    def _on_stop_animation(self):
        """Stop mechanism animation"""
        self.animate_btn.setEnabled(True)
        self.stop_animate_btn.setEnabled(False)

        # Stop timer
        self.animation_timer.stop()

        # Restore original positions
        for mechanism_id, anim_data in self.animating_mechanisms.items():
            for item, original_transform in anim_data["original_transforms"].items():
                if item and item.scene():
                    item.setTransform(original_transform)

        self.animating_mechanisms.clear()
        self.animation_time = 0.0
        logging.info("Stopped mechanism animation")

    @pyqtSlot()
    def _on_layer_selection_changed(self):
        """Handle mechanism layer selection change"""
        selected_items = self.mechanism_layers_list.selectedItems()
        if selected_items:
            mechanism_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.selected_mechanism_id = mechanism_id
            logging.info(f"Selected mechanism layer: {mechanism_id}")

            # Update enable checkbox state
            if self.enable_mechanisms_checkbox and mechanism_id in self.mechanism_enabled_state:
                self.enable_mechanisms_checkbox.setChecked(self.mechanism_enabled_state[mechanism_id])

            # Highlight selected layer in preview
            if mechanism_id in self.mechanism_layers:
                layer_data = self.mechanism_layers[mechanism_id]

                # Reset all items to normal appearance
                for item in self.mechanism_scene.items():
                    if isinstance(item, QGraphicsPathItem):
                        # Reset to default pen
                        pen = item.pen()
                        pen.setWidth(2.0)
                        item.setPen(pen)
                        item.setOpacity(0.7)

                # Highlight items belonging to selected layer
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if item and item.scene() == self.mechanism_scene:
                        # Highlight with thicker pen and full opacity
                        pen = item.pen()
                        pen.setWidth(4.0)
                        item.setPen(pen)
                        item.setOpacity(1.0)

                # Show/hide interactive handles
                for mech_id, handles in self.interactive_handles.items():
                    for handle in handles:
                        handle.setVisible(mech_id == mechanism_id)
        else:
            self.selected_mechanism_id = None

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the layers list"""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data

        # Add to list widget
        item = QListWidgetItem(layer_name)
        item.setData(Qt.ItemDataRole.UserRole, mechanism_id)  # Store ID for reference
        self.mechanism_layers_list.addItem(item)

        # Enable controls
        if self.start_edit_btn is not None:
            self.start_edit_btn.setEnabled(True)
        if self.animate_btn is not None:
            self.animate_btn.setEnabled(True)
        if self.enable_mechanisms_checkbox is not None:
            self.enable_mechanisms_checkbox.setEnabled(True)
        if self.parametric_edit_btn is not None:
            self.parametric_edit_btn.setEnabled(True)

    @pyqtSlot(dict)
    def _on_mechanism_preview_selected(self, mechanism_data: dict):
        """Handle mechanism preview selection from recommendation dialog"""
        logging.info(f"Mechanism preview selected: {mechanism_data.get('type', 'Unknown')}")
        # Could update a preview or show additional info here

    def _update_animation(self):
        """Update animation frame - mechanisms drive part motion"""
        # Increment animation time
        self.animation_time += 0.033 * self.animation_speed  # 33ms * speed

        # For each enabled mechanism, calculate its output motion
        for mechanism_id, is_enabled in self.mechanism_enabled_state.items():
            if not is_enabled:
                continue

            if mechanism_id not in self.mechanism_layers:
                continue

            layer_data = self.mechanism_layers[mechanism_id]
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})
            attached_part = layer_data.get("part_name")

            # Calculate mechanism output position
            output_pos = self._calculate_mechanism_output(mech_type, params, self.animation_time)

            # Move attached part to follow mechanism
            if attached_part and attached_part in self.current_editor_items:
                part_item = self.current_editor_items[attached_part]
                if output_pos:
                    # Part follows mechanism's output point
                    part_item.set_scene_position_from_anchor(output_pos)

            # Update mechanism visuals
            self._update_mechanism_visuals(mechanism_id, self.animation_time)

        # Update scene
        self.mechanism_scene.update()

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float) -> Optional[QPointF]:
        """Calculate the output position of a mechanism at given time"""
        if mech_type == "cam":
            center = params.get("center", QPointF(0, 0))
            base_radius = params.get("base_radius", 50)
            rise = params.get("rise", 30)

            # Simple cam profile - can be made more sophisticated
            angle = time
            radius = base_radius + rise * (1 + math.sin(angle)) / 2

            # Follower position (assuming vertical follower)
            return QPointF(center.x(), center.y() - radius)

        elif mech_type == "4_bar_linkage":
            # Calculate coupler point position using 4-bar kinematics
            # This is simplified - real implementation would use proper kinematic equations
            crank_angle = time
            crank_length = params.get("crank_length", 80)
            coupler_length = params.get("coupler_length", 150)

            # Simplified calculation
            crank_end = QPointF(
                crank_length * math.cos(crank_angle),
                crank_length * math.sin(crank_angle)
            )

            # Coupler midpoint (simplified)
            return QPointF(
                crank_end.x() + coupler_length * 0.5 * math.cos(crank_angle + math.pi/4),
                crank_end.y() + coupler_length * 0.5 * math.sin(crank_angle + math.pi/4)
            )

        return None

    def _update_mechanism_visuals(self, mechanism_id: str, time: float):
        """Update visual representation of mechanism during animation"""
        # Update mechanism linkages, cam rotation, etc.
        pass

    def _create_interactive_handles_for_mechanism(self, mechanism_id: str, mechanism_type: str, params: dict):
        """Create draggable handles for parametric design"""
        if mechanism_id in self.interactive_handles:
            # Remove existing handles
            for handle in self.interactive_handles[mechanism_id]:
                if handle.scene():
                    self.mechanism_scene.removeItem(handle)
            self.interactive_handles[mechanism_id].clear()

        handles = []

        if mechanism_type == "4_bar_linkage":
            # Create handles for ground pivots and link endpoints
            # These will be circles that can be dragged to adjust parameters
            p0 = params.get("ground_pivot_1", QPointF(0, 0))
            p3 = params.get("ground_pivot_2", QPointF(200, 0))

            # Ground pivot handles
            handle_p0 = self._create_drag_handle(p0, "ground_pivot_1", mechanism_id)
            handle_p3 = self._create_drag_handle(p3, "ground_pivot_2", mechanism_id)
            handles.extend([handle_p0, handle_p3])

            # Link length handles (shown as adjustable endpoints)
            # These will update when dragged

        elif mechanism_type == "3_bar_linkage":
            # Similar handles for 3-bar
            pass

        elif mechanism_type == "cam":
            # Handle for cam center and radius
            center = params.get("center", QPointF(0, 0))
            radius = params.get("base_radius", 50)

            # Center handle
            handle_center = self._create_drag_handle(center, "center", mechanism_id)
            handles.append(handle_center)

            # Radius handle (on perimeter)
            radius_pos = QPointF(center.x() + radius, center.y())
            handle_radius = self._create_drag_handle(radius_pos, "radius", mechanism_id)
            handles.append(handle_radius)

        self.interactive_handles[mechanism_id] = handles

    def _create_drag_handle(self, position: QPointF, param_name: str, mechanism_id: str) -> QGraphicsEllipseItem:
        """Create a draggable handle for parameter adjustment"""
        handle = QGraphicsEllipseItem(-8, -8, 16, 16)
        handle.setPos(position)
        handle.setBrush(QBrush(QColor(23, 162, 184)))  # Teal color
        handle.setPen(QPen(QColor(255, 255, 255), 2))
        handle.setZValue(100)  # Above other items
        handle.setCursor(Qt.CursorShape.OpenHandCursor)

        # Store metadata
        handle.setData(0, mechanism_id)
        handle.setData(1, param_name)

        # Make draggable when in parametric edit mode
        handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, self.parametric_edit_mode)
        handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)

        # Connect position change to parameter update
        if hasattr(handle, 'itemChange'):
            # Override itemChange to handle parameter updates
            original_itemChange = handle.itemChange
            def handle_itemChange(change, value):
                if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
                    self._update_mechanism_from_handle_position(mechanism_id, param_name, handle.pos())
                return original_itemChange(change, value)
            handle.itemChange = handle_itemChange

        self.mechanism_scene.addItem(handle)
        return handle

    def _get_initial_mechanism_params(self, mechanism_type: str) -> dict:
        """Get initial parameters for a mechanism type"""
        if mechanism_type == "4_bar_linkage":
            return {
                "ground_pivot_1": QPointF(-100, 0),
                "ground_pivot_2": QPointF(100, 0),
                "crank_length": 80.0,
                "coupler_length": 150.0,
                "rocker_length": 100.0
            }
        elif mechanism_type == "3_bar_linkage":
            return {
                "ground_pivot": QPointF(0, 0),
                "link1_length": 100.0,
                "link2_length": 120.0
            }
        elif mechanism_type == "cam":
            return {
                "center": QPointF(0, 0),
                "base_radius": 50.0,
                "rise": 30.0,
                "dwell_angle": 90.0,
                "profile_type": "cycloidal"
            }
        else:
            return {}

    def _create_4bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of 4-bar linkage"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get pivot points and link parameters
        p0 = params.get("ground_pivot_1", QPointF(-100, 0))
        p3 = params.get("ground_pivot_2", QPointF(100, 0))
        crank_length = params.get("crank_length", 80.0)
        coupler_length = params.get("coupler_length", 150.0)
        rocker_length = params.get("rocker_length", 100.0)

        # Calculate current positions (simplified - for static display)
        angle = 0.0  # Can be parameterized later for animation
        p1 = QPointF(p0.x() + crank_length * math.cos(angle),
                    p0.y() + crank_length * math.sin(angle))

        # Simplified calculation for p2 (coupler point)
        p2 = QPointF(p1.x() + coupler_length * math.cos(angle + math.pi/4),
                    p1.y() + coupler_length * math.sin(angle + math.pi/4))

        # Create links as lines
        crank_line = QGraphicsPathItem()
        crank_path = QPainterPath()
        crank_path.moveTo(p0)
        crank_path.lineTo(p1)
        crank_line.setPath(crank_path)
        crank_line.setPen(QPen(QColor(0, 100, 200), 4))
        visual_items.append(crank_line)

        coupler_line = QGraphicsPathItem()
        coupler_path = QPainterPath()
        coupler_path.moveTo(p1)
        coupler_path.lineTo(p2)
        coupler_line.setPath(coupler_path)
        coupler_line.setPen(QPen(QColor(200, 100, 0), 4))
        visual_items.append(coupler_line)

        rocker_line = QGraphicsPathItem()
        rocker_path = QPainterPath()
        rocker_path.moveTo(p2)
        rocker_path.lineTo(p3)
        rocker_line.setPath(rocker_path)
        rocker_line.setPen(QPen(QColor(100, 200, 0), 4))
        visual_items.append(rocker_line)

        # Create pivot points
        for point in [p0, p1, p2, p3]:
            pivot = QGraphicsEllipseItem(-5, -5, 10, 10)
            pivot.setPos(point)
            pivot.setBrush(QBrush(QColor(255, 0, 0)))
            pivot.setPen(QPen(QColor(0, 0, 0), 2))
            visual_items.append(pivot)

        return visual_items

    def _create_3bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of 3-bar linkage"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get parameters
        ground_pivot = params.get("ground_pivot", QPointF(0, 0))
        link1_length = params.get("link1_length", 100.0)
        link2_length = params.get("link2_length", 120.0)

        # Calculate positions (simplified)
        angle1 = 0.0
        angle2 = math.pi/3

        p1 = QPointF(ground_pivot.x() + link1_length * math.cos(angle1),
                    ground_pivot.y() + link1_length * math.sin(angle1))
        p2 = QPointF(p1.x() + link2_length * math.cos(angle2),
                    p1.y() + link2_length * math.sin(angle2))

        # Create links
        link1_line = QGraphicsPathItem()
        link1_path = QPainterPath()
        link1_path.moveTo(ground_pivot)
        link1_path.lineTo(p1)
        link1_line.setPath(link1_path)
        link1_line.setPen(QPen(QColor(0, 150, 200), 4))
        visual_items.append(link1_line)

        link2_line = QGraphicsPathItem()
        link2_path = QPainterPath()
        link2_path.moveTo(p1)
        link2_path.lineTo(p2)
        link2_line.setPath(link2_path)
        link2_line.setPen(QPen(QColor(200, 150, 0), 4))
        visual_items.append(link2_line)

        # Create pivots
        for point in [ground_pivot, p1, p2]:
            pivot = QGraphicsEllipseItem(-5, -5, 10, 10)
            pivot.setPos(point)
            pivot.setBrush(QBrush(QColor(255, 0, 0)))
            pivot.setPen(QPen(QColor(0, 0, 0), 2))
            visual_items.append(pivot)

        return visual_items

    def _create_cam_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of cam mechanism"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get parameters
        center = params.get("center", QPointF(0, 0))
        base_radius = params.get("base_radius", 50.0)
        rise = params.get("rise", 30.0)

        # Create cam body (simplified circular cam)
        cam_body = QGraphicsEllipseItem(-base_radius, -base_radius,
                                       base_radius * 2, base_radius * 2)
        cam_body.setPos(center)
        cam_body.setBrush(QBrush(QColor(100, 100, 200, 150)))
        cam_body.setPen(QPen(QColor(0, 0, 150), 3))
        visual_items.append(cam_body)

        # Create follower
        follower_pos = QPointF(center.x(), center.y() - base_radius - rise/2)
        follower = QGraphicsEllipseItem(-10, -20, 20, 40)
        follower.setPos(follower_pos)
        follower.setBrush(QBrush(QColor(200, 100, 100)))
        follower.setPen(QPen(QColor(150, 0, 0), 2))
        visual_items.append(follower)

        # Create center point
        center_point = QGraphicsEllipseItem(-3, -3, 6, 6)
        center_point.setPos(center)
        center_point.setBrush(QBrush(QColor(0, 0, 0)))
        visual_items.append(center_point)

        return visual_items

    def _create_generic_mechanism_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create generic visual representation for unknown mechanism types"""
        visual_items = []

        # Create a simple placeholder box
        placeholder = QGraphicsEllipseItem(-25, -25, 50, 50)
        placeholder.setBrush(QBrush(QColor(150, 150, 150, 100)))
        placeholder.setPen(QPen(QColor(100, 100, 100), 2))
        visual_items.append(placeholder)

        return visual_items

    def _generate_mechanism_visuals_directly(self, mechanism_id: str, mechanism_type: str, params: dict):
        """Generate mechanism visuals directly without external mechanism manager"""

        # Scale parameters to fit the view appropriately
        scene_rect = self.mechanism_view.sceneRect()
        if scene_rect.isEmpty():
            scene_rect = QRectF(-200, -200, 400, 400)

        # Scale factor to fit mechanism in scene
        scale_factor = min(scene_rect.width(), scene_rect.height()) / 400.0

        # Scale parameters
        scaled_params = self._scale_mechanism_params(params, scale_factor)

        # Create mechanism graphics data
        mechanism_graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": mechanism_type,
            "params": scaled_params,
            "scale_factor": scale_factor
        }

        # Handle the visuals directly
        self.handle_mechanism_visuals(mechanism_graphics_data)

        logging.info(f"MechanismDesignTab: Generated visuals for {mechanism_type} mechanism {mechanism_id}")

    def _scale_mechanism_params(self, params: dict, scale_factor: float) -> dict:
        """Scale mechanism parameters to fit appropriately in the scene"""
        scaled_params = {}

        for key, value in params.items():
            if key.endswith("_length") or key.endswith("_radius"):
                # Scale length and radius parameters
                scaled_params[key] = value * scale_factor
            elif isinstance(value, QPointF):
                # Scale point coordinates
                scaled_params[key] = QPointF(value.x() * scale_factor, value.y() * scale_factor)
            else:
                # Keep other parameters as-is
                scaled_params[key] = value

        return scaled_params

    def _update_mechanism_from_handle_position(self, mechanism_id: str, param_name: str, new_position: QPointF):
        """Update mechanism parameters when a handle is moved"""
        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers[mechanism_id]
        params = layer_data.get("params", {})
        mechanism_type = layer_data.get("type")

        # Update the parameter based on the handle's new position
        if param_name in ["ground_pivot_1", "ground_pivot_2", "center", "ground_pivot"]:
            params[param_name] = new_position
        elif param_name == "radius":
            # For radius handles, calculate distance from center
            center = params.get("center", QPointF(0, 0))
            radius = math.sqrt((new_position.x() - center.x())**2 + (new_position.y() - center.y())**2)
            params["base_radius"] = radius

        # Regenerate the mechanism visuals with updated parameters
        self._regenerate_mechanism_visuals(mechanism_id, mechanism_type, params)

        # Emit parameter change signal
        self.mechanism_parameters_changed.emit(mechanism_id, params)

    def _regenerate_mechanism_visuals(self, mechanism_id: str, mechanism_type: str, params: dict):
        """Regenerate mechanism visuals after parameter changes"""
        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers[mechanism_id]

        # Remove old visual items
        old_items = layer_data.get("visual_items", [])
        for item in old_items:
            if item and item.scene():
                self.mechanism_scene.removeItem(item)

        # Generate new visuals
        self._generate_mechanism_visuals_directly(mechanism_id, mechanism_type, params)

        # Update interactive handles to new positions
        self._update_interactive_handles_positions(mechanism_id, mechanism_type, params)

    def _update_interactive_handles_positions(self, mechanism_id: str, mechanism_type: str, params: dict):
        """Update positions of interactive handles after parameter changes"""
        if mechanism_id not in self.interactive_handles:
            return

        handles = self.interactive_handles[mechanism_id]

        for handle in handles:
            param_name = handle.data(1)

            if param_name in params:
                value = params[param_name]
                if isinstance(value, QPointF):
                    handle.setPos(value)
                elif param_name == "radius" and "center" in params and "base_radius" in params:
                    # Position radius handle on perimeter
                    center = params["center"]
                    radius = params["base_radius"]
                    handle.setPos(QPointF(center.x() + radius, center.y()))
