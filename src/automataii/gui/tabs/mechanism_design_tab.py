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
from PyQt6.QtCore import pyqtSignal, QPointF, Qt, QTimer, QRectF, QLineF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform, QFont

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
    qpainterpath_to_numpy_array,
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

        # Skeleton visualization items
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
        
        # Mechanism path tracing
        self.mechanism_trace_paths: Dict[str, QPainterPath] = {}  # Store traced paths
        self.mechanism_trace_items: Dict[str, QGraphicsPathItem] = {}  # Visual path items
        self.mechanism_trace_points: Dict[str, List[QPointF]] = {}  # Store trace points

        # UI Elements
        self.blueprint_btn: Optional[QPushButton] = None
        self.recommendation_btn: Optional[QPushButton] = None
        self.mechanism_layers_list: Optional[QListWidget] = None
        self.play_btn: Optional[QPushButton] = None
        self.stop_btn: Optional[QPushButton] = None
        self.reset_btn: Optional[QPushButton] = None
        self.animation_status_label: Optional[QLabel] = None
        self.enable_mechanisms_checkbox: Optional[QCheckBox] = None
        self.parametric_edit_btn: Optional[QPushButton] = None

        self._setup_ui()
        self._connect_signals()
        self._connect_to_ik_manager()
        
        # Enable debug consistency checking if in debug mode
        if self.debug_mode:
            self._debug_data_consistency_check = self._debug_data_consistency_check

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

        # 1. Mechanism Layers Group
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
        layers_layout.addWidget(self.mechanism_layers_list)

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

        self.recommendation_btn = QPushButton("Get Recommendations")
        self.recommendation_btn.setEnabled(False)
        self.recommendation_btn.setToolTip("Get mechanism recommendations based on motion paths")
        generation_layout.addWidget(self.recommendation_btn)

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

        self.animation_status_label = QLabel("No mechanisms defined")
        self.animation_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        animation_layout.addWidget(self.animation_status_label)

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()

        self.play_btn = QPushButton("Play")
        self.stop_btn = QPushButton("Stop")
        self.reset_btn = QPushButton("Reset")
        
        # Set initial button states
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

        animation_controls_layout = QHBoxLayout()
        animation_controls_layout.addWidget(self.play_btn)
        animation_controls_layout.addWidget(self.stop_btn)
        animation_controls_layout.addWidget(self.reset_btn)

        centering_layout.addLayout(animation_controls_layout)
        centering_layout.addStretch()

        animation_layout.addLayout(centering_layout)
        panel_layout.addWidget(animation_group)

        panel_layout.addStretch(1)

        control_panel.setMinimumWidth(280)
        scroll_area.setWidget(control_panel)
        main_layout.addWidget(scroll_area)

        # Right side - Editor view
        main_layout.addWidget(self.mechanism_view, 1)

    def _connect_signals(self):
        """Connect signals"""
        self.recommendation_btn.clicked.connect(self._on_get_recommendations)
        self.play_btn.clicked.connect(self._on_start_animation)
        self.stop_btn.clicked.connect(self._on_stop_animation)
        self.reset_btn.clicked.connect(self._on_reset_animation)
        self.mechanism_layers_list.itemSelectionChanged.connect(self._on_layer_selection_changed)
        self.enable_mechanisms_checkbox.stateChanged.connect(self._on_mechanism_enable_toggled)
    
    def _connect_to_ik_manager(self):
        """Connect to IK manager signals for skeleton animation."""
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Connect to skeleton pose updates
                self.main_window.ik_manager.skeleton_pose_updated.connect(self.on_skeleton_updated)
                logging.info("Connected to IK manager skeleton_pose_updated signal")
            except Exception as e:
                logging.warning(f"Failed to connect to IK manager: {e}")

    def set_path_data_from_editor(self, path_data: Dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        logging.info(f"MechanismDesignTab: Received path data for {len(path_data)} parts.")
        self.path_data = path_data.copy()
        self.recommendation_btn.setEnabled(bool(self.path_data))
        self._display_paths_in_preview()

    def set_parts_data(self, parts_data: Dict[str, PartInfo]):
        """Set parts data (synchronized with editor tab)"""
        self.parts_data = parts_data.copy() if parts_data else {}
        self.mechanism_scene.clear()
        self.current_editor_items.clear()

        if parts_data:
            project_dir = self.main_window.project_data_manager.project_dir
            for part_name, p_info in parts_data.items():
                if project_dir:
                    item = CharacterPartItem(part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode)
                    item.setZValue(5)  # Parts below mechanisms but above background
                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item
            self._position_parts_at_anchor_joints()
            self.mechanism_view.zoom_to_fit()
        logging.info(f"Mechanism tab loaded {len(self.current_editor_items)} parts.")

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

    def cache_initial_skeleton(self, skeleton_data_dict: Optional[Dict]):
        """Cache the initial skeleton data dictionary"""
        self._initial_skeleton_data_cache = skeleton_data_dict.copy() if skeleton_data_dict else None
        if self._initial_skeleton_data_cache:
            if self.mechanism_view and hasattr(self.mechanism_view, "set_joint_map"):
                self.mechanism_view.set_joint_map(self._initial_skeleton_data_cache.get("joint_map"))
            if self.current_editor_items:
                self._position_parts_at_anchor_joints()

    def on_skeleton_updated(self, skeleton_data: Optional[Dict]):
        """Handle skeleton updates from IK manager (like in editor tab)."""
        if self.mechanism_view and skeleton_data:
            # Check if we received raw animation data from IK manager
            if skeleton_data and all(isinstance(v, tuple) and len(v) == 2 for v in skeleton_data.values()):
                # Convert IK manager format Dict[str, Tuple[float, float]] to expected format
                # Update skeleton visualization using the animation data directly
                if hasattr(self.mechanism_view, 'update_skeleton_animation'):
                    self.mechanism_view.update_skeleton_animation(skeleton_data)
                
                # Transform to expected format for part updates
                transformed_data = {
                    "joints": {
                        joint_id: {
                            "scene_position": list(pos),
                            "id": joint_id
                        } 
                        for joint_id, pos in skeleton_data.items()
                    }
                }
                skeleton_data = transformed_data
            else:
                # Standard skeleton model format - use existing method
                if hasattr(self.mechanism_view, 'update_visuals_from_animation_data'):
                    self.mechanism_view.update_visuals_from_animation_data(skeleton_data)
            
            # Update part positions from skeleton during animation
            if self.animation_timer.isActive():
                self._update_parts_from_skeleton(skeleton_data)
            else:
                # Even when not animating, update parts that aren't mechanism-controlled
                self._update_parts_from_skeleton(skeleton_data)
    
    def _update_parts_from_skeleton(self, skeleton_data: Dict):
        """Update part positions based on skeleton joint movements (like in editor tab)."""
        joints_dict = skeleton_data.get("joints", {})
        
        for part_name, part_item in self.current_editor_items.items():
            part_info = self.parts_data.get(part_name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                
                # Check if this part is controlled by a mechanism
                is_mechanism_controlled = self._is_part_mechanism_controlled(part_name)
                
                # Always update part position, but mechanism-controlled parts get priority
                if "scene_position" in joint_data:
                    scene_pos = joint_data["scene_position"]
                    if isinstance(scene_pos, (list, tuple)) and len(scene_pos) >= 2:
                        scene_pos = QPointF(scene_pos[0], scene_pos[1])
                        part_item.set_scene_position_from_anchor(scene_pos)
                
                # Update rotation for all parts (skeleton handles this)
                if "world_rotation_degrees" in joint_data:
                    rotation = float(joint_data["world_rotation_degrees"])
                    part_item.setRotation(rotation)
                elif not is_mechanism_controlled:
                    # For non-mechanism parts, use basic skeleton positioning
                    if "scene_position" in joint_data:
                        scene_pos = joint_data["scene_position"]
                        if isinstance(scene_pos, (list, tuple)) and len(scene_pos) >= 2:
                            scene_pos = QPointF(scene_pos[0], scene_pos[1])
                            part_item.set_scene_position_from_anchor(scene_pos)
    
    def _is_part_mechanism_controlled(self, part_name: str) -> bool:
        """Check if a part is currently controlled by an active mechanism."""
        for mech_id, layer_data in self.mechanism_layers.items():
            if (self.mechanism_enabled_state.get(mech_id, False) and 
                layer_data.get("part_name") == part_name):
                return True
        return False

    def clear_mechanism_data(self):
        """Clear all mechanism-related data and reset the tab's state."""
        logging.info("Clearing all mechanism data from MechanismDesignTab.")
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            self.animation_time = 0.0

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

        if self.mechanism_layers_list:
            self.mechanism_layers_list.clear()

        if self.mechanism_scene:
            self.mechanism_scene.clear()

        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.recommendation_btn.setEnabled(False)
        self.enable_mechanisms_checkbox.setEnabled(False)
        self.enable_mechanisms_checkbox.setChecked(False)

        if self.animation_status_label:
            self.animation_status_label.setText("No mechanisms defined")

        self.selected_mechanism_id = None

    @pyqtSlot()
    def _on_get_recommendations(self):
        """Show mechanism recommendation dialog"""
        if not self.path_data:
            QMessageBox.warning(self, "Warning", "No motion paths available.")
            return

        # For simplicity, we use the first available path
        target_part_name, target_path = next(iter(self.path_data.items()))
        self.selected_part_name = target_part_name

        import os
        from automataii.utils.paths import get_project_root
        generated_paths_file = os.path.join(get_project_root(), "src", "automataii", "kinematics", "generated_mechanism_paths.json")

        if not os.path.exists(generated_paths_file):
            QMessageBox.critical(self, "Error", "Generated mechanism paths file not found.")
            return

        dialog = MechanismRecommendationDialog(target_path, generated_paths_file, parent=self)
        # Connect the preview signal to handle mechanism previews
        dialog.mechanism_preview_selected.connect(self._on_mechanism_preview_selected)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mechanism = dialog.selected_mechanism_data
            if selected_mechanism:
                self._generate_mechanism_from_candidate(selected_mechanism)

    def _on_mechanism_preview_selected(self, mechanism_data: Dict[str, Any]):
        """Handle mechanism preview selection from dialog."""
        # Temporarily show the mechanism in the view
        self._preview_mechanism(mechanism_data)
    
    def _preview_mechanism(self, mechanism_data: Dict[str, Any]):
        """Preview a mechanism without adding it to the layers."""
        # Clear any existing preview items
        if hasattr(self, '_preview_items'):
            for item in self._preview_items:
                if item.scene():
                    self.mechanism_scene.removeItem(item)
        self._preview_items = []
        
        # Create temporary visuals for the preview
        mechanism_type_value = mechanism_data.get('type', 'Unknown')
        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage", 
            "Cam & Follower": "cam",
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")
        
        if internal_type == "4_bar_linkage":
            visual_items = self._create_4bar_linkage_visuals(mechanism_data)
            self._preview_items.extend(visual_items)
    
    def _generate_mechanism_from_candidate(self, candidate_data: Dict[str, Any]):
        """Generates a mechanism layer and visuals from a selected candidate."""
        mechanism_id = str(uuid.uuid4())[:8]
        mechanism_type_value = candidate_data.get('type', 'Unknown')
        raw_params = candidate_data.get('parameters', {})
        params = self._convert_json_params_to_internal(mechanism_type_value, raw_params)

        mechanism_type_mapping = {
            "4-Bar Linkage": "4_bar_linkage", 
            "Cam & Follower": "cam",
            "Gears (Simple Pair)": "gear",
            "Gear Contact": "gear",
        }
        internal_type = mechanism_type_mapping.get(mechanism_type_value, "4_bar_linkage")

        layer_name = f"{self.selected_part_name} - {mechanism_type_value}"
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
        }
        
        # DEBUG: Log the mechanism data structure
        if self.debug_mode:
            full_sim_data = layer_data.get("full_simulation_data", {})
            logging.info(f"[DEBUG] _generate_mechanism_from_candidate: mechanism_id={mechanism_id}")
            logging.info(f"[DEBUG] candidate_data keys: {list(candidate_data.keys())}")
            logging.info(f"[DEBUG] full_simulation_data keys: {list(full_sim_data.keys())}")
            
            if "joint_positions" in full_sim_data:
                joint_pos = full_sim_data["joint_positions"]
                logging.info(f"[DEBUG] joint_positions keys: {list(joint_pos.keys())}")
                if "p1_positions" in joint_pos:
                    logging.info(f"[DEBUG] joint_positions has {len(joint_pos['p1_positions'])} frames")
            else:
                logging.warning(f"[DEBUG] No joint_positions in full_simulation_data!")
            
            if "coupler_path" in full_sim_data:
                coupler_path = full_sim_data["coupler_path"]
                logging.info(f"[DEBUG] coupler_path has {len(coupler_path)} points")
            else:
                logging.warning(f"[DEBUG] No coupler_path in full_simulation_data!")
        
        # Verify and adjust coupler point connection to skeleton joint
        self._verify_coupler_joint_connection(layer_data)
        self._adjust_mechanism_to_target_joint(layer_data)
        
        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, params, layer_data)
        
        # Add debug visualization for transform comparison
        self._add_transform_comparison_visuals(layer_data)
        
        # Log mechanism attachment information
        skeleton_attachment = layer_data.get("skeleton_attachment", {})
        mechanism_layout = layer_data.get("mechanism_layout", {})
        if skeleton_attachment:
            attachment_point = skeleton_attachment.get("attachment_point", "unknown")
            attachment_desc = skeleton_attachment.get("description", "")
            logging.info(f"Mechanism attachment: {attachment_point} - {attachment_desc}")
        
        if mechanism_layout:
            layout_desc = mechanism_layout.get("description", "")
            coord_system = mechanism_layout.get("coordinate_system", {})
            logging.info(f"Mechanism layout: {layout_desc}")
            logging.info(f"Coordinate system: origin={coord_system.get('origin', 'unknown')}")

        # Update UI to show mechanism is ready
        self.animation_status_label.setText(f"Mechanism ready: {layer_name}")
        
        # Select the newly added mechanism in the list
        for i in range(self.mechanism_layers_list.count()):
            item = self.mechanism_layers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == mechanism_id:
                self.mechanism_layers_list.setCurrentItem(item)
                self.enable_mechanisms_checkbox.setChecked(True)
                break
                
        logging.info(f"Added mechanism {mechanism_id} with type {internal_type}")

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
                        logging.info(f"Attachment point ({attachment_point}) connected to joint {anchor_joint_id}, distance = {distance:.1f}")
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
                    else:
                        logging.info(f"Mechanism output point connected to joint {anchor_joint_id}, distance = {distance:.1f}")
    
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
                        user_path_np = self._qpainterpath_to_numpy(target_path)
                        if user_path_np is not None:
                            target_center_np = np.mean(user_path_np, axis=0)
                            
                            # Adjust target center to align with skeleton joint
                            new_target_center = target_center_np + offset
                            
                            # Store the adjustment for the transform function
                            layer_data["_target_center_adjustment"] = new_target_center.tolist()
                            
                            logging.info(f"Adjusted mechanism target center by {offset}")
                            logging.info(f"New target center: {new_target_center}")
                else:
                    logging.warning("Cannot adjust mechanism: missing full simulation data")

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the layers list"""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data
        item = QListWidgetItem(layer_name)
        item.setData(Qt.ItemDataRole.UserRole, mechanism_id)
        self.mechanism_layers_list.addItem(item)
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.enable_mechanisms_checkbox.setEnabled(True)
        
        # Initialize path tracing for this mechanism
        self._init_mechanism_path_trace(mechanism_id)

    def _qpainterpath_to_numpy(self, path: QPainterPath, num_points: int = 100) -> Optional[np.ndarray]:
        """Converts a QPainterPath to a numpy array of points."""
        return qpainterpath_to_numpy_array(path, num_points)

    def _get_scene_transform_function(self, layer_data: dict) -> Optional[callable]:
        """Creates a function to transform points from mechanism's original space to scene space.
        
        Uses the same transformation as recommendation dialog to ensure consistent rotation.
        """
        target_path = layer_data.get("generated_path")
        transform_params = layer_data.get("transform_params")
        vis_params = layer_data.get("visualization_params")

        if not all([target_path, transform_params, vis_params]):
            return None

        user_path_np = self._qpainterpath_to_numpy(target_path)
        if user_path_np is None:
            return None

        # Get transformation parameters from alignment (same as dialog)
        center = np.array(vis_params["center"])
        scale = vis_params["scale"]
        angle = transform_params["rotation"]

        if np.isclose(scale, 0):
            return None

        # Apply rotation matrix (same as dialog)
        rotation_matrix = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])

        # Calculate target positioning (use adjustment if available)
        if "_target_center_adjustment" in layer_data:
            target_center_np = np.array(layer_data["_target_center_adjustment"])
        else:
            target_center_np = np.mean(user_path_np, axis=0)
        
        # Use simple, consistent scaling approach
                
        def to_scene_coords(p_orig: np.ndarray) -> QPointF:
            # Apply EXACT same transformation as recommendation dialog
            # 1. Normalize using mechanism's bounding box parameters
            p_norm = ((p_orig - center) / scale) @ rotation_matrix.T
            
            # 2. Simple scaling and positioning like dialog (no complex scale_factor)
            p_scaled = p_norm * 80  # Fixed reasonable scale for scene
            p_final = p_scaled + target_center_np
            
            # DEBUG: Log transformation steps
            if hasattr(self, 'debug_mode') and self.debug_mode:
                # Only log every 10th call to reduce spam
                if not hasattr(to_scene_coords, '_debug_call_count'):
                    to_scene_coords._debug_call_count = 0
                to_scene_coords._debug_call_count += 1
                if to_scene_coords._debug_call_count % 10 == 1:
                    logging.info(f"[DEBUG] Transform: p_orig={p_orig} -> p_norm={p_norm} -> p_scaled={p_scaled} -> p_final={p_final}")
                    logging.info(f"[DEBUG] Transform params: center={center}, scale={scale}, angle={angle:.3f}, target_center={target_center_np}")
            
            return QPointF(p_final[0], p_final[1])
        
        return to_scene_coords

    def _add_transform_comparison_visuals(self, layer_data: dict):
        """Add visual indicators to compare dialog preview vs final mechanism positioning."""
        if not self.debug_mode:
            return
            
        # Get initial mechanism position
        initial_pos = self._calculate_mechanism_output(
            layer_data["type"], layer_data["params"], 0.0, layer_data
        )
        
        if initial_pos:
            # Add a cross-hair marker at the initial position
            cross_size = 20
            cross_pen = QPen(QColor("#ff0000"), 3)  # Red cross
            
            # Horizontal line
            h_line = self.mechanism_scene.addLine(
                initial_pos.x() - cross_size/2, initial_pos.y(),
                initial_pos.x() + cross_size/2, initial_pos.y(),
                cross_pen
            )
            h_line.setZValue(25)  # High Z to be visible
            
            # Vertical line
            v_line = self.mechanism_scene.addLine(
                initial_pos.x(), initial_pos.y() - cross_size/2,
                initial_pos.x(), initial_pos.y() + cross_size/2,
                cross_pen
            )
            v_line.setZValue(25)
            
            # Add text label
            text_item = self.mechanism_scene.addText(
                f"Mech@t=0", 
                QFont("Arial", 10)
            )
            text_item.setDefaultTextColor(QColor("#ff0000"))
            text_item.setPos(initial_pos.x() + 10, initial_pos.y() - 10)
            text_item.setZValue(25)
            
            # Store debug items for cleanup
            if not hasattr(self, '_debug_items'):
                self._debug_items = []
            self._debug_items.extend([h_line, v_line, text_item])
            
            logging.info(f"Added transform comparison visual at {initial_pos.x():.1f}, {initial_pos.y():.1f}")

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, layer_data: dict) -> Optional[QPointF]:
        """Calculates mechanism output point using dataset's joint positions for perfect consistency with visuals."""
        full_sim_data = layer_data.get("full_simulation_data", {})
        
        # DEBUG: Log the data availability
        if self.debug_mode:
            logging.info(f"[DEBUG] _calculate_mechanism_output: mech_type={mech_type}, time={time:.3f}")
            logging.info(f"[DEBUG] full_sim_data keys: {list(full_sim_data.keys())}")
            if "joint_positions" in full_sim_data:
                joint_keys = list(full_sim_data["joint_positions"].keys())
                logging.info(f"[DEBUG] joint_positions keys: {joint_keys}")
                if "p1_positions" in full_sim_data["joint_positions"]:
                    num_frames = len(full_sim_data["joint_positions"]["p1_positions"])
                    logging.info(f"[DEBUG] joint_positions has {num_frames} frames")
        
        if mech_type == "4_bar_linkage" and "joint_positions" in full_sim_data:
            # Use joint positions to calculate coupler point - SAME AS VISUALS
            joint_positions = full_sim_data["joint_positions"]
            to_scene_coords = self._get_scene_transform_function(layer_data)
            
            if "p1_positions" in joint_positions and to_scene_coords:
                num_frames = len(joint_positions["p1_positions"])
                normalized_time = time / (2 * math.pi)
                frame_index = int(normalized_time * (num_frames - 1))
                frame_index = max(0, min(frame_index, num_frames - 1))
                
                # DEBUG: Log frame index calculation (same as visuals)
                if self.debug_mode:
                    logging.info(f"[DEBUG] _calculate_mechanism_output: time={time:.3f}, normalized_time={normalized_time:.3f}, frame_index={frame_index}/{num_frames-1}")
                
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
                
                # DEBUG: Log the calculated coupler point
                if self.debug_mode:
                    logging.info(f"[DEBUG] Calculated coupler point from joints: p3={p3}, p4={p4}")
                    logging.info(f"[DEBUG] Coupler params: x={coupler_point_x}, y={coupler_point_y}")
                    logging.info(f"[DEBUG] Final coupler point: {p_coupler}")
                
                # Apply the same transformation as the visuals
                scene_point = to_scene_coords(p_coupler)
                if self.debug_mode:
                    logging.info(f"[DEBUG] transformed scene_point: ({scene_point.x():.2f}, {scene_point.y():.2f})")
                return scene_point
            else:
                logging.warning("[DEBUG] Missing joint_positions or transform function")
                return None
                
        elif mech_type == "cam":
            # Calculate cam follower output using skeleton attachment info
            skeleton_attachment = layer_data.get("skeleton_attachment", {})
            attachment_coords = skeleton_attachment.get("attachment_coordinates")
            
            if attachment_coords:
                # Use attachment coordinates as base, then calculate position at time
                params = layer_data.get("params", {})
                base_radius = params.get("base_radius", 25.0)
                eccentricity = params.get("eccentricity", 10.0)
                to_scene_coords = self._get_scene_transform_function(layer_data)
                
                if to_scene_coords:
                    # Calculate cam rotation and follower position (same as dataset)
                    angle = time
                    rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                    cam_center_orig = rotation_matrix @ np.array([eccentricity, 0])
                    follower_y = cam_center_orig[1] + base_radius
                    follower_pos_orig = np.array([0, follower_y])
                    
                    scene_point = to_scene_coords(follower_pos_orig)
                    if self.debug_mode:
                        logging.info(f"[DEBUG] Cam output (from attachment): follower_y={follower_y:.2f}, scene=({scene_point.x():.2f}, {scene_point.y():.2f})")
                    return scene_point
            
            # Fallback to manual calculation
            params = layer_data.get("params", {})
            base_radius = params.get("base_radius", 25.0)
            eccentricity = params.get("eccentricity", 10.0)
            to_scene_coords = self._get_scene_transform_function(layer_data)
            
            if to_scene_coords:
                angle = time
                rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                cam_center_orig = rotation_matrix @ np.array([eccentricity, 0])
                follower_y = cam_center_orig[1] + base_radius
                follower_pos_orig = np.array([0, follower_y])
                
                scene_point = to_scene_coords(follower_pos_orig)
                if self.debug_mode:
                    logging.info(f"[DEBUG] Cam output (fallback): follower_y={follower_y:.2f}, scene=({scene_point.x():.2f}, {scene_point.y():.2f})")
                return scene_point
            else:
                return None
                
        elif mech_type == "gear":
            # Calculate gear train output using skeleton attachment info
            skeleton_attachment = layer_data.get("skeleton_attachment", {})
            attachment_coords = skeleton_attachment.get("attachment_coordinates")
            
            if attachment_coords:
                # Use attachment coordinates as reference for gear 1 circumference point
                params = layer_data.get("params", {})
                r1 = params.get("r1", 30)
                mechanism_layout = layer_data.get("mechanism_layout", {})
                gear1_center_coords = None
                
                if mechanism_layout:
                    components = mechanism_layout.get("components", {})
                    gear1_info = components.get("gear1", {})
                    gear1_center_coords = gear1_info.get("center")
                
                to_scene_coords = self._get_scene_transform_function(layer_data)
                if to_scene_coords and gear1_center_coords:
                    # Calculate point on gear 1 circumference (same as dataset)
                    theta1 = time
                    gear1_center = np.array(gear1_center_coords)
                    output_point_orig = gear1_center + np.array([r1 * np.cos(theta1), r1 * np.sin(theta1)])
                    
                    scene_point = to_scene_coords(output_point_orig)
                    if self.debug_mode:
                        logging.info(f"[DEBUG] Gear output (from attachment): theta1={theta1:.2f}, scene=({scene_point.x():.2f}, {scene_point.y():.2f})")
                    return scene_point
            
            # Fallback to manual calculation
            params = layer_data.get("params", {})
            r1 = params.get("r1", 30)
            to_scene_coords = self._get_scene_transform_function(layer_data)
            
            if to_scene_coords:
                # Calculate point on gear 1 circumference
                theta1 = time
                gear1_center = np.array([-r1, 0])  # Default position
                output_point_orig = gear1_center + np.array([r1 * np.cos(theta1), r1 * np.sin(theta1)])
                
                scene_point = to_scene_coords(output_point_orig)
                if self.debug_mode:
                    logging.info(f"[DEBUG] Gear output (fallback): theta1={theta1:.2f}, scene=({scene_point.x():.2f}, {scene_point.y():.2f})")
                return scene_point
            else:
                return None
                
        else:
            # Fallback to manual calculation if no simulation data
            if self.debug_mode:
                logging.warning(f"[DEBUG] Using fallback calculation for {mech_type} - no joint_positions available")
            return self._calculate_mechanism_output_manual(mech_type, params, time, layer_data)
    
    def _calculate_mechanism_output_manual(self, mech_type: str, params: dict, time: float, layer_data: dict) -> Optional[QPointF]:
        """Manual calculation fallback (original implementation)."""
        key_points = layer_data.get("key_points")
        output_point_orig = None

        if mech_type == "4_bar_linkage":
            if not key_points or not params: 
                if self.debug_mode:
                    logging.warning(f"Missing key_points or params for 4-bar linkage")
                return None

            l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
            p1_coords, p2_coords = key_points.get("ground_pivot_1"), key_points.get("ground_pivot_2")
            coupler_point_x, coupler_point_y = params.get("coupler_point_x", 0), params.get("coupler_point_y", 0)

            if not all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
                 logging.warning(f"Incomplete 4-bar linkage parameters: l2={l2}, l3={l3}, l4={l4}, p1={p1_coords}, p2={p2_coords}")
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
            if not (abs(l3 - l4) <= d <= (l3 + l4)): return None

            a = (l3**2 - l4**2 + d_sq) / (2 * d)
            h = math.sqrt(max(0, l3**2 - a**2))
            p3_p2_unit = (p2 - p3) / d
            midpoint = p3 + a * p3_p2_unit
            p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

            coupler_link_vec = p4 - p3
            coupler_link_len = np.linalg.norm(coupler_link_vec)
            if np.isclose(coupler_link_len, 0): return None

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
        """Update animation frame."""
        dt = 0.033 * self.animation_speed
        self.animation_time += dt
        if self.animation_time > 2 * math.pi: self.animation_time -= 2 * math.pi

        # Track which parts are being animated by mechanisms
        animated_parts = {}
        
        for mechanism_id, is_enabled in self.mechanism_enabled_state.items():
            if not is_enabled: continue
            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data: continue

            output_pos = self._calculate_mechanism_output(layer_data["type"], layer_data["params"], self.animation_time, layer_data)

            if output_pos:
                part_name = layer_data.get("part_name")
                if part_name in self.current_editor_items:
                    animated_parts[part_name] = output_pos
                    
                    # Update IK system with current target position for this frame
                    if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
                        try:
                            part_info = self.parts_data.get(part_name)
                            if part_info and part_info.anchor_joint_id:
                                # Create a simple path with current position for IK manager
                                current_path = QPainterPath()
                                current_path.moveTo(output_pos)
                                current_path.lineTo(output_pos.x() + 1, output_pos.y())  # Tiny movement
                                self.main_window.ik_manager.update_part_motion_path(part_name, current_path)
                        except Exception as e:
                            if self.debug_mode:
                                logging.warning(f"Failed to update IK target position: {e}")
                    
                    # Update mechanism visuals (this should use same data as _calculate_mechanism_output)
                    try:
                        self._update_mechanism_visuals_for_animation(mechanism_id, self.animation_time, layer_data)
                        
                        # DEBUG: Compare output positions if both functions succeed
                        if self.debug_mode and hasattr(self, '_debug_data_consistency_check'):
                            self._debug_data_consistency_check(mechanism_id, self.animation_time, layer_data, output_pos)
                            
                    except Exception as e:
                        if self.debug_mode:
                            logging.warning(f"Failed to update mechanism visuals: {e}")
                else:
                    if self.debug_mode and self.animation_time < 0.2:  # Log once at start
                        available_parts = list(self.current_editor_items.keys())
                        logging.warning(f"Part '{part_name}' not found. Available parts: {available_parts}")
        
        # Update mechanism path tracing after animation
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if self.mechanism_enabled_state.get(mechanism_id, False):
                output_pos = self._calculate_mechanism_output(
                    layer_data["type"], layer_data["params"], self.animation_time, layer_data
                )
                if output_pos:
                    self._update_mechanism_path_trace(mechanism_id, output_pos)

    def _update_mechanism_visuals_for_animation(self, mechanism_id: str, time: float, layer_data: dict):
        """Update mechanism visual elements during animation using exact dataset positions."""
        try:
            mech_type = layer_data.get("type")
            visual_items = layer_data.get("visual_items", [])
            
            # DEBUG: Log visual update start
            if self.debug_mode:
                logging.info(f"[DEBUG] _update_mechanism_visuals_for_animation: mechanism_id={mechanism_id}, time={time:.3f}")
                logging.info(f"[DEBUG] mech_type={mech_type}, visual_items count={len(visual_items)}")
            
            if mech_type == "4_bar_linkage" and len(visual_items) >= 8:  # 4 links + 4 pivots
                full_sim_data = layer_data.get("full_simulation_data", {})
                to_scene_coords = self._get_scene_transform_function(layer_data)
                
                # DEBUG: Log data availability for visuals
                if self.debug_mode:
                    has_joint_pos = "joint_positions" in full_sim_data
                    has_transform = to_scene_coords is not None
                    logging.info(f"[DEBUG] has_joint_positions={has_joint_pos}, has_transform={has_transform}")
                
                # Use exact joint positions from dataset for perfect consistency
                if "joint_positions" in full_sim_data and to_scene_coords:
                    joint_positions = full_sim_data["joint_positions"]
                    
                    # Calculate which frame corresponds to current time
                    if "p1_positions" in joint_positions:
                        num_frames = len(joint_positions["p1_positions"])
                        normalized_time = time / (2 * math.pi)
                        frame_index = int(normalized_time * (num_frames - 1))
                        frame_index = max(0, min(frame_index, num_frames - 1))
                        
                        # DEBUG: Log frame index calculation (same as _calculate_mechanism_output)
                        if self.debug_mode:
                            logging.info(f"[DEBUG] _update_mechanism_visuals: time={time:.3f}, normalized_time={normalized_time:.3f}, frame_index={frame_index}/{num_frames-1}")
                        
                        # Get exact positions from dataset
                        p1 = np.array(joint_positions["p1_positions"][frame_index])
                        p2 = np.array(joint_positions["p2_positions"][frame_index])
                        p3 = np.array(joint_positions["p3_positions"][frame_index])
                        p4 = np.array(joint_positions["p4_positions"][frame_index])
                        
                        # Calculate coupler point using same method as _calculate_mechanism_output
                        params = layer_data.get("params", {})
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
                        
                        # DEBUG: Log original joint positions and coupler point
                        if self.debug_mode:
                            logging.info(f"[DEBUG] Original joint positions: p1={p1}, p2={p2}, p3={p3}, p4={p4}")
                            logging.info(f"[DEBUG] Coupler point in visuals: {p_coupler}")
                        
                        # Transform to scene coordinates
                        p1_t, p2_t, p3_t, p4_t = map(to_scene_coords, [p1, p2, p3, p4])
                        p_coupler_t = to_scene_coords(p_coupler)
                        
                        # DEBUG: Log transformed positions
                        if self.debug_mode:
                            logging.info(f"[DEBUG] Transformed positions: p1_t=({p1_t.x():.2f},{p1_t.y():.2f}), p3_t=({p3_t.x():.2f},{p3_t.y():.2f})")
                            logging.info(f"[DEBUG] Transformed coupler: ({p_coupler_t.x():.2f},{p_coupler_t.y():.2f})")
                        
                        # Update link positions (first 4 items are links)
                        if len(visual_items) >= 4:
                            if isinstance(visual_items[0], QGraphicsLineItem):
                                visual_items[0].setLine(QLineF(p1_t, p3_t))  # Link 1
                            if isinstance(visual_items[1], QGraphicsLineItem):
                                visual_items[1].setLine(QLineF(p3_t, p4_t))  # Link 2
                            if isinstance(visual_items[2], QGraphicsLineItem):
                                visual_items[2].setLine(QLineF(p4_t, p2_t))  # Link 3
                            # Link 4 (ground) doesn't move
                        
                        # Update pivot positions (items 4-7 are pivots)
                        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
                        for i, pos in enumerate(pivot_positions):
                            if i + 4 < len(visual_items):
                                pivot_item = visual_items[i + 4]
                                if isinstance(pivot_item, QGraphicsEllipseItem):
                                    pivot_item.setPos(pos.x() - pivot_item.rect().width()/2, 
                                                     pos.y() - pivot_item.rect().height()/2)
                        
                        # Add coupler point marker if not already present (visual items 8+)
                        if len(visual_items) >= 9 and isinstance(visual_items[8], QGraphicsEllipseItem):
                            coupler_marker = visual_items[8]
                            coupler_marker.setPos(p_coupler_t.x() - coupler_marker.rect().width()/2,
                                                p_coupler_t.y() - coupler_marker.rect().height()/2)
                        
                        if self.debug_mode:
                            logging.info(f"[DEBUG] Successfully updated visuals using dataset joint_positions")
                        return  # Success, exit early
                
                # Fallback to manual calculation if dataset doesn't have joint positions
                if self.debug_mode:
                    logging.warning(f"[DEBUG] Using fallback calculation for mechanism {mechanism_id} - dataset may be outdated or missing joint_positions")
                else:
                    logging.warning(f"Using fallback calculation for mechanism {mechanism_id} - dataset may be outdated")
                self._update_mechanism_visuals_fallback(visual_items, time, layer_data)
            
            elif mech_type == "cam" and len(visual_items) >= 2:  # Cam and follower
                params = layer_data.get("params", {})
                base_radius = params.get("base_radius", 25.0)
                eccentricity = params.get("eccentricity", 10.0)
                to_scene_coords = self._get_scene_transform_function(layer_data)
                
                if to_scene_coords:
                    # Calculate cam rotation based on time
                    angle = time
                    rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                    cam_center_orig = rotation_matrix @ np.array([eccentricity, 0])
                    
                    # Calculate follower position
                    follower_y = cam_center_orig[1] + base_radius
                    follower_pos_orig = np.array([0, follower_y])
                    
                    # Transform to scene coordinates
                    cam_center_scene = to_scene_coords(cam_center_orig)
                    follower_scene = to_scene_coords(follower_pos_orig)
                    
                    # Update cam visual (assuming first item is cam)
                    if len(visual_items) >= 1 and hasattr(visual_items[0], 'setPos'):
                        visual_items[0].setPos(cam_center_scene.x() - base_radius, cam_center_scene.y() - base_radius)
                    
                    # Update follower visual (assuming second item is follower)
                    if len(visual_items) >= 2 and hasattr(visual_items[1], 'setPos'):
                        visual_items[1].setPos(follower_scene.x() - 10, follower_scene.y() - 5)
                    
                    if self.debug_mode:
                        logging.info(f"[DEBUG] Updated cam mechanism: cam_center={cam_center_scene.x():.1f},{cam_center_scene.y():.1f}, follower={follower_scene.x():.1f},{follower_scene.y():.1f}")
                    return
            
            elif mech_type == "gear" and len(visual_items) >= 4:  # Gear train
                params = layer_data.get("params", {})
                r1 = params.get("r1", 30)
                r2 = params.get("r2", 50)
                to_scene_coords = self._get_scene_transform_function(layer_data)
                
                if to_scene_coords:
                    # Calculate gear rotations
                    theta1 = time
                    theta2 = -theta1 * (r1 / r2)  # Gear ratio
                    
                    # Gear centers
                    gear1_center = np.array([-r1, 0])
                    gear2_center = np.array([r2, 0])
                    
                    # Transform to scene coordinates
                    g1_center_scene = to_scene_coords(gear1_center)
                    g2_center_scene = to_scene_coords(gear2_center)
                    
                    # Update gear visual positions (assuming items 0,1 are gear bodies, 2,3 are indicators)
                    if len(visual_items) >= 2:
                        if hasattr(visual_items[0], 'setPos'):
                            visual_items[0].setPos(g1_center_scene.x() - r1, g1_center_scene.y() - r1)
                        if hasattr(visual_items[1], 'setPos'):
                            visual_items[1].setPos(g2_center_scene.x() - r2, g2_center_scene.y() - r2)
                    
                    # Update gear rotation indicators (lines)
                    if len(visual_items) >= 4:
                        # Gear 1 indicator
                        if isinstance(visual_items[2], QGraphicsLineItem):
                            end1 = g1_center_scene + QPointF(r1 * math.cos(theta1), r1 * math.sin(theta1))
                            visual_items[2].setLine(QLineF(g1_center_scene, end1))
                        
                        # Gear 2 indicator  
                        if isinstance(visual_items[3], QGraphicsLineItem):
                            end2 = g2_center_scene + QPointF(r2 * math.cos(theta2), r2 * math.sin(theta2))
                            visual_items[3].setLine(QLineF(g2_center_scene, end2))
                    
                    if self.debug_mode:
                        logging.info(f"[DEBUG] Updated gear mechanism: theta1={theta1:.2f}, theta2={theta2:.2f}")
                    return
                        
        except Exception as e:
            logging.warning(f"Error updating mechanism visuals for {mechanism_id}: {e}")
    
    def _update_mechanism_visuals_fallback(self, visual_items: list, time: float, layer_data: dict):
        """Fallback visual update using manual calculation."""
        to_scene_coords = self._get_scene_transform_function(layer_data)
        params = layer_data.get("params", {})
        key_points = layer_data.get("key_points")
        
        if to_scene_coords and key_points and params:
            l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
            p1_coords, p2_coords = key_points.get("ground_pivot_1"), key_points.get("ground_pivot_2")
            
            if all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
                p1, p2 = np.array(p1_coords), np.array(p2_coords)
                
                # Manual calculation (geometric approximation)
                p3 = p1 + np.array([l2 * math.cos(time), l2 * math.sin(time)])
                d = np.linalg.norm(p2 - p3)
                
                if abs(l3 - l4) <= d <= l3 + l4:
                    a = (l3**2 - l4**2 + d**2) / (2 * d)
                    h = math.sqrt(max(0, l3**2 - a**2))
                    p3_p2_unit = (p2 - p3) / d
                    midpoint = p3 + a * p3_p2_unit
                    p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])
                    
                    # Transform to scene coordinates
                    p1_t, p2_t, p3_t, p4_t = map(to_scene_coords, [p1, p2, p3, p4])
                    
                    # Update visuals
                    if len(visual_items) >= 4:
                        if isinstance(visual_items[0], QGraphicsLineItem):
                            visual_items[0].setLine(QLineF(p1_t, p3_t))
                        if isinstance(visual_items[1], QGraphicsLineItem):
                            visual_items[1].setLine(QLineF(p3_t, p4_t))
                        if isinstance(visual_items[2], QGraphicsLineItem):
                            visual_items[2].setLine(QLineF(p4_t, p2_t))
                    
                    pivot_positions = [p1_t, p2_t, p3_t, p4_t]
                    for i, pos in enumerate(pivot_positions):
                        if i + 4 < len(visual_items):
                            pivot_item = visual_items[i + 4]
                            if isinstance(pivot_item, QGraphicsEllipseItem):
                                pivot_item.setPos(pos.x() - pivot_item.rect().width()/2, 
                                                 pos.y() - pivot_item.rect().height()/2)

    def _display_paths_in_preview(self):
        """Display motion paths from editor tab in the preview"""
        for item in self.path_visual_items.values():
            if item.scene(): self.mechanism_scene.removeItem(item)
        self.path_visual_items.clear()

        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                path_item = QGraphicsPathItem(path)
                pen = QPen(QColor(0, 200, 0), 4.0)  # Thicker line
                pen.setCosmetic(True)
                path_item.setPen(pen)
                path_item.setZValue(20)  # Higher Z value to appear on top
                self.mechanism_scene.addItem(path_item)
                self.path_visual_items[part_name] = path_item
        self.mechanism_view.zoom_to_fit()

    def _create_4bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of 4-bar linkage using transformation."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})
        key_points = mechanism_data.get("key_points")
        if not to_scene_coords or not key_points or not params: return []

        l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
        p1_coords, p2_coords = key_points.get("ground_pivot_1"), key_points.get("ground_pivot_2")

        if not all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
            logging.warning("Incomplete 4-bar linkage parameters for visualization.")
            return []

        p1, p2 = np.array(p1_coords), np.array(p2_coords)
        # Draw at initial angle (time = 0)
        p3 = p1 + np.array([l2 * math.cos(0), l2 * math.sin(0)])
        d = np.linalg.norm(p2 - p3)
        if not (abs(l3 - l4) <= d <= l3 + l4):
            logging.warning("4-bar linkage cannot be assembled at initial position.")
            return []

        a = (l3**2 - l4**2 + d**2) / (2 * d)
        h = math.sqrt(max(0, l3**2 - a**2))
        p3_p2_unit = (p2 - p3) / d
        midpoint = p3 + a * p3_p2_unit
        p4 = midpoint + h * np.array([-p3_p2_unit[1], p3_p2_unit[0]])

        p1_t, p2_t, p3_t, p4_t = map(to_scene_coords, [p1, p2, p3, p4])

        visual_items = []
        # More colorful mechanism visuals
        link_colors = [QColor("#e74c3c"), QColor("#3498db"), QColor("#2ecc71"), QColor("#9b59b6")]
        link_width = 8

        # Create and add links with different colors
        links = [
            QGraphicsLineItem(QLineF(p1_t, p3_t)),  # Link 1 - red
            QGraphicsLineItem(QLineF(p3_t, p4_t)),  # Link 2 - blue
            QGraphicsLineItem(QLineF(p4_t, p2_t)),  # Link 3 - green
            QGraphicsLineItem(QLineF(p2_t, p1_t))   # Link 4 (ground) - purple
        ]

        for i, link in enumerate(links):
            link_pen = QPen(link_colors[i], link_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            link.setPen(link_pen)
            link.setZValue(10)  # Below paths but above background
            self.mechanism_scene.addItem(link)
            visual_items.append(link)

        # Colorful pivots with gradient effect
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        
        for i, (pos, color) in enumerate(zip(pivot_positions, pivot_colors)):
            # Outer circle for contrast
            outer_ellipse = self.mechanism_scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                QPen(color.darker(150), 2),
                QBrush(color)
            )
            outer_ellipse.setZValue(15)  # Below paths but above links
            visual_items.append(outer_ellipse)
            
            # Inner circle for highlight
            inner_ellipse = self.mechanism_scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )
            inner_ellipse.setZValue(16)  # Highest for mechanism components
            visual_items.append(inner_ellipse)

        # Add coupler point marker (will be updated during animation)
        coupler_color = QColor("#ff0000")  # Red for coupler point
        coupler_marker = self.mechanism_scene.addEllipse(
            p3_t.x() - 6, p3_t.y() - 6, 12, 12,  # Initial position at p3
            QPen(coupler_color.darker(150), 3),
            QBrush(coupler_color)
        )
        coupler_marker.setZValue(20)  # Highest Z value to be visible
        visual_items.append(coupler_marker)

        return visual_items

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """Handle mechanism visualization data"""
        mechanism_id = mechanism_graphics_data.get("mechanism_id")
        mechanism_type = mechanism_graphics_data.get("mechanism_type")
        layer_data = self.mechanism_layers.get(mechanism_id)
        if not layer_data: return

        visual_items = []
        if mechanism_type == "4_bar_linkage":
            visual_items.extend(self._create_4bar_linkage_visuals(mechanism_graphics_data))
        elif mechanism_type == "cam":
            visual_items.extend(self._create_cam_visuals(mechanism_graphics_data))
        elif mechanism_type == "gear":
            visual_items.extend(self._create_gear_visuals(mechanism_graphics_data))

        layer_data["visual_items"] = visual_items

    def _generate_mechanism_visuals_directly(self, mechanism_id: str, mechanism_type: str, params: dict, layer_data: dict):
        """Generate mechanism visuals directly."""
        mechanism_graphics_data = {
            "mechanism_id": mechanism_id,
            "mechanism_type": mechanism_type,
            "params": params,
            **layer_data
        }
        self.handle_mechanism_visuals(mechanism_graphics_data)

    def _convert_json_params_to_internal(self, mechanism_type: str, json_params: dict) -> dict:
        """Convert parameters from JSON format to our internal format"""
        if "4-Bar" in mechanism_type:
            params = {
                "l1": json_params.get('l1'),  # Add missing l1 parameter
                "l2": json_params.get('l2'),
                "l3": json_params.get('l3'),
                "l4": json_params.get('l4'),
            }
            coupler_point = json_params.get("coupler_point", {})
            params["coupler_point_x"] = coupler_point.get("x")
            params["coupler_point_y"] = coupler_point.get("y")
            
            # Debug: log the converted parameters
            logging.info(f"Converted 4-bar params: {params}")
            return params
        elif "Cam" in mechanism_type:
            params = {
                "base_radius": json_params.get("base_radius", 25.0),
                "eccentricity": json_params.get("eccentricity", 10.0),
            }
            logging.info(f"Converted cam params: {params}")
            return params
        elif "Gear" in mechanism_type:
            params = {
                "r1": json_params.get("r1", 30),
                "r2": json_params.get("r2", 50),
            }
            logging.info(f"Converted gear params: {params}")
            return params
        return json_params

    # Animation control methods
    def _on_start_animation(self): 
        """Start the animation timer and IK animation."""
        if self.mechanism_enabled_state:
            # Set up IK system with parts data before starting animation
            if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
                try:
                    # First, ensure IK manager has the necessary data
                    if self.parts_data:
                        # Convert parts_data to format expected by IK manager
                        self.main_window.ik_manager.set_project_parts_data(self.parts_data)
                        logging.info(f"Set project_parts_data in IK manager: {list(self.parts_data.keys())}")
                    
                    # Set skeleton data if available
                    if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                        self.main_window.ik_manager.on_skeleton_data_updated_from_manager(self._initial_skeleton_data_cache)
                        logging.info("Set skeleton data in IK manager")
                    
                    # Generate and set motion paths for mechanism-controlled parts
                    for mech_id, layer_data in self.mechanism_layers.items():
                        if self.mechanism_enabled_state.get(mech_id, False):
                            part_name = layer_data.get("part_name")
                            if part_name and part_name in self.current_editor_items:
                                # Generate full motion path for this mechanism
                                motion_path = self._generate_mechanism_motion_path(layer_data)
                                
                                # Set the part's motion path in the IK manager
                                if motion_path and not motion_path.isEmpty():
                                    self.main_window.ik_manager.update_part_motion_path(part_name, motion_path)
                                    logging.info(f"Set motion path for part '{part_name}' from mechanism {mech_id}")
                                    
                                    # Also try to set up IK for the anchor joint
                                    part_info = self.parts_data.get(part_name)
                                    if part_info and part_info.anchor_joint_id:
                                        # Try to set joint motion if method exists
                                        if hasattr(self.main_window.ik_manager, 'set_joint_motion_path'):
                                            self.main_window.ik_manager.set_joint_motion_path(
                                                part_info.anchor_joint_id, motion_path
                                            )
                                            logging.info(f"Set joint motion path for joint '{part_info.anchor_joint_id}'")
                                        else:
                                            logging.info(f"IK manager doesn't support set_joint_motion_path")
                    
                    # Start IK animation for skeleton integration
                    self.main_window.ik_manager.start_animation()
                    logging.info("Started IK animation for skeleton integration")
                except Exception as e:
                    logging.warning(f"Failed to start IK animation: {e}")
                    # Continue with basic mechanism animation even if IK fails
            
            # Start mechanism animation timer for visuals and path tracing
            self.animation_timer.start(33)  # ~30 FPS
            
            self.play_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.animation_status_label.setText("Animation running")
            logging.info("Started mechanism animation")
        else:
            QMessageBox.warning(self, "Warning", "No mechanisms are enabled for animation.")
    
    def _on_stop_animation(self): 
        """Stop the animation timer and IK animation."""
        self.animation_timer.stop()
        
        # Also stop IK animation for skeleton integration
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                self.main_window.ik_manager.stop_animation()
                logging.info("Stopped IK animation")
            except Exception as e:
                logging.warning(f"Failed to stop IK animation: {e}")
        
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.animation_status_label.setText("Animation stopped")
        logging.info("Stopped mechanism animation")
    
    def _on_reset_animation(self):
        """Reset animation to start position."""
        self.animation_timer.stop()
        self.animation_time = 0
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Reset parts to initial positions
        self._position_parts_at_anchor_joints()
        
        # Reset mechanism visuals to initial state
        for mechanism_id, layer_data in self.mechanism_layers.items():
            self._update_mechanism_visuals_for_animation(mechanism_id, 0, layer_data)
            # Clear mechanism traces
            if mechanism_id in self.mechanism_trace_points:
                self.mechanism_trace_points[mechanism_id].clear()
                self.mechanism_trace_paths[mechanism_id] = QPainterPath()
                if mechanism_id in self.mechanism_trace_items:
                    self.mechanism_trace_items[mechanism_id].setPath(QPainterPath())
        
        # Reset skeleton to initial state if available
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop and reset IK animation
                self.main_window.ik_manager.stop_animation()
                self.main_window.ik_manager.reset_all_ik_systems_and_data()
                logging.info("Reset IK animation and skeleton state")
            except Exception as e:
                if self.debug_mode:
                    logging.warning(f"Failed to reset IK: {e}")
        
        self.animation_status_label.setText("Animation reset")
        logging.info("Reset mechanism animation")
    def _on_layer_selection_changed(self): pass
    def _on_mechanism_enable_toggled(self, state):
        selected = self.mechanism_layers_list.selectedItems()
        if selected:
            mech_id = selected[0].data(Qt.ItemDataRole.UserRole)
            self.mechanism_enabled_state[mech_id] = (state == Qt.CheckState.Checked.value)
    def _create_interactive_handles_for_mechanism(self, mechanism_id, mechanism_type, params): 
        # TODO: Implement interactive parameter handles
        _ = mechanism_id, mechanism_type, params  # Unused parameters
        pass
    def _create_3bar_linkage_visuals(self, mechanism_data): 
        # TODO: Implement 3-bar linkage visuals
        _ = mechanism_data  # Unused parameter
        return []
    def _create_cam_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of cam and follower mechanism."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})
        
        if not to_scene_coords or not params:
            return []
        
        base_radius = params.get("base_radius", 25.0)
        eccentricity = params.get("eccentricity", 10.0)
        
        # Initial cam position (at time=0)
        cam_center_orig = np.array([eccentricity, 0])
        rotation_center_orig = np.array([0, 0])
        initial_follower_y = eccentricity + base_radius
        follower_pos_orig = np.array([0, initial_follower_y])
        
        # Transform to scene coordinates
        cam_center_scene = to_scene_coords(cam_center_orig)
        rotation_center_scene = to_scene_coords(rotation_center_orig)
        follower_scene = to_scene_coords(follower_pos_orig)
        
        visual_items = []
        
        # Create cam body (circle)
        cam_color = QColor("#e74c3c")  # Red
        cam_body = self.mechanism_scene.addEllipse(
            cam_center_scene.x() - base_radius, cam_center_scene.y() - base_radius,
            base_radius * 2, base_radius * 2,
            QPen(cam_color, 4),
            QBrush(cam_color.lighter(160))
        )
        cam_body.setZValue(10)
        visual_items.append(cam_body)
        
        # Create follower (rectangular block)
        follower_color = QColor("#2ecc71")  # Green
        follower_width, follower_height = 20, 10
        follower_body = self.mechanism_scene.addRect(
            follower_scene.x() - follower_width/2, follower_scene.y() - follower_height/2,
            follower_width, follower_height,
            QPen(follower_color, 3),
            QBrush(follower_color.lighter(150))
        )
        follower_body.setZValue(15)
        visual_items.append(follower_body)
        
        # Create rotation center marker
        center_color = QColor("#f39c12")  # Orange
        rotation_marker = self.mechanism_scene.addEllipse(
            rotation_center_scene.x() - 8, rotation_center_scene.y() - 8, 16, 16,
            QPen(center_color.darker(150), 3),
            QBrush(center_color)
        )
        rotation_marker.setZValue(20)
        visual_items.append(rotation_marker)
        
        # Create cam center marker
        cam_center_color = QColor("#3498db")  # Blue
        cam_center_marker = self.mechanism_scene.addEllipse(
            cam_center_scene.x() - 6, cam_center_scene.y() - 6, 12, 12,
            QPen(cam_center_color.darker(150), 2),
            QBrush(cam_center_color)
        )
        cam_center_marker.setZValue(25)
        visual_items.append(cam_center_marker)
        
        return visual_items
    
    def _create_gear_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
        """Create visual representation of gear train mechanism."""
        to_scene_coords = self._get_scene_transform_function(mechanism_data)
        params = mechanism_data.get("params", {})
        
        if not to_scene_coords or not params:
            return []
        
        r1 = params.get("r1", 30)
        r2 = params.get("r2", 50)
        
        # Gear centers in original coordinates
        gear1_center_orig = np.array([-r1, 0])
        gear2_center_orig = np.array([r2, 0])
        
        # Transform to scene coordinates
        gear1_center_scene = to_scene_coords(gear1_center_orig)
        gear2_center_scene = to_scene_coords(gear2_center_orig)
        
        visual_items = []
        
        # Create gear 1 (driver)
        gear1_color = QColor("#3498db")  # Blue
        gear1_body = self.mechanism_scene.addEllipse(
            gear1_center_scene.x() - r1, gear1_center_scene.y() - r1,
            r1 * 2, r1 * 2,
            QPen(gear1_color, 4),
            QBrush(gear1_color.lighter(170))
        )
        gear1_body.setZValue(10)
        visual_items.append(gear1_body)
        
        # Create gear 2 (driven)
        gear2_color = QColor("#2ecc71")  # Green
        gear2_body = self.mechanism_scene.addEllipse(
            gear2_center_scene.x() - r2, gear2_center_scene.y() - r2,
            r2 * 2, r2 * 2,
            QPen(gear2_color, 4),
            QBrush(gear2_color.lighter(170))
        )
        gear2_body.setZValue(10)
        visual_items.append(gear2_body)
        
        # Create rotation indicators (lines that will rotate)
        indicator_color = QColor("#ffffff")  # White lines
        
        # Gear 1 indicator (initially horizontal)
        gear1_indicator = self.mechanism_scene.addLine(
            gear1_center_scene.x(), gear1_center_scene.y(),
            gear1_center_scene.x() + r1, gear1_center_scene.y(),
            QPen(indicator_color, 3)
        )
        gear1_indicator.setZValue(15)
        visual_items.append(gear1_indicator)
        
        # Gear 2 indicator (initially horizontal)
        gear2_indicator = self.mechanism_scene.addLine(
            gear2_center_scene.x(), gear2_center_scene.y(),
            gear2_center_scene.x() + r2, gear2_center_scene.y(),
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
    
    def _create_generic_mechanism_visuals(self, mechanism_data): 
        # TODO: Implement generic mechanism visuals
        _ = mechanism_data  # Unused parameter
        return []
    
    def _init_mechanism_path_trace(self, mechanism_id: str):
        """Initialize path tracing for a mechanism."""
        self.mechanism_trace_points[mechanism_id] = []
        self.mechanism_trace_paths[mechanism_id] = QPainterPath()
        
        # Create visual trace item with thicker, more visible pen
        trace_item = QGraphicsPathItem()
        trace_pen = QPen(QColor("#ff3030"), 6.0)  # Bright red trace path, thicker
        trace_pen.setStyle(Qt.PenStyle.DashLine)  # More visible dash style
        trace_pen.setCosmetic(True)
        trace_item.setPen(trace_pen)
        trace_item.setZValue(25)  # Higher Z to be clearly visible above everything
        self.mechanism_scene.addItem(trace_item)
        self.mechanism_trace_items[mechanism_id] = trace_item
        
        logging.info(f"Initialized path tracing for mechanism {mechanism_id}")
    
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
    
    def _generate_mechanism_motion_path(self, layer_data: dict) -> Optional[QPainterPath]:
        """Generate a complete motion path for a mechanism over one full cycle."""
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})
        
        if mech_type != "4_bar_linkage":
            return None  # Only 4-bar linkages supported for now
        
        motion_path = QPainterPath()
        num_points = 100  # Number of points in the path
        
        try:
            for i in range(num_points + 1):  # +1 to close the path
                # Calculate angle for this point (full rotation)
                angle = (i / num_points) * 2 * math.pi
                
                # Calculate mechanism output position
                output_pos = self._calculate_mechanism_output(mech_type, params, angle, layer_data)
                
                if output_pos:
                    if i == 0:
                        motion_path.moveTo(output_pos)
                    else:
                        motion_path.lineTo(output_pos)
                else:
                    # If we can't calculate a position, fall back to empty path
                    return QPainterPath()
            
            return motion_path
            
        except Exception as e:
            if self.debug_mode:
                logging.warning(f"Failed to generate mechanism motion path: {e}")
            return QPainterPath()

    def _debug_data_consistency_check(self, mechanism_id: str, time: float, layer_data: dict, output_pos: QPointF):
        """DEBUG: Check consistency between _calculate_mechanism_output and visual update data."""
        # Only run this check occasionally to avoid performance impact
        if not hasattr(self, '_debug_check_counter'):
            self._debug_check_counter = 0
        self._debug_check_counter += 1
        
        # Run check every 30 frames (about once per second at 30fps)
        if self._debug_check_counter % 30 != 0:
            return
            
        try:
            full_sim_data = layer_data.get("full_simulation_data", {})
            
            if "joint_positions" in full_sim_data and "coupler_path" in full_sim_data:
                joint_positions = full_sim_data["joint_positions"]
                coupler_path = np.array(full_sim_data["coupler_path"])
                
                if "p1_positions" in joint_positions and len(coupler_path) > 0:
                    # Calculate frame index using same logic as both functions
                    num_frames = len(joint_positions["p1_positions"])
                    num_coupler_points = len(coupler_path)
                    normalized_time = time / (2 * math.pi)
                    
                    joint_frame_index = int(normalized_time * (num_frames - 1))
                    joint_frame_index = max(0, min(joint_frame_index, num_frames - 1))
                    
                    coupler_frame_index = int(normalized_time * (num_coupler_points - 1))
                    coupler_frame_index = max(0, min(coupler_frame_index, num_coupler_points - 1))
                    
                    # Get the coupler point from dataset
                    coupler_point_orig = coupler_path[coupler_frame_index]
                    
                    # Apply same transform as output calculation
                    to_scene_coords = self._get_scene_transform_function(layer_data)
                    if to_scene_coords:
                        expected_output = to_scene_coords(coupler_point_orig)
                        
                        # Compare with actual output position
                        distance = math.sqrt((output_pos.x() - expected_output.x())**2 + 
                                           (output_pos.y() - expected_output.y())**2)
                        
                        logging.info(f"[DEBUG] Data consistency check for {mechanism_id}:")
                        logging.info(f"[DEBUG]   Time: {time:.3f}, joint_frame: {joint_frame_index}/{num_frames-1}, coupler_frame: {coupler_frame_index}/{num_coupler_points-1}")
                        logging.info(f"[DEBUG]   Expected output: ({expected_output.x():.2f}, {expected_output.y():.2f})")
                        logging.info(f"[DEBUG]   Actual output: ({output_pos.x():.2f}, {output_pos.y():.2f})")
                        logging.info(f"[DEBUG]   Distance difference: {distance:.2f}")
                        
                        if distance > 5.0:  # Threshold for "concerning" difference
                            logging.warning(f"[DEBUG] Large discrepancy detected in {mechanism_id}: {distance:.2f} pixels")
                        else:
                            logging.info(f"[DEBUG] Data consistency OK for {mechanism_id}")
                    
        except Exception as e:
            logging.warning(f"[DEBUG] Error in consistency check: {e}")

    # ... other methods from the original file can be added here if needed

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
