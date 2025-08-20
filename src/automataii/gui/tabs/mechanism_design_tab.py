import logging
import math
import uuid
from collections.abc import Callable
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from automataii.config.z_indices import (
    Z_MECHANISM_PIVOT,
    Z_MOTION_PATH_LINE,
    Z_PART_DEFAULT,
    Z_SELECTION_MARKER,
    Z_SKELETON_OVERLAY,
)
from automataii.utils.paths import get_project_root, resolve_path

# Parametric Design System (ULTRATHINK Architecture)
try:
    from automataii.gui.parametric_editor import (
        ParametricEditor, MechanismEditor, FourBarEditor, 
        CamEditor, GearEditor, ParametricHandle
    )
    PARAMETRIC_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Parametric design system not available: {e}")
    PARAMETRIC_AVAILABLE = False

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene

from automataii.core.models import PartInfo
from automataii.gui.blueprint.exporter import BlueprintExporter
from automataii.gui.dialogs.recommendation_dialog import (
    MechanismRecommendationDialog,
    qpainterpath_to_numpy_array,
)
from automataii.gui.graphics_items.part_item import CharacterPartItem
from automataii.gui.tabs.mechanism_design_utils import convert_json_params_to_internal
from automataii.gui.tabs.mechanism_design_utils import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)
from automataii.gui.views.editor_view import EditorView
from automataii.kinematics.mechanism import (
    MechanismCandidate,
)

logger = logging.getLogger(__name__)

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

        self.candidates: list[MechanismCandidate] = []
        self.selected_mechanism: MechanismCandidate | None = None

        # Path data from editor tab
        self.path_data: dict[str, QPainterPath] = {}
        self.selected_part_name: str | None = None
        self.parts_data: dict[str, PartInfo] = {}  # Store parts data
        self.current_editor_items: dict[str, CharacterPartItem] = {}
        self.part_enabled_state: dict[str, bool] = {}  # Track which parts are enabled for mechanism generation

        # Mechanism generation state
        self.current_mechanism_type: str | None = None
        self.mechanism_params: dict[str, Any] = {}
        self.mechanism_layers: dict[str, Any] = {}  # Store mechanism layers with enable/disable state
        self.path_visual_items: dict[str, QGraphicsPathItem] = {}  # Store path visuals
        self.mechanism_paths: dict[str, QPainterPath] = {}  # Generated mechanism paths
        self.mechanism_instances: dict[str, Any] = {}  # Store actual mechanism objects
        self.mechanism_enabled_state: dict[str, bool] = {}  # Track which mechanisms are enabled
        self.interactive_handles: dict[str, list[QGraphicsItem]] = {}  # Drag handles for params

        # Graphics scene for mechanism preview
        self.mechanism_scene = QGraphicsScene(self)
        self.mechanism_view = EditorView(self.mechanism_scene, self, mechanism_mode=True)

        # Blueprint exporter (encapsulates legacy blueprint logic)
        self.blueprint_exporter = BlueprintExporter(
            parent=self,
            mechanism_view=self.mechanism_view,
            get_mechanism_layers=lambda: self.mechanism_layers,
            get_current_editor_items=lambda: self.current_editor_items,
            get_scene_transform_function=self._get_scene_transform_function,
        )

        # Skeleton visualization items
        self.skeleton_joint_items: dict[str, QGraphicsEllipseItem] = {}
        self.skeleton_bone_items: dict[str, QGraphicsLineItem] = {}

        # Mechanism path tracing
        self.mechanism_path_items: dict[str, QGraphicsPathItem] = {}
        self.mechanism_path_points: dict[str, list[QPointF]] = {}

        # Visualization items
        self.debug_items: list[QGraphicsItem] = []
        self.show_debug = False

        # Edit mode state
        self.edit_mode = False
        self.parametric_edit_mode = False  # For interactive parameter adjustment
        self.selected_mechanism_id: str | None = None

        # Animation state
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_time = 0.0
        self.animation_speed = 1.0  # radians per second
        self.animating_mechanisms = {}  # Store original positions for animation

        # Tab state tracking for safe Qt object lifecycle management
        self._tab_visible = False
        self._tab_active = False  # Critical: Track if tab is active to prevent race conditions
        self._scene_recently_cleared = False  # Track scene clear operations to prevent redundant cleanup

        # Mechanism path tracing
        self.mechanism_trace_paths: dict[str, QPainterPath] = {}  # Store traced paths

        # Parametric Design System (ULTRATHINK Architecture)
        self.parametric_editor: ParametricEditor | None = None
        self.parametric_mode_enabled = False

        # Initialize parametric system if available
        if PARAMETRIC_AVAILABLE:
            self._initialize_parametric_system()
        else:
            logging.info("Parametric design features disabled (module not available)")
        self.mechanism_trace_items: dict[str, QGraphicsPathItem] = {}  # Visual path items
        self.mechanism_trace_points: dict[str, list[QPointF]] = {}  # Store trace points

        # UI Elements
        self.blueprint_btn: QPushButton | None = None
        self.recommendation_btn: QPushButton | None = None
        self.mechanism_layers_list: QListWidget | None = None
        self.play_btn: QPushButton | None = None
        self.stop_btn: QPushButton | None = None
        self.reset_btn: QPushButton | None = None
        self.parametric_edit_btn: QPushButton | None = None

        self._setup_ui()
        self._connect_signals()
        self._connect_to_ik_manager()

        # Connect parametric system signals if available
        # Signals are connected in _initialize_parametric_system for the new ParametricEditor

        # Load generated paths (support both dev and bundled layouts)
        generated_paths_file = resolve_path("automataii/kinematics/generated_mechanism_paths.json")
        # Initialize with empty QPainterPath since no user path is drawn yet
        empty_path = QPainterPath()
        self.recommendation_dialog = MechanismRecommendationDialog(empty_path, generated_paths_file, parent=self)
        self.recommendation_dialog.mechanism_selected.connect(self._handle_recommendation_selection)


        self.generated_paths = self.load_generated_paths(generated_paths_file)

    def load_generated_paths(self, file_path):
        """Loads generated mechanism paths from a JSON file."""
        # ... existing code ...

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
        self.control_panel = control_panel  # Store as instance variable for recreation methods
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Parts List Group - EXACT COPY from EditorTab
        layers_group = QGroupBox("1 Parts for Mechanisms")
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
        logging.error(f"[MECHANISM TAB] Created mechanism_layers_list widget: {id(self.mechanism_layers_list)}")
        self.mechanism_layers_list.setToolTip("Parts for mechanisms - black: has motion path, gray: no motion path")
        self.mechanism_layers_list.setMinimumHeight(180)
        self.mechanism_layers_list.setStyleSheet("""
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
        """)
        # Add widget to layout (Qt handles parent automatically)
        # layers_layout.addWidget(self.mechanism_layers_list)
        # panel_layout.addWidget(layers_group)

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

        self.recommendation_btn = QPushButton("Get Mechanism")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations based on motion paths")
        self.recommendation_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        generation_layout.addWidget(self.recommendation_btn)

        # Parametric Design Button (ULTRATHINK Architecture)
        if PARAMETRIC_AVAILABLE:
            self.parametric_edit_btn = QPushButton("Parametric Edit")
            self.parametric_edit_btn.setToolTip("Enable interactive parameter editing with drag handles")
            self.parametric_edit_btn.setEnabled(False)  # Enable when mechanisms are loaded
            self.parametric_edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-size: 13px;
                    font-weight: normal;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:disabled {
                    background-color: #bdc3c7;
                    color: #7f8c8d;
                }
            """)
            generation_layout.addWidget(self.parametric_edit_btn)


            # Dimension Display Button
            self.show_dimensions_btn = QPushButton("📏 Show Dimensions")
            self.show_dimensions_btn.setToolTip("Display mechanism dimensions for printing")
            self.show_dimensions_btn.setVisible(False)  # Hidden until parametric mode
            self.show_dimensions_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: normal;
                    min-height: 16px;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
            """)
            generation_layout.addWidget(self.show_dimensions_btn)

            # Export Blueprint Button
            self.export_blueprint_btn = QPushButton("📄 Export Blueprint")
            self.export_blueprint_btn.setToolTip("Export mechanism as printable blueprint")
            self.export_blueprint_btn.setVisible(False)  # Hidden until parametric mode
            self.export_blueprint_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e67e22;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: normal;
                    min-height: 16px;
                }
                QPushButton:hover {
                    background-color: #d35400;
                }
            """)
            generation_layout.addWidget(self.export_blueprint_btn)
        else:
            # Parametric features not available
            self.parametric_edit_btn = None
            self.show_dimensions_btn = None
            self.export_blueprint_btn = None

        panel_layout.addWidget(generation_group)

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

        style = self.style()
        anim_button_layout = QHBoxLayout()
        anim_button_layout.setSpacing(12)

        self.play_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay), "")
        self.play_btn.setToolTip("Play Animation")
        self.play_btn.setEnabled(False)

        self.stop_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop), "")
        self.stop_btn.setToolTip("Stop Animation")
        self.stop_btn.setEnabled(False)

        self.reset_btn = QPushButton(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "")
        self.reset_btn.setToolTip("Reset Animation")
        self.reset_btn.setEnabled(False)

        anim_button_layout.addStretch()
        anim_button_layout.addWidget(self.play_btn)
        anim_button_layout.addWidget(self.stop_btn)
        anim_button_layout.addWidget(self.reset_btn)
        anim_button_layout.addStretch()

        animation_layout.addLayout(anim_button_layout)
        panel_layout.addWidget(animation_group)


        # 4. Blueprint Export Group
        export_group = QGroupBox("4 Blueprint Export")
        export_group.setStyleSheet("""
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
        export_layout = QVBoxLayout(export_group)

        self.blueprint_btn = QPushButton("Export Blueprint")
        self.blueprint_btn.setEnabled(False)
        self.blueprint_btn.setToolTip("Export character parts and mechanisms as SVG blueprint")
        self.blueprint_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                font-weight: normal;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        export_layout.addWidget(self.blueprint_btn)

        # Info label for single large page export
        self.blueprint_info_label = QLabel("Exports to single large-format blueprint (1200×1600mm)")
        self.blueprint_info_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 10px;
                font-style: italic;
                padding: 2px;
            }
        """)
        export_layout.addWidget(self.blueprint_info_label)
        panel_layout.addWidget(export_group)

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

        # Center on Character button
        self.center_character_btn = QPushButton("⎈")
        self.center_character_btn.setToolTip("Center on Character")
        self.center_character_btn.setStyleSheet(zoom_button_style)
        zoom_controls_layout.addWidget(self.center_character_btn)

        view_controls_layout.addLayout(zoom_controls_layout)
        panel_layout.addWidget(view_controls_group)

        panel_layout.addStretch(1)

        control_panel.setMinimumWidth(280)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)

        main_layout.addWidget(self.mechanism_view, 1)

    def _connect_signals(self):
        """Connect signals"""
        self.recommendation_btn.clicked.connect(self._on_get_recommendations)
        self.play_btn.clicked.connect(self._on_start_animation)
        self.stop_btn.clicked.connect(self._on_stop_animation)
        self.reset_btn.clicked.connect(self._on_reset_animation)
        self.mechanism_layers_list.itemSelectionChanged.connect(self._on_layer_selection_changed)
        self.mechanism_layers_list.itemClicked.connect(self._on_layer_item_clicked)

        # Connect EditorView's joint_bend_direction_changed signal
        if hasattr(self.mechanism_view, 'joint_bend_direction_changed'):
            self.mechanism_view.joint_bend_direction_changed.connect(self._handle_joint_bend_direction_changed)

        # Blueprint Export signal
        if self.blueprint_btn:
            self.blueprint_btn.clicked.connect(self._on_export_blueprint)
        
        # View Controls signals
        if hasattr(self, 'zoom_in_btn'):
            self.zoom_in_btn.clicked.connect(lambda: self.mechanism_view.zoom(1))
            self.zoom_out_btn.clicked.connect(lambda: self.mechanism_view.zoom(-1))
            self.zoom_fit_btn.clicked.connect(self.mechanism_view.zoom_to_fit)
            self.center_character_btn.clicked.connect(self.center_on_character)

        # Parametric Design System signals
        if PARAMETRIC_AVAILABLE and self.parametric_edit_btn:
            self.parametric_edit_btn.clicked.connect(lambda: self.toggle_parametric_mode())

            # Connect dimension and export buttons
            if self.show_dimensions_btn:
                self.show_dimensions_btn.clicked.connect(self._show_current_mechanism_dimensions)
            if self.export_blueprint_btn:
                self.export_blueprint_btn.clicked.connect(self._export_current_mechanism_blueprint)

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change from EditorView."""
        logging.info(f"MechanismDesignTab: Joint '{joint_id}' bend direction changed to {new_direction}")

        # Update skeleton manager if available
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            self.main_window.skeleton_manager.set_joint_bend_direction(joint_id, new_direction)
            logging.info("MechanismDesignTab: Updated bend direction in skeleton_manager")

    def on_skeleton_manager_updated(self, skeleton_data: dict | None):
        """Handle skeleton updates from skeleton_manager (for bend_direction sync)."""
        if not skeleton_data:
            return

        logging.info("MechanismDesignTab: Received skeleton update from skeleton_manager")

        # Update skeleton visualization with new bend_direction values
        if hasattr(self.mechanism_view, 'skeleton_graphics_item') and self.mechanism_view.skeleton_graphics_item:
            try:
                # Check if skeleton graphics item is valid
                _ = self.mechanism_view.skeleton_graphics_item.boundingRect()

                # Update bend directions in the skeleton graphics item
                joints_dict = skeleton_data.get("joints", {})
                for joint_id, joint_data in joints_dict.items():
                    bend_dir = joint_data.get("bend_direction")
                    if bend_dir is not None and ('elbow' in joint_id or 'knee' in joint_id):
                        self.mechanism_view.skeleton_graphics_item.set_joint_bend_direction(joint_id, bend_dir)
                        logging.info(f"MechanismDesignTab: Updated bend_direction for '{joint_id}' to {bend_dir}")

                # Update the visual
                self.mechanism_view.skeleton_graphics_item.update()

            except RuntimeError:
                # Skeleton item was deleted, will be recreated on next update
                pass


    def _connect_to_ik_manager(self):
        """Connect to IK manager signals for skeleton animation."""
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Connect to skeleton pose updates
                self.main_window.ik_manager.skeleton_pose_updated.connect(self.on_skeleton_updated)
            except Exception as e:
                logging.warning(f"Failed to connect to IK manager: {e}")

        # Also connect to skeleton_manager for bend_direction updates
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            try:
                # Connect to skeleton_manager updates to sync bend_direction changes
                self.main_window.skeleton_manager.skeleton_updated.connect(self.on_skeleton_manager_updated)
                logging.info("MechanismDesignTab: Connected to skeleton_manager for bend_direction updates")
            except Exception as e:
                logging.warning(f"Failed to connect to skeleton_manager: {e}")

    def set_path_data_from_editor(self, path_data: dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        logging.debug(f"[MECHANISM TAB] set_path_data_from_editor called with {len(path_data) if path_data else 0} paths")
        if path_data:
            logging.debug(f"[MECHANISM TAB] Path parts: {list(path_data.keys())}")

            # Debug individual path data
            for part_name, path in path_data.items():
                if path and not path.isEmpty():
                    path_rect = path.boundingRect()
                    logging.debug(f"[MECHANISM TAB] Path '{part_name}': bounding rect = {path_rect}")

                    # Check if path has any elements
                    element_count = path.elementCount()
                    logging.debug(f"[MECHANISM TAB] Path '{part_name}': element count = {element_count}")
                else:
                    logging.debug(f"[MECHANISM TAB] Path '{part_name}': empty or None")

        # 🔧 PATH SYNC FIX: Clear mechanisms for parts that no longer have paths or have new paths
        current_parts = set(path_data.keys()) if path_data else set()
        previous_parts = set(self.path_data.keys()) if hasattr(self, 'path_data') and self.path_data else set()

        # Find parts that were removed or changed
        parts_to_clear = previous_parts - current_parts  # Parts that no longer have paths

        # Also clear parts that have new/different paths
        for part_name in current_parts:
            if (hasattr(self, 'path_data') and part_name in self.path_data and
                path_data.get(part_name) != self.path_data.get(part_name)):
                parts_to_clear.add(part_name)

        # Clear mechanisms for affected parts
        for part_name in parts_to_clear:
            self._clear_mechanism_for_part(part_name)
            logging.info(f"[MECHANISM TAB] Cleared mechanism for part '{part_name}' due to path change")

        self.path_data = path_data.copy() if path_data else {}

        # Initialize enabled state for new parts (default to enabled)
        for part_name in self.path_data.keys():
            if part_name not in self.part_enabled_state:
                self.part_enabled_state[part_name] = True

        # Remove enabled state for parts that no longer have paths
        parts_to_remove = [name for name in self.part_enabled_state.keys() if name not in self.path_data]
        for part_name in parts_to_remove:
            del self.part_enabled_state[part_name]

        # Update recommendation button state based on enabled parts
        self._update_recommendation_button_state()

        # Update tooltip with part information
        if self.path_data:
            part_names = ", ".join(list(self.path_data.keys())[:3])
            if len(self.path_data) > 3:
                part_names += f", ... ({len(self.path_data)} total)"
            if self.recommendation_btn:
                self.recommendation_btn.setToolTip(f"Parts with paths: {part_names}")
        else:
            if self.recommendation_btn:
                self.recommendation_btn.setToolTip("No motion paths available")

        self._display_paths_in_preview()

        # 🔧 UI UPDATE: Update mechanism layers list to reflect cleared mechanisms
        self._update_mechanism_layers_list()

    def set_parts_data(self, parts_data: dict[str, PartInfo]):
        """Set parts data (synchronized with editor tab)"""
        logging.debug(f"[MECHANISM TAB] set_parts_data called with {len(parts_data) if parts_data else 0} parts")
        if parts_data:
            logging.debug(f"[MECHANISM TAB] Parts: {list(parts_data.keys())}")

        # Sort parts data to show parts with paths first
        if parts_data:
            sorted_part_names = sorted(
                parts_data.keys(),
                key=lambda name: name in self.path_data,
                reverse=True
            )
            self.parts_data = {name: parts_data[name] for name in sorted_part_names}
        else:
            self.parts_data = {}

        # Clear scene but preserve skeleton graphics item
        self._clear_scene_preserve_skeleton()
        self.current_editor_items.clear()

        if self.parts_data:
            project_dir = self.main_window.project_data_manager.project_dir
            for part_name, p_info in parts_data.items():
                if project_dir:
                    item = CharacterPartItem(part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode)
                    item.setZValue(Z_PART_DEFAULT)  # Use standardized Z-level for parts

                    # Disable part dragging in mechanism tab while keeping click functionality
                    item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                    # Ensure parts remain selectable for click interactions
                    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)

                    # All parts display normally without any highlighting
                    item.setOpacity(1.0)

                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item
            self._position_parts_at_anchor_joints()
            # self.mechanism_view.zoom_to_fit()

        # Update mechanism layers list to show parts
        self._update_mechanism_layers_list()


    def _position_parts_at_anchor_joints(self):
        """Position parts at their anchor joints using cached skeleton data."""
        if not hasattr(self, '_initial_skeleton_data_cache') or not self._initial_skeleton_data_cache:
            return

        joints_dict = self._initial_skeleton_data_cache.get("joints", {})
        for part_name, part_item in self.current_editor_items.items():
            part_info = self.parts_data.get(part_name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                joint_pos = joint_data.get("position", [0, 0])
                if len(joint_pos) >= 2:
                    scene_pos = QPointF(joint_pos[0], joint_pos[1])
                    part_item.set_scene_position_from_anchor(scene_pos)

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
        """Cache the initial skeleton data dictionary and ensure skeleton visualization is set up"""
        self._initial_skeleton_data_cache = skeleton_data_dict.copy() if skeleton_data_dict else None
        if self._initial_skeleton_data_cache:
            if self.mechanism_view and hasattr(self.mechanism_view, "set_joint_map"):
                self.mechanism_view.set_joint_map(self._initial_skeleton_data_cache.get("joint_map"))

            # Ensure skeleton visualization is initialized with complete skeleton data
            self._ensure_skeleton_visualization(self._initial_skeleton_data_cache)

            # Only position parts at anchor joints if animation is NOT running
            # This prevents parts from being reset to initial positions during animation
            if self.current_editor_items and not self._is_animation_running():
                self._position_parts_at_anchor_joints()

    def _is_animation_running(self) -> bool:
        """Check if mechanism animation is currently running."""
        return self.animation_timer and self.animation_timer.isActive()

    def on_skeleton_updated(self, skeleton_data: dict | None):
        """Handle skeleton updates from IK manager with improved error handling and mechanism integration."""
        # Validate skeleton_data first
        if not skeleton_data:
            return

        # Check if mechanism_view and its skeleton components exist
        if not self.mechanism_view:
            return

        # Validate skeleton data structure
        is_valid_data = False
        if isinstance(skeleton_data, dict):
            if skeleton_data.get("joints") and len(skeleton_data["joints"]) > 0:
                is_valid_data = True
            elif all(isinstance(v, (tuple, list)) and len(v) == 2 for v in skeleton_data.values()):
                is_valid_data = True

        if not is_valid_data:
            return

        try:
            # Check if we received raw animation data from IK manager
            if skeleton_data and all(isinstance(v, (tuple, list)) and len(v) == 2 for v in skeleton_data.values()):
                # Convert IK manager format Dict[str, Tuple[float, float]] to expected format
                transformed_data = {
                    "joints": {
                        joint_id: {
                            "scene_position": list(pos),
                            "id": joint_id
                        }
                        for joint_id, pos in skeleton_data.items()
                    }
                }

                # Ensure skeleton is initialized before animation
                self._ensure_skeleton_visualization(transformed_data)

                # Now update skeleton animation using the transformed data
                if hasattr(self.mechanism_view, 'update_skeleton_animation'):
                    self.mechanism_view.update_skeleton_animation(skeleton_data)

                skeleton_data = transformed_data
            else:
                # Standard skeleton model format - ensure skeleton visualization is set up
                self._ensure_skeleton_visualization(skeleton_data)

            # Update part positions from skeleton during animation
            if self.animation_timer.isActive():
                self._update_parts_from_skeleton(skeleton_data)
            else:
                # Even when not animating, update parts that aren't mechanism-controlled
                self._update_parts_from_skeleton(skeleton_data)

        except Exception:
            # Don't let skeleton errors crash the mechanism animation
            pass

    def _update_parts_from_skeleton(self, skeleton_data: dict):
        """Update part positions and rotations based on skeleton joint movements (matching editor tab behavior)."""
        joints_dict = skeleton_data.get("joints", {})
        # hierarchy = skeleton_data.get("hierarchy", {})


        for part_name, part_item in self.current_editor_items.items():
            part_info = self.parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            anchor_joint_id = part_info.anchor_joint_id
            if anchor_joint_id not in joints_dict:
                continue

            joint_data = joints_dict[anchor_joint_id]

            # 1. UPDATE POSITION (unconditionally)
            position_updated = False
            scene_pos_to_set = None

            position_data = joint_data.get("scene_position") or joint_data.get("position")
            if isinstance(position_data, (list, tuple)) and len(position_data) >= 2:
                scene_pos_to_set = QPointF(position_data[0], position_data[1])
                part_item.set_scene_position_from_anchor(scene_pos_to_set)
                position_updated = True

            # 2. UPDATE ROTATION (CRITICAL: like editor tab)
            rotation_updated = False

            # Try multiple rotation data sources
            if "world_rotation_degrees" in joint_data:
                rotation = float(joint_data["world_rotation_degrees"])
                part_item.setRotation(rotation)
                rotation_updated = True
            elif "angle" in joint_data:
                angle = joint_data["angle"]
                if isinstance(angle, (int, float)):
                    rotation_degrees = math.degrees(angle) if abs(angle) <= 2*math.pi else angle
                    part_item.setRotation(rotation_degrees)
                    rotation_updated = True
            elif "rotation" in joint_data:
                rotation = joint_data["rotation"]
                if isinstance(rotation, (int, float)):
                    part_item.setRotation(rotation)
                    rotation_updated = True
            else:
                # FALLBACK: Calculate bone angle from parent-child relationship
                parent_joint_id = joint_data.get("parent_id") or joint_data.get("parent")
                if parent_joint_id and parent_joint_id in joints_dict:
                    parent_data = joints_dict[parent_joint_id]
                    parent_pos_data = parent_data.get("scene_position") or parent_data.get("position")

                    if (scene_pos_to_set and parent_pos_data and
                        isinstance(parent_pos_data, (list, tuple)) and len(parent_pos_data) >= 2):

                        dx = scene_pos_to_set.x() - parent_pos_data[0]
                        dy = scene_pos_to_set.y() - parent_pos_data[1]

                        if abs(dx) > 0.01 or abs(dy) > 0.01:
                            bone_angle_rad = math.atan2(dy, dx)
                            bone_angle_deg = math.degrees(bone_angle_rad)
                            part_item.setRotation(bone_angle_deg)
                            rotation_updated = True


    def _ensure_skeleton_visualization(self, skeleton_data: dict):
        """Ensure skeleton visualization is properly set up and updated."""
        if not hasattr(self.mechanism_view, 'visualize_skeleton'):
            return

        try:
            # Check if skeleton graphics item exists and is valid
            skeleton_item = getattr(self.mechanism_view, 'skeleton_graphics_item', None)
            needs_initialization = False

            if not skeleton_item:
                needs_initialization = True
            else:
                try:
                    # Test if the skeleton item is still valid (not deleted by C++)
                    _ = skeleton_item.boundingRect()
                    # Check if skeleton has joint items for animation
                    if not hasattr(skeleton_item, '_joint_items') or not skeleton_item._joint_items:
                        needs_initialization = True
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        needs_initialization = True
                    else:
                        raise

            if needs_initialization:
                # Format skeleton data for visualize_skeleton like editor tab does
                skeleton_for_view, hierarchy = self._format_skeleton_for_visualization(skeleton_data)
                if skeleton_for_view:
                    self.mechanism_view.visualize_skeleton(skeleton_for_view, hierarchy)

                    # Ensure proper Z-order after creation
                    if hasattr(self.mechanism_view, 'skeleton_graphics_item') and self.mechanism_view.skeleton_graphics_item:
                        self.mechanism_view.skeleton_graphics_item.setZValue(Z_SKELETON_OVERLAY)
            else:
                # Skeleton exists, just update animation
                if skeleton_item and hasattr(skeleton_item, 'set_animated_pose'):
                    # Convert skeleton_data to the format expected by set_animated_pose
                    pose_data = self._convert_skeleton_data_for_animation(skeleton_data)
                    if pose_data:
                        skeleton_item.set_animated_pose(pose_data)

        except Exception:
            pass

    def _format_skeleton_for_visualization(self, skeleton_data: dict):
        """Format skeleton data for visualize_skeleton method like editor tab does."""
        from PyQt6.QtCore import QPointF

        skeleton_for_view = []
        hierarchy: dict[str, list[str]] = {}

        if "joints" in skeleton_data:
            joints_dict = skeleton_data["joints"]
            for joint_id, joint_info in joints_dict.items():
                # Handle different joint data formats
                if isinstance(joint_info, dict):
                    position = joint_info.get("position") or joint_info.get("scene_position", [0, 0])
                    parent_id = joint_info.get("parent")
                    joint_name = joint_info.get("name", joint_id)
                elif isinstance(joint_info, (list, tuple)) and len(joint_info) >= 2:
                    position = joint_info[:2]
                    parent_id = None
                    joint_name = joint_id
                else:
                    continue

                # Convert position to QPointF
                if isinstance(position, QPointF):
                    pos_qpoint = position
                elif isinstance(position, (list, tuple)) and len(position) >= 2:
                    pos_qpoint = QPointF(float(position[0]), float(position[1]))
                else:
                    continue

                joint_view_data = {
                    "id": joint_id,
                    "name": joint_name,
                    "position": pos_qpoint,
                    "parent": parent_id,
                    "color": "blue",
                    "label": joint_name
                }
                skeleton_for_view.append(joint_view_data)

                # Build hierarchy
                if parent_id:
                    if parent_id not in hierarchy:
                        hierarchy[parent_id] = []
                    hierarchy[parent_id].append(joint_id)

        # Also check hierarchy from skeleton_data
        if "hierarchy" in skeleton_data:
            hierarchy.update(skeleton_data["hierarchy"])

        return skeleton_for_view, hierarchy

    def _convert_skeleton_data_for_animation(self, skeleton_data: dict):
        """Convert skeleton data to format expected by set_animated_pose."""
        pose_data = {}

        if "joints" in skeleton_data:
            joints_dict = skeleton_data["joints"]
            for joint_id, joint_info in joints_dict.items():
                if isinstance(joint_info, dict):
                    position = joint_info.get("position") or joint_info.get("scene_position")
                    if position and len(position) >= 2:
                        pose_data[joint_id] = (float(position[0]), float(position[1]))
                elif isinstance(joint_info, (list, tuple)) and len(joint_info) >= 2:
                    pose_data[joint_id] = (float(joint_info[0]), float(joint_info[1]))

        return pose_data

    def _clear_scene_preserve_skeleton(self):
        """Clear the scene but preserve the skeleton graphics item."""
        if not self.mechanism_scene:
            return

        # Store skeleton item reference if it exists
        skeleton_item = None
        if self.mechanism_view and hasattr(self.mechanism_view, 'skeleton_graphics_item'):
            skeleton_item = self.mechanism_view.skeleton_graphics_item

        # Remove skeleton from scene temporarily to prevent deletion
        try:
            if skeleton_item and hasattr(skeleton_item, 'scene') and skeleton_item.scene() == self.mechanism_scene:
                self.mechanism_scene.removeItem(skeleton_item)
        except RuntimeError:
            # Skeleton item was already deleted by Qt - ignore
            logging.debug("Skeleton item already deleted by Qt, skipping removal")
            pass

        # CRITICAL: Clear data structures BEFORE clearing scene to prevent Qt object access errors
        logging.debug("[MECHANISM TAB] Clearing data structures before Qt scene clear")

        # 1. Clear all mechanism visual item references FIRST
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if "visual_items" in layer_data:
                layer_data["visual_items"] = []
                logging.debug(f"Cleared visual items for mechanism {mechanism_id}")

        # 2. Clear other visual tracking structures
        self.mechanism_trace_items.clear()
        if hasattr(self, 'path_visual_items'):
            self.path_visual_items.clear()

        # 3. NOW clear the scene (this will delete all Qt objects atomically)
        logging.debug("[MECHANISM TAB] Performing Qt scene clear")
        self._scene_recently_cleared = True  # Flag to prevent individual item removal
        self.mechanism_scene.clear()

        # Reset the flag after a short delay to allow normal operations
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: setattr(self, '_scene_recently_cleared', False))

        # 4. Re-add skeleton item if it was preserved
        if skeleton_item:
            try:
                # Test if skeleton item is still valid
                _ = skeleton_item.boundingRect()
                self.mechanism_scene.addItem(skeleton_item)
                # Set proper Z-order: skeleton at bottom (Z=0)
                skeleton_item.setZValue(Z_SKELETON_OVERLAY)
                logging.debug("[MECHANISM TAB] Skeleton item preserved and re-added")
            except RuntimeError:
                # Skeleton was already deleted, clear the reference
                if hasattr(self.mechanism_view, 'skeleton_graphics_item'):
                    self.mechanism_view.skeleton_graphics_item = None
                logging.debug("[MECHANISM TAB] Skeleton item was deleted during clear")

    def _get_target_joint_for_mechanism_control(self, part_name: str, anchor_joint_id: str) -> str:
        """Get the correct target joint (end effector) for mechanism control based on part name.
        ALL PARTS ARE END EFFECTORS - every part should control its furthest joint.
        """
        # Import BODY_PARTS to get joint definitions
        try:
            from automataii.animate.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}
            logging.warning("Could not import BODY_PARTS for end effector detection")

        # CRITICAL FIX: Always use neck for head mechanism control
        if part_name == "head":
            return "neck"

        # Check if this part has joint definitions
        part_definition = BODY_PARTS.get(part_name, {})
        part_joints = part_definition.get("joints", [])

        # All parts are end effectors
        # Every part should control its FURTHEST joint (last in the joint chain)
        if part_joints and len(part_joints) > 0:
            # Always use the LAST joint as the end effector for this part
            end_effector = part_joints[-1]
            return end_effector

        # Fallback mapping for parts without joint definitions
        FALLBACK_PART_TO_TARGET_JOINT = {
            # Arms - target should be hands (end effectors)
            "left_arm_upper": "left_elbow",     # shoulder → elbow (end of upper arm)
            "left_arm_lower": "left_hand",     # elbow → hand (end of lower arm)
            "right_arm_upper": "right_elbow",  # shoulder → elbow (end of upper arm)
            "right_arm_lower": "right_hand",   # elbow → hand (end of lower arm)

            # Legs - target should be feet (end effectors)
            "left_leg_upper": "left_knee",     # hip → knee (end of upper leg)
            "left_leg_lower": "left_foot",     # knee → foot (end of lower leg)
            "right_leg_upper": "right_knee",   # hip → knee (end of upper leg)
            "right_leg_lower": "right_foot",   # knee → foot (end of lower leg)

            # Special cases
            "head": "neck",                    # head is controlled via neck joint
            "torso": "torso",                  # torso → torso (center)
        }

        target_joint = FALLBACK_PART_TO_TARGET_JOINT.get(part_name, anchor_joint_id)


        return target_joint

    def _setup_mechanism_ik_integration(self):
        """Setup integration between mechanism animation and IK system."""
        if not hasattr(self.main_window, 'ik_manager') or not self.main_window.ik_manager:
            return False

        try:
            # Set up parts data in IK manager
            if self.parts_data:
                if hasattr(self.main_window.ik_manager, 'set_project_parts_data'):
                    self.main_window.ik_manager.set_project_parts_data(self.parts_data)

            # Set skeleton data if available
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                if hasattr(self.main_window.ik_manager, 'on_skeleton_data_updated_from_manager'):
                    self.main_window.ik_manager.on_skeleton_data_updated_from_manager(self._initial_skeleton_data_cache)

            # Register mechanism controllers for each active mechanism
            for mech_id, layer_data in self.mechanism_layers.items():
                if self.mechanism_enabled_state.get(mech_id, False):
                    part_name = layer_data.get("part_name")
                    if part_name and part_name in self.parts_data:
                        part_info = self.parts_data[part_name]
                        if part_info.anchor_joint_id:
                            self._register_mechanism_controller(mech_id, layer_data, part_info.anchor_joint_id)

            return True

        except Exception:
            pass
            return False

    def _register_mechanism_controller(self, mech_id: str, layer_data: dict, joint_id: str):
        """Register a mechanism as a controller for a specific joint with enhanced IK integration."""
        try:
            # Create a callback function that calculates mechanism output for the joint
            def mechanism_joint_callback(time: float) -> QPointF | None:
                return self._calculate_mechanism_output(
                    layer_data.get("type"),
                    layer_data.get("params", {}),
                    time,
                    layer_data
                )

            # Method 1: Generate complete motion path for IK system
            joint_motion_path = self._generate_joint_motion_path(layer_data, joint_id)
            if joint_motion_path:
                # Set motion path directly (most effective for IK)
                if hasattr(self.main_window.ik_manager, 'set_joint_motion_path'):
                    self.main_window.ik_manager.set_joint_motion_path(joint_id, joint_motion_path)

                # Set motion path for part name as well (alternative interface)
                part_name = layer_data.get("part_name")
                if part_name and hasattr(self.main_window.ik_manager, 'set_part_motion_path'):
                    self.main_window.ik_manager.set_part_motion_path(part_name, joint_motion_path)

            # Method 2: Register mechanism controller callback
            if hasattr(self.main_window.ik_manager, 'register_mechanism_controller'):
                self.main_window.ik_manager.register_mechanism_controller(
                    joint_id, mech_id, mechanism_joint_callback
                )

            # Method 3: Enable IK for the affected body part
            part_name = layer_data.get("part_name")
            if part_name and hasattr(self.main_window.ik_manager, 'enable_ik_for_part'):
                self.main_window.ik_manager.enable_ik_for_part(part_name, True)

        except Exception:
            pass


    def clear_mechanism_data(self):
        """Clear all mechanism-related data and reset the tab's state with IK cleanup."""
        # Stop animation and clear IK connections first
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            self.animation_time = 0.0

        # Clear IK system connections
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop any running animation
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                self.main_window.ik_manager.clear_mechanism_position_targets()


            except Exception:
                pass

        # Clear mechanism data
        self.path_data.clear()
        self.selected_part_name = None
        self.mechanism_layers.clear()
        self.mechanism_enabled_state.clear()
        self.interactive_handles.clear()
        self.path_visual_items.clear()
        self.mechanism_path_items.clear()
        self.mechanism_path_points.clear()
        self.current_editor_items.clear()
        self.parts_data.clear()

        # Clear mechanism path tracing
        self.mechanism_trace_paths.clear()
        self.mechanism_trace_items.clear()
        self.mechanism_trace_points.clear()

        # Clear UI elements
        if self.mechanism_layers_list:
            self.mechanism_layers_list.clear()

        if self.mechanism_scene:
            self._clear_scene_preserve_skeleton()

        # Reset UI state
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.recommendation_btn.setEnabled(False)

        self.selected_mechanism_id = None


    @pyqtSlot()
    def _on_get_recommendations(self):
        """Show mechanism recommendation dialog"""
        # Get enabled parts with paths
        enabled_parts_with_paths = {
            name: path for name, path in self.path_data.items()
            if self.part_enabled_state.get(name, True)
        }

        if not enabled_parts_with_paths:
            QMessageBox.warning(self, "Warning", "No enabled parts with motion paths available.")
            return

        # Check if a part is selected from the list
        selected_items = self.mechanism_layers_list.selectedItems()
        target_part_name = None

        if selected_items:
            # Get the part name from UserRole data
            selected_part = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if selected_part and selected_part in enabled_parts_with_paths:
                target_part_name = selected_part

        # If no valid part selected or part is not enabled, show selection dialog
        if not target_part_name:
            if len(enabled_parts_with_paths) > 1:
                from PyQt6.QtWidgets import QInputDialog
                enabled_part_names = list(enabled_parts_with_paths.keys())
                selected_part, ok = QInputDialog.getItem(
                    self,
                    "Select Part",
                    "Select which enabled part to generate mechanism for:",
                    enabled_part_names,
                    0,  # default selection
                    False  # not editable
                )
                if not ok:
                    return
                target_part_name = selected_part
            elif len(enabled_parts_with_paths) == 1:
                # Only one enabled part available, use it
                target_part_name = next(iter(enabled_parts_with_paths.keys()))
            else:
                QMessageBox.warning(self, "Warning", "No enabled parts with motion paths available.")
                return

        target_path = enabled_parts_with_paths[target_part_name]
        self.selected_part_name = target_part_name

        from automataii.utils.paths import resolve_path
        generated_paths_file = resolve_path("automataii/kinematics/generated_mechanism_paths.json")

        if not generated_paths_file.exists():
            QMessageBox.critical(self, "Error", "Generated mechanism paths file not found.")
            return

        dialog = MechanismRecommendationDialog(target_path, generated_paths_file, parent=self)
        dialog.setWindowTitle(f"Mechanism Recommendations for {target_part_name}")
        # Connect the preview signal to handle mechanism previews
        dialog.mechanism_preview_selected.connect(self._on_mechanism_preview_selected)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            if selected_mechanism:
                self._generate_mechanism_from_candidate(selected_mechanism)

    def _on_mechanism_preview_selected(self, mechanism_data: dict[str, Any]):
        """Handle mechanism preview selection from dialog."""
        # Temporarily show the mechanism in the view
        self._preview_mechanism(mechanism_data)

    def _get_character_position(self):
        """Get the character's position for mechanism placement."""
        if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
            joints = self._initial_skeleton_data_cache.get("joints", {})
            if joints:
                # Look specifically for foot joints
                foot_joints = []
                lowest_y = float('-inf')

                for joint_id, joint_data in joints.items():
                    pos = joint_data.get("position", [0, 0])
                    # Check if this is likely a foot joint (lowest joints)
                    if "foot" in joint_id.lower() or "ankle" in joint_id.lower():
                        foot_joints.append(pos)
                    # Track the lowest Y position
                    if pos[1] > lowest_y:  # In Qt, y increases downward
                        lowest_y = pos[1]

                # If we found foot joints, use their average X
                if foot_joints:
                    avg_x = sum(pos[0] for pos in foot_joints) / len(foot_joints)
                    avg_y = sum(pos[1] for pos in foot_joints) / len(foot_joints)
                    # CAM should be directly below feet
                    return [avg_x, avg_y + 50]  # Place CAM 50 units below feet

                # Otherwise, find the lowest joints (likely feet)
                lowest_joints = []
                for joint_id, joint_data in joints.items():
                    pos = joint_data.get("position", [0, 0])
                    # Consider joints near the lowest position as feet
                    if abs(pos[1] - lowest_y) < 20:  # Within 20 units of lowest
                        lowest_joints.append(pos)

                if lowest_joints:
                    # Average X position of lowest joints
                    avg_x = sum(pos[0] for pos in lowest_joints) / len(lowest_joints)
                    # CAM below the lowest point
                    return [avg_x, lowest_y + 50]

        # Fallback to center position
        return [300, 400]

    def _handle_recommendation_selection(self, mechanism_data: dict[str, Any]):
        """Handle mechanism selection from recommendation dialog.
        Converts the recommendation data format to the format expected by handle_mechanism_visuals."""

        # Extract mechanism type and map it to internal type
        mechanism_type_value = mechanism_data.get('type', 'Unknown')
        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage",
            "4-bar Coupler": "4_bar_linkage",
            "Cam & Follower": "cam",
            "Cam-Follower": "cam",
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
            "Simple Gear": "gear",
            "Planetary Gear": "planetary_gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        # Generate unique mechanism ID
        import uuid
        mechanism_id = str(uuid.uuid4())
        
        # Get the actual user-drawn path for this part
        target_path = None
        if hasattr(self, 'selected_part_name') and self.selected_part_name:
            target_path = self.path_data.get(self.selected_part_name)
        
        # If no user path available, try to create from path_coordinates
        if not target_path:
            path_coords = mechanism_data.get("path_coordinates")
            if path_coords and isinstance(path_coords, list) and len(path_coords) > 0:
                target_path = QPainterPath()
                target_path.moveTo(path_coords[0][0], path_coords[0][1])
                for coord in path_coords[1:]:
                    target_path.lineTo(coord[0], coord[1])

        # Convert recommendation data to the format expected by handle_mechanism_visuals
        graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": internal_type,
            "params": mechanism_data.get("parameters", {}),
            "transform_params": mechanism_data.get("transform_params"),
            "generated_path": target_path if target_path else QPainterPath(),  # Use actual user path
            "visualization_params": mechanism_data.get("visualization_params"),
            "full_simulation_data": mechanism_data.get("full_simulation_data", {}),
            "key_points": mechanism_data.get("key_points", {}),
            "name": mechanism_data.get("name", f"{mechanism_type_value} Mechanism"),
            "type": mechanism_type_value
        }

        # Create mechanism layer data
        layer_data = {
            "id": mechanism_id,
            "name": graphics_data["name"],
            "type": internal_type,
            "params": graphics_data["params"],
            "transform_params": graphics_data["transform_params"],
            "generated_path": graphics_data["generated_path"],
            "visualization_params": graphics_data["visualization_params"],
            "full_simulation_data": graphics_data["full_simulation_data"],
            "key_points": graphics_data["key_points"],
            "visual_items": []
        }

        # Add scaling factors for CAM mechanisms
        # TODO: Calculate based on character size (see CAM_DECOUPLING_ANALYSIS.md)
        if internal_type == "cam":
            # Adjust scaling for better visibility near character
            layer_data["cam_scale_factor"] = 1.0  # Normal CAM size for visibility
            layer_data["rod_length_multiplier"] = 1.0  # Direct rod length control (no scaling)
            
            # Ensure params dictionary exists and contains center coordinates
            if "params" not in layer_data:
                layer_data["params"] = {}

            # For CAM, we need to position it directly below the drawn path
            # The generated_path contains the actual drawn path in scene coordinates
            if layer_data.get("generated_path"):
                # If we have a generated path, get its scene bounds
                try:
                    from automataii.generation.utils import utils_qpainterpath_to_numpy_array
                    path_np = utils_qpainterpath_to_numpy_array(layer_data["generated_path"])
                    if path_np is not None and len(path_np) > 0:
                        # Get the X center of the path and the lowest Y point
                        path_x_center = np.mean(path_np[:, 0])
                        path_y_max = np.max(path_np[:, 1])  # Maximum Y (lowest point in Qt coordinates)
                        
                        # Place CAM directly below the path
                        # Use the X center of the path and position Y below the lowest point
                        cam_pos = [float(path_x_center), float(path_y_max) + 80]
                        layer_data["cam_position"] = cam_pos
                        
                        # Set center_x and center_y in params for the CamEditor
                        layer_data["params"]["center_x"] = cam_pos[0]
                        layer_data["params"]["center_y"] = cam_pos[1]
                        
                        logging.info(f"[CAM] Positioned at X={cam_pos[0]:.1f}, Y={cam_pos[1]:.1f} (below path)")
                    else:
                        # Fallback to character position
                        char_pos = self._get_character_position()
                        layer_data["cam_position"] = char_pos
                        layer_data["params"]["center_x"] = char_pos[0]
                        layer_data["params"]["center_y"] = char_pos[1]
                except Exception as e:
                    logging.warning(f"[CAM] Could not extract path position: {e}")
                    char_pos = self._get_character_position()
                    layer_data["cam_position"] = char_pos
                    layer_data["params"]["center_x"] = char_pos[0]
                    layer_data["params"]["center_y"] = char_pos[1]
            else:
                # Fallback to character position if no path data
                char_pos = self._get_character_position()
                layer_data["cam_position"] = char_pos
                layer_data["params"]["center_x"] = char_pos[0]
                layer_data["params"]["center_y"] = char_pos[1]

            # Create custom transform for CAM placement
            if not graphics_data.get("transform_params"):
                graphics_data["transform_params"] = {
                    "center": [0, 0],
                    "scale": 1.0,
                    "rotation": 0
                }

        # Add mechanism layer
        self._add_mechanism_layer(graphics_data["name"], layer_data)

        # Handle visual creation
        self.handle_mechanism_visuals(graphics_data)

    def _preview_mechanism(self, mechanism_data: dict[str, Any]):
        """Preview a mechanism without adding it to the layers."""
        # Clear any existing preview items safely
        if hasattr(self, '_preview_items'):
            for item in self._preview_items:
                try:
                    if item and hasattr(item, 'scene') and item.scene():
                        self.mechanism_scene.removeItem(item)
                except RuntimeError:
                    # Item was already deleted by Qt - ignore
                    logging.debug("Preview item already deleted by Qt, skipping removal")
                    pass
        self._preview_items = []

        # Create temporary visuals for the preview
        mechanism_type_value = mechanism_data.get('type', 'Unknown')
        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage",
            "4-bar Coupler": "4_bar_linkage",  # From dataset
            "Cam & Follower": "cam",
            "Cam-Follower": "cam",  # From dataset
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
            "Simple Gear": "gear",  # From dataset
            "Planetary Gear": "planetary_gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        if internal_type == "4_bar_linkage":
            visual_items = self._create_4bar_linkage_visuals(mechanism_data)
            self._preview_items.extend(visual_items)


    def _clear_mechanism_for_part(self, part_name: str):
        """Clear mechanism for a specific part only, keeping others intact."""
        # CRITICAL: Clear animation cache when clearing mechanism
        self._clear_animation_cache()

        mechanisms_to_remove = []

        # Find mechanisms for this part
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if layer_data.get("part_name") == part_name:
                mechanisms_to_remove.append(mechanism_id)

                # Remove visual items safely
                visual_items = layer_data.get("visual_items", [])
                self._safe_remove_visual_items(visual_items)

                # CRITICAL FIX: Clear mechanism trace completely using dedicated function
                self._clear_mechanism_trace(mechanism_id)

        # Remove from mechanism_layers
        for mechanism_id in mechanisms_to_remove:
            del self.mechanism_layers[mechanism_id]
            logging.info(f"[MECHANISM TAB] Removed mechanism {mechanism_id} for part {part_name}")

        # Clear enabled state for this part
        if part_name in self.mechanism_enabled_state:
            del self.mechanism_enabled_state[part_name]
        
        # CRITICAL: Clear any mechanism path items for this part to prevent duplicate paths
        if part_name in self.mechanism_path_items:
            path_item = self.mechanism_path_items[part_name]
            if path_item and path_item.scene():
                self.mechanism_scene.removeItem(path_item)
            del self.mechanism_path_items[part_name]
            logging.debug(f"[MECHANISM TAB] Cleared mechanism path item for part {part_name}")

    def _generate_mechanism_from_candidate(self, candidate_data: dict[str, Any]):
        """Generates a mechanism layer and visuals from a selected candidate."""
        # CHANGED: Support multiple mechanisms - only clear mechanism for current part
        if hasattr(self, 'selected_part_name') and self.selected_part_name:
            self._clear_mechanism_for_part(self.selected_part_name)
            
            # CRITICAL: Also clear any old trace paths for ALL mechanisms of this part
            # This ensures no duplicate paths remain when switching mechanisms
            for mechanism_id in list(self.mechanism_trace_items.keys()):
                layer_data = self.mechanism_layers.get(mechanism_id)
                if layer_data and layer_data.get("part_name") == self.selected_part_name:
                    self._clear_mechanism_trace(mechanism_id)
        else:
            logging.warning("[MECHANISM TAB] No selected part - creating mechanism anyway")

        mechanism_id = str(uuid.uuid4())[:8]
        mechanism_type_value = candidate_data.get('type', 'Unknown')
        raw_params = candidate_data.get('parameters', {})
        params = convert_json_params_to_internal(mechanism_type_value, raw_params)

        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage",
            "4-bar Coupler": "4_bar_linkage",  # From dataset
            "Cam & Follower": "cam",
            "Cam-Follower": "cam",  # From dataset
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
            "Simple Gear": "gear",  # From dataset
            "Planetary Gear": "planetary_gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        layer_name = self.selected_part_name
        target_path = self.path_data.get(self.selected_part_name)

        layer_data = {
            "id": mechanism_id,
            "type": internal_type,
            "part_name": self.selected_part_name,
            "params": params,
            "visual_items": [],
            "generated_path": target_path,
            "transform_params": candidate_data.get("transform_params"),
            "visualization_params": candidate_data.get("visualization_params"),
            "key_points": candidate_data.get("key_points"),
            "original_json_type": candidate_data.get("original_json_type"),
            "path_normalization": candidate_data.get("path_normalization", {}),
            "full_simulation_data": candidate_data.get("full_simulation_data", {}),
            "reverse_direction": False,  # Can be set to True to reverse mechanism animation direction
        }

        # Generate key_points from full_simulation_data if missing (critical for animation)
        if not layer_data.get("key_points") and layer_data.get("full_simulation_data"):
            layer_data["key_points"] = self._extract_key_points_from_simulation(
                layer_data["full_simulation_data"], internal_type
            )

        # CRITICAL FIX: For CAM mechanisms, ensure center_x and center_y are in params
        if internal_type == "cam":
            # Calculate CAM position based on the drawn path
            if target_path and not target_path.isEmpty():
                try:
                    path_np = utils_qpainterpath_to_numpy_array(target_path)
                    if path_np is not None and len(path_np) > 0:
                        # Get the X center of the path and the lowest Y point
                        path_x_center = np.mean(path_np[:, 0])
                        path_y_max = np.max(path_np[:, 1])  # Maximum Y (lowest point in Qt coordinates)
                        
                        # Place CAM directly below the path
                        cam_pos = [float(path_x_center), float(path_y_max) + 80]
                        layer_data["cam_position"] = cam_pos
                        
                        # Set center_x and center_y in params for the CamEditor
                        layer_data["params"]["center_x"] = cam_pos[0]
                        layer_data["params"]["center_y"] = cam_pos[1]
                        
                        logging.info(f"[CAM] Set center position to ({cam_pos[0]:.1f}, {cam_pos[1]:.1f})")
                except Exception as e:
                    logging.warning(f"[CAM] Could not extract path position: {e}")
                    # Fallback to default position
                    layer_data["params"]["center_x"] = 400
                    layer_data["params"]["center_y"] = 300
            else:
                # No path available, use default position
                layer_data["params"]["center_x"] = 400
                layer_data["params"]["center_y"] = 300

        # Verify and adjust coupler point connection to skeleton joint
        self._verify_coupler_joint_connection(layer_data)
        self._adjust_mechanism_to_target_joint(layer_data)

        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, params, layer_data)

        # Ensure current_editor_items is populated with parts data for blueprint export
        if not self.current_editor_items and self.parts_data:
            # Get current parts data from project manager if not already populated
            current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts_data:
                self.set_parts_data(current_parts_data)

        # Update blueprint button state now that parts are available
        self._update_blueprint_button_state()

        # Log mechanism attachment information
        skeleton_attachment = layer_data.get("skeleton_attachment", {})
        mechanism_layout = layer_data.get("mechanism_layout", {})
        if skeleton_attachment:
            attachment_point = skeleton_attachment.get("attachment_point", "unknown")
            attachment_desc = skeleton_attachment.get("description", "")

        if mechanism_layout:
            layout_desc = mechanism_layout.get("description", "")
            coord_system = mechanism_layout.get("coordinate_system", {})

        # Select the part that got the mechanism in the list
        part_name = layer_data.get("part_name")
        if part_name:
            for i in range(self.mechanism_layers_list.count()):
                item = self.mechanism_layers_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == part_name:
                    self.mechanism_layers_list.setCurrentItem(item)
                    break


    def _verify_coupler_joint_connection(self, layer_data: dict):
        """Verify that the mechanism attachment point is properly connected to the target skeleton joint."""
        part_name = layer_data.get("part_name")
        if not part_name or part_name not in self.parts_data:
            return

        part_info = self.parts_data[part_name]
        anchor_joint_id = part_info.anchor_joint_id

        # Get the target joint position from cached skeleton data
        if (hasattr(self, '_initial_skeleton_data_cache') and
            self._initial_skeleton_data_cache and
            anchor_joint_id in self._initial_skeleton_data_cache.get("joints", {})):

            joint_data = self._initial_skeleton_data_cache["joints"][anchor_joint_id]
            target_joint_pos = np.array(joint_data.get("position", [0, 0]))

            # Get mechanism attachment info from dataset
            skeleton_attachment = layer_data.get("skeleton_attachment", {})
            attachment_coords = skeleton_attachment.get("attachment_coordinates")
            attachment_point = skeleton_attachment.get("attachment_point", "unknown")

            if attachment_coords:
                # Use the specified attachment coordinates from dataset
                to_scene_coords = self._get_scene_transform_function(layer_data)
                if to_scene_coords:
                    attachment_scene_pos = to_scene_coords(np.array(attachment_coords))
                    initial_pos_np = np.array([attachment_scene_pos.x(), attachment_scene_pos.y()])
                    distance = np.linalg.norm(initial_pos_np - target_joint_pos)

                    if distance > 50:  # Threshold for "close enough" in scene coordinates
                        logging.warning(f"Attachment point ({attachment_point}) far from target joint {anchor_joint_id}: distance = {distance:.1f}")
                        logging.warning(f"Target joint: {target_joint_pos}, Attachment: {initial_pos_np}")
            else:
                # Fallback to calculating mechanism output
                initial_coupler_pos = self._calculate_mechanism_output(
                    layer_data["type"], layer_data["params"], 0.0, layer_data
                )

                if initial_coupler_pos:
                    initial_pos_np = np.array([initial_coupler_pos.x(), initial_coupler_pos.y()])
                    distance = np.linalg.norm(initial_pos_np - target_joint_pos)

                    if distance > 50:  # Threshold for "close enough" in scene coordinates
                        logging.warning(f"Mechanism output point far from target joint {anchor_joint_id}: distance = {distance:.1f}")
                        logging.warning(f"Target joint: {target_joint_pos}, Output: {initial_pos_np}")

    def _adjust_mechanism_to_target_joint(self, layer_data: dict):
        """Adjust mechanism positioning so coupler point aligns with target skeleton joint."""
        part_name = layer_data.get("part_name")
        if not part_name or part_name not in self.parts_data:
            return

        part_info = self.parts_data[part_name]
        anchor_joint_id = part_info.anchor_joint_id

        # Get the target joint position from cached skeleton data
        if (hasattr(self, '_initial_skeleton_data_cache') and
            self._initial_skeleton_data_cache and
            anchor_joint_id in self._initial_skeleton_data_cache.get("joints", {})):

            joint_data = self._initial_skeleton_data_cache["joints"][anchor_joint_id]
            target_joint_pos = np.array(joint_data.get("position", [0, 0]))

            # Calculate the current mechanism coupler point position
            current_coupler_pos = self._calculate_mechanism_output(
                layer_data["type"], layer_data["params"], 0.0, layer_data
            )

            if current_coupler_pos:
                current_pos_np = np.array([current_coupler_pos.x(), current_coupler_pos.y()])
                offset = target_joint_pos - current_pos_np

                # Simple offset adjustment - modify the target center directly
                full_sim_data = layer_data.get("full_simulation_data", {})
                if "coupler_path" in full_sim_data:
                    # Calculate required adjustment in mechanism space
                    target_path = layer_data.get("generated_path")
                    if target_path:
                        user_path_np = utils_qpainterpath_to_numpy_array(target_path)
                        if user_path_np is not None:
                            target_center_np = np.mean(user_path_np, axis=0)

                            # Adjust target center to align with skeleton joint
                            new_target_center = target_center_np + offset

                            # Store the adjustment for the transform function
                            layer_data["_target_center_adjustment"] = new_target_center.tolist()
                else:
                    logging.warning("Cannot adjust mechanism: missing full simulation data")

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the internal data structure (no separate UI display)"""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data
        # Don't add separate mechanism item to list - mechanisms are shown through part highlighting
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)

        # Update parametric edit button state
        self._update_parametric_button_state()

        # Refresh the parts list to show mechanism assignment
        self._update_mechanism_layers_list()

        # Initialize path tracing for this mechanism
        self._init_mechanism_path_trace(mechanism_id)


    def _get_scene_transform_function(self, layer_data: dict) -> Callable | None:
        """
        Creates proper coordinate transformation using recommendation system's transform_params.
        This ensures mechanism animations match the recommended mechanism orientation and scale.

        ULTRATHINK: Added safety checks to prevent abnormal coordinate values.
        """
        # Get transformation parameters from recommendation system
        transform_params = layer_data.get("transform_params")
        target_path = layer_data.get("generated_path")

        if not transform_params or not target_path:
            # Fallback: simple centering
            scene_center = QPointF(400, 300)
            return lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y()) if len(p) == 2 else scene_center

        try:
            # Extract transformation parameters (same as recommendation dialog)
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            # ULTRATHINK SAFETY CHECK: Validate scale
            if np.isclose(scale, 0) or scale < 1e-6 or scale > 1e6:
                logging.warning(f"[TRANSFORM] ⚠️  Invalid scale detected: {scale}, using fallback")
                scene_center = QPointF(400, 300)
                return lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y()) if len(p) == 2 else scene_center

            # ULTRATHINK SAFETY CHECK: Validate center
            if np.any(np.abs(center) > 1e6):
                logging.warning(f"[TRANSFORM] ⚠️  Invalid center detected: {center}, using fallback")
                scene_center = QPointF(400, 300)
                return lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y()) if len(p) == 2 else scene_center

            logging.info(f"[TRANSFORM] Transform params: center={center}, scale={scale:.6f}, rotation={rotation_angle:.6f}")

            # Create rotation matrix (same as recommendation dialog)
            rotation_matrix = np.array([
                [np.cos(rotation_angle), -np.sin(rotation_angle)],
                [np.sin(rotation_angle), np.cos(rotation_angle)]
            ])

            # Get user path bounds for mapping to scene space (use original path)
            try:
                user_path_np = utils_qpainterpath_to_numpy_array(target_path)
            except Exception as e:
                logging.warning(f"[TRANSFORM] Error converting path to numpy: {e}")
                user_path_np = None

            if user_path_np is None or len(user_path_np) == 0:
                scene_center = QPointF(400, 300)
                return lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y()) if len(p) == 2 else scene_center

            # Calculate user path properties for mapping
            user_center = np.mean(user_path_np, axis=0)
            user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 100.0

            # ULTRATHINK SAFETY CHECK: Validate user_scale
            if user_scale < 10 or user_scale > 10000:
                logging.warning(f"[TRANSFORM] ⚠️  Invalid user_scale: {user_scale}, clamping to reasonable range")
                user_scale = np.clip(user_scale, 50, 1000)

            logging.info(f"[TRANSFORM] User path: center={user_center}, bbox={user_bbox}, scale={user_scale}")

            def to_scene_coords(p_orig: np.ndarray) -> QPointF:
                """
                Apply the EXACT same transformation as recommendation system:
                1. Center the point (subtract mechanism center)
                2. Scale down to normalized space
                3. Apply rotation
                4. Map to user path space

                ULTRATHINK: Added safety checks at each step.
                """
                if p_orig is None or len(p_orig) != 2:
                    return QPointF(user_center[0], user_center[1])

                try:
                    # ULTRATHINK SAFETY CHECK: Validate input point
                    if np.any(np.abs(p_orig) > 1e6):
                        logging.warning(f"[TRANSFORM] ⚠️  Abnormal input point: {p_orig}, using fallback")
                        return QPointF(user_center[0], user_center[1])

                    # Apply same transformation as align_and_compare_paths
                    p_centered = p_orig - center                    # Center

                    # ULTRATHINK SAFETY CHECK: Check centered result
                    if np.any(np.abs(p_centered) > 1e6):
                        logging.warning(f"[TRANSFORM] ⚠️  Abnormal centered point: {p_centered}, using reduced values")
                        p_centered = np.clip(p_centered, -1e4, 1e4)

                    p_scaled = p_centered / scale                   # Scale to normalized space

                    # ULTRATHINK SAFETY CHECK: Check scaled result
                    if np.any(np.abs(p_scaled) > 1e4):
                        logging.warning(f"[TRANSFORM] ⚠️  Abnormal scaled point: {p_scaled}, clamping")
                        p_scaled = np.clip(p_scaled, -1e3, 1e3)

                    p_rotated = p_scaled @ rotation_matrix.T        # Apply rotation

                    # Transform from normalized space to user path space
                    final_point = p_rotated * user_scale + user_center

                    # ULTRATHINK SAFETY CHECK: Final validation
                    if np.any(np.abs(final_point) > 1e5):
                        logging.warning(f"[TRANSFORM] ⚠️  Abnormal final point: {final_point}, using user center")
                        return QPointF(user_center[0], user_center[1])

                    result = QPointF(float(final_point[0]), float(final_point[1]))

                    # Log first few transforms for debugging
                    if not hasattr(to_scene_coords, '_debug_count'):
                        to_scene_coords._debug_count = 0

                    if to_scene_coords._debug_count < 5:
                        logging.info(f"[TRANSFORM] #{to_scene_coords._debug_count}: {p_orig} -> {result}")
                        to_scene_coords._debug_count += 1

                    return result

                except (ValueError, TypeError, IndexError, ZeroDivisionError, OverflowError) as e:
                    # Robust fallback
                    logging.warning(f"[TRANSFORM] ⚠️  Transform error: {e}, using fallback")
                    return QPointF(user_center[0], user_center[1])

            return to_scene_coords

        except (KeyError, ValueError, TypeError) as e:
            logging.warning(f"Error creating transform function: {e}")
            # Fallback: simple centering
            scene_center = QPointF(400, 300)
            return lambda p: QPointF(p[0] * 2.0 + scene_center.x(), p[1] * 2.0 + scene_center.y()) if len(p) == 2 else scene_center

    def _get_inverse_scene_transform_function(self, layer_data: dict) -> Callable | None:
        """
        Returns a function that converts a scene-space QPointF back to the mechanism's
        original coordinate space used by the recommendation system. This is the
        exact inverse of `_get_scene_transform_function`.

        ULTRATHINK: Added safety checks to prevent abnormal coordinate values.
        """
        transform_params = layer_data.get("transform_params")
        target_path = layer_data.get("generated_path")

        if not transform_params or not target_path:
            return None

        try:
            center = np.array(transform_params["center"])
            scale = transform_params["scale"]
            rotation_angle = transform_params["rotation"]

            # ULTRATHINK SAFETY CHECK: Same validations as forward transform
            if np.isclose(scale, 0) or scale < 1e-6 or scale > 1e6:
                logging.warning(f"[INV_TRANSFORM] ⚠️  Invalid scale detected: {scale}")
                return None

            if np.any(np.abs(center) > 1e6):
                logging.warning(f"[INV_TRANSFORM] ⚠️  Invalid center detected: {center}")
                return None

            # Rotation matrix is orthonormal; inverse is transpose
            rotation_matrix = np.array([
                [np.cos(rotation_angle), -np.sin(rotation_angle)],
                [np.sin(rotation_angle),  np.cos(rotation_angle)],
            ])

            user_path_np = utils_qpainterpath_to_numpy_array(target_path)
            if user_path_np is None or len(user_path_np) == 0:
                return None

            user_center = np.mean(user_path_np, axis=0)
            user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
            user_scale = np.max(user_bbox) / 2.0 if np.max(user_bbox) > 0 else 100.0

            # ULTRATHINK SAFETY CHECK: Validate user_scale
            if user_scale < 10 or user_scale > 10000:
                logging.warning(f"[INV_TRANSFORM] ⚠️  Invalid user_scale: {user_scale}, clamping to reasonable range")
                user_scale = np.clip(user_scale, 50, 1000)

            def to_mechanism_coords(scene_point: QPointF) -> np.ndarray:
                """
                Inverse transformation with safety checks.
                """
                try:
                    # ULTRATHINK SAFETY CHECK: Validate input scene point
                    if abs(scene_point.x()) > 1e5 or abs(scene_point.y()) > 1e5:
                        logging.warning(f"[INV_TRANSFORM] ⚠️  Abnormal scene point: ({scene_point.x()}, {scene_point.y()}), clamping")
                        scene_point = QPointF(
                            np.clip(scene_point.x(), -1e4, 1e4),
                            np.clip(scene_point.y(), -1e4, 1e4)
                        )

                    # g = (scene - user_center)/user_scale
                    g = np.array([scene_point.x(), scene_point.y()])
                    g = (g - user_center) / user_scale

                    # ULTRATHINK SAFETY CHECK: Check intermediate result
                    if np.any(np.abs(g) > 1e3):
                        logging.warning(f"[INV_TRANSFORM] ⚠️  Abnormal normalized point: {g}, clamping")
                        g = np.clip(g, -1e3, 1e3)

                    # ((p - center)/scale) = g @ R
                    p_scaled = g @ rotation_matrix
                    p_orig = center + scale * p_scaled

                    # ULTRATHINK SAFETY CHECK: Validate final result
                    if np.any(np.abs(p_orig) > 1e5):
                        logging.warning(f"[INV_TRANSFORM] ⚠️  Abnormal final mechanism point: {p_orig}, clamping")
                        p_orig = np.clip(p_orig, -1e4, 1e4)

                    return p_orig

                except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
                    logging.warning(f"[INV_TRANSFORM] ⚠️  Transform error: {e}, using default")
                    return center  # Return mechanism center as fallback

            return to_mechanism_coords

        except (KeyError, ValueError, TypeError) as e:
            logging.warning(f"[INV_TRANSFORM] ⚠️  Error creating inverse transform: {e}")
            return None

    def _extract_key_points_from_simulation(self, full_sim_data: dict, mechanism_type: str) -> dict:
        """Extract key_points from full_simulation_data to enable proper animation."""
        key_points = {}

        try:
            if mechanism_type == "4_bar_linkage" and "joint_positions" in full_sim_data:
                joint_pos = full_sim_data["joint_positions"]
                # Extract initial positions as key points
                if "p1_positions" in joint_pos and len(joint_pos["p1_positions"]) > 0:
                    key_points["ground_pivot_1"] = joint_pos["p1_positions"][0]
                if "p2_positions" in joint_pos and len(joint_pos["p2_positions"]) > 0:
                    key_points["ground_pivot_2"] = joint_pos["p2_positions"][0]
                if "p3_positions" in joint_pos and len(joint_pos["p3_positions"]) > 0:
                    key_points["crank_end"] = joint_pos["p3_positions"][0]
                if "p4_positions" in joint_pos and len(joint_pos["p4_positions"]) > 0:
                    key_points["rocker_end"] = joint_pos["p4_positions"][0]

            elif mechanism_type == "cam" and "cam_data" in full_sim_data:
                cam_data = full_sim_data["cam_data"]
                if "cam_centers" in cam_data and len(cam_data["cam_centers"]) > 0:
                    key_points["cam_center"] = cam_data["cam_centers"][0]
                if "follower_y_positions" in cam_data and len(cam_data["follower_y_positions"]) > 0:
                    key_points["follower_position"] = [0, cam_data["follower_y_positions"][0]]

            elif mechanism_type in ["gear", "planetary_gear"] and "gear_positions" in full_sim_data:
                gear_pos = full_sim_data["gear_positions"]
                if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
                    key_points["sun_center"] = gear_pos["sun_centers"][0]
                if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
                    key_points["planet_center"] = gear_pos["planet_centers"][0]

            elif mechanism_type == "simple_gear" and "gear_data" in full_sim_data:
                gear_data = full_sim_data["gear_data"]
                if "gear1_centers" in gear_data and len(gear_data["gear1_centers"]) > 0:
                    key_points["gear1_center"] = gear_data["gear1_centers"][0]
                if "gear2_centers" in gear_data and len(gear_data["gear2_centers"]) > 0:
                    key_points["gear2_center"] = gear_data["gear2_centers"][0]

        except (KeyError, IndexError, TypeError) as e:
            logging.warning(f"Error extracting key_points for {mechanism_type}: {e}")
            # Fallback key points
            key_points = {"center": [0, 0], "reference": [50, 0]}

        return key_points

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, layer_data: dict) -> QPointF | None:
        """Calculates mechanism output point using dataset's joint positions for perfect consistency with visuals."""
        full_sim_data = layer_data.get("full_simulation_data", {})


        if mech_type == "4_bar_linkage" and "joint_positions" in full_sim_data:
            # Use joint positions to calculate coupler point - SAME AS VISUALS
            joint_positions = full_sim_data["joint_positions"]
            to_scene_coords = self._get_scene_transform_function(layer_data)

            if "p1_positions" in joint_positions and to_scene_coords:
                num_frames = len(joint_positions["p1_positions"])
                normalized_time = time / (2 * math.pi)

                # MECHANISM DIRECTION FIX: Check if mechanism should run in reverse
                # Try both directions and pick the one that matches expected motion
                reverse_direction = layer_data.get("reverse_direction", False)
                if reverse_direction:
                    normalized_time = 1.0 - normalized_time

                frame_index = int(normalized_time * (num_frames - 1))
                frame_index = max(0, min(frame_index, num_frames - 1))


                # Get exact positions from dataset (SAME AS VISUALS)
                p3 = np.array(joint_positions["p3_positions"][frame_index])
                p4 = np.array(joint_positions["p4_positions"][frame_index])

                # Calculate coupler point using same method as dataset generation
                coupler_point_x = params.get("coupler_point_x", 0.0)
                coupler_point_y = params.get("coupler_point_y", 0.0)

                # Calculate coupler point position relative to the coupler link (p3-p4)
                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                else:
                    p_coupler = p3


                # Apply the same transformation as the visuals
                scene_point = to_scene_coords(p_coupler)
                return scene_point
            else:
                pass
                return None

        elif mech_type == "cam":
            # First try to use full_simulation_data from dataset
            full_sim_data = layer_data.get("full_simulation_data", {})
            cam_data = full_sim_data.get("cam_data", {})
            to_scene_coords = self._get_scene_transform_function(layer_data)

            if cam_data and "follower_y_positions" in cam_data and to_scene_coords:
                follower_positions = cam_data["follower_y_positions"]
                num_frames = len(follower_positions)
                if num_frames > 0:
                    # Fix frame index calculation - remove modulo to prevent jumping
                    normalized_time = (time / (2 * math.pi)) % 1.0  # Keep in [0, 1] range
                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))  # Clamp to valid range
                    follower_y = follower_positions[frame_index]
                    follower_pos_orig = np.array([0, follower_y])

                    scene_point = to_scene_coords(follower_pos_orig)
                    return scene_point

            # Fallback calculation using EXACT same formula as dataset generator with Y-axis flip
            params = layer_data.get("params", {})
            base_radius = params.get("base_radius", 25.0)
            eccentricity = params.get("eccentricity", 10.0)

            if to_scene_coords:
                # Y-axis flipped coordinate transform for cam-below orientation
                def to_scene_coords_flipped(p):
                    p_flipped = np.array([p[0], -p[1]])
                    return to_scene_coords(p_flipped)

                # Use EXACT same calculation as simulate_cam_motion() in dataset generator
                angle = time
                cam_offset = np.array([eccentricity, 0])  # Same as dataset
                rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                rotated_center = rotation_matrix @ cam_offset
                follower_y = rotated_center[1] + base_radius  # Exact dataset formula
                follower_pos_orig = np.array([0, follower_y])

                scene_point = to_scene_coords_flipped(follower_pos_orig)
                return scene_point
            else:
                return None

        elif mech_type == "gear":
            # First try to use full_simulation_data from dataset
            full_sim_data = layer_data.get("full_simulation_data", {})
            gear_data = full_sim_data.get("gear_data", {})
            to_scene_coords = self._get_scene_transform_function(layer_data)

            if gear_data and "tracking_points" in gear_data and to_scene_coords:
                tracking_points = gear_data["tracking_points"]
                num_frames = len(tracking_points)
                if num_frames > 0:
                    # Fix frame index calculation - remove modulo to prevent jumping
                    normalized_time = (time / (2 * np.pi)) % 1.0  # Keep in [0, 1] range
                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))  # Clamp to valid range

                    # Use the tracking point directly from dataset
                    tracking_point = np.array(tracking_points[frame_index])

                    scene_point = to_scene_coords(tracking_point)
                    return scene_point

            # Fallback to manual calculation if no simulation data
            params = layer_data.get("params", {})
            r1 = params.get("r1", 30)
            key_points = layer_data.get("key_points", {})

            if to_scene_coords:
                # Use gear center from key_points if available
                if "gear1_center" in key_points:
                    gear1_center = np.array(key_points["gear1_center"])
                else:
                    gear1_center = np.array([0, 0])  # Default - match dataset generator

                # Calculate point on gear 1 circumference
                theta1 = time
                output_point_orig = gear1_center + np.array([r1 * np.cos(theta1), r1 * np.sin(theta1)])

                scene_point = to_scene_coords(output_point_orig)
                return scene_point
            else:
                return None

        elif mech_type == "planetary_gear":
            # Handle planetary gear using full_simulation_data
            full_sim_data = layer_data.get("full_simulation_data", {})
            gear_positions = full_sim_data.get("gear_positions", {})
            to_scene_coords = self._get_scene_transform_function(layer_data)

            if gear_positions and "tracking_points" in gear_positions and to_scene_coords:
                tracking_points = gear_positions["tracking_points"]
                num_frames = len(tracking_points)
                if num_frames > 0:
                    # Fix frame index calculation - remove modulo to prevent jumping
                    normalized_time = (time / (2 * np.pi)) % 1.0  # Keep in [0, 1] range
                    frame_index = int(normalized_time * (num_frames - 1))
                    frame_index = max(0, min(frame_index, num_frames - 1))  # Clamp to valid range

                    # Use the tracking point directly from dataset
                    tracking_point = np.array(tracking_points[frame_index])

                    scene_point = to_scene_coords(tracking_point)
                    return scene_point

            # Fallback calculation for planetary gear
            params = layer_data.get("params", {})
            r_sun = params.get("r_sun", 20)
            r_planet = params.get("r_planet", 30)
            arm_length = params.get("arm_length", 15)

            if to_scene_coords:
                # Calculate planetary gear positions manually
                planet_orbital_angle = time
                planet_rotation_angle = -time * (r_sun / r_planet)

                # Sun is stationary at origin
                sun_center_orig = np.array([0, 0])

                # Planet center orbits around sun
                planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                    np.cos(planet_orbital_angle),
                    np.sin(planet_orbital_angle)
                ])

                # Tracking point on planet
                tracking_point_orig = planet_center_orig + arm_length * np.array([
                    np.cos(planet_rotation_angle),
                    np.sin(planet_rotation_angle)
                ])

                scene_point = to_scene_coords(tracking_point_orig)
                return scene_point

            # Fallback calculation for planetary gear
            return None

        else:
            # Fallback to manual calculation if no simulation data
            return self._calculate_mechanism_output_manual(mech_type, params, time, layer_data)

    def _calculate_mechanism_output_manual(self, mech_type: str, params: dict, time: float, layer_data: dict) -> QPointF | None:
        """Manual calculation fallback (original implementation)."""
        key_points = layer_data.get("key_points")
        output_point_orig = None

        if mech_type == "4_bar_linkage":
            if not key_points or not params:
                return None

            l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
            p1_coords, p2_coords = key_points.get("ground_pivot_1"), key_points.get("ground_pivot_2")
            coupler_point_x, coupler_point_y = params.get("coupler_point_x", 0), params.get("coupler_point_y", 0)

            if not all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
                 return None

            # Use default coupler point if None (reduce logging spam)
            if coupler_point_x is None:
                coupler_point_x = 0.0
            if coupler_point_y is None:
                coupler_point_y = 0.0

            p1, p2 = np.array(p1_coords, dtype=float), np.array(p2_coords, dtype=float)
            p3 = p1 + np.array([l2 * math.cos(time), l2 * math.sin(time)])

            d_sq = np.sum((p2 - p3)**2)
            d = np.sqrt(d_sq)
            if not (abs(l3 - l4) <= d <= (l3 + l4)):
                return None

            a = (l3**2 - l4**2 + d_sq) / (2 * d)
            h = math.sqrt(max(0, l3**2 - a**2))
            p3_p2_unit = (p2 - p3) / d
            midpoint = p3 + a * p3_p2_unit
            p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

            coupler_link_vec = p4 - p3
            coupler_link_len = np.linalg.norm(coupler_link_vec)
            if np.isclose(coupler_link_len, 0):
                return None

            coupler_local_x_axis = coupler_link_vec / coupler_link_len
            coupler_local_y_axis = np.array([-coupler_local_x_axis[1], coupler_local_x_axis[0]])

            coupler_point_offset = coupler_point_x * coupler_local_x_axis + coupler_point_y * coupler_local_y_axis
            output_point_orig = p3 + coupler_point_offset

        if output_point_orig is None:
            return None

        to_scene_coords = self._get_scene_transform_function(layer_data)
        if to_scene_coords:
            scene_point = to_scene_coords(output_point_orig)
            return scene_point
        else:
            logging.warning("No transform function available")
            return None

    def _update_animation(self):
        """
        Update animation frame by calculating mechanism outputs and setting them as targets for the IK system.
        The IK system is the single source of truth for skeleton and part animation.
        """
        # CRITICAL: Prevent animation updates when tab is not active
        if not hasattr(self, '_tab_active') or not self._tab_active:
            logging.debug("[MECHANISM TAB] Stopping animation - tab is not active")
            if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
                self.animation_timer.stop()
            return

        dt = 0.05 * self.animation_speed
        self.animation_time += dt
        if self.animation_time > 2 * math.pi:
            self.animation_time -= 2 * math.pi

        active_joint_updates = {}

        # DEBUG: Check if mechanism_layers has any data
        logging.info(f"🔍 MECHANISM DEBUG: mechanism_layers count: {len(self.mechanism_layers)}")
        if not self.mechanism_layers:
            logging.warning("🚨 MECHANISM DEBUG: mechanism_layers is empty!")
        else:
            for mech_id, layer_data in self.mechanism_layers.items():
                part_name = layer_data.get("part_name", "unknown")
                logging.info(f"🔍 MECHANISM DEBUG: Found mechanism {mech_id} for part {part_name}")

        # 1. Calculate all mechanism outputs and determine IK targets
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if not layer_data or not layer_data.get("part_name"):
                continue

            part_name = layer_data["part_name"]
            # Check if this part is enabled in the parts list
            is_enabled = self.part_enabled_state.get(part_name, True)
            if not is_enabled:
                continue

            try:
                output_pos = self._calculate_mechanism_output(
                    layer_data["type"], layer_data["params"], self.animation_time, layer_data
                )

                if output_pos:
                    # Get the correct end effector joint for this part
                    part_info = self.parts_data.get(part_name)
                    if part_info and part_info.anchor_joint_id:
                        target_joint_id = self._get_target_joint_for_mechanism_control(part_name, part_info.anchor_joint_id)

                        # Find the standardized joint ID for the IK system
                        std_joint_id = self._get_standardized_joint_id(target_joint_id)

                        # DEBUG: Log target joint conversion for all parts
                        logging.info(f"🎯 TARGET DEBUG: part_name='{part_name}', anchor_joint_id='{part_info.anchor_joint_id}', target_joint_id='{target_joint_id}', std_joint_id='{std_joint_id}'")

                        if std_joint_id:
                            # This is the target for the IK system
                            active_joint_updates[std_joint_id] = output_pos
                        else:
                            logging.warning(f"Could not find standardized joint ID for '{target_joint_id}'")

                    # Update mechanism visuals and path trace
                    self._update_mechanism_visuals_for_animation(mechanism_id, self.animation_time, layer_data)
                    self._update_mechanism_path_trace(mechanism_id, output_pos)

            except Exception as e:
                logging.error(f"Error calculating mechanism output for {mechanism_id}: {e}", exc_info=True)

        # 2. Set targets in the IK system
        if active_joint_updates and hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            ik_manager = self.main_window.ik_manager
            for joint_id, target_pos in active_joint_updates.items():
                # The IK manager will handle validation and smoothing
                ik_manager.set_mechanism_position_target(joint_id, target_pos)

        # NOTE: All part and skeleton visual updates are now handled by the signal/slot connection
        # to on_skeleton_updated, which is called after the IK manager solves the pose.
        # This simplifies the flow and makes IK the single source of truth.

    def _get_standardized_joint_id(self, abstract_joint_id: str) -> str | None:
        """Helper to find the standardized joint ID from an abstract name."""
        if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
            joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
            for orig_name, std_name in joint_map.items():
                if orig_name == abstract_joint_id:
                    return std_name
        # Fallback if not in map (e.g., might already be a std id)
        if self._initial_skeleton_data_cache and abstract_joint_id in self._initial_skeleton_data_cache.get("joints", {}):
            return abstract_joint_id
        return None

    def _update_mechanism_visuals_for_animation(self, mechanism_id: str, time: float, layer_data: dict):
        """Update mechanism visual elements during animation using exact dataset positions."""
        try:
            mech_type = layer_data.get("type")
            visual_items = layer_data.get("visual_items", [])


            if mech_type == "4_bar_linkage" and len(visual_items) >= 13:  # All visual elements including ground link and pivots
                full_sim_data = layer_data.get("full_simulation_data", {})
                to_scene_coords = self._get_scene_transform_function(layer_data)


                # Use exact joint positions from dataset for perfect consistency
                if "joint_positions" in full_sim_data and to_scene_coords:
                    joint_positions = full_sim_data["joint_positions"]

                    # Calculate which frame corresponds to current time
                    if "p1_positions" in joint_positions:
                        num_frames = len(joint_positions["p1_positions"])
                        normalized_time = time / (2 * math.pi)

                        # MECHANISM DIRECTION FIX: Apply same direction correction as output calculation
                        reverse_direction = layer_data.get("reverse_direction", False)
                        if reverse_direction:
                            normalized_time = 1.0 - normalized_time

                        frame_index = int(normalized_time * (num_frames - 1))
                        frame_index = max(0, min(frame_index, num_frames - 1))

                        # Get exact positions from dataset
                        p1 = np.array(joint_positions["p1_positions"][frame_index])
                        p2 = np.array(joint_positions["p2_positions"][frame_index])
                        p3 = np.array(joint_positions["p3_positions"][frame_index])
                        p4 = np.array(joint_positions["p4_positions"][frame_index])

                        # Calculate coupler point using same method as dataset
                        params = layer_data.get("params", {})
                        coupler_point_x = params.get("coupler_point_x", 0.0)
                        coupler_point_y = params.get("coupler_point_y", 0.0)

                        coupler_vec = p4 - p3
                        coupler_length = np.linalg.norm(coupler_vec)
                        if coupler_length > 0:
                            coupler_unit = coupler_vec / coupler_length
                            coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                            p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                        else:
                            p_coupler = p3

                        # Transform to scene coordinates
                        p1_t = to_scene_coords(p1)
                        p2_t = to_scene_coords(p2)
                        p3_t = to_scene_coords(p3)
                        p4_t = to_scene_coords(p4)
                        p_coupler_t = to_scene_coords(p_coupler)

                        # Update driver link (item 0)
                        if len(visual_items) > 0:
                            driver_link = visual_items[0]
                            if isinstance(driver_link, QGraphicsLineItem):
                                driver_link.setLine(QLineF(p1_t, p3_t))

                        # Update follower link (item 1)
                        if len(visual_items) > 1:
                            follower_link = visual_items[1]
                            if isinstance(follower_link, QGraphicsLineItem):
                                follower_link.setLine(QLineF(p2_t, p4_t))

                        # Update coupler triangle/line (item 2)
                        if len(visual_items) > 2:
                            coupler_item = visual_items[2]

                            # Check collinearity (same as dataset generator)
                            # area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2

                            if isinstance(coupler_item, QGraphicsLineItem):
                                # Update line
                                coupler_item.setLine(QLineF(p3_t, p4_t))
                            elif isinstance(coupler_item, QGraphicsPolygonItem):
                                # Update triangle
                                triangle_points = [p3_t, p4_t, p_coupler_t]
                                triangle_polygon = QPolygonF(triangle_points)
                                coupler_item.setPolygon(triangle_polygon)

                        # Ground link (item 3) doesn't need updating - it's fixed

                        # Update moving pivot positions (items 6 and 7 for outer circles, 10 and 11 for inner circles)
                        moving_pivot_positions = [p3_t, p4_t]  # Moving joints

                        # Update moving pivot outer circles (items 6-7)
                        for i, pos in enumerate(moving_pivot_positions):
                            outer_idx = 6 + i  # Moving pivots are at indices 6-7
                            inner_idx = 10 + i  # Inner highlights are at indices 10-11

                            if len(visual_items) > outer_idx:
                                outer_pivot = visual_items[outer_idx]
                                if isinstance(outer_pivot, QGraphicsEllipseItem):
                                    outer_pivot.setRect(pos.x() - 8, pos.y() - 8, 16, 16)

                            if len(visual_items) > inner_idx:
                                inner_pivot = visual_items[inner_idx]
                                if isinstance(inner_pivot, QGraphicsEllipseItem):
                                    inner_pivot.setRect(pos.x() - 4, pos.y() - 4, 8, 8)

                        # Update coupler marker (item 12)
                        if len(visual_items) > 12:
                            coupler_marker = visual_items[12]
                            if isinstance(coupler_marker, QGraphicsEllipseItem):
                                coupler_marker.setRect(p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8)


                    else:
                        pass
                else:
                    pass

            elif mech_type == "cam" and len(visual_items) >= 2:  # Cam and follower
                params = layer_data.get("params", {})
                base_radius = params.get("base_radius", 25.0)
                eccentricity = params.get("eccentricity", 10.0)

                # Get scaling factors from layer data (set during visual creation)
                cam_scale_factor = layer_data.get('cam_scale_factor', 1.0)
                rod_length_multiplier = layer_data.get('rod_length_multiplier', 1.0)

                # Apply scaling to match visual creation
                scaled_base_radius = base_radius * cam_scale_factor
                scaled_eccentricity = eccentricity * cam_scale_factor
                scaled_rod_length = params.get("follower_rod_length", 40.0) * rod_length_multiplier

                full_sim_data = layer_data.get("full_simulation_data", {})
                cam_data = full_sim_data.get("cam_data", {})

                # CRITICAL FIX: Always use the stored transform function from visual creation
                cam_to_scene_coords = layer_data.get('cam_transform_function')
                if not cam_to_scene_coords:
                    logging.warning("[CAM_ANIMATION] No stored transform function, creating fallback")
                    # Get character position for fallback
                    character_position = layer_data.get('cam_position', self._get_character_position())
                    # Fallback transform - position at character feet
                    cam_to_scene_coords = lambda p: QPointF(
                        float(p[0] + character_position[0]),
                        float(p[1] + character_position[1])
                    ) if len(p) == 2 else QPointF(character_position[0], character_position[1])

                # Calculate cam position and rotation
                if cam_data and "cam_centers" in cam_data and "follower_y_positions" in cam_data:
                    cam_centers = cam_data["cam_centers"]
                    follower_positions = cam_data["follower_y_positions"]
                    num_frames = len(cam_centers)

                    if num_frames > 0:
                        normalized_time = (time / (2 * math.pi)) % 1.0
                        frame_index = int(normalized_time * (num_frames - 1))
                        frame_index = max(0, min(frame_index, num_frames - 1))
                        current_cam_center = np.array(cam_centers[frame_index])
                        follower_y = follower_positions[frame_index]
                        follower_pos_orig = np.array([0, follower_y])
                else:
                    # Manual calculation - keep cam center fixed, move follower
                    angle = time
                    current_cam_center = np.array([0, 0])

                    # Calculate follower position based on scaled cam profile
                    lift = scaled_eccentricity * (1 + np.cos(angle)) / 2  # Egg shape formula
                    cam_radius_at_angle = scaled_base_radius + lift
                    follower_y = current_cam_center[1] - cam_radius_at_angle - scaled_rod_length
                    follower_pos_orig = np.array([0, follower_y])

                # Update egg-shaped cam with rotation
                if len(visual_items) >= 1 and isinstance(visual_items[0], QGraphicsPolygonItem):
                    # Generate egg profile (same as visual creation)
                    def create_egg_shape_profile(base_radius, eccentricity):
                        points = []
                        num_points = 100
                        for i in range(num_points):
                            theta = (i / num_points) * 2 * np.pi
                            lift = eccentricity * (1 + np.cos(theta)) / 2  # Egg shape
                            r = base_radius + lift
                            x = r * np.cos(theta)
                            y = r * np.sin(theta)
                            points.append([x, y])
                        return points

                    # Use scaled dimensions for animation
                    egg_profile = create_egg_shape_profile(scaled_base_radius, scaled_eccentricity)

                    # Apply rotation
                    rotation_angle = time
                    cos_rot = np.cos(rotation_angle)
                    sin_rot = np.sin(rotation_angle)

                    # Transform egg profile to scene coordinates
                    cam_polygon_points = []
                    for point in egg_profile:
                        # Rotate point around cam center
                        x, y = point[0], point[1]
                        x_rot = x * cos_rot - y * sin_rot
                        y_rot = x * sin_rot + y * cos_rot

                        # Position relative to cam center and transform to scene
                        rotated_point = np.array([x_rot, y_rot]) + current_cam_center
                        scene_point = cam_to_scene_coords(rotated_point)
                        cam_polygon_points.append(scene_point)

                    # Update the polygon
                    if cam_polygon_points:
                        cam_polygon = QPolygonF(cam_polygon_points)
                        visual_items[0].setPolygon(cam_polygon)

                # Update follower position with proportional size
                if len(visual_items) >= 2 and isinstance(visual_items[1], QGraphicsRectItem):
                    follower_scene = cam_to_scene_coords(follower_pos_orig)
                    follower_width, follower_height = 20, 15  # Larger for visibility
                    visual_items[1].setRect(
                        follower_scene.x() - follower_width/2,
                        follower_scene.y() - follower_height/2,
                        follower_width, follower_height
                    )

                # Update cam center marker with smaller size
                if len(visual_items) >= 3 and isinstance(visual_items[2], QGraphicsEllipseItem):
                    cam_center_scene = cam_to_scene_coords(current_cam_center)
                    visual_items[2].setRect(
                        cam_center_scene.x() - 3, cam_center_scene.y() - 3, 6, 6
                    )

                # Update rod connection line (connect from top of cam to follower)
                if len(visual_items) >= 4 and isinstance(visual_items[3], QGraphicsLineItem):
                    follower_scene = cam_to_scene_coords(follower_pos_orig)
                    # Connect from top of cam to follower
                    cam_top_orig = current_cam_center + np.array([0, -scaled_base_radius])
                    cam_top_scene = cam_to_scene_coords(cam_top_orig)
                    visual_items[3].setLine(QLineF(cam_top_scene, follower_scene))

                return

            elif mech_type == "gear" and len(visual_items) >= 4:  # Gear train
                params = layer_data.get("params", {})
                r1 = params.get("r1", 30)
                r2 = params.get("r2", 50)
                full_sim_data = layer_data.get("full_simulation_data", {})
                gear_data = full_sim_data.get("gear_data", {})
                to_scene_coords = self._get_scene_transform_function(layer_data)

                if to_scene_coords:
                    # 🔧 POSITION CONSISTENCY: Always use fixed positions to match initial creation
                    distance = r1 + r2  # Gears touching
                    gear1_center = np.array([0, 0])
                    gear2_center = np.array([distance, 0])

                    # Get rotation angles from dataset if available
                    if gear_data and "gear1_angles" in gear_data and "gear2_angles" in gear_data:
                        gear1_angles = gear_data["gear1_angles"]
                        gear2_angles = gear_data["gear2_angles"]
                        num_frames = len(gear1_angles)

                        if num_frames > 0:
                            # Use continuous rotation - don't limit to one cycle
                            # The gear should complete multiple full rotations
                            normalized_time = (time / (2 * np.pi)) % 1.0  # Get fractional part for frame lookup
                            frame_index = int(normalized_time * (num_frames - 1))
                            frame_index = max(0, min(frame_index, num_frames - 1))  # Clamp to valid range

                            # Get base angle from frame and add full rotations
                            full_rotations = int(time / (2 * np.pi))  # Number of complete rotations
                            theta1 = gear1_angles[frame_index] + full_rotations * 2 * np.pi
                            theta2 = gear2_angles[frame_index] + full_rotations * 2 * np.pi * (-r1/r2)
                    else:
                        # Fallback to manual calculation - continuous rotation
                        theta1 = time  # Direct use of time for continuous rotation
                        theta2 = -theta1 * (r1 / r2)  # Gear ratio

                    # Transform to scene coordinates
                    g1_center_scene = to_scene_coords(gear1_center)
                    g2_center_scene = to_scene_coords(gear2_center)

                    # 🔧 GEAR POSITION FIX: Calculate screen-space radii for proper positioning
                    gear1_edge_orig = gear1_center + np.array([r1, 0])
                    gear1_edge_scene = to_scene_coords(gear1_edge_orig)
                    r1_screen = QLineF(g1_center_scene, gear1_edge_scene).length()

                    gear2_edge_orig = gear2_center + np.array([r2, 0])
                    gear2_edge_scene = to_scene_coords(gear2_edge_orig)
                    r2_screen = QLineF(g2_center_scene, gear2_edge_scene).length()

                    # Update gear visual positions (assuming items 0,1 are gear bodies, 2,3 are indicators)
                    if len(visual_items) >= 2:
                        # 🔧 GEAR BODY FIX: Update ellipse rect directly instead of setPos
                        if hasattr(visual_items[0], 'setRect'):
                            visual_items[0].setRect(
                                g1_center_scene.x() - r1_screen, g1_center_scene.y() - r1_screen,
                                r1_screen * 2, r1_screen * 2
                            )
                        if hasattr(visual_items[1], 'setRect'):
                            visual_items[1].setRect(
                                g2_center_scene.x() - r2_screen, g2_center_scene.y() - r2_screen,
                                r2_screen * 2, r2_screen * 2
                            )

                    # Update gear rotation indicators (lines)
                    if len(visual_items) >= 4:
                        # Gear 1 indicator - use screen-space radius
                        if isinstance(visual_items[2], QGraphicsLineItem):
                            end1 = g1_center_scene + QPointF(r1_screen * math.cos(theta1), r1_screen * math.sin(theta1))
                            visual_items[2].setLine(QLineF(g1_center_scene, end1))

                        # Gear 2 indicator - use screen-space radius
                        if isinstance(visual_items[3], QGraphicsLineItem):
                            end2 = g2_center_scene + QPointF(r2_screen * math.cos(theta2), r2_screen * math.sin(theta2))
                            visual_items[3].setLine(QLineF(g2_center_scene, end2))

                    return

            elif mech_type == "planetary_gear" and len(visual_items) >= 5:  # Planetary gear
                params = layer_data.get("params", {})
                r_sun = params.get("r_sun", 20)
                r_planet = params.get("r_planet", 30)
                arm_length = params.get("arm_length", 15)
                to_scene_coords = self._get_scene_transform_function(layer_data)

                if to_scene_coords:
                    # Calculate normalized time for all planetary gear calculations
                    normalized_time = time / (2 * math.pi)

                    # Apply direction correction if needed
                    reverse_direction = layer_data.get("reverse_direction", False)
                    if reverse_direction:
                        normalized_time = 1.0 - normalized_time

                    # Use dataset planetary gear data if available
                    full_sim_data = layer_data.get("full_simulation_data", {})
                    gear_positions = full_sim_data.get("gear_positions", {})

                    if gear_positions and "planet_centers" in gear_positions:
                        # Use exact dataset positions
                        planet_centers = gear_positions.get("planet_centers", [])
                        sun_centers = gear_positions.get("sun_centers", [])
                        tracking_points = gear_positions.get("tracking_points", [])

                        if planet_centers and sun_centers and tracking_points:
                            # Calculate proper frame index for multi-revolution planetary motion
                            num_frames = len(planet_centers)
                            frame_index = int(normalized_time * (num_frames - 1))
                            frame_index = max(0, min(frame_index, num_frames - 1))

                            sun_center_orig = np.array(sun_centers[frame_index])
                            planet_center_orig = np.array(planet_centers[frame_index])
                            tracking_point_orig = np.array(tracking_points[frame_index])
                        else:
                            # Fallback to single revolution calculation
                            planet_orbital_angle = time
                            planet_rotation_angle = -time * (r_sun / r_planet)
                            sun_center_orig = np.array([0, 0])
                            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                                np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
                            ])
                            tracking_point_orig = planet_center_orig + arm_length * np.array([
                                np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
                            ])
                    else:
                        # Fallback to single revolution calculation
                        planet_orbital_angle = time
                        planet_rotation_angle = -time * (r_sun / r_planet)
                        sun_center_orig = np.array([0, 0])
                        planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([
                            np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
                        ])
                        tracking_point_orig = planet_center_orig + arm_length * np.array([
                            np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
                        ])

                    # Transform to scene coordinates
                    planet_center_scene = to_scene_coords(planet_center_orig)
                    tracking_scene = to_scene_coords(tracking_point_orig)

                    # Update planet gear position (item 1)
                    if len(visual_items) > 1 and isinstance(visual_items[1], QGraphicsEllipseItem):
                        # Calculate screen radius for proper positioning
                        planet_edge_orig = planet_center_orig + np.array([r_planet, 0])
                        planet_edge_scene = to_scene_coords(planet_edge_orig)
                        r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

                        # Use setRect instead of setPos to properly position the ellipse
                        visual_items[1].setRect(
                            planet_center_scene.x() - r_planet_screen,
                            planet_center_scene.y() - r_planet_screen,
                            r_planet_screen * 2,
                            r_planet_screen * 2
                        )

                    # Update arm line (item 2)
                    if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
                        visual_items[2].setLine(QLineF(
                            planet_center_scene,
                            tracking_scene
                        ))

                    # Update tracking point marker (item 3)
                    if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsEllipseItem):
                        visual_items[3].setRect(
                            tracking_scene.x() - 8,
                            tracking_scene.y() - 8,
                            16, 16
                        )


                    return

        except Exception as e:
            logging.warning(f"Error updating mechanism visuals for {mechanism_id}: {e}")


    def _display_paths_in_preview(self):
        """Display motion paths from editor tab in the preview"""
        logging.debug(f"[MECHANISM TAB] _display_paths_in_preview called with {len(self.path_data)} paths")

        # Clear ALL existing path-related items to prevent accumulation
        # 1. Clear user path visual items
        for item in self.path_visual_items.values():
            if item.scene():
                self.mechanism_scene.removeItem(item)
        self.path_visual_items.clear()
        
        # 2. Clear mechanism path items (paths generated by mechanisms)
        for part_name, item in list(self.mechanism_path_items.items()):
            if item and item.scene():
                self.mechanism_scene.removeItem(item)
        self.mechanism_path_items.clear()

        # 3. Clear existing control point items
        if hasattr(self, 'control_point_items'):
            for part_name, control_points in self.control_point_items.items():
                for control_point in control_points:
                    if control_point.scene():
                        self.mechanism_scene.removeItem(control_point)
            self.control_point_items.clear()
        
        # 4. Clear any lingering mechanism traces for all parts
        for part_name in self.path_data.keys():
            # Find and clear any mechanism traces for this part
            for mechanism_id, layer_data in list(self.mechanism_layers.items()):
                if layer_data.get("part_name") == part_name:
                    # Only clear the trace path visual, not the entire mechanism
                    if mechanism_id in self.mechanism_trace_items:
                        trace_item = self.mechanism_trace_items[mechanism_id]
                        if trace_item and trace_item.scene():
                            self.mechanism_scene.removeItem(trace_item)
                        del self.mechanism_trace_items[mechanism_id]
                    if mechanism_id in self.mechanism_trace_paths:
                        del self.mechanism_trace_paths[mechanism_id]
                    if mechanism_id in self.mechanism_trace_points:
                        del self.mechanism_trace_points[mechanism_id]

        # Calculate combined bounds of all paths to set scene rect properly
        combined_bounds = None

        # Add new path items with enhanced debugging
        paths_added = 0
        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                logging.debug(f"[MECHANISM TAB] Adding path for part: {part_name}")
                path_bounds = path.boundingRect()
                logging.debug(f"[MECHANISM TAB] Path bounding rect: {path_bounds}")

                # Track combined bounds
                if combined_bounds is None:
                    combined_bounds = path_bounds
                else:
                    combined_bounds = combined_bounds.united(path_bounds)

                path_item = QGraphicsPathItem(path)
                pen = QPen(QColor(0, 200, 0), 4.0)  # Thicker line
                pen.setCosmetic(True)
                path_item.setPen(pen)
                path_item.setZValue(Z_MOTION_PATH_LINE)  # Use standardized Z-level for motion paths

                # Ensure the path is visible by setting additional properties
                path_item.setVisible(True)
                path_item.setEnabled(True)

                # Add to scene
                self.mechanism_scene.addItem(path_item)
                self.path_visual_items[part_name] = path_item
                paths_added += 1

                # Add control points for each path
                self._add_control_points_for_path(part_name, path)

                logging.debug(f"[MECHANISM TAB] Path item scene position: {path_item.scenePos()}")
                logging.debug(f"[MECHANISM TAB] Path item bounding rect: {path_item.boundingRect()}")
            else:
                logging.debug(f"[MECHANISM TAB] Skipping empty path for part: {part_name}")

        logging.debug(f"[MECHANISM TAB] Added {paths_added} path items to scene")

        # Debug scene bounds
        scene_rect = self.mechanism_scene.itemsBoundingRect()
        logging.debug(f"[MECHANISM TAB] Scene bounding rect after adding paths: {scene_rect}")

    def _add_control_points_for_path(self, part_name: str, path: QPainterPath):
        """Add control points (blue dots) for a motion path"""
        if not path or path.isEmpty():
            return

        # Store control point items for this path
        control_point_items = []

        # Sample points along the path to create control points
        # For a more detailed display, we can sample more points
        total_length = path.length()
        if total_length > 0:
            num_points = min(20, max(5, int(total_length / 50)))  # Adaptive point count

            for i in range(num_points + 1):  # +1 to include the end point
                t = i / num_points if num_points > 0 else 0
                point = path.pointAtPercent(t)

                # Create a blue control point
                control_point = QGraphicsEllipseItem(-4, -4, 8, 8)  # 8x8 pixel circle
                control_point.setPos(point)
                control_point.setBrush(QBrush(QColor(0, 100, 255)))  # Blue color
                control_point.setPen(QPen(QColor(0, 50, 200), 1))  # Darker blue border
                control_point.setZValue(Z_MOTION_PATH_LINE + 1)  # Above the path

                # Make it visible
                control_point.setVisible(True)
                control_point.setEnabled(True)

                # Add to scene
                self.mechanism_scene.addItem(control_point)
                control_point_items.append(control_point)

        # Store control points with path name for cleanup
        if not hasattr(self, 'control_point_items'):
            self.control_point_items = {}
        self.control_point_items[part_name] = control_point_items

        logging.debug(f"[MECHANISM TAB] Added {len(control_point_items)} control points for {part_name}")

    def _add_test_path_for_debugging(self):
        """Add a simple test path to verify the scene is working."""
        try:
            from PyQt6.QtCore import QPointF
            from PyQt6.QtGui import QPainterPath

            # Create a simple rectangular path for testing
            test_path = QPainterPath()
            test_path.moveTo(QPointF(0, 0))
            test_path.lineTo(QPointF(100, 0))
            test_path.lineTo(QPointF(100, 100))
            test_path.lineTo(QPointF(0, 100))
            test_path.closeSubpath()

            test_item = QGraphicsPathItem(test_path)
            test_pen = QPen(QColor(255, 0, 0), 5.0)  # Red, thick line
            test_pen.setCosmetic(True)
            test_item.setPen(test_pen)
            test_item.setZValue(100)  # High Z-value to ensure visibility

            self.mechanism_scene.addItem(test_item)
            logging.debug("[MECHANISM TAB] Added test path for debugging")

            # REMOVED: Don't auto-zoom to test path to preserve user camera position
            test_rect = test_item.boundingRect()
            if test_rect.isValid():
                logging.debug(f"[MECHANISM TAB] Test path bounds: {test_rect} (not auto-zooming)")

        except Exception as e:
            logging.error(f"[MECHANISM TAB] Failed to add test path: {e}")


    def _update_recommendation_button_state(self):
        """Update the recommendation button state based on parts with motion paths."""
        # Check if any parts have motion paths
        has_parts_with_paths = bool(self.path_data)

        if self.recommendation_btn:
            self.recommendation_btn.setEnabled(has_parts_with_paths)

    def _update_mechanism_layers_list(self):
        """Update the mechanism layers list to show all parts with simple path-based coloring and toggle functionality."""
        logging.error("[MECHANISM TAB] _update_mechanism_layers_list() CALLED - DEBUGGING")

        # If widget is None, create a simple replacement immediately
        if not self.mechanism_layers_list:
            logging.error("[MECHANISM TAB] mechanism_layers_list is None! Creating simple replacement...")

            # Create simple replacement widget
            self.mechanism_layers_list = QListWidget()
            self.mechanism_layers_list.setToolTip("Parts for mechanisms")
            self.mechanism_layers_list.setMinimumHeight(180)
            self.mechanism_layers_list.setStyleSheet("""
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
            """)

            # Try to add it to existing layout if possible, but check for duplicates first
            if hasattr(self, 'control_panel') and self.control_panel:
                # Check if we already have a "Parts for Mechanisms" group
                existing_groups = self.control_panel.findChildren(QGroupBox)
                parts_group_exists = any("Parts for Mechanisms" in group.title() for group in existing_groups)

                if not parts_group_exists:
                    layout = self.control_panel.layout()
                    if layout:
                        # Create a simple group to contain it
                        temp_group = QGroupBox("Parts for Mechanisms")
                        temp_layout = QVBoxLayout(temp_group)
                        temp_layout.addWidget(self.mechanism_layers_list)
                        layout.insertWidget(0, temp_group)
                        logging.error("[MECHANISM TAB] Added replacement widget to layout")
                else:
                    # Try to find existing group and add widget there
                    for group in existing_groups:
                        if "Parts for Mechanisms" in group.title():
                            group_layout = group.layout()
                            if group_layout and group_layout.count() == 0:  # Empty group
                                group_layout.addWidget(self.mechanism_layers_list)
                                logging.error("[MECHANISM TAB] Added widget to existing empty group")
                                break

                # Reconnect signals
                if hasattr(self, '_on_layers_list_item_clicked'):
                    self.mechanism_layers_list.itemClicked.connect(self._on_layers_list_item_clicked)

            logging.error(f"[MECHANISM TAB] Created replacement widget: {id(self.mechanism_layers_list)}")

        if not hasattr(self.mechanism_layers_list, 'clear'):
            logging.error(f"[MECHANISM TAB] mechanism_layers_list missing 'clear' method! Type: {type(self.mechanism_layers_list)}")
            return

        # Safety check - verify the widget is still connected to Qt
        try:
            _ = self.mechanism_layers_list.count()
        except RuntimeError:
            logging.warning("[MECHANISM TAB] Widget was deleted by Qt, skipping update")
            return

        # Simple clear like editor tab
        self.mechanism_layers_list.clear()

        # CRITICAL: Use editor tab data directly instead of local copy
        editor_parts_data = None
        editor_path_data = None

        logging.error(f"[MECHANISM TAB] main_window exists: {hasattr(self, 'main_window') and self.main_window is not None}")

        if hasattr(self, 'main_window') and self.main_window:
            logging.error(f"[MECHANISM TAB] editor_tab exists: {hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab is not None}")

            if hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab:
                editor_parts_data = self.main_window.editor_tab.current_parts_info
                editor_path_data = self.main_window.editor_tab.get_current_path_data()

                logging.error(f"[MECHANISM TAB] editor_parts_data type: {type(editor_parts_data)}")
                logging.error(f"[MECHANISM TAB] editor_path_data type: {type(editor_path_data)}")

        logging.error(f"[MECHANISM TAB] FINAL - Using EDITOR TAB data: {len(editor_parts_data) if editor_parts_data else 0} parts")
        logging.error(f"[MECHANISM TAB] FINAL - Using EDITOR TAB paths: {len(editor_path_data) if editor_path_data else 0} paths")

        # Simple population using editor tab data directly
        if editor_parts_data:
            # Apply same filtering as editor tab for consistency
            disabled_parts = {
                'torso',
                'left_arm_upper', 'right_arm_upper',
                'left_leg_upper', 'right_leg_upper'
            }

            # Filter out disabled parts to match editor tab behavior
            all_parts = [
                part_name for part_name in editor_parts_data.keys()
                if not any(disabled_part in part_name.lower() for disabled_part in disabled_parts)
            ]
            all_parts.sort()

            for part_name in all_parts:
                has_path = part_name in editor_path_data if editor_path_data else False
                is_enabled = self.part_enabled_state.get(part_name, True)  # Default to enabled
                has_mechanism = self._part_has_mechanism(part_name)

                # Create list item with toggle indicator
                display_text = part_name
                if has_path:
                    # Add toggle indicator for parts with paths
                    toggle_symbol = "●" if is_enabled else "○"
                    display_text = f"{part_name} {toggle_symbol}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, part_name)  # Store part name

                # Color coding like editor tab
                if has_path:
                    if is_enabled:
                        # Enabled part with path - normal black text
                        item.setForeground(QBrush(QColor(0, 0, 0)))
                        item.setToolTip(f"{part_name} - Has motion path (enabled)")
                    else:
                        # Disabled part with path - gray text
                        item.setForeground(QBrush(QColor(128, 128, 128)))
                        item.setToolTip(f"{part_name} - Has motion path (disabled)")
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                else:
                    # Part without path - gray text and disabled
                    item.setForeground(QBrush(QColor(160, 160, 160)))
                    item.setToolTip(f"{part_name} - No motion path defined")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

                # Add to list
                self.mechanism_layers_list.addItem(item)
                logging.error(f"[MECHANISM TAB] ADDED ITEM: {part_name} (has_path: {has_path}, enabled: {is_enabled})")
        else:
            logging.error("[MECHANISM TAB] NO EDITOR PARTS DATA - LIST WILL BE EMPTY!")

        final_count = self.mechanism_layers_list.count() if self.mechanism_layers_list else 0
        logging.error(f"[MECHANISM TAB] FINAL RESULT: {final_count} items in list")

        # CRITICAL: Check widget state immediately
        logging.error(f"[MECHANISM TAB] Widget exists: {self.mechanism_layers_list is not None}")
        logging.error(f"[MECHANISM TAB] Widget type: {type(self.mechanism_layers_list)}")

        # CRITICAL: Check widget visibility and parent
        if self.mechanism_layers_list:
            logging.error(f"[MECHANISM TAB] Widget visible: {self.mechanism_layers_list.isVisible()}")
            logging.error(f"[MECHANISM TAB] Widget size: {self.mechanism_layers_list.size()}")
            logging.error(f"[MECHANISM TAB] Widget parent: {self.mechanism_layers_list.parent()}")
            logging.error(f"[MECHANISM TAB] Widget geometry: {self.mechanism_layers_list.geometry()}")

            # FORCE VISIBILITY AND PROPER PARENT
            self.mechanism_layers_list.setVisible(True)
            self.mechanism_layers_list.show()
            self.mechanism_layers_list.raise_()

            # Force parent if missing
            if not self.mechanism_layers_list.parent():
                logging.error("[MECHANISM TAB] CRITICAL: Widget has no parent! Finding container...")
                if hasattr(self, 'control_panel') and self.control_panel:
                    # Find or create a group for it
                    found_group = False
                    for group in self.control_panel.findChildren(QGroupBox):
                        if "Parts" in group.title():
                            if group.layout():
                                group.layout().addWidget(self.mechanism_layers_list)
                                logging.error(f"[MECHANISM TAB] Added widget to existing group: {group.title()}")
                                found_group = True
                                break

                    if not found_group:
                        # Create new group
                        new_group = QGroupBox("Parts for Mechanisms")
                        new_layout = QVBoxLayout(new_group)
                        new_layout.addWidget(self.mechanism_layers_list)
                        self.control_panel.layout().insertWidget(0, new_group)
                        logging.error("[MECHANISM TAB] Created emergency group for widget")

        if final_count == 0:
            logging.error("[MECHANISM TAB] CRITICAL: List is empty after update!")

            # Don't set to None - keep existing widget if possible

    def _part_has_mechanism(self, part_name: str) -> bool:
        """Check if a part has any mechanism assigned to it."""
        for layer_data in self.mechanism_layers.values():
            if layer_data.get("part_name") == part_name:
                return True
        return False

    def _create_4bar_linkage_visuals(self, mechanism_data: dict) -> list[QGraphicsItem]:
        """Create visual representation of 4-bar linkage with triangular coupler (like dataset generator)."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})
        key_points = mechanism_data.get("key_points")


        if not to_scene_coords or not params:
            return []

        l1 = params.get("l1")
        l2 = params.get("l2")
        l3 = params.get("l3")
        l4 = params.get("l4")

        if not all([l1 is not None, l2 is not None, l3 is not None, l4 is not None]):
            logging.warning(f"Incomplete 4-bar linkage parameters: l1={l1}, l2={l2}, l3={l3}, l4={l4}")
            return []

        # Use initial positions from simulation data if available
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        if "joint_positions" in full_sim_data:
            joint_positions = full_sim_data["joint_positions"]
            if "p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0:
                # Use first frame from simulation
                p1 = np.array(joint_positions["p1_positions"][0])
                p2 = np.array(joint_positions["p2_positions"][0])
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])

                # Calculate initial coupler point position (same as dataset)
                coupler_point_x = params.get("coupler_point_x", 0.0)
                coupler_point_y = params.get("coupler_point_y", 0.0)

                coupler_vec = p4 - p3
                coupler_length = np.linalg.norm(coupler_vec)
                if coupler_length > 0:
                    coupler_unit = coupler_vec / coupler_length
                    coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                    p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
                else:
                    p_coupler = p3
            else:
                return []
        else:
            # Fallback - use default ground pivot positions based on l1
            p1 = np.array([0, 0])
            p2 = np.array([l1, 0])
            p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])
            d = np.linalg.norm(p2 - p3)
            if not (abs(l3 - l4) <= d <= l3 + l4):
                return []

            a = (l3**2 - l4**2 + d**2) / (2 * d)
            h = math.sqrt(max(0, l3**2 - a**2))
            p3_p2_unit = (p2 - p3) / d
            midpoint = p3 + a * p3_p2_unit
            p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

            coupler_point_x = params.get("coupler_point_x", l3/2)
            coupler_point_y = params.get("coupler_point_y", 0.0)

            coupler_vec = p4 - p3
            coupler_length = np.linalg.norm(coupler_vec)
            if coupler_length > 0:
                coupler_unit = coupler_vec / coupler_length
                coupler_normal = np.array([-coupler_unit[1], coupler_unit[0]])
                p_coupler = p3 + coupler_point_x * coupler_unit + coupler_point_y * coupler_normal
            else:
                p_coupler = p3

        # Transform all points to scene coordinates
        p1_t = to_scene_coords(p1)
        p2_t = to_scene_coords(p2)
        p3_t = to_scene_coords(p3)
        p4_t = to_scene_coords(p4)
        p_coupler_t = to_scene_coords(p_coupler)


        visual_items = []

        # Draw basic links (driver and follower)
        driver_link = QGraphicsLineItem(QLineF(p1_t, p3_t))
        driver_pen = QPen(QColor("#e74c3c"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        driver_link.setPen(driver_pen)
        driver_link.setZValue(15)  # Above parts (Z_PART_DEFAULT = 10)
        self.mechanism_scene.addItem(driver_link)
        visual_items.append(driver_link)

        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_pen = QPen(QColor("#f39c12"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        follower_link.setPen(follower_pen)
        follower_link.setZValue(15)  # Above parts
        self.mechanism_scene.addItem(follower_link)
        visual_items.append(follower_link)

        # Check if coupler forms a triangle or is collinear (same as dataset generator)
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2

        if area < 1e-3:  # Collinear - show as line
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_pen = QPen(QColor("#2ecc71"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            coupler_line.setPen(coupler_pen)
            coupler_line.setZValue(16)  # Above other links
            self.mechanism_scene.addItem(coupler_line)
            visual_items.append(coupler_line)
        else:  # Non-collinear - show as triangle
            # Create triangular coupler plate (p3, p4, coupler_point)
            triangle_points = [p3_t, p4_t, p_coupler_t]
            triangle_polygon = QPolygonF(triangle_points)

            coupler_triangle = QGraphicsPolygonItem(triangle_polygon)
            triangle_pen = QPen(QColor("#2ecc71"), 2, Qt.PenStyle.SolidLine)
            triangle_brush = QBrush(QColor("#2ecc71").lighter(160))
            triangle_brush.setStyle(Qt.BrushStyle.SolidPattern)
            coupler_triangle.setPen(triangle_pen)
            coupler_triangle.setBrush(triangle_brush)
            coupler_triangle.setZValue(16)  # Above other links
            coupler_triangle.setOpacity(0.8)
            self.mechanism_scene.addItem(coupler_triangle)
            visual_items.append(coupler_triangle)

        # Add ground link (p1 to p2) with colorful style like dataset generator
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_pen = QPen(QColor("#9b59b6"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)  # Purple
        ground_link.setPen(ground_pen)
        ground_link.setZValue(14)  # Base mechanism level, above parts
        self.mechanism_scene.addItem(ground_link)
        visual_items.append(ground_link)

        # Add pivot points with colorful style (like dataset generator)
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]  # Orange, Orange, Red, Blue
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names, strict=False):
            # Outer circle
            outer_pivot = self.mechanism_scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                QPen(color.darker(150), 2),
                QBrush(color)
            )
            outer_pivot.setZValue(Z_MECHANISM_PIVOT)
            outer_pivot.setToolTip(name)  # Add tooltip for identification
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = self.mechanism_scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )
            inner_pivot.setZValue(Z_MECHANISM_PIVOT + 1)
            visual_items.append(inner_pivot)

        # Add coupler point marker (red dot)
        coupler_marker = self.mechanism_scene.addEllipse(
            p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8,
            QPen(QColor("#ff0000"), 2),
            QBrush(QColor("#ff0000"))
        )
        coupler_marker.setZValue(Z_SELECTION_MARKER)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)


        return visual_items

    def _create_5bar_linkage_visuals(self, mechanism_data: dict) -> list:
        """Create visual representation for 5-bar linkage mechanism."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = self._get_scene_transform_function(mechanism_data)

            if not to_scene_coords:
                logging.warning("[5BAR] No scene transform available")
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                L3 = params.get("L3", 50)
                L4 = params.get("L4", 45)
                L5 = params.get("L5", 55)

                p3 = p1 + np.array([L2, 0])
                p4 = p3 + np.array([L3 * 0.7, L3 * 0.7])
                p5 = p2 + np.array([-L5 * 0.5, L5 * 0.866])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)

            # Create links
            pen = QPen(QColor(100, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.mechanism_scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler 1 (p3 to p4)
            coupler1 = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler1.setPen(pen)
            self.mechanism_scene.addItem(coupler1)
            visual_items.append(coupler1)

            # Coupler 2 (p4 to p5)
            coupler2 = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            coupler2.setPen(pen)
            self.mechanism_scene.addItem(coupler2)
            visual_items.append(coupler2)

            # Output link (p5 to p2)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p2_scene))
            output_link.setPen(pen)
            self.mechanism_scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground link
            ground_pen = QPen(QColor(50, 50, 50), 4)
            ground_link = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground_link.setPen(ground_pen)
            self.mechanism_scene.addItem(ground_link)
            visual_items.append(ground_link)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 2))
                self.mechanism_scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 1))
                self.mechanism_scene.addItem(pivot)
                visual_items.append(pivot)

            logging.info(f"[5BAR] Created {len(visual_items)} visual items")

        except Exception as e:
            logging.error(f"[5BAR] Failed to create visuals: {e}")

        return visual_items

    def _create_6bar_linkage_visuals(self, mechanism_data: dict) -> list:
        """Create visual representation for 6-bar linkage mechanism (Stephenson Type I)."""
        visual_items = []

        try:
            params = mechanism_data.get("params", {})
            to_scene_coords = self._get_scene_transform_function(mechanism_data)

            if not to_scene_coords:
                logging.warning("[6BAR] No scene transform available")
                return visual_items

            # Get ground pivots
            p1 = np.array(params.get("ground_pivot_1", [0, 0]))
            p2 = np.array(params.get("ground_pivot_2", [100, 0]))
            p6 = np.array(params.get("ground_pivot_3", [50, -30]))

            # Get initial joint positions from simulation data or calculate
            full_sim_data = mechanism_data.get("full_simulation_data", {})
            joint_positions = full_sim_data.get("joint_positions", {})

            if joint_positions and "p3_positions" in joint_positions:
                # Use first frame positions
                p3 = np.array(joint_positions["p3_positions"][0])
                p4 = np.array(joint_positions["p4_positions"][0])
                p5 = np.array(joint_positions["p5_positions"][0])
            else:
                # Calculate initial positions
                L2 = params.get("L2", 40)
                L3 = params.get("L3", 60)
                L4 = params.get("L4", 50)
                L5 = params.get("L5", 45)

                p3 = p1 + np.array([L2, 0])
                p4 = p2 + np.array([-L4 * 0.5, L4 * 0.866])
                p5 = p6 + np.array([L5 * 0.7, L5 * 0.7])

            # Transform to scene coordinates
            p1_scene = to_scene_coords(p1)
            p2_scene = to_scene_coords(p2)
            p3_scene = to_scene_coords(p3)
            p4_scene = to_scene_coords(p4)
            p5_scene = to_scene_coords(p5)
            p6_scene = to_scene_coords(p6)

            # Create links
            pen = QPen(QColor(150, 100, 200), 3)

            # Input link (p1 to p3)
            input_link = QGraphicsLineItem(QLineF(p1_scene, p3_scene))
            input_link.setPen(pen)
            self.mechanism_scene.addItem(input_link)
            visual_items.append(input_link)

            # Coupler (p3 to p4)
            coupler = QGraphicsLineItem(QLineF(p3_scene, p4_scene))
            coupler.setPen(pen)
            self.mechanism_scene.addItem(coupler)
            visual_items.append(coupler)

            # Rocker (p4 to p2)
            rocker = QGraphicsLineItem(QLineF(p4_scene, p2_scene))
            rocker.setPen(pen)
            self.mechanism_scene.addItem(rocker)
            visual_items.append(rocker)

            # Ternary link (p4 to p5)
            ternary = QGraphicsLineItem(QLineF(p4_scene, p5_scene))
            ternary.setPen(QPen(QColor(200, 150, 100), 3))
            self.mechanism_scene.addItem(ternary)
            visual_items.append(ternary)

            # Output link (p5 to p6)
            output_link = QGraphicsLineItem(QLineF(p5_scene, p6_scene))
            output_link.setPen(pen)
            self.mechanism_scene.addItem(output_link)
            visual_items.append(output_link)

            # Ground links
            ground_pen = QPen(QColor(50, 50, 50), 4)

            ground1 = QGraphicsLineItem(QLineF(p1_scene, p2_scene))
            ground1.setPen(ground_pen)
            self.mechanism_scene.addItem(ground1)
            visual_items.append(ground1)

            ground2 = QGraphicsLineItem(QLineF(p2_scene, p6_scene))
            ground2.setPen(QPen(QColor(50, 50, 50), 2, Qt.PenStyle.DashLine))
            self.mechanism_scene.addItem(ground2)
            visual_items.append(ground2)

            # Add pivot markers
            pivot_brush = QBrush(QColor(150, 150, 255))
            ground_pivot_brush = QBrush(QColor(80, 80, 80))

            # Ground pivots
            for pos in [p1_scene, p2_scene, p6_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 8, pos.y() - 8, 16, 16)
                pivot.setBrush(ground_pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 2))
                self.mechanism_scene.addItem(pivot)
                visual_items.append(pivot)

            # Moving joints
            for pos in [p3_scene, p4_scene, p5_scene]:
                pivot = QGraphicsEllipseItem(pos.x() - 6, pos.y() - 6, 12, 12)
                pivot.setBrush(pivot_brush)
                pivot.setPen(QPen(Qt.GlobalColor.black, 1))
                self.mechanism_scene.addItem(pivot)
                visual_items.append(pivot)

            logging.info(f"[6BAR] Created {len(visual_items)} visual items")

        except Exception as e:
            logging.error(f"[6BAR] Failed to create visuals: {e}")

        return visual_items

    def _reset_skeleton_to_initial_state(self):
        """Reset skeleton to initial state (addresses issues #9, #10, #11)."""
        logging.info("[MECHANISM TAB] === SKELETON RESET STARTED ===")

        # Stop any animation first
        if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
            self.animation_timer.stop()
            self.animation_time = 0
            logging.info("[MECHANISM TAB] Animation timer stopped")

        # Reset IK system to initial pose
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop any running animation
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()
                    logging.info("[MECHANISM TAB] IK Manager animation stopped")

                # Clear all mechanism position targets
                if hasattr(self.main_window.ik_manager, 'clear_mechanism_position_targets'):
                    self.main_window.ik_manager.clear_mechanism_position_targets()
                    logging.info("[MECHANISM TAB] Mechanism position targets cleared")

                # Reset to initial pose
                if hasattr(self.main_window.ik_manager, 'reset_animation_state'):
                    self.main_window.ik_manager.reset_animation_state()
                    logging.info("[MECHANISM TAB] IK animation state reset")
                elif hasattr(self.main_window.ik_manager, 'reset_all_ik_systems_and_data'):
                    self.main_window.ik_manager.reset_all_ik_systems_and_data()
                    logging.info("[MECHANISM TAB] IK system fully reset")

            except Exception as e:
                logging.warning(f"[MECHANISM TAB] Failed to reset IK manager: {e}")

        # Reset skeleton visualization using cached initial state
        if self._initial_skeleton_data_cache:
            logging.info("[MECHANISM TAB] Applying cached initial skeleton data")

            # First, position parts at their anchor joints
            self._position_parts_at_anchor_joints()

            # Then update skeleton visualization with initial state
            self.on_skeleton_updated(self._initial_skeleton_data_cache.copy())

            # Force skeleton visualization update
            if hasattr(self.mechanism_view, 'skeleton_graphics_item') and self.mechanism_view.skeleton_graphics_item:
                self.mechanism_view.skeleton_graphics_item.update()
                logging.info("[MECHANISM TAB] Skeleton graphics item updated")

            logging.info("[MECHANISM TAB] Skeleton and parts reset to cached initial state")
        else:
            # If no cached data, try to get from skeleton manager
            if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
                initial_skeleton = self.main_window.skeleton_manager.get_current_skeleton_data()
                if initial_skeleton:
                    self.cache_initial_skeleton(initial_skeleton)
                    self.on_skeleton_updated(initial_skeleton.copy())
                    logging.info("[MECHANISM TAB] Retrieved and applied skeleton from skeleton manager")
                else:
                    logging.warning("[MECHANISM TAB] No skeleton data available from skeleton manager")
            else:
                logging.warning("[MECHANISM TAB] No cached initial skeleton data and no skeleton manager available")

        logging.info("[MECHANISM TAB] === SKELETON RESET COMPLETED ===")

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """Handle mechanism visualization data"""
        # CRITICAL: Clear all cached animation states when mechanism changes
        self._clear_animation_cache()

        # ISSUE #9: Reset skeleton immediately when mechanism changes
        self._reset_skeleton_to_initial_state()

        mechanism_id = mechanism_graphics_data.get("mechanism_id")
        mechanism_type = mechanism_graphics_data.get("mechanism_type")
        layer_data = self.mechanism_layers.get(mechanism_id)
        if not layer_data:
            return

        # Remove any existing visual items for this mechanism safely
        existing_visual_items = layer_data.get("visual_items", [])
        self._safe_remove_visual_items(existing_visual_items)

        visual_items = []
        if mechanism_type == "4_bar_linkage":
            visual_items.extend(self._create_4bar_linkage_visuals(mechanism_graphics_data))
        elif mechanism_type == "cam":
            visual_items.extend(self._create_cam_visuals(mechanism_graphics_data))
        elif mechanism_type == "gear":
            visual_items.extend(self._create_gear_visuals(mechanism_graphics_data))
        elif mechanism_type == "planetary_gear":
            visual_items.extend(self._create_planetary_gear_visuals(mechanism_graphics_data))

        layer_data["visual_items"] = visual_items

        # Force scene update to ensure visuals are displayed
        self.mechanism_scene.update()

    def _clear_animation_cache(self):
        """Clear cached animation state variables when mechanism changes, but preserve skeleton data."""
        # List of specific animation cache attributes to clear (mechanism-specific only)
        animation_cache_attrs = [
            '_initial_cam_center_scene',  # Cam animation cache
        ]

        # Clear only animation-specific cached states, not skeleton data
        for attr in animation_cache_attrs:
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                    logging.debug(f"[ANIMATION CACHE] Cleared animation cache: {attr}")
                except AttributeError:
                    pass  # Already cleared

        # Also clear any additional _animation_ or _cam_ prefixed caches
        all_attrs = [attr for attr in dir(self) if
                     attr.startswith('_animation_') or
                     attr.startswith('_cam_') or
                     attr.startswith('_gear_') or
                     attr.startswith('_fourbar_')]

        for attr in all_attrs:
            if hasattr(self, attr) and not attr.endswith('_cache'):  # Preserve important caches
                try:
                    delattr(self, attr)
                    logging.debug(f"[ANIMATION CACHE] Cleared mechanism cache: {attr}")
                except AttributeError:
                    pass

        logging.info("[ANIMATION CACHE] Animation cache cleared, skeleton data preserved")

    def _safe_remove_visual_items(self, visual_items: list):
        """Safely remove visual items from scene, handling Qt object lifecycle issues."""
        if not visual_items:
            return

        # CRITICAL: Don't attempt individual removal if scene was already cleared
        # This prevents the "Visual item already deleted by Qt" flood
        if hasattr(self, '_scene_recently_cleared') and self._scene_recently_cleared:
            logging.debug(f"[MECHANISM TAB] Skipping individual item removal - scene was recently cleared ({len(visual_items)} items)")
            return

        valid_items_count = 0
        deleted_items_count = 0

        for item in visual_items:
            if item is None:
                continue

            try:
                # Quick validity check without accessing properties that might crash
                if hasattr(item, 'scene'):
                    scene = item.scene()

                    # Only try to remove if item is actually in a scene
                    if scene is not None:
                        try:
                            # Quick check if scene is still valid
                            _ = scene.itemsBoundingRect()
                            scene.removeItem(item)
                            valid_items_count += 1
                        except RuntimeError as e:
                            if "wrapped C/C++ object" in str(e):
                                deleted_items_count += 1
                            else:
                                logging.warning(f"Unexpected error removing visual item: {e}")

            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    deleted_items_count += 1
                else:
                    logging.warning(f"Unexpected RuntimeError with visual item: {e}")
            except Exception as e:
                logging.warning(f"Unexpected error checking visual item: {e}")

        if deleted_items_count > 0:
            logging.debug(f"[MECHANISM TAB] Visual item cleanup: {valid_items_count} removed, {deleted_items_count} already deleted by Qt")
        elif valid_items_count > 0:
            logging.debug(f"[MECHANISM TAB] Successfully removed {valid_items_count} visual items")

    def cleanup_tab_resources(self):
        """Clean up resources when switching away from mechanism tab."""
        try:
            logging.info("[MECHANISM TAB] Cleaning up tab resources for tab switch")

            # CRITICAL: Stop IK manager animations to prevent race conditions
            if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
                try:
                    self.main_window.ik_manager.stop_animation()
                    logging.debug("Stopped IK manager animation to prevent race conditions")
                except Exception as e:
                    logging.warning(f"Error stopping IK animation: {e}")

            # Stop any running mechanism animations
            if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
                self.animation_timer.stop()
                logging.debug("Stopped mechanism animation timer")

            # CRITICAL: Clear data structures FIRST, then attempt safe Qt cleanup
            logging.debug("[MECHANISM TAB] Clearing mechanism data structures during tab cleanup")

            # 1. Store references to visual items before clearing data structures
            all_visual_items = []
            for mechanism_id, layer_data in self.mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                all_visual_items.extend(visual_items)
                # Clear the visual items list FIRST
                layer_data["visual_items"] = []
                logging.debug(f"Cleared data structure for mechanism {mechanism_id}")

            # 2. Clear other tracking structures
            self.mechanism_trace_items.clear()
            if hasattr(self, 'path_visual_items'):
                self.path_visual_items.clear()

            # 3. NOW attempt safe removal of Qt objects (many may already be deleted)
            if all_visual_items:
                self._safe_remove_visual_items(all_visual_items)
                logging.debug(f"Attempted safe cleanup of {len(all_visual_items)} visual items")

            # Clear scene if needed
            if hasattr(self, 'mechanism_scene') and self.mechanism_scene:
                try:
                    # Don't clear the entire scene, just ensure it's stable
                    self.mechanism_scene.update()
                except Exception as e:
                    logging.warning(f"Error updating scene during cleanup: {e}")

            logging.info("[MECHANISM TAB] Tab resource cleanup completed")

        except Exception as e:
            logging.error(f"Error during tab resource cleanup: {e}")

    def prepare_tab_activation(self):
        """Prepare tab for activation when switching back to mechanism tab."""
        try:
            logging.info("[MECHANISM TAB] Preparing tab for activation")

            # Ensure skeleton is properly initialized if we have cached data
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                try:
                    self._ensure_skeleton_visualization(self._initial_skeleton_data_cache)
                    logging.debug("Skeleton visualization ensured for tab activation")
                except Exception as e:
                    logging.warning(f"Error ensuring skeleton visualization: {e}")

            # Refresh mechanism visuals if any mechanisms are enabled
            enabled_mechanisms = [mid for mid, enabled in self.mechanism_enabled_state.items() if enabled]
            if enabled_mechanisms:
                logging.debug(f"Refreshing visuals for {len(enabled_mechanisms)} enabled mechanisms")
                for mechanism_id in enabled_mechanisms:
                    layer_data = self.mechanism_layers.get(mechanism_id)
                    if layer_data:
                        try:
                            # Only regenerate visuals if they don't exist or are invalid
                            visual_items = layer_data.get("visual_items", [])
                            needs_regeneration = not visual_items or any(
                                item is None or self._is_visual_item_invalid(item)
                                for item in visual_items
                            )

                            if needs_regeneration:
                                mechanism_graphics_data = {
                                    "mechanism_id": mechanism_id,
                                    "mechanism_type": layer_data.get("type"),
                                    **layer_data
                                }
                                self._generate_mechanism_visuals_directly(
                                    mechanism_id,
                                    layer_data.get("type"),
                                    layer_data.get("params", {}),
                                    layer_data
                                )
                                logging.debug(f"Regenerated visuals for mechanism {mechanism_id}")

                            # CRITICAL FIX: Regenerate trace items (red paths) if missing or invalid
                            trace_item = self.mechanism_trace_items.get(mechanism_id)
                            trace_needs_regeneration = (
                                trace_item is None or
                                self._is_visual_item_invalid(trace_item)
                            )

                            if trace_needs_regeneration:
                                logging.debug(f"Regenerating trace path for mechanism {mechanism_id}")
                                self._init_mechanism_path_trace(mechanism_id)

                                # Restore trace points if they exist in data
                                if mechanism_id in self.mechanism_trace_points and self.mechanism_trace_points[mechanism_id]:
                                    trace_points = self.mechanism_trace_points[mechanism_id]
                                    if len(trace_points) > 1:
                                        path = QPainterPath()
                                        path.moveTo(trace_points[0])
                                        for point in trace_points[1:]:
                                            path.lineTo(point)
                                        self.mechanism_trace_paths[mechanism_id] = path
                                        self.mechanism_trace_items[mechanism_id].setPath(path)
                                        logging.debug(f"Restored {len(trace_points)} trace points for mechanism {mechanism_id}")

                        except Exception as e:
                            logging.warning(f"Error refreshing mechanism {mechanism_id}: {e}")

            logging.info("[MECHANISM TAB] Tab activation preparation completed")

        except Exception as e:
            logging.error(f"Error during tab activation preparation: {e}")

    def _is_visual_item_invalid(self, item) -> bool:
        """Check if a visual item is invalid (deleted by Qt)."""
        try:
            if item is None:
                return True

            # Try to access a simple property
            _ = item.isVisible()
            return False

        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                return True
            raise
        except:
            return True

    def deactivate_tab(self):
        """Called when user switches away from mechanism tab."""
        self._tab_active = False  # CRITICAL: Stop IK race condition
        logging.info("[MECHANISM TAB] Tab deactivating - cleaning up resources")
        self.cleanup_tab_resources()

    def activate_tab(self):
        """Called when user switches to mechanism tab."""
        self._tab_active = True  # CRITICAL: Allow IK updates
        logging.info("[MECHANISM TAB] Tab activating - preparing resources")

        self.prepare_tab_activation()

        # Data synchronization is now handled by MainWindow before activate_tab is called
        # Just update the layers list with current data
        self._update_mechanism_layers_list()

        # CRITICAL: Update all button states when tab is activated
        self._update_recommendation_button_state()
        self._update_parametric_button_state()
        self._update_blueprint_button_state()
        self._update_animation_button_states()

    def showEvent(self, event):
        """Handle widget show event for additional safety."""
        super().showEvent(event)
        try:
            # Additional activation logic if needed
            if hasattr(self, '_tab_visible'):
                self._tab_visible = True
        except Exception as e:
            logging.warning(f"Error in showEvent: {e}")


    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
        """Receives IK results and updates the MechanismView - SAME AS EDITOR TAB.
        This ensures natural skeleton movement in mechanism design tab.
        """
        # CRITICAL: Prevent race condition crashes during tab switching
        if not hasattr(self, '_tab_active') or not self._tab_active:
            logging.debug("[MECHANISM TAB] Ignoring IK update - tab is not active")
            return

        if not self.isVisible():
            logging.debug("[MECHANISM TAB] Ignoring IK update - tab is not visible")
            return

        if not self.mechanism_view:
            logging.warning("MechanismDesignTab: MechanismView not available to handle IK update.")
            return

        if not ik_results:
            return

        try:
            # Use the same method as EditorTab to ensure consistent skeleton movement
            # The mechanism_view is an EditorView, so it has the same update_visuals_from_animation_data method
            if hasattr(self.mechanism_view, 'update_visuals_from_animation_data'):
                self.mechanism_view.update_visuals_from_animation_data(ik_results)
            else:
                logging.error("MechanismDesignTab: mechanism_view does not have update_visuals_from_animation_data method")

            # Update the scene to reflect changes - with safety checks
            if self.mechanism_scene and hasattr(self, '_tab_active') and self._tab_active:
                try:
                    self.mechanism_scene.update()
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        logging.debug("Scene already deleted, ignoring update")
                    else:
                        raise

        except Exception as e:
            logging.warning(f"Error in handle_ik_update: {e}")

    def _generate_mechanism_visuals_directly(self, mechanism_id: str, mechanism_type: str, params: dict, layer_data: dict):
        """Generate mechanism visuals directly."""
        # Don't add user path - it's already on screen
        # Generate mechanism visuals directly
        mechanism_graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": mechanism_type,
            "params": params,
            **layer_data
        }
        self.handle_mechanism_visuals(mechanism_graphics_data)


    # Animation control methods
    def _on_start_animation(self):
        """Start the animation timer and IK animation with enhanced mechanism-IK integration."""
        if self.mechanism_enabled_state:
            # Ensure skeleton is properly initialized before starting animation
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                self._ensure_skeleton_visualization(self._initial_skeleton_data_cache)

            # Setup comprehensive mechanism-IK integration
            integration_success = self._setup_mechanism_ik_integration()

            if integration_success:
                try:
                    # Start IK animation for skeleton integration
                    if hasattr(self.main_window.ik_manager, 'start_animation'):
                        self.main_window.ik_manager.start_animation()


                except Exception:
                    # Continue with basic mechanism animation even if IK fails
                    pass
            else:
                pass

            # Start mechanism animation timer for visuals and path tracing
            self.animation_timer.start(33)  # ~30 FPS

            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)


        else:
            QMessageBox.warning(self, "Warning", "No mechanisms are enabled for animation.")

    def _on_stop_animation(self):
        """Stop the animation timer and IK animation with proper cleanup."""
        self.animation_timer.stop()

        # Stop IK animation for skeleton integration
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                self.main_window.ik_manager.clear_mechanism_position_targets()


            except Exception:
                pass

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_reset_animation(self):
        """Reset animation to start position with comprehensive IK reset."""
        logging.info("[MECHANISM TAB] === RESET ANIMATION STARTED ===")

        self.animation_timer.stop()
        self.animation_time = 0
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Clear all traced paths
        for mechanism_id in list(self.mechanism_trace_items.keys()):
            self._init_mechanism_path_trace(mechanism_id)

        # CRITICAL: Reset skeleton to initial state first
        self._reset_skeleton_to_initial_state()
        logging.info("[MECHANISM TAB] Skeleton reset to initial state completed")

        # Reset skeleton and IK system
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop any running animation
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                self.main_window.ik_manager.clear_mechanism_position_targets()

                # Reset IK system to initial state
                if hasattr(self.main_window.ik_manager, 'reset_animation_state'):
                    self.main_window.ik_manager.reset_animation_state()

                logging.info("[MECHANISM TAB] IK Manager reset completed")
            except Exception as e:
                logging.warning(f"[MECHANISM TAB] IK Manager reset failed: {e}")

        # Reset parts to initial positions
        self._position_parts_at_anchor_joints()
        logging.info("[MECHANISM TAB] Parts repositioned at anchor joints")

        # Reset mechanism visuals to initial state (time=0)
        for mechanism_id, layer_data in self.mechanism_layers.items():
            try:
                self._update_mechanism_visuals_for_animation(mechanism_id, 0, layer_data)
            except Exception:
                pass

            # Clear mechanism traces
            if mechanism_id in self.mechanism_trace_points:
                self.mechanism_trace_points[mechanism_id].clear()
                self.mechanism_trace_paths[mechanism_id] = QPainterPath()
                if mechanism_id in self.mechanism_trace_items:
                    self.mechanism_trace_items[mechanism_id].setPath(QPainterPath())

    def _on_layer_selection_changed(self):
        """Handle selection changes in the mechanism layers list."""
        # CRITICAL: Clear animation cache when layer selection changes
        self._clear_animation_cache()
        
        # CRITICAL: Clear all mechanism traces when switching selection to prevent old paths from lingering
        for mechanism_id in list(self.mechanism_trace_items.keys()):
            self._clear_mechanism_trace(mechanism_id)

        # ISSUE #11: Reset skeleton when selection changes while preserving view
        current_view_transform = self.mechanism_view.transform()  # Save current view

        self._reset_skeleton_to_initial_state()

        # Restore the view transform to maintain user's current view
        self.mechanism_view.setTransform(current_view_transform)

        selected_items = self.mechanism_layers_list.selectedItems()
        is_selection_valid = bool(selected_items)

        if is_selection_valid:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.selected_part_name = part_name  # CRITICAL: Set selected part for mechanism operations
            logging.info(f"[MECHANISM TAB] Selected part for mechanism: {part_name}")
            
            # In parametric mode, update handles for the newly selected mechanism
            if self.parametric_mode_enabled:
                self._update_parametric_handles_for_selection(part_name)
                
        else:
            self.selected_part_name = None  # Clear selection
            logging.debug("No part selected")
            
            # In parametric mode, hide all handles when nothing is selected
            if self.parametric_mode_enabled:
                self._hide_all_parametric_handles()

    def _on_layer_item_clicked(self, item):
        """Handle clicking on a layer item.
        
        In normal mode: Toggle part enabled/disabled state
        In parametric mode: Just allow selection change without toggling state
        """
        part_name = item.data(Qt.ItemDataRole.UserRole)

        # Only process clicks on parts with motion paths
        if part_name not in self.path_data:
            logging.debug(f"Part {part_name} has no motion path, ignoring click")
            return

        # In parametric mode, don't toggle enabled/disabled state
        # Just allow the selection to change for parametric editing
        if self.parametric_mode_enabled:
            logging.debug(f"In parametric mode - allowing selection of {part_name} without toggling state")
            # The selection change is handled by _on_layer_selection_changed
            return

        # Normal mode: Toggle enabled/disabled state
        current_state = self.part_enabled_state.get(part_name, True)
        new_state = not current_state
        self.part_enabled_state[part_name] = new_state

        # Update visual representation and animation control
        self._update_part_visibility_and_animation(part_name, new_state)

        # Update the list display to reflect new state
        self._update_mechanism_layers_list()

        logging.debug(f"Toggled {part_name}: {current_state} -> {new_state}")

    def _update_part_visibility_and_animation(self, part_name: str, enabled: bool):
        """Update part visibility and animation control based on enabled state."""
        # Control part visibility in the scene
        if hasattr(self, 'current_editor_items') and part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, 'setVisible'):
                part_item.setVisible(enabled)
                logging.debug(f"Set part {part_name} visibility to {enabled}")

        # Control mechanism visuals if they exist
        has_mechanism = self._part_has_mechanism(part_name)
        if has_mechanism:
            self._toggle_mechanism_visuals(part_name, enabled)

        # Update animation control buttons if needed
        self._update_animation_button_states()

        # Update parametric edit button state
        self._update_parametric_button_state()

    def _update_animation_button_states(self):
        """Update animation button states based on enabled parts."""
        # Check if any parts with paths are enabled
        has_enabled_parts = any(
            self.part_enabled_state.get(part_name, True)
            for part_name in self.path_data.keys()
        )

        # Enable/disable animation buttons based on enabled parts
        self.play_btn.setEnabled(has_enabled_parts and bool(self.path_data))
        self.reset_btn.setEnabled(has_enabled_parts and bool(self.path_data))

    def _update_parametric_button_state(self):
        """Update parametric edit button state based on available mechanisms."""
        if not PARAMETRIC_AVAILABLE or not self.parametric_edit_btn:
            return

        # Enable parametric edit if we have any mechanisms loaded
        has_mechanisms = bool(self.mechanism_layers)
        # Enable parametric edit button based on available mechanisms
        self.parametric_edit_btn.setEnabled(has_mechanisms)

        if has_mechanisms:
            self.parametric_edit_btn.setToolTip(
                "Enable interactive parameter editing with drag handles\n"
                f"{len(self.mechanism_layers)} mechanism(s) available for editing"
            )
        else:
            self.parametric_edit_btn.setToolTip(
                "Generate mechanisms first to enable parametric editing"
            )

    def _toggle_mechanism_visuals(self, part_name: str, enabled: bool):
        """Toggle visibility of mechanism visuals for a specific part."""
        # Find mechanism(s) for this part
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if layer_data.get("part_name") == part_name:
                # Update visual items visibility
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setVisible'):
                        item.setVisible(enabled)

                # Update trace item visibility if it exists
                if mechanism_id in self.mechanism_trace_items:
                    trace_item = self.mechanism_trace_items[mechanism_id]
                    if hasattr(trace_item, 'setVisible'):
                        trace_item.setVisible(enabled)

                logging.debug(f"Set {len(visual_items)} visual items visibility to {enabled} for {part_name}")


    def _create_cam_visuals(self, mechanism_data: dict) -> list[QGraphicsItem]:
        """Create visual representation of cam and follower mechanism with egg-shaped cam."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not params:
            return []

        # Adjusted parameters for more realistic CAM size
        # CAM should be smaller, rod should be longer for realistic appearance
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        follower_rod_length = params.get("follower_rod_length", 40.0)

        # Scale CAM appropriately for character interaction
        # Use stored scaling factors if available, otherwise use defaults
        cam_scale_factor = mechanism_data.get('cam_scale_factor', 1.0)  # Normal CAM size
        rod_length_multiplier = mechanism_data.get('rod_length_multiplier', 1.0)  # Direct rod length control

        # Apply scaling
        scaled_base_radius = base_radius * cam_scale_factor
        scaled_eccentricity = eccentricity * cam_scale_factor
        scaled_rod_length = follower_rod_length * rod_length_multiplier

        # Create egg-shaped cam profile
        def create_egg_shape_profile(base_radius, eccentricity):
            """Create an egg-shaped cam profile using parametric equations"""
            points = []
            num_points = 100

            for i in range(num_points):
                theta = (i / num_points) * 2 * np.pi

                # Create egg shape: one end more pointed than the other
                # The egg is wider at bottom (theta = π/2) and narrower at top (theta = 3π/2)
                # This creates proper egg shape with follower riding on the surface
                lift = eccentricity * (1 + np.cos(theta)) / 2  # Maximum at theta=0 (right side)
                r = base_radius + lift

                # Convert to Cartesian coordinates
                x = r * np.cos(theta)
                y = r * np.sin(theta)

                points.append([x, y])

            return points

        # Get CAM position - use stored position if available, otherwise calculate
        if 'cam_position' in mechanism_data:
            character_position = mechanism_data['cam_position']
        else:
            character_position = self._get_character_position()
            mechanism_data['cam_position'] = character_position

        # CAM is positioned at bottom with follower above (gravity physics)
        # Position cam at origin for proper coordinate transformation
        cam_center_orig = np.array([0, 0])  # CAM center at origin

        # Place follower ABOVE cam center
        # Follower should be at foot level, so calculate based on that
        follower_y_orig = cam_center_orig[1] - (scaled_base_radius + scaled_rod_length)
        follower_pos_orig = np.array([cam_center_orig[0], follower_y_orig])

        # Create egg-shaped cam profile with scaled dimensions
        egg_profile = create_egg_shape_profile(scaled_base_radius, scaled_eccentricity)

        # Use existing transform function if available, otherwise create new one
        if 'cam_transform_function' in mechanism_data:
            cam_to_scene_coords = mechanism_data['cam_transform_function']
        else:
            # Create custom transformation for CAM positioning
            # CAM should be positioned directly at character feet position
            def cam_to_scene_coords(p):
                """Transform CAM coordinates to scene, placing CAM at character feet."""
                if len(p) != 2:
                    return QPointF(character_position[0], character_position[1])

                # Transform point relative to character position
                # Y coordinate: character_position[1] is already at feet + offset
                # CAM should be centered at this position
                return QPointF(
                    float(p[0] + character_position[0]),
                    float(p[1] + character_position[1])
                )
            mechanism_data['cam_transform_function'] = cam_to_scene_coords

        # Store scaling factors for consistency in animation and parametric editing
        mechanism_data['cam_scale_factor'] = cam_scale_factor
        mechanism_data['rod_length_multiplier'] = rod_length_multiplier

        # Transform key points to scene coordinates
        cam_center_scene = cam_to_scene_coords(cam_center_orig)
        follower_scene = cam_to_scene_coords(follower_pos_orig)

        # Transform egg profile points to scene coordinates
        cam_polygon_points = []
        for point in egg_profile:
            # Position relative to cam center
            point_offset = np.array(point) + cam_center_orig
            scene_point = cam_to_scene_coords(point_offset)
            cam_polygon_points.append(scene_point)

        # Create QPolygonF from points
        cam_polygon = QPolygonF(cam_polygon_points)

        visual_items = []

        # Create egg-shaped cam body with enhanced visibility
        cam_color = QColor("#2196f3")  # Modern blue
        cam_body = QGraphicsPolygonItem(cam_polygon)
        cam_body.setPen(QPen(cam_color.darker(120), 3))  # Thinner border for smaller cam
        cam_body.setBrush(QBrush(cam_color.lighter(130)))
        cam_body.setZValue(15)  # Above parts
        cam_body.setOpacity(1.0)  # Full opacity for visibility
        cam_body.setToolTip("Cam - Egg-shaped rotating profile")
        self.mechanism_scene.addItem(cam_body)
        visual_items.append(cam_body)
        logging.debug(f"[CAM_VISUALS] Created cam body at center {cam_center_scene.x():.1f}, {cam_center_scene.y():.1f}")
        logging.debug(f"[CAM_VISUALS] Character position: {character_position}")
        logging.debug(f"[CAM_VISUALS] Scaled CAM: base_radius={scaled_base_radius:.1f}, eccentricity={scaled_eccentricity:.1f}")

        # Create follower with appropriate size
        follower_color = QColor("#ff9800")  # Orange
        follower_width, follower_height = 20, 15  # Larger for visibility
        follower_body = QGraphicsRectItem(
            follower_scene.x() - follower_width/2,
            follower_scene.y() - follower_height/2,
            follower_width,
            follower_height
        )
        follower_body.setPen(QPen(follower_color.darker(120), 2))
        follower_body.setBrush(QBrush(follower_color))
        follower_body.setZValue(16)  # Above cam
        follower_body.setToolTip("Follower - Moves up/down as cam rotates")
        self.mechanism_scene.addItem(follower_body)
        visual_items.append(follower_body)
        logging.debug(f"[CAM_VISUALS] Created follower at {follower_scene.x():.1f}, {follower_scene.y():.1f}")
        logging.debug(f"[CAM_VISUALS] Rod length: {scaled_rod_length:.1f}")

        # Create cam center marker (rotation point)
        cam_center_color = QColor("#f44336")  # Red for rotation center
        cam_center_marker = QGraphicsEllipseItem(
            cam_center_scene.x() - 5, cam_center_scene.y() - 5, 10, 10
        )
        cam_center_marker.setPen(QPen(cam_center_color.darker(150), 2))
        cam_center_marker.setBrush(QBrush(cam_center_color))
        cam_center_marker.setZValue(20)  # Top level
        cam_center_marker.setToolTip("Cam Center - Rotation axis")
        self.mechanism_scene.addItem(cam_center_marker)
        visual_items.append(cam_center_marker)

        # Create follower rod line to show connection
        rod_pen = QPen(QColor("#9e9e9e"), 3, Qt.PenStyle.DashLine)  # Gray dashed line, thicker
        follower_rod = QGraphicsLineItem(
            cam_center_scene.x(), cam_center_scene.y(),
            follower_scene.x(), follower_scene.y()
        )
        follower_rod.setPen(rod_pen)
        follower_rod.setZValue(14)  # Below cam but above parts
        follower_rod.setToolTip("Connecting Rod")
        self.mechanism_scene.addItem(follower_rod)
        visual_items.append(follower_rod)

        # Return visual items
        return visual_items

    def _create_gear_visuals(self, mechanism_data: dict) -> list[QGraphicsItem]:
        """Create visual representation of gear train mechanism."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)

        # Gear centers in original coordinates - match dataset generator
        distance = r1 + r2  # Gears touching
        gear1_center_orig = np.array([0, 0])
        gear2_center_orig = np.array([distance, 0])

        # Transform to scene coordinates
        gear1_center_scene = to_scene_coords(gear1_center_orig)
        gear2_center_scene = to_scene_coords(gear2_center_orig)

        visual_items = []

        # Create gear 1 (driver) with proper screen coordinates
        gear1_color = QColor("#3498db")  # Blue

        # Calculate screen radius for gear1
        gear1_edge_orig = gear1_center_orig + np.array([r1, 0])
        gear1_edge_scene = to_scene_coords(gear1_edge_orig)
        r1_screen = QLineF(gear1_center_scene, gear1_edge_scene).length()

        gear1_body = self.mechanism_scene.addEllipse(
            gear1_center_scene.x() - r1_screen, gear1_center_scene.y() - r1_screen,
            r1_screen * 2, r1_screen * 2,
            QPen(gear1_color, 4),
            QBrush(gear1_color.lighter(170))
        )
        gear1_body.setZValue(15)  # Above parts
        visual_items.append(gear1_body)

        # Create gear 2 (driven) with proper screen coordinates
        gear2_color = QColor("#2ecc71")  # Green

        # Calculate screen radius for gear2
        gear2_edge_orig = gear2_center_orig + np.array([r2, 0])
        gear2_edge_scene = to_scene_coords(gear2_edge_orig)
        r2_screen = QLineF(gear2_center_scene, gear2_edge_scene).length()

        gear2_body = self.mechanism_scene.addEllipse(
            gear2_center_scene.x() - r2_screen, gear2_center_scene.y() - r2_screen,
            r2_screen * 2, r2_screen * 2,
            QPen(gear2_color, 4),
            QBrush(gear2_color.lighter(170))
        )
        gear2_body.setZValue(15)  # Above parts
        visual_items.append(gear2_body)

        # Create rotation indicators (lines that will rotate)
        indicator_color = QColor("#ffffff")  # White lines

        # Gear 1 indicator (initially horizontal) - use screen-space radius
        gear1_indicator = self.mechanism_scene.addLine(
            gear1_center_scene.x(), gear1_center_scene.y(),
            gear1_center_scene.x() + r1_screen, gear1_center_scene.y(),
            QPen(indicator_color, 3)
        )
        gear1_indicator.setZValue(15)
        visual_items.append(gear1_indicator)

        # Gear 2 indicator (initially horizontal) - use screen-space radius
        gear2_indicator = self.mechanism_scene.addLine(
            gear2_center_scene.x(), gear2_center_scene.y(),
            gear2_center_scene.x() + r2_screen, gear2_center_scene.y(),
            QPen(indicator_color, 3)
        )
        gear2_indicator.setZValue(15)
        visual_items.append(gear2_indicator)

        # Create center pivots
        pivot_color = QColor("#f39c12")  # Orange

        # Gear 1 center
        gear1_pivot = self.mechanism_scene.addEllipse(
            gear1_center_scene.x() - 8, gear1_center_scene.y() - 8, 16, 16,
            QPen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear1_pivot.setZValue(20)
        visual_items.append(gear1_pivot)

        # Gear 2 center
        gear2_pivot = self.mechanism_scene.addEllipse(
            gear2_center_scene.x() - 8, gear2_center_scene.y() - 8, 16, 16,
            QPen(pivot_color.darker(150), 3),
            QBrush(pivot_color)
        )
        gear2_pivot.setZValue(20)
        visual_items.append(gear2_pivot)

        return visual_items

    def _create_planetary_gear_visuals(self, mechanism_data: dict) -> list[QGraphicsItem]:
        """Create visual representation of planetary gear mechanism."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})

        if not to_scene_coords or not params:
            return []

        r_sun = params.get("r_sun", 20)
        r_planet = params.get("r_planet", 30)
        arm_length = params.get("arm_length", 15)

        visual_items = []

        # Try to get initial positions from simulation data
        full_sim_data = mechanism_data.get("full_simulation_data", {})
        gear_positions = full_sim_data.get("gear_positions", {})

        if gear_positions and "sun_centers" in gear_positions and len(gear_positions["sun_centers"]) > 0:
            # Use simulation data for accurate positioning
            frame_idx = 0
            sun_center_orig = np.array(gear_positions["sun_centers"][frame_idx])
            planet_center_orig = np.array(gear_positions["planet_centers"][frame_idx])
            tracking_point_orig = np.array(gear_positions["tracking_points"][frame_idx])
        else:
            # Fallback to calculated initial positions
            sun_center_orig = np.array([0, 0])
            planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1, 0])  # Initial position
            tracking_point_orig = planet_center_orig + arm_length * np.array([1, 0])  # Initial tracking point

        # Transform to scene coordinates
        sun_center_scene = to_scene_coords(sun_center_orig)
        planet_center_scene = to_scene_coords(planet_center_orig)
        tracking_point_scene = to_scene_coords(tracking_point_orig)

        # Calculate screen radii for proper scaling
        sun_edge_orig = sun_center_orig + np.array([r_sun, 0])
        planet_edge_orig = planet_center_orig + np.array([r_planet, 0])

        sun_edge_scene = to_scene_coords(sun_edge_orig)
        planet_edge_scene = to_scene_coords(planet_edge_orig)

        r_sun_screen = QLineF(sun_center_scene, sun_edge_scene).length()
        r_planet_screen = QLineF(planet_center_scene, planet_edge_scene).length()

        # Create sun gear (stationary)
        sun_color = QColor("#7f8c8d")  # Gray
        sun_gear = self.mechanism_scene.addEllipse(
            sun_center_scene.x() - r_sun_screen, sun_center_scene.y() - r_sun_screen,
            r_sun_screen * 2, r_sun_screen * 2,
            QPen(sun_color, 4),
            QBrush(sun_color.lighter(150))
        )
        sun_gear.setZValue(14)  # Base level, above parts
        visual_items.append(sun_gear)

        # Create planet gear (orbiting)
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = self.mechanism_scene.addEllipse(
            planet_center_scene.x() - r_planet_screen, planet_center_scene.y() - r_planet_screen,
            r_planet_screen * 2, r_planet_screen * 2,
            QPen(planet_color, 4),
            QBrush(planet_color.lighter(150))
        )
        planet_gear.setZValue(15)  # Above base level
        visual_items.append(planet_gear)

        # Create arm connecting planet center to tracking point
        arm_color = QColor("#f39c12")  # Golden
        arm_line = self.mechanism_scene.addLine(
            QLineF(planet_center_scene, tracking_point_scene),
            QPen(arm_color, 3)
        )
        arm_line.setZValue(15)
        visual_items.append(arm_line)

        # Create tracking point marker
        tracking_color = QColor("#e74c3c")  # Red
        tracking_marker = self.mechanism_scene.addEllipse(
            tracking_point_scene.x() - 8, tracking_point_scene.y() - 8, 16, 16,
            QPen(tracking_color, 2),
            QBrush(tracking_color)
        )
        tracking_marker.setZValue(20)
        visual_items.append(tracking_marker)

        # Create center markers for pivots
        center_color = QColor("#3498db")  # Blue

        # Sun center marker
        sun_center_marker = self.mechanism_scene.addEllipse(
            sun_center_scene.x() - 6, sun_center_scene.y() - 6, 12, 12,
            QPen(center_color.darker(150), 2),
            QBrush(center_color)
        )
        sun_center_marker.setZValue(25)
        visual_items.append(sun_center_marker)

        # Planet center marker
        planet_center_marker = self.mechanism_scene.addEllipse(
            planet_center_scene.x() - 4, planet_center_scene.y() - 4, 8, 8,
            QPen(center_color.darker(150), 1),
            QBrush(center_color.lighter(130))
        )
        planet_center_marker.setZValue(25)
        visual_items.append(planet_center_marker)


        return visual_items


    def _init_mechanism_path_trace(self, mechanism_id: str):
        """Initialize path tracing for a mechanism."""
        # Clear any existing trace for this mechanism first
        if mechanism_id in self.mechanism_trace_items:
            old_item = self.mechanism_trace_items[mechanism_id]
            if old_item and old_item.scene() == self.mechanism_scene:
                self.mechanism_scene.removeItem(old_item)

        self.mechanism_trace_points[mechanism_id] = []
        self.mechanism_trace_paths[mechanism_id] = QPainterPath()

        # Create visual trace item with thicker, more visible pen
        trace_item = QGraphicsPathItem()
        trace_pen = QPen(QColor("#ff3030"), 3.0)  # Red trace path, thinner
        trace_pen.setStyle(Qt.PenStyle.SolidLine)  # Solid line for better visibility
        trace_pen.setCosmetic(True)
        trace_item.setPen(trace_pen)
        trace_item.setZValue(Z_SELECTION_MARKER)  # Use standardized Z-level for selection markers
        self.mechanism_scene.addItem(trace_item)
        self.mechanism_trace_items[mechanism_id] = trace_item

    def _update_mechanism_path_trace(self, mechanism_id: str, position: QPointF):
        """Update the traced path for a mechanism."""
        if mechanism_id not in self.mechanism_trace_points:
            self._init_mechanism_path_trace(mechanism_id)

        # Add point to trace
        self.mechanism_trace_points[mechanism_id].append(position)

        # Limit trace length to prevent memory issues
        max_points = 1000
        if len(self.mechanism_trace_points[mechanism_id]) > max_points:
            self.mechanism_trace_points[mechanism_id] = self.mechanism_trace_points[mechanism_id][-max_points:]

        # Update visual path
        trace_points = self.mechanism_trace_points[mechanism_id]
        if len(trace_points) > 1:
            path = QPainterPath()
            path.moveTo(trace_points[0])
            for point in trace_points[1:]:
                path.lineTo(point)

            self.mechanism_trace_paths[mechanism_id] = path
            self.mechanism_trace_items[mechanism_id].setPath(path)

    def _clear_mechanism_trace(self, mechanism_id: str):
        """Clear trace path for a specific mechanism to prevent old paths from persisting."""
        try:
            # Remove trace visual item from scene
            if mechanism_id in self.mechanism_trace_items:
                trace_item = self.mechanism_trace_items[mechanism_id]
                if trace_item and hasattr(trace_item, 'scene') and trace_item.scene():
                    self.mechanism_scene.removeItem(trace_item)
                del self.mechanism_trace_items[mechanism_id]
                logging.debug(f"[PARAMETRIC] 🧹 Cleared trace visual item for {mechanism_id}")

            # Clear trace data
            if mechanism_id in self.mechanism_trace_points:
                del self.mechanism_trace_points[mechanism_id]
                logging.debug(f"[PARAMETRIC] 🧹 Cleared trace points for {mechanism_id}")

            if mechanism_id in self.mechanism_trace_paths:
                del self.mechanism_trace_paths[mechanism_id]
                logging.debug(f"[PARAMETRIC] 🧹 Cleared trace paths for {mechanism_id}")

            logging.info(f"[PARAMETRIC] ✅ Successfully cleared all traces for {mechanism_id}")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to clear mechanism trace for {mechanism_id}: {e}")

    def _generate_joint_motion_path(self, layer_data: dict, joint_id: str) -> QPainterPath | None:
        """Generate a motion path specifically for a skeleton joint using mechanism calculations."""
        joint_motion_path = QPainterPath()
        num_points = 180  # High resolution for smooth joint motion

        try:
            for i in range(num_points + 1):
                # Calculate angle for this point (full rotation)
                angle = (i / num_points) * 2 * math.pi

                # Calculate mechanism output position for joint
                joint_pos = self._calculate_mechanism_output(
                    layer_data.get("type"), layer_data.get("params", {}), angle, layer_data
                )

                if joint_pos:
                    if i == 0:
                        joint_motion_path.moveTo(joint_pos)
                    else:
                        joint_motion_path.lineTo(joint_pos)
                else:
                    return None

            return joint_motion_path

        except Exception:
            return None


    # ================================================================================
    # PARAMETRIC DESIGN SYSTEM (ULTRATHINK Architecture)
    # Jeff Dean Performance + Kent Beck Simplicity + Rob Pike Clarity
    # ================================================================================

    def _initialize_parametric_system(self):
        """
        Initialize the parametric design system for interactive manipulation.

        Features:
        - Interactive drag handles for mechanism parameters
        - Real-time parameter updates with constraint validation
        - Performance-optimized update throttling
        - Physics-based simulation for realistic motion
        """
        if not PARAMETRIC_AVAILABLE:
            return

        try:
            # Initialize parametric editor with the mechanism scene
            self.parametric_editor = ParametricEditor(self.mechanism_scene)
            
            # Connect signals for mechanism updates
            self.parametric_editor.mechanism_updated.connect(self._on_parametric_mechanism_update)
            self.parametric_editor.visual_refresh_requested.connect(self._on_parametric_visual_refresh)

            logging.info("Parametric design system (new editor) initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize parametric system: {e}")
            self.parametric_editor = None

    def toggle_parametric_mode(self, enabled: bool | None = None):
        """
        Toggle parametric editing mode on/off.

        Args:
            enabled: Explicit enable/disable, or None to toggle current state
        """
        logging.info(f"[PARAMETRIC] toggle_parametric_mode called with enabled={enabled}, current_mode={self.parametric_mode_enabled}")

        if not PARAMETRIC_AVAILABLE:
            logging.warning("Parametric mode not available - PARAMETRIC_AVAILABLE is False")
            return

        if not self.parametric_editor:
            logging.warning("Parametric mode not available - parametric_editor is None")
            return

        if enabled is None:
            enabled = not self.parametric_mode_enabled

        logging.info(f"[PARAMETRIC] Will set parametric mode to: {enabled}")

        # Debug: Show current state
        logging.info("[PARAMETRIC] Current system state:")
        logging.info(f"[PARAMETRIC] - PARAMETRIC_AVAILABLE: {PARAMETRIC_AVAILABLE}")
        logging.info(f"[PARAMETRIC] - parametric_editor: {self.parametric_editor is not None}")
        logging.info(f"[PARAMETRIC] - mechanism_layers count: {len(self.mechanism_layers) if hasattr(self, 'mechanism_layers') else 'No attribute'}")
        if hasattr(self, 'mechanism_layers'):
            logging.info(f"[PARAMETRIC] - mechanism_layers keys: {list(self.mechanism_layers.keys())}")

        # Check if we have mechanisms to edit
        if enabled and not self.mechanism_layers:
            logging.warning("Cannot enable parametric mode: no mechanisms loaded")
            # Show user-friendly message
            if hasattr(self, 'main_window'):
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self.main_window,
                    "Parametric Edit",
                    "Please generate mechanisms first using 'Get Mechanism' button.\n\n"
                    "Parametric editing allows you to interactively adjust mechanism parameters by dragging anchor points."
                )
            return

        # CRITICAL: Handle animation conflicts properly
        animation_was_running = False
        if enabled:
            # Enabling parametric mode - stop any running animation
            animation_was_running = self._is_animation_running()
            if animation_was_running:
                self._on_stop_animation()
                logging.info("[PARAMETRIC] Stopped animation before enabling parametric mode")

            # Store animation state for potential restoration
            if not hasattr(self, '_animation_state_before_parametric'):
                self._animation_state_before_parametric = animation_was_running
        else:
            # Disabling parametric mode - check if we should restore animation
            should_restore_animation = getattr(self, '_animation_state_before_parametric', False)
            if hasattr(self, '_animation_state_before_parametric'):
                delattr(self, '_animation_state_before_parametric')

        self.parametric_mode_enabled = enabled

        if enabled:
            self._enable_parametric_mode()
        else:
            self._disable_parametric_mode()

            # Restore animation if it was running before parametric mode
            if 'should_restore_animation' in locals() and should_restore_animation:
                # Small delay to ensure visual state is fully restored before starting animation
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(100, self._on_start_animation)
                logging.info("[PARAMETRIC] Scheduled animation restoration after parametric mode disabled")

        logging.info(f"Parametric mode {'enabled' if enabled else 'disabled'}")

    def _enable_parametric_mode(self):
        """Enable parametric editing mode - show interactive handles.

        ULTRATHINK: Enhanced to use new ParametricEditor system.
        """
        if not self.parametric_editor:
            return

        try:
            logging.info(f"[PARAMETRIC] 🚀 Enabling parametric mode for {len(self.mechanism_layers)} mechanisms")

            # CRITICAL FIX: Clear all mechanism traces when entering parametric mode
            logging.info("[PARAMETRIC] 🧹 Clearing all existing mechanism traces")
            for mechanism_id in list(self.mechanism_layers.keys()):
                self._clear_mechanism_trace(mechanism_id)

            # Create editors for all existing mechanisms
            for mechanism_id, layer_data in self.mechanism_layers.items():
                part_name = layer_data.get("part_name")
                mechanism_type = layer_data.get("type")
                logging.info(f"[PARAMETRIC] 🔨 Creating editor for mechanism {mechanism_id}, type: {mechanism_type}, part: {part_name}")
                
                try:
                    if "params" not in layer_data:
                        layer_data["params"] = {}
                    
                    # CRITICAL FIX: Ensure all required parameters are present for each mechanism type
                    
                    if mechanism_type == "cam":
                        # CAM: Ensure center_x and center_y are in params
                        cam_position = layer_data.get("cam_position")
                        if cam_position and len(cam_position) >= 2:
                            layer_data["params"]["center_x"] = cam_position[0]
                            layer_data["params"]["center_y"] = cam_position[1]
                            logging.info(f"[PARAMETRIC] CAM: Set center to ({cam_position[0]:.1f}, {cam_position[1]:.1f})")
                        else:
                            # Fallback to default position if cam_position not set
                            layer_data["params"]["center_x"] = 400
                            layer_data["params"]["center_y"] = 300
                            logging.warning("[PARAMETRIC] CAM: Using default center position (400, 300)")
                    
                    elif mechanism_type == "4_bar_linkage":
                        # 4-BAR: Extract anchor positions from simulation data and transform to scene coords
                        params = layer_data["params"]
                        full_sim_data = layer_data.get("full_simulation_data", {})
                        
                        if "joint_positions" in full_sim_data:
                            joint_positions = full_sim_data["joint_positions"]
                            if ("p1_positions" in joint_positions and len(joint_positions["p1_positions"]) > 0 and
                                "p2_positions" in joint_positions and len(joint_positions["p2_positions"]) > 0):
                                # Use first frame positions as anchor positions
                                p1 = joint_positions["p1_positions"][0]
                                p2 = joint_positions["p2_positions"][0]
                                p3 = joint_positions["p3_positions"][0] if "p3_positions" in joint_positions else None
                                p4 = joint_positions["p4_positions"][0] if "p4_positions" in joint_positions else None
                                
                                # Transform ALL positions to scene coordinates using the same function as visuals
                                to_scene = self._get_scene_transform_function(layer_data)
                                if to_scene:
                                    p1_scene = to_scene(np.array(p1))
                                    p2_scene = to_scene(np.array(p2))
                                    
                                    # Convert QPointF to x,y values
                                    if hasattr(p1_scene, 'x'):
                                        params["anchor1_x"] = p1_scene.x()
                                        params["anchor1_y"] = p1_scene.y()
                                    else:
                                        params["anchor1_x"] = float(p1_scene[0]) if isinstance(p1_scene, np.ndarray) else p1_scene[0]
                                        params["anchor1_y"] = float(p1_scene[1]) if isinstance(p1_scene, np.ndarray) else p1_scene[1]
                                    
                                    if hasattr(p2_scene, 'x'):
                                        params["anchor2_x"] = p2_scene.x()
                                        params["anchor2_y"] = p2_scene.y()
                                    else:
                                        params["anchor2_x"] = float(p2_scene[0]) if isinstance(p2_scene, np.ndarray) else p2_scene[0]
                                        params["anchor2_y"] = float(p2_scene[1]) if isinstance(p2_scene, np.ndarray) else p2_scene[1]
                                    
                                    # Transform p3 and p4 for angles and coupler position
                                    if p3 is not None:
                                        p3_scene = to_scene(np.array(p3))
                                        if hasattr(p3_scene, 'x'):
                                            p3_x, p3_y = p3_scene.x(), p3_scene.y()
                                        else:
                                            p3_x = float(p3_scene[0]) if isinstance(p3_scene, np.ndarray) else p3_scene[0]
                                            p3_y = float(p3_scene[1]) if isinstance(p3_scene, np.ndarray) else p3_scene[1]
                                        
                                        # Calculate crank angle in scene space
                                        dx = p3_x - params["anchor1_x"]
                                        dy = p3_y - params["anchor1_y"]
                                        params["crank_angle"] = math.degrees(math.atan2(dy, dx))
                                        params["crank_x"] = p3_x  # Store crank position
                                        params["crank_y"] = p3_y
                                    
                                    if p4 is not None:
                                        p4_scene = to_scene(np.array(p4))
                                        if hasattr(p4_scene, 'x'):
                                            p4_x, p4_y = p4_scene.x(), p4_scene.y()
                                        else:
                                            p4_x = float(p4_scene[0]) if isinstance(p4_scene, np.ndarray) else p4_scene[0]
                                            p4_y = float(p4_scene[1]) if isinstance(p4_scene, np.ndarray) else p4_scene[1]
                                        
                                        # Calculate rocker angle in scene space
                                        dx = p4_x - params["anchor2_x"]
                                        dy = p4_y - params["anchor2_y"]
                                        params["rocker_angle"] = math.degrees(math.atan2(dy, dx))
                                        params["rocker_x"] = p4_x  # Store rocker position
                                        params["rocker_y"] = p4_y
                                        
                                        # Calculate coupler position
                                        if p3 is not None:
                                            # Get coupler offset from original params
                                            coupler_point_x = params.get("coupler_point_x", 0.0)
                                            coupler_point_y = params.get("coupler_point_y", 0.0)
                                            
                                            # Calculate coupler position in scene space (like in visuals)
                                            coupler_vec_x = p4_x - p3_x
                                            coupler_vec_y = p4_y - p3_y
                                            coupler_length = math.sqrt(coupler_vec_x**2 + coupler_vec_y**2)
                                            
                                            if coupler_length > 0:
                                                coupler_unit_x = coupler_vec_x / coupler_length
                                                coupler_unit_y = coupler_vec_y / coupler_length
                                                coupler_normal_x = -coupler_unit_y
                                                coupler_normal_y = coupler_unit_x
                                                
                                                # Transform coupler offset to scene scale
                                                scale = layer_data.get("transform_params", {}).get("scale", 1.0)
                                                scaled_offset_x = coupler_point_x * scale
                                                scaled_offset_y = coupler_point_y * scale
                                                
                                                params["coupler_x"] = p3_x + scaled_offset_x * coupler_unit_x + scaled_offset_y * coupler_normal_x
                                                params["coupler_y"] = p3_y + scaled_offset_x * coupler_unit_y + scaled_offset_y * coupler_normal_y
                                            else:
                                                params["coupler_x"] = p3_x
                                                params["coupler_y"] = p3_y
                                
                                else:
                                    # No transformation available, use raw values
                                    params["anchor1_x"] = p1[0] if isinstance(p1, (list, tuple)) else p1
                                    params["anchor1_y"] = p1[1] if isinstance(p1, (list, tuple)) else 0
                                    params["anchor2_x"] = p2[0] if isinstance(p2, (list, tuple)) else p2
                                    params["anchor2_y"] = p2[1] if isinstance(p2, (list, tuple)) else 0
                                    params["crank_angle"] = 0
                                    params["rocker_angle"] = 45
                                    params["coupler_x"] = 350
                                    params["coupler_y"] = 250
                                
                                logging.info(f"[PARAMETRIC] 4-BAR: Set anchors from simulation data (scene coords)")
                                logging.info(f"[PARAMETRIC] anchor1: ({params.get('anchor1_x', 0):.1f}, {params.get('anchor1_y', 0):.1f})")
                                logging.info(f"[PARAMETRIC] anchor2: ({params.get('anchor2_x', 0):.1f}, {params.get('anchor2_y', 0):.1f})")
                            else:
                                # Fallback: Use default positions
                                l1 = params.get("l1", 100)
                                params["anchor1_x"] = 400
                                params["anchor1_y"] = 300
                                params["anchor2_x"] = 400 + l1
                                params["anchor2_y"] = 300
                                params["crank_angle"] = 0
                                params["rocker_angle"] = 45
                                params["coupler_x"] = 450
                                params["coupler_y"] = 250
                                logging.warning("[PARAMETRIC] 4-BAR: Using default anchor positions")
                        else:
                            # No simulation data, use defaults
                            l1 = params.get("l1", 100)
                            params["anchor1_x"] = 400
                            params["anchor1_y"] = 300
                            params["anchor2_x"] = 400 + l1
                            params["anchor2_y"] = 300
                            params["crank_angle"] = 0
                            params["rocker_angle"] = 45
                            params["coupler_x"] = 450
                            params["coupler_y"] = 250
                    
                    elif mechanism_type in ["gear", "simple_gear"]:
                        # GEAR: Convert r1, r2 to gear parameters with scene positions
                        params = layer_data["params"]
                        full_sim_data = layer_data.get("full_simulation_data", {})
                        
                        # Map radius parameters
                        if "r1" in params:
                            params["gear1_radius"] = params["r1"]
                        if "r2" in params:
                            params["gear2_radius"] = params["r2"]
                        
                        # Try to get positions from simulation data
                        to_scene = self._get_scene_transform_function(layer_data)
                        
                        if "gear_data" in full_sim_data and to_scene:
                            gear_data = full_sim_data["gear_data"]
                            # Get first frame gear centers
                            if "gear1_centers" in gear_data and len(gear_data["gear1_centers"]) > 0:
                                g1_center = gear_data["gear1_centers"][0]
                                g1_scene = to_scene(np.array(g1_center))
                                if hasattr(g1_scene, 'x'):
                                    params["gear1_x"] = g1_scene.x()
                                    params["gear1_y"] = g1_scene.y()
                                else:
                                    params["gear1_x"] = float(g1_scene[0]) if isinstance(g1_scene, np.ndarray) else g1_scene[0]
                                    params["gear1_y"] = float(g1_scene[1]) if isinstance(g1_scene, np.ndarray) else g1_scene[1]
                            
                            if "gear2_centers" in gear_data and len(gear_data["gear2_centers"]) > 0:
                                g2_center = gear_data["gear2_centers"][0]
                                g2_scene = to_scene(np.array(g2_center))
                                if hasattr(g2_scene, 'x'):
                                    params["gear2_x"] = g2_scene.x()
                                    params["gear2_y"] = g2_scene.y()
                                else:
                                    params["gear2_x"] = float(g2_scene[0]) if isinstance(g2_scene, np.ndarray) else g2_scene[0]
                                    params["gear2_y"] = float(g2_scene[1]) if isinstance(g2_scene, np.ndarray) else g2_scene[1]
                        else:
                            # Set default scene positions if not present
                            if "gear1_x" not in params:
                                params["gear1_x"] = 400
                            if "gear1_y" not in params:
                                params["gear1_y"] = 300
                            if "gear2_x" not in params:
                                # Position gear2 to mesh with gear1
                                r1 = params.get("gear1_radius", params.get("r1", 40))
                                r2 = params.get("gear2_radius", params.get("r2", 60))
                                params["gear2_x"] = params["gear1_x"] + r1 + r2 + 2  # Small clearance
                            if "gear2_y" not in params:
                                params["gear2_y"] = params["gear1_y"]
                        
                        logging.info(f"[PARAMETRIC] GEAR: Set gear positions in scene coords")
                    
                    elif mechanism_type == "planetary_gear":
                        # PLANETARY GEAR: Map to GearEditor parameters with scene coordinates
                        params = layer_data["params"]
                        full_sim_data = layer_data.get("full_simulation_data", {})
                        
                        # Map radius parameters
                        if "r_sun" in params:
                            params["gear1_radius"] = params["r_sun"]
                        elif "sun_radius" in params:
                            params["gear1_radius"] = params["sun_radius"]
                        else:
                            params["gear1_radius"] = 20  # Default sun radius
                        
                        if "r_planet" in params:
                            params["gear2_radius"] = params["r_planet"]
                        elif "planet_radius" in params:
                            params["gear2_radius"] = params["planet_radius"]
                        else:
                            params["gear2_radius"] = 30  # Default planet radius
                        
                        # Try to get positions from simulation data
                        to_scene = self._get_scene_transform_function(layer_data)
                        
                        if "gear_positions" in full_sim_data and to_scene:
                            gear_pos = full_sim_data["gear_positions"]
                            # Get sun center
                            if "sun_centers" in gear_pos and len(gear_pos["sun_centers"]) > 0:
                                sun_center = gear_pos["sun_centers"][0]
                                sun_scene = to_scene(np.array(sun_center))
                                if hasattr(sun_scene, 'x'):
                                    params["gear1_x"] = sun_scene.x()
                                    params["gear1_y"] = sun_scene.y()
                                else:
                                    params["gear1_x"] = float(sun_scene[0]) if isinstance(sun_scene, np.ndarray) else sun_scene[0]
                                    params["gear1_y"] = float(sun_scene[1]) if isinstance(sun_scene, np.ndarray) else sun_scene[1]
                            
                            # Get planet center
                            if "planet_centers" in gear_pos and len(gear_pos["planet_centers"]) > 0:
                                planet_center = gear_pos["planet_centers"][0]
                                planet_scene = to_scene(np.array(planet_center))
                                if hasattr(planet_scene, 'x'):
                                    params["gear2_x"] = planet_scene.x()
                                    params["gear2_y"] = planet_scene.y()
                                else:
                                    params["gear2_x"] = float(planet_scene[0]) if isinstance(planet_scene, np.ndarray) else planet_scene[0]
                                    params["gear2_y"] = float(planet_scene[1]) if isinstance(planet_scene, np.ndarray) else planet_scene[1]
                        else:
                            # Set default scene positions
                            if "gear1_x" not in params:
                                params["gear1_x"] = 400
                            if "gear1_y" not in params:
                                params["gear1_y"] = 300
                            
                            # Set planet position based on arm length
                            arm_length = params.get("arm_length", params.get("carrier_length", 50))
                            if "gear2_x" not in params:
                                params["gear2_x"] = params["gear1_x"] + params["gear1_radius"] + params["gear2_radius"] + arm_length
                            if "gear2_y" not in params:
                                params["gear2_y"] = params["gear1_y"]
                        
                        logging.info(f"[PARAMETRIC] PLANETARY: Set positions in scene coords")
                    
                    # Create appropriate editor for mechanism type
                    editor = self.parametric_editor.create_editor(mechanism_id, layer_data)
                    if editor:
                        logging.info(f"[PARAMETRIC] ✅ Successfully created editor for {mechanism_id} (part: {part_name})")
                except Exception as e:
                    logging.error(f"[PARAMETRIC] ❌ Failed to create editor for {mechanism_id}: {e}")
                    import traceback
                    logging.error(f"[PARAMETRIC] Traceback: {traceback.format_exc()}")

            # Enable editing mode
            self.parametric_editor.enable_editing()

            # Set active editor based on currently selected part in the UI
            logging.info(f"[PARAMETRIC] 🎯 Current selected_part_name: {self.selected_part_name}")
            
            # Get the currently selected item from the mechanism layers list
            selected_items = self.mechanism_layers_list.selectedItems()
            if selected_items:
                selected_part = selected_items[0].data(Qt.ItemDataRole.UserRole)
                logging.info(f"[PARAMETRIC] 📌 Currently selected in UI: {selected_part}")
                
                # Find mechanism for the UI-selected part
                found = False
                for mechanism_id, layer_data in self.mechanism_layers.items():
                    part_name = layer_data.get("part_name")
                    if part_name == selected_part:
                        self.parametric_editor.set_active_editor(mechanism_id)
                        logging.info(f"[PARAMETRIC] ✅ Activated editor for selected part: {mechanism_id} (part: {selected_part})")
                        found = True
                        break
                    else:
                        logging.debug(f"[PARAMETRIC] Skipping {mechanism_id} (part: {part_name} != {selected_part})")
                
                if not found:
                    logging.warning(f"[PARAMETRIC] ⚠️ No mechanism found for selected part: {selected_part}")
                    # Default to first mechanism if no match
                    if self.mechanism_layers:
                        first_id = list(self.mechanism_layers.keys())[0]
                        self.parametric_editor.set_active_editor(first_id)
                        logging.info(f"[PARAMETRIC] Using first mechanism as fallback: {first_id}")
            else:
                logging.info(f"[PARAMETRIC] No part selected in UI, using selected_part_name: {self.selected_part_name}")
                if self.selected_part_name:
                    # Find mechanism for selected part
                    for mechanism_id, layer_data in self.mechanism_layers.items():
                        if layer_data.get("part_name") == self.selected_part_name:
                            self.parametric_editor.set_active_editor(mechanism_id)
                            logging.info(f"[PARAMETRIC] Set active editor for {mechanism_id} (part: {self.selected_part_name})")
                            break

            # Update UI to show parametric mode
            if self.parametric_edit_btn:
                self.parametric_edit_btn.setText("Exit Parametric Mode")
                self.parametric_edit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)

            # Disable animation controls in parametric mode
            self._disable_animation_controls_for_parametric()
            logging.info("[PARAMETRIC] ✅ Disabled animation controls during parametric editing")

            # Disable mechanism visual interaction to allow handle interaction
            self._disable_mechanism_visual_interaction()

            logging.info("[PARAMETRIC] ✅ Parametric mode enabled successfully")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to enable parametric mode: {e}")
            import traceback
            logging.error(f"[PARAMETRIC] ❌ Traceback: {traceback.format_exc()}")

    def _disable_animation_controls_for_parametric(self):
        """
        Disable animation controls when parametric mode is active.
        ULTRATHINK: Prevent conflicts between parametric editing and animation.
        """
        try:
            # Find and disable play button
            if hasattr(self, 'play_btn') and self.play_btn:
                self.play_btn.setEnabled(False)
                self.play_btn.setToolTip("⚠️ Animation disabled during parametric editing")
                logging.info("[PARAMETRIC] 🚫 Disabled play button")

            # Find and disable stop button
            if hasattr(self, 'stop_btn') and self.stop_btn:
                self.stop_btn.setEnabled(False)
                self.stop_btn.setToolTip("⚠️ Animation disabled during parametric editing")
                logging.info("[PARAMETRIC] 🚫 Disabled stop button")

            # Find and disable reset button
            if hasattr(self, 'reset_btn') and self.reset_btn:
                self.reset_btn.setEnabled(False)
                self.reset_btn.setToolTip("⚠️ Animation disabled during parametric editing")
                logging.info("[PARAMETRIC] 🚫 Disabled reset button")

            # Disable any running animation
            if hasattr(self, '_is_animation_running') and self._is_animation_running():
                if hasattr(self, '_on_stop_animation'):
                    self._on_stop_animation()
                    logging.info("[PARAMETRIC] ⏹️ Stopped running animation")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to disable animation controls: {e}")

    def _enable_animation_controls_after_parametric(self):
        """
        Re-enable animation controls when exiting parametric mode.
        ULTRATHINK: Restore normal functionality after parametric editing.
        """
        try:
            # Re-enable play button
            if hasattr(self, 'play_btn') and self.play_btn:
                self.play_btn.setEnabled(True)
                self.play_btn.setToolTip("▶️ Play mechanism animation")
                logging.info("[PARAMETRIC] ✅ Re-enabled play button")

            # Re-enable stop button
            if hasattr(self, 'stop_btn') and self.stop_btn:
                self.stop_btn.setEnabled(True)
                self.stop_btn.setToolTip("⏹️ Stop mechanism animation")
                logging.info("[PARAMETRIC] ✅ Re-enabled stop button")

            # Re-enable reset button
            if hasattr(self, 'reset_btn') and self.reset_btn:
                self.reset_btn.setEnabled(True)
                self.reset_btn.setToolTip("🔄 Reset mechanism to initial state")
                logging.info("[PARAMETRIC] ✅ Re-enabled reset button")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to enable animation controls: {e}")


    def _check_4bar_validity(self, key_points: dict) -> str:
        """
        Check 4-bar linkage kinematic constraints.
        ULTRATHINK: Triangle inequality and Grashof condition.
        """
        try:
            required_points = ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]
            if not all(point in key_points for point in required_points):
                return "invalid"

            # Get positions
            p1 = QPointF(key_points["ground_pivot_1"][0], key_points["ground_pivot_1"][1])
            p2 = QPointF(key_points["ground_pivot_2"][0], key_points["ground_pivot_2"][1])
            p3 = QPointF(key_points["crank_end"][0], key_points["crank_end"][1])
            p4 = QPointF(key_points["rocker_end"][0], key_points["rocker_end"][1])

            # Calculate link lengths
            l1 = math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)  # Ground link
            l2 = math.sqrt((p3.x() - p1.x())**2 + (p3.y() - p1.y())**2)  # Crank
            l3 = math.sqrt((p4.x() - p3.x())**2 + (p4.y() - p3.y())**2)  # Coupler
            l4 = math.sqrt((p4.x() - p2.x())**2 + (p4.y() - p2.y())**2)  # Rocker

            # Check triangle inequality (existence condition)
            if l3 > (l2 + l4 - l1) and l3 < (l2 + l4 + l1):
                # Check Grashof condition for good mobility
                links = [l1, l2, l3, l4]
                s = min(links)  # shortest
                l = max(links)  # longest
                p = sum(links) - s - l  # sum of other two

                if s + l <= p:
                    return "valid"  # Grashof linkage
                else:
                    return "approximate"  # Non-Grashof but kinematically valid
            else:
                return "invalid"  # Triangle inequality violated

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ 4-bar validity check failed: {e}")
            return "invalid"

    def _check_multibar_validity(self, key_points: dict) -> str:
        """Check multi-bar linkage validity based on reasonable distances."""
        if len(key_points) < 3:
            return "invalid"
        # Simple check - if points are not too far apart, assume approximate
        return "approximate"

    def _check_gear_validity(self, key_points: dict) -> str:
        """Check gear mechanism validity based on center distances."""
        if len(key_points) < 2:
            return "invalid"
        # Simple check for gear mechanisms
        return "approximate"

    def _disable_parametric_mode(self):
        """Disable parametric editing mode - hide handles and restore normal interaction.

        ULTRATHINK: Enhanced to use new ParametricEditor system.
        """
        if not self.parametric_editor:
            return

        try:
            logging.info("[PARAMETRIC] 🛑 Disabling parametric mode")

            # Disable editing mode
            self.parametric_editor.disable_editing()

            # Remove all editors
            for mechanism_id in list(self.parametric_editor.editors.keys()):
                self.parametric_editor.remove_editor(mechanism_id)
                logging.info(f"[PARAMETRIC] 🗑️ Removed editor for {mechanism_id}")

            logging.info(f"[PARAMETRIC] ✅ Removed all editors")

            # Clear all mechanism traces on exit  
            logging.info("[PARAMETRIC] 🧹 Clearing all mechanism traces on exit")
            for mechanism_id in list(self.mechanism_trace_items.keys()):
                self._clear_mechanism_trace(mechanism_id)
                logging.info(f"[PARAMETRIC] ✅ Successfully cleared all traces for {mechanism_id}")

            # Re-enable mechanism visual interaction
            self._enable_mechanism_visual_interaction()

            # Update UI
            if self.parametric_edit_btn:
                self.parametric_edit_btn.setText("Enter Parametric Mode")
                self.parametric_edit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #229954;
                    }
                """)

            # Re-enable animation controls
            self._enable_animation_controls_after_parametric()
            logging.info("[PARAMETRIC] ✅ Re-enabled animation controls")

            logging.info("[PARAMETRIC] ✅ Parametric mode disabled successfully")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to disable parametric mode: {e}")
            import traceback
            logging.error(f"[PARAMETRIC] ❌ Traceback: {traceback.format_exc()}")

    def _create_rotation_handle(self, mechanism_id: str, center_pos: QPointF, radius: float = 60) -> QGraphicsItem:
        """
        Create a rotation handle using custom class with built-in drag logic.
        ULTRATHINK: Use custom RotationHandle class for proper event handling.

        Args:
            mechanism_id: ID of the mechanism
            center_pos: Center position for the rotation handle
            radius: Distance from center for the handle

        Returns:
            QGraphicsItem: The rotation handle with built-in rotation logic
        """
        try:
            logging.info(f"[PARAMETRIC] 🔄 Creating interactive rotation handle for {mechanism_id}")

            # Create custom rotation handle with built-in logic
            rotation_handle = self.RotationHandle(
                parent_tab=self,
                mechanism_id=mechanism_id,
                center_pos=center_pos,
                radius=radius
            )

            logging.info(f"[PARAMETRIC] ✅ Created interactive rotation handle at ({rotation_handle.pos().x():.1f}, {rotation_handle.pos().y():.1f})")
            logging.info(f"[PARAMETRIC] Rotation center: ({center_pos.x():.1f}, {center_pos.y():.1f})")

            return rotation_handle

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to create interactive rotation handle: {e}")
            import traceback
            logging.error(f"[PARAMETRIC] ❌ Traceback: {traceback.format_exc()}")
            return None

    def _rotate_mechanism(self, mechanism_id: str, center: QPointF, angle_radians: float):
        """
        Rotate all anchor points freely - no physics constraints.
        ULTRATHINK: User freedom mode - allow any configuration even if physically impossible.

        Args:
            mechanism_id: ID of the mechanism to rotate
            center: Center point for rotation (user's drag position)
            angle_radians: Angle to rotate in radians
        """
        try:
            if mechanism_id not in self.parametric_handles:
                logging.warning(f"[PARAMETRIC] No handles found for mechanism {mechanism_id}")
                return

            handles = self.parametric_handles[mechanism_id]

            cos_angle = math.cos(angle_radians)
            sin_angle = math.sin(angle_radians)

            rotated_count = 0

            # Apply rotation to all anchor handles - no constraints!
            for handle in handles:
                # Skip the rotation handle itself
                if hasattr(handle, 'handle_type') and handle.handle_type == 'rotation':
                    continue

                current_pos = handle.pos()

                # Translate to rotation center
                dx = current_pos.x() - center.x()
                dy = current_pos.y() - center.y()

                # Apply rotation matrix
                new_dx = dx * cos_angle - dy * sin_angle
                new_dy = dx * sin_angle + dy * cos_angle

                # Translate back
                new_pos = QPointF(center.x() + new_dx, center.y() + new_dy)

                # Apply new position immediately - no validation!
                handle.setPos(new_pos)
                rotated_count += 1

                # Update key_points in layer_data
                if hasattr(handle, 'anchor_name') and mechanism_id in self.mechanism_layers:
                    layer_data = self.mechanism_layers[mechanism_id]
                    if "key_points" not in layer_data:
                        layer_data["key_points"] = {}
                    layer_data["key_points"][handle.anchor_name] = [new_pos.x(), new_pos.y()]

            # Update visual feedback (always show as "approximate" in free mode)
            if rotated_count > 0:
                self._show_free_edit_feedback(mechanism_id)

            # Force scene update
            self.mechanism_scene.update()

            logging.info(f"[PARAMETRIC] 🆓 Free rotation: {rotated_count} anchors by {math.degrees(angle_radians):.1f}° around user position")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Free rotation failed: {e}")
            import traceback
            logging.error(f"[PARAMETRIC] ❌ Traceback: {traceback.format_exc()}")


        # Create rotation handle at the geometric center
        rotation_handle = self._create_rotation_handle(mechanism_id, mechanism_center, radius=100)

        if rotation_handle:
            # Store the calculated center in the rotation handle for consistent reference
            rotation_handle.true_mechanism_center = mechanism_center

            # Add rotation handle to scene
            self.mechanism_scene.addItem(rotation_handle)
            handles.append(rotation_handle)

            logging.info(f"[PARAMETRIC] ✅ Added rotation handle to {mechanism_id} with true center")
            return True
        else:
            logging.warning(f"[PARAMETRIC] ⚠️ Failed to create rotation handle for {mechanism_id}")
            return False

    def _regenerate_mechanism_simulation(self, mechanism_id: str, layer_data: dict):
        """
        Regenerate simulation data for a mechanism after parameters have changed.
        This recalculates joint positions and paths for the new configuration.
        """
        try:
            mech_type = layer_data.get("type")
            params = layer_data.get("params", {})

            logging.info(f"[PARAMETRIC] 🔄 Regenerating simulation for {mech_type} mechanism {mechanism_id}")

            # CRITICAL FIX: Clear existing mechanism traces to prevent old red paths from persisting
            self._clear_mechanism_trace(mechanism_id)

            if mech_type == "4_bar_linkage":
                # Generate new simulation data for 4-bar linkage
                num_frames = 100
                joint_positions = {
                    "p1_positions": [],
                    "p2_positions": [],
                    "p3_positions": [],
                    "p4_positions": []
                }

                p1 = np.array(params.get("ground_pivot_1", [0, 0]))
                p2 = np.array(params.get("ground_pivot_2", [100, 0]))
                L2 = params.get("L2", 40)  # Crank length
                L3 = params.get("L3", 60)  # Coupler length
                L4 = params.get("L4", 50)  # Rocker length

                for i in range(num_frames):
                    theta = (i / num_frames) * 2 * np.pi

                    # Calculate crank position (p3)
                    p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])

                    # Calculate rocker position (p4) using circle-circle intersection
                    # p4 must be L3 from p3 and L4 from p2
                    p4 = self._solve_circle_intersection(p3, L3, p2, L4)

                    if p4 is not None:
                        joint_positions["p1_positions"].append(p1.tolist())
                        joint_positions["p2_positions"].append(p2.tolist())
                        joint_positions["p3_positions"].append(p3.tolist())
                        joint_positions["p4_positions"].append(p4.tolist())

                # Store the new simulation data
                layer_data["full_simulation_data"] = {
                    "joint_positions": joint_positions
                }

                logging.info(f"[PARAMETRIC] ✅ Generated {len(joint_positions['p1_positions'])} frames for 4-bar linkage")

            elif mech_type == "5_bar_linkage":
                # Generate new simulation data for 5-bar linkage
                num_frames = 100
                joint_positions = {
                    "p1_positions": [],
                    "p2_positions": [],
                    "p3_positions": [],
                    "p4_positions": [],
                    "p5_positions": []
                }

                # Get updated positions from key_points
                key_points = layer_data.get("key_points", {})
                p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
                p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))

                # Calculate link lengths from key points
                if "joint_3" in key_points and "joint_4" in key_points and "joint_5" in key_points:
                    p3 = np.array(key_points["joint_3"])
                    p4 = np.array(key_points["joint_4"])
                    p5 = np.array(key_points["joint_5"])

                    L2 = np.linalg.norm(p3 - p1)  # Input link
                    L3 = np.linalg.norm(p4 - p3)  # Coupler 1
                    L4 = np.linalg.norm(p5 - p4)  # Coupler 2
                    L5 = np.linalg.norm(p5 - p2)  # Output link

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

                    # Calculate positions for 5-bar linkage
                    p3 = p1 + L2 * np.array([np.cos(theta), np.sin(theta)])

                    # Simplified 5-bar kinematics - use approximate positions
                    p4 = p3 + L3 * np.array([np.cos(theta + 0.5), np.sin(theta + 0.5)])
                    p5 = self._solve_circle_intersection(p4, L4, p2, L5)

                    if p5 is not None:
                        joint_positions["p1_positions"].append(p1.tolist())
                        joint_positions["p2_positions"].append(p2.tolist())
                        joint_positions["p3_positions"].append(p3.tolist())
                        joint_positions["p4_positions"].append(p4.tolist())
                        joint_positions["p5_positions"].append(p5.tolist())

                layer_data["full_simulation_data"] = {
                    "joint_positions": joint_positions
                }

                logging.info(f"[PARAMETRIC] ✅ Generated {len(joint_positions['p1_positions'])} frames for 5-bar linkage")

            elif mech_type == "6_bar_linkage":
                # Generate new simulation data for 6-bar linkage (Stephenson Type I)
                num_frames = 100
                joint_positions = {
                    "p1_positions": [],
                    "p2_positions": [],
                    "p3_positions": [],
                    "p4_positions": [],
                    "p5_positions": [],
                    "p6_positions": []
                }

                # Get updated positions from key_points
                key_points = layer_data.get("key_points", {})
                p1 = np.array(key_points.get("ground_pivot_1", [0, 0]))
                p2 = np.array(key_points.get("ground_pivot_2", [100, 0]))
                p6 = np.array(key_points.get("ground_pivot_3", [50, -30]))

                # Calculate link lengths
                if all(k in key_points for k in ["joint_3", "joint_4", "joint_5"]):
                    p3 = np.array(key_points["joint_3"])
                    p4 = np.array(key_points["joint_4"])
                    p5 = np.array(key_points["joint_5"])

                    L2 = np.linalg.norm(p3 - p1)
                    L3 = np.linalg.norm(p4 - p3)
                    L4 = np.linalg.norm(p4 - p2)
                    L5 = np.linalg.norm(p5 - p4)
                    L6 = np.linalg.norm(p5 - p6)

                    params.update({
                        "L2": float(L2), "L3": float(L3), "L4": float(L4),
                        "L5": float(L5), "L6": float(L6)
                    })
                else:
                    L2 = params.get("L2", 40)
                    L3 = params.get("L3", 60)
                    L4 = params.get("L4", 50)
                    L5 = params.get("L5", 45)
                    L6 = params.get("L6", 55)

                for i in range(num_frames):
                    theta = (i / num_frames) * 2 * np.pi

                    # Calculate positions for 6-bar linkage
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

                layer_data["full_simulation_data"] = {
                    "joint_positions": joint_positions
                }

                logging.info(f"[PARAMETRIC] ✅ Generated {len(joint_positions['p1_positions'])} frames for 6-bar linkage")

            elif mech_type == "cam":
                # Generate cam mechanism data with correct physics
                num_frames = 100
                base_radius = params.get("base_radius", 25.0)
                eccentricity = params.get("eccentricity", 10.0)
                rod_length = params.get("follower_rod_length", 40.0)

                # Update from key_points if available
                key_points = layer_data.get("key_points", {})
                if "cam_center" in key_points:
                    cam_center_base = np.array(key_points["cam_center"])
                else:
                    cam_center_base = np.array([0, 0])

                cam_data = {
                    "cam_centers": [],
                    "follower_y_positions": []
                }

                for i in range(num_frames):
                    # Cam rotates in place at cam_center_base
                    angle = (i / num_frames) * 2 * np.pi

                    # Calculate cam radius at this rotation angle using our corrected egg shape
                    # Proper cam profile: lift when convex part is at bottom (pushes follower up)
                    lift = eccentricity * (1 + np.cos(angle + np.pi/2)) / 2  # Shifted for proper phase
                    cam_radius_at_angle = base_radius + lift

                    # Cam center stays fixed (cam rotates in place)
                    current_cam_center = cam_center_base

                    # Follower rides on top of cam at the contact point
                    # The follower's Y position is cam center Y + cam radius + rod length offset
                    follower_y = current_cam_center[1] - cam_radius_at_angle - rod_length

                    cam_data["cam_centers"].append(current_cam_center.tolist())
                    cam_data["follower_y_positions"].append(follower_y)

                layer_data["full_simulation_data"] = {
                    "cam_data": cam_data
                }

                logging.info("[PARAMETRIC] ✅ Generated cam mechanism data")

            elif mech_type == "gear":
                # Generate gear rotation data
                num_frames = 100
                r1 = params.get("r1", 30)
                r2 = params.get("r2", 50)

                # Update gear positions from key_points if available
                key_points = layer_data.get("key_points", {})
                if "gear1_center" in key_points and "gear2_center" in key_points:
                    g1 = np.array(key_points["gear1_center"])
                    g2 = np.array(key_points["gear2_center"])
                    distance = np.linalg.norm(g2 - g1)

                    # Maintain gear ratio but adjust sizes to fit distance
                    ratio = r2 / r1
                    r1 = distance / (1 + ratio)
                    r2 = r1 * ratio
                    params["r1"] = float(r1)
                    params["r2"] = float(r2)

                gear_data = {
                    "gear1_angles": [],
                    "gear2_angles": []
                }

                for i in range(num_frames):
                    theta1 = (i / num_frames) * 2 * np.pi
                    theta2 = -theta1 * (r1 / r2)  # Gear ratio

                    gear_data["gear1_angles"].append(theta1)
                    gear_data["gear2_angles"].append(theta2)

                layer_data["full_simulation_data"] = {
                    "gear_data": gear_data
                }

                logging.info("[PARAMETRIC] ✅ Generated gear rotation data")

            elif mech_type == "planetary_gear":
                # Generate planetary gear data
                num_frames = 100
                r_sun = params.get("r_sun", 20)
                r_planet = params.get("r_planet", 30)
                arm_length = params.get("arm_length", 15)

                # Update from key_points if available
                key_points = layer_data.get("key_points", {})
                if "sun_center" in key_points:
                    sun_center_base = np.array(key_points["sun_center"])
                else:
                    sun_center_base = np.array([0, 0])

                gear_positions = {
                    "sun_centers": [],
                    "planet_centers": [],
                    "tracking_points": []
                }

                for i in range(num_frames):
                    angle = (i / num_frames) * 2 * np.pi
                    planet_orbital_angle = angle
                    planet_rotation_angle = -angle * (r_sun / r_planet)

                    sun_center = sun_center_base
                    planet_center = sun_center + (r_sun + r_planet) * np.array([
                        np.cos(planet_orbital_angle), np.sin(planet_orbital_angle)
                    ])
                    tracking_point = planet_center + arm_length * np.array([
                        np.cos(planet_rotation_angle), np.sin(planet_rotation_angle)
                    ])

                    gear_positions["sun_centers"].append(sun_center.tolist())
                    gear_positions["planet_centers"].append(planet_center.tolist())
                    gear_positions["tracking_points"].append(tracking_point.tolist())

                layer_data["full_simulation_data"] = {
                    "gear_positions": gear_positions
                }

                logging.info("[PARAMETRIC] ✅ Generated planetary gear data")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to regenerate simulation: {e}")

    def _regenerate_cam_mechanism_realtime(self, mechanism_id: str, layer_data: dict):
        """Regenerate CAM mechanism with updated parameters in real-time."""
        try:
            params = layer_data.get("params", {})
            if not params:
                logging.warning(f"[CAM_REALTIME] No parameters for {mechanism_id}")
                return

            # Extract updated CAM parameters
            base_radius = params.get("base_radius", 25.0)
            eccentricity = params.get("eccentricity", 10.0)
            rod_length = params.get("follower_rod_length", 40.0)

            logging.debug(f"[CAM_REALTIME] Regenerating {mechanism_id}: radius={base_radius:.1f}, "
                        f"ecc={eccentricity:.1f}, rod={rod_length:.1f}")

            # Clear existing trace for this mechanism
            self._clear_mechanism_trace(mechanism_id)

            # Regenerate simulation data for the updated cam
            self._regenerate_mechanism_simulation(mechanism_id, layer_data)

            # Update visual items with new parameters using centralized system
            self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

            logging.debug(f"[CAM_REALTIME] ✅ Regenerated CAM mechanism {mechanism_id}")

        except Exception as e:
            logging.error(f"[CAM_REALTIME] ❌ Failed to regenerate CAM {mechanism_id}: {e}")

    def _solve_circle_intersection(self, center1: np.ndarray, radius1: float,
                                   center2: np.ndarray, radius2: float) -> np.ndarray:
        """
        Find the intersection point of two circles.
        Returns the intersection point that maintains linkage continuity.
        """
        try:
            d = np.linalg.norm(center2 - center1)

            # Check if circles intersect
            if d > radius1 + radius2 or d < abs(radius1 - radius2) or d == 0:
                # No intersection - return approximate position
                direction = (center2 - center1) / d if d > 0 else np.array([1, 0])
                return center1 + direction * radius1

            # Calculate intersection points
            a = (radius1**2 - radius2**2 + d**2) / (2 * d)
            h = np.sqrt(radius1**2 - a**2)

            # Point on line between centers
            p = center1 + a * (center2 - center1) / d

            # Perpendicular offset
            offset = h * np.array([-(center2[1] - center1[1]), center2[0] - center1[0]]) / d

            # Two possible intersection points
            intersection1 = p + offset
            intersection2 = p - offset

            # Choose the one that maintains continuity (typically the upper one for 4-bar)
            if intersection1[1] >= intersection2[1]:
                return intersection1
            else:
                return intersection2

        except Exception as e:
            logging.error(f"Circle intersection failed: {e}")
            # Return a fallback position
            return center1 + np.array([radius1, 0])

    def _recreate_mechanism_visuals(self, mechanism_id: str, layer_data: dict):
        """
        Recreate visual items for a mechanism after parameters have changed.
        """
        try:
            logging.info(f"[PARAMETRIC] 🎨 Recreating visuals for mechanism {mechanism_id}")

            # Remove existing visual items
            existing_items = layer_data.get("visual_items", [])
            self._safe_remove_visual_items(existing_items)

            # Create new visual items based on mechanism type
            mech_type = layer_data.get("type")
            mechanism_graphics_data = layer_data.copy()

            visual_items = []
            if mech_type == "4_bar_linkage":
                visual_items.extend(self._create_4bar_linkage_visuals(mechanism_graphics_data))
            elif mech_type == "5_bar_linkage":
                visual_items.extend(self._create_5bar_linkage_visuals(mechanism_graphics_data))
            elif mech_type == "6_bar_linkage":
                visual_items.extend(self._create_6bar_linkage_visuals(mechanism_graphics_data))
            elif mech_type == "cam":
                visual_items.extend(self._create_cam_visuals(mechanism_graphics_data))
            elif mech_type == "gear":
                visual_items.extend(self._create_gear_visuals(mechanism_graphics_data))
            elif mech_type == "planetary_gear":
                visual_items.extend(self._create_planetary_gear_visuals(mechanism_graphics_data))

            # Store new visual items
            layer_data["visual_items"] = visual_items

            logging.info(f"[PARAMETRIC] ✅ Created {len(visual_items)} new visual items for {mech_type}")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to recreate visuals: {e}")

    def _update_other_handles(self, mechanism_id: str, moved_handle: str):
        """
        Update positions of other parametric handles when one handle is moved.
        Syncs all handles for the given mechanism using current key_points.
        """
        try:
            handles = self.parametric_handles.get(mechanism_id, []) if hasattr(self, 'parametric_handles') else []
            if not handles:
                return

            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data:
                return

            key_points = layer_data.get("key_points", {})
            to_scene = self._get_scene_transform_function(layer_data)

            # Guard against missing transform; still update with raw coords if needed
            def _scene_pos_from_mech(pos_list):
                if to_scene:
                    return to_scene(np.array(pos_list))
                return QPointF(float(pos_list[0]), float(pos_list[1]))

            # Prevent recursive callbacks during programmatic moves
            self._updating_handles_programmatically = True
            try:
                for handle in handles:
                    if getattr(handle, 'handle_type', '') == 'rotation':
                        continue

                    anchor_name = getattr(handle, 'anchor_name', '')
                    if not anchor_name:
                        handle_id = getattr(handle, 'handle_id', '')
                        parts = handle_id.split('_', 1)
                        anchor_name = parts[1] if len(parts) > 1 else ''

                    if not anchor_name or anchor_name == moved_handle:
                        continue

                    if anchor_name in key_points:
                        new_scene_pos = _scene_pos_from_mech(key_points[anchor_name])

                        # Temporarily disable callback if present
                        original_cb = getattr(handle, 'update_callback', None)
                        if original_cb is not None:
                            handle.update_callback = None
                        handle.setPos(new_scene_pos)
                        if original_cb is not None:
                            handle.update_callback = original_cb
            finally:
                self._updating_handles_programmatically = False

            # Ensure all handles are correct relative to full key_points state
            self._update_handle_positions_from_key_points(mechanism_id, layer_data)

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to update other handles: {e}")

    def _show_free_edit_feedback(self, mechanism_id: str):
        """
        Show visual feedback for free editing mode - always allow user freedom.
        ULTRATHINK: Blue color for "user-controlled" mode - no physics constraints.

        Args:
            mechanism_id: ID of the mechanism to show feedback for
        """
        try:
            if mechanism_id not in self.parametric_handles:
                return

            handles = self.parametric_handles[mechanism_id]

            # Update handle colors to show "free edit" mode
            for handle in handles:
                if hasattr(handle, 'handle_type') and handle.handle_type == 'rotation':
                    continue  # Skip rotation handle

                # Blue color for free editing mode
                handle.setBrush(QBrush(QColor(50, 150, 255)))    # Blue - user controlled
                handle.setPen(QPen(QColor(40, 120, 200), 3))
                handle.setToolTip("🆓 Free Edit Mode: Any position allowed")

            self.mechanism_scene.update()
            logging.info(f"[PARAMETRIC] 🆓 Updated free edit feedback for {mechanism_id}")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to show free edit feedback: {e}")


    def _show_current_mechanism_dimensions(self):
        """Delegate to BlueprintExporter to show dimensions for a mechanism."""
        try:
            self.blueprint_exporter.show_current_mechanism_dimensions()
        except Exception as e:
            logging.error(f"[DIMENSIONS] Failed to show current mechanism dimensions: {e}")

    def _export_current_mechanism_blueprint(self):
        """Delegate to BlueprintExporter to export all content."""
        self.blueprint_exporter.export_all()


    def _create_gear_handles(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Create handles for gear mechanism with rotation."""
        try:
            logging.info(f"[PARAMETRIC] 🚀 Creating gear handles for {mechanism_id}")

            if mechanism_id in self.parametric_handles:
                self._remove_parametric_handles_for_mechanism(mechanism_id)

            handles = []

            # Define gear control points
            center_x, center_y = 400, 300
            anchor_positions = {
                "gear_center_1": QPointF(center_x - 60, center_y),
                "gear_center_2": QPointF(center_x + 60, center_y),
                "radius_control_1": QPointF(center_x - 60, center_y - 50),
                "radius_control_2": QPointF(center_x + 60, center_y - 50)
            }

            # Create anchor handles
            for anchor_name, anchor_pos in anchor_positions.items():
                anchor_handle = QGraphicsEllipseItem(-15, -15, 30, 30)
                anchor_handle.setPos(anchor_pos)
                anchor_handle.setBrush(QBrush(QColor(255, 50, 50)))
                anchor_handle.setPen(QPen(QColor(200, 40, 40), 2))
                anchor_handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                anchor_handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                anchor_handle.setZValue(1000000)

                anchor_handle.handle_id = f"{mechanism_id}_{anchor_name}"
                anchor_handle.anchor_name = anchor_name
                anchor_handle.setToolTip(f"Gear Mechanism: {anchor_name}")

                self.mechanism_scene.addItem(anchor_handle)
                handles.append(anchor_handle)

            # Add rotation handle
            self._add_rotation_handle_to_mechanism(mechanism_id, handles, anchor_positions)

            self.parametric_handles[mechanism_id] = handles
            self.mechanism_scene.update()

            logging.info(f"[PARAMETRIC] ✅ Created {len(handles)} handles for gear mechanism")

        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to create gear handles: {e}")

    def _regenerate_cam_visuals_with_params(self, mechanism_id: str, layer_data: dict):
        """Regenerate cam visuals when parameters change during parametric editing."""
        try:
            # Clear existing visual items
            visual_items = layer_data.get("visual_items", [])
            for item in visual_items:
                if item and item.scene():
                    self.mechanism_scene.removeItem(item)

            # Create new visual items with updated parameters
            new_visual_items = self._create_cam_visuals(layer_data)
            layer_data["visual_items"] = new_visual_items

            logging.debug(f"[CAM_HANDLES] Regenerated {len(new_visual_items)} cam visual items")

        except Exception as e:
            logging.error(f"[CAM_HANDLES] Error regenerating cam visuals: {e}")

    class RotationHandle(QGraphicsEllipseItem):
        """
        Simple rotation handle that just moves around the center.
        ULTRATHINK: Don't modify the actual mechanism - just move the handle.
        """
        def __init__(self, parent_tab, mechanism_id: str, center_pos: QPointF, radius: float = 60):
            super().__init__(-25, -25, 50, 50)  # Large yellow circle

            self.parent_tab = parent_tab
            self.mechanism_id = mechanism_id
            self.rotation_center = center_pos
            self.is_dragging = False
            self.current_rotation = 0

            # Position handle
            handle_pos = QPointF(center_pos.x() + radius, center_pos.y())
            self.setPos(handle_pos)

            # Visual styling
            self.setBrush(QBrush(QColor(255, 255, 0)))    # Bright yellow
            self.setPen(QPen(QColor(255, 140, 0), 5))     # Orange thick border

            # Enable drag
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            self.setZValue(1000002)

            # Add identification
            self.handle_id = f"{mechanism_id}_rotation"
            self.handle_type = "rotation"
            self.setToolTip("🔄 Rotation Handle: Drag to set rotation angle (visual only)")

        def mousePressEvent(self, event):
            """Handle mouse press - start rotation tracking."""
            if event.button() == Qt.MouseButton.LeftButton:
                self.is_dragging = True

                # Initialize previous angle for rotation calculation
                scene_pos = event.scenePos()
                dx = scene_pos.x() - self.rotation_center.x()
                dy = scene_pos.y() - self.rotation_center.y()
                self.previous_angle = math.atan2(dy, dx)

                logging.info(f"[PARAMETRIC] 🔄 Started rotation drag for {self.mechanism_id}")
                event.accept()
            else:
                super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            """Handle mouse move - rotate mechanism and move handle in circle."""
            if self.is_dragging:
                scene_pos = event.scenePos()

                # Calculate position relative to center
                dx = scene_pos.x() - self.rotation_center.x()
                dy = scene_pos.y() - self.rotation_center.y()

                # Calculate current angle
                current_angle = math.atan2(dy, dx)

                # Check if we have a previous angle to calculate difference
                if hasattr(self, 'previous_angle'):
                    # Calculate angle difference for mechanism rotation
                    angle_diff = current_angle - self.previous_angle

                    # Handle angle wrap-around (crossing 180° boundary)
                    if angle_diff > math.pi:
                        angle_diff -= 2 * math.pi
                    elif angle_diff < -math.pi:
                        angle_diff += 2 * math.pi

                    # Apply rotation to mechanism if significant movement
                    if abs(angle_diff) > 0.01:  # Lower threshold for responsive rotation
                        # Use current mouse position as rotation center for maximum user control
                        current_rotation_center = scene_pos
                        self.parent_tab._rotate_mechanism(self.mechanism_id, current_rotation_center, angle_diff)
                        logging.info(f"[PARAMETRIC] 🆓 Free rotation by {math.degrees(angle_diff):.1f}° around mouse position")

                # Store current angle for next movement
                self.previous_angle = current_angle

                # Allow free positioning of rotation handle - not constrained to circle!
                # User can place it anywhere for maximum control
                self.setPos(scene_pos)

                # Update display angle
                self.current_rotation = math.degrees(current_angle)
                self.setToolTip(f"🔄 Rotation Handle: {self.current_rotation:.1f}° (drag to rotate)")

                event.accept()
            else:
                # Allow normal movement when not dragging
                super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            """Handle mouse release - end rotation tracking."""
            if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
                self.is_dragging = False
                # Clear previous angle tracking
                if hasattr(self, 'previous_angle'):
                    del self.previous_angle
                logging.info(f"[PARAMETRIC] 🔄 Ended rotation drag for {self.mechanism_id} at angle {self.current_rotation:.1f}°")
                event.accept()
            else:
                super().mouseReleaseEvent(event)


    def _create_gear_handles(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Create interactive handles for simple gear pair centers using recommendation transform."""
        try:
            to_scene = self._get_scene_transform_function(layer_data)
            params = layer_data.get("params", {})
            r1 = params.get("r1", 30)
            r2 = params.get("r2", 50)

            if not to_scene:
                logging.warning(f"[GEAR_HANDLES] No transform function for {mechanism_id}")
                return

            # Match the visual creation logic exactly
            # Gear centers in original coordinates
            distance = r1 + r2  # Gears touching
            gear1_center_orig = np.array([0, 0])
            gear2_center_orig = np.array([distance, 0])

            # Check if there are stored key_points (for consistency with visual updates)
            kp = layer_data.get("key_points", {})
            if "gear1_center" in kp and isinstance(kp["gear1_center"], (list, tuple)):
                gear1_center_orig = np.array(kp["gear1_center"], dtype=float)
            if "gear2_center" in kp and isinstance(kp["gear2_center"], (list, tuple)):
                gear2_center_orig = np.array(kp["gear2_center"], dtype=float)

            # Transform to scene coordinates
            g1_scene = to_scene(gear1_center_orig)
            g2_scene = to_scene(gear2_center_orig)

            def on_move_g1(handle_id: str, pos: QPointF):
                """Handle gear 1 center movement"""
                try:
                    to_mech = self._get_inverse_scene_transform_function(layer_data)
                    if to_mech:
                        p = to_mech(pos)
                        layer_data.setdefault("key_points", {})["gear1_center"] = [float(p[0]), float(p[1])]
                    else:
                        layer_data.setdefault("key_points", {})["gear1_center"] = [pos.x(), pos.y()]

                    # Clear traces and update visuals
                    self._clear_mechanism_trace(mechanism_id)
                    self._regenerate_mechanism_simulation(mechanism_id, layer_data)
                    self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

                    logging.info(f"[GEAR_HANDLES] Updated gear1 center to {layer_data['key_points']['gear1_center']}")
                except Exception as e:
                    logging.error(f"[GEAR_HANDLES] Error moving gear1: {e}")

            def on_move_g2(handle_id: str, pos: QPointF):
                """Handle gear 2 center movement"""
                try:
                    to_mech = self._get_inverse_scene_transform_function(layer_data)
                    if to_mech:
                        p = to_mech(pos)
                        layer_data.setdefault("key_points", {})["gear2_center"] = [float(p[0]), float(p[1])]
                    else:
                        layer_data.setdefault("key_points", {})["gear2_center"] = [pos.x(), pos.y()]

                    # Clear traces and update visuals
                    self._clear_mechanism_trace(mechanism_id)
                    self._regenerate_mechanism_simulation(mechanism_id, layer_data)
                    self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

                    logging.info(f"[GEAR_HANDLES] Updated gear2 center to {layer_data['key_points']['gear2_center']}")
                except Exception as e:
                    logging.error(f"[GEAR_HANDLES] Error moving gear2: {e}")

            # Create handles
            handle1 = DraggableHandle(f"{mechanism_id}_gear1_center", g1_scene, update_callback=on_move_g1)
            handle2 = DraggableHandle(f"{mechanism_id}_gear2_center", g2_scene, update_callback=on_move_g2)

            # Add to scene and track
            self.mechanism_scene.addItem(handle1)
            self.mechanism_scene.addItem(handle2)

            if mechanism_id not in self.parametric_handles:
                self.parametric_handles[mechanism_id] = []
            self.parametric_handles[mechanism_id] = [handle1, handle2]

            logging.info(f"[GEAR_HANDLES] Created 2 parametric handles for {mechanism_id} at gear1={g1_scene}, gear2={g2_scene}")

        except Exception as e:
            logging.error(f"[GEAR_HANDLES] Failed to create gear handles for {mechanism_id}: {e}")

    def _remove_parametric_handles_for_mechanism(self, mechanism_id: str):
        """
        Remove all parametric handles for a specific mechanism.
        
        DEPRECATED: This method is replaced by ParametricEditor.remove_editor()
        in the new parametric system.

        Args:
            mechanism_id: Mechanism ID to remove handles for
        """
        # Deprecated - the new ParametricEditor handles this
        # Kept for compatibility with any legacy code
        pass

    def _update_parametric_handles_for_selection(self, part_name: str):
        """
        Update parametric handles visibility based on selected part.
        Shows handles only for the mechanism associated with the selected part.
        
        Args:
            part_name: Name of the selected part
        """
        if not self.parametric_mode_enabled or not self.parametric_editor:
            return
            
        try:
            # Debug: Log all mechanism-part mappings
            logging.info(f"[PARAMETRIC] 🔍 Looking for mechanisms for part: {part_name}")
            logging.info(f"[PARAMETRIC] Current mechanism_layers mappings:")
            for mid, mdata in self.mechanism_layers.items():
                logging.info(f"[PARAMETRIC]   {mid}: part_name={mdata.get('part_name')}, type={mdata.get('type')}")
            
            # Find ALL mechanism_ids for this part
            selected_mechanism_ids = []
            for mechanism_id, layer_data in self.mechanism_layers.items():
                mechanism_part = layer_data.get("part_name")
                if mechanism_part == part_name:
                    selected_mechanism_ids.append(mechanism_id)
                    logging.info(f"[PARAMETRIC] ✅ Found mechanism {mechanism_id} for part {part_name}")
                else:
                    logging.info(f"[PARAMETRIC] ⏭️ Skipping mechanism {mechanism_id} (part: {mechanism_part} != {part_name})")
            
            if not selected_mechanism_ids:
                logging.warning(f"[PARAMETRIC] ⚠️ No mechanisms found for part {part_name}")
                # Hide all editors
                self.parametric_editor.set_active_editor(None)
                return
            
            logging.info(f"[PARAMETRIC] Total {len(selected_mechanism_ids)} mechanism(s) found for part {part_name}")
            
            # FIXED: Properly activate the mechanism for the selected part
            # If multiple mechanisms exist for same part, use the first one
            # But most importantly, activate the correct mechanism for the selected part
            if selected_mechanism_ids:
                # Store the selected part to properly identify its mechanism
                self.selected_part_name = part_name
                # Activate the editor for this part's mechanism
                mechanism_to_activate = selected_mechanism_ids[0]
                self.parametric_editor.set_active_editor(mechanism_to_activate)
                logging.info(f"[PARAMETRIC] 🎯 Activated editor for mechanism {mechanism_to_activate} (part: {part_name})")
                        
            logging.info(f"[PARAMETRIC] ✅ Updated handle visibility for part {part_name}")
            
        except Exception as e:
            logging.error(f"[PARAMETRIC] ❌ Failed to update handles for selection: {e}")
    
    def _hide_all_parametric_handles(self):
        """
        Hide all parametric handles when no part is selected.
        
        DEPRECATED: This functionality is now handled by ParametricEditor.set_active_editor(None)
        """
        if self.parametric_editor:
            self.parametric_editor.set_active_editor(None)

    # Parametric Event Handlers

    def _on_anchor_moved(self, anchor_name: str, new_position: QPointF):
        """
        Handle anchor point movement from interactive manipulation.
        Updates both key points and regenerates mechanism visuals.

        Args:
            anchor_name: Name of anchor that was moved
            new_position: New position in scene coordinates
        """
        try:
            # Skip if we're updating handles programmatically to prevent recursion
            if getattr(self, '_updating_handles_programmatically', False):
                logging.info(f"[PARAMETRIC] ⏸️  Skipping callback for {anchor_name} (programmatic update)")
                return

            logging.info(f"[PARAMETRIC] 🔥 ANCHOR MOVED: {anchor_name} -> ({new_position.x():.1f}, {new_position.y():.1f})")

            # Find which mechanism this anchor belongs to
            found_mechanism = False
            for mechanism_id, layer_data in self.mechanism_layers.items():
                key_points = layer_data.get("key_points", {})
                logging.info(f"[PARAMETRIC] Checking mechanism {mechanism_id}, has {list(key_points.keys())}")

                if anchor_name in key_points:
                    found_mechanism = True
                    logging.info(f"[PARAMETRIC] 🎯 Found anchor {anchor_name} in mechanism {mechanism_id}")

                    # Update the anchor position in mechanism data
                    to_mech = self._get_inverse_scene_transform_function(layer_data)
                    old_pos = key_points.get(anchor_name)
                    if to_mech:
                        mech_xy = to_mech(new_position)
                        key_points[anchor_name] = [float(mech_xy[0]), float(mech_xy[1])]
                    else:
                        key_points[anchor_name] = [new_position.x(), new_position.y()]

                    logging.info(f"[PARAMETRIC] ✅ Updated {anchor_name}: {old_pos} -> [{key_points[anchor_name][0]:.1f}, {key_points[anchor_name][1]:.1f}]")

                    mech_type = layer_data.get("type")
                    params = layer_data.get("params", {})

                    # Update mechanism parameters based on new key points
                    if mech_type == "4_bar_linkage":
                        # Update the 4-bar linkage parameters from key points
                        if all(k in key_points for k in ["ground_pivot_1", "ground_pivot_2", "crank_end", "rocker_end"]):
                            p1 = np.array(key_points["ground_pivot_1"])
                            p2 = np.array(key_points["ground_pivot_2"])
                            p3 = np.array(key_points["crank_end"])
                            p4 = np.array(key_points["rocker_end"])

                            # Calculate new link lengths
                            L1 = np.linalg.norm(p2 - p1)  # Ground link
                            L2 = np.linalg.norm(p3 - p1)  # Crank
                            L3 = np.linalg.norm(p4 - p3)  # Coupler
                            L4 = np.linalg.norm(p4 - p2)  # Rocker

                            # Update parameters
                            params["L1"] = float(L1)
                            params["L2"] = float(L2)
                            params["L3"] = float(L3)
                            params["L4"] = float(L4)

                            # Update ground pivot positions
                            params["ground_pivot_1"] = key_points["ground_pivot_1"]
                            params["ground_pivot_2"] = key_points["ground_pivot_2"]

                            logging.info(f"[PARAMETRIC] 📐 Updated 4-bar parameters: L1={L1:.1f}, L2={L2:.1f}, L3={L3:.1f}, L4={L4:.1f}")

                    elif mech_type == "5_bar_linkage":
                        # Update 5-bar linkage parameters from key points
                        if all(k in key_points for k in ["ground_pivot_1", "ground_pivot_2"]):
                            p1 = np.array(key_points["ground_pivot_1"])
                            p2 = np.array(key_points["ground_pivot_2"])
                            params["ground_pivot_1"] = key_points["ground_pivot_1"]
                            params["ground_pivot_2"] = key_points["ground_pivot_2"]

                            # Update link lengths if intermediate joints are available
                            if all(k in key_points for k in ["joint_3", "joint_4", "joint_5"]):
                                p3 = np.array(key_points["joint_3"])
                                p4 = np.array(key_points["joint_4"])
                                p5 = np.array(key_points["joint_5"])

                                params["L2"] = float(np.linalg.norm(p3 - p1))  # Input link
                                params["L3"] = float(np.linalg.norm(p4 - p3))  # Coupler 1
                                params["L4"] = float(np.linalg.norm(p5 - p4))  # Coupler 2
                                params["L5"] = float(np.linalg.norm(p5 - p2))  # Output link

                                logging.info(f"[PARAMETRIC] 📐 Updated 5-bar parameters: L2-L5={params['L2']:.1f},{params['L3']:.1f},{params['L4']:.1f},{params['L5']:.1f}")

                    elif mech_type == "6_bar_linkage":
                        # Update 6-bar linkage parameters from key points
                        if all(k in key_points for k in ["ground_pivot_1", "ground_pivot_2", "ground_pivot_3"]):
                            p1 = np.array(key_points["ground_pivot_1"])
                            p2 = np.array(key_points["ground_pivot_2"])
                            p6 = np.array(key_points["ground_pivot_3"])

                            params["ground_pivot_1"] = key_points["ground_pivot_1"]
                            params["ground_pivot_2"] = key_points["ground_pivot_2"]
                            params["ground_pivot_3"] = key_points["ground_pivot_3"]

                            # Update link lengths if intermediate joints are available
                            if all(k in key_points for k in ["joint_3", "joint_4", "joint_5"]):
                                p3 = np.array(key_points["joint_3"])
                                p4 = np.array(key_points["joint_4"])
                                p5 = np.array(key_points["joint_5"])

                                params["L2"] = float(np.linalg.norm(p3 - p1))
                                params["L3"] = float(np.linalg.norm(p4 - p3))
                                params["L4"] = float(np.linalg.norm(p4 - p2))
                                params["L5"] = float(np.linalg.norm(p5 - p4))
                                params["L6"] = float(np.linalg.norm(p5 - p6))

                                logging.info("[PARAMETRIC] 📐 Updated 6-bar parameters")

                    elif mech_type == "cam":
                        # Update cam mechanism parameters
                        if "cam_center" in key_points:
                            cam_center = np.array(key_points["cam_center"])
                            params["cam_center"] = key_points["cam_center"]

                            # If follower position is also in key_points, update eccentricity
                            if "follower_base" in key_points:
                                follower = np.array(key_points["follower_base"])
                                distance = np.linalg.norm(follower - cam_center)
                                params["base_radius"] = max(10, distance - 20)  # Maintain minimum radius

                                logging.info(f"[PARAMETRIC] 📐 Updated cam parameters: radius={params['base_radius']:.1f}")

                    elif mech_type == "gear":
                        # Update gear positions and radii if needed
                        if "gear1_center" in key_points and "gear2_center" in key_points:
                            g1 = np.array(key_points["gear1_center"])
                            g2 = np.array(key_points["gear2_center"])
                            distance = np.linalg.norm(g2 - g1)

                            # Maintain gear ratio but adjust sizes to fit distance
                            ratio = params.get("r2", 50) / params.get("r1", 30)
                            params["r1"] = distance / (1 + ratio)
                            params["r2"] = params["r1"] * ratio

                            logging.info(f"[PARAMETRIC] ⚙️ Updated gear radii: r1={params['r1']:.1f}, r2={params['r2']:.1f}")

                    elif mech_type == "planetary_gear":
                        # Update planetary gear parameters
                        if "sun_center" in key_points:
                            sun_center = np.array(key_points["sun_center"])
                            params["sun_center"] = key_points["sun_center"]

                            # If planet position is also in key_points, update radii
                            if "planet_center" in key_points:
                                planet = np.array(key_points["planet_center"])
                                orbital_radius = np.linalg.norm(planet - sun_center)

                                # Maintain ratio but adjust sizes
                                ratio = params.get("r_planet", 30) / params.get("r_sun", 20)
                                params["r_sun"] = orbital_radius / (1 + ratio)
                                params["r_planet"] = params["r_sun"] * ratio

                                logging.info(f"[PARAMETRIC] ⚙️ Updated planetary gear: r_sun={params['r_sun']:.1f}, r_planet={params['r_planet']:.1f}")

                    # Regenerate simulation data for the new configuration
                    self._regenerate_mechanism_simulation(mechanism_id, layer_data)

                    # Recreate the visual items with new configuration
                    self._recreate_mechanism_visuals(mechanism_id, layer_data)

                    # Update other parametric handles to reflect the new positions
                    self._update_other_handles(mechanism_id, anchor_name)

                    # Force view update
                    self.mechanism_view.update()

                    logging.info(f"[PARAMETRIC] ✅ Completed {mech_type} mechanism {mechanism_id} update and visual regeneration")
                    break

            if not found_mechanism:
                logging.error(f"[PARAMETRIC] ❌ Could not find mechanism for anchor {anchor_name}")
                logging.error(f"[PARAMETRIC] Available mechanisms: {list(self.mechanism_layers.keys())}")

        except Exception as e:
            logging.error(f"❌ Failed to handle anchor movement: {e}")
            import traceback
            logging.error(f"❌ Traceback: {traceback.format_exc()}")


    def _calculate_4bar_rocker_position(self, p2: np.ndarray, p3: np.ndarray, l3: float, l4: float) -> np.ndarray:
        """
        Calculate rocker_end position using circle intersection.
        p4 must be l3 distance from p3 AND l4 distance from p2.
        """
        try:
            # Distance between the two circle centers
            d = np.linalg.norm(p2 - p3)

            # Check if intersection is possible
            if d > (l3 + l4) or d < abs(l3 - l4) or d == 0:
                logging.warning(f"[KINEMATICS] ⚠️  No valid intersection: d={d}, l3={l3}, l4={l4}")
                # Fallback: place p4 on line between p2 and p3
                if d > 0:
                    direction = (p2 - p3) / d
                    return p3 + l3 * direction
                else:
                    return p2 + np.array([l4, 0])

            # Calculate intersection points of two circles
            a = (l3**2 - l4**2 + d**2) / (2 * d)
            h = math.sqrt(l3**2 - a**2)

            # Point on line between p3 and p2
            p_mid = p3 + a * (p2 - p3) / d

            # Two possible intersection points
            perpendicular = np.array([-(p2[1] - p3[1]), p2[0] - p3[0]]) / d
            p4_option1 = p_mid + h * perpendicular
            p4_option2 = p_mid - h * perpendicular

            # Choose the option closer to current rocker position if available
            # For now, just return option1 (could be enhanced with preference logic)
            return p4_option1

        except Exception as e:
            logging.error(f"[KINEMATICS] ❌ Rocker calculation failed: {e}")
            return p2 + np.array([-l4, 0])  # Safe fallback

    def _update_handle_positions_from_key_points(self, mechanism_id: str, layer_data: dict):
        """
        Update scene handle positions to match updated key_points after kinematic constraints.

        ULTRATHINK: Prevents infinite recursion by temporarily disabling callbacks.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Layer data with updated key_points
        """
        try:
            logging.info(f"[KINEMATICS] 🔄 Updating handle positions for {mechanism_id}")

            # Get handles for this mechanism
            handles = self.parametric_handles.get(mechanism_id, [])
            if not handles:
                logging.warning(f"[KINEMATICS] ⚠️  No handles found for {mechanism_id}")
                return

            # Get transform function
            to_scene = self._get_scene_transform_function(layer_data)
            key_points = layer_data.get("key_points", {})

            # ULTRATHINK: Set flag to prevent callback recursion
            self._updating_handles_programmatically = True

            # Update each handle position
            updated_count = 0
            for handle in handles:
                handle_id = getattr(handle, 'handle_id', '')
                anchor_name = getattr(handle, 'anchor_name', '')

                # Extract anchor name from handle_id if anchor_name not available
                if not anchor_name and handle_id:
                    # Format: "{mechanism_id}_{anchor_name}"
                    parts = handle_id.split('_', 1)
                    if len(parts) > 1:
                        anchor_name = parts[1]

                if anchor_name in key_points:
                    # Get new position in mechanism coordinates
                    mech_pos = key_points[anchor_name]

                    # Transform to scene coordinates
                    if to_scene:
                        scene_pos = to_scene(np.array(mech_pos))
                    else:
                        scene_pos = QPointF(mech_pos[0], mech_pos[1])

                    # Update handle position (avoid triggering callbacks during programmatic move)
                    old_pos = handle.pos()

                    # ULTRATHINK: Temporarily disable callback for DraggableHandle
                    original_callback = None
                    if hasattr(handle, 'update_callback'):
                        original_callback = handle.update_callback
                        handle.update_callback = None

                    # Update position
                    handle.setPos(scene_pos)

                    # Restore callback
                    if original_callback:
                        handle.update_callback = original_callback

                    logging.info(f"[KINEMATICS] 🎯 Updated handle {anchor_name}: ({old_pos.x():.1f}, {old_pos.y():.1f}) -> ({scene_pos.x():.1f}, {scene_pos.y():.1f})")
                    updated_count += 1
                else:
                    logging.warning(f"[KINEMATICS] ⚠️  No key_point found for handle anchor: {anchor_name}")

            # Clear the flag
            self._updating_handles_programmatically = False

            logging.info(f"[KINEMATICS] ✅ Updated {updated_count}/{len(handles)} handle positions")

        except Exception as e:
            logging.error(f"[KINEMATICS] ❌ Failed to update handle positions: {e}")
            # Make sure to clear the flag even if error occurs
            self._updating_handles_programmatically = False


    def _validate_anchor_constraints(self, param_name: str, new_value: Any) -> Any:
        """
        Validate anchor position constraints.

        Args:
            param_name: Parameter name being changed
            new_value: Proposed new value

        Returns:
            Validated value (may be adjusted to meet constraints)
        """
        # Constraints are handled within the AnchorHandle class
        # This is a placeholder for additional global constraints
        return new_value

    @pyqtSlot(str, dict)
    def _on_parametric_mechanism_update(self, mechanism_id: str, params: dict[str, Any]):
        """
        Handle mechanism update request from parametric editor.

        Args:
            mechanism_id: Mechanism ID to update
            params: Updated mechanism parameters
        """
        try:
            # Update mechanism layer data with new parameters
            if mechanism_id in self.mechanism_layers:
                layer_data = self.mechanism_layers[mechanism_id]
                
                # Update parameters
                if "params" in params:
                    layer_data["params"].update(params["params"])
                
                # Regenerate mechanism simulation with new parameters
                self._regenerate_mechanism_simulation(mechanism_id, layer_data)
                
                # Update visual representation
                self._update_mechanism_visuals_realtime(mechanism_id, layer_data)
                
                logging.debug(f"[PARAMETRIC] Updated mechanism {mechanism_id} with new parameters")

        except Exception as e:
            logging.error(f"[PARAMETRIC] Failed to update mechanism {mechanism_id}: {e}")

    @pyqtSlot(str)
    def _on_parametric_visual_refresh(self, mechanism_id: str):
        """
        Handle visual refresh request from parametric controller.

        Args:
            mechanism_id: Mechanism ID to refresh visuals for
        """
        try:
            if mechanism_id in self.mechanism_layers:
                layer_data = self.mechanism_layers[mechanism_id]
                self._refresh_mechanism_visuals(mechanism_id, layer_data)

        except Exception as e:
            logging.error(f"Failed to refresh visuals for {mechanism_id}: {e}")

    def _update_mechanism_visuals_realtime(self, mechanism_id: str, params_changed: dict[str, Any]):
        """
        Update mechanism visuals in real-time during parametric editing.
        CRITICAL: This needs to be extremely fast for smooth interaction.
        
        Args:
            mechanism_id: ID of mechanism being updated
            params_changed: Changed parameters
        """
        try:
            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data:
                return
            
            logging.debug(f"[PARAMETRIC] Updating visuals for {mechanism_id} with changes: {params_changed}")
            
            # Critical: Stop animation during update to prevent conflicts
            animation_was_running = self.animation_timer.isActive()
            if animation_was_running:
                self._on_stop_animation()
                
            # Extract the previous visual properties to restore later (for consistency)
            visual_items = layer_data.get("visual_items", [])
            original_visual_properties = []
            for item in visual_items:
                if item and not sip.isdeleted(item):
                    try:
                        props = {
                            'pen': item.pen() if hasattr(item, 'pen') else None,
                            'brush': item.brush() if hasattr(item, 'brush') else None,
                            'z_value': item.zValue(),
                            'visible': item.isVisible(),
                            'enabled': item.isEnabled()
                        }
                        original_visual_properties.append(props)
                    except RuntimeError:
                        # Item was deleted
                        original_visual_properties.append({})
                        
            # Remove old visual items from scene
            for item in visual_items:
                if item and not sip.isdeleted(item):
                    try:
                        if item.scene() == self.mechanism_scene:
                            self.mechanism_scene.removeItem(item)
                    except RuntimeError:
                        # Item was already deleted
                        pass
                        
            # Update parameters in layer data
            params = layer_data.get("params", {})
            params.update(params_changed)
            layer_data["params"] = params
            
            # Recreate visual items with updated parameters
            mechanism_type = layer_data.get("type")
            new_items = []
            
            if mechanism_type == "4_bar_linkage":
                new_items = self._create_4bar_linkage_visuals(layer_data)
            elif mechanism_type == "6_bar_linkage":
                new_items = self._create_6bar_linkage_visuals(layer_data)
            elif mechanism_type == "cam":
                new_items = self._create_cam_visuals(layer_data)
            elif mechanism_type == "gear":
                new_items = self._create_gear_visuals(layer_data)
            elif mechanism_type == "planetary_gear":
                new_items = self._create_planetary_gear_visuals(layer_data)
            else:
                logging.warning(f"[PARAMETRIC] Unknown mechanism type for realtime update: {mechanism_type}")
                
            # CRITICAL: Apply original visual properties to new items if available
            for i, item in enumerate(new_items):
                if i < len(original_visual_properties) and item:
                    try:
                        props = original_visual_properties[i]
                        if props['pen'] and hasattr(item, 'setPen'):
                            item.setPen(props['pen'])
                        if props['brush'] and hasattr(item, 'setBrush'):
                            item.setBrush(props['brush'])
                        item.setZValue(props['z_value'])
                        item.setVisible(props['visible'])
                        item.setEnabled(props['enabled'])
                    except (RuntimeError, KeyError):
                        # Item properties couldn't be restored - continue
                        continue
                        
            # Store updated visual items
            layer_data["visual_items"] = new_items
            logging.debug(f"[PARAMETRIC] Recreated {len(new_items)} visual items for {mechanism_type}")
            
            # Skip handle position update if parametric_handles doesn't exist
            # This is for the new parametric system which uses ParametricEditor
            if hasattr(self, 'parametric_handles') and mechanism_id in self.parametric_handles and self.parametric_mode_enabled:
                self._update_handle_positions_for_mechanism(mechanism_id, layer_data)
                
            # Update display
            self.mechanism_view.update()
            
            # Resume animation if it was running (but only if parametric mode allows it)
            if animation_was_running and not self.parametric_mode_enabled:
                self._on_start_animation()
                logging.debug(f"[PARAMETRIC] Resumed animation after visual update for {mechanism_id}")
                
        except Exception as e:
            logging.error(f"Failed to update visuals realtime for {mechanism_id}: {e}")

    def _update_handle_positions_for_mechanism(self, mechanism_id: str, layer_data: dict[str, Any]):
        """
        Update handle positions to match mechanism's current state.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Current mechanism data
        """
        try:
            handles = self.parametric_handles.get(mechanism_id, [])
            if not handles:
                return

            mechanism_type = layer_data.get("type")

            # Get updated anchor positions based on mechanism type
            anchor_positions = self._get_anchor_positions_for_mechanism(layer_data)

            logging.info(f"[HANDLE_UPDATE] Updating {len(handles)} handles for {mechanism_type} mechanism")

            # Update each handle's position based on its ID
            for handle in handles:
                handle_id = getattr(handle, 'handle_id', None)
                if not handle_id:
                    continue

                new_pos = None

                # Map handle IDs to anchor positions based on mechanism type
                if mechanism_type == "cam":
                    if "rod_length" in handle_id:
                        new_pos = anchor_positions.get("cam_rod_length")
                    elif "cam_size" in handle_id:
                        new_pos = anchor_positions.get("cam_size")

                elif mechanism_type == "gear":
                    if "gear1_center" in handle_id:
                        new_pos = anchor_positions.get("gear1_center")
                    elif "gear2_center" in handle_id:
                        new_pos = anchor_positions.get("gear2_center")

                elif mechanism_type == "planetary_gear":
                    if "sun_center" in handle_id:
                        new_pos = anchor_positions.get("sun_center")
                    elif "planet_center" in handle_id:
                        new_pos = anchor_positions.get("planet_center")

                elif mechanism_type == "4_bar_linkage":
                    # Original 4-bar logic
                    anchor_name = getattr(handle, 'anchor_name', None)
                    if anchor_name and anchor_name in anchor_positions:
                        new_pos = anchor_positions[anchor_name]

                # Update handle position if we found a match
                if new_pos:
                    handle.setPos(new_pos)
                    logging.debug(f"[HANDLE_UPDATE] Updated handle {handle_id} to position {new_pos}")
                else:
                    logging.warning(f"[HANDLE_UPDATE] No position found for handle {handle_id}")

        except Exception as e:
            logging.error(f"Failed to update handle positions for {mechanism_id}: {e}")

    def _refresh_mechanism_visuals(self, mechanism_id: str, layer_data: dict[str, Any]):
        """
        Refresh mechanism visuals after parametric changes.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Mechanism data
        """
        # Delegate to existing visual update system
        self._update_mechanism_visuals_realtime(mechanism_id, layer_data)

    def _get_anchor_positions_for_mechanism(self, layer_data: dict[str, Any]) -> dict[str, QPointF]:
        """
        Get anchor positions for mechanism handles.

        Args:
            layer_data: Mechanism layer data

        Returns:
            Dictionary mapping anchor names to QPointF positions
        """
        anchor_positions = {}
        mechanism_type = layer_data.get("type")

        try:
            # Get the transformation function for this mechanism
            to_scene_coords = self._get_scene_transform_function(layer_data)

            if mechanism_type == "cam":
                # Handle CAM mechanism anchor positions
                params = layer_data.get("params", {})
                base_radius = params.get("base_radius", 25.0)
                eccentricity = params.get("eccentricity", 10.0)
                rod_length = params.get("follower_rod_length", 40.0)

                # Use stored transform function if available
                if 'cam_transform_function' in layer_data:
                    cam_to_scene_coords = layer_data['cam_transform_function']
                elif to_scene_coords:
                    cam_to_scene_coords = to_scene_coords
                else:
                    # Fallback transform
                    def cam_to_scene_coords(p_orig: np.ndarray) -> QPointF:
                        return QPointF(float(p_orig[0] * 2 + 300), float(p_orig[1] * 2 + 300))

                # Calculate handle positions (same as in _create_cam_handles)
                cam_center_orig = np.array([0.0, 0.0])
                rod_handle_orig = np.array([0.0, -(base_radius + rod_length)])
                size_handle_orig = np.array([base_radius + eccentricity, 0.0])

                # Transform to scene coordinates
                anchor_positions["cam_rod_length"] = cam_to_scene_coords(rod_handle_orig)
                anchor_positions["cam_size"] = cam_to_scene_coords(size_handle_orig)

                logging.debug(f"[CAM_ANCHORS] Rod handle: {anchor_positions['cam_rod_length']}")
                logging.debug(f"[CAM_ANCHORS] Size handle: {anchor_positions['cam_size']}")

            elif mechanism_type == "gear":
                # Get visual items to find actual positions
                visual_items = layer_data.get("visual_items", [])
                
                # First try to get positions from actual visual items if they exist
                if visual_items:
                    # Visual items for gear: gear circles and teeth
                    # Get center positions from the gear circles
                    gear_circles = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]
                    
                    if len(gear_circles) >= 2:
                        # Typically: gear1, gear2
                        anchor_positions["gear1_center"] = gear_circles[0].scenePos() + gear_circles[0].rect().center()
                        anchor_positions["gear2_center"] = gear_circles[1].scenePos() + gear_circles[1].rect().center()
                        
                        logging.info(f"[GEAR_ANCHORS] Got positions from visual items")
                        return anchor_positions
                
                # Fallback to calculation
                params = layer_data.get("params", {})
                r1 = params.get("r1", 30)
                r2 = params.get("r2", 50)
                distance = r1 + r2

                gear1_center_orig = np.array([0, 0])
                gear2_center_orig = np.array([distance, 0])

                # Check for stored positions
                key_points = layer_data.get("key_points", {})
                if "gear1_center" in key_points:
                    gear1_center_orig = np.array(key_points["gear1_center"])
                if "gear2_center" in key_points:
                    gear2_center_orig = np.array(key_points["gear2_center"])

                if to_scene_coords:
                    anchor_positions["gear1_center"] = to_scene_coords(gear1_center_orig)
                    anchor_positions["gear2_center"] = to_scene_coords(gear2_center_orig)
                else:
                    anchor_positions["gear1_center"] = QPointF(gear1_center_orig[0], gear1_center_orig[1])
                    anchor_positions["gear2_center"] = QPointF(gear2_center_orig[0], gear2_center_orig[1])

            elif mechanism_type == "planetary_gear":
                # Get visual items to find actual positions
                visual_items = layer_data.get("visual_items", [])
                
                # First try to get positions from actual visual items if they exist
                if visual_items:
                    # Visual items for planetary gear: sun gear, planet gears, carrier
                    # Get center positions from the gear circles
                    gear_circles = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]
                    
                    if len(gear_circles) >= 2:
                        # Typically: sun gear, planet gear(s)
                        anchor_positions["sun_center"] = gear_circles[0].scenePos() + gear_circles[0].rect().center()
                        anchor_positions["planet_center"] = gear_circles[1].scenePos() + gear_circles[1].rect().center()
                        
                        logging.info(f"[PLANETARY_ANCHORS] Got positions from visual items")
                        return anchor_positions
                
                # Fallback to calculation
                params = layer_data.get("params", {})
                r_sun = params.get("r_sun", 20)
                r_planet = params.get("r_planet", 30)

                # Check for simulation data or key points
                full_sim_data = layer_data.get("full_simulation_data", {})
                gear_positions = full_sim_data.get("gear_positions", {})

                if gear_positions and "sun_centers" in gear_positions:
                    sun_center_orig = np.array(gear_positions["sun_centers"][0])
                    planet_center_orig = np.array(gear_positions["planet_centers"][0])
                else:
                    sun_center_orig = np.array([0, 0])
                    planet_center_orig = sun_center_orig + (r_sun + r_planet) * np.array([1, 0])

                if to_scene_coords:
                    anchor_positions["sun_center"] = to_scene_coords(sun_center_orig)
                    anchor_positions["planet_center"] = to_scene_coords(planet_center_orig)
                else:
                    anchor_positions["sun_center"] = QPointF(sun_center_orig[0], sun_center_orig[1])
                    anchor_positions["planet_center"] = QPointF(planet_center_orig[0], planet_center_orig[1])

            elif mechanism_type == "4_bar_linkage":
                # Get visual items to find actual positions
                visual_items = layer_data.get("visual_items", [])
                
                # First try to get positions from actual visual items if they exist
                if visual_items:
                    # Visual items for 4-bar: ground links, moving links, pivots, coupler
                    # Get pivot positions from the pivot items (small circles)
                    pivot_items = [item for item in visual_items if isinstance(item, QGraphicsEllipseItem)]
                    
                    if len(pivot_items) >= 4:
                        # Typically: p1, p2, p3, p4 pivots
                        anchor_positions["ground_pivot_1"] = pivot_items[0].scenePos() + pivot_items[0].rect().center()
                        anchor_positions["ground_pivot_2"] = pivot_items[1].scenePos() + pivot_items[1].rect().center()
                        anchor_positions["crank_end"] = pivot_items[2].scenePos() + pivot_items[2].rect().center()
                        anchor_positions["rocker_end"] = pivot_items[3].scenePos() + pivot_items[3].rect().center()
                        
                        logging.info(f"[4BAR_ANCHORS] Got positions from visual items")
                        return anchor_positions
                
                # Fallback to using transform and simulation data
                key_points = layer_data.get("key_points", {})
                full_sim_data = layer_data.get("full_simulation_data", {})
                joint_positions = full_sim_data.get("joint_positions", {})

                if all(key in joint_positions for key in ["p1_positions", "p2_positions", "p3_positions", "p4_positions"]):
                    p1_pos = joint_positions["p1_positions"][0]
                    p2_pos = joint_positions["p2_positions"][0]
                    p3_pos = joint_positions["p3_positions"][0]
                    p4_pos = joint_positions["p4_positions"][0]

                    if to_scene_coords:
                        if "ground_pivot_1" not in anchor_positions:
                            anchor_positions["ground_pivot_1"] = to_scene_coords(np.array(p1_pos))
                        if "ground_pivot_2" not in anchor_positions:
                            anchor_positions["ground_pivot_2"] = to_scene_coords(np.array(p2_pos))
                        if "crank_end" not in anchor_positions:
                            anchor_positions["crank_end"] = to_scene_coords(np.array(p3_pos))
                        if "rocker_end" not in anchor_positions:
                            anchor_positions["rocker_end"] = to_scene_coords(np.array(p4_pos))

                # Create defaults if still missing
                if len(anchor_positions) < 2:
                    scene_center = QPointF(400, 300)
                    if "ground_pivot_1" not in anchor_positions:
                        anchor_positions["ground_pivot_1"] = QPointF(scene_center.x() - 100, scene_center.y())
                    if "ground_pivot_2" not in anchor_positions:
                        anchor_positions["ground_pivot_2"] = QPointF(scene_center.x() + 100, scene_center.y())
                    if "crank_end" not in anchor_positions:
                        anchor_positions["crank_end"] = QPointF(scene_center.x() - 50, scene_center.y() - 80)
                    if "rocker_end" not in anchor_positions:
                        anchor_positions["rocker_end"] = QPointF(scene_center.x() + 50, scene_center.y() - 80)

            logging.info(f"[ANCHORS] Generated {len(anchor_positions)} anchor positions for {mechanism_type}")

        except Exception as e:
            logging.error(f"Failed to get anchor positions for {mechanism_type}: {e}")

        return anchor_positions

    def _disable_mechanism_visual_interaction(self):
        """Disable mouse interaction on mechanism visual items to allow handle interaction."""
        try:
            for mechanism_id, layer_data in self.mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setFlag'):
                        # Disable all mouse interaction flags
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                        if hasattr(item, 'setAcceptedMouseButtons'):
                            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                        if hasattr(item, 'setAcceptHoverEvents'):
                            item.setAcceptHoverEvents(False)

            logging.info("[PARAMETRIC] Disabled interaction on mechanism visuals")

        except Exception as e:
            logging.error(f"Failed to disable mechanism visual interaction: {e}")

    def _enable_mechanism_visual_interaction(self):
        """Re-enable mouse interaction on mechanism visual items."""
        try:
            for mechanism_id, layer_data in self.mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                for item in visual_items:
                    if hasattr(item, 'setFlag'):
                        # Restore default interaction flags for mechanism visuals
                        # Mechanism visuals should be selectable but not necessarily movable
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
                        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                        if hasattr(item, 'setAcceptedMouseButtons'):
                            # Restore mouse button acceptance
                            item.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
                        if hasattr(item, 'setAcceptHoverEvents'):
                            item.setAcceptHoverEvents(True)

            logging.info("[PARAMETRIC] Re-enabled interaction on mechanism visuals")

        except Exception as e:
            logging.error(f"Failed to enable mechanism visual interaction: {e}")

        # Re-enable animation controls if we have enabled mechanisms
        has_enabled_mechanisms = any(self.mechanism_enabled_state.values()) if self.mechanism_enabled_state else False
        if self.mechanism_layers and has_enabled_mechanisms:
            self.play_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)


    def _on_export_blueprint(self):
        """Delegate to BlueprintExporter to export all content."""
        self.blueprint_exporter.export_all()


    def center_on_character(self):
        """Center the view on the character (all parts and mechanisms)."""
        if not self.mechanism_scene:
            return
        
        # Calculate bounding box of all parts and mechanisms
        combined_rect = None
        
        # Include parts (current_editor_items stores CharacterPartItem objects directly)
        if self.current_editor_items:
            for part_name, part_item in self.current_editor_items.items():
                if part_item and part_item.scene():
                    part_rect = part_item.sceneBoundingRect()
                    if combined_rect is None:
                        combined_rect = part_rect
                    else:
                        combined_rect = combined_rect.united(part_rect)
        
        # Include skeleton joints and bones
        if hasattr(self, 'skeleton_joint_items'):
            for joint_item in self.skeleton_joint_items.values():
                if joint_item and joint_item.scene():
                    joint_rect = joint_item.sceneBoundingRect()
                    if combined_rect is None:
                        combined_rect = joint_rect
                    else:
                        combined_rect = combined_rect.united(joint_rect)
        
        if combined_rect:
            # Add some padding
            padding = 50
            combined_rect.adjust(-padding, -padding, padding, padding)
            
            # Center on the character without changing zoom
            center = combined_rect.center()
            self.mechanism_view.centerOn(center)

    def _update_blueprint_button_state(self):
        """Update blueprint button enabled state based on available parts."""
        if self.blueprint_btn:
            has_parts = bool(self.current_editor_items)
            self.blueprint_btn.setEnabled(has_parts)

            if has_parts:
                part_count = len(self.current_editor_items)
                self.blueprint_btn.setToolTip(f"Export {part_count} character parts and mechanisms as SVG blueprint")
            else:
                self.blueprint_btn.setToolTip("Export character parts and mechanisms as SVG blueprint")


# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
