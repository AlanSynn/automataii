"""Mechanism Design Tab - MVP View for mechanism design and animation."""
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainterPath
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QMessageBox,
    QWidget,
)

from automataii.application.mechanisms import MechanismService, SkeletonService
from automataii.config.z_indices import Z_PART_DEFAULT, Z_SKELETON_OVERLAY

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

from automataii.application.mechanism_foundry.mechanism_generation_service import (
    MechanismGenerationService,
)
from automataii.application.mechanism_foundry.mechanism_lifecycle_coordinator import (
    MechanismLifecycleCoordinator,
)
from automataii.presentation.qt.models import PartInfo

# Domain and Application layer imports (Hexagonal Architecture)
from automataii.domain.kinematics.joint_mapping_service import JointMappingService
from automataii.domain.kinematics.mechanism import MechanismCandidate
from automataii.domain.kinematics.motion_path_generator import MotionPathGenerator
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.tabs.mechanism_design.components import (
    AnimationLifecycleController,
    MechanismOutputCalculator,
    MechanismVisualAnimator,
    SkeletonVisualizationHandler,
)
from automataii.presentation.qt.tabs.mechanism_design.controller_adapter import (
    build_presenter,
    convert_paths,
)
from automataii.presentation.qt.tabs.mechanism_design.controller_adapter import (
    feature_enabled as controller_feature_enabled,
)
from automataii.presentation.qt.tabs.mechanism_design.controllers import (
    LayerSelectionController,
    ParametricModeController,
    RecommendationController,
)
from automataii.presentation.qt.tabs.mechanism_design.handles import RotationHandle
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_layout import (
    MechanismDesignTabLayout,
)
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_signals import (
    MechanismDesignTabSignals,
)
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_ui_state import (
    MechanismDesignTabUIState,
    UIState,
)
from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_utils import (
    qpainterpath_to_numpy_array as utils_qpainterpath_to_numpy_array,
)
from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import (
    PathTraceConfig,
    PathTraceManager,
)
from automataii.presentation.qt.tabs.mechanism_design.presenter import MechanismDesignPresenter
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
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory


class MechanismDesignTab(QWidget):
    """MVP View for mechanism design. Delegates business logic to Presenter."""

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
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.animation_time
        return 0.0

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set animation time."""
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            self._animation_frame_coordinator.animation_time = value

    @property
    def animation_speed(self) -> float:
        """Animation speed. Delegates to AnimationFrameCoordinator."""
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.animation_speed
        return 1.0

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed."""
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            self._animation_frame_coordinator.animation_speed = value

    @property
    def _trace_frame_tick(self) -> int:
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.trace_frame_tick
        return 0

    # === STATE DELEGATION TO PRESENTER (Passive View Pattern) ===
    # These attributes are delegated to _mvp_presenter when available
    _DELEGATED_ATTRS = frozenset({
        'mechanism_layers', 'mechanism_enabled_state', 'parametric_handles',
        'path_data', 'part_enabled_state', 'parts_data'
    })

    def __getattr__(self, name: str):
        if name in MechanismDesignTab._DELEGATED_ATTRS:
            if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
                return getattr(self._mvp_presenter, name)
            return getattr(self, f'_local_{name}', {})
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value) -> None:
        if name in MechanismDesignTab._DELEGATED_ATTRS:
            if hasattr(self, '_mvp_presenter') and self._mvp_presenter:
                setattr(self._mvp_presenter, name, value)
            else:
                super().__setattr__(f'_local_{name}', value)
        else:
            super().__setattr__(name, value)

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

        # Tab lifecycle state
        self._tab_visible = False
        self._tab_active = False
        self._scene_recently_cleared = False

        # Feature-flagged presenter
        self._presenter = None
        self._presenter_view_model = None
        if controller_feature_enabled():
            self._presenter = build_presenter(self)
            self._presenter.add_view_listener(self._on_presenter_view_update)

        # Parametric system
        self.parametric_editor: ParametricEditor | None = None
        self.parametric_mode_enabled = False
        self.parametric_manager = ParametricEditingManager(self)

        # Path trace manager
        self._path_trace_manager = PathTraceManager(
            config=PathTraceConfig(max_points=500, update_stride=5, pen_color=QColor(255, 0, 0, 150), pen_width=2.0, z_value=100)
        )
        # Note: _trace_frame_tick is a read-only property delegated to _animation_frame_coordinator

        # MVP Presenter (initialized before scene, scene assigned after layout)
        self._mvp_presenter = MechanismDesignPresenter(tab=self, parent=self)

        # UI setup - creates mechanism_scene and mechanism_view
        self.layout_manager = MechanismDesignTabLayout()
        self.layout_manager.setup_main_layout(self)
        self.ui_widgets = self.layout_manager.get_all_widgets()

        # Now mechanism_scene is available - initialize dependent components
        self.visualization_adapter: VisualizationAdapter | None = None
        if VISUALIZATION_AVAILABLE:
            self.visualization_adapter = VisualizationAdapter(self.mechanism_scene)
        self.visuals_factory = MechanismVisualsFactory(self.mechanism_scene)
        self._mvp_presenter._scene = self.mechanism_scene

        # Connect MVP presenter signals
        self._mvp_presenter.view_update_requested.connect(self._handle_mvp_view_update)

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

        # Backward compatibility: UI element references
        for name in ('blueprint_btn', 'recommendation_btn', 'mechanism_layers_list', 'play_btn',
                     'stop_btn', 'reset_btn', 'parametric_edit_btn', 'zoom_in_btn', 'zoom_out_btn',
                     'zoom_fit_btn', 'center_character_btn', 'blueprint_info_label'):
            setattr(self, name, self.ui_widgets.get(name))

        # Connect all signals using new signal manager
        self.signal_manager.connect_all_signals(self)

        # Initialize parametric system now that mechanism_scene is available
        if PARAMETRIC_AVAILABLE:
            self.parametric_manager._initialize_parametric_system()

        # Initialize extracted components (must be before _update_all_ui_states)
        self._animation_controller = AnimationLifecycleController(
            mechanism_scene=self.mechanism_scene, path_trace_manager=self._path_trace_manager, parent=self
        )
        self._skeleton_handler = SkeletonVisualizationHandler(
            mechanism_view=self.mechanism_view, mechanism_scene=self.mechanism_scene, parent=self
        )
        self._output_calculator = MechanismOutputCalculator(get_scene_transform=self._get_scene_transform_function)
        self._visual_animator = MechanismVisualAnimator(get_scene_transform=self._get_scene_transform_function)

        # Initialize mode controllers
        self._layer_selection_controller = LayerSelectionController(
            path_trace_manager=self._path_trace_manager, parent=self
        )
        self._parametric_mode_controller = ParametricModeController(parent=self)
        self._recommendation_controller = RecommendationController(parent=self)

        # Configure all service/controller callbacks via configurator
        TabCallbackConfigurator(self).configure_all()

        # Initialize UI state (after all components are ready)
        self._current_ui_state = UIState()
        self._update_all_ui_states()

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

    def _handle_mvp_view_update(self, update_type: str, data: object) -> None:
        """Handle view_update_requested signal from MVP presenter.

        Routes update types to appropriate handler methods.

        Args:
            update_type: Type of update ('generate_mechanism_visuals', etc.)
            data: Update data payload
        """
        import logging
        logging.debug(f"MechanismDesignTab: _handle_mvp_view_update: {update_type}")

        if not isinstance(data, dict):
            data = {}

        if update_type == 'generate_mechanism_visuals':
            # Route to mechanism visuals handler (new mechanism created)
            self.handle_mechanism_visuals(data)

        elif update_type == 'regenerate_visuals':
            # Regenerate visuals for existing mechanism
            mechanism_id = data.get('mechanism_id')
            layer_data = data.get('layer_data') or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._generate_mechanism_visuals_directly(
                    mechanism_id,
                    layer_data.get('type', ''),
                    layer_data.get('params', {}),
                    layer_data
                )

        elif update_type == 'recreate_visuals':
            # Recreate visuals after parameter change
            mechanism_id = data.get('mechanism_id')
            layer_data = data.get('layer_data') or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._recreate_mechanism_visuals(mechanism_id, layer_data)

        elif update_type == 'update_mechanism_visuals':
            # Update existing mechanism visuals
            mechanism_id = data.get('mechanism_id')
            if mechanism_id:
                layer_data = self.mechanism_layers.get(mechanism_id)
                if layer_data:
                    self._generate_mechanism_visuals_directly(
                        mechanism_id,
                        layer_data.get('type', ''),
                        layer_data.get('params', {}),
                        layer_data
                    )

        elif update_type == 'update_mechanism_animation':
            # Update mechanism during animation
            mechanism_id = data.get('mechanism_id')
            time = data.get('time', 0.0)
            layer_data = data.get('layer_data') or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._update_mechanism_visuals_for_animation(mechanism_id, time, layer_data)

        elif update_type == 'toggle_mechanism_visuals':
            # Toggle mechanism visibility
            mechanism_id = data.get('mechanism_id')
            enabled = data.get('enabled', True)
            if mechanism_id:
                # Get part_name from layer_data (mechanisms are associated with parts)
                layer_data = self.mechanism_layers.get(mechanism_id, {})
                part_name = layer_data.get('part_name')
                if part_name:
                    self._toggle_mechanism_visuals(part_name, enabled)

        elif update_type == 'refresh_view':
            if hasattr(self, 'mechanism_scene') and self.mechanism_scene:
                self.mechanism_scene.update()

        elif update_type == 'update_mechanism_list':
            self._update_mechanism_list()

        else:
            logging.debug(f"MechanismDesignTab: Unhandled update type: {update_type}")

    def _update_all_ui_states(self) -> None:
        """Update all UI states based on current data."""
        vm = self._presenter_view_model
        if vm:
            parts = vm.parts
            has_paths, has_mechanisms, has_enabled_parts = (
                any(p.enabled for p in parts), any(p.has_layers for p in parts), any(p.enabled for p in parts))
        else:
            has_paths = bool(getattr(self, 'path_data', {}))
            has_mechanisms = bool(getattr(self, 'mechanism_layers', {}))
            has_enabled_parts = any(getattr(self, 'part_enabled_state', {}).values())

        # Check animation state from controller (not Tab's vestigial timer)
        animation_running = False
        if hasattr(self, '_animation_controller') and self._animation_controller:
            animation_running = self._animation_controller.is_animation_running()

        ui_state = UIState(
            has_paths=has_paths, has_mechanisms=has_mechanisms, has_enabled_parts=has_enabled_parts,
            animation_running=animation_running,
            parametric_mode=getattr(self, 'parametric_mode_enabled', False),
            has_parts_data=bool(getattr(self, 'parts_data', {})))
        if hasattr(self, 'ui_state_manager'):
            self.ui_state_manager.update_button_states(ui_state)
        self._current_ui_state = ui_state
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
        """Set path data from editor."""
        if self._presenter:
            self._presenter.update_paths(convert_paths(path_data or {}))
        self.path_data = self._tab_data_coordinator.set_path_data_from_editor(
            path_data, current_path_data=self.path_data, part_enabled_state=self.part_enabled_state,
            mechanism_layers=self.mechanism_layers, scene=self.mechanism_scene, update_ui_fn=self._update_all_ui_states)
        if self.recommendation_btn:
            if self.path_data:
                names = list(self.path_data.keys())[:3]
                tip = f"Parts with paths: {', '.join(names)}" + (f", ... ({len(self.path_data)} total)" if len(self.path_data) > 3 else "")
            else:
                tip = "No motion paths available"
            self.recommendation_btn.setToolTip(tip)
        self._update_mechanism_layers_list()

    def set_parts_data(self, parts_data: dict[str, PartInfo]):
        """Set parts data. Presenter handles sorting, Tab handles scene items."""
        # Let Presenter handle data sorting
        self._mvp_presenter.set_parts_data(parts_data)

        # Clear scene but preserve skeleton
        self._clear_scene_preserve_skeleton()
        self.current_editor_items.clear()

        # Create visual items (View responsibility)
        if self.parts_data:
            project_dir = self.main_window.project_data_manager.project_dir
            for part_name, p_info in parts_data.items():
                if project_dir:
                    item = CharacterPartItem(part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode)
                    item.setZValue(Z_PART_DEFAULT)
                    item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                    item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                    item.setOpacity(1.0)
                    self.mechanism_scene.addItem(item)
                    self.current_editor_items[part_name] = item
            self._position_parts_at_anchor_joints()

        self._update_mechanism_layers_list()

    def _position_parts_at_anchor_joints(self):
        """Position parts at their anchor joints using cached skeleton data."""
        if not hasattr(self, '_initial_skeleton_data_cache') or not self._initial_skeleton_data_cache:
            return

        # Delegate to skeleton service
        self.skeleton_service.position_parts_at_anchor_joints(
            self.current_editor_items,
            self.parts_data,
            self._initial_skeleton_data_cache
        )

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
        self._skeleton_handler.cache_initial_skeleton(skeleton_data_dict)
        self._initial_skeleton_data_cache = self._skeleton_handler.initial_skeleton_data_cache

    def set_animation_scheduler(self, scheduler) -> None:
        """
        Set the central animation scheduler for unified animation timing.

        Args:
            scheduler: CentralAnimationScheduler instance from MainWindow
        """
        # Pass scheduler to the AnimationLifecycleController
        if hasattr(self, '_animation_controller') and self._animation_controller:
            self._animation_controller.set_scheduler(scheduler)

        # Store reference for direct access if needed
        self._central_scheduler = scheduler

    def _is_animation_running(self) -> bool:
        # Check AnimationLifecycleController first
        if hasattr(self, '_animation_controller') and self._animation_controller:
            return self._animation_controller.is_animation_running()
        # Fallback to tab's own timer
        return self.animation_timer and self.animation_timer.isActive()

    def on_skeleton_updated(self, skeleton_data: dict | None):
        self._skeleton_handler.on_skeleton_updated(skeleton_data)

    def _update_parts_from_skeleton(self, skeleton_data: dict):
        self._skeleton_handler._update_parts_from_skeleton(skeleton_data)

    def _ensure_skeleton_visualization(self, skeleton_data: dict):
        self._skeleton_handler.ensure_skeleton_visualization(skeleton_data)


    def _clear_scene_preserve_skeleton(self):
        """Clear scene but preserve skeleton graphics item."""
        if not self.mechanism_scene:
            return

        # Store and remove skeleton temporarily
        skeleton_item = getattr(self.mechanism_view, 'skeleton_graphics_item', None) if self.mechanism_view else None
        try:
            if skeleton_item and skeleton_item.scene() == self.mechanism_scene:
                self.mechanism_scene.removeItem(skeleton_item)
        except (RuntimeError, AttributeError):
            skeleton_item = None

        # Clear data before scene.clear() to prevent Qt object access errors
        for layer_data in self.mechanism_layers.values():
            layer_data["visual_items"] = []
        self._path_trace_manager.clear_all_traces(self.mechanism_scene)
        if hasattr(self, 'path_visual_items'):
            self.path_visual_items.clear()

        self._scene_recently_cleared = True
        self.mechanism_scene.clear()
        QTimer.singleShot(100, lambda: setattr(self, '_scene_recently_cleared', False))

        # Re-add skeleton if valid
        if skeleton_item:
            try:
                _ = skeleton_item.boundingRect()
                self.mechanism_scene.addItem(skeleton_item)
                skeleton_item.setZValue(Z_SKELETON_OVERLAY)
            except RuntimeError:
                if hasattr(self.mechanism_view, 'skeleton_graphics_item'):
                    self.mechanism_view.skeleton_graphics_item = None

    def _get_target_joint_for_mechanism_control(self, part_name: str, anchor_joint_id: str) -> str:
        return self._joint_mapping_service.get_target_joint(part_name, anchor_joint_id)

    def _setup_mechanism_ik_integration(self):
        """Setup IK integration. Delegates to Presenter."""
        return self._mvp_presenter.setup_mechanism_ik_integration()

    def _register_mechanism_controller(self, mech_id: str, layer_data: dict, joint_id: str):
        """Register mechanism controller. Delegates to Presenter."""
        self._mvp_presenter._register_mechanism_controller(mech_id, layer_data, joint_id)

    def clear_mechanism_data(self):
        """Clear all mechanism data. Delegates to Presenter."""
        self._mvp_presenter.clear_mechanism_data()

    @pyqtSlot()
    def _on_get_recommendations(self):
        self._recommendation_controller.show_recommendations(self)

    def _get_character_position(self):
        skeleton_data = getattr(self, '_initial_skeleton_data_cache', None)
        return list(self._joint_mapping_service.get_character_ground_position(skeleton_data))

    def _handle_recommendation_selection(self, mechanism_data: dict[str, Any]):
        self._recommendation_controller.handle_recommendation_selection(mechanism_data, self)

    def _clear_mechanism_for_part(self, part_name: str):
        """Clear mechanism for a part. Delegates to Presenter."""
        self._mvp_presenter._clear_mechanism_for_part(part_name)

    def _generate_mechanism_from_candidate(self, candidate_data: dict[str, Any]):
        """Generate mechanism from candidate. Delegates to Presenter."""
        self._mvp_presenter.generate_mechanism_from_candidate(candidate_data)
        # Ensure parts data and update UI
        if not self.current_editor_items and self.parts_data:
            current_parts_data = self.main_window.project_data_manager.get_current_parts_data()
            if current_parts_data:
                self.set_parts_data(current_parts_data)
        self._update_all_ui_states()

    def _select_part_in_list(self, part_name: str | None) -> None:
        """Select a part in the mechanism layers list."""
        if not part_name or not self.mechanism_layers_list:
            return
        for i in range(self.mechanism_layers_list.count()):
            item = self.mechanism_layers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == part_name:
                self.mechanism_layers_list.setCurrentItem(item)
                break

    def _add_mechanism_layer(self, _layer_name: str, layer_data: Any):
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
        return self._output_calculator.extract_key_points_from_simulation(full_sim_data, mechanism_type)

    def _calculate_mechanism_output(self, mech_type: str, params: dict, time: float, layer_data: dict) -> QPointF | None:
        return self._output_calculator.calculate_output(mech_type, params, time, layer_data)

    def _update_animation(self):
        if not hasattr(self, '_animation_frame_coordinator') or not self._animation_frame_coordinator:
            return
        self._animation_frame_coordinator.update_frame(
            tab_active=self._tab_active, mechanism_layers=self.mechanism_layers,
            part_enabled_state=self.part_enabled_state, parts_data=self.parts_data,
            ik_manager=getattr(self.main_window, 'ik_manager', None),
            path_trace_manager=self._path_trace_manager, scene=self.mechanism_scene,
            initial_skeleton_cache=getattr(self, '_initial_skeleton_data_cache', None))

    def _get_standardized_joint_id(self, abstract_joint_id: str) -> str | None:
        return self._mvp_presenter.get_standardized_joint_id(abstract_joint_id)

    def _update_mechanism_visuals_for_animation(self, mechanism_id: str, time: float, layer_data: dict):
        self._visual_animator.update_visuals(mechanism_id=mechanism_id, time=time, layer_data=layer_data, visuals_factory=self.visuals_factory)

    def _update_mechanism_layers_list(self):
        self._tab_data_coordinator.update_mechanism_layers_list(
            self.ui_widgets.get('mechanism_layers_list') if hasattr(self, 'ui_widgets') else None,
            presenter_view_model=self._presenter_view_model, part_enabled_state=self.part_enabled_state, main_window=self.main_window)

    def _part_has_mechanism(self, part_name: str) -> bool:
        if self._presenter_view_model:
            part_vm = self._presenter_view_model.find_part(part_name)
            if part_vm is not None and part_vm.has_layers:
                return True
        return any(ld.get("part_name") == part_name for ld in self.mechanism_layers.values())

    def _reset_skeleton_to_initial_state(self):
        self._mvp_presenter.reset_skeleton_to_initial_state()

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        self._mvp_presenter.handle_mechanism_visuals(mechanism_graphics_data)

    def _clear_animation_cache(self):
        if hasattr(self, '_animation_frame_coordinator') and self._animation_frame_coordinator:
            self._animation_frame_coordinator.clear_animation_cache(self)

    def _safe_remove_visual_items(self, visual_items: list):
        self._visual_item_manager.set_scene_cleared_flag(getattr(self, '_scene_recently_cleared', False))
        self._visual_item_manager.safe_remove_visual_items(visual_items)

    def cleanup_tab_resources(self):
        self._mvp_presenter._cleanup_resources()

    def prepare_tab_activation(self):
        self._mvp_presenter._prepare_activation()

    def _is_visual_item_invalid(self, item) -> bool:
        return self._visual_item_manager.is_visual_item_invalid(item)

    def deactivate_tab(self):
        self._tab_active = False
        self.cleanup_tab_resources()

    def activate_tab(self):
        self._tab_active = True
        self.prepare_tab_activation()
        self._update_mechanism_layers_list()
        self._update_all_ui_states()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            if hasattr(self, '_tab_visible'):
                self._tab_visible = True
        except Exception:
            pass

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
        if self.isVisible():
            self._mvp_presenter.handle_ik_update(ik_results)

    def _generate_mechanism_visuals_directly(self, mechanism_id: str, mechanism_type: str, params: dict, layer_data: dict):
        self.handle_mechanism_visuals({"mechanism_id": mechanism_id, "mechanism_type": mechanism_type, "params": params, **layer_data})

    def _on_start_animation(self):
        if self.mechanism_enabled_state:
            self._animation_controller.start_animation(mechanism_enabled_state=self.mechanism_enabled_state, initial_skeleton_data=getattr(self, '_initial_skeleton_data_cache', None))
        else:
            QMessageBox.warning(self, "Warning", "No mechanisms are enabled for animation.")

    def _on_stop_animation(self):
        self._animation_controller.stop_animation()

    def _on_reset_animation(self):
        self._animation_controller.reset_animation()

    def _on_layer_selection_changed(self):
        self._layer_selection_controller.on_selection_changed()

    def _on_layer_item_clicked(self, item):
        self._layer_selection_controller.on_item_clicked(item)

    def _update_part_visibility_and_animation(self, part_name: str, enabled: bool):
        self._layer_selection_controller.update_part_visibility_and_animation(part_name, enabled)

    def _toggle_mechanism_visuals(self, part_name: str, enabled: bool):
        self._layer_selection_controller.toggle_mechanism_visuals(part_name, enabled)


    def apply_performance_preset(self, preset: str) -> None:
        """Apply performance preset. Delegates to AnimationFrameCoordinator."""
        if not hasattr(self, '_animation_frame_coordinator') or not self._animation_frame_coordinator:
            return
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

    # --- Cleanup ---

    def closeEvent(self, event) -> None:
        """
        Handle tab close event - cleanup signals, timers, and resources.

        Stops animation timers, disconnects signal connections,
        and cleans up resources to prevent memory leaks.
        """
        import logging
        logging.info("MechanismDesignTab: closeEvent - cleaning up")

        # Stop animation controller first (primary animation system)
        try:
            if hasattr(self, '_animation_controller') and self._animation_controller:
                self._animation_controller.stop_animation()
        except (TypeError, RuntimeError, AttributeError) as e:
            logging.debug(f"MechanismDesignTab: Animation controller cleanup: {e}")

        # Stop legacy animation timer (vestigial, but cleanup for safety)
        try:
            if hasattr(self, 'animation_timer') and self.animation_timer:
                self.animation_timer.stop()
                self.animation_timer.timeout.disconnect()
        except (TypeError, RuntimeError) as e:
            logging.debug(f"MechanismDesignTab: Timer cleanup: {e}")

        # Disconnect presenter listeners
        try:
            if hasattr(self, '_presenter') and self._presenter:
                self._presenter.remove_view_listener(self._on_presenter_view_update)
        except (TypeError, RuntimeError, AttributeError) as e:
            logging.debug(f"MechanismDesignTab: Presenter cleanup: {e}")

        # Cleanup tab resources via existing method
        try:
            self.cleanup_tab_resources()
        except Exception as e:
            logging.debug(f"MechanismDesignTab: Resource cleanup: {e}")

        # Clear data references
        self.current_editor_items.clear()
        self.current_parts_info.clear()
        self.mechanism_layers.clear()
        self.visual_items_store.clear()
        self.debug_items.clear()
        self.animating_mechanisms.clear()
        self._initial_skeleton_data_cache = None

        logging.info("MechanismDesignTab: closeEvent - cleanup complete")
        super().closeEvent(event)

# Keep this part for running the tab standalone for testing if required.
# if __name__ == "__main__":
#     import sys
#     app = QApplication(sys.argv)
#     # ... test setup
#     sys.exit(app.exec())
