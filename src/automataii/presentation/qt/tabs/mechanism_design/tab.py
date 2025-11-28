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
from PyQt6.QtCore import QLineF, QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF, QPainter
from PyQt6 import sip
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
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

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsScene

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
from automataii.presentation.qt.tabs.mechanism_design.services import (
    AnchorMovementHandler,
    AnchorPositionService,
    AnimationFrameCoordinator,
    HandlePositionCoordinator,
    MechanismInstantiationService,
    SceneManagementService,
    TabDataCoordinator,
    TransformService,
    VisualItemManager,
)
from automataii.presentation.qt.views.editor_view import EditorView
from automataii.domain.kinematics.mechanism import (
    MechanismCandidate,
)
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_ui import MechanismDesignUI
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_layout import MechanismDesignTabLayout
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_ui_state import (
    MechanismDesignTabUIState, UIState,
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
from automataii.presentation.qt.tabs.mechanism_design.handles import RotationHandle
from automataii.presentation.qt.tabs.mechanism_design.presenter import MechanismDesignPresenter

# Domain and Application layer imports (Hexagonal Architecture)
from automataii.domain.kinematics.joint_mapping_service import JointMappingService
from automataii.application.mechanism_foundry.mechanism_lifecycle_coordinator import (
    MechanismLifecycleCoordinator,
    MechanismLifecycleContext,
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

    # Mapping from display names to internal mechanism types (extracted from duplicates)
    MECHANISM_TYPE_MAPPING: dict[str, str] = {
        "4-Bar Linkage": "4_bar_linkage",
        "4-bar Coupler": "4_bar_linkage",
        "Cam & Follower": "cam",
        "Cam-Follower": "cam",
        "Gears (Simple Pair)": "gear",
        "Gear Contact": "gear",
        "Simple Gear": "gear",
        "Planetary Gear": "planetary_gear",
    }

    # Properties delegating to AnimationFrameCoordinator (god class decomposition)
    @property
    def animation_time(self) -> float:
        """Current animation time. Delegates to AnimationFrameCoordinator."""
        return self._animation_frame_coordinator.animation_time

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set animation time."""
        self._animation_frame_coordinator.animation_time = value

    @property
    def animation_speed(self) -> float:
        """Animation speed. Delegates to AnimationFrameCoordinator."""
        return self._animation_frame_coordinator.animation_speed

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed."""
        self._animation_frame_coordinator.animation_speed = value

    @property
    def _trace_frame_tick(self) -> int:
        """Frame tick for path tracing. Delegates to AnimationFrameCoordinator."""
        return self._animation_frame_coordinator.trace_frame_tick

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

        # Business logic services (Application Layer)
        self.mechanism_service = MechanismService()
        self.skeleton_service = SkeletonService()

        # Domain Layer services (Hexagonal Architecture)
        self._joint_mapping_service = JointMappingService()

        # Application Layer coordinators (Hexagonal Architecture)
        self._lifecycle_coordinator = MechanismLifecycleCoordinator()

        # Extracted services (god class decomposition)
        self._transform_service = TransformService()
        self._anchor_position_service = AnchorPositionService(self._transform_service)
        self._anchor_movement_handler = AnchorMovementHandler()
        self._visual_item_manager = VisualItemManager()
        self._mechanism_instantiation = MechanismInstantiationService()
        self._mechanism_instantiation.set_path_converter(utils_qpainterpath_to_numpy_array)
        self._handle_position_coordinator = HandlePositionCoordinator()
        self._handle_position_coordinator.set_rotation_handle_class(self.RotationHandle)
        self._animation_frame_coordinator = AnimationFrameCoordinator(
            ik_update_rate_hz=30,
            mechanism_update_fraction=0.5,
            pos_epsilon_px=0.5,
        )
        self._tab_data_coordinator = TabDataCoordinator()
        self._scene_management_service = SceneManagementService()

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

        # Animation state (timer connects to coordinator via _update_animation)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.animating_mechanisms = {}  # Store original positions for animation

        # Animation time/speed properties delegate to coordinator
        # Kept for backward compatibility with external access

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

        # MVP Presenter (god class decomposition - Phase 2)
        # Presenter owns business state and coordinates services
        # Tab remains a thin UI wrapper (Passive View pattern)
        self._mvp_presenter = MechanismDesignPresenter(tab=self, parent=self)

        # Performance controls (Phase 0 quick wins)

        # Initialize new visualization system if available
        self.visualization_adapter: VisualizationAdapter | None = None
        if VISUALIZATION_AVAILABLE:
            self.visualization_adapter = VisualizationAdapter(self.mechanism_scene)

        # PHASE 1 REFACTORING: Use new UI management system
        # UI setup with new layout manager
        self.layout_manager = MechanismDesignTabLayout()
        self.layout_manager.setup_main_layout(self)
        
        # Get all created widgets
        self.ui_widgets = self.layout_manager.get_all_widgets()
        
        # Initialize mechanism visuals factory now that scene is created
        self.visuals_factory = MechanismVisualsFactory(self.mechanism_scene)

        # Wire MVP Presenter to scene (now that UI is initialized)
        self._mvp_presenter._scene = self.mechanism_scene

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

        # PHASE 8: Configure anchor movement handler callbacks
        self._configure_anchor_movement_callbacks()

        # PHASE 9: Configure animation frame coordinator callbacks
        self._configure_animation_frame_coordinator()

        # PHASE 10: Configure tab data coordinator callbacks
        self._configure_tab_data_coordinator()

        # PHASE 11: Configure scene management service callbacks
        self._configure_scene_management_service()

    def _configure_anchor_movement_callbacks(self) -> None:
        """Configure callbacks for the anchor movement handler."""
        self._anchor_movement_handler.configure_callbacks(
            on_params_updated=lambda mid, ld: self.parametric_manager._regenerate_mechanism_simulation(mid, ld),
            on_visuals_recreate=self._recreate_mechanism_visuals,
            on_handles_update=self._update_other_handles,
            on_view_refresh=self.mechanism_view.update,
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

    def _configure_animation_frame_coordinator(self) -> None:
        """Configure callbacks for the animation frame coordinator (god class decomposition)."""
        self._animation_frame_coordinator.configure_callbacks(
            calculate_output=self._calculate_mechanism_output,
            get_target_joint=self._get_target_joint_for_mechanism_control,
            get_standardized_joint=self._get_standardized_joint_id,
            update_visuals=self._update_mechanism_visuals_for_animation,
            stop_timer=self.animation_timer.stop,
        )

    def _configure_tab_data_coordinator(self) -> None:
        """Configure callbacks for the tab data coordinator (god class decomposition)."""
        self._tab_data_coordinator.configure_callbacks(
            clear_mechanism_for_part=self._clear_mechanism_for_part,
            part_has_mechanism=self._part_has_mechanism,
        )

    def _configure_scene_management_service(self) -> None:
        """Configure callbacks for the scene management service (god class decomposition)."""
        self._scene_management_service.configure_callbacks(
            is_visual_item_invalid=self._is_visual_item_invalid,
            safe_remove_visual_items=self._safe_remove_visual_items,
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
        """Receive path data from editor tab. Delegates to TabDataCoordinator (god class decomposition)."""
        # Presenter integration
        if self._presenter:
            converted_paths = convert_paths(path_data or {})
            self._presenter.update_paths(converted_paths)

        # Delegate data processing to coordinator
        self.path_data = self._tab_data_coordinator.set_path_data_from_editor(
            path_data,
            current_path_data=self.path_data,
            part_enabled_state=self.part_enabled_state,
            mechanism_layers=self.mechanism_layers,
            scene=self.mechanism_scene,
            update_ui_fn=self._update_all_ui_states,
        )

        # Update tooltip
        if self.path_data:
            part_names = ", ".join(list(self.path_data.keys())[:3])
            if len(self.path_data) > 3:
                part_names += f", ... ({len(self.path_data)} total)"
            if self.recommendation_btn:
                self.recommendation_btn.setToolTip(f"Parts with paths: {part_names}")
        else:
            if self.recommendation_btn:
                self.recommendation_btn.setToolTip("No motion paths available")

        # Update mechanism layers list
        self._update_mechanism_layers_list()

    def set_parts_data(self, parts_data: dict[str, PartInfo]):
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
        """Delegate to domain service (Hexagonal Architecture)."""
        return self._joint_mapping_service.get_target_joint(part_name, anchor_joint_id)

    def _setup_mechanism_ik_integration(self):
        """Setup integration between mechanism animation and IK system."""
        ik_manager = getattr(self.main_window, 'ik_manager', None)
        if not ik_manager:
            return False

        context = MechanismLifecycleContext(
            mechanism_layers=self.mechanism_layers,
            mechanism_enabled_state=self.mechanism_enabled_state,
            parts_data=self.parts_data,
            skeleton_cache=getattr(self, '_initial_skeleton_data_cache', None),
        )

        return self._lifecycle_coordinator.setup_ik_integration(
            ik_manager=ik_manager,
            context=context,
            register_controller_fn=self._register_mechanism_controller,
        )

    def _register_mechanism_controller(self, mech_id: str, layer_data: dict, joint_id: str):
        """Register mechanism as IK controller. Delegates to application coordinator."""
        ik_manager = getattr(self.main_window, 'ik_manager', None)
        if not ik_manager:
            return

        # Generate motion path callback
        joint_motion_path = self._generate_joint_motion_path(layer_data, joint_id)
        if joint_motion_path and hasattr(ik_manager, 'set_joint_motion_path'):
            ik_manager.set_joint_motion_path(joint_id, joint_motion_path)
            part_name = layer_data.get("part_name")
            if part_name and hasattr(ik_manager, 'set_part_motion_path'):
                ik_manager.set_part_motion_path(part_name, joint_motion_path)

        # Register controller callback
        def mechanism_callback(time: float) -> QPointF | None:
            return self._calculate_mechanism_output(
                layer_data.get("type"), layer_data.get("params", {}), time, layer_data
            )

        if hasattr(ik_manager, 'register_mechanism_controller'):
            ik_manager.register_mechanism_controller(joint_id, mech_id, mechanism_callback)

        # Enable IK for affected part
        part_name = layer_data.get("part_name")
        if part_name and hasattr(ik_manager, 'enable_ik_for_part'):
            ik_manager.enable_ik_for_part(part_name, True)

    def clear_mechanism_data(self):
        """Clear all mechanism-related data. Delegates to SceneManagementService (god class decomposition)."""
        # Stop animation
        if self.animation_timer.isActive():
            self.animation_timer.stop()
        self._animation_frame_coordinator.reset_state()

        # Delegate core clearing to service
        ik_manager = getattr(self.main_window, 'ik_manager', None)
        self._scene_management_service.clear_mechanism_data(
            mechanism_layers=self.mechanism_layers,
            mechanism_enabled_state=self.mechanism_enabled_state,
            path_visual_items=self.path_visual_items,
            mechanism_path_items=self.mechanism_path_items,
            mechanism_instances=self.mechanism_instances,
            parametric_handles=self.parametric_handles,
            interactive_handles=self.interactive_handles,
            path_trace_manager=self._path_trace_manager,
            scene=self.mechanism_scene,
            ik_manager=ik_manager,
        )

        # Clear additional local data
        self.path_data.clear()
        self.selected_part_name = None
        self.mechanism_path_points.clear()
        self.current_editor_items.clear()
        self.parts_data.clear()

        # Clear UI elements
        if self.mechanism_layers_list:
            self.mechanism_layers_list.clear()

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
        """Delegate to domain service (Hexagonal Architecture)."""
        skeleton_data = getattr(self, '_initial_skeleton_data_cache', None)
        return list(self._joint_mapping_service.get_character_ground_position(skeleton_data))

    def _handle_recommendation_selection(self, mechanism_data: dict[str, Any]):
        """Handle mechanism selection from recommendation dialog.
        Delegates to MechanismInstantiationService (god class decomposition)."""
        # Get target path for this part
        target_path = None
        if hasattr(self, 'selected_part_name') and self.selected_part_name:
            target_path = self.path_data.get(self.selected_part_name)

        # Fallback: create path from coordinates if no user path
        if not target_path:
            path_coords = mechanism_data.get("path_coordinates")
            if path_coords and isinstance(path_coords, list) and len(path_coords) > 0:
                target_path = QPainterPath()
                target_path.moveTo(path_coords[0][0], path_coords[0][1])
                for coord in path_coords[1:]:
                    target_path.lineTo(coord[0], coord[1])

        # Create layer and graphics data via service
        layer_data, graphics_data = self._mechanism_instantiation.create_layer_data_from_recommendation(
            mechanism_data=mechanism_data,
            target_path=target_path,
            fallback_position=self._get_character_position(),
        )

        # Add mechanism layer and create visuals
        self._add_mechanism_layer(graphics_data["name"], layer_data)
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
        internal_type = self.MECHANISM_TYPE_MAPPING.get(mechanism_type_value, "4_bar_linkage")

        if internal_type == "4_bar_linkage":
            visual_items = self._create_4bar_linkage_visuals(mechanism_data)
            self._preview_items.extend(visual_items)

    def _clear_mechanism_for_part(self, part_name: str):
        """Clear mechanism for a specific part. Delegates to application coordinator."""
        self._clear_animation_cache()

        def on_visual_cleanup(mech_id: str, layer_data: dict) -> None:
            visual_items = layer_data.get("visual_items", [])
            self._safe_remove_visual_items(visual_items)
            self._path_trace_manager.clear_trace(mech_id, self.mechanism_scene)

        self._lifecycle_coordinator.clear_mechanism_for_part(
            part_name,
            mechanism_layers=self.mechanism_layers,
            mechanism_enabled_state=self.mechanism_enabled_state,
            on_visual_cleanup=on_visual_cleanup,
        )

        # Clear path items for this part
        if part_name in self.mechanism_path_items:
            path_item = self.mechanism_path_items[part_name]
            if path_item and path_item.scene():
                self.mechanism_scene.removeItem(path_item)
            del self.mechanism_path_items[part_name]

    def _generate_mechanism_from_candidate(self, candidate_data: dict[str, Any]):
        """Generates a mechanism layer and visuals from a selected candidate.
        Uses MechanismInstantiationService for layer creation (god class decomposition)."""
        # Clear existing mechanism for current part
        if hasattr(self, 'selected_part_name') and self.selected_part_name:
            self._clear_mechanism_for_part(self.selected_part_name)
            # Clear old trace paths for this part
            for mechanism_id in self._path_trace_manager.get_all_mechanism_ids():
                ld = self.mechanism_layers.get(mechanism_id)
                if ld and ld.get("part_name") == self.selected_part_name:
                    self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)

        # Create layer data via service
        target_path = self.path_data.get(self.selected_part_name) if self.selected_part_name else None
        layer_data = self._mechanism_instantiation.create_layer_data_from_candidate(
            candidate_data=candidate_data,
            selected_part_name=self.selected_part_name or "",
            target_path=target_path,
            convert_params_fn=convert_json_params_to_internal,
            extract_key_points_fn=self._extract_key_points_from_simulation,
        )

        # Verify and adjust coupler point connection
        self._verify_coupler_joint_connection(layer_data)
        self._adjust_mechanism_to_target_joint(layer_data)

        # Add layer and generate visuals
        mechanism_id = layer_data["id"]
        internal_type = layer_data["type"]
        params = layer_data["params"]

        self._add_mechanism_layer(self.selected_part_name, layer_data)
        self.mechanism_enabled_state[mechanism_id] = True
        self._generate_mechanism_visuals_directly(mechanism_id, internal_type, params, layer_data)

        # Ensure parts data for blueprint export
        if not self.current_editor_items and self.parts_data:
            current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts_data:
                self.set_parts_data(current_parts_data)

        self._update_all_ui_states()

        # Select the part in the list
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

    def _update_animation(self):
        """Update animation frame. Delegates to AnimationFrameCoordinator (god class decomposition)."""
        ik_manager = getattr(self.main_window, 'ik_manager', None)
        skeleton_cache = getattr(self, '_initial_skeleton_data_cache', None)

        self._animation_frame_coordinator.update_frame(
            tab_active=self._tab_active,
            mechanism_layers=self.mechanism_layers,
            part_enabled_state=self.part_enabled_state,
            parts_data=self.parts_data,
            ik_manager=ik_manager,
            path_trace_manager=self._path_trace_manager,
            scene=self.mechanism_scene,
            initial_skeleton_cache=skeleton_cache,
        )

    def _get_standardized_joint_id(self, abstract_joint_id: str) -> str | None:
        """Delegate standardization, with skeleton cache fallback."""
        # First try domain service standardization
        std_id = self._joint_mapping_service.standardize_joint_id(abstract_joint_id)
        if std_id and self._initial_skeleton_data_cache:
            if std_id in self._initial_skeleton_data_cache.get("joints", {}):
                return std_id
        # Check skeleton cache joint_map
        if self._initial_skeleton_data_cache:
            joint_map = self._initial_skeleton_data_cache.get("joint_map", {})
            if abstract_joint_id in joint_map:
                return joint_map[abstract_joint_id]
            if abstract_joint_id in self._initial_skeleton_data_cache.get("joints", {}):
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

    def _update_mechanism_layers_list(self):
        """Update the mechanism layers list. Delegates to TabDataCoordinator (god class decomposition)."""
        mechanism_layers_list = self.ui_widgets.get('mechanism_layers_list') if hasattr(self, 'ui_widgets') else None
        self._tab_data_coordinator.update_mechanism_layers_list(
            mechanism_layers_list,
            presenter_view_model=self._presenter_view_model,
            part_enabled_state=self.part_enabled_state,
            main_window=self.main_window,
        )

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
        """Reset skeleton to initial state. Delegates to application coordinator."""
        ik_manager = getattr(self.main_window, 'ik_manager', None)
        self.animation_time = 0

        # Delegate IK reset to application layer
        def on_skeleton_reset(skeleton_data: dict) -> None:
            self._position_parts_at_anchor_joints()
            self.on_skeleton_updated(skeleton_data)
            if hasattr(self.mechanism_view, 'skeleton_graphics_item') and self.mechanism_view.skeleton_graphics_item:
                self.mechanism_view.skeleton_graphics_item.update()

        self._lifecycle_coordinator.reset_skeleton_state(
            ik_manager=ik_manager,
            skeleton_cache=self._initial_skeleton_data_cache,
            animation_timer=self.animation_timer,
            on_skeleton_reset=on_skeleton_reset,
        )

        # Fallback: try to get from skeleton manager if no cache
        if not self._initial_skeleton_data_cache:
            skeleton_mgr = getattr(self.main_window, 'skeleton_manager', None)
            if skeleton_mgr:
                initial_skeleton = skeleton_mgr.get_current_skeleton_data()
                if initial_skeleton:
                    self.cache_initial_skeleton(initial_skeleton)
                    on_skeleton_reset(initial_skeleton)

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
        """Safely remove visual items from scene.
        Delegates to VisualItemManager (god class decomposition)."""
        self._visual_item_manager.set_scene_cleared_flag(
            getattr(self, '_scene_recently_cleared', False)
        )
        self._visual_item_manager.safe_remove_visual_items(visual_items)

    def cleanup_tab_resources(self):
        """Clean up resources when switching away from mechanism tab.

        Delegates to MVP Presenter (god class decomposition).
        """
        self._mvp_presenter._cleanup_resources()

    def prepare_tab_activation(self):
        """Prepare tab for activation when switching back to mechanism tab.

        Delegates to MVP Presenter (god class decomposition).
        """
        self._mvp_presenter._prepare_activation()

    def _is_visual_item_invalid(self, item) -> bool:
        """Check if a visual item is invalid.
        Delegates to VisualItemManager (god class decomposition)."""
        return self._visual_item_manager.is_visual_item_invalid(item)

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
        Delegates to HandlePositionCoordinator (god class decomposition).
        """
        handles = self.parametric_handles.get(mechanism_id, []) if hasattr(self, 'parametric_handles') else []
        layer_data = self.mechanism_layers.get(mechanism_id)
        if not handles or not layer_data:
            return

        self._handle_position_coordinator.update_other_handles(
            mechanism_id=mechanism_id,
            moved_handle=moved_handle,
            handles=handles,
            layer_data=layer_data,
            transform_fn=self._get_scene_transform_function,
        )
        # Ensure all handles are correct relative to full key_points state
        self._update_handle_positions_from_key_points(mechanism_id, layer_data)

    def _show_free_edit_feedback(self, mechanism_id: str):
        """Show visual feedback for free editing mode.
        Delegates to VisualItemManager (god class decomposition)."""
        if mechanism_id not in self.parametric_handles:
            return
        handles = self.parametric_handles[mechanism_id]
        self._visual_item_manager.show_free_edit_feedback(handles, self.mechanism_scene)

    def _create_gear_handles(self, mechanism_id: str, layer_data: dict[str, Any]):
        """Create handles for gear mechanism with rotation.
        Delegates to HandlePositionCoordinator (god class decomposition)."""
        handles = self._handle_position_coordinator.create_gear_handles(
            mechanism_id=mechanism_id,
            layer_data=layer_data,
            scene=self.mechanism_scene,
            add_rotation_handle_fn=self._add_rotation_handle_to_mechanism,
        )
        if handles:
            self.parametric_handles[mechanism_id] = handles
            self.mechanism_scene.update()

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

    def _update_handle_positions_from_key_points(self, mechanism_id: str, layer_data: dict):
        """
        Update scene handle positions to match updated key_points after kinematic constraints.
        Delegates to HandlePositionCoordinator (god class decomposition).

        Args:
            mechanism_id: Mechanism ID
            layer_data: Layer data with updated key_points
        """
        handles = self.parametric_handles.get(mechanism_id, [])
        if not handles:
            return

        self._handle_position_coordinator.update_handles_from_key_points(
            mechanism_id=mechanism_id,
            handles=handles,
            layer_data=layer_data,
            transform_fn=self._get_scene_transform_function,
        )

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
        Delegates to HandlePositionCoordinator (god class decomposition).

        Args:
            mechanism_id: Mechanism ID
            layer_data: Current mechanism data
        """
        handles = self.parametric_handles.get(mechanism_id, [])
        if not handles:
            return

        anchor_positions = self._get_anchor_positions_for_mechanism(layer_data)
        self._handle_position_coordinator.update_handles_for_mechanism(
            mechanism_id=mechanism_id,
            handles=handles,
            layer_data=layer_data,
            anchor_positions=anchor_positions,
        )

    def _get_anchor_positions_for_mechanism(self, layer_data: dict[str, Any]) -> dict[str, QPointF]:
        """
        Get anchor positions for mechanism handles.
        Delegates to AnchorPositionService (god class decomposition).

        Args:
            layer_data: Mechanism layer data

        Returns:
            Dictionary mapping anchor names to QPointF positions
        """
        return self._anchor_position_service.get_anchor_positions(layer_data)

    def _disable_mechanism_visual_interaction(self):
        """Disable mouse interaction on mechanism visual items.
        Delegates to VisualItemManager (god class decomposition)."""
        self._visual_item_manager.disable_mechanism_visual_interaction(self.mechanism_layers)

    def _enable_mechanism_visual_interaction(self):
        """Re-enable mouse interaction on mechanism visual items.
        Delegates to VisualItemManager (god class decomposition)."""
        self._visual_item_manager.enable_mechanism_visual_interaction(self.mechanism_layers)

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
