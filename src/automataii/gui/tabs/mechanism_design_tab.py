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
    
    def _update_parts_from_skeleton(self, skeleton_data: Dict):
        """Update part positions based on skeleton joint movements (like in editor tab)."""
        joints_dict = skeleton_data.get("joints", {})
        
        for part_name, part_item in self.current_editor_items.items():
            part_info = self.parts_data.get(part_name)
            if part_info and part_info.anchor_joint_id in joints_dict:
                joint_data = joints_dict[part_info.anchor_joint_id]
                
                # Check if this part is controlled by a mechanism
                is_mechanism_controlled = self._is_part_mechanism_controlled(part_name)
                
                # If not controlled by mechanism, update from skeleton
                if not is_mechanism_controlled:
                    if "scene_position" in joint_data:
                        scene_pos = joint_data["scene_position"]
                        if isinstance(scene_pos, (list, tuple)) and len(scene_pos) >= 2:
                            scene_pos = QPointF(scene_pos[0], scene_pos[1])
                        part_item.set_scene_position_from_anchor(scene_pos)
                    
                    if "world_rotation_degrees" in joint_data:
                        rotation = float(joint_data["world_rotation_degrees"])
                        part_item.setRotation(rotation)
    
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
            "4-Bar Linkage": "4_bar_linkage", "Cam & Follower": "cam",
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
            "4-Bar Linkage": "4_bar_linkage", "Cam & Follower": "cam",
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
        }
        
        # Verify coupler point connection to skeleton joint
        self._verify_coupler_joint_connection(layer_data)
        
        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, params, layer_data)
        
        # Add debug visualization for transform comparison
        self._add_transform_comparison_visuals(layer_data)
        
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
        """Verify that the coupler point is properly connected to the target skeleton joint."""
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
            
            # Calculate the mechanism's initial coupler point position
            initial_coupler_pos = self._calculate_mechanism_output(
                layer_data["type"], layer_data["params"], 0.0, layer_data
            )
            
            if initial_coupler_pos:
                initial_pos_np = np.array([initial_coupler_pos.x(), initial_coupler_pos.y()])
                distance = np.linalg.norm(initial_pos_np - target_joint_pos)
                
                if distance > 50:  # Threshold for "close enough" in scene coordinates
                    logging.warning(f"Coupler point far from target joint {anchor_joint_id}: distance = {distance:.1f}")
                    logging.warning(f"Target joint: {target_joint_pos}, Coupler: {initial_pos_np}")
                else:
                    logging.info(f"Coupler point connected to joint {anchor_joint_id}, distance = {distance:.1f}")

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
        
        This function ensures consistent transformation between dialog preview and main tab
        by using the same logic as the recommendation dialog.
        """
        transform_params = layer_data.get("transform_params")
        vis_params = layer_data.get("visualization_params")
        target_path = layer_data.get("generated_path")

        if not all([transform_params, vis_params, target_path]):
            return None

        user_path_np = self._qpainterpath_to_numpy(target_path)
        if user_path_np is None:
            return None

        # Use the same transformation logic as the recommendation dialog
        mech_orig_center_np = np.array(vis_params["center"])
        mech_orig_scale = vis_params["scale"]
        angle = transform_params["rotation"]

        if np.isclose(mech_orig_scale, 0):
            return None

        rotation_matrix = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        
        # Calculate target bounds to match dialog preview positioning
        target_center_np = np.mean(user_path_np, axis=0)
        target_centered = user_path_np - target_center_np
        target_extent = np.max(np.abs(target_centered))
        
        # Calculate scale to match target path size, similar to dialog preview
        if not np.isclose(target_extent, 0):
            final_scale = target_extent / mech_orig_scale
        else:
            final_scale = 1.0

        def to_scene_coords(p_orig: np.ndarray) -> QPointF:
            # Step 1: Center and normalize the original mechanism point
            p_centered = p_orig - mech_orig_center_np
            
            # Step 2: Apply rotation from path alignment
            p_rotated = p_centered @ rotation_matrix.T
            
            # Step 3: Scale to match target path size
            p_scaled = p_rotated * final_scale
            
            # Step 4: Translate to target path center
            p_final = p_scaled + target_center_np
            
            # Debug logging for transform verification
            if self.debug_mode and hasattr(self, '_transform_debug_count'):
                self._transform_debug_count = getattr(self, '_transform_debug_count', 0) + 1
                if self._transform_debug_count <= 5:  # Log first 5 transforms only
                    logging.info(f"Transform debug {self._transform_debug_count}:")
                    logging.info(f"  Original point: {p_orig}")
                    logging.info(f"  Mech center: {mech_orig_center_np}, scale: {mech_orig_scale}")
                    logging.info(f"  Target center: {target_center_np}, extent: {target_extent}")
                    logging.info(f"  Final scale: {final_scale}, angle: {angle}")
                    logging.info(f"  Final point: {p_final}")
            
            return QPointF(p_final[0], p_final[1])
        
        # Initialize debug counter
        if self.debug_mode:
            self._transform_debug_count = 0
            
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
        """Calculates mechanism output point in original space, then transforms to scene space."""
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
            # Debug: Check if transform produces reasonable coordinates
            if self.debug_mode and (abs(scene_point.x()) > 10000 or abs(scene_point.y()) > 10000):
                logging.warning(f"Transform produced extreme coordinates: {scene_point.x():.1f}, {scene_point.y():.1f}")
                logging.warning(f"Original point: {output_point_orig}")
                logging.warning(f"Transform params: {layer_data.get('transform_params')}")
                logging.warning(f"Visualization params: {layer_data.get('visualization_params')}")
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
                    
                    # Don't move parts directly - let IK system handle it
                    # Store the target position for IK system
                    pass
                    
                    # Update mechanism visuals
                    try:
                        self._update_mechanism_visuals_for_animation(mechanism_id, self.animation_time, layer_data)
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
        
        # This will be handled in _on_start_animation instead of every frame
        pass

    def _update_mechanism_visuals_for_animation(self, mechanism_id: str, time: float, layer_data: dict):
        """Update mechanism visual elements during animation."""
        try:
            mech_type = layer_data.get("type")
            visual_items = layer_data.get("visual_items", [])
            
            if mech_type == "4_bar_linkage" and len(visual_items) >= 8:  # 4 links + 4 pivots
                # Update 4-bar linkage visuals
                to_scene_coords = self._get_scene_transform_function(layer_data)
                params = layer_data.get("params", {})
                key_points = layer_data.get("key_points")
                
                if to_scene_coords and key_points and params:
                    l2, l3, l4 = params.get("l2"), params.get("l3"), params.get("l4")
                    p1_coords, p2_coords = key_points.get("ground_pivot_1"), key_points.get("ground_pivot_2")
                    
                    if all([l2 is not None, l3 is not None, l4 is not None, p1_coords, p2_coords]):
                        p1, p2 = np.array(p1_coords), np.array(p2_coords)
                        
                        # Calculate current positions based on animation time
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
        except Exception as e:
            logging.warning(f"Error updating mechanism visuals for {mechanism_id}: {e}")

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
                "l2": json_params.get('l2'),
                "l3": json_params.get('l3'),
                "l4": json_params.get('l4'),
            }
            coupler_point = json_params.get("coupler_point", {})
            params["coupler_point_x"] = coupler_point.get("x")
            params["coupler_point_y"] = coupler_point.get("y")
            return params
        return json_params

    # Animation control methods
    def _on_start_animation(self): 
        """Start the animation timer and IK animation."""
        if self.mechanism_enabled_state:
            # Set up motion paths for IK system before starting animation
            if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
                try:
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
                    
                    # Start IK animation for skeleton integration
                    self.main_window.ik_manager.start_animation()
                    logging.info("Started IK animation for skeleton integration")
                except Exception as e:
                    logging.warning(f"Failed to start IK animation: {e}")
            
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
        pass
    def _create_3bar_linkage_visuals(self, mechanism_data): 
        # TODO: Implement 3-bar linkage visuals
        _ = mechanism_data  # Unused parameter
        return []
    def _create_cam_visuals(self, mechanism_data): 
        # TODO: Implement cam mechanism visuals
        _ = mechanism_data  # Unused parameter
        return []
    def _create_generic_mechanism_visuals(self, mechanism_data): 
        # TODO: Implement generic mechanism visuals
        _ = mechanism_data  # Unused parameter
        return []
    
    def _init_mechanism_path_trace(self, mechanism_id: str):
        """Initialize path tracing for a mechanism."""
        self.mechanism_trace_points[mechanism_id] = []
        self.mechanism_trace_paths[mechanism_id] = QPainterPath()
        
        # Create visual trace item
        trace_item = QGraphicsPathItem()
        trace_pen = QPen(QColor("#ff6b6b"), 3.0)  # Red trace path
        trace_pen.setStyle(Qt.PenStyle.DotLine)
        trace_pen.setCosmetic(True)
        trace_item.setPen(trace_pen)
        trace_item.setZValue(18)  # Above mechanisms but below target paths
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

    # ... other methods from the original file can be added here if needed

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
