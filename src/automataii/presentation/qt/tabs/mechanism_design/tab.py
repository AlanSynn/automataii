"""
Mechanism Design Tab for Character Animation

This module provides the main interface for designing and editing mechanical systems
for character animation. It coordinates multiple subsystems including:
- Mechanism generation and visualization
- Animation controls and timeline
- Parametric editing (delegated to ParametricEditingManager)
- Blueprint export functionality

The class has been refactored to extract the parametric editing system into a separate
manager for better modularity and maintainability.
"""

import math
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, Qt, QTimer, QElapsedTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF, QPainter
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGroupBox,
    QHBoxLayout, 
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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
from automataii.application.mechanisms import MechanismService, SkeletonService

# New Visualization System
try:
    from automataii.presentation.qt.mechanisms.visualization import (
        VisualizationAdapter,
        VisualizationConfig,
        VisualizerFactory
    )
    from automataii.presentation.qt.mechanisms.visualization.adapter import VisualizationAdapter
    VISUALIZATION_AVAILABLE = True
except ImportError as e:
    VISUALIZATION_AVAILABLE = False
    VisualizationAdapter = None

# Parametric Design System (ULTRATHINK Architecture)
from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager

try:
    from automataii.presentation.qt.parametric_editor import (
        ParametricEditor, MechanismEditor, FourBarEditor,
        CamEditor, GearEditor, ParametricHandle
    )
    PARAMETRIC_AVAILABLE = True
except ImportError as e:
    PARAMETRIC_AVAILABLE = False

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene

from automataii.core.models import PartInfo
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter
from automataii.presentation.qt.dialogs.recommendation_dialog import (
    MechanismRecommendationDialog,
    qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import convert_json_params_to_internal
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.tabs.mechanism_design.services import TransformService
from automataii.presentation.qt.views.editor_view import EditorView
from automataii.domain.kinematics.mechanism import (
    MechanismCandidate,
)
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_ui import MechanismDesignUI
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_layout import MechanismDesignTabLayout
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_ui_state import (
    MechanismDesignTabUIState, UIState, AnimationState
)
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_signals import MechanismDesignTabSignals
from automataii.presentation.qt.tabs.mechanism_design.controller_adapter import (
    feature_enabled as controller_feature_enabled,
    build_presenter,
    convert_paths,
)
from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import (
    PathTraceManager,
    PathTraceConfig,
)
from automataii.presentation.qt.tabs.mechanism_design.components import (
    AnimationLifecycleController,
    MechanismOutputCalculator,
    MechanismVisualAnimator,
    SkeletonVisualizationHandler,
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

        # Business logic services
        self.mechanism_service = MechanismService()
        self.skeleton_service = SkeletonService()

        # Extracted services (god class decomposition)
        self._transform_service = TransformService()

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

        # Phase 1 performance: IK throttling and mechanism update batching
        self.ik_update_rate_hz: int = 30  # target IK updates per second
        self._ik_min_interval_ms: int = int(1000 / max(1, self.ik_update_rate_hz))
        self._ik_throttle_timer: QElapsedTimer = QElapsedTimer()
        self._ik_throttle_timer.invalidate()
        self._last_target_pos_by_joint: dict[str, QPointF] = {}
        self._pos_epsilon_px: float = 0.5  # minimum movement to trigger IK update
        self.mechanism_update_fraction: float = 0.5  # update only 50% mechanisms per frame
        self._mech_rr_cursor: int = 0

        # Tab state tracking for safe Qt object lifecycle management
        self._tab_visible = False
        self._tab_active = False  # Critical: Track if tab is active to prevent race conditions
        self._scene_recently_cleared = False  # Track scene clear operations to prevent redundant cleanup

        # Presenter / controller (feature-flagged)
        self._presenter = None
        self._presenter_view_model = None
        if controller_feature_enabled():
            self._presenter = build_presenter(self)
            self._presenter.add_view_listener(self._on_presenter_view_update)

        # Mechanism path tracing

        # Parametric Design System (ULTRATHINK Architecture)
        self.parametric_editor: ParametricEditor | None = None
        self.parametric_mode_enabled = False

        # Initialize parametric editing manager (will be fully initialized after UI setup)
        self.parametric_manager = ParametricEditingManager(self)

        # Path trace visualization (extracted responsibility)
        self._path_trace_manager = PathTraceManager(
            config=PathTraceConfig(
                max_points=500,
                update_stride=5,
                pen_color=QColor(255, 0, 0, 150),
                pen_width=2.0,
                z_value=100,
            )
        )
        self._trace_frame_tick: int = 0  # Animation frame counter

        # Performance controls (Phase 0 quick wins)

        # Initialize new visualization system if available
        self.visualization_adapter: VisualizationAdapter | None = None
        if VISUALIZATION_AVAILABLE:
            self.visualization_adapter = VisualizationAdapter(self.mechanism_scene)
        else:
            pass

        # PHASE 1 REFACTORING: Use new UI management system
        # UI setup with new layout manager
        self.layout_manager = MechanismDesignTabLayout()
        self.layout_manager.setup_main_layout(self)
        
        # Get all created widgets
        self.ui_widgets = self.layout_manager.get_all_widgets()
        
        # Initialize mechanism visuals factory now that scene is created
        self.visuals_factory = MechanismVisualsFactory(self.mechanism_scene)
        
        # Blueprint exporter (now that mechanism_view is available)
        self.blueprint_exporter = BlueprintExporter(
            parent=self,
            mechanism_view=self.mechanism_view,
            get_mechanism_layers=lambda: self.mechanism_layers,
            get_current_editor_items=lambda: self.current_editor_items,
            get_scene_transform_function=self._get_scene_transform_function,
        )
        
        # UI state manager
        self.ui_state_manager = MechanismDesignTabUIState(self.ui_widgets)
        
        # Signal connection manager
        self.signal_manager = MechanismDesignTabSignals(self.ui_widgets)
        
        # Backward compatibility: Create references to UI elements
        self.blueprint_btn = self.ui_widgets.get('blueprint_btn')
        self.recommendation_btn = self.ui_widgets.get('recommendation_btn')
        self.mechanism_layers_list = self.ui_widgets.get('mechanism_layers_list')
        self.play_btn = self.ui_widgets.get('play_btn')
        self.stop_btn = self.ui_widgets.get('stop_btn')
        self.reset_btn = self.ui_widgets.get('reset_btn')
        self.parametric_edit_btn = self.ui_widgets.get('parametric_edit_btn')
        self.zoom_in_btn = self.ui_widgets.get('zoom_in_btn')
        self.zoom_out_btn = self.ui_widgets.get('zoom_out_btn')
        self.zoom_fit_btn = self.ui_widgets.get('zoom_fit_btn')
        self.center_character_btn = self.ui_widgets.get('center_character_btn')
        self.blueprint_info_label = self.ui_widgets.get('blueprint_info_label')
        
        # Connect all signals using new signal manager
        self.signal_manager.connect_all_signals(self)
        
        # Initialize parametric system now that mechanism_scene is available
        if PARAMETRIC_AVAILABLE:
            self.parametric_manager._initialize_parametric_system()
        
        # PHASE 1: Initialize UI state management
        self._current_ui_state = UIState()
        self._update_all_ui_states()

        # PHASE 4: Initialize animation controller (only used extracted component)
        self._animation_controller = AnimationLifecycleController(
            mechanism_scene=self.mechanism_scene,
            path_trace_manager=self._path_trace_manager,
            parent=self,
        )
        self._configure_animation_controller_callbacks()

        # PHASE 5: Initialize skeleton visualization handler
        self._skeleton_handler = SkeletonVisualizationHandler(
            mechanism_view=self.mechanism_view,
            mechanism_scene=self.mechanism_scene,
            parent=self,
        )
        self._configure_skeleton_handler_callbacks()

        # PHASE 6: Initialize mechanism output calculator
        self._output_calculator = MechanismOutputCalculator(
            get_scene_transform=self._get_scene_transform_function,
        )

        # PHASE 7: Initialize mechanism visual animator
        self._visual_animator = MechanismVisualAnimator(
            get_scene_transform=self._get_scene_transform_function,
            set_line_if_changed=self._set_line_if_changed,
        )

    def _configure_skeleton_handler_callbacks(self) -> None:
        """Configure callbacks for the skeleton visualization handler."""
        self._skeleton_handler.configure_callbacks(
            get_main_window=lambda: self.main_window,
            get_current_editor_items=lambda: self.current_editor_items,
            get_parts_data=lambda: self.parts_data,
            is_animation_running=self._is_animation_running,
            position_parts_at_anchor_joints=self._position_parts_at_anchor_joints,
        )

    def _configure_animation_controller_callbacks(self) -> None:
        """Configure callbacks for the animation lifecycle controller."""
        self._animation_controller.configure_callbacks(
            get_main_window=lambda: self.main_window,
            get_mechanism_layers=lambda: self.mechanism_layers,
            get_part_enabled_state=lambda: self.part_enabled_state,
            get_parts_data=lambda: self.parts_data,
            get_presenter=lambda: self._presenter,
            get_ui_state_manager=lambda: self.ui_state_manager,
            calculate_mechanism_output=self._calculate_mechanism_output,
            update_mechanism_visuals_for_animation=self._update_mechanism_visuals_for_animation,
            get_target_joint_for_mechanism_control=self._get_target_joint_for_mechanism_control,
            get_standardized_joint_id=self._get_standardized_joint_id,
            ensure_skeleton_visualization=self._ensure_skeleton_visualization,
            setup_mechanism_ik_integration=self._setup_mechanism_ik_integration,
            reset_skeleton_to_initial_state=self._reset_skeleton_to_initial_state,
            position_parts_at_anchor_joints=self._position_parts_at_anchor_joints,
            clear_animation_cache=self._clear_animation_cache,
        )

    def _on_presenter_view_update(self, view_model):
        """Receive presenter view-model updates and sync lightweight state."""
        self._presenter_view_model = view_model
        self.part_enabled_state = {part.name: part.enabled for part in view_model.parts}
        selected_part = next((p.name for p in view_model.parts if p.is_selected), None)
        if selected_part is not None:
            self.selected_part_name = selected_part
        self._update_all_ui_states()

    def _update_all_ui_states(self) -> None:
        """Update all UI component states based on current data."""
        # Update UI state based on current mechanism and path data
        if self._presenter_view_model is not None:
            parts = self._presenter_view_model.parts
            has_paths = any(part.enabled for part in parts)
            has_mechanisms = any(part.has_layers for part in parts)
            has_enabled_parts = any(part.enabled for part in parts)
        else:
            has_paths = bool(getattr(self, 'path_data', {}))
            has_mechanisms = bool(getattr(self, 'mechanism_layers', {}))
            has_enabled_parts = any(
                getattr(self, 'part_enabled_state', {}).values()
            )
        ui_state = UIState(
            has_paths=has_paths,
            has_mechanisms=has_mechanisms,
            has_enabled_parts=has_enabled_parts,
            animation_running=getattr(self, 'animation_timer', None) and 
                            getattr(self.animation_timer, 'isActive', lambda: False)(),
            parametric_mode=getattr(self, 'parametric_mode_enabled', False),
            has_parts_data=bool(getattr(self, 'parts_data', {}))
        )
        
        # Update UI state manager
        if hasattr(self, 'ui_state_manager'):
            self.ui_state_manager.update_button_states(ui_state)
        
        self._current_ui_state = ui_state
        # Connect to IK manager and other external systems
        self._connect_to_ik_manager()

        # Connect parametric system signals if available
        # Signals are connected in _initialize_parametric_system for the new ParametricEditor

        # Load generated paths (support both dev and bundled layouts)
        generated_paths_file = resolve_path("resources/data/generated_mechanism_paths.json")
        # Initialize with empty QPainterPath since no user path is drawn yet
        empty_path = QPainterPath()
        self.recommendation_dialog = MechanismRecommendationDialog(empty_path, generated_paths_file, parent=self)
        self.recommendation_dialog.mechanism_selected.connect(self._handle_recommendation_selection)

        self.generated_paths = self.load_generated_paths(generated_paths_file)

    def load_generated_paths(self, file_path):
        """Loads generated mechanism paths from a JSON file."""
        # ... existing code ...

    # PHASE 1 REFACTORING: Old _setup_ui method removed - now handled by MechanismDesignTabLayout
    # This massive 400+ line method has been extracted into focused, single-responsibility classes

    # PHASE 1 REFACTORING: Old _connect_signals method removed - now handled by MechanismDesignTabSignals
    # Signal connections are now centralized and organized by functional area

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change from EditorView."""

        # Update skeleton manager if available
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            self.main_window.skeleton_manager.set_joint_bend_direction(joint_id, new_direction)

    def on_skeleton_manager_updated(self, skeleton_data: dict | None):
        """Handle skeleton updates from skeleton_manager. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler.on_skeleton_manager_updated(skeleton_data)

    def _connect_to_ik_manager(self):
        """Connect to IK manager signals. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler.connect_to_ik_manager()

    def set_path_data_from_editor(self, path_data: dict[str, QPainterPath]):
        """Receive path data from editor tab"""
        if self._presenter:
            converted_paths = convert_paths(path_data or {})
            self._presenter.update_paths(converted_paths)
        if path_data:

            # Debug individual path data
            for part_name, path in path_data.items():
                if path and not path.isEmpty():
                    path_rect = path.boundingRect()

                    # Check if path has any elements
                    element_count = path.elementCount()
                else:
                    pass

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

        self.path_data = path_data.copy() if path_data else {}

        # Initialize enabled state for new parts (default to enabled)
        for part_name in self.path_data.keys():
            if part_name not in self.part_enabled_state:
                self.part_enabled_state[part_name] = True

        # Remove enabled state for parts that no longer have paths
        parts_to_remove = [name for name in self.part_enabled_state.keys() if name not in self.path_data]
        for part_name in parts_to_remove:
            del self.part_enabled_state[part_name]

        # Update UI state based on enabled parts
        self._update_all_ui_states()

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
        if parts_data:
            pass

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

        # Update mechanism layers list to show parts
        self._update_mechanism_layers_list()

    def _position_parts_at_anchor_joints(self):
        """Position parts at their anchor joints using cached skeleton data."""
        if not hasattr(self, '_initial_skeleton_data_cache') or not self._initial_skeleton_data_cache:
            return

        # Delegate to skeleton service
        positioned_count = self.skeleton_service.position_parts_at_anchor_joints(
            self.current_editor_items,
            self.parts_data,
            self._initial_skeleton_data_cache
        )

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
        """Cache skeleton data. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler.cache_initial_skeleton(skeleton_data_dict)
        # Keep local reference for backwards compatibility
        self._initial_skeleton_data_cache = self._skeleton_handler.initial_skeleton_data_cache

    def _is_animation_running(self) -> bool:
        """Check if mechanism animation is currently running."""
        return self.animation_timer and self.animation_timer.isActive()

    def on_skeleton_updated(self, skeleton_data: dict | None):
        """Handle skeleton updates from IK manager. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler.on_skeleton_updated(skeleton_data)

    def _update_parts_from_skeleton(self, skeleton_data: dict):
        """Update part positions from skeleton. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler._update_parts_from_skeleton(skeleton_data)

    def _ensure_skeleton_visualization(self, skeleton_data: dict):
        """Ensure skeleton visualization is set up. Delegates to SkeletonVisualizationHandler."""
        self._skeleton_handler.ensure_skeleton_visualization(skeleton_data)

    def _format_skeleton_for_visualization(self, skeleton_data: dict):
        """Format skeleton data. Delegates to SkeletonVisualizationHandler."""
        return self._skeleton_handler.format_skeleton_for_visualization(skeleton_data)

    def _convert_skeleton_data_for_animation(self, skeleton_data: dict):
        """Convert skeleton data. Delegates to SkeletonVisualizationHandler."""
        return self._skeleton_handler.convert_skeleton_data_for_animation(skeleton_data)

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
            pass

        # CRITICAL: Clear data structures BEFORE clearing scene to prevent Qt object access errors

        # 1. Clear all mechanism visual item references FIRST
        for mechanism_id, layer_data in self.mechanism_layers.items():
            if "visual_items" in layer_data:
                layer_data["visual_items"] = []

        # 2. Clear other visual tracking structures
        self._path_trace_manager.clear_all_traces(self.mechanism_scene)
        if hasattr(self, 'path_visual_items'):
            self.path_visual_items.clear()

        # 3. NOW clear the scene (this will delete all Qt objects atomically)
        self._scene_recently_cleared = True  # Flag to prevent individual item removal
        self.mechanism_scene.clear()

        # Reset the flag after a short delay to allow normal operations
        QTimer.singleShot(100, lambda: setattr(self, '_scene_recently_cleared', False))

        # 4. Re-add skeleton item if it was preserved
        if skeleton_item:
            try:
                # Test if skeleton item is still valid
                _ = skeleton_item.boundingRect()
                self.mechanism_scene.addItem(skeleton_item)
                # Set proper Z-order: skeleton at bottom (Z=0)
                skeleton_item.setZValue(Z_SKELETON_OVERLAY)
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
            from automataii.domain.animation.part_definitions import BODY_PARTS
        except ImportError:
            BODY_PARTS = {}

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
        self._path_trace_manager.clear_all_traces(self.mechanism_scene)

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
        if self._presenter:
            self._presenter.select_part(target_part_name)

        from automataii.utils.paths import resolve_path
        generated_paths_file = resolve_path("resources/data/generated_mechanism_paths.json")

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

                    else:
                        # Fallback to character position
                        char_pos = self._get_character_position()
                        layer_data["cam_position"] = char_pos
                        layer_data["params"]["center_x"] = char_pos[0]
                        layer_data["params"]["center_y"] = char_pos[1]
                except Exception as e:
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
                self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)

        # Remove from mechanism_layers
        for mechanism_id in mechanisms_to_remove:
            del self.mechanism_layers[mechanism_id]

        # Clear enabled state for this part
        if part_name in self.mechanism_enabled_state:
            del self.mechanism_enabled_state[part_name]

        # CRITICAL: Clear any mechanism path items for this part to prevent duplicate paths
        if part_name in self.mechanism_path_items:
            path_item = self.mechanism_path_items[part_name]
            if path_item and path_item.scene():
                self.mechanism_scene.removeItem(path_item)
            del self.mechanism_path_items[part_name]

    def _generate_mechanism_from_candidate(self, candidate_data: dict[str, Any]):
        """Generates a mechanism layer and visuals from a selected candidate."""
        # CHANGED: Support multiple mechanisms - only clear mechanism for current part
        if hasattr(self, 'selected_part_name') and self.selected_part_name:
            self._clear_mechanism_for_part(self.selected_part_name)

            # CRITICAL: Also clear any old trace paths for ALL mechanisms of this part
            # This ensures no duplicate paths remain when switching mechanisms
            for mechanism_id in self._path_trace_manager.get_all_mechanism_ids():
                layer_data = self.mechanism_layers.get(mechanism_id)
                if layer_data and layer_data.get("part_name") == self.selected_part_name:
                    self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)
        else:
            pass

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

                        # Compute total lift from target path (use Y-range)
                        path_y_min = np.min(path_np[:, 1])
                        total_lift_screen = float(path_y_max - path_y_min)

                        # Normalize eccentricity to mechanism space used by transform (avoid double scaling)
                        # Match _get_scene_transform_function: user_scale = max(user_bbox)/2
                        x_min, y_min = np.min(path_np[:, 0]), np.min(path_np[:, 1])
                        x_max, y_max = np.max(path_np[:, 0]), np.max(path_np[:, 1])
                        user_bbox_w = float(x_max - x_min)
                        user_bbox_h = float(y_max - y_min)
                        user_scale = max(user_bbox_w, user_bbox_h) / 2.0 if max(user_bbox_w, user_bbox_h) > 0 else 1.0
                        ecc_norm = total_lift_screen / user_scale if user_scale > 0 else total_lift_screen

                        # Set normalized parameters
                        layer_data["params"]["eccentricity"] = max(1e-6, ecc_norm)
                        # If base_radius missing or too large, choose a reasonable default relative to lift
                        br = layer_data["params"].get("base_radius")
                        if (br is None) or (br <= 0) or (br > 3 * ecc_norm):
                            layer_data["params"]["base_radius"] = 0.3 * ecc_norm

                except Exception as e:
                    # Fallback to default position
                    layer_data["params"]["center_x"] = 400
                    layer_data["params"]["center_y"] = 300
            else:
                # No path available, use default position
                layer_data["params"]["center_x"] = 400
                layer_data["params"]["center_y"] = 300

            # Set default cam template SVG path for template-driven cam design (pear cam)
            try:
                template_rel = Path("resources/blueprints/tom/pear_cam_4.3in.svg")
                template_path = resolve_path(template_rel)
                if template_path.exists():
                    template_str = str(template_path)
                    layer_data["cam_template_svg_path"] = template_str
                    layer_data["params"]["cam_template_svg_path"] = template_str
            except Exception:
                pass

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

        # Update UI state now that parts are available
        self._update_all_ui_states()

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
        # Delegate to mechanism service
        if hasattr(self, '_initial_skeleton_data_cache'):
            is_connected = self.mechanism_service.verify_coupler_joint_connection(
                layer_data,
                self.parts_data,
                self._initial_skeleton_data_cache,
                self._get_scene_transform_function,
                self._calculate_mechanism_output
            )

    def _adjust_mechanism_to_target_joint(self, layer_data: dict):
        """Adjust mechanism positioning so coupler point aligns with target skeleton joint."""
        # Delegate to mechanism service
        if hasattr(self, '_initial_skeleton_data_cache'):
            adjusted = self.mechanism_service.adjust_mechanism_to_target_joint(
                layer_data,
                self.parts_data,
                self._initial_skeleton_data_cache,
                self._calculate_mechanism_output
            )

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the internal data structure (no separate UI display)"""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data
        # Don't add separate mechanism item to list - mechanisms are shown through part highlighting
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)

        # Update UI state
        self._update_all_ui_states()

        # Refresh the parts list to show mechanism assignment
        self._update_mechanism_layers_list()

        # Initialize path tracing for this mechanism
        self._path_trace_manager.init_trace(mechanism_id, self.mechanism_scene)

        # Sync UI state so Parametric Edit becomes enabled immediately
        try:
            self._update_all_ui_states()
        except Exception:
            pass

    def _get_scene_transform_function(self, layer_data: dict) -> Callable | None:
        """
        Creates coordinate transformation from mechanism space to scene space.
        Delegates to TransformService (god class decomposition).
        """
        return self._transform_service.get_scene_transform(layer_data)

    def _get_inverse_scene_transform_function(self, layer_data: dict) -> Callable | None:
        """
        Creates coordinate transformation from scene space to mechanism space.
        Delegates to TransformService (god class decomposition).
        """
        return self._transform_service.get_inverse_scene_transform(layer_data)

    def _extract_key_points_from_simulation(self, full_sim_data: dict, mechanism_type: str) -> dict:
        """Extract key_points from simulation. Delegates to MechanismOutputCalculator."""
        return self._output_calculator.extract_key_points_from_simulation(full_sim_data, mechanism_type)

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, layer_data: dict) -> QPointF | None:
        """Calculate mechanism output. Delegates to MechanismOutputCalculator."""
        return self._output_calculator.calculate_output(mech_type, params, time, layer_data)

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
            return None

    def _update_animation(self):
        """
        Update animation frame by calculating mechanism outputs and setting them as targets for the IK system.
        The IK system is the single source of truth for skeleton and part animation.
        """
        # CRITICAL: Prevent animation updates when tab is not active
        if not hasattr(self, '_tab_active') or not self._tab_active:
            if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
                self.animation_timer.stop()
            return

        dt = 0.05 * self.animation_speed
        self.animation_time += dt
        if self.animation_time > 2 * math.pi:
            self.animation_time -= 2 * math.pi
        # Advance trace frame tick for stride gating
        self._trace_frame_tick = (self._trace_frame_tick + 1) % 1000000

        active_joint_updates = {}

        # DEBUG: Check if mechanism_layers has any data
        if not self.mechanism_layers:
            pass
        else:
            for mech_id, layer_data in self.mechanism_layers.items():
                part_name = layer_data.get("part_name", "unknown")

        # 1. Calculate mechanism outputs (round-robin subset) and determine IK targets
        mech_items = list(self.mechanism_layers.items())
        total_mechs = len(mech_items)
        if total_mechs > 0:
            batch_count = max(1, int(math.ceil(total_mechs * max(0.05, min(1.0, self.mechanism_update_fraction)))))
            start = self._mech_rr_cursor % total_mechs
            end = start + batch_count
            if end <= total_mechs:
                selected = mech_items[start:end]
            else:
                selected = mech_items[start:] + mech_items[: (end % total_mechs)]
            self._mech_rr_cursor = (self._mech_rr_cursor + batch_count) % total_mechs
        else:
            selected = []

        for mechanism_id, layer_data in selected:
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

                        if std_joint_id:
                            # This is the target for the IK system
                            active_joint_updates[std_joint_id] = output_pos
                        else:
                            pass

                    # Update mechanism visuals and path trace
                    self._update_mechanism_visuals_for_animation(mechanism_id, self.animation_time, layer_data)
                    self._path_trace_manager.update_trace(mechanism_id, output_pos, self.mechanism_scene)

            except Exception as e:
                pass

        # 2. Throttled IK target updates with epsilon-based skipping
        if active_joint_updates and hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            if not self._ik_throttle_timer.isValid():
                self._ik_throttle_timer.start()
            if self._ik_throttle_timer.elapsed() >= self._ik_min_interval_ms:
                ik_manager = self.main_window.ik_manager
                eps = max(0.0, float(getattr(self, '_pos_epsilon_px', 0.5)))
                for joint_id, target_pos in active_joint_updates.items():
                    last = self._last_target_pos_by_joint.get(joint_id)
                    if last is None or (abs(target_pos.x() - last.x()) > eps or abs(target_pos.y() - last.y()) > eps):
                        ik_manager.set_mechanism_position_target(joint_id, target_pos)
                        self._last_target_pos_by_joint[joint_id] = target_pos
                self._ik_throttle_timer.restart()

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
        """Update mechanism visual elements during animation.

        Delegates to MechanismVisualAnimator (god class decomposition).
        """
        self._visual_animator.update_visuals(
            mechanism_id=mechanism_id,
            time=time,
            layer_data=layer_data,
            visuals_factory=self.visuals_factory,
        )

    def _display_paths_in_preview(self):
        """Display motion paths from editor tab in the preview"""

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
                    # Clear trace using manager
                    self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)

        # Calculate combined bounds of all paths to set scene rect properly
        combined_bounds = None

        # Add new path items with enhanced debugging
        paths_added = 0
        for part_name, path in self.path_data.items():
            if not path.isEmpty():
                path_bounds = path.boundingRect()

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

            else:
                pass

        # Debug scene bounds
        scene_rect = self.mechanism_scene.itemsBoundingRect()

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

    def _update_mechanism_layers_list(self):
        """Update the mechanism layers list to show all parts with simple path-based coloring and toggle functionality.
        
        PHASE 1 REFACTORING: UI list management is now handled by layout manager.
        This method now updates the data and shows parts with motion paths in black, others in gray.
        """
        # Get the widget from UI system
        if hasattr(self, 'ui_widgets') and 'mechanism_layers_list' in self.ui_widgets:
            mechanism_layers_list = self.ui_widgets['mechanism_layers_list']

            # Simple clear and repopulate
            mechanism_layers_list.clear()

            # Use presenter view-model when feature flag is enabled
            if self._presenter_view_model:
                from PyQt6.QtGui import QFont  # Only QFont not in top-level imports

                for part_vm in self._presenter_view_model.parts:
                    part_name = part_vm.name
                    enabled = part_vm.enabled
                    has_layers = part_vm.has_layers or self._part_has_mechanism(part_name)

                    self.part_enabled_state[part_name] = enabled

                    item = QListWidgetItem(part_name)
                    item.setData(Qt.ItemDataRole.UserRole, part_name)
                    item.setForeground(Qt.GlobalColor.black if enabled else Qt.GlobalColor.gray)
                    if has_layers:
                        font = QFont(item.font())
                        font.setBold(True)
                        item.setFont(font)
                        item.setToolTip(f"{part_name} — mechanism layers active")
                    elif not enabled:
                        item.setToolTip(f"{part_name} — disabled")
                    else:
                        item.setToolTip(f"{part_name} — no mechanism applied")
                    item.setSelected(part_vm.is_selected)
                    mechanism_layers_list.addItem(item)
                return

            # Get editor parts data and path data
            editor_parts_data = None
            editor_path_data = None
            
            if hasattr(self, 'main_window') and self.main_window:
                if hasattr(self.main_window, 'editor_tab') and self.main_window.editor_tab:
                    editor_parts_data = self.main_window.editor_tab.current_parts_info
                    editor_path_data = self.main_window.editor_tab.get_current_path_data()
                    
            if editor_parts_data:
                # Filter out disabled parts
                disabled_parts = {
                    'torso',
                    'left_arm_upper', 'right_arm_upper',
                    'left_leg_upper', 'right_leg_upper'
                }
                
                all_parts = [
                    part for part in editor_parts_data.keys()
                    if part not in disabled_parts
                ]
                
                # Add items to the list
                for part in all_parts:
                    item = QListWidgetItem(part)
                    item.setData(Qt.ItemDataRole.UserRole, part)
                    
                    # Color based on whether part has motion path (not mechanism)
                    has_motion_path = (editor_path_data and 
                                     part in editor_path_data and 
                                     editor_path_data[part] is not None and
                                     not editor_path_data[part].isEmpty())
                    
                    if has_motion_path:
                        item.setForeground(Qt.GlobalColor.black)
                        item.setToolTip(f"{part} - has motion path")
                    else:
                        item.setForeground(Qt.GlobalColor.gray) 
                        item.setToolTip(f"{part} - no motion path")
                        
                    mechanism_layers_list.addItem(item)
            # Don't set to None - keep existing widget if possible

    def _part_has_mechanism(self, part_name: str) -> bool:
        """Check if a part has any mechanism assigned to it."""
        if self._presenter_view_model:
            part_vm = self._presenter_view_model.find_part(part_name)
            if part_vm is not None and part_vm.has_layers:
                return True
        for layer_data in self.mechanism_layers.values():
            if layer_data.get("part_name") == part_name:
                return True
        return False


    def _reset_skeleton_to_initial_state(self):
        """Reset skeleton to initial state (addresses issues #9, #10, #11)."""

        # Stop any animation first
        if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
            self.animation_timer.stop()
            self.animation_time = 0

        # Reset IK system to initial pose
        if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
            try:
                # Stop any running animation
                if hasattr(self.main_window.ik_manager, 'stop_animation'):
                    self.main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                if hasattr(self.main_window.ik_manager, 'clear_mechanism_position_targets'):
                    self.main_window.ik_manager.clear_mechanism_position_targets()

                # Reset to initial pose
                if hasattr(self.main_window.ik_manager, 'reset_animation_state'):
                    self.main_window.ik_manager.reset_animation_state()
                elif hasattr(self.main_window.ik_manager, 'reset_all_ik_systems_and_data'):
                    self.main_window.ik_manager.reset_all_ik_systems_and_data()

            except Exception as e:
                pass

        # Reset skeleton visualization using cached initial state
        if self._initial_skeleton_data_cache:

            # First, position parts at their anchor joints
            self._position_parts_at_anchor_joints()

            # Then update skeleton visualization with initial state
            self.on_skeleton_updated(self._initial_skeleton_data_cache.copy())

            # Force skeleton visualization update
            if hasattr(self.mechanism_view, 'skeleton_graphics_item') and self.mechanism_view.skeleton_graphics_item:
                self.mechanism_view.skeleton_graphics_item.update()

        else:
            # If no cached data, try to get from skeleton manager
            if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
                initial_skeleton = self.main_window.skeleton_manager.get_current_skeleton_data()
                if initial_skeleton:
                    self.cache_initial_skeleton(initial_skeleton)
                    self.on_skeleton_updated(initial_skeleton.copy())
                else:
                    pass
            else:
                pass

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
        transform_func = self._get_scene_transform_function(mechanism_graphics_data)
        if mechanism_type == "4_bar_linkage":
            visual_items.extend(self.visuals_factory.create_4bar_linkage_visuals(mechanism_graphics_data, transform_func))
        elif mechanism_type == "cam":
            char_pos = self._get_character_position()
            visual_items.extend(self.visuals_factory.create_cam_visuals(mechanism_graphics_data, transform_func, char_pos))
        elif mechanism_type == "gear":
            visual_items.extend(self.visuals_factory.create_gear_visuals(mechanism_graphics_data, transform_func))
        elif mechanism_type == "planetary_gear":
            visual_items.extend(self.visuals_factory.create_planetary_gear_visuals(mechanism_graphics_data, transform_func))

        layer_data["visual_items"] = visual_items

        # Merge back important computed fields from visuals to persistent layer_data
        for k in (
            'cam_profile_local_points', 'cam_points_local', 'cam_template_svg_path',
            'cam_transform_function', 'cam_axis_local', 'cam_scale_factor', 'rod_length_multiplier',
            'follower_fixed_x_scene'
        ):
            if k in mechanism_graphics_data:
                layer_data[k] = mechanism_graphics_data[k]

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
                except AttributeError:
                    pass

    def _safe_remove_visual_items(self, visual_items: list):
        """Safely remove visual items from scene, handling Qt object lifecycle issues."""
        if not visual_items:
            return

        # CRITICAL: Don't attempt individual removal if scene was already cleared
        # This prevents the "Visual item already deleted by Qt" flood
        if hasattr(self, '_scene_recently_cleared') and self._scene_recently_cleared:
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
                                pass

            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    deleted_items_count += 1
                else:
                    pass
            except Exception as e:
                pass

        if deleted_items_count > 0:
            pass
        elif valid_items_count > 0:
            pass

    def cleanup_tab_resources(self):
        """Clean up resources when switching away from mechanism tab."""
        try:

            # CRITICAL: Stop IK manager animations to prevent race conditions
            if hasattr(self.main_window, 'ik_manager') and self.main_window.ik_manager:
                try:
                    self.main_window.ik_manager.stop_animation()
                except Exception as e:
                    pass

            # Stop any running mechanism animations
            if hasattr(self, 'animation_timer') and self.animation_timer.isActive():
                self.animation_timer.stop()

            # CRITICAL: Clear data structures FIRST, then attempt safe Qt cleanup

            # 1. Store references to visual items before clearing data structures
            all_visual_items = []
            for mechanism_id, layer_data in self.mechanism_layers.items():
                visual_items = layer_data.get("visual_items", [])
                all_visual_items.extend(visual_items)
                # Clear the visual items list FIRST
                layer_data["visual_items"] = []

            # 2. Clear other tracking structures
            self._path_trace_manager.clear_all_traces(self.mechanism_scene)
            if hasattr(self, 'path_visual_items'):
                self.path_visual_items.clear()

            # 3. NOW attempt safe removal of Qt objects (many may already be deleted)
            if all_visual_items:
                self._safe_remove_visual_items(all_visual_items)

            # Clear scene if needed
            if hasattr(self, 'mechanism_scene') and self.mechanism_scene:
                try:
                    # Don't clear the entire scene, just ensure it's stable
                    self.mechanism_scene.update()
                except Exception as e:
                    pass

        except Exception as e:
            pass

    def prepare_tab_activation(self):
        """Prepare tab for activation when switching back to mechanism tab."""
        try:

            # Ensure skeleton is properly initialized if we have cached data
            if hasattr(self, '_initial_skeleton_data_cache') and self._initial_skeleton_data_cache:
                try:
                    self._ensure_skeleton_visualization(self._initial_skeleton_data_cache)
                except Exception as e:
                    pass

            # Refresh mechanism visuals if any mechanisms are enabled
            enabled_mechanisms = [mid for mid, enabled in self.mechanism_enabled_state.items() if enabled]
            if enabled_mechanisms:
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

                            # CRITICAL FIX: Regenerate trace items (red paths) if missing or invalid
                            # Check if trace needs regeneration using manager
                            trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                            if trace_item is None or self._is_visual_item_invalid(trace_item):
                                self._path_trace_manager.init_trace(mechanism_id, self.mechanism_scene)
                                # Restore trace points if they exist
                                trace_points = self._path_trace_manager.get_trace_points(mechanism_id)
                                if len(trace_points) > 1:
                                    path = QPainterPath()
                                    path.moveTo(trace_points[0])
                                    for point in trace_points[1:]:
                                        path.lineTo(point)
                                    if trace_item:
                                        trace_item.setPath(path)

                        except Exception as e:
                            pass

        except Exception as e:
            pass

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
        self.cleanup_tab_resources()

    def activate_tab(self):
        """Called when user switches to mechanism tab.
        
        PHASE 1 REFACTORING: Simplified to use new UI management system.
        """
        self._tab_active = True  # CRITICAL: Allow IK updates

        self.prepare_tab_activation()

        # Update the mechanism layers list with current data
        self._update_mechanism_layers_list()
        
        # CRITICAL: Update all UI states when tab is activated
        self._update_all_ui_states()

    def showEvent(self, event):
        """Handle widget show event for additional safety."""
        super().showEvent(event)
        try:
            # Additional activation logic if needed
            if hasattr(self, '_tab_visible'):
                self._tab_visible = True
        except Exception as e:
            pass

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
        """Receives IK results and updates the MechanismView - SAME AS EDITOR TAB.
        This ensures natural skeleton movement in mechanism design tab.
        """
        # CRITICAL: Prevent race condition crashes during tab switching
        if not hasattr(self, '_tab_active') or not self._tab_active:
            return

        if not self.isVisible():
            return

        if not self.mechanism_view:
            return

        if not ik_results:
            return

        try:
            # Use the same method as EditorTab to ensure consistent skeleton movement
            # The mechanism_view is an EditorView, so it has the same update_visuals_from_animation_data method
            if hasattr(self.mechanism_view, 'update_visuals_from_animation_data'):
                self.mechanism_view.update_visuals_from_animation_data(ik_results)
            else:
                pass

            # Update the scene to reflect changes - with safety checks
            if self.mechanism_scene and hasattr(self, '_tab_active') and self._tab_active:
                try:
                    self.mechanism_scene.update()
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        pass
                    else:
                        raise

        except Exception as e:
            pass

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
        """Start the animation timer and IK animation with enhanced mechanism-IK integration.

        Delegated to AnimationLifecycleController for god class decomposition.
        """
        if self.mechanism_enabled_state:
            initial_data = getattr(self, '_initial_skeleton_data_cache', None)
            self._animation_controller.start_animation(
                mechanism_enabled_state=self.mechanism_enabled_state,
                initial_skeleton_data=initial_data,
            )
        else:
            QMessageBox.warning(self, "Warning", "No mechanisms are enabled for animation.")

    def _on_stop_animation(self):
        """Stop the animation timer and IK animation with proper cleanup.

        Delegated to AnimationLifecycleController for god class decomposition.
        """
        self._animation_controller.stop_animation()

    def _on_reset_animation(self):
        """Reset animation to start position with comprehensive IK reset.

        Delegated to AnimationLifecycleController for god class decomposition.
        """
        self._animation_controller.reset_animation()

    def _on_layer_selection_changed(self):
        """Handle selection changes in the mechanism layers list."""
        # CRITICAL: Clear animation cache when layer selection changes
        self._clear_animation_cache()

        # CRITICAL: Clear all mechanism traces when switching selection to prevent old paths from lingering
        for mechanism_id in self._path_trace_manager.get_all_mechanism_ids():
            self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)

        # ISSUE #11: Reset skeleton when selection changes while preserving view
        current_view_transform = self.mechanism_view.transform()  # Save current view

        self._reset_skeleton_to_initial_state()

        # Restore the view transform to maintain user's current view
        self.mechanism_view.setTransform(current_view_transform)

        selected_items = self.mechanism_layers_list.selectedItems()
        is_selection_valid = bool(selected_items)

        if is_selection_valid:
            part_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if self._presenter:
                self._presenter.select_part(part_name)
            self.selected_part_name = part_name

            if self.parametric_mode_enabled:
                self._update_parametric_handles_for_selection(part_name)

        else:
            if self._presenter:
                self._presenter.select_part(None)
            self.selected_part_name = None

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
            return

        # In parametric mode, don't toggle enabled/disabled state
        # Just allow the selection to change for parametric editing
        if self.parametric_mode_enabled:
            # The selection change is handled by _on_layer_selection_changed
            return

        # Normal mode: Toggle enabled/disabled state
        if self._presenter_view_model and self._presenter:
            part_vm = self._presenter_view_model.find_part(part_name)
            current_state = part_vm.enabled if part_vm else True
        else:
            current_state = self.part_enabled_state.get(part_name, True)

        new_state = not current_state

        if self._presenter:
            self._presenter.enable_part(part_name, new_state)
        self.part_enabled_state[part_name] = new_state

        self._update_part_visibility_and_animation(part_name, new_state)
        self._update_mechanism_layers_list()

    def _update_part_visibility_and_animation(self, part_name: str, enabled: bool):
        """Update part visibility and animation control based on enabled state."""
        # Control part visibility in the scene
        if hasattr(self, 'current_editor_items') and part_name in self.current_editor_items:
            part_item = self.current_editor_items[part_name]
            if hasattr(part_item, 'setVisible'):
                part_item.setVisible(enabled)

        # Control mechanism visuals if they exist
        has_mechanism = self._part_has_mechanism(part_name)
        if has_mechanism:
            self._toggle_mechanism_visuals(part_name, enabled)

        # Update UI state
        self._update_all_ui_states()

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
                # Update trace visibility using manager
                trace_item = self._path_trace_manager.get_trace_item(mechanism_id)
                if trace_item and hasattr(trace_item, 'setVisible'):
                    trace_item.setVisible(enabled)





    # ====== Performance Utilities ======
    def _set_line_if_changed(self, line_item: QGraphicsLineItem, p1: QPointF, p2: QPointF, eps: float = 0.1) -> None:
        """Set line only if endpoints changed beyond epsilon (in scene px)."""
        try:
            current = line_item.line()
            if (abs(current.p1().x() - p1.x()) > eps or abs(current.p1().y() - p1.y()) > eps or
                abs(current.p2().x() - p2.x()) > eps or abs(current.p2().y() - p2.y()) > eps):
                line_item.setLine(QLineF(p1, p2))
        except Exception:
            # Fallback if any issue
            try:
                line_item.setLine(QLineF(p1, p2))
            except Exception:
                pass

    def apply_performance_preset(self, preset: str) -> None:
        """Apply performance preset to mechanism simulation and view.

        Presets:
        - Fast: fewer updates, simpler trace, lower IK rate
        - Balanced: defaults
        - High: more updates, longer trace, higher IK rate
        """
        p = (preset or '').strip().lower()
        if p == 'fast':
            self.ik_update_rate_hz = 15
            self._ik_min_interval_ms = int(1000 / self.ik_update_rate_hz)
            self._pos_epsilon_px = 1.0
            self.mechanism_update_fraction = 0.33
            self.trace_update_stride = 4
            self.trace_max_points = 250
            # Render hint: prefer speed (no AA)
            if hasattr(self, 'mechanism_view') and self.mechanism_view:
                try:
                    self.mechanism_view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                except Exception:
                    pass
        elif p == 'high':
            self.ik_update_rate_hz = 60
            self._ik_min_interval_ms = int(1000 / self.ik_update_rate_hz)
            self._pos_epsilon_px = 0.2
            self.mechanism_update_fraction = 1.0
            self.trace_update_stride = 1
            self.trace_max_points = 1000
            # Enable AA for nicer visuals
            if hasattr(self, 'mechanism_view') and self.mechanism_view:
                try:
                    self.mechanism_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                except Exception:
                    pass
        else:  # balanced/default
            self.ik_update_rate_hz = 30
            self._ik_min_interval_ms = int(1000 / self.ik_update_rate_hz)
            self._pos_epsilon_px = 0.5
            self.mechanism_update_fraction = 0.5
            self.trace_update_stride = 2
            self.trace_max_points = 500
            if hasattr(self, 'mechanism_view') and self.mechanism_view:
                try:
                    self.mechanism_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                except Exception:
                    pass

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

    def toggle_parametric_mode(self, enabled: bool | None = None):
        """Toggle parametric editing mode on/off by delegating to the manager."""
        self.parametric_manager.toggle_parametric_mode(enabled)
        self.parametric_mode_enabled = self.parametric_manager.parametric_mode_enabled
        if self._presenter:
            self._presenter.set_parametric_mode(self.parametric_mode_enabled)
        self._update_all_ui_states()

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

            # Create custom rotation handle with built-in logic
            rotation_handle = self.RotationHandle(
                parent_tab=self,
                mechanism_id=mechanism_id,
                center_pos=center_pos,
                radius=radius
            )

            return rotation_handle

        except Exception as e:
            import traceback
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

        except Exception as e:
            import traceback

        # Create rotation handle at the geometric center
        rotation_handle = self._create_rotation_handle(mechanism_id, mechanism_center, radius=100)

        if rotation_handle:
            # Store the calculated center in the rotation handle for consistent reference
            rotation_handle.true_mechanism_center = mechanism_center

            # Add rotation handle to scene
            self.mechanism_scene.addItem(rotation_handle)
            handles.append(rotation_handle)

            return True
        else:
            return False

    def _recreate_mechanism_visuals(self, mechanism_id: str, layer_data: dict):
        """
        Recreate visual items for a mechanism after parameters have changed.
        """
        try:

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
                # Use centralized visuals factory for cam
                transform_func = self._get_scene_transform_function(mechanism_graphics_data)
                char_pos = self._get_character_position() if hasattr(self, '_get_character_position') else None
                visual_items.extend(self.visuals_factory.create_cam_visuals(mechanism_graphics_data, transform_func, char_pos))
            elif mech_type == "gear":
                visual_items.extend(self._create_gear_visuals(mechanism_graphics_data))
            elif mech_type == "planetary_gear":
                visual_items.extend(self._create_planetary_gear_visuals(mechanism_graphics_data))

            # Store new visual items
            layer_data["visual_items"] = visual_items

        except Exception as e:
            pass

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
            pass

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

        except Exception as e:
            pass

    def _create_gear_handles(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Create handles for gear mechanism with rotation."""
        try:
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

        except Exception as e:
            pass

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
                event.accept()
            else:
                super().mouseReleaseEvent(event)

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
            for mid, mdata in self.mechanism_layers.items():
                pass

            # Find ALL mechanism_ids for this part
            selected_mechanism_ids = []
            for mechanism_id, layer_data in self.mechanism_layers.items():
                mechanism_part = layer_data.get("part_name")
                if mechanism_part == part_name:
                    selected_mechanism_ids.append(mechanism_id)
                else:
                    pass

            if not selected_mechanism_ids:
                # Hide all editors
                self.parametric_editor.set_active_editor(None)
                return

            # FIXED: Properly activate the mechanism for the selected part
            # If multiple mechanisms exist for same part, use the first one
            # But most importantly, activate the correct mechanism for the selected part
            if selected_mechanism_ids:
                # Store the selected part to properly identify its mechanism
                self.selected_part_name = part_name
                # Activate the editor for this part's mechanism
                mechanism_to_activate = selected_mechanism_ids[0]
                self.parametric_editor.set_active_editor(mechanism_to_activate)

        except Exception as e:
            pass

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
                return

            # Find which mechanism this anchor belongs to
            found_mechanism = False
            for mechanism_id, layer_data in self.mechanism_layers.items():
                key_points = layer_data.get("key_points", {})

                if anchor_name in key_points:
                    found_mechanism = True

                    # Update the anchor position in mechanism data
                    to_mech = self._get_inverse_scene_transform_function(layer_data)
                    old_pos = key_points.get(anchor_name)
                    if to_mech:
                        mech_xy = to_mech(new_position)
                        key_points[anchor_name] = [float(mech_xy[0]), float(mech_xy[1])]
                    else:
                        key_points[anchor_name] = [new_position.x(), new_position.y()]

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

                    # Regenerate simulation data for the new configuration
                    self.parametric_manager._regenerate_mechanism_simulation(mechanism_id, layer_data)

                    # Recreate the visual items with new configuration
                    self._recreate_mechanism_visuals(mechanism_id, layer_data)

                    # Update other parametric handles to reflect the new positions
                    self._update_other_handles(mechanism_id, anchor_name)

                    # Force view update
                    self.mechanism_view.update()

                    break

            if not found_mechanism:
                pass

        except Exception as e:
            import traceback

      # Safe fallback

    def _update_handle_positions_from_key_points(self, mechanism_id: str, layer_data: dict):
        """
        Update scene handle positions to match updated key_points after kinematic constraints.

        ULTRATHINK: Prevents infinite recursion by temporarily disabling callbacks.

        Args:
            mechanism_id: Mechanism ID
            layer_data: Layer data with updated key_points
        """
        try:

            # Get handles for this mechanism
            handles = self.parametric_handles.get(mechanism_id, [])
            if not handles:
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

                    updated_count += 1
                else:
                    pass

            # Clear the flag
            self._updating_handles_programmatically = False

        except Exception as e:
            # Make sure to clear the flag even if error occurs
            self._updating_handles_programmatically = False

    @pyqtSlot(str, dict)
    def _on_parametric_mechanism_update(self, mechanism_id: str, params: dict[str, Any]):
        """Handle mechanism update by delegating to the manager."""
        self.parametric_manager._on_parametric_mechanism_update(mechanism_id, params)

    @pyqtSlot(str)
    def _on_parametric_visual_refresh(self, mechanism_id: str):
        """Handle visual refresh by delegating to the manager."""
        self.parametric_manager._on_parametric_visual_refresh(mechanism_id)

    def _update_mechanism_visuals_realtime(self, mechanism_id: str, mechanism_data: dict[str, Any]):
        """Update mechanism visuals in real-time by delegating to the manager."""
        self.parametric_manager._update_mechanism_visuals_realtime(mechanism_id, mechanism_data)

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
                else:
                    pass

        except Exception as e:
            pass

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

        except Exception as e:
            pass

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

        except Exception as e:
            pass

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

        except Exception as e:
            pass

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

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
