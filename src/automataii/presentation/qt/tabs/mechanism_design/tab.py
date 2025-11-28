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
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QLineF, QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainterPath
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QMessageBox,
    QWidget,
)

from automataii.config.z_indices import Z_PART_DEFAULT, Z_SKELETON_OVERLAY
from automataii.application.mechanisms import MechanismService, SkeletonService

# New Visualization System
try:
    from automataii.presentation.qt.mechanisms.visualization import VisualizationAdapter
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    VisualizationAdapter = None

# Parametric Design System
from automataii.presentation.qt.tabs.parametric_editing_manager import ParametricEditingManager

try:
    from automataii.presentation.qt.parametric_editor import ParametricEditor
    PARAMETRIC_AVAILABLE = True
except ImportError:
    PARAMETRIC_AVAILABLE = False

from PyQt6.QtWidgets import QGraphicsPathItem

from automataii.core.models import PartInfo
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
    convert_json_params_to_internal,
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.tabs.mechanism_design.services import (
    AnchorMovementHandler,
    AnchorPositionService,
    AnimationFrameCoordinator,
    HandlePositionCoordinator,
    MechanismInstantiationService,
    SceneManagementService,
    TabCallbackConfigurator,
    TabDataCoordinator,
    TransformService,
    ViewUtilitiesService,
    VisualItemManager,
)
from automataii.domain.kinematics.mechanism import MechanismCandidate
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
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
from automataii.presentation.qt.tabs.mechanism_design.controllers import (
    AnimationModeController,
    LayerSelectionController,
    ParametricModeController,
    RecommendationController,
)

# Domain and Application layer imports (Hexagonal Architecture)
from automataii.domain.kinematics.joint_mapping_service import JointMappingService
from automataii.domain.kinematics.motion_path_generator import MotionPathGenerator
from automataii.application.mechanism_foundry.mechanism_lifecycle_coordinator import (
    MechanismLifecycleCoordinator,
    MechanismLifecycleContext,
)
from automataii.application.mechanism_foundry.mechanism_generation_service import (
    MechanismGenerationService,
    MechanismGenerationContext,
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
        return self._animation_frame_coordinator.trace_frame_tick

    # === STATE DELEGATION TO PRESENTER (Passive View Pattern) ===

    @property
    def mechanism_layers(self) -> dict[str, Any]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.mechanism_layers
        return getattr(self, '_local_mechanism_layers', {})

    @mechanism_layers.setter
    def mechanism_layers(self, value: dict[str, Any]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.mechanism_layers = value
        else:
            self._local_mechanism_layers = value

    @property
    def mechanism_enabled_state(self) -> dict[str, bool]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.mechanism_enabled_state
        return getattr(self, '_local_mechanism_enabled_state', {})

    @mechanism_enabled_state.setter
    def mechanism_enabled_state(self, value: dict[str, bool]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.mechanism_enabled_state = value
        else:
            self._local_mechanism_enabled_state = value

    @property
    def parametric_handles(self) -> dict[str, list]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.parametric_handles
        return getattr(self, '_local_parametric_handles', {})

    @parametric_handles.setter
    def parametric_handles(self, value: dict[str, list]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.parametric_handles = value
        else:
            self._local_parametric_handles = value

    @property
    def path_data(self) -> dict[str, QPainterPath]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.path_data
        return getattr(self, '_local_path_data', {})

    @path_data.setter
    def path_data(self, value: dict[str, QPainterPath]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.path_data = value
        else:
            self._local_path_data = value

    @property
    def part_enabled_state(self) -> dict[str, bool]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.part_enabled_state
        return getattr(self, '_local_part_enabled_state', {})

    @part_enabled_state.setter
    def part_enabled_state(self, value: dict[str, bool]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.part_enabled_state = value
        else:
            self._local_part_enabled_state = value

    @property
    def parts_data(self) -> dict[str, Any]:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            return self._mvp_presenter.parts_data
        return getattr(self, '_local_parts_data', {})

    @parts_data.setter
    def parts_data(self, value: dict[str, Any]) -> None:
        if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
            self._mvp_presenter.parts_data = value
        else:
            self._local_parts_data = value

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.debug_mode = getattr(main_window, "debug_mode", False)

        self.candidates: list[MechanismCandidate] = []
        self.selected_mechanism: MechanismCandidate | None = None
        self.selected_part_name: str | None = None
        self.current_editor_items: dict[str, CharacterPartItem] = {}

        # Non-delegated mechanism state
        self.current_mechanism_type: str | None = None
        self.mechanism_params: dict[str, Any] = {}
        self.path_visual_items: dict[str, QGraphicsPathItem] = {}
        self.mechanism_paths: dict[str, QPainterPath] = {}
        self.mechanism_instances: dict[str, Any] = {}
        self.interactive_handles: dict[str, list[QGraphicsItem]] = {}
        # Delegated to Presenter: mechanism_layers, mechanism_enabled_state,
        # parametric_handles, path_data, part_enabled_state, parts_data

        # Initialize all services (domain, application, presentation)
        self._initialize_services()

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
        
        # Initialize UI state
        self._current_ui_state = UIState()
        self._update_all_ui_states()

        # Initialize extracted components
        self._animation_controller = AnimationLifecycleController(
            mechanism_scene=self.mechanism_scene, path_trace_manager=self._path_trace_manager, parent=self
        )
        self._skeleton_handler = SkeletonVisualizationHandler(
            mechanism_view=self.mechanism_view, mechanism_scene=self.mechanism_scene, parent=self
        )
        self._output_calculator = MechanismOutputCalculator(get_scene_transform=self._get_scene_transform_function)
        self._visual_animator = MechanismVisualAnimator(
            get_scene_transform=self._get_scene_transform_function, set_line_if_changed=self._set_line_if_changed
        )

        # Initialize mode controllers
        self._layer_selection_controller = LayerSelectionController(
            path_trace_manager=self._path_trace_manager, parent=self
        )
        self._parametric_mode_controller = ParametricModeController(parent=self)
        self._recommendation_controller = RecommendationController(parent=self)

        # Configure all service/controller callbacks via configurator
        TabCallbackConfigurator(self).configure_all()

    def _initialize_services(self) -> None:
        """Initialize all domain, application, and presentation services."""
        # Business logic services (Application Layer)
        self.mechanism_service = MechanismService()
        self.skeleton_service = SkeletonService()

        # Domain Layer services
        self._joint_mapping_service = JointMappingService()

        # Application Layer coordinators
        self._lifecycle_coordinator = MechanismLifecycleCoordinator()
        self._motion_path_generator = MotionPathGenerator()
        self._mechanism_generation_service = MechanismGenerationService()

        # Presentation services (extracted from god class)
        self._transform_service = TransformService()
        self._anchor_position_service = AnchorPositionService(self._transform_service)
        self._anchor_movement_handler = AnchorMovementHandler()
        self._visual_item_manager = VisualItemManager()
        self._mechanism_instantiation = MechanismInstantiationService()
        self._mechanism_instantiation.set_path_converter(utils_qpainterpath_to_numpy_array)
        self._handle_position_coordinator = HandlePositionCoordinator()
        self._handle_position_coordinator.set_rotation_handle_class(RotationHandle)
        self._animation_frame_coordinator = AnimationFrameCoordinator(
            ik_update_rate_hz=30, mechanism_update_fraction=0.5, pos_epsilon_px=0.5
        )
        self._tab_data_coordinator = TabDataCoordinator()
        self._scene_management_service = SceneManagementService()
        self._view_utilities_service = ViewUtilitiesService()

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
        # Calculate UI state from presenter or local data
        if self._presenter_view_model is not None:
            parts = self._presenter_view_model.parts
            has_paths = any(part.enabled for part in parts)
            has_mechanisms = any(part.has_layers for part in parts)
            has_enabled_parts = any(part.enabled for part in parts)
        else:
            has_paths = bool(getattr(self, 'path_data', {}))
            has_mechanisms = bool(getattr(self, 'mechanism_layers', {}))
            has_enabled_parts = any(getattr(self, 'part_enabled_state', {}).values())

        ui_state = UIState(
            has_paths=has_paths,
            has_mechanisms=has_mechanisms,
            has_enabled_parts=has_enabled_parts,
            animation_running=self.animation_timer.isActive() if self.animation_timer else False,
            parametric_mode=getattr(self, 'parametric_mode_enabled', False),
            has_parts_data=bool(getattr(self, 'parts_data', {}))
        )

        # Update UI state manager and cache
        if hasattr(self, 'ui_state_manager'):
            self.ui_state_manager.update_button_states(ui_state)
        self._current_ui_state = ui_state

        # Ensure IK connection
        self._connect_to_ik_manager()

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change from EditorView."""

        # Update skeleton manager if available
        if hasattr(self.main_window, 'skeleton_manager') and self.main_window.skeleton_manager:
            self.main_window.skeleton_manager.set_joint_bend_direction(joint_id, new_direction)

    def on_skeleton_manager_updated(self, skeleton_data: dict | None):
        self._skeleton_handler.on_skeleton_manager_updated(skeleton_data)

    def _connect_to_ik_manager(self):
        self._skeleton_handler.connect_to_ik_manager()

    def set_path_data_from_editor(self, path_data: dict[str, QPainterPath]):
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
        self._skeleton_handler.cache_initial_skeleton(skeleton_data_dict)
        self._initial_skeleton_data_cache = self._skeleton_handler.initial_skeleton_data_cache

    def _is_animation_running(self) -> bool:
        return self.animation_timer and self.animation_timer.isActive()

    def on_skeleton_updated(self, skeleton_data: dict | None):
        self._skeleton_handler.on_skeleton_updated(skeleton_data)

    def _update_parts_from_skeleton(self, skeleton_data: dict):
        self._skeleton_handler._update_parts_from_skeleton(skeleton_data)

    def _ensure_skeleton_visualization(self, skeleton_data: dict):
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
        self.selected_mechanism_id = None

        # Update UI
        if self.mechanism_layers_list:
            self.mechanism_layers_list.clear()
        self._update_all_ui_states()

    @pyqtSlot()
    def _on_get_recommendations(self):
        self._recommendation_controller.show_recommendations(self)

    def _get_character_position(self):
        skeleton_data = getattr(self, '_initial_skeleton_data_cache', None)
        return list(self._joint_mapping_service.get_character_ground_position(skeleton_data))

    def _handle_recommendation_selection(self, mechanism_data: dict[str, Any]):
        self._recommendation_controller.handle_recommendation_selection(mechanism_data, self)

    def _clear_mechanism_for_part(self, part_name: str):
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
        """Generate mechanism from candidate. Delegates to MechanismGenerationService."""
        # Clear existing mechanism and traces for current part
        if self.selected_part_name:
            self._clear_mechanism_for_part(self.selected_part_name)
            for mech_id in self._path_trace_manager.get_all_mechanism_ids():
                ld = self.mechanism_layers.get(mech_id)
                if ld and ld.get("part_name") == self.selected_part_name:
                    self._path_trace_manager.clear_trace(mech_id, self.mechanism_scene)

        # Generate mechanism via application service
        context = MechanismGenerationContext(
            selected_part_name=self.selected_part_name or "",
            target_path=self.path_data.get(self.selected_part_name),
            candidate_data=candidate_data,
            parts_data=self.parts_data,
            skeleton_cache=getattr(self, '_initial_skeleton_data_cache', None),
        )
        result = self._mechanism_generation_service.generate_mechanism(context)

        if not result.success or not result.layer_data:
            return

        # Add layer and generate visuals (presentation concerns)
        layer_data = result.layer_data
        self._add_mechanism_layer(self.selected_part_name, layer_data)
        self.mechanism_enabled_state[result.mechanism_id] = True
        self._generate_mechanism_visuals_directly(
            result.mechanism_id, layer_data["type"], layer_data["params"], layer_data
        )

        # Ensure parts data and update UI
        if not self.current_editor_items and self.parts_data:
            current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts_data:
                self.set_parts_data(current_parts_data)

        self._update_all_ui_states()
        self._select_part_in_list(layer_data.get("part_name"))

    def _select_part_in_list(self, part_name: str | None) -> None:
        """Select a part in the mechanism layers list."""
        if not part_name or not self.mechanism_layers_list:
            return
        for i in range(self.mechanism_layers_list.count()):
            item = self.mechanism_layers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == part_name:
                self.mechanism_layers_list.setCurrentItem(item)
                break

    def _add_mechanism_layer(self, layer_name: str, layer_data: Any):
        """Add a mechanism layer to the internal data structure."""
        mechanism_id = layer_data["id"]
        self.mechanism_layers[mechanism_id] = layer_data

        # Initialize path tracing and update UI
        self._path_trace_manager.init_trace(mechanism_id, self.mechanism_scene)
        self._update_mechanism_layers_list()
        self._update_all_ui_states()

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
        """Clear animation caches. Delegates to AnimationFrameCoordinator."""
        self._animation_frame_coordinator.clear_animation_cache(self)

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
        self._layer_selection_controller.on_selection_changed()

    def _on_layer_item_clicked(self, item):
        self._layer_selection_controller.on_item_clicked(item)

    def _update_part_visibility_and_animation(self, part_name: str, enabled: bool):
        self._layer_selection_controller.update_part_visibility_and_animation(part_name, enabled)

    def _toggle_mechanism_visuals(self, part_name: str, enabled: bool):
        self._layer_selection_controller.toggle_mechanism_visuals(part_name, enabled)


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
        """Apply performance preset. Delegates to AnimationFrameCoordinator."""
        view_hints = self._animation_frame_coordinator.apply_performance_preset(preset)

        # Apply view-specific hints
        if hasattr(self, 'mechanism_view') and self.mechanism_view:
            self._view_utilities_service.apply_render_hints(
                self.mechanism_view,
                antialiasing=view_hints.get("antialiasing", True),
            )

        # Update trace settings
        if "trace_stride" in view_hints:
            self.trace_update_stride = view_hints["trace_stride"]
        if "trace_max_points" in view_hints:
            self.trace_max_points = view_hints["trace_max_points"]

    def _generate_joint_motion_path(self, layer_data: dict, joint_id: str) -> QPainterPath | None:
        """Delegate to domain service (Hexagonal Architecture)."""
        return self._motion_path_generator.generate_joint_motion_path(
            layer_data, joint_id, self._calculate_mechanism_output
        )

    # PARAMETRIC DESIGN SYSTEM

    def toggle_parametric_mode(self, enabled: bool | None = None):
        self.parametric_mode_enabled = self._parametric_mode_controller.toggle_mode(enabled)

    def _recreate_mechanism_visuals(self, mechanism_id: str, layer_data: dict):
        try:
            self._safe_remove_visual_items(layer_data.get("visual_items", []))
            mechanism_graphics_data = {"mechanism_id": mechanism_id, **layer_data}
            self.handle_mechanism_visuals(mechanism_graphics_data)
        except Exception:
            pass

    def _update_other_handles(self, mechanism_id: str, moved_handle: str):
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
        if mechanism_id not in self.parametric_handles:
            return
        handles = self.parametric_handles[mechanism_id]
        self._visual_item_manager.show_free_edit_feedback(handles, self.mechanism_scene)

    def _create_gear_handles(self, mechanism_id: str, layer_data: dict[str, Any]):
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
        self._parametric_mode_controller.update_handles_for_selection(part_name)

    def _hide_all_parametric_handles(self):
        self._parametric_mode_controller.hide_all_handles()

    def _update_handle_positions_from_key_points(self, mechanism_id: str, layer_data: dict):
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
        self.parametric_manager._on_parametric_mechanism_update(mechanism_id, params)

    @pyqtSlot(str)
    def _on_parametric_visual_refresh(self, mechanism_id: str):
        self.parametric_manager._on_parametric_visual_refresh(mechanism_id)

    def _update_mechanism_visuals_realtime(self, mechanism_id: str, mechanism_data: dict[str, Any]):
        self.parametric_manager._update_mechanism_visuals_realtime(mechanism_id, mechanism_data)

    def _update_handle_positions_for_mechanism(self, mechanism_id: str, layer_data: dict[str, Any]):
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
        return self._anchor_position_service.get_anchor_positions(layer_data)

    def _disable_mechanism_visual_interaction(self):
        self._visual_item_manager.disable_mechanism_visual_interaction(self.mechanism_layers)

    def _enable_mechanism_visual_interaction(self):
        self._visual_item_manager.enable_mechanism_visual_interaction(self.mechanism_layers)

        # Re-enable animation controls if we have enabled mechanisms
        has_enabled_mechanisms = any(self.mechanism_enabled_state.values()) if self.mechanism_enabled_state else False
        if self.mechanism_layers and has_enabled_mechanisms:
            self.play_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)

    def _on_export_blueprint(self):
        self.blueprint_exporter.export_all()

    def center_on_character(self):
        if not self.mechanism_view:
            return
        self._view_utilities_service.center_view_on_character(
            self.mechanism_view,
            current_editor_items=self.current_editor_items,
            skeleton_joint_items=getattr(self, 'skeleton_joint_items', None),
        )

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
