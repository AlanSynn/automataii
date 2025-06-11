import logging
from typing import Optional, Dict, Any, List
import math
import uuid
import numpy as np

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QDialog,
    QGraphicsItem,
    QCheckBox,
    QScrollArea,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QGraphicsTextItem,
    QStyle,
)
from PyQt6.QtCore import pyqtSignal, QPointF, Qt, QTimer, QRectF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform

from ..views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem
from automataii.core.models import PartInfo
from automataii.kinematics.mechanism import (
    MechanismCandidate,
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

        # Ensure mechanism view has access to current_editor_items like editor tab
        # This is needed for IK updates to work properly

        # Skeleton visualization items (manual approach for mechanism tab)
        self.skeleton_joint_items: Dict[str, QGraphicsEllipseItem] = {}
        self.skeleton_bone_items: Dict[str, QGraphicsLineItem] = {}

        # Mechanism path tracing
        self.mechanism_path_items: Dict[str, QGraphicsPathItem] = {}
        self.mechanism_path_points: Dict[str, List[QPointF]] = {}

        # Debug visualization items
        self.debug_items: List[QGraphicsItem] = []
        self.show_debug = False

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
        self.blueprint_btn: Optional[QPushButton] = None
        self.recommendation_btn: Optional[QPushButton] = None
        self.mechanism_layers_list: Optional[QListWidget] = None
        self.play_btn: Optional[QPushButton] = None
        self.stop_btn: Optional[QPushButton] = None
        self.reset_btn: Optional[QPushButton] = None
        self.animation_status_label: Optional[QLabel] = None

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

        # 2. Mechanism Generation Group (simplified)
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

        # Only recommendation button - no target part or type selection
        self.recommendation_btn = QPushButton("Get Recommendations")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations based on motion paths")
        generation_layout.addWidget(self.recommendation_btn)

        # Parametric Design as subsection within Generation Group
        param_info_label = QLabel("Select a mechanism layer to adjust parameters")
        param_info_label.setWordWrap(True)
        param_info_label.setStyleSheet("""
            padding: 10px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            color: #495057;
            margin-top: 15px;
        """)
        generation_layout.addWidget(param_info_label)

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
        generation_layout.addWidget(self.parametric_edit_btn)

        panel_layout.addWidget(generation_group)

        # 3. Animation Group (Editor Tab style)
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

        # Animation status label (like Editor Tab)
        self.animation_status_label = QLabel("No mechanisms defined")
        self.animation_status_label.setStyleSheet("""
            font-size: 13px;
            color: #6c757d;
            padding-bottom: 8px;
        """)
        self.animation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        animation_layout.addWidget(self.animation_status_label)

        # Centering layout for animation controls (like Editor Tab)
        centering_layout = QHBoxLayout()
        centering_layout.addStretch()

        animation_controls_layout = QHBoxLayout()
        animation_controls_layout.setSpacing(0)

        icon_size = 18
        button_size = icon_size + 16

        # Common style for all animation buttons (like Editor Tab)
        animation_button_style = f"""
            QPushButton {{
                background-color: #ffffff;
                border: 1px solid #d0d7de;
                padding: 8px;
                max-width: {button_size}px;
                max-height: {button_size}px;
                min-width: {button_size}px;
                min-height: {button_size}px;
            }}
            QPushButton:hover {{
                background-color: #f6f8fa;
            }}
            QPushButton:pressed {{
                background-color: #e9ecef;
                border-color: #b0b7bf;
            }}
            QPushButton:disabled {{
                background-color: #f6f8fa;
                opacity: 0.6;
            }}
        """

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("playButton")
        play_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.play_btn.setIcon(play_icon)
        self.play_btn.setIconSize(play_icon.actualSize(self.play_btn.size()))
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setStyleSheet(animation_button_style + """
            QPushButton#playButton {
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                border-right-width: 0px;
            }
        """)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("stopButton")
        stop_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.stop_btn.setIcon(stop_icon)
        self.stop_btn.setIconSize(stop_icon.actualSize(self.stop_btn.size()))
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setStyleSheet(animation_button_style + """
            QPushButton#stopButton {
                border-radius: 0px;
                border-right-width: 0px;
            }
        """)

        self.reset_btn = QPushButton()
        self.reset_btn.setObjectName("resetButton")
        reset_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.reset_btn.setIcon(reset_icon)
        self.reset_btn.setIconSize(reset_icon.actualSize(self.reset_btn.size()))
        self.reset_btn.setToolTip("Reset Animation")
        self.reset_btn.setStyleSheet(animation_button_style + """
            QPushButton#resetButton {
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)

        animation_controls_layout.addWidget(self.play_btn)
        animation_controls_layout.addWidget(self.stop_btn)
        animation_controls_layout.addWidget(self.reset_btn)

        # Add clear paths button
        self.clear_paths_btn = QPushButton()
        self.clear_paths_btn.setObjectName("clearPathsButton")
        clear_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        self.clear_paths_btn.setIcon(clear_icon)
        self.clear_paths_btn.setIconSize(clear_icon.actualSize(self.clear_paths_btn.size()))
        self.clear_paths_btn.setToolTip("Clear Mechanism Paths")
        self.clear_paths_btn.setStyleSheet(animation_button_style + """
            QPushButton#clearPathsButton {
                border-left: none;
                border-radius: 0px;
            }
        """)
        self.clear_paths_btn.clicked.connect(self._clear_mechanism_paths)
        animation_controls_layout.addWidget(self.clear_paths_btn)

        # Add debug toggle button
        self.debug_btn = QPushButton("Debug")
        self.debug_btn.setCheckable(True)
        self.debug_btn.setToolTip("Toggle coordinate system debug display")
        self.debug_btn.setStyleSheet(animation_button_style + """
            QPushButton {
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QPushButton:checked {
                background-color: #0969da;
                color: white;
            }
        """)
        self.debug_btn.toggled.connect(self._toggle_debug_display)
        animation_controls_layout.addWidget(self.debug_btn)

        centering_layout.addLayout(animation_controls_layout)
        centering_layout.addStretch()

        animation_layout.addLayout(centering_layout)

        panel_layout.addWidget(animation_group)

        # 4. Blueprint Generation Group (separate section)
        blueprint_group = QGroupBox("4 Blueprint Generation")
        blueprint_group.setStyleSheet("""
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
        blueprint_layout = QVBoxLayout(blueprint_group)

        # Blueprint button
        self.blueprint_btn = QPushButton("Generate Blueprint")
        self.blueprint_btn.setEnabled(False)
        self.blueprint_btn.setToolTip("Generate manufacturing blueprint from selected mechanism")
        self.blueprint_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                border: 1px solid #1e7e34;
                border-radius: 7px;
                padding: 10px 18px;
                font-weight: bold;
                color: white;
                min-height: 30px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #e0e6ed;
                color: #a0aab5;
                border-color: #dbe4f0;
            }
        """)
        blueprint_layout.addWidget(self.blueprint_btn)

        panel_layout.addWidget(blueprint_group)

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
        # Removed UI elements (Target Part and Type selection)
        # self.mechanism_type_combo.currentTextChanged.connect(self._on_mechanism_type_changed)
        # self.parts_selection_combo.currentTextChanged.connect(self._on_part_selection_changed)
        # self.generate_mechanism_btn.clicked.connect(self._on_generate_mechanism)

        # Main generation and blueprint buttons
        self.blueprint_btn.clicked.connect(self._on_generate_blueprint)
        self.recommendation_btn.clicked.connect(self._on_get_recommendations)

        # Animation controls (Editor Tab style)
        self.play_btn.clicked.connect(self._on_start_animation)
        self.stop_btn.clicked.connect(self._on_stop_animation)
        self.reset_btn.clicked.connect(self._on_reset_animation)

        # Layer management
        self.mechanism_layers_list.itemSelectionChanged.connect(self._on_layer_selection_changed)
        self.enable_mechanisms_checkbox.stateChanged.connect(self._on_mechanism_enable_toggled)

        # Parametric editing
        self.parametric_edit_btn.toggled.connect(self._on_parametric_edit_toggled)

        # Connect zoom controls
        self.zoom_in_btn.clicked.connect(lambda: self.mechanism_view.zoom(1))
        self.zoom_out_btn.clicked.connect(lambda: self.mechanism_view.zoom(-1))
        self.zoom_fit_btn.clicked.connect(self.mechanism_view.zoom_to_fit)
        self.zoom_reset_btn.clicked.connect(self.mechanism_view.reset_view)

        # Connect to IK manager signals (like editor tab does)
        # Note: This might be called before IK manager is initialized, so we'll retry in connect_ik_signals
        self.connect_ik_signals()

    def connect_ik_signals(self):
        """Connect to IK manager signals - can be called multiple times safely"""
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            ik_manager = self.main_window.ik_manager
            if hasattr(ik_manager, 'character_visuals_updated'):
                try:
                    # Disconnect first to avoid duplicate connections
                    ik_manager.character_visuals_updated.disconnect(self.handle_ik_update)
                except (TypeError, RuntimeError):
                    pass  # Ignore if not connected

                ik_manager.character_visuals_updated.connect(self.handle_ik_update)
                logging.info("Connected mechanism tab to IK manager character_visuals_updated signal")
                return True
        else:
            logging.debug("IK manager not available for signal connection")
            return False

    @pyqtSlot(dict)
    def handle_ik_update(self, ik_results: Dict[str, Dict[str, Any]]):
        """Handle IK updates from the IK manager (like editor tab does)"""
        if not self.mechanism_view:
            return

        if ik_results:
            # Update skeleton and part visuals using the same method as editor tab
            self.mechanism_view.update_visuals_from_animation_data(ik_results)
            logging.debug(f"Updated mechanism tab visuals from IK results: {len(ik_results)} joints")

        # Update the scene
        if self.mechanism_scene:
            self.mechanism_scene.update()

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
        if self.recommendation_btn is None:
            return  # UI not initialized yet

        # Enable recommendation button if any paths exist
        self.recommendation_btn.setEnabled(bool(self.path_data))

        # Enable blueprint generation if any mechanisms exist
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(bool(self.mechanism_layers))

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

    def on_skeleton_updated(self, skeleton_data: Optional[Dict]):
        """Called when skeleton is updated - display skeleton that follows mechanism motion."""
        if not skeleton_data:
            logging.info("MechanismDesignTab: Clearing skeleton visualization")
            if hasattr(self, 'skeleton_joints'):
                for joint_item in self.skeleton_joints.values():
                    if joint_item and joint_item.scene():
                        self.mechanism_scene.removeItem(joint_item)
                self.skeleton_joints.clear()
            if hasattr(self, 'skeleton_bones'):
                for bone_item in self.skeleton_bones:
                    if bone_item and bone_item.scene():
                        self.mechanism_scene.removeItem(bone_item)
                self.skeleton_bones.clear()
            return

        # Store skeleton data for reference
        self.current_skeleton_data = skeleton_data

        # Also pass skeleton data to mechanism view for proper skeleton visualization
        if hasattr(self.mechanism_view, 'visualize_skeleton'):
            skeleton_joints = skeleton_data.get("joints", {})
            hierarchy_data = skeleton_data.get("hierarchy", {})

            # Convert to format expected by EditorView.visualize_skeleton
            skeleton_data_for_view = []
            for joint_id, joint_info in skeleton_joints.items():
                joint_entry = {
                    'id': joint_id,
                    'position': joint_info.get('position', [0, 0]),
                    'parent': None  # Will be filled from hierarchy
                }
                skeleton_data_for_view.append(joint_entry)

            # Set parent relationships from hierarchy
            for parent_id, children_ids in hierarchy_data.items():
                for child_id in children_ids:
                    for joint_entry in skeleton_data_for_view:
                        if joint_entry['id'] == child_id:
                            joint_entry['parent'] = parent_id
                            break

            self.mechanism_view.visualize_skeleton(skeleton_data_for_view, hierarchy_data)
            logging.debug(f"Passed skeleton data to mechanism view: {len(skeleton_data_for_view)} joints")

        # Update part positions based on skeleton joints (like editor tab)
        # BUT skip parts that are being controlled by mechanisms
        if self.current_editor_items and self.parts_data:
            joints_dict = skeleton_data.get("joints", {})
            joint_map = skeleton_data.get("joint_map", {})

            # Get list of parts controlled by active mechanisms
            mechanism_controlled_parts = set()
            if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
                for mechanism_id, is_enabled in self.mechanism_enabled_state.items():
                    if is_enabled and mechanism_id in self.mechanism_layers:
                        attached_part = self.mechanism_layers[mechanism_id].get("part_name")
                        if attached_part:
                            mechanism_controlled_parts.add(attached_part)

            for part_name, part_item in self.current_editor_items.items():
                # Skip parts controlled by mechanisms during animation
                if part_name in mechanism_controlled_parts:
                    logging.debug(f"MechanismDesignTab: Skipping part '{part_name}' - controlled by mechanism")
                    continue

                if part_name in self.parts_data:
                    part_info = self.parts_data[part_name]
                    anchor_joint_id = part_info.anchor_joint_id

                    if anchor_joint_id:
                        # Find standardized joint ID
                        std_joint_id = None
                        for orig_name, std_id in joint_map.items():
                            if orig_name == anchor_joint_id:
                                std_joint_id = std_id
                                break

                        # Update part position if joint found
                        if std_joint_id and std_joint_id in joints_dict:
                            joint_data = joints_dict[std_joint_id]
                            joint_pos = joint_data.get("position", [0, 0])
                            if len(joint_pos) >= 2:
                                scene_pos = QPointF(joint_pos[0], joint_pos[1])
                                part_item.set_scene_position_from_anchor(scene_pos)
                                logging.debug(f"MechanismDesignTab: Updated part '{part_name}' position to joint '{std_joint_id}' at ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})")

        # Create skeleton visualization items if not already created
        if not hasattr(self, 'skeleton_joints'):
            self.skeleton_joints = {}
        if not hasattr(self, 'skeleton_bones'):
            self.skeleton_bones = []

        # Clear existing skeleton visuals
        for joint_item in self.skeleton_joints.values():
            if joint_item and joint_item.scene():
                self.mechanism_scene.removeItem(joint_item)
        self.skeleton_joints.clear()

        for bone_item in self.skeleton_bones:
            if bone_item and bone_item.scene():
                self.mechanism_scene.removeItem(bone_item)
        self.skeleton_bones.clear()

        # Create joint visuals
        joints_dict = skeleton_data.get("joints", {})
        hierarchy = skeleton_data.get("hierarchy", {})

        for joint_id, joint_data in joints_dict.items():
            pos_list = joint_data.get("position", [0, 0])
            if len(pos_list) >= 2:
                # Create joint visual
                joint_pos = QPointF(pos_list[0], pos_list[1])
                joint_radius = 5
                joint_item = QGraphicsEllipseItem(
                    -joint_radius, -joint_radius,
                    joint_radius * 2, joint_radius * 2
                )
                joint_item.setPos(joint_pos)
                joint_item.setBrush(QBrush(QColor(255, 165, 0)))  # Orange
                joint_item.setPen(QPen(QColor(0, 0, 0), 1))
                joint_item.setZValue(10)  # High z-value to draw on top
                self.mechanism_scene.addItem(joint_item)
                self.skeleton_joints[joint_id] = joint_item

        # Create bone visuals based on hierarchy
        for parent_id, children_ids in hierarchy.items():
            if parent_id in self.skeleton_joints:
                parent_item = self.skeleton_joints[parent_id]
                for child_id in children_ids:
                    if child_id in self.skeleton_joints:
                        child_item = self.skeleton_joints[child_id]
                        # Create bone line
                        bone_line = QGraphicsLineItem()
                        bone_line.setPen(QPen(QColor(255, 140, 0), 3))  # Orange
                        bone_line.setZValue(9)  # Below joints but above mechanism
                        bone_line.setLine(
                            parent_item.pos().x(), parent_item.pos().y(),
                            child_item.pos().x(), child_item.pos().y()
                        )
                        self.mechanism_scene.addItem(bone_line)
                        self.skeleton_bones.append(bone_line)

                        # Store bone connections for updates
                        bone_line.setData(0, parent_id)  # Parent joint ID
                        bone_line.setData(1, child_id)   # Child joint ID

    def cache_initial_skeleton(self, skeleton_data_dict: Optional[Dict]):
        """Cache the initial skeleton data dictionary (like editor tab does)"""
        if skeleton_data_dict:
            self._initial_skeleton_data_cache = skeleton_data_dict.copy()
            logging.info("MechanismDesignTab: Initial skeleton data has been cached")

            # Pass the joint_map to the mechanism_view
            if self.mechanism_view and hasattr(self.mechanism_view, "set_joint_map"):
                joint_map = self._initial_skeleton_data_cache.get("joint_map")
                self.mechanism_view.set_joint_map(joint_map)

            # Position parts at their anchor joints if parts are already loaded
            if self.current_editor_items:
                self._position_parts_at_anchor_joints()
        else:
            self._initial_skeleton_data_cache = None
            logging.info("MechanismDesignTab: Initial skeleton data cache has been cleared")
            if self.mechanism_view and hasattr(self.mechanism_view, "set_joint_map"):
                self.mechanism_view.set_joint_map(None)

    def _update_parts_selection(self):
        """Update parts selection - deprecated method (no longer needed)"""
        # This method is no longer needed since we removed parts selection combo
        # Parts are now auto-detected from paths or layers
        pass

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

                    # Position parts at their anchor joints if skeleton data is available (like editor tab)
                    anchor_joint_id = p_info.anchor_joint_id
                    if not anchor_joint_id:
                        # Import BODY_PARTS as a fallback
                        try:
                            from automataii.animate.part_definitions import BODY_PARTS
                            part_def = BODY_PARTS.get(part_name, {})
                            anchor_joint_id = part_def.get("anchor_joint")
                            if anchor_joint_id:
                                logging.info(f"MechanismDesignTab: Using fallback anchor_joint '{anchor_joint_id}' for part '{part_name}' from BODY_PARTS")
                        except ImportError:
                            logging.warning("MechanismDesignTab: Could not import BODY_PARTS for fallback anchor joint lookup")

                    if anchor_joint_id and hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
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
                                logging.info(f"MechanismDesignTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})")

                            # Check if joint is locked and update the part item
                            is_locked = joint_data.get("is_locked", False)
                            item.set_joint_locked(is_locked)
                            if is_locked:
                                logging.info(f"MechanismDesignTab: Joint '{std_joint_id}' for part '{part_name}' is locked")
                        else:
                            # Log if we couldn't find the anchor joint
                            logging.warning(f"MechanismDesignTab: Could not find anchor joint for part '{part_name}'. "
                                          f"anchor_joint_id='{anchor_joint_id}', std_joint_id='{std_joint_id}', "
                                          f"Available joints: {list(joints_dict.keys()) if joints_dict else 'No joints'}")

                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item

            # Auto-fit view when parts are loaded
            self.mechanism_view.zoom_to_fit()

            # Ensure IK manager connection is established now that parts are loaded
            if not self.connect_ik_signals():
                logging.warning("Could not connect to IK manager after parts loaded")

            logging.info(f"Mechanism tab loaded {len(self.current_editor_items)} parts for mechanism-driven animation")

    def _position_parts_at_anchor_joints(self):
        """Position parts at their anchor joints using cached skeleton data (like editor tab does)"""
        if not hasattr(self, '_initial_skeleton_data_cache') or not self._initial_skeleton_data_cache:
            logging.debug("No cached skeleton data available for positioning parts")
            return

        skeleton_data = self._initial_skeleton_data_cache
        joints_dict = skeleton_data.get("joints", {})
        joint_map = skeleton_data.get("joint_map", {})

        # Import BODY_PARTS for fallback anchor joint lookup
        try:
            from automataii.animate.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}
            logging.warning("MechanismDesignTab: Could not import BODY_PARTS for fallback anchor joint lookup")

        logging.debug(f"Positioning {len(self.current_editor_items)} parts at anchor joints")

        for part_name, part_item in self.current_editor_items.items():
            if part_name in self.parts_data:
                part_info = self.parts_data[part_name]

                # Get anchor_joint_id, with fallback to BODY_PARTS
                anchor_joint_id = part_info.anchor_joint_id
                if not anchor_joint_id and BODY_PARTS:
                    part_def = BODY_PARTS.get(part_name, {})
                    anchor_joint_id = part_def.get("anchor_joint")
                    if anchor_joint_id:
                        logging.info(f"MechanismDesignTab: Using fallback anchor_joint '{anchor_joint_id}' for part '{part_name}' from BODY_PARTS")

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
                            logging.info(f"MechanismDesignTab: Positioned part '{part_name}' at anchor joint '{std_joint_id}' position: ({joint_pos[0]:.1f}, {joint_pos[1]:.1f})")
                    else:
                        # Log if we couldn't find the anchor joint
                        logging.warning(f"MechanismDesignTab: Could not find anchor joint for part '{part_name}'. "
                                      f"anchor_joint_id='{anchor_joint_id}', std_joint_id='{std_joint_id}', "
                                      f"Available joints: {list(joints_dict.keys())}")

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

        # Clear scene
        if self.mechanism_scene is not None:
            self.mechanism_scene.clear()

        # Update UI button states
        if self.blueprint_btn is not None:
            self.blueprint_btn.setEnabled(False)
        if self.recommendation_btn is not None:
            self.recommendation_btn.setEnabled(False)
        if self.play_btn is not None:
            self.play_btn.setEnabled(False)
        if self.stop_btn is not None:
            self.stop_btn.setEnabled(False)
        if self.reset_btn is not None:
            self.reset_btn.setEnabled(False)
        if self.mechanism_layers_list is not None:
            self.mechanism_layers_list.clear()
        if self.enable_mechanisms_checkbox is not None:
            self.enable_mechanisms_checkbox.setEnabled(False)
            self.enable_mechanisms_checkbox.setChecked(False)
        if self.parametric_edit_btn is not None:
            self.parametric_edit_btn.setEnabled(False)
            self.parametric_edit_btn.setChecked(False)

        # Update animation status
        if hasattr(self, '_update_animation_status'):
            self._update_animation_status()

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

            # Also display the target path that this mechanism should follow
            if "generated_path" in layer_data and layer_data["generated_path"]:
                path = layer_data["generated_path"]
                if isinstance(path, QPainterPath) and not path.isEmpty():
                    path_item = QGraphicsPathItem(path)
                    path_item.setPen(QPen(QColor(0, 200, 0, 100), 2, Qt.PenStyle.DashLine))  # Semi-transparent green dashed line
                    path_item.setZValue(-1)  # Draw behind mechanism
                    self.mechanism_scene.addItem(path_item)
                    visual_items.append(path_item)  # Store with other visual items

            logging.info(f"MechanismDesignTab: Added {len(visual_items)} visual items for mechanism {mechanism_id}")

        # Don't auto-zoom after adding mechanism - maintain current view
        # self.mechanism_view.zoom_to_fit()

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

        # Add skeleton visualization
        self._update_skeleton_display()

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
            QMessageBox.warning(self, "Warning", "No motion paths available. Please define motion paths in the Editor tab first.")
            return

        # Auto-detect selected part from layers list or use first available path
        target_path = None
        target_part_name = None

        # Try to get currently selected layer's part
        selected_items = self.mechanism_layers_list.selectedItems()
        if selected_items:
            mechanism_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if mechanism_id in self.mechanism_layers:
                target_part_name = self.mechanism_layers[mechanism_id].get("part_name")
                if target_part_name and target_part_name in self.path_data:
                    target_path = self.path_data[target_part_name]

        # Fall back to first available path if no selection or selected part has no path
        if not target_path:
            for part_name, path in self.path_data.items():
                if not path.isEmpty():
                    target_path = path
                    target_part_name = part_name
                    break

        if not target_path:
            QMessageBox.warning(self, "Warning", "No valid motion paths found. Please define motion paths in the Editor tab first.")
            return

        # Store the target part for mechanism generation
        self.selected_part_name = target_part_name

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

    def _select_candidate(self, candidate):
        """Handles the selection of a mechanism candidate."""
        self.selected_mechanism = candidate

        # Handle both MechanismCandidate objects and dict data from recommendation dialog
        if hasattr(candidate, 'mechanism_type'):
            # MechanismCandidate object
            mechanism_type_value = candidate.mechanism_type.value
            logging.info(f"Selected candidate: {mechanism_type_value}")
        elif isinstance(candidate, dict):
            # Dict from recommendation dialog
            mechanism_type_value = candidate.get('type', 'Unknown')
            logging.info(f"Selected mechanism from dialog: {mechanism_type_value}")
        else:
            logging.error(f"Unexpected candidate type: {type(candidate)}")
            return

        # Directly generate the mechanism from the candidate
        # No need to update UI combos since they were removed
        logging.info(f"Processing selected candidate: {candidate}")
        self._generate_mechanism_from_candidate(candidate)

    def _generate_mechanism_from_candidate(self, candidate):
        """Generates a mechanism layer and visuals from a selected candidate."""
        mechanism_id = str(uuid.uuid4())[:8]

        # Handle both MechanismCandidate objects and dict data from recommendation dialog
        if hasattr(candidate, 'mechanism_type'):
            # MechanismCandidate object
            mechanism_type_value = candidate.mechanism_type.value
            params = candidate.parameters
        elif isinstance(candidate, dict):
            # Dict from recommendation dialog
            mechanism_type_value = candidate.get('type', 'Unknown')
            raw_params = candidate.get('parameters', {})

            logging.info(f"Received candidate from recommendation: type={mechanism_type_value}")
            logging.info(f"Received raw parameters: {raw_params}")

            # Convert parameters from JSON format to our internal format
            params = self._convert_json_params_to_internal(mechanism_type_value, raw_params)
            logging.info(f"Converted parameters: {params}")

            # IMPORTANT: Use the actual parameters from the recommendation
            # These parameters were calculated to match the user's path
            if not params and candidate.get('path_coordinates_np') is not None:
                # Try to extract parameters from the path data if available
                logging.warning(f"No parameters provided for {mechanism_type_value}, using defaults")
                mechanism_type_mapping = {
                    MECHANISM_TYPE_USER_DISPLAY_4_BAR: "4_bar_linkage",
                    MECHANISM_TYPE_USER_DISPLAY_3_BAR: "3_bar_linkage",
                    MECHANISM_TYPE_USER_DISPLAY_CAM: "cam",
                    "Gears (Simple Pair)": "gear",
                    "4-Bar Linkage": "4_bar_linkage",
                    "3-Bar Linkage": "3_bar_linkage",
                    "Cam Profile": "cam"
                }
                internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")
                params = self._get_initial_mechanism_params(internal_type)
        else:
            logging.error(f"Unexpected candidate type in _generate_mechanism_from_candidate: {type(candidate)}")
            return

        layer_name = f"{self.selected_part_name} - {mechanism_type_value}"

        # Convert display type to internal type for storage
        mechanism_type_mapping = {
            MECHANISM_TYPE_USER_DISPLAY_4_BAR: "4_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_3_BAR: "3_bar_linkage",
            MECHANISM_TYPE_USER_DISPLAY_CAM: "cam",
            "Gears (Simple Pair)": "gear",
            "4-Bar Linkage": "4_bar_linkage",
            "3-Bar Linkage": "3_bar_linkage",
            "Cam Profile": "cam"
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        # Get the target path and position from current part
        target_path = None
        target_position = QPointF(0, 0)
        if self.selected_part_name and self.selected_part_name in self.path_data:
            target_path = self.path_data[self.selected_part_name]
            # Get the starting position of the path as the mechanism base position
            if not target_path.isEmpty():
                element = target_path.elementAt(0)
                target_position = QPointF(element.x, element.y)

        # If part has an anchor position, use that
        if self.selected_part_name in self.current_editor_items:
            part_item = self.current_editor_items[self.selected_part_name]
            anchor_pos = part_item.get_anchor_point_scene_pos()
            if anchor_pos:
                target_position = anchor_pos

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": self.selected_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": target_path,
            "base_position": target_position,  # Store mechanism base position
            "mechanism_instance": None,  # Will store the actual mechanism object
        }
        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True

        # Create visuals and interactive handles
        self._generate_mechanism_visuals_directly(
            mechanism_id, internal_type, params
        )
        self._create_interactive_handles_for_mechanism(
            mechanism_id, internal_type, params
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
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.reset_btn.setEnabled(False)

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

        # Initialize mechanism path tracking
        self._init_mechanism_path_tracking()

        self.animation_timer.start(33)  # ~30 FPS
        logging.info("Started mechanism animation")

    @pyqtSlot()
    def _on_stop_animation(self):
        """Stop mechanism animation"""
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_btn.setEnabled(True)

        # Stop timer
        self.animation_timer.stop()

        # Clear mechanism path traces (optional - commented out to keep traces)
        # self._clear_mechanism_paths()

        # Restore original positions
        for mechanism_id, anim_data in self.animating_mechanisms.items():
            for item, original_transform in anim_data["original_transforms"].items():
                if item and item.scene():
                    item.setTransform(original_transform)

        self.animating_mechanisms.clear()
        self.animation_time = 0.0
        logging.info("Stopped mechanism animation")

    @pyqtSlot()
    def _on_reset_animation(self):
        """Reset mechanism animation to initial state"""
        # Stop animation if running
        if self.animation_timer.isActive():
            self._on_stop_animation()

        # Reset all parts to original positions
        for part_name, part_item in self.current_editor_items.items():
            if hasattr(part_item, "_original_anchor_pos"):
                part_item.set_scene_position_from_anchor(part_item._original_anchor_pos)

        # Reset mechanism visuals to initial state
        for mechanism_id, layer_data in self.mechanism_layers.items():
            mechanism_type = layer_data.get("type")
            params = layer_data.get("params", {})
            self._regenerate_mechanism_visuals(mechanism_id, mechanism_type, params)

        # Update button states
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

        # Update scene
        self.mechanism_scene.update()
        logging.info("Reset mechanism animation")

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

        # Format layer name as "Part Name - Mechanism Type"
        part_name = layer_data.get("part_name", "Unknown Part")
        mechanism_type = layer_data.get("type", "Unknown Type")

        # Convert internal type to display name
        type_display_mapping = {
            "4_bar_linkage": "4-Bar Linkage",
            "3_bar_linkage": "3-Bar Linkage",
            "cam": "Cam Profile",
            "gear": "Gear System"
        }
        display_type = type_display_mapping.get(mechanism_type, mechanism_type)

        display_name = f"{part_name} - {display_type}"

        # Add to list widget
        item = QListWidgetItem(display_name)
        item.setData(Qt.ItemDataRole.UserRole, mechanism_id)  # Store ID for reference
        self.mechanism_layers_list.addItem(item)

        # Enable controls
        if self.play_btn is not None:
            self.play_btn.setEnabled(True)
        if self.enable_mechanisms_checkbox is not None:
            self.enable_mechanisms_checkbox.setEnabled(True)
        if self.parametric_edit_btn is not None:
            self.parametric_edit_btn.setEnabled(True)

        # Update animation status
        self._update_animation_status()

        # Generate and display orange mechanism path preview
        self._generate_mechanism_path_preview(mechanism_id)

    def _generate_mechanism_path_preview(self, mechanism_id: str):
        """Generate orange path preview for a mechanism to show complete path it will draw"""
        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers[mechanism_id]
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})
        base_position = layer_data.get("base_position", QPointF(0, 0))

        # Generate complete path by sampling mechanism over full rotation
        preview_path = QPainterPath()
        num_samples = 120  # Sample points for smooth path

        first_point = True
        for i in range(num_samples + 1):  # +1 to close the path
            time = (i / num_samples) * 2 * math.pi  # Full rotation

            # Calculate mechanism output at this time
            output_pos = self._calculate_mechanism_output(mech_type, params, time, base_position)
            if output_pos:
                if first_point:
                    preview_path.moveTo(output_pos)
                    first_point = False
                else:
                    preview_path.lineTo(output_pos)

        # Create visual item for the preview path
        if not preview_path.isEmpty():
            preview_path_item = QGraphicsPathItem(preview_path)
            preview_path_item.setPen(QPen(QColor(255, 165, 0), 3, Qt.PenStyle.DashLine))  # Orange dashed line
            preview_path_item.setBrush(QBrush(Qt.GlobalColor.transparent))
            preview_path_item.setZValue(5)  # Above target paths but below skeleton

            # Store the preview item for later management
            if not hasattr(self, 'mechanism_preview_paths'):
                self.mechanism_preview_paths = {}
            self.mechanism_preview_paths[mechanism_id] = preview_path_item

            # Add to scene
            self.mechanism_scene.addItem(preview_path_item)

            logging.info(f"Generated orange path preview for mechanism {mechanism_id} with {num_samples} sample points")

    def _update_animation_status(self):
        """Update animation status label based on current mechanisms"""
        mechanism_count = len(self.mechanism_layers)
        if mechanism_count == 0:
            self.animation_status_label.setText("No mechanisms defined")
        elif mechanism_count == 1:
            self.animation_status_label.setText("1 mechanism defined")
        else:
            self.animation_status_label.setText(f"{mechanism_count} mechanisms defined")

    @pyqtSlot(dict)
    def _on_mechanism_preview_selected(self, mechanism_data: dict):
        """Handle mechanism preview selection from recommendation dialog"""
        logging.info(f"Mechanism preview selected: {mechanism_data.get('type', 'Unknown')}")
        # Could update a preview or show additional info here

    def _update_animation(self):
        """Update animation frame - mechanisms drive part motion and skeleton follows"""
        # Increment animation time with better error handling
        dt = 0.033 * self.animation_speed  # 33ms * speed
        self.animation_time += dt

        # Wrap animation time to prevent overflow (reset every 2π for circular mechanisms)
        if self.animation_time > 2 * math.pi * 10:  # Reset after 10 full rotations
            self.animation_time = self.animation_time % (2 * math.pi)

        successful_updates = 0
        failed_updates = 0

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
            base_position = layer_data.get("base_position", QPointF(0, 0))

            # Skip if no part attached
            if not attached_part:
                continue

            try:
                # Calculate mechanism output position with proper base position
                output_pos = self._calculate_mechanism_output(mech_type, params, self.animation_time, base_position)

                if output_pos is None:
                    failed_updates += 1
                    continue

                # Update mechanism visuals (links, cams, etc.)
                self._update_mechanism_visuals(mechanism_id, self.animation_time)

                # Track mechanism path if output position is valid
                if output_pos:
                    self._update_mechanism_path_tracking(mechanism_id, output_pos)

                # Move attached part to follow mechanism
                if attached_part in self.current_editor_items:
                    part_item = self.current_editor_items[attached_part]
                    # Store original position if not already stored
                    if not hasattr(part_item, "_original_anchor_pos"):
                        part_item._original_anchor_pos = part_item.get_anchor_point_scene_pos()
                        logging.debug(f"Stored original position for {attached_part}: {part_item._original_anchor_pos}")

                    # Move part directly and trigger IK to update skeleton accordingly
                    part_item.set_scene_position_from_anchor(output_pos)

                    # Trigger IK update so skeleton follows the mechanism-driven part movement
                    self._trigger_ik_update_for_part(attached_part, output_pos)
                    successful_updates += 1
                else:
                    logging.debug(f"Part {attached_part} not found in current_editor_items")
                    failed_updates += 1

            except Exception as e:
                logging.debug(f"Error updating mechanism {mechanism_id}: {e}")
                failed_updates += 1

        # Log animation health occasionally
        if self.animation_time % (math.pi) < dt:  # Every π radians (half rotation)
            if failed_updates > 0:
                logging.info(f"Animation health: {successful_updates} successful, {failed_updates} failed updates")

        # Update scene
        self.mechanism_scene.update()

    def _update_skeleton_visuals_directly(self, part_movements: Dict[str, QPointF]):
        """Legacy function - now using individual IK updates instead"""
        pass  # This function is no longer used

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, base_position: QPointF = None) -> Optional[QPointF]:
        """Calculate the output position of a mechanism at given time using proper kinematics"""
        if base_position is None:
            base_position = QPointF(0, 0)

        logging.debug(f"Calculating output for {mech_type} at time {time:.3f}, base_position: ({base_position.x():.1f}, {base_position.y():.1f})")

        # Use the MechanismSimulator for accurate kinematics
        try:
            if mech_type == "cam":
                # Cam parameters for simulator: [base_radius, rise, offset]
                base_radius = params.get("base_radius", 50)
                rise = params.get("rise", 30)
                offset = params.get("offset", 0)

                # Validate cam parameters
                if base_radius <= 0 or rise <= 0:
                    logging.warning(f"Invalid cam parameters: base_radius={base_radius}, rise={rise}")
                    return None

                sim_params = np.array([base_radius, rise, offset])
                points = self.mechanism_simulator._simulate_cam(sim_params, np.array([time]))

                if len(points) > 0:
                    # Cam follower moves vertically, add base position
                    return QPointF(base_position.x() + points[0][0], base_position.y() - points[0][1])

            elif mech_type == "4_bar_linkage":
                # Extract from our parameter format
                p0_local = params.get("ground_pivot_1", QPointF(-100, 0))
                p3_local = params.get("ground_pivot_2", QPointF(100, 0))
                crank_length = params.get("crank_length", 80.0)
                coupler_length = params.get("coupler_length", 150.0)
                rocker_length = params.get("rocker_length", 100.0)

                # The ground pivots from params are local to the base_position
                p0_scene = base_position + p0_local
                p3_scene = base_position + p3_local

                # Calculate ground link length and angle for transformation
                dx = p3_scene.x() - p0_scene.x()
                dy = p3_scene.y() - p0_scene.y()
                l1 = math.sqrt(dx**2 + dy**2)
                ground_angle = math.atan2(dy, dx)

                # Validate 4-bar parameters (Grashof criterion and basic feasibility)
                if crank_length <= 0 or coupler_length <= 0 or rocker_length <= 0 or l1 <= 0:
                    logging.warning(f"Invalid 4-bar link lengths: crank={crank_length}, coupler={coupler_length}, rocker={rocker_length}, ground={l1}")
                    return self._fallback_4bar_calculation(time, params, base_position)

                # Check Grashof criterion to ensure the mechanism can rotate
                lengths = [l1, crank_length, coupler_length, rocker_length]
                lengths.sort()
                if lengths[0] + lengths[3] > lengths[1] + lengths[2]:
                    # Non-Grashof linkage - may not have continuous rotation
                    logging.debug(f"Non-Grashof 4-bar linkage detected at time {time:.3f}")

                # Coupler point location relative to the coupler link
                p_x = params.get("coupler_point_x", coupler_length * 0.7)
                p_y = params.get("coupler_point_y", 0)

                sim_params = np.array([l1, crank_length, coupler_length, rocker_length,
                                     p_x, p_y, 0, 1])  # theta0=0, omega=1

                # Simulate single point
                points = self.mechanism_simulator._simulate_4bar(sim_params, np.array([time]))

                if len(points) > 0 and not (np.isnan(points[0][0]) or np.isnan(points[0][1])):
                    # Transform simulated point to scene coordinates.
                    # The simulator returns points relative to the first ground pivot (p0),
                    # assuming the ground link lies on the X-axis.
                    sim_x, sim_y = points[0][0], points[0][1]

                    # Rotate the point by the ground link's angle
                    cos_angle = math.cos(ground_angle)
                    sin_angle = math.sin(ground_angle)
                    rotated_x = sim_x * cos_angle - sim_y * sin_angle
                    rotated_y = sim_x * sin_angle + sim_y * cos_angle

                    # Translate to the scene position of the first ground pivot
                    output_scene = QPointF(p0_scene.x() + rotated_x,
                                         p0_scene.y() + rotated_y)

                    logging.debug(f"4-bar sim success: time={time:.3f}, output={output_scene}")
                    return output_scene
                else:
                    # Simulation failed, try fallback
                    logging.warning(f"4-bar simulation failed at time {time:.3f}, points={points if len(points) > 0 else 'empty'}")
                    logging.warning(f"4-bar params: l1={l1:.1f}, crank={crank_length:.1f}, coupler={coupler_length:.1f}, rocker={rocker_length:.1f}")
                    return self._fallback_4bar_calculation(time, params, base_position)

            elif mech_type == "3_bar_linkage":
                # 3-bar parameters: [l1, l2, l3, theta0, omega]
                ground_pivot = params.get("ground_pivot", QPointF(0, 0))
                link1_length = params.get("link1_length", 100.0)
                link2_length = params.get("link2_length", 120.0)

                # Validate 3-bar parameters
                if link1_length <= 0 or link2_length <= 0:
                    logging.warning(f"Invalid 3-bar parameters: link1={link1_length}, link2={link2_length}")
                    return None

                sim_params = np.array([link1_length, link2_length, 0, 0, 1])  # l3=0, theta0=0, omega=1
                points = self.mechanism_simulator._simulate_3bar(sim_params, np.array([time]))

                if len(points) > 0:
                    return QPointF(base_position.x() + ground_pivot.x() + points[0][0],
                                 base_position.y() + ground_pivot.y() + points[0][1])

        except Exception as e:
            logging.debug(f"Exception in mechanism calculation: {e}")
            # Fall back to simplified calculation
            if mech_type == "4_bar_linkage":
                return self._fallback_4bar_calculation(time, params, base_position)

        logging.debug(f"No output calculated for mechanism type: {mech_type}")
        return None

    def _fallback_4bar_calculation(self, time: float, params: dict, base_position: QPointF) -> QPointF:
        """Fallback calculation for 4-bar linkage when simulation fails"""
        crank_angle_relative = time
        crank_length = params.get("crank_length", 80)

        p0_local = params.get("ground_pivot_1", QPointF(-100, 0))
        p3_local = params.get("ground_pivot_2", QPointF(100, 0))

        p0_scene = base_position + p0_local
        p3_scene = base_position + p3_local

        # Calculate ground link angle
        dx = p3_scene.x() - p0_scene.x()
        dy = p3_scene.y() - p0_scene.y()
        ground_angle = math.atan2(dy, dx)

        # Total angle is ground link angle + relative crank angle
        total_angle = ground_angle + crank_angle_relative

        # Simple circular motion fallback around the first ground pivot
        crank_end = QPointF(
            p0_scene.x() + crank_length * math.cos(total_angle),
            p0_scene.y() + crank_length * math.sin(total_angle)
        )
        logging.debug(f"4-bar fallback calculation result: {crank_end}")
        return crank_end

    def _trigger_ik_update_for_part(self, part_name: str, new_position: QPointF):
        """Trigger IK update for a single part movement to make skeleton follow"""
        # Get part info to find its anchor joint
        if part_name not in self.parts_data:
            return

        part_info = self.parts_data[part_name]
        anchor_joint_id = part_info.anchor_joint_id

        if not anchor_joint_id:
            return

        # Directly update the skeleton joint position for this part's anchor
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            skeleton_manager = self.main_window.skeleton_manager
            if skeleton_manager.standardized_model:
                try:
                    # Find the standardized joint ID
                    if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                        joint_map = self._initial_skeleton_data_cache.get("joint_map", {})

                        # Find standardized joint ID from original anchor_joint_id
                        std_joint_id = None
                        for orig_name, std_id in joint_map.items():
                            if orig_name == anchor_joint_id:
                                std_joint_id = std_id
                                break

                        if std_joint_id:
                            # Update joint position in skeleton model
                            joints_dict = skeleton_manager.standardized_model.joints
                            if std_joint_id in joints_dict:
                                joint_model = joints_dict[std_joint_id]
                                joint_model.position = [new_position.x(), new_position.y()]

                                # Emit skeleton update to refresh visuals
                                updated_skeleton_data = skeleton_manager.standardized_model.model_dump()
                                self.on_skeleton_updated(updated_skeleton_data)

                                logging.debug(f"Updated skeleton joint '{std_joint_id}' to position {new_position} for part '{part_name}'")

                except Exception as e:
                    logging.debug(f"Error updating skeleton joint for part {part_name}: {e}")

        # Also create a motion path for the current position (for consistency with editor tab)
        try:
            motion_qpath = QPainterPath()
            motion_qpath.moveTo(new_position)

            # Update the part's motion path in the project data manager
            if hasattr(self.main_window, 'project_data_manager'):
                current_parts = self.main_window.project_data_manager.get_current_parts_data()
                if current_parts and part_name in current_parts:
                    current_parts[part_name].motion_path = motion_qpath
                    logging.debug(f"Updated motion_path in ProjectDataManager for '{part_name}'")

            # Update the CharacterPartItem's motion path
            if part_name in self.current_editor_items:
                char_part_item = self.current_editor_items[part_name]
                char_part_item.set_motion_path(motion_qpath)
                logging.debug(f"Set motion path on CharacterPartItem for '{part_name}'")

        except Exception as e:
            logging.debug(f"Error setting motion path for part {part_name}: {e}")

    def _scale_mechanism_output_to_target(self, mechanism_output: QPointF, part_name: str, base_position: QPointF) -> QPointF:
        """Scale mechanism output to match target path scale"""
        if not mechanism_output or not part_name:
            return mechanism_output

        # Get target path for this part
        if part_name not in self.path_data:
            return mechanism_output

        target_path = self.path_data[part_name]
        if target_path.isEmpty():
            return mechanism_output

        # Get target path bounds
        target_bounds = target_path.boundingRect()
        if target_bounds.isEmpty():
            return mechanism_output

        # Calculate mechanism output relative to base position
        mechanism_relative = QPointF(
            mechanism_output.x() - base_position.x(),
            mechanism_output.y() - base_position.y()
        )

        # Get expected mechanism path size (this should be calculated from mechanism parameters)
        # For now, use a heuristic based on mechanism type
        expected_mechanism_size = 200.0  # Default expected radius for 4-bar linkage

        # Calculate target path size
        target_size = max(target_bounds.width(), target_bounds.height())

        # Calculate scale factor
        if expected_mechanism_size > 0:
            scale_factor = target_size / expected_mechanism_size
        else:
            scale_factor = 1.0

        # Apply scale and return to scene coordinates
        scaled_output = QPointF(
            base_position.x() + mechanism_relative.x() * scale_factor,
            base_position.y() + mechanism_relative.y() * scale_factor
        )

        logging.debug(f"Scaling mechanism output: target_size={target_size:.1f}, scale={scale_factor:.3f}")
        return scaled_output

    def showEvent(self, event):
        """Called when the tab is shown - fit view to content"""
        super().showEvent(event)
        # Fit view when tab is shown (like editor tab)
        if self.mechanism_view:
            self.mechanism_view.zoom_to_fit()
            logging.info("MechanismDesignTab: Fitted view on tab show")

    def _update_skeleton_display(self):
        """Update skeleton visualization in mechanism scene (manual approach)"""
        # Clear existing skeleton items
        for item in self.skeleton_joint_items.values():
            if item.scene():
                self.mechanism_scene.removeItem(item)
        for item in self.skeleton_bone_items.values():
            if item.scene():
                self.mechanism_scene.removeItem(item)
        self.skeleton_joint_items.clear()
        self.skeleton_bone_items.clear()

        # Get skeleton data from main window
        if not hasattr(self.main_window, 'skeleton_manager') or not self.main_window.skeleton_manager:
            return

        skeleton_manager = self.main_window.skeleton_manager
        if not skeleton_manager.standardized_model:
            return

        try:
            # Get skeleton data
            skeleton_data = skeleton_manager.standardized_model.model_dump()
            joints_dict = skeleton_data.get("joints", {})
            hierarchy = skeleton_data.get("hierarchy", {})

            # Draw joints
            for joint_id, joint_data in joints_dict.items():
                position = joint_data.get("position", [0, 0])
                if len(position) >= 2:
                    joint_pos = QPointF(position[0], position[1])

                    # Create joint visual
                    joint_item = QGraphicsEllipseItem(-3, -3, 6, 6)
                    joint_item.setPos(joint_pos)
                    joint_item.setPen(QPen(QColor(255, 0, 0), 1))  # Red joints
                    joint_item.setBrush(QBrush(QColor(255, 0, 0, 100)))
                    joint_item.setZValue(10)  # Draw above everything else

                    self.mechanism_scene.addItem(joint_item)
                    self.skeleton_joint_items[joint_id] = joint_item

            # Draw bones using hierarchy (parent -> children relationships)
            for parent_id, child_ids in hierarchy.items():
                if parent_id in joints_dict:
                    parent_pos_data = joints_dict[parent_id].get("position", [0, 0])
                    if len(parent_pos_data) >= 2:
                        parent_pos = QPointF(parent_pos_data[0], parent_pos_data[1])

                        for child_id in child_ids:
                            if child_id in joints_dict:
                                child_pos_data = joints_dict[child_id].get("position", [0, 0])
                                if len(child_pos_data) >= 2:
                                    child_pos = QPointF(child_pos_data[0], child_pos_data[1])

                                    # Create bone visual (line from parent to child)
                                    bone_key = f"{parent_id}_to_{child_id}"
                                    bone_item = QGraphicsLineItem(parent_pos.x(), parent_pos.y(),
                                                                child_pos.x(), child_pos.y())
                                    bone_item.setPen(QPen(QColor(100, 100, 255), 2))  # Blue bones
                                    bone_item.setZValue(5)  # Draw below joints but above other items

                                    self.mechanism_scene.addItem(bone_item)
                                    self.skeleton_bone_items[bone_key] = bone_item

            logging.debug(f"MechanismDesignTab: Displayed skeleton with {len(self.skeleton_joint_items)} joints and {len(self.skeleton_bone_items)} bones")

        except Exception as e:
            logging.debug(f"MechanismDesignTab: Error updating skeleton display: {e}")

    def _init_mechanism_path_tracking(self):
        """Initialize mechanism path tracking for animation"""
        for mechanism_id in self.mechanism_layers:
            if mechanism_id not in self.mechanism_path_points:
                self.mechanism_path_points[mechanism_id] = []

    def _update_mechanism_path_tracking(self, mechanism_id: str, output_pos: QPointF):
        """Add current mechanism output position to path tracking"""
        if mechanism_id not in self.mechanism_path_points:
            self.mechanism_path_points[mechanism_id] = []

        # Add current position
        self.mechanism_path_points[mechanism_id].append(output_pos)

        # Limit path history to prevent memory issues
        max_points = 500
        if len(self.mechanism_path_points[mechanism_id]) > max_points:
            self.mechanism_path_points[mechanism_id] = self.mechanism_path_points[mechanism_id][-max_points:]

        # Update visual path
        self._update_mechanism_path_visual(mechanism_id)

    def _update_mechanism_path_visual(self, mechanism_id: str):
        """Update the visual representation of mechanism path"""
        if mechanism_id not in self.mechanism_path_points:
            return

        points = self.mechanism_path_points[mechanism_id]
        if len(points) < 2:
            return

        # Remove existing path visual
        if mechanism_id in self.mechanism_path_items:
            self.mechanism_scene.removeItem(self.mechanism_path_items[mechanism_id])

        # Create new path
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)

        # Create path visual
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(QColor(255, 165, 0), 2))  # Orange for mechanism paths
        path_item.setZValue(2)  # Draw above target paths but below skeleton

        self.mechanism_scene.addItem(path_item)
        self.mechanism_path_items[mechanism_id] = path_item

    def _clear_mechanism_paths(self):
        """Clear all mechanism path traces"""
        for path_item in self.mechanism_path_items.values():
            self.mechanism_scene.removeItem(path_item)
        self.mechanism_path_items.clear()
        self.mechanism_path_points.clear()

    def _toggle_debug_display(self, checked: bool):
        """Toggle coordinate system debug display"""
        self.show_debug = checked
        if checked:
            self._show_debug_info()
        else:
            self._hide_debug_info()

    def _show_debug_info(self):
        """Show coordinate system debug information"""
        self._hide_debug_info()  # Clear existing debug items first

        # Show coordinate axes at origin
        origin = QPointF(0, 0)
        axis_length = 100

        # X-axis (red)
        x_axis = QGraphicsLineItem(origin.x(), origin.y(), origin.x() + axis_length, origin.y())
        x_axis.setPen(QPen(QColor(255, 0, 0), 3))
        x_axis.setZValue(15)
        self.mechanism_scene.addItem(x_axis)
        self.debug_items.append(x_axis)

        # Y-axis (green)
        y_axis = QGraphicsLineItem(origin.x(), origin.y(), origin.x(), origin.y() + axis_length)
        y_axis.setPen(QPen(QColor(0, 255, 0), 3))
        y_axis.setZValue(15)
        self.mechanism_scene.addItem(y_axis)
        self.debug_items.append(y_axis)

        # Show mechanism base positions
        for mechanism_id, layer_data in self.mechanism_layers.items():
            base_position = layer_data.get("base_position", QPointF(0, 0))
            if base_position:
                # Base position marker (blue circle)
                marker = QGraphicsEllipseItem(-5, -5, 10, 10)
                marker.setPos(base_position)
                marker.setPen(QPen(QColor(0, 0, 255), 2))
                marker.setBrush(QBrush(QColor(0, 0, 255, 100)))
                marker.setZValue(15)
                self.mechanism_scene.addItem(marker)
                self.debug_items.append(marker)

                # Base position label
                label = QGraphicsTextItem(f"{mechanism_id[:8]}\n({base_position.x():.0f}, {base_position.y():.0f})")
                label.setPos(base_position.x() + 10, base_position.y() - 10)
                label.setDefaultTextColor(QColor(0, 0, 255))
                label.setZValue(15)
                self.mechanism_scene.addItem(label)
                self.debug_items.append(label)

        # Show target path start points and bounding boxes
        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                start_element = path.elementAt(0)
                start_pos = QPointF(start_element.x, start_element.y)

                # Target path start marker (magenta square)
                marker = QGraphicsRectItem(-4, -4, 8, 8)
                marker.setPos(start_pos)
                marker.setPen(QPen(QColor(255, 0, 255), 2))
                marker.setBrush(QBrush(QColor(255, 0, 255, 100)))
                marker.setZValue(15)
                self.mechanism_scene.addItem(marker)
                self.debug_items.append(marker)

                # Target path start label
                label = QGraphicsTextItem(f"{part_name}\n({start_pos.x():.0f}, {start_pos.y():.0f})")
                label.setPos(start_pos.x() + 10, start_pos.y() - 25)
                label.setDefaultTextColor(QColor(255, 0, 255))
                label.setZValue(15)
                self.mechanism_scene.addItem(label)
                self.debug_items.append(label)

                # Show bounding box
                bounds = path.boundingRect()
                bbox_item = QGraphicsRectItem(bounds)
                bbox_item.setPen(QPen(QColor(255, 255, 0), 1, Qt.PenStyle.DashLine))  # Yellow dashed
                bbox_item.setZValue(14)
                self.mechanism_scene.addItem(bbox_item)
                self.debug_items.append(bbox_item)

                # Bounding box info
                bbox_label = QGraphicsTextItem(f"W: {bounds.width():.0f}\nH: {bounds.height():.0f}")
                bbox_label.setPos(bounds.topRight())
                bbox_label.setDefaultTextColor(QColor(255, 255, 0))
                bbox_label.setZValue(15)
                self.mechanism_scene.addItem(bbox_label)
                self.debug_items.append(bbox_label)

    def _hide_debug_info(self):
        """Hide coordinate system debug information"""
        for item in self.debug_items:
            self.mechanism_scene.removeItem(item)
        self.debug_items.clear()

    def _update_mechanism_visuals(self, mechanism_id: str, time: float):
        """Update visual representation of mechanism during animation"""
        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers[mechanism_id]
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})
        base_position = layer_data.get("base_position", QPointF(0, 0))
        visual_items = layer_data.get("visual_items", [])

        if mech_type == "4_bar_linkage":
            # Update 4-bar linkage visuals
            ground_pivot_1 = params.get("ground_pivot_1", QPointF(-100, 0))
            ground_pivot_2 = params.get("ground_pivot_2", QPointF(100, 0))
            crank_length = params.get("crank_length", 80.0)
            coupler_length = params.get("coupler_length", 150.0)
            rocker_length = params.get("rocker_length", 100.0)

            # Calculate current positions using forward kinematics
            crank_angle = time
            p0 = QPointF(base_position.x() + ground_pivot_1.x(),
                        base_position.y() + ground_pivot_1.y())
            p3 = QPointF(base_position.x() + ground_pivot_2.x(),
                        base_position.y() + ground_pivot_2.y())

            # Calculate crank end position
            p1 = QPointF(p0.x() + crank_length * math.cos(crank_angle),
                        p0.y() + crank_length * math.sin(crank_angle))

            # Solve for rocker position (p2) using cosine law
            # This is simplified - should use full 4-bar kinematics
            d = math.sqrt((p3.x() - p1.x())**2 + (p3.y() - p1.y())**2)

            if d <= coupler_length + rocker_length and d >= abs(coupler_length - rocker_length):
                # Valid configuration - calculate p2
                # Use cosine law to find angles
                cos_gamma = (d**2 + coupler_length**2 - rocker_length**2) / (2 * d * coupler_length)
                cos_gamma = max(-1, min(1, cos_gamma))  # Clamp to valid range
                gamma = math.acos(cos_gamma)

                phi = math.atan2(p3.y() - p1.y(), p3.x() - p1.x())

                # Two possible solutions, choose one
                p2 = QPointF(p1.x() + coupler_length * math.cos(phi + gamma),
                           p1.y() + coupler_length * math.sin(phi + gamma))

                # Update visual items (links)
                # Assuming visual_items contains [crank_line, coupler_line, rocker_line, ...pivots]
                if len(visual_items) >= 3:
                    # Update crank
                    crank_path = QPainterPath()
                    crank_path.moveTo(p0)
                    crank_path.lineTo(p1)
                    visual_items[0].setPath(crank_path)

                    # Update coupler
                    coupler_path = QPainterPath()
                    coupler_path.moveTo(p1)
                    coupler_path.lineTo(p2)
                    visual_items[1].setPath(coupler_path)

                    # Update rocker
                    rocker_path = QPainterPath()
                    rocker_path.moveTo(p2)
                    rocker_path.lineTo(p3)
                    visual_items[2].setPath(rocker_path)

                    # Update pivot positions if they exist
                    if len(visual_items) >= 7:  # 3 links + 4 pivots
                        visual_items[3].setPos(p0)  # Ground pivot 1
                        visual_items[4].setPos(p1)  # Crank-coupler joint
                        visual_items[5].setPos(p2)  # Coupler-rocker joint
                        visual_items[6].setPos(p3)  # Ground pivot 2

        elif mech_type == "cam":
            # Update cam rotation
            center = params.get("center", QPointF(0, 0))
            base_radius = params.get("base_radius", 50.0)
            rise = params.get("rise", 30.0)

            # Rotate cam body
            if len(visual_items) >= 1:
                cam_body = visual_items[0]
                if isinstance(cam_body, QGraphicsEllipseItem):
                    # Apply rotation transform
                    transform = QTransform()
                    transform.translate(base_position.x() + center.x(),
                                      base_position.y() + center.y())
                    transform.rotate(math.degrees(time))
                    transform.translate(-(base_position.x() + center.x()),
                                      -(base_position.y() + center.y()))
                    cam_body.setTransform(transform)

            # Update follower position
            if len(visual_items) >= 2:
                follower = visual_items[1]
                if isinstance(follower, QGraphicsRectItem):
                    # Calculate follower height based on cam rotation
                    radius = base_radius + rise * (1 + math.sin(time)) / 2
                    follower_width = follower.rect().width()
                    follower_height = follower.rect().height()
                    follower_x = base_position.x() + center.x() - follower_width / 2
                    follower_y = base_position.y() + center.y() - radius - follower_height
                    follower.setPos(follower_x, follower_y)

        elif mech_type == "3_bar_linkage":
            # Update 3-bar linkage visuals
            ground_pivot = params.get("ground_pivot", QPointF(0, 0))
            link1_length = params.get("link1_length", 100.0)
            link2_length = params.get("link2_length", 120.0)

            angle1 = time
            angle2 = angle1 + math.pi/3  # Simplified - should calculate properly

            p0 = QPointF(base_position.x() + ground_pivot.x(),
                        base_position.y() + ground_pivot.y())
            p1 = QPointF(p0.x() + link1_length * math.cos(angle1),
                        p0.y() + link1_length * math.sin(angle1))
            p2 = QPointF(p1.x() + link2_length * math.cos(angle2),
                        p1.y() + link2_length * math.sin(angle2))

            # Update visual items
            if len(visual_items) >= 2:
                # Update link 1
                link1_path = QPainterPath()
                link1_path.moveTo(p0)
                link1_path.lineTo(p1)
                visual_items[0].setPath(link1_path)

                # Update link 2
                link2_path = QPainterPath()
                link2_path.moveTo(p1)
                link2_path.lineTo(p2)
                visual_items[1].setPath(link2_path)

                # Update pivots if they exist
                if len(visual_items) >= 5:  # 2 links + 3 pivots
                    visual_items[2].setPos(p0)  # Ground pivot
                    visual_items[3].setPos(p1)  # Joint 1
                    visual_items[4].setPos(p2)  # End effector

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

    def _convert_json_params_to_internal(self, mechanism_type: str, json_params: dict) -> dict:
        """Convert parameters from JSON format to our internal format"""
        if "4-bar" in mechanism_type or "4_bar" in mechanism_type:
            # JSON format: L1, L2, L3, L4_ground
            # Our format: ground_pivot_1, ground_pivot_2, crank_length, coupler_length, rocker_length
            # L1 = ground link length
            # L2 = crank length
            # L3 = coupler length
            # L4_ground = rocker length

            L1 = json_params.get('L1', 60)
            L2 = json_params.get('L2', 40)  # crank
            L3 = json_params.get('L3', 50)  # coupler
            L4 = json_params.get('L4_ground', json_params.get('L4', 60))  # rocker

            # Get coupler point location
            lc_ratio = json_params.get('lc_ratio', 0.5)  # Default to middle
            beta_coupler = json_params.get('beta_coupler', 0)  # Angle offset in degrees

            # Calculate coupler point position
            # lc_ratio is the distance along coupler from crank joint
            # beta_coupler is the angle offset from the coupler line
            import math
            coupler_point_x = L3 * lc_ratio
            coupler_point_y = L3 * lc_ratio * math.tan(math.radians(beta_coupler))

            # Place ground pivots symmetrically around origin
            return {
                "ground_pivot_1": QPointF(-L1/2, 0),
                "ground_pivot_2": QPointF(L1/2, 0),
                "crank_length": L2,
                "coupler_length": L3,
                "rocker_length": L4,
                # Coupler point position on coupler link
                "coupler_point_x": coupler_point_x,
                "coupler_point_y": coupler_point_y,
                "lc_ratio": lc_ratio,
                "beta_coupler": beta_coupler
            }
        elif "cam" in mechanism_type.lower():
            # Cam parameters are more straightforward
            return {
                "center": QPointF(0, 0),
                "base_radius": json_params.get('base_radius', 50),
                "rise": json_params.get('rise', 30),
                "rise_angle": json_params.get('rise_angle', 90),
                "fall_angle": json_params.get('fall_angle', 90),
                "profile_type": json_params.get('profile_type', 'cycloidal')
            }
        elif "3-bar" in mechanism_type or "3_bar" in mechanism_type:
            return {
                "ground_pivot": QPointF(0, 0),
                "link1_length": json_params.get('L1', 100),
                "link2_length": json_params.get('L2', 120)
            }
        else:
            # Return raw params if type not recognized
            return json_params

    def _get_initial_mechanism_params(self, mechanism_type: str) -> dict:
        """Get initial parameters for a mechanism type, scaled to target path"""
        # Get target path bounds to scale parameters appropriately
        target_bounds = QRectF()
        if self.selected_part_name and self.selected_part_name in self.path_data:
            target_path = self.path_data[self.selected_part_name]
            if not target_path.isEmpty():
                target_bounds = target_path.boundingRect()

        # If no valid bounds, use default scale
        if target_bounds.isEmpty():
            scale_factor = 1.0
            is_vertical = False
        else:
            # Use the larger dimension for scaling
            path_width = target_bounds.width()
            path_height = target_bounds.height()
            path_size = max(path_width, path_height)
            scale_factor = path_size / 200.0  # Normalize to a base size of 200

            # Determine if path is primarily vertical
            is_vertical = path_height > path_width * 1.5

        logging.info(f"Scaling mechanism params by factor: {scale_factor:.2f} based on path bounds: {target_bounds}")
        logging.info(f"Path orientation: {'vertical' if is_vertical else 'horizontal'}")

        if mechanism_type == "4_bar_linkage":
            if is_vertical:
                # Rotate mechanism 90 degrees for vertical paths
                return {
                    "ground_pivot_1": QPointF(0, -100 * scale_factor),
                    "ground_pivot_2": QPointF(0, 100 * scale_factor),
                    "crank_length": 80.0 * scale_factor,
                    "coupler_length": 150.0 * scale_factor,
                    "rocker_length": 100.0 * scale_factor
                }
            else:
                return {
                    "ground_pivot_1": QPointF(-100 * scale_factor, 0),
                    "ground_pivot_2": QPointF(100 * scale_factor, 0),
                    "crank_length": 80.0 * scale_factor,
                    "coupler_length": 150.0 * scale_factor,
                    "rocker_length": 100.0 * scale_factor
                }
        elif mechanism_type == "3_bar_linkage":
            return {
                "ground_pivot": QPointF(0, 0),
                "link1_length": 100.0 * scale_factor,
                "link2_length": 120.0 * scale_factor
            }
        elif mechanism_type == "cam":
            # For cam, use half the path height as rise
            rise = target_bounds.height() / 2 if not target_bounds.isEmpty() else 30.0
            return {
                "center": QPointF(0, 0),
                "base_radius": 50.0 * scale_factor,
                "rise": rise,
                "dwell_angle": 90.0,
                "profile_type": "cycloidal"
            }
        else:
            return {}

    def _create_4bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of 4-bar linkage"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get base position from mechanism data
        base_position = self.mechanism_layers.get(mechanism_data.get("mechanism_id", ""), {}).get("base_position", QPointF(0, 0))

        # Get pivot points and link parameters
        p0_local = params.get("ground_pivot_1", QPointF(-100, 0))
        p3_local = params.get("ground_pivot_2", QPointF(100, 0))
        crank_length = params.get("crank_length", 80.0)
        coupler_length = params.get("coupler_length", 150.0)
        rocker_length = params.get("rocker_length", 100.0)

        # Transform to scene coordinates
        p0 = QPointF(base_position.x() + p0_local.x(), base_position.y() + p0_local.y())
        p3 = QPointF(base_position.x() + p3_local.x(), base_position.y() + p3_local.y())

        # Calculate initial positions (angle = 0)
        angle = 0.0
        p1 = QPointF(p0.x() + crank_length * math.cos(angle),
                    p0.y() + crank_length * math.sin(angle))

        # Use proper 4-bar kinematics for initial p2 position
        d = math.sqrt((p3.x() - p1.x())**2 + (p3.y() - p1.y())**2)

        if d <= coupler_length + rocker_length and d >= abs(coupler_length - rocker_length):
            # Valid configuration
            cos_gamma = (d**2 + coupler_length**2 - rocker_length**2) / (2 * d * coupler_length)
            cos_gamma = max(-1, min(1, cos_gamma))
            gamma = math.acos(cos_gamma)
            phi = math.atan2(p3.y() - p1.y(), p3.x() - p1.x())
            p2 = QPointF(p1.x() + coupler_length * math.cos(phi + gamma),
                       p1.y() + coupler_length * math.sin(phi + gamma))
        else:
            # Invalid configuration - use simplified position
            p2 = QPointF(p1.x() + coupler_length * math.cos(angle + math.pi/4),
                       p1.y() + coupler_length * math.sin(angle + math.pi/4))

        # Create links as lines with proper styling
        # Crank (input link)
        crank_line = QGraphicsPathItem()
        crank_path = QPainterPath()
        crank_path.moveTo(p0)
        crank_path.lineTo(p1)
        crank_line.setPath(crank_path)
        crank_line.setPen(QPen(QColor(52, 152, 219), 6))  # Blue
        crank_line.setZValue(1)
        visual_items.append(crank_line)

        # Coupler
        coupler_line = QGraphicsPathItem()
        coupler_path = QPainterPath()
        coupler_path.moveTo(p1)
        coupler_path.lineTo(p2)
        coupler_line.setPath(coupler_path)
        coupler_line.setPen(QPen(QColor(231, 76, 60), 6))  # Red
        coupler_line.setZValue(1)
        visual_items.append(coupler_line)

        # Rocker (output link)
        rocker_line = QGraphicsPathItem()
        rocker_path = QPainterPath()
        rocker_path.moveTo(p2)
        rocker_path.lineTo(p3)
        rocker_line.setPath(rocker_path)
        rocker_line.setPen(QPen(QColor(46, 204, 113), 6))  # Green
        rocker_line.setZValue(1)
        visual_items.append(rocker_line)

        # Create pivot points with better styling
        pivot_radius = 8
        for i, (point, color) in enumerate([
            (p0, QColor(52, 73, 94)),      # Dark blue-gray for ground pivots
            (p1, QColor(41, 128, 185)),    # Blue for crank joint
            (p2, QColor(192, 57, 43)),     # Red for coupler joint
            (p3, QColor(52, 73, 94))       # Dark blue-gray for ground pivots
        ]):
            pivot = QGraphicsEllipseItem(-pivot_radius, -pivot_radius, pivot_radius*2, pivot_radius*2)
            pivot.setPos(point)
            pivot.setBrush(QBrush(color))
            pivot.setPen(QPen(QColor(0, 0, 0), 2))
            pivot.setZValue(2)  # Draw pivots on top
            visual_items.append(pivot)

        # Add ground symbols for fixed pivots
        ground_size = 15
        for ground_pivot in [p0, p3]:
            # Create small triangle or hash marks to indicate ground
            ground_path = QPainterPath()
            ground_path.moveTo(ground_pivot.x() - ground_size, ground_pivot.y() + pivot_radius)
            ground_path.lineTo(ground_pivot.x() + ground_size, ground_pivot.y() + pivot_radius)
            for i in range(3):
                x = ground_pivot.x() - ground_size + (i+1) * ground_size/2
                ground_path.moveTo(x, ground_pivot.y() + pivot_radius)
                ground_path.lineTo(x - 5, ground_pivot.y() + pivot_radius + 8)
            ground_item = QGraphicsPathItem(ground_path)
            ground_item.setPen(QPen(QColor(127, 140, 141), 2))
            ground_item.setZValue(0)
            visual_items.append(ground_item)

        return visual_items

    def _create_3bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of 3-bar linkage"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get base position from mechanism data
        base_position = self.mechanism_layers.get(mechanism_data.get("mechanism_id", ""), {}).get("base_position", QPointF(0, 0))

        # Get parameters
        ground_pivot_local = params.get("ground_pivot", QPointF(0, 0))
        link1_length = params.get("link1_length", 100.0)
        link2_length = params.get("link2_length", 120.0)

        # Transform to scene coordinates
        ground_pivot = QPointF(base_position.x() + ground_pivot_local.x(),
                             base_position.y() + ground_pivot_local.y())

        # Calculate initial positions
        angle1 = 0.0
        angle2 = math.pi/3

        p1 = QPointF(ground_pivot.x() + link1_length * math.cos(angle1),
                    ground_pivot.y() + link1_length * math.sin(angle1))
        p2 = QPointF(p1.x() + link2_length * math.cos(angle2),
                    p1.y() + link2_length * math.sin(angle2))

        # Create links with better styling
        link1_line = QGraphicsPathItem()
        link1_path = QPainterPath()
        link1_path.moveTo(ground_pivot)
        link1_path.lineTo(p1)
        link1_line.setPath(link1_path)
        link1_line.setPen(QPen(QColor(52, 152, 219), 6))  # Blue
        link1_line.setZValue(1)
        visual_items.append(link1_line)

        link2_line = QGraphicsPathItem()
        link2_path = QPainterPath()
        link2_path.moveTo(p1)
        link2_path.lineTo(p2)
        link2_line.setPath(link2_path)
        link2_line.setPen(QPen(QColor(231, 76, 60), 6))  # Red
        link2_line.setZValue(1)
        visual_items.append(link2_line)

        # Create pivots with better styling
        pivot_radius = 8
        for i, (point, color) in enumerate([
            (ground_pivot, QColor(52, 73, 94)),  # Dark blue-gray for ground pivot
            (p1, QColor(41, 128, 185)),          # Blue for joint
            (p2, QColor(192, 57, 43))            # Red for end effector
        ]):
            pivot = QGraphicsEllipseItem(-pivot_radius, -pivot_radius, pivot_radius*2, pivot_radius*2)
            pivot.setPos(point)
            pivot.setBrush(QBrush(color))
            pivot.setPen(QPen(QColor(0, 0, 0), 2))
            pivot.setZValue(2)
            visual_items.append(pivot)

        # Add ground symbol for fixed pivot
        ground_size = 15
        ground_path = QPainterPath()
        ground_path.moveTo(ground_pivot.x() - ground_size, ground_pivot.y() + pivot_radius)
        ground_path.lineTo(ground_pivot.x() + ground_size, ground_pivot.y() + pivot_radius)
        for i in range(3):
            x = ground_pivot.x() - ground_size + (i+1) * ground_size/2
            ground_path.moveTo(x, ground_pivot.y() + pivot_radius)
            ground_path.lineTo(x - 5, ground_pivot.y() + pivot_radius + 8)
        ground_item = QGraphicsPathItem(ground_path)
        ground_item.setPen(QPen(QColor(127, 140, 141), 2))
        ground_item.setZValue(0)
        visual_items.append(ground_item)

        return visual_items

    def _create_cam_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of cam mechanism"""
        visual_items = []
        params = mechanism_data.get("params", {})

        # Get base position from mechanism data
        base_position = self.mechanism_layers.get(mechanism_data.get("mechanism_id", ""), {}).get("base_position", QPointF(0, 0))

        # Get parameters
        center_local = params.get("center", QPointF(0, 0))
        base_radius = params.get("base_radius", 50.0)
        rise = params.get("rise", 30.0)

        # Transform center to scene coordinates
        center = QPointF(base_position.x() + center_local.x(),
                        base_position.y() + center_local.y())

        # Create cam body (eccentric cam for more interesting motion)
        cam_body = QGraphicsEllipseItem(-base_radius, -base_radius,
                                       base_radius * 2, base_radius * 2)
        cam_body.setPos(center)
        cam_body.setBrush(QBrush(QColor(52, 152, 219, 180)))  # Semi-transparent blue
        cam_body.setPen(QPen(QColor(41, 128, 185), 4))
        cam_body.setZValue(1)
        visual_items.append(cam_body)

        # Add eccentric circle to show cam profile
        ecc_radius = base_radius * 0.7
        ecc_offset = (base_radius - ecc_radius) * 0.5
        ecc_circle = QGraphicsEllipseItem(-ecc_radius, -ecc_radius,
                                         ecc_radius * 2, ecc_radius * 2)
        ecc_circle.setPos(center.x() + ecc_offset, center.y())
        ecc_circle.setBrush(QBrush(QColor(41, 128, 185, 100)))
        ecc_circle.setPen(QPen(QColor(41, 128, 185), 2, Qt.PenStyle.DashLine))
        ecc_circle.setZValue(1)
        visual_items.append(ecc_circle)

        # Create follower with better design
        follower_width = 30
        follower_height = 60
        follower_x = center.x() - follower_width / 2
        follower_y = center.y() - base_radius - rise - follower_height

        follower = QGraphicsRectItem(0, 0, follower_width, follower_height)
        follower.setPos(follower_x, follower_y)
        follower.setBrush(QBrush(QColor(231, 76, 60)))  # Red
        follower.setPen(QPen(QColor(192, 57, 43), 3))
        follower.setZValue(2)
        visual_items.append(follower)

        # Add follower guide rails
        rail_width = follower_width + 20
        rail_height = base_radius * 3
        rail_x = center.x() - rail_width / 2
        rail_y = center.y() - base_radius - rise - follower_height - 10

        left_rail = QGraphicsPathItem()
        left_path = QPainterPath()
        left_path.moveTo(rail_x, rail_y)
        left_path.lineTo(rail_x, rail_y + rail_height)
        left_rail.setPath(left_path)
        left_rail.setPen(QPen(QColor(127, 140, 141), 3))
        left_rail.setZValue(0)
        visual_items.append(left_rail)

        right_rail = QGraphicsPathItem()
        right_path = QPainterPath()
        right_path.moveTo(rail_x + rail_width, rail_y)
        right_path.lineTo(rail_x + rail_width, rail_y + rail_height)
        right_rail.setPath(right_path)
        right_rail.setPen(QPen(QColor(127, 140, 141), 3))
        right_rail.setZValue(0)
        visual_items.append(right_rail)

        # Create center shaft
        shaft_radius = 8
        center_point = QGraphicsEllipseItem(-shaft_radius, -shaft_radius,
                                          shaft_radius * 2, shaft_radius * 2)
        center_point.setPos(center)
        center_point.setBrush(QBrush(QColor(52, 73, 94)))
        center_point.setPen(QPen(QColor(0, 0, 0), 2))
        center_point.setZValue(3)
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
        # Don't scale parameters - use them as-is to maintain coordinate matching
        # The parameters should already be in the correct coordinate system from the recommendation

        # Create mechanism graphics data
        mechanism_graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": mechanism_type,
            "params": params,  # Use original parameters
            "scale_factor": 1.0  # No scaling
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
