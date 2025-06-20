import logging
from typing import Callable, Optional, Dict, Any, List
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
    QDialog,
    QGraphicsItem,
    QScrollArea,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QStyle,
)
from PyQt6.QtCore import pyqtSignal, QPointF, Qt, QTimer, QLineF
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QPolygonF, QFont, QIcon, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from automataii.kinematics.ik_manager import IKManager
from automataii.utils.paths import get_project_root, resolve_path

from automataii.gui.views.editor_view import EditorView
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsPolygonItem
from automataii.core.models import PartInfo
from automataii.kinematics.mechanism import (
    MechanismCandidate,
)
from automataii.kinematics.motion_database import MotionDatabase
from automataii.kinematics.mechanism_simulator import MechanismSimulator
from automataii.gui.graphics_items.part_item import CharacterPartItem

from automataii.gui.dialogs.recommendation_dialog import (
    MechanismRecommendationDialog,
    qpainterpath_to_numpy_array,
)
from automataii.gui.tabs.mechanism_design_utils import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
    convert_json_params_to_internal
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
        self.part_enabled_state: Dict[str, bool] = {}  # Track which parts are enabled for mechanism generation

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

        # Visualization items
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
        self.parametric_edit_btn: Optional[QPushButton] = None

        self._setup_ui()
        self._connect_signals()
        self._connect_to_ik_manager()

        # Load generated paths
        generated_paths_file = resolve_path("automataii/kinematics/generated_mechanism_paths.json")
        # Initialize with empty QPainterPath since no user path is drawn yet
        empty_path = QPainterPath()
        self.recommendation_dialog = MechanismRecommendationDialog(empty_path, generated_paths_file, parent=self)
        self.recommendation_dialog.mechanism_selected.connect(self.handle_mechanism_visuals)


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
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(15)

        # 1. Parts for Mechanism Generation
        layers_group = QGroupBox("1 Parts for Mechanism Generation")
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
        self.mechanism_layers_list.setToolTip("Parts list - gray items have no motion paths")
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
        """)
        layers_layout.addWidget(self.mechanism_layers_list)

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

        self.recommendation_btn = QPushButton("Get Mechanism")
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

    def _connect_to_ik_manager(self):
        """Connect to IK manager signals for skeleton animation."""
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Connect to skeleton pose updates
                self.main_window.ik_manager.skeleton_pose_updated.connect(self.on_skeleton_updated)
            except Exception as e:
                logging.warning(f"Failed to connect to IK manager: {e}")

    def set_path_data_from_editor(self, path_data: Dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        self.path_data = path_data.copy()

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
        self._update_mechanism_layers_list()

    def set_parts_data(self, parts_data: Dict[str, PartInfo]):
        """Set parts data (synchronized with editor tab)"""
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
                    item.setZValue(1)  # Parts above skeleton (Z=0) but below mechanisms

                    # All parts display normally without any highlighting
                    item.setOpacity(1.0)

                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item
            self._position_parts_at_anchor_joints()
            self.mechanism_view.zoom_to_fit()

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

    def cache_initial_skeleton(self, skeleton_data_dict: Optional[Dict]):
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

    def on_skeleton_updated(self, skeleton_data: Optional[Dict]):
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

        except Exception as e:
            # Don't let skeleton errors crash the mechanism animation
            pass

    def _update_parts_from_skeleton(self, skeleton_data: Dict):
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


    def _is_part_mechanism_controlled(self, part_name: str) -> bool:
        """Check if a part is currently controlled by an active mechanism."""
        for mech_id, layer_data in self.mechanism_layers.items():
            if (self.mechanism_enabled_state.get(mech_id, False) and
                layer_data.get("part_name") == part_name):
                return True
        return False

    def _ensure_skeleton_visualization(self, skeleton_data: Dict):
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
                        self.mechanism_view.skeleton_graphics_item.setZValue(0)
            else:
                # Skeleton exists, just update animation
                if skeleton_item and hasattr(skeleton_item, 'set_animated_pose'):
                    # Convert skeleton_data to the format expected by set_animated_pose
                    pose_data = self._convert_skeleton_data_for_animation(skeleton_data)
                    if pose_data:
                        skeleton_item.set_animated_pose(pose_data)

        except Exception as e:
            pass

    def _format_skeleton_for_visualization(self, skeleton_data: Dict):
        """Format skeleton data for visualize_skeleton method like editor tab does."""
        from PyQt6.QtCore import QPointF

        skeleton_for_view = []
        hierarchy: Dict[str, List[str]] = {}

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

    def _convert_skeleton_data_for_animation(self, skeleton_data: Dict):
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
        if skeleton_item and skeleton_item.scene() == self.mechanism_scene:
            self.mechanism_scene.removeItem(skeleton_item)

        # Clear the scene (this will delete all other items)
        self.mechanism_scene.clear()

        # Re-add skeleton item if it was preserved
        if skeleton_item:
            try:
                # Test if skeleton item is still valid
                _ = skeleton_item.boundingRect()
                self.mechanism_scene.addItem(skeleton_item)
                # Set proper Z-order: skeleton at bottom (Z=0)
                skeleton_item.setZValue(0)
            except RuntimeError:
                # Skeleton was already deleted, clear the reference
                if hasattr(self.mechanism_view, 'skeleton_graphics_item'):
                    self.mechanism_view.skeleton_graphics_item = None

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

    def _get_all_end_effector_parts(self) -> List[str]:
        """Get list of all parts that are end effectors (have terminal joints)."""
        try:
            from automataii.animate.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}

        end_effector_parts = []

        # Parts that control end effectors
        end_effector_candidates = [
            "left_arm_lower",   # controls left_hand
            "right_arm_lower",  # controls right_hand
            "left_leg_lower",   # controls left_foot
            "right_leg_lower",  # controls right_foot
            "head",             # controls via neck
        ]

        for part_name in end_effector_candidates:
            if part_name in BODY_PARTS:
                end_effector_parts.append(part_name)


        return end_effector_parts

    def _is_end_effector_part(self, part_name: str) -> bool:
        """Check if a part is an end effector."""
        return part_name in self._get_all_end_effector_parts()

    def _get_current_skeleton_data_with_mechanism_override(self, mechanism_joint_updates: Dict[str, QPointF]) -> Dict[str, tuple]:
        """Get current skeleton data and override mechanism-controlled joints."""
        # Start with the initial skeleton data as base
        base_skeleton_data = {}

        if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
            # Use cached initial skeleton data as base
            joints_dict = self._initial_skeleton_data_cache.get("joints", {})
            for joint_id, joint_info in joints_dict.items():
                if isinstance(joint_info, dict):
                    position = joint_info.get("position", [0, 0])
                    if len(position) >= 2:
                        base_skeleton_data[joint_id] = (float(position[0]), float(position[1]))

        # Get standardized joint IDs for the base skeleton
        if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
            joints_dict = self._initial_skeleton_data_cache.get("joints", {})
            joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
            for orig_name, std_name in joint_map.items():
                if orig_name in joints_dict:
                    joint_info = joints_dict[orig_name]
                    if isinstance(joint_info, dict):
                        position = joint_info.get("position", [0, 0])
                        if len(position) >= 2:
                            base_skeleton_data[std_name] = (float(position[0]), float(position[1]))

        # Override with mechanism-controlled joint positions AND compute IK for connected joints
        for joint_id, mechanism_pos in mechanism_joint_updates.items():
            base_skeleton_data[joint_id] = (mechanism_pos.x(), mechanism_pos.y())

            # Compute IK for the entire limb chain to make all parts follow
            self._compute_ik_chain_for_mechanism_joint(joint_id, mechanism_pos, base_skeleton_data)


        return base_skeleton_data

    def _compute_ik_chain_for_mechanism_joint(self, target_joint_id: str, target_pos: QPointF, skeleton_data: Dict[str, tuple]):
        """Compute IK for the entire limb chain when a target joint is controlled by mechanism."""
        import math

        # Define limb chains and their lengths
        LIMB_CHAINS = {
            # Left arm: shoulder → elbow → hand
            "left_hand": {
                "joints": ["left_shoulder", "left_elbow", "left_hand"],
                "std_joints": ["left_shoulder_7", "left_elbow_8", "left_hand_9"],
                "lengths": [100, 80]  # shoulder-elbow, elbow-hand
            },
            "left_hand_9": {  # Handle standardized ID too
                "joints": ["left_shoulder", "left_elbow", "left_hand"],
                "std_joints": ["left_shoulder_7", "left_elbow_8", "left_hand_9"],
                "lengths": [100, 80]
            },

            # Right arm: shoulder → elbow → hand
            "right_hand": {
                "joints": ["right_shoulder", "right_elbow", "right_hand"],
                "std_joints": ["right_shoulder_4", "right_elbow_5", "right_hand_6"],
                "lengths": [100, 80]
            },
            "right_hand_6": {
                "joints": ["right_shoulder", "right_elbow", "right_hand"],
                "std_joints": ["right_shoulder_4", "right_elbow_5", "right_hand_6"],
                "lengths": [100, 80]
            },

            # Left leg: hip → knee → foot
            "left_foot": {
                "joints": ["left_hip", "left_knee", "left_foot"],
                "std_joints": ["left_hip_13", "left_knee_14", "left_foot_15"],
                "lengths": [120, 100]
            },
            "left_foot_15": {
                "joints": ["left_hip", "left_knee", "left_foot"],
                "std_joints": ["left_hip_13", "left_knee_14", "left_foot_15"],
                "lengths": [120, 100]
            },

            # Right leg: hip → knee → foot
            "right_foot": {
                "joints": ["right_hip", "right_knee", "right_foot"],
                "std_joints": ["right_hip_10", "right_knee_11", "right_foot_12"],
                "lengths": [120, 100]
            },
            "right_foot_12": {
                "joints": ["right_hip", "right_knee", "right_foot"],
                "std_joints": ["right_hip_10", "right_knee_11", "right_foot_12"],
                "lengths": [120, 100]
            }
        }

        chain_info = LIMB_CHAINS.get(target_joint_id)
        if not chain_info:
            return

        std_joints = chain_info["std_joints"]
        lengths = chain_info["lengths"]

        if len(std_joints) != 3 or len(lengths) != 2:
            return

        try:
            # Get positions: root, middle, target
            root_joint_id = std_joints[0]
            middle_joint_id = std_joints[1]
            target_joint_id = std_joints[2]

            # Root position (fixed - shoulder/hip)
            root_pos = skeleton_data.get(root_joint_id, (0, 0))
            root_x, root_y = root_pos[0], root_pos[1]

            # Target position (controlled by mechanism)
            target_x, target_y = target_pos.x(), target_pos.y()

            # 2-bone IK calculation
            l1, l2 = lengths[0], lengths[1]  # root-middle, middle-target lengths

            # Distance from root to target
            dx = target_x - root_x
            dy = target_y - root_y
            distance = math.sqrt(dx*dx + dy*dy)

            # Clamp distance to reachable range
            max_reach = l1 + l2
            min_reach = abs(l1 - l2)
            distance = max(min_reach, min(distance, max_reach))

            # Use law of cosines to find elbow angle
            cos_angle = (l1*l1 + l2*l2 - distance*distance) / (2 * l1 * l2)
            cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
            # elbow_angle = math.acos(cos_angle)

            # Calculate shoulder angle
            cos_shoulder = (l1*l1 + distance*distance - l2*l2) / (2 * l1 * distance)
            cos_shoulder = max(-1, min(1, cos_shoulder))
            shoulder_to_target_angle = math.atan2(dy, dx)
            shoulder_angle = shoulder_to_target_angle - math.acos(cos_shoulder)

            # Calculate middle joint (elbow/knee) position
            middle_x = root_x + l1 * math.cos(shoulder_angle)
            middle_y = root_y + l1 * math.sin(shoulder_angle)

            # Update skeleton data with computed positions
            skeleton_data[middle_joint_id] = (middle_x, middle_y)
            skeleton_data[target_joint_id] = (target_x, target_y)  # Ensure target is set


        except Exception as e:
            pass

    def _force_parts_to_follow_mechanism(self, mechanism_outputs: Dict[str, QPointF]):
        """Smoothly animate parts to follow mechanism outputs (prevent blinking)."""
        if not mechanism_outputs:
            return

        for part_name, mechanism_pos in mechanism_outputs.items():
            # Find the part item
            part_item = self.current_editor_items.get(part_name)
            if not part_item:
                continue

            # Get part info to understand anchor joint
            part_info = self.parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            try:
                # SMOOTH ANIMATION: Use interpolation instead of instant teleport
                current_pos = part_item.pos()

                # Calculate distance for smooth movement
                distance_vector = mechanism_pos - current_pos
                distance = (distance_vector.x() ** 2 + distance_vector.y() ** 2) ** 0.5

                if distance > 2.0:  # Only move if significant difference
                    # Interpolate for smooth movement (adjust factor for speed)
                    interpolation_factor = min(0.25, 2.0 / distance)  # Adaptive smooth movement
                    new_pos = current_pos + distance_vector * interpolation_factor

                    # Use the interpolated position for smooth animation
                    part_item.set_scene_position_from_anchor(new_pos)


            except Exception as e:
                pass

    def _force_parts_to_mechanism_positions_immediately(self, mechanism_outputs: Dict[str, QPointF]):
        """CRITICAL: Force parts to mechanism positions immediately (like editor tab does)."""
        if not mechanism_outputs:
            return

        for part_name, mechanism_pos in mechanism_outputs.items():
            part_item = self.current_editor_items.get(part_name)
            if not part_item:
                continue

            part_info = self.parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            try:
                # IMMEDIATE POSITION UPDATE (like editor tab)
                old_pos = part_item.pos()
                part_item.set_scene_position_from_anchor(mechanism_pos)


                # Force immediate visual update
                part_item.update()

            except Exception as e:
                logging.error(f"[CRITICAL] Failed to immediately move part '{part_name}' to mechanism position: {e}")

    def _align_skeleton_to_parts_immediately(self, mechanism_outputs: Dict[str, QPointF]):
        """Force skeleton joints to align with parts immediately."""
        if not mechanism_outputs or not hasattr(self.mechanism_view, 'skeleton_graphics_item'):
            return

        skeleton_item = self.mechanism_view.skeleton_graphics_item
        if not skeleton_item or not hasattr(skeleton_item, '_joint_items'):
            return

        try:
            # Update skeleton joint positions to match part positions
            for part_name, mechanism_pos in mechanism_outputs.items():
                part_info = self.parts_data.get(part_name)
                if not part_info or not part_info.anchor_joint_id:
                    continue

                anchor_joint_id = part_info.anchor_joint_id

                # Find standardized joint ID
                std_joint_id = None
                if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                    joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
                    for orig_name, std_id in joint_map.items():
                        if orig_name == anchor_joint_id:
                            std_joint_id = std_id
                            break

                # Update skeleton joint position
                if std_joint_id and std_joint_id in skeleton_item._joint_items:
                    joint_item = skeleton_item._joint_items[std_joint_id]
                    joint_item.setPos(mechanism_pos)

                    # Update cached position in skeleton data
                    for cached_joint in skeleton_item._joints_data_cache:
                        if cached_joint["id"] == std_joint_id:
                            cached_joint["position"] = mechanism_pos
                            break


            # Force skeleton bone updates
            if hasattr(skeleton_item, '_update_existing_bone_positions'):
                skeleton_item._update_existing_bone_positions()

        except Exception as e:
            logging.error(f"[CRITICAL] Failed to align skeleton to parts: {e}")

    def _update_parts_from_mechanism_directly(self, mechanism_outputs: Dict[str, QPointF]):
        """CRITICAL: Update parts directly from mechanism outputs like editor tab does."""
        if not mechanism_outputs or not self.current_editor_items:
            return

        # Create joint data structure similar to EditorView.update_visuals_from_animation_data
        joint_data = {}

        # Use anchor joint positions, not end effector positions
        # The mechanism calculates end effector positions, but parts are positioned at their anchor joints
        for part_name, mechanism_pos in mechanism_outputs.items():
            part_info = self.parts_data.get(part_name)
            if not part_info or not part_info.anchor_joint_id:
                continue

            # Use the ANCHOR JOINT position, not the mechanism output position
            # The mechanism output is for end effector (e.g., left_hand) but part is anchored at left_elbow
            anchor_joint_id = part_info.anchor_joint_id

            # Find standardized joint ID for the ANCHOR JOINT
            std_joint_id = None
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
                for orig_name, std_id in joint_map.items():
                    if orig_name == anchor_joint_id:
                        std_joint_id = std_id
                        break

            if std_joint_id:
                # Get the current skeleton joint position (from IK calculation)
                # This should be the anchor joint position, not the mechanism output
                anchor_pos = mechanism_pos  # Temporary: use mechanism pos until IK provides anchor pos

                # For now, we'll use the mechanism position as anchor position
                # This is not ideal but will move the part toward the mechanism

                # Create joint transform data like EditorView expects
                joint_data[std_joint_id] = {
                    "scene_position": anchor_pos,
                    "world_rotation_degrees": 0.0  # Start with 0 rotation
                }


        # Update parts using the same logic as EditorView
        for part_item in self.current_editor_items.values():
            if not isinstance(part_item, CharacterPartItem):
                continue

            original_anchor_joint_name = part_item.anchor_joint_id
            if not original_anchor_joint_name:
                continue

            # Find standardized joint ID (same as EditorView)
            standardized_anchor_joint_id = None
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
                standardized_anchor_joint_id = joint_map.get(original_anchor_joint_name)

            if not standardized_anchor_joint_id or standardized_anchor_joint_id not in joint_data:
                continue

            joint_transform_data = joint_data[standardized_anchor_joint_id]
            target_joint_scene_pos = joint_transform_data.get("scene_position")
            target_part_world_rotation = joint_transform_data.get("world_rotation_degrees", part_item.rotation())

            if not isinstance(target_joint_scene_pos, QPointF):
                continue

            # Apply the calculated world rotation and position (exactly like EditorView)
            part_item.setRotation(float(target_part_world_rotation))
            part_item.set_scene_position_from_anchor(target_joint_scene_pos)


        # Force scene update
        if hasattr(self.mechanism_view, 'scene') and self.mechanism_view.scene():
            self.mechanism_view.scene().update()

    def _recreate_skeleton_visualization(self, skeleton_data: Dict):
        """Recreate skeleton visualization when the graphics item was deleted."""
        # Use the new ensure method instead
        self._ensure_skeleton_visualization(skeleton_data)

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

        except Exception as e:
            pass
            return False

    def _register_mechanism_controller(self, mech_id: str, layer_data: dict, joint_id: str):
        """Register a mechanism as a controller for a specific joint with enhanced IK integration."""
        try:
            # Create a callback function that calculates mechanism output for the joint
            def mechanism_joint_callback(time: float) -> Optional[QPointF]:
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

        except Exception as e:
            pass

    def _update_ik_with_mechanism_output(self, mechanism_outputs: Dict[str, QPointF]):
        """Update IK system with current mechanism outputs for real-time animation."""
        if not hasattr(self.main_window, 'ik_manager') or not self.main_window.ik_manager:
            return

        try:
            # Update joint positions in IK system based on mechanism outputs
            for part_name, output_pos in mechanism_outputs.items():
                if part_name in self.parts_data:
                    part_info = self.parts_data[part_name]
                    if part_info.anchor_joint_id:
                        # Use the new mechanism position target system
                        self.main_window.ik_manager.set_mechanism_position_target(
                            part_info.anchor_joint_id, output_pos
                        )

        except Exception as e:
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


            except Exception as e:
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

        import os
        from automataii.utils.paths import get_project_root
        generated_paths_file = os.path.join(get_project_root(), "src", "automataii", "kinematics", "generated_mechanism_paths.json")

        if not os.path.exists(generated_paths_file):
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

    def _generate_mechanism_from_candidate(self, candidate_data: Dict[str, Any]):
        """Generates a mechanism layer and visuals from a selected candidate."""
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
            "reverse_direction": False,  # Can be set to True to reverse mechanism animation direction
        }


        # Verify and adjust coupler point connection to skeleton joint
        self._verify_coupler_joint_connection(layer_data)
        self._adjust_mechanism_to_target_joint(layer_data)

        self._add_mechanism_layer(layer_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, params, layer_data)

        # Log mechanism attachment information
        skeleton_attachment = layer_data.get("skeleton_attachment", {})
        mechanism_layout = layer_data.get("mechanism_layout", {})
        if skeleton_attachment:
            attachment_point = skeleton_attachment.get("attachment_point", "unknown")
            attachment_desc = skeleton_attachment.get("description", "")

        if mechanism_layout:
            layout_desc = mechanism_layout.get("description", "")
            coord_system = mechanism_layout.get("coordinate_system", {})

        # Select the newly added mechanism in the list
        for i in range(self.mechanism_layers_list.count()):
            item = self.mechanism_layers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == mechanism_id:
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
        """Add a mechanism layer to the layers list"""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data
        item = QListWidgetItem(layer_name)
        item.setData(Qt.ItemDataRole.UserRole, mechanism_id)
        self.mechanism_layers_list.addItem(item)
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)

        # Initialize path tracing for this mechanism
        self._init_mechanism_path_trace(mechanism_id)

    def _qpainterpath_to_numpy(self, path: QPainterPath, num_points: int = 100) -> Optional[np.ndarray]:
        """Converts a QPainterPath to a numpy array of points."""
        return qpainterpath_to_numpy_array(path, num_points)

    def _get_scene_transform_function(self, layer_data: dict) -> Optional[Callable]:
        """
        Creates a function to transform points from mechanism's original space to scene space.
        Uses the EXACT same transformation parameters as the recommendation dialog for perfect alignment.
        """
        # Get the transformation parameters computed by recommendation dialog
        transform_params = layer_data.get("transform_params")
        if not transform_params:
            return None

        # Extract transformation parameters (same as recommendation dialog)
        center = np.array(transform_params["center"])
        scale = transform_params["scale"]
        rotation_angle = transform_params["rotation"]

        if np.isclose(scale, 0):
            return None

        # Create rotation matrix
        rotation_matrix = np.array([
            [np.cos(rotation_angle), -np.sin(rotation_angle)],
            [np.sin(rotation_angle), np.cos(rotation_angle)]
        ])

        def to_scene_coords(p_orig: np.ndarray) -> QPointF:
            """
            Apply the EXACT same transformation as align_and_compare_paths:
            1. Center the point (subtract mechanism center)
            2. Scale down to normalized space
            3. Apply rotation
            4. Result is in the same space as user_path_aligned_np
            """
            # Apply the same transformation as align_and_compare_paths
            p_centered = p_orig - center                    # Center
            p_scaled = p_centered / scale                   # Scale to normalized space
            p_rotated = p_scaled @ rotation_matrix.T        # Apply rotation

            # The result is now in the same coordinate system as the user path
            # We need to get the user path in scene coordinates
            target_path = layer_data.get("generated_path")
            if target_path:
                user_path_np = utils_qpainterpath_to_numpy_array(target_path)
                if user_path_np is not None and len(user_path_np) > 0:
                    # Map normalized coordinates to actual user path space
                    user_center = np.mean(user_path_np, axis=0)
                    user_bbox = np.max(user_path_np, axis=0) - np.min(user_path_np, axis=0)
                    user_scale = np.max(user_bbox) / 2.0  # Same scaling as normalize

                    # Transform from normalized space to user path space
                    final_point = p_rotated * user_scale + user_center
                    return QPointF(final_point[0], final_point[1])

            # Fallback: return normalized coordinates scaled up
            return QPointF(p_rotated[0] * 100, p_rotated[1] * 100)

        return to_scene_coords


    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, layer_data: dict) -> Optional[QPointF]:
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
                    frame_index = int((time / (2 * math.pi)) * (num_frames - 1)) % num_frames
                    follower_y = follower_positions[frame_index]
                    follower_pos_orig = np.array([0, follower_y])

                    scene_point = to_scene_coords(follower_pos_orig)
                    return scene_point

            # Fallback to manual calculation if no simulation data
            params = layer_data.get("params", {})
            base_radius = params.get("base_radius", 25.0)
            eccentricity = params.get("eccentricity", 10.0)

            if to_scene_coords:
                angle = time
                rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                cam_center_orig = rotation_matrix @ np.array([eccentricity, 0])
                follower_y = cam_center_orig[1] + base_radius
                follower_pos_orig = np.array([0, follower_y])

                scene_point = to_scene_coords(follower_pos_orig)
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
                    frame_index = int((time / (2 * np.pi)) * (num_frames - 1)) % num_frames
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
                    gear1_center = np.array([-r1, 0])  # Default

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
                    frame_index = int((time / (2 * np.pi)) * (num_frames - 1)) % num_frames
                    frame_index = max(0, min(frame_index, num_frames - 1))  # Clamp to valid range
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

    def _calculate_mechanism_output_manual(self, mech_type: str, params: dict, time: float, layer_data: dict) -> Optional[QPointF]:
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
        dt = 0.033 * self.animation_speed
        self.animation_time += dt
        if self.animation_time > 2 * math.pi:
            self.animation_time -= 2 * math.pi

        active_joint_updates = {}

        # 1. Calculate all mechanism outputs and determine IK targets
        for mechanism_id, is_enabled in self.mechanism_enabled_state.items():
            if not is_enabled:
                continue

            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data or not layer_data.get("part_name"):
                continue

            try:
                output_pos = self._calculate_mechanism_output(
                    layer_data["type"], layer_data["params"], self.animation_time, layer_data
                )

                if output_pos:
                    part_name = layer_data["part_name"]

                    # Get the correct end effector joint for this part
                    part_info = self.parts_data.get(part_name)
                    if part_info and part_info.anchor_joint_id:
                        target_joint_id = self._get_target_joint_for_mechanism_control(part_name, part_info.anchor_joint_id)

                        # Find the standardized joint ID for the IK system
                        std_joint_id = self._get_standardized_joint_id(target_joint_id)

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

    def _get_standardized_joint_id(self, abstract_joint_id: str) -> Optional[str]:
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
                full_sim_data = layer_data.get("full_simulation_data", {})
                cam_data = full_sim_data.get("cam_data", {})
                to_scene_coords = self._get_scene_transform_function(layer_data)

                if to_scene_coords:
                    # First try to use dataset positions
                    if cam_data and "cam_centers" in cam_data and "follower_y_positions" in cam_data:
                        cam_centers = cam_data["cam_centers"]
                        follower_positions = cam_data["follower_y_positions"]
                        num_frames = len(cam_centers)

                        if num_frames > 0:
                            frame_index = int((time / (2 * math.pi)) * (num_frames - 1)) % num_frames
                            cam_center_orig = np.array(cam_centers[frame_index])
                            follower_y = follower_positions[frame_index]
                            follower_pos_orig = np.array([0, follower_y])
                    else:
                        # Fallback to manual calculation
                        angle = time
                        rotation_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
                        cam_center_orig = rotation_matrix @ np.array([eccentricity, 0])
                        follower_y = cam_center_orig[1] + base_radius
                        follower_pos_orig = np.array([0, follower_y])

                    # Transform to scene coordinates
                    cam_center_scene = to_scene_coords(cam_center_orig)
                    follower_scene = to_scene_coords(follower_pos_orig)

                    # Update cam visual (assuming first item is cam)
                    if len(visual_items) >= 1 and isinstance(visual_items[0], QGraphicsEllipseItem):
                        visual_items[0].setRect(cam_center_scene.x() - base_radius, cam_center_scene.y() - base_radius,
                                               base_radius * 2, base_radius * 2)

                    # Update follower visual (assuming second item is follower)
                    if len(visual_items) >= 2 and isinstance(visual_items[1], QGraphicsRectItem):
                        visual_items[1].setRect(follower_scene.x() - 10, follower_scene.y() - 5, 20, 10)

                    return

            elif mech_type == "gear" and len(visual_items) >= 4:  # Gear train
                params = layer_data.get("params", {})
                r1 = params.get("r1", 30)
                r2 = params.get("r2", 50)
                full_sim_data = layer_data.get("full_simulation_data", {})
                gear_data = full_sim_data.get("gear_data", {})
                to_scene_coords = self._get_scene_transform_function(layer_data)

                if to_scene_coords:
                    # First try to use dataset positions
                    if gear_data and "gear1_angles" in gear_data and "gear2_angles" in gear_data:
                        gear1_angles = gear_data["gear1_angles"]
                        gear2_angles = gear_data["gear2_angles"]
                        gear1_centers = gear_data.get("gear1_centers", [])
                        gear2_centers = gear_data.get("gear2_centers", [])
                        num_frames = len(gear1_angles)

                        if num_frames > 0:
                            frame_index = int((time / (2 * np.pi)) * (num_frames - 1)) % num_frames
                            theta1 = gear1_angles[frame_index]
                            theta2 = gear2_angles[frame_index]

                            # Use centers from dataset if available
                            if gear1_centers and gear2_centers:
                                gear1_center = np.array(gear1_centers[frame_index])
                                gear2_center = np.array(gear2_centers[frame_index])
                            else:
                                gear1_center = np.array([-r1, 0])
                                gear2_center = np.array([r2, 0])
                    else:
                        # Fallback to manual calculation
                        theta1 = time
                        theta2 = -theta1 * (r1 / r2)  # Gear ratio
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

                    return

            elif mech_type == "planetary_gear" and len(visual_items) >= 5:  # Planetary gear
                params = layer_data.get("params", {})
                r_sun = params.get("r_sun", 20)
                r_planet = params.get("r_planet", 30)
                arm_length = params.get("arm_length", 15)
                to_scene_coords = self._get_scene_transform_function(layer_data)

                if to_scene_coords:
                    # Calculate planetary gear positions
                    # Planet orbits around sun
                    planet_orbital_angle = time
                    # Planet rotation angle (depends on gear ratio)
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

                    # Transform to scene coordinates
                    planet_center_scene = to_scene_coords(planet_center_orig)
                    tracking_scene = to_scene_coords(tracking_point_orig)

                    # Update planet gear position (item 1)
                    if len(visual_items) > 1 and isinstance(visual_items[1], QGraphicsEllipseItem):
                        visual_items[1].setPos(
                            planet_center_scene.x() - r_planet,
                            planet_center_scene.y() - r_planet
                        )

                    # Update arm line (item 2)
                    if len(visual_items) > 2 and isinstance(visual_items[2], QGraphicsLineItem):
                        visual_items[2].setLine(QLineF(
                            planet_center_scene,
                            tracking_scene
                        ))

                    # Update tracking point marker (item 3)
                    if len(visual_items) > 3 and isinstance(visual_items[3], QGraphicsEllipseItem):
                        visual_items[3].setPos(
                            tracking_scene.x() - 8,
                            tracking_scene.y() - 8
                        )


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
            if item.scene():
                self.mechanism_scene.removeItem(item)
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

    def _update_parts_visual_state(self):
        """Update visual state of parts - now does nothing as we only use the list."""
        pass

    def _update_recommendation_button_state(self):
        """Update the recommendation button state based on parts with motion paths."""
        # Check if any parts have motion paths
        has_parts_with_paths = bool(self.path_data)

        if self.recommendation_btn:
            self.recommendation_btn.setEnabled(has_parts_with_paths)

    def _update_mechanism_layers_list(self):
        """Update the mechanism layers list to show all parts with togglable mechanism states."""
        if not self.mechanism_layers_list:
            return

        self.mechanism_layers_list.clear()

        # Show all parts (like in editor tab)
        if self.parts_data:
            # Get all parts and sort alphabetically
            all_parts = list(self.parts_data.keys())
            all_parts.sort()

            for part_name in all_parts:
                has_path = part_name in self.path_data
                has_mechanism = self._part_has_mechanism(part_name)
                mechanism_enabled = self.mechanism_enabled_state.get(part_name, False)

                # Create list item
                item = QListWidgetItem(part_name)
                item.setData(Qt.ItemDataRole.UserRole, part_name)  # Store part name

                # Style based on part state
                if has_path:
                    if has_mechanism:
                        if mechanism_enabled:
                            # Part with enabled mechanism: dark sky blue
                            item.setForeground(QBrush(QColor(0, 100, 150)))  # Dark blue text
                            item.setBackground(QBrush(QColor(135, 206, 250)))  # Sky blue background
                            item.setToolTip(f"{part_name} - Mechanism ENABLED (click to disable)")
                        else:
                            # Part with disabled mechanism: light sky blue
                            item.setForeground(QBrush(QColor(70, 130, 180)))  # Medium blue text
                            item.setBackground(QBrush(QColor(176, 224, 230)))  # Light sky blue background
                            item.setToolTip(f"{part_name} - Mechanism DISABLED (click to enable)")
                    else:
                        # Part with path but no mechanism: normal appearance
                        item.setForeground(QBrush(QColor(51, 51, 51)))  # Dark text
                        item.setBackground(QBrush(QColor(Qt.GlobalColor.transparent)))  # Transparent background
                        item.setToolTip(f"{part_name} - Has motion path (click to generate mechanism)")

                    # Enable for parts with paths
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                else:
                    # Part without path: grayed out
                    item.setForeground(QBrush(QColor(150, 150, 150)))  # Gray text
                    item.setBackground(QBrush(QColor(240, 240, 240)))  # Light gray background
                    item.setToolTip(f"{part_name} - No motion path")
                    # Disable selection for parts without paths
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

                # Add to list
                self.mechanism_layers_list.addItem(item)

    def _part_has_mechanism(self, part_name: str) -> bool:
        """Check if a part has any mechanism assigned to it."""
        for layer_data in self.mechanism_layers.values():
            if layer_data.get("part_name") == part_name:
                return True
        return False

    def _create_4bar_linkage_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
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
        driver_link.setZValue(3)
        self.mechanism_scene.addItem(driver_link)
        visual_items.append(driver_link)

        follower_link = QGraphicsLineItem(QLineF(p2_t, p4_t))
        follower_pen = QPen(QColor("#f39c12"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        follower_link.setPen(follower_pen)
        follower_link.setZValue(3)
        self.mechanism_scene.addItem(follower_link)
        visual_items.append(follower_link)

        # Check if coupler forms a triangle or is collinear (same as dataset generator)
        area = abs(p3[0]*(p4[1]-p_coupler[1]) + p4[0]*(p_coupler[1]-p3[1]) + p_coupler[0]*(p3[1]-p4[1])) / 2

        if area < 1e-3:  # Collinear - show as line
            coupler_line = QGraphicsLineItem(QLineF(p3_t, p4_t))
            coupler_pen = QPen(QColor("#2ecc71"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            coupler_line.setPen(coupler_pen)
            coupler_line.setZValue(4)
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
            coupler_triangle.setZValue(4)
            coupler_triangle.setOpacity(0.8)
            self.mechanism_scene.addItem(coupler_triangle)
            visual_items.append(coupler_triangle)

        # Add ground link (p1 to p2) with colorful style like dataset generator
        ground_link = QGraphicsLineItem(QLineF(p1_t, p2_t))
        ground_pen = QPen(QColor("#9b59b6"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)  # Purple
        ground_link.setPen(ground_pen)
        ground_link.setZValue(2)  # Lower than other links
        self.mechanism_scene.addItem(ground_link)
        visual_items.append(ground_link)

        # Add pivot points with colorful style (like dataset generator)
        pivot_colors = [QColor("#f39c12"), QColor("#f39c12"), QColor("#e74c3c"), QColor("#3498db")]  # Orange, Orange, Red, Blue
        pivot_positions = [p1_t, p2_t, p3_t, p4_t]
        pivot_names = ["Ground Pivot 1", "Ground Pivot 2", "Moving Joint 1", "Moving Joint 2"]

        for pos, color, name in zip(pivot_positions, pivot_colors, pivot_names):
            # Outer circle
            outer_pivot = self.mechanism_scene.addEllipse(
                pos.x() - 8, pos.y() - 8, 16, 16,
                QPen(color.darker(150), 2),
                QBrush(color)
            )
            outer_pivot.setZValue(10)
            outer_pivot.setToolTip(name)  # Add tooltip for identification
            visual_items.append(outer_pivot)

            # Inner highlight
            inner_pivot = self.mechanism_scene.addEllipse(
                pos.x() - 4, pos.y() - 4, 8, 8,
                QPen(Qt.PenStyle.NoPen),
                QBrush(color.lighter(150))
            )
            inner_pivot.setZValue(11)
            visual_items.append(inner_pivot)

        # Add coupler point marker (red dot)
        coupler_marker = self.mechanism_scene.addEllipse(
            p_coupler_t.x() - 4, p_coupler_t.y() - 4, 8, 8,
            QPen(QColor("#ff0000"), 2),
            QBrush(QColor("#ff0000"))
        )
        coupler_marker.setZValue(25)
        coupler_marker.setToolTip("Coupler Point (follows path)")
        visual_items.append(coupler_marker)


        return visual_items

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        """Handle mechanism visualization data"""
        mechanism_id = mechanism_graphics_data.get("mechanism_id")
        mechanism_type = mechanism_graphics_data.get("mechanism_type")
        layer_data = self.mechanism_layers.get(mechanism_id)
        if not layer_data:
            return

        # Remove any existing visual items for this mechanism
        existing_visual_items = layer_data.get("visual_items", [])
        for item in existing_visual_items:
            if item and item.scene():
                self.mechanism_scene.removeItem(item)

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


    def handle_ik_update(self, ik_results: Dict[str, Dict[str, Any]]):
        """Receives IK results and updates the MechanismView - SAME AS EDITOR TAB.
        This ensures natural skeleton movement in mechanism design tab.
        """

        if not self.mechanism_view:
            logging.warning("MechanismDesignTab: MechanismView not available to handle IK update.")
            return

        if not ik_results:
            return

        # Use the same method as EditorTab to ensure consistent skeleton movement
        # The mechanism_view is an EditorView, so it has the same update_visuals_from_animation_data method
        if hasattr(self.mechanism_view, 'update_visuals_from_animation_data'):
            self.mechanism_view.update_visuals_from_animation_data(ik_results)
        else:
            logging.error("MechanismDesignTab: mechanism_view does not have update_visuals_from_animation_data method")

        # Update the scene to reflect changes
        if self.mechanism_scene:
            self.mechanism_scene.update()

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


                except Exception as e:
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


            except Exception as e:
                pass

        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_reset_animation(self):
        """Reset animation to start position with comprehensive IK reset."""
        self.animation_timer.stop()
        self.animation_time = 0
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Reset skeleton and IK system first
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop any running animation
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                self.main_window.ik_manager.clear_mechanism_position_targets()

                # Reset IK system to initial state
                if hasattr(self.main_window.ik_manager, 'reset_all_ik_systems_and_data'):
                    self.main_window.ik_manager.reset_all_ik_systems_and_data()
                elif hasattr(self.main_window.ik_manager, 'reset_to_initial_pose'):
                    self.main_window.ik_manager.reset_to_initial_pose()


            except Exception as e:
                pass

        # Reset parts to initial positions
        self._position_parts_at_anchor_joints()

        # Reset mechanism visuals to initial state (time=0)
        for mechanism_id, layer_data in self.mechanism_layers.items():
            try:
                self._update_mechanism_visuals_for_animation(mechanism_id, 0, layer_data)
            except Exception as e:
                pass

            # Clear mechanism traces
            if mechanism_id in self.mechanism_trace_points:
                self.mechanism_trace_points[mechanism_id].clear()
                self.mechanism_trace_paths[mechanism_id] = QPainterPath()
                if mechanism_id in self.mechanism_trace_items:
                    self.mechanism_trace_items[mechanism_id].setPath(QPainterPath())

    def _on_layer_selection_changed(self):
        """Handle selection changes in the mechanism layers list."""
        selected_items = self.mechanism_layers_list.selectedItems()
        is_selection_valid = bool(selected_items)

        if is_selection_valid:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            logging.debug(f"Selected part: {part_name}")
        else:
            logging.debug("No part selected")

    def _on_layer_item_clicked(self, item):
        """Handle clicking on a layer item to toggle mechanism state."""
        part_name = item.data(Qt.ItemDataRole.UserRole)

        # Only process clicks on parts with motion paths
        if part_name not in self.path_data:
            logging.debug(f"Part {part_name} has no motion path, ignoring click")
            return

        has_mechanism = self._part_has_mechanism(part_name)

        if has_mechanism:
            # Toggle mechanism enabled/disabled state
            current_state = self.mechanism_enabled_state.get(part_name, False)
            new_state = not current_state
            self.mechanism_enabled_state[part_name] = new_state

            # Update visual items visibility
            self._toggle_mechanism_visuals(part_name, new_state)

        else:
            # No mechanism yet - trigger mechanism generation
            self._request_mechanism_for_part(part_name)

        # Update the list display
        self._update_mechanism_layers_list()

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

    def _request_mechanism_for_part(self, part_name: str):
        """Request mechanism generation for a specific part (replaces existing if any)."""
        # Check if part already has a mechanism and remove it first
        existing_mechanism_id = None
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if layer_data.get("part_name") == part_name:
                existing_mechanism_id = mechanism_id
                break

        if existing_mechanism_id:
            self._remove_mechanism(existing_mechanism_id)

        # Trigger recommendation generation for this specific part
        # Use existing recommendation logic but focus on this part
        self._generate_mechanism_for_part(part_name)

    def _remove_mechanism(self, mechanism_id: str):
        """Remove a specific mechanism and its visuals."""
        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers.pop(mechanism_id)

        # Remove visual items from scene
        visual_items = layer_data.get("visual_items", [])
        for item in visual_items:
            if item.scene():
                self.mechanism_scene.removeItem(item)

        # Remove trace item
        if mechanism_id in self.mechanism_trace_items:
            trace_item = self.mechanism_trace_items.pop(mechanism_id)
            if trace_item.scene():
                self.mechanism_scene.removeItem(trace_item)

        # Remove from trace points
        if mechanism_id in self.mechanism_trace_points:
            del self.mechanism_trace_points[mechanism_id]

        # Remove from enabled state (use part name as key)
        part_name = layer_data.get("part_name")
        if part_name and part_name in self.mechanism_enabled_state:
            del self.mechanism_enabled_state[part_name]


    def _generate_mechanism_for_part(self, part_name: str):
        """Generate a mechanism for a specific part using the recommendation system."""
        # Set this part as enabled for generation
        self.part_enabled_state = {part_name: True}

        # Trigger the recommendation system
        try:
            self._on_get_recommendations()
            # Set the new mechanism as enabled by default
            self.mechanism_enabled_state[part_name] = True
        except Exception as e:
            logging.error(f"Failed to generate mechanism for {part_name}: {e}")
            QMessageBox.warning(self, "Mechanism Generation Error",
                              f"Failed to generate mechanism for {part_name}: {str(e)}")


    def _create_interactive_handles_for_mechanism(self, mechanism_id, mechanism_type, params):
        _ = mechanism_id, mechanism_type, params  # Unused parameters
        pass
    def _create_3bar_linkage_visuals(self, mechanism_data):
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

    def _create_planetary_gear_visuals(self, mechanism_data: dict) -> List[QGraphicsItem]:
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
        sun_gear.setZValue(5)
        visual_items.append(sun_gear)

        # Create planet gear (orbiting)
        planet_color = QColor("#e67e22")  # Orange
        planet_gear = self.mechanism_scene.addEllipse(
            planet_center_scene.x() - r_planet_screen, planet_center_scene.y() - r_planet_screen,
            r_planet_screen * 2, r_planet_screen * 2,
            QPen(planet_color, 4),
            QBrush(planet_color.lighter(150))
        )
        planet_gear.setZValue(10)
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

    def _create_generic_mechanism_visuals(self, mechanism_data):
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

    def _generate_joint_motion_path(self, layer_data: dict, joint_id: str) -> Optional[QPainterPath]:
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

        except Exception as e:
            return None

    def _generate_mechanism_motion_path(self, layer_data: dict) -> Optional[QPainterPath]:
        """Generate a complete motion path for a mechanism over one full cycle."""
        mech_type = layer_data.get("type")
        params = layer_data.get("params", {})

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

                        if distance > 5.0:  # Threshold for "concerning" difference
                            pass
                        else:
                            pass

        except Exception as e:
            pass

    def activate_tab(self):
        """Called when the tab becomes active. Restore animation controls if needed."""
        # Ensure IKManager has the current parts data
        # Try to get the most up-to-date parts data
        parts_data_to_use = None
        if hasattr(self.main_window, 'project_data_manager') and self.main_window.project_data_manager:
            parts_data_to_use = self.main_window.project_data_manager.get_current_parts_data()

        # Fallback to local parts data if project data manager doesn't have it
        if not parts_data_to_use and hasattr(self, 'parts_data') and self.parts_data:
            parts_data_to_use = self.parts_data

        # If we don't have parts data locally, try to get it from project manager
        if not self.parts_data and parts_data_to_use:
            self.set_parts_data(parts_data_to_use)

        # Try to get path data from editor tab if we don't have it
        if not self.path_data and hasattr(self.main_window, 'editor_tab'):
            editor_tab = self.main_window.editor_tab
            if hasattr(editor_tab, '_collect_path_data'):
                current_path_data = editor_tab._collect_path_data()
                if current_path_data:
                    self.set_path_data_from_editor(current_path_data)

        # Set the parts data in IKManager
        if parts_data_to_use and hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            if hasattr(self.main_window.ik_manager, 'set_project_parts_data'):
                self.main_window.ik_manager.set_project_parts_data(parts_data_to_use)

        # Update mechanism layers list to show current parts and path status
        self._update_mechanism_layers_list()

        # Re-enable animation controls if we have enabled mechanisms
        has_enabled_mechanisms = any(self.mechanism_enabled_state.values()) if self.mechanism_enabled_state else False
        if self.mechanism_layers and has_enabled_mechanisms:
            self.play_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)


    def deactivate_tab(self):
        """Called when leaving the tab. Stop any running animations."""
        # Stop animation if running
        if self.animation_timer.isActive():
            self._on_stop_animation()


    # ... other methods from the original file can be added here if needed

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
