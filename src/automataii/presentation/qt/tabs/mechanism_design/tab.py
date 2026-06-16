"""Mechanism Design Tab - MVP View for mechanism design and animation."""

import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPainterPath
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QInputDialog,
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

# Domain and Application layer imports (Hexagonal Architecture)
from automataii.domain.kinematics.joint_mapping_service import JointMappingService
from automataii.domain.kinematics.mechanism import MechanismCandidate
from automataii.domain.kinematics.motion_path_generator import MotionPathGenerator
from automataii.presentation.qt.blueprint.exporter import BlueprintExporter
from automataii.presentation.qt.graphics_items.part_item import CharacterPartItem
from automataii.presentation.qt.mechanism_parameter_utils import (
    finite_float,
    positive_finite_param,
)
from automataii.presentation.qt.models import PartInfo
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
    MechanismCharacterRebindService,
    MechanismInstantiationService,
    SceneManagementService,
    TabCallbackConfigurator,
    TabDataCoordinator,
    TransformService,
    ViewUtilitiesService,
    VisualItemManager,
)
from automataii.presentation.qt.tabs.mechanism_design.services.foundry_scene_contract import (
    rebuild_fourbar_scene_geometry_from_params,
)
from automataii.presentation.qt.tabs.mechanism_visuals_factory import MechanismVisualsFactory
from automataii.shared.physical_kit import (
    DEFAULT_GRID_CELL_CM,
    DEFAULT_PHYSICAL_KIT_PROFILE,
    PhysicalKitContext,
    PhysicalKitProfile,
    gear_center_distance,
    grid_enabled_from_params,
    grid_step_mm,
    physical_context_from_params,
    physical_context_from_settings,
    physical_profile_from_params,
    snap_gear_params,
    snap_physical_params,
)
from automataii.utils.paths import resolve_path


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
        # Four-bar linkage variants
        "4-Bar Linkage": "4_bar_linkage",
        "4-bar Coupler": "4_bar_linkage",
        "Four-Bar Linkage": "4_bar_linkage",
        "Four-Bar": "4_bar_linkage",
        "3-bar Output": "4_bar_linkage",
        # Cam mechanism variants
        "Cam & Follower": "cam",
        "Cam-Follower": "cam",
        "Cam Profile": "cam",
        "Cam": "cam",
        # Gear mechanism variants
        "Gears": "gear",  # Family name from recommendation dialog
        "Gears (Simple Pair)": "gear",
        "Gear Train": "gear",
        "Gear Contact": "gear",
        "Simple Gear": "gear",
        "Planetary Gear": "planetary_gear",
    }

    # Properties delegating to AnimationFrameCoordinator (god class decomposition)
    @property
    def animation_time(self) -> float:
        """Current animation time. Delegates to AnimationFrameCoordinator."""
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.animation_time
        return 0.0

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set animation time."""
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            self._animation_frame_coordinator.animation_time = value

    @property
    def animation_speed(self) -> float:
        """Animation speed. Delegates to AnimationFrameCoordinator."""
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.animation_speed
        return 1.0

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed."""
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            self._animation_frame_coordinator.animation_speed = value

    @property
    def _trace_frame_tick(self) -> int:
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            return self._animation_frame_coordinator.trace_frame_tick
        return 0

    # === STATE DELEGATION TO PRESENTER (Passive View Pattern) ===
    # These attributes are delegated to _mvp_presenter when available
    _DELEGATED_ATTRS = frozenset(
        {
            "mechanism_layers",
            "mechanism_enabled_state",
            "parametric_handles",
            "path_data",
            "part_enabled_state",
            "parts_data",
        }
    )

    def __getattr__(self, name: str):
        if name in MechanismDesignTab._DELEGATED_ATTRS:
            if hasattr(self, "_mvp_presenter") and self._mvp_presenter:
                return getattr(self._mvp_presenter, name)
            return getattr(self, f"_local_{name}", {})
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value) -> None:
        if name in MechanismDesignTab._DELEGATED_ATTRS:
            if hasattr(self, "_mvp_presenter") and self._mvp_presenter:
                setattr(self._mvp_presenter, name, value)
            else:
                super().__setattr__(f"_local_{name}", value)
        else:
            super().__setattr__(name, value)

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        logging.info(
            f"[TAB-INIT] MechanismDesignTab.__init__ STARTING, self_id={id(self)}, main_window={main_window}"
        )
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
        self._grid_system_enabled = True
        self._grid_cell_cm = DEFAULT_GRID_CELL_CM
        self._grid_pitch_choice = physical_context_from_settings(
            True,
            DEFAULT_GRID_CELL_CM,
            profile=DEFAULT_PHYSICAL_KIT_PROFILE,
        ).grid_pitch_choice
        self._physical_profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE
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
        self._preserve_mechanisms_on_next_set_parts = False
        self._pending_character_rebind = False
        self._skeleton_cache_generation = 0
        self._required_rebind_skeleton_generation: int | None = None

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
            config=PathTraceConfig(
                max_points=500,
                update_stride=5,
                pen_color=QColor(255, 0, 0, 150),
                pen_width=2.0,
                z_value=100,
            )
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
        self.visuals_factory = MechanismVisualsFactory(
            self.mechanism_scene,
            show_diagnostics=self.debug_mode,
        )
        self._mvp_presenter.set_scene(self.mechanism_scene)  # Initializes scene batcher for perf

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
        for name in (
            "blueprint_btn",
            "recommendation_btn",
            "assign_character_btn",
            "mechanism_layers_list",
            "play_btn",
            "stop_btn",
            "reset_btn",
            "parametric_edit_btn",
            "zoom_in_btn",
            "zoom_out_btn",
            "zoom_fit_btn",
            "center_character_btn",
            "blueprint_info_label",
        ):
            setattr(self, name, self.ui_widgets.get(name))

        # Initialize extracted components BEFORE connecting signals
        # (signals may trigger callbacks that require these components)
        self._animation_controller = AnimationLifecycleController(
            mechanism_scene=self.mechanism_scene,
            path_trace_manager=self._path_trace_manager,
            parent=self,
        )
        logging.debug(
            f"[INIT] Animation controller created: {self._animation_controller}, tab_id={id(self)}"
        )
        self._skeleton_handler = SkeletonVisualizationHandler(
            mechanism_view=self.mechanism_view, mechanism_scene=self.mechanism_scene, parent=self
        )
        self._output_calculator = MechanismOutputCalculator(
            get_scene_transform=self._get_scene_transform_function
        )
        self._visual_animator = MechanismVisualAnimator(
            get_scene_transform=self._get_scene_transform_function
        )

        # Initialize mode controllers
        self._layer_selection_controller = LayerSelectionController(
            path_trace_manager=self._path_trace_manager, parent=self
        )
        self._parametric_mode_controller = ParametricModeController(parent=self)
        self._recommendation_controller = RecommendationController(parent=self)

        # Connect all signals using new signal manager (after components are ready)
        self.signal_manager.connect_all_signals(self)

        # Initialize parametric system now that mechanism_scene is available
        if PARAMETRIC_AVAILABLE:
            self.parametric_manager._initialize_parametric_system()

        # Configure all service/controller callbacks via configurator
        TabCallbackConfigurator(self).configure_all()

        # Initialize UI state (after all components are ready)
        self._current_ui_state = UIState()
        self._update_all_ui_states()
        logging.info(
            f"[TAB-INIT] MechanismDesignTab.__init__ COMPLETE, self_id={id(self)}, has_animation_controller={hasattr(self, '_animation_controller')}"
        )

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
        self._mechanism_instantiation.set_physical_profile(self._physical_profile)
        self._mechanism_instantiation.set_path_converter(utils_qpainterpath_to_numpy_array)
        self._handle_position_coordinator = HandlePositionCoordinator()
        self._handle_position_coordinator.set_rotation_handle_class(RotationHandle)
        self._animation_frame_coordinator = AnimationFrameCoordinator(
            ik_update_rate_hz=30, mechanism_update_fraction=0.5, pos_epsilon_px=0.5
        )
        self._tab_data_coordinator = TabDataCoordinator()
        self._scene_management_service = SceneManagementService()
        self._view_utilities_service = ViewUtilitiesService()
        self._character_rebind_service = MechanismCharacterRebindService(
            scene_to_mech=self._scene_to_mechanism_coords_for_rebind
        )

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

        if update_type == "generate_mechanism_visuals":
            # Route to mechanism visuals handler (new mechanism created)
            self.handle_mechanism_visuals(data)

        elif update_type == "regenerate_visuals":
            # Regenerate visuals for existing mechanism
            mechanism_id = data.get("mechanism_id")
            layer_data = data.get("layer_data") or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._generate_mechanism_visuals_directly(
                    mechanism_id,
                    layer_data.get("type", ""),
                    layer_data.get("params", {}),
                    layer_data,
                )

        elif update_type == "recreate_visuals":
            # Recreate visuals after parameter change
            mechanism_id = data.get("mechanism_id")
            layer_data = data.get("layer_data") or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._recreate_mechanism_visuals(mechanism_id, layer_data)

        elif update_type == "update_mechanism_visuals":
            # Update existing mechanism visuals
            mechanism_id = data.get("mechanism_id")
            if mechanism_id:
                layer_data = self.mechanism_layers.get(mechanism_id)
                if layer_data:
                    self._generate_mechanism_visuals_directly(
                        mechanism_id,
                        layer_data.get("type", ""),
                        layer_data.get("params", {}),
                        layer_data,
                    )

        elif update_type == "update_mechanism_animation":
            # Update mechanism during animation
            mechanism_id = data.get("mechanism_id")
            time = data.get("time", 0.0)
            layer_data = data.get("layer_data") or self.mechanism_layers.get(mechanism_id)
            if mechanism_id and layer_data:
                self._update_mechanism_visuals_for_animation(mechanism_id, time, layer_data)

        elif update_type == "toggle_mechanism_visuals":
            # Toggle mechanism visibility
            mechanism_id = data.get("mechanism_id")
            enabled = data.get("enabled", True)
            if mechanism_id:
                # Get part_name from layer_data (mechanisms are associated with parts)
                layer_data = self.mechanism_layers.get(mechanism_id, {})
                part_name = layer_data.get("part_name")
                if part_name:
                    self._toggle_mechanism_visuals(part_name, enabled)

        elif update_type == "refresh_view":
            if hasattr(self, "mechanism_scene") and self.mechanism_scene:
                self.mechanism_scene.update()

        elif update_type == "update_mechanism_list":
            self._update_mechanism_list()

        else:
            logging.debug(f"MechanismDesignTab: Unhandled update type: {update_type}")

    def _update_all_ui_states(self) -> None:
        """Update all UI states based on current data."""
        vm = self._presenter_view_model
        if vm:
            parts = vm.parts
            local_mechanism_layers = bool(getattr(self, "mechanism_layers", {}))
            has_paths, has_mechanisms, has_enabled_parts = (
                any(p.enabled for p in parts),
                any(p.has_layers for p in parts) or local_mechanism_layers,
                any(p.enabled for p in parts),
            )
        else:
            has_paths = bool(getattr(self, "path_data", {}))
            has_mechanisms = bool(getattr(self, "mechanism_layers", {}))
            has_enabled_parts = any(getattr(self, "part_enabled_state", {}).values())

        # Check animation state from controller (not Tab's vestigial timer)
        animation_running = False
        if hasattr(self, "_animation_controller") and self._animation_controller:
            animation_running = self._animation_controller.is_animation_running()

        ui_state = UIState(
            has_paths=has_paths,
            has_mechanisms=has_mechanisms,
            has_enabled_parts=has_enabled_parts,
            animation_running=animation_running,
            parametric_mode=getattr(self, "parametric_mode_enabled", False),
            has_parts_data=bool(getattr(self, "parts_data", {})),
        )
        if hasattr(self, "ui_state_manager"):
            self.ui_state_manager.update_button_states(ui_state)
        self._current_ui_state = ui_state
        self._connect_to_ik_manager()

    def _handle_joint_bend_direction_changed(self, joint_id: str, new_direction: float):
        """Handle joint bend direction change from EditorView."""

        # Update skeleton manager if available
        if hasattr(self.main_window, "skeleton_manager") and self.main_window.skeleton_manager:
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
            path_data,
            current_path_data=self.path_data,
            part_enabled_state=self.part_enabled_state,
            mechanism_layers=self.mechanism_layers,
            scene=self.mechanism_scene,
            update_ui_fn=self._update_all_ui_states,
        )
        if self.recommendation_btn:
            if self.path_data:
                names = list(self.path_data.keys())[:3]
                tip = f"Parts with paths: {', '.join(names)}" + (
                    f", ... ({len(self.path_data)} total)" if len(self.path_data) > 3 else ""
                )
            else:
                tip = "No motion paths available"
            self.recommendation_btn.setToolTip(tip)
        self._update_mechanism_layers_list()

    def set_parts_data(self, parts_data: dict[str, PartInfo], clear_mechanisms: bool = True):
        """Set parts data. Presenter handles sorting, Tab handles scene items.

        Args:
            parts_data: Dictionary of part name to PartInfo
            clear_mechanisms: If True, clears existing mechanism layers when
                parts change (default True to prevent stale references)
        """
        preserve_existing_mechanisms = bool(self._preserve_mechanisms_on_next_set_parts)
        self._preserve_mechanisms_on_next_set_parts = False
        effective_clear_mechanisms = clear_mechanisms and not preserve_existing_mechanisms

        # Clear mechanism data if requested (prevents stale mechanism references)
        if effective_clear_mechanisms and self.mechanism_layers:
            self.clear_mechanism_data()
        elif preserve_existing_mechanisms and self.mechanism_layers:
            self._pending_character_rebind = True

        # Let Presenter handle data sorting
        self._mvp_presenter.set_parts_data(parts_data)

        # Clear scene but preserve skeleton
        self._clear_scene_preserve_skeleton()
        self.current_editor_items.clear()

        # Create visual items (View responsibility)
        if self.parts_data:
            # Use project_dir if available, fallback to cwd for preset-based parts
            project_dir = (
                self.main_window.project_data_manager.project_dir
                or self.main_window.project_state_manager.state.project_dir
                or Path.cwd()
            )
            for part_name, p_info in parts_data.items():
                item = CharacterPartItem(
                    part_info=p_info, project_dir=project_dir, debug_mode=self.debug_mode
                )
                item.setZValue(Z_PART_DEFAULT)
                item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, True)
                item.setOpacity(1.0)
                self.mechanism_scene.addItem(item)
                self.current_editor_items[part_name] = item
            self._position_parts_at_anchor_joints()

        self._update_mechanism_layers_list()
        self._attempt_pending_character_rebind()

    def prepare_character_rebind(self) -> None:
        """Preserve mechanisms during next character load and request rebind."""
        current_cache = getattr(self, "_initial_skeleton_data_cache", None)
        has_cached_skeleton = bool(isinstance(current_cache, dict) and current_cache.get("joints"))
        if has_cached_skeleton:
            # Wait for the next skeleton cache refresh to avoid rebinding against stale (e.g. dummy) joints.
            self._required_rebind_skeleton_generation = self._skeleton_cache_generation + 1
        else:
            # No skeleton cached yet; allow rebind as soon as parts are ready.
            self._required_rebind_skeleton_generation = self._skeleton_cache_generation
        self._preserve_mechanisms_on_next_set_parts = True
        self._pending_character_rebind = True

    def cancel_character_rebind(self) -> None:
        """Clear pending/preserve flags if character load is aborted or fails."""
        self._preserve_mechanisms_on_next_set_parts = False
        self._pending_character_rebind = False
        self._required_rebind_skeleton_generation = None

    def _attempt_pending_character_rebind(self) -> None:
        if not self._pending_character_rebind:
            return

        if not self.mechanism_layers:
            self._pending_character_rebind = False
            return

        if not self.parts_data:
            return

        required_generation = self._required_rebind_skeleton_generation
        if (
            required_generation is not None
            and self._skeleton_cache_generation < required_generation
        ):
            return

        self._map_orphan_mechanisms_to_character()

        skeleton_cache = getattr(self, "_initial_skeleton_data_cache", None)
        joints = skeleton_cache.get("joints") if isinstance(skeleton_cache, dict) else None
        has_skeleton_data = isinstance(joints, dict) and bool(joints)
        if (
            required_generation is not None
            and self._skeleton_cache_generation >= required_generation
        ):
            self._pending_character_rebind = False
            self._required_rebind_skeleton_generation = None
        elif has_skeleton_data:
            self._pending_character_rebind = False

    def _position_parts_at_anchor_joints(self):
        """Position parts at their anchor joints and reset rotations using cached skeleton data."""
        if (
            not hasattr(self, "_initial_skeleton_data_cache")
            or not self._initial_skeleton_data_cache
        ):
            return

        def position_setter(part_item, pos: tuple[float, float]) -> None:
            """Set position so that anchor point is at the given position."""
            if hasattr(part_item, "set_scene_position_from_anchor"):
                # Use anchor-aware positioning (accounts for local_pivot_offset)
                part_item.set_scene_position_from_anchor(
                    QPointF(pos[0], pos[1]), bypass_validation=True
                )
            elif hasattr(part_item, "setPos"):
                part_item.setPos(pos[0], pos[1])

        def rotation_setter(part_item, rotation_degrees: float) -> None:
            """Set rotation on a QGraphicsItem (world coordinates)."""
            if hasattr(part_item, "setRotation"):
                part_item.setRotation(rotation_degrees)

        # Delegate to skeleton service with both position and rotation setters
        self.skeleton_service.position_parts_at_anchor_joints(
            self.current_editor_items,
            self.parts_data,
            self._initial_skeleton_data_cache,
            position_setter=position_setter,
            rotation_setter=rotation_setter,
        )

    def cache_initial_skeleton(self, skeleton_data_dict: dict | None):
        self._skeleton_handler.cache_initial_skeleton(skeleton_data_dict)
        self._initial_skeleton_data_cache = self._skeleton_handler.initial_skeleton_data_cache
        self._skeleton_cache_generation += 1
        self._attempt_pending_character_rebind()

    def set_animation_scheduler(self, scheduler) -> None:
        """
        Set the central animation scheduler for unified animation timing.

        Args:
            scheduler: CentralAnimationScheduler instance from MainWindow
        """
        # Pass scheduler to the AnimationLifecycleController
        if hasattr(self, "_animation_controller") and self._animation_controller:
            self._animation_controller.set_scheduler(scheduler)

        # Store reference for direct access if needed
        self._central_scheduler = scheduler

    def _is_animation_running(self) -> bool:
        # Check AnimationLifecycleController first
        if hasattr(self, "_animation_controller") and self._animation_controller:
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
        skeleton_item = (
            getattr(self.mechanism_view, "skeleton_graphics_item", None)
            if self.mechanism_view
            else None
        )
        try:
            if skeleton_item and skeleton_item.scene() == self.mechanism_scene:
                self.mechanism_scene.removeItem(skeleton_item)
        except (RuntimeError, AttributeError):
            skeleton_item = None

        # Clear data before scene.clear() to prevent Qt object access errors
        for layer_data in self.mechanism_layers.values():
            layer_data["visual_items"] = []
        self._path_trace_manager.clear_all_traces(self.mechanism_scene)
        if hasattr(self, "path_visual_items"):
            self.path_visual_items.clear()

        self._scene_recently_cleared = True
        self.mechanism_scene.clear()
        QTimer.singleShot(100, lambda: setattr(self, "_scene_recently_cleared", False))

        # Re-add skeleton if valid
        if skeleton_item:
            try:
                _ = skeleton_item.boundingRect()
                self.mechanism_scene.addItem(skeleton_item)
                skeleton_item.setZValue(Z_SKELETON_OVERLAY)
            except RuntimeError:
                if hasattr(self.mechanism_view, "skeleton_graphics_item"):
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
        # Clear animation caches for performance optimization
        self._visual_animator.clear_caches()
        self._mvp_presenter.clear_mechanism_data()

    @pyqtSlot()
    def _on_get_recommendations(self):
        self._recommendation_controller.show_recommendations(self)

    @pyqtSlot()
    def _on_assign_dummy_character(self):
        """Slot for the Assign Character button. Loads the pre-processed dummy character."""
        logging.info("Assign Character button clicked. Loading dummy character.")

        # Determine if we need to warn about overwriting
        if self.parts_data:
            reply = QMessageBox.question(
                self,
                "Assign Dummy Character",
                "This will replace the current character parts with the default dummy character.\n\n"
                "Existing mechanisms will be mapped to the new parts where possible.\n"
                "Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        dummy_dir = self._resolve_dummy_character_dir()
        success = self.load_character_from_directory(dummy_dir) if dummy_dir is not None else False
        if success:
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage("Dummy character assigned.", 3000)
            self.center_on_character()
        else:
            QMessageBox.warning(self, "Error", "Failed to load dummy character.")

    def _resolve_dummy_character_dir(self) -> Path | None:
        """Resolve dummy character directory from known workspace locations."""
        candidates: list[Path] = []
        try:
            candidates.append(
                Path(__file__).resolve().parents[6]
                / "resources"
                / "presets"
                / "characters"
                / "dummy"
            )
        except (IndexError, RuntimeError):
            pass

        candidates.append(resolve_path("resources/presets/characters/dummy"))
        try:
            candidates.append(
                Path(__file__).resolve().parents[5]
                / "resources"
                / "presets"
                / "characters"
                / "dummy"
            )
        except (IndexError, RuntimeError):
            pass

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _ensure_character_for_foundry_import(self) -> bool:
        """Ensure a character is loaded before Foundry mechanism import."""
        if self.parts_data:
            return True

        logging.info("No character parts found. Auto-loading dummy character.")
        dummy_dir = self._resolve_dummy_character_dir()
        if (
            dummy_dir is not None
            and self.load_character_from_directory(dummy_dir)
            and self.parts_data
        ):
            return True

        logging.warning(
            "Failed to load dummy character or no parts created. Falling back to silhouette_human preset."
        )
        preset_loaded = bool(self.apply_character_preset("silhouette_human"))
        return bool(preset_loaded and self.parts_data)

    def _resolve_target_part_for_foundry_import(self) -> str | None:
        """Resolve valid target part for Foundry import."""
        part_name = self.selected_part_name
        if part_name and part_name not in self.parts_data:
            logging.info(
                "Selected part '%s' is not available in current character. Re-selecting target part.",
                part_name,
            )
            part_name = None

        if part_name:
            return part_name

        available_parts = [str(name) for name in self.parts_data.keys()]
        if not available_parts:
            return None

        part_name = self._prompt_target_part_for_foundry_import(available_parts)
        if part_name:
            self.selected_part_name = part_name
            if getattr(self, "_mvp_presenter", None):
                try:
                    self._mvp_presenter.select_part(part_name)
                except Exception:
                    logging.debug(
                        "Suppressed exception while selecting part in presenter", exc_info=True
                    )
            if hasattr(self, "_select_part_in_list"):
                self._select_part_in_list(part_name)
            logging.info("Selected target part for Foundry import: %s", part_name)
        else:
            logging.info("Foundry import canceled: target part selection canceled by user")
        return part_name

    def _prompt_target_part_for_foundry_import(self, available_parts: list[str]) -> str | None:
        if not available_parts:
            return None
        if len(available_parts) == 1:
            return available_parts[0]

        selected_part, ok = QInputDialog.getItem(
            self,
            "Select Target Part",
            "Assign imported mechanism to part:",
            available_parts,
            0,
            False,
        )
        if not ok or not selected_part:
            return None
        return str(selected_part)

    def _resolve_joint_scene_position_for_part(self, part_name: str) -> tuple[float, float] | None:
        part_item = (
            self.current_editor_items.get(part_name)
            if isinstance(getattr(self, "current_editor_items", None), dict)
            else None
        )
        if part_item is not None:
            try:
                if hasattr(part_item, "mapToScene") and hasattr(part_item, "transformOriginPoint"):
                    anchor_scene = part_item.mapToScene(part_item.transformOriginPoint())
                    return (float(anchor_scene.x()), float(anchor_scene.y()))
                if hasattr(part_item, "sceneBoundingRect"):
                    rect = part_item.sceneBoundingRect()
                    center = rect.center()
                    return (float(center.x()), float(center.y()))
            except Exception:
                logging.debug(
                    "Suppressed exception while resolving part-item scene position for %s",
                    part_name,
                    exc_info=True,
                )

        part_info = self.parts_data.get(part_name) if isinstance(self.parts_data, dict) else None
        if not part_info:
            return None

        anchor_joint_id = getattr(part_info, "anchor_joint_id", None)
        if isinstance(anchor_joint_id, str) and anchor_joint_id:
            skeleton_cache = getattr(self, "initial_skeleton_cache", None)
            joints = skeleton_cache.get("joints", {}) if isinstance(skeleton_cache, dict) else {}
            if isinstance(joints, dict) and joints:
                joint_data = joints.get(anchor_joint_id)
                if not joint_data:
                    for joint_id, candidate in joints.items():
                        if not isinstance(joint_id, str):
                            continue
                        if joint_id.startswith(anchor_joint_id + "_"):
                            joint_data = candidate
                            break
                        if joint_id.startswith(anchor_joint_id) and len(joint_id) > len(
                            anchor_joint_id
                        ):
                            suffix = joint_id[len(anchor_joint_id) :]
                            if suffix and suffix[0].isdigit():
                                joint_data = candidate
                                break

                if isinstance(joint_data, dict):
                    raw_position = joint_data.get("position") or joint_data.get("scene_position")
                    if isinstance(raw_position, list | tuple) and len(raw_position) >= 2:
                        try:
                            return (float(raw_position[0]), float(raw_position[1]))
                        except (TypeError, ValueError):
                            pass

        roi = getattr(part_info, "roi", None)
        if isinstance(roi, list | tuple) and len(roi) >= 4:
            try:
                return (
                    float(roi[0]) + (float(roi[2]) * 0.5),
                    float(roi[1]) + (float(roi[3]) * 0.5),
                )
            except (TypeError, ValueError):
                return None

        return None

    def _resolve_foundry_import_scene_position(self, part_name: str) -> tuple[float, float]:
        anchor_scene_position = self._resolve_joint_scene_position_for_part(part_name)
        if anchor_scene_position is not None:
            return anchor_scene_position

        scene_position = (400.0, 300.0)
        if self.mechanism_view:
            view_center = self.mechanism_view.mapToScene(
                self.mechanism_view.viewport().rect().center()
            )
            scene_position = (view_center.x(), view_center.y())
        return scene_position

    def load_character_from_directory(self, char_dir: Path) -> bool:
        """Load a character from a directory containing parts_info.json.

        Uses the same flow as ImageProcessingTab -> MainWindow -> EditorTab,
        ensuring consistent character loading across all tabs.

        Args:
            char_dir: Path to the character directory.

        Returns:
            True if loaded successfully.
        """
        logging.info(f"Loading character from: {char_dir}")

        parts_info_path = char_dir / "parts_info.json"

        if not parts_info_path.exists():
            logging.error(f"parts_info.json not found in {char_dir}")
            return False

        try:
            self.prepare_character_rebind()

            # Use ProjectDataManager for consistent loading (same as ImageProcessingTab flow)
            # This will:
            # 1. Load and validate parts_info.json
            # 2. Emit project_data_loaded signal
            # 3. MainWindow._handle_project_data_loaded will call:
            #    - editor_tab.set_parts_data(parts_info)
            #    - mechanism_design_tab.set_parts_data(parts_info)
            #    - skeleton_manager.load_skeleton_from_project_data(...)
            success = self.main_window.project_data_manager.load_project_from_file(
                str(parts_info_path)
            )

            if success:
                logging.info(f"Loaded character from {char_dir}")
            else:
                self.cancel_character_rebind()

            return success

        except Exception as e:
            logging.exception(f"Failed to load character: {e}")
            self.cancel_character_rebind()
            return False

    @pyqtSlot(str)
    def apply_character_preset(self, preset_id: str) -> bool:
        """
        Apply a character preset to the tab (Public Slot).

        This is now triggered externally (e.g., from ImageProcessingTab via MainWindow).

        Args:
            preset_id: ID of the character preset to load

        Returns:
            True if the preset was applied successfully.
        """
        import logging

        from automataii.application.character import CharacterPresetService
        from automataii.domain.project.models import PartInfoModel
        from automataii.presentation.qt.models import PartInfo

        logging.info(f"Applying character preset: {preset_id}")

        try:
            # 1. Load preset from service (allow dependency injection for tests)
            service = getattr(self, "character_preset_service", None)
            if service is None:
                service = CharacterPresetService()
            preset = service.get_preset(preset_id)
            if not preset:
                logging.error(f"Preset not found: {preset_id}")
                return False

            # 2. Determine canvas center for character placement
            canvas_center = (400.0, 300.0)
            if self.mechanism_view:
                view_center = self.mechanism_view.mapToScene(
                    self.mechanism_view.viewport().rect().center()
                )
                canvas_center = (view_center.x(), view_center.y())

            # 3. Build skeleton data with absolute positions
            skeleton_dict = self._convert_preset_skeleton_to_dict(preset, canvas_center)
            joints_data = skeleton_dict.get("joints", {})

            # 4. Convert preset parts to PartInfo dict using absolute joint positions
            parts_data: dict[str, PartInfo] = {}
            if hasattr(preset, "get_parts_sorted_by_z"):
                sorted_parts = list(preset.get_parts_sorted_by_z())
            else:
                raw_parts = getattr(preset, "parts", {})
                if isinstance(raw_parts, dict):
                    sorted_parts = list(raw_parts.values())
                else:
                    sorted_parts = list(raw_parts) if raw_parts else []
                sorted_parts.sort(key=lambda part: float(getattr(part, "z_index", 0) or 0))

            for preset_part in sorted_parts:
                part_name = str(getattr(preset_part, "name", "")).strip()
                if not part_name:
                    continue

                anchor_joint = getattr(preset_part, "anchor_joint", "root")
                if not isinstance(anchor_joint, str) or not anchor_joint:
                    anchor_joint = "root"

                # Get absolute position from computed skeleton
                joint_data = joints_data.get(anchor_joint, {})
                abs_pos = joint_data.get("position", [canvas_center[0], canvas_center[1]])
                x, y = abs_pos[0], abs_pos[1]

                # Add transform offset
                tx, ty, _ = (0.0, 0.0, 0.0)
                transform = getattr(preset_part, "default_transform", (0.0, 0.0, 0.0))
                if isinstance(transform, tuple | list) and len(transform) == 3:
                    try:
                        tx = float(transform[0])
                        ty = float(transform[1])
                    except (TypeError, ValueError):
                        tx = 0.0
                        ty = 0.0
                x += tx
                y += ty

                z_index = 0.0
                try:
                    z_index = float(getattr(preset_part, "z_index", 0))
                except (TypeError, ValueError):
                    z_index = 0.0

                svg_path = getattr(preset_part, "svg_path", None)
                image_path = str(svg_path) if isinstance(svg_path, str) else None

                model = PartInfoModel(
                    name=part_name,
                    roi=[x, y, 50.0, 50.0],  # Default size, will be updated from SVG
                    z_value=z_index,
                    image_path=image_path,
                    fill_color="rgba(255,255,255,0.9)",
                    fixed=False,
                    opacity=1.0,
                    anchor_joint_id=anchor_joint,
                )

                # Create PartInfo, resolving the SVG path
                part_info = PartInfo.from_pydantic(model, project_dir=Path.cwd())
                parts_data[part_name] = part_info

            # 5. Preserve mechanisms and request rebind before skeleton/parts update.
            # Order matters: this ensures rebind waits for the new skeleton generation.
            self.prepare_character_rebind()

            # 6. Cache skeleton for IK and positioning
            if skeleton_dict:
                self.cache_initial_skeleton(skeleton_dict)

            # 7. Set parts data (without clearing existing mechanisms)
            self.set_parts_data(parts_data, clear_mechanisms=False)

            # 8. Ensure skeleton visualization is displayed
            if hasattr(self, "_skeleton_handler") and self._skeleton_handler:
                self._skeleton_handler.ensure_skeleton_visualization(skeleton_dict)

            # 9. Map orphan mechanisms (created without character) to the new parts
            self._map_orphan_mechanisms_to_character()

            # 10. Center view on the character
            self.center_on_character()

            logging.info(f"Applied preset '{preset.name}' with {len(parts_data)} parts")
            return True

        except Exception as e:
            logging.exception(f"Failed to apply character preset: {e}")
            self.cancel_character_rebind()
            return False

    def _convert_preset_skeleton_to_dict(
        self, preset, canvas_center: tuple[float, float] = (400.0, 300.0)
    ) -> dict:
        """Convert preset skeleton to the format expected by skeleton manager.

        Converts relative joint positions to absolute scene coordinates,
        centered on the canvas.

        Args:
            preset: The CharacterPreset with skeleton data.
            canvas_center: Center point to place the character (x, y).

        Returns:
            Dictionary in skeleton manager format with absolute positions.
        """
        from automataii.domain.character import CharacterPreset

        if not isinstance(preset, CharacterPreset):
            return {}

        # First pass: compute absolute positions by traversing from root
        absolute_positions: dict[str, tuple[float, float]] = {}

        def compute_absolute_position(joint_id: str) -> tuple[float, float]:
            """Recursively compute absolute position for a joint."""
            if joint_id in absolute_positions:
                return absolute_positions[joint_id]

            joint = preset.skeleton.get(joint_id)
            if not joint:
                return (0.0, 0.0)

            rel_x, rel_y = joint.position

            if joint.parent_id is None:
                # Root joint: position relative to canvas center
                abs_pos = (canvas_center[0] + rel_x, canvas_center[1] + rel_y)
            else:
                # Child joint: position relative to parent's absolute position
                parent_pos = compute_absolute_position(joint.parent_id)
                abs_pos = (parent_pos[0] + rel_x, parent_pos[1] + rel_y)

            absolute_positions[joint_id] = abs_pos
            return abs_pos

        # Compute all absolute positions
        for joint_id in preset.skeleton:
            compute_absolute_position(joint_id)

        # Build joints dictionary with absolute positions
        joints = {}
        for joint_id, joint in preset.skeleton.items():
            abs_pos = absolute_positions.get(joint_id, (0.0, 0.0))
            joints[joint_id] = {
                "id": joint.id,
                "name": joint.id,  # Add name field for visualization
                "parent": joint.parent_id,
                "position": [abs_pos[0], abs_pos[1]],
                "children": list(joint.children),
                "rotation": 0.0,  # Initial rotation
            }

        return {"joints": joints}

    def _map_orphan_mechanisms_to_character(self) -> None:
        """
        Rebind mechanisms to currently loaded character parts.

        Handles:
        - orphan mapping (missing/invalid part_name)
        - name-based mapping for part replacement
        - linkage/cam readjustment to current skeleton anchors
        """
        if not self.parts_data or not self.mechanism_layers:
            return

        result = self._character_rebind_service.rebind_all(
            mechanism_layers=self.mechanism_layers,
            parts_data=self.parts_data,
            skeleton_cache=getattr(self, "_initial_skeleton_data_cache", None),
            force_readjust=True,
        )
        for warning in result.warnings:
            logging.warning(warning)

        if not result.changed_ids:
            return

        for mechanism_id in result.changed_ids:
            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data:
                continue

            mech_type = str(layer_data.get("type", ""))
            if mech_type in ("4_bar_linkage", "cam"):
                self._regenerate_foundry_layer_simulation(mechanism_id, layer_data)

            self._visual_animator.build_cache(mechanism_id, layer_data)
            self._render_mechanism_layer(mechanism_id)

        self._setup_mechanism_ik_integration()
        self._update_all_ui_states()
        self._update_mechanism_layers_list()
        if self.mechanism_scene:
            self.mechanism_scene.update()

    def _get_character_position(self):
        skeleton_data = getattr(self, "_initial_skeleton_data_cache", None)
        return list(self._joint_mapping_service.get_character_ground_position(skeleton_data))

    def _handle_recommendation_selection(self, mechanism_data: dict[str, Any]):
        self._recommendation_controller.handle_recommendation_selection(mechanism_data, self)

    def _clear_mechanism_for_part(self, part_name: str):
        """Clear mechanism for a part. Delegates to Presenter."""
        self._mvp_presenter._clear_mechanism_for_part(part_name)

    def _clear_mechanism_trace(self, mechanism_id: str) -> None:
        """Clear the path trace for a specific mechanism."""
        if hasattr(self, "_path_trace_manager") and self._path_trace_manager:
            self._path_trace_manager.clear_trace(mechanism_id, self.mechanism_scene)

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

        # Build animation cache for performance optimization
        self._visual_animator.build_cache(mechanism_id, layer_data)

        # Calculate t=0 coupler position for path trace initialization
        initial_coupler_pos = None
        try:
            initial_coupler_pos = self._calculate_mechanism_output_position(
                layer_data.get("type", ""),
                layer_data.get("params", {}),
                0.0,  # time=0
                layer_data,
            )
        except Exception:
            pass  # Silently fail, trace will be initialized without initial point

        # Initialize path tracing with t=0 position and update UI
        self._path_trace_manager.init_trace(mechanism_id, self.mechanism_scene, initial_coupler_pos)
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

    def _scene_to_mechanism_coords_for_rebind(
        self, layer_data: dict[str, Any], scene_position: tuple[float, float]
    ) -> tuple[float, float] | None:
        inverse = self._get_inverse_scene_transform_function(layer_data)
        if inverse is None:
            return None

        try:
            mech_xy = inverse(QPointF(float(scene_position[0]), float(scene_position[1])))
            if mech_xy is None or len(mech_xy) < 2:
                return None
            return (float(mech_xy[0]), float(mech_xy[1]))
        except Exception:
            logging.debug("Suppressed exception while converting scene->mechanism", exc_info=True)
            return None

    def _extract_key_points_from_simulation(self, full_sim_data: dict, mechanism_type: str) -> dict:
        return self._output_calculator.extract_key_points_from_simulation(
            full_sim_data, mechanism_type
        )

    def _calculate_mechanism_output(
        self, mech_type: str, params: dict, time: float, layer_data: dict
    ) -> QPointF | None:
        return self._output_calculator.calculate_output(mech_type, params, time, layer_data)

    def _update_animation(self):
        if (
            not hasattr(self, "_animation_frame_coordinator")
            or not self._animation_frame_coordinator
        ):
            return
        self._animation_frame_coordinator.update_frame(
            tab_active=self._tab_active,
            mechanism_layers=self.mechanism_layers,
            part_enabled_state=self.part_enabled_state,
            parts_data=self.parts_data,
            ik_manager=getattr(self.main_window, "ik_manager", None),
            path_trace_manager=self._path_trace_manager,
            scene=self.mechanism_scene,
            initial_skeleton_cache=getattr(self, "_initial_skeleton_data_cache", None),
        )

    def _get_standardized_joint_id(self, abstract_joint_id: str) -> str | None:
        return self._mvp_presenter.get_standardized_joint_id(abstract_joint_id)

    def _update_mechanism_visuals_for_animation(
        self, mechanism_id: str, time: float, layer_data: dict
    ):
        import logging

        logging.debug(
            f"[TAB-VISUAL] _update_mechanism_visuals_for_animation called: id={mechanism_id}, time={time:.3f}"
        )
        try:
            self._visual_animator.update_visuals(
                mechanism_id=mechanism_id,
                time=time,
                layer_data=layer_data,
                visuals_factory=self.visuals_factory,
            )
        except Exception as e:
            logging.error(f"[TAB-VISUAL] Exception in update_visuals: {e}", exc_info=True)

    def _update_mechanism_layers_list(self):
        self._tab_data_coordinator.update_mechanism_layers_list(
            self.ui_widgets.get("mechanism_layers_list") if hasattr(self, "ui_widgets") else None,
            presenter_view_model=self._presenter_view_model,
            part_enabled_state=self.part_enabled_state,
            main_window=self.main_window,
        )

    def _part_has_mechanism(self, part_name: str) -> bool:
        if self._presenter_view_model:
            part_vm = self._presenter_view_model.find_part(part_name)
            if part_vm is not None and part_vm.has_layers:
                return True
        return any(ld.get("part_name") == part_name for ld in self.mechanism_layers.values())

    def _reset_skeleton_to_initial_state(self):
        self._mvp_presenter.reset_skeleton_to_initial_state()

    def _reset_character_rotations_to_world_zero(self):
        """
        Reset all character/part rotations to world 0.

        This ensures that when entering the mechanism design tab or resetting,
        all parts have zero rotation in world space, preventing broken orientations.
        """
        try:
            # Reset part item rotations to 0
            if hasattr(self, "current_editor_items") and self.current_editor_items:
                for _part_name, part_item in self.current_editor_items.items():
                    if part_item and hasattr(part_item, "setRotation"):
                        part_item.setRotation(0.0)
                        # Also update the initial world rotation to 0
                        if hasattr(part_item, "_initial_world_rotation"):
                            part_item._initial_world_rotation = 0.0
                logging.debug(f"Reset {len(self.current_editor_items)} part rotations to world 0")

            # Reset through IK manager if available
            main_window = getattr(self, "main_window", None)
            if main_window and hasattr(main_window, "ik_manager") and main_window.ik_manager:
                ik_manager = main_window.ik_manager
                # Reset animation state which restores initial rotations
                if hasattr(ik_manager, "reset_animation_state"):
                    ik_manager.reset_animation_state()
        except Exception:
            logging.debug("Suppressed exception during rotation reset", exc_info=True)

    def handle_mechanism_visuals(self, mechanism_graphics_data: dict):
        self._mvp_presenter.handle_mechanism_visuals(mechanism_graphics_data)

    def _clear_animation_cache(self):
        if hasattr(self, "_animation_frame_coordinator") and self._animation_frame_coordinator:
            self._animation_frame_coordinator.clear_animation_cache(self)

    def _safe_remove_visual_items(self, visual_items: list):
        self._visual_item_manager.set_scene_cleared_flag(
            getattr(self, "_scene_recently_cleared", False)
        )
        self._visual_item_manager.safe_remove_visual_items(visual_items)

    def cleanup_tab_resources(self):
        self._mvp_presenter._cleanup_resources()

    def prepare_tab_activation(self):
        self._mvp_presenter._prepare_activation()

    def _is_visual_item_invalid(self, item) -> bool:
        return self._visual_item_manager.is_visual_item_invalid(item)

    def deactivate_tab(self):
        """Deactivate tab - stop animation timers to prevent resource leaks."""
        self._tab_active = False

        # Sync tab_active with animation controller
        if hasattr(self, "_animation_controller") and self._animation_controller:
            self._animation_controller.tab_active = False

        # Stop animation controller (primary animation system)
        if hasattr(self, "_animation_controller") and self._animation_controller:
            try:
                self._animation_controller.stop_animation()
            except (TypeError, RuntimeError, AttributeError):
                logging.debug("Suppressed exception stopping animation controller", exc_info=True)

        # Stop legacy animation timer (vestigial, but prevent timer leak)
        if hasattr(self, "animation_timer") and self.animation_timer:
            try:
                self.animation_timer.stop()
            except (TypeError, RuntimeError):
                logging.debug("Suppressed exception stopping animation timer", exc_info=True)

        self.cleanup_tab_resources()

    def activate_tab(self):
        self._tab_active = True

        # Sync tab_active with animation controller
        if hasattr(self, "_animation_controller") and self._animation_controller:
            self._animation_controller.tab_active = True

        self.prepare_tab_activation()

        # Reset character/skeleton rotations to world 0 when entering tab
        # This prevents broken rotations from previous tab interactions
        self._reset_character_rotations_to_world_zero()

        self._update_mechanism_layers_list()
        self._update_all_ui_states()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            if hasattr(self, "_tab_visible"):
                self._tab_visible = True
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def handle_ik_update(self, ik_results: dict[str, dict[str, Any]]):
        if self.isVisible():
            self._mvp_presenter.handle_ik_update(ik_results)

    def _generate_mechanism_visuals_directly(
        self, mechanism_id: str, mechanism_type: str, params: dict, layer_data: dict
    ):
        self.handle_mechanism_visuals(
            {
                "mechanism_id": mechanism_id,
                "mechanism_type": mechanism_type,
                "params": params,
                **layer_data,
            }
        )

    def _on_start_animation(self):
        # Check animation controller state
        controller = getattr(self, "_animation_controller", None)

        # Defensive: If controller is missing, try to reinitialize it
        if controller is None:
            logging.warning(
                f"[ANIMATION] Animation controller missing, attempting reinitialization (tab_id={id(self)})"
            )
            if hasattr(self, "mechanism_scene") and hasattr(self, "_path_trace_manager"):
                try:
                    from automataii.presentation.qt.tabs.mechanism_design.components.animation_lifecycle_controller import (
                        AnimationLifecycleController,
                    )

                    self._animation_controller = AnimationLifecycleController(
                        mechanism_scene=self.mechanism_scene,
                        path_trace_manager=self._path_trace_manager,
                        parent=self,
                    )
                    # Configure callbacks via TabCallbackConfigurator
                    from automataii.presentation.qt.tabs.mechanism_design.services.callback_configurator import (
                        TabCallbackConfigurator,
                    )

                    TabCallbackConfigurator(self)._configure_animation_controller()
                    controller = self._animation_controller
                    logging.info("[ANIMATION] Controller reinitialized successfully")
                except Exception as e:
                    logging.error(f"[ANIMATION] Failed to reinitialize controller: {e}")
                    return

        if controller is None:
            logging.error("[ANIMATION] Cannot start animation - no controller available")
            return

        enabled_state = self.mechanism_enabled_state
        if enabled_state:
            logging.debug(f"[ANIMATION] Starting animation with {len(enabled_state)} mechanism(s)")
            controller.start_animation(
                mechanism_enabled_state=enabled_state,
                initial_skeleton_data=getattr(self, "_initial_skeleton_data_cache", None),
            )
        else:
            QMessageBox.warning(self, "Warning", "No mechanisms are enabled for animation.")

    def _on_stop_animation(self):
        if not hasattr(self, "_animation_controller") or not self._animation_controller:
            return
        self._animation_controller.stop_animation()

    def _on_reset_animation(self):
        if not hasattr(self, "_animation_controller") or not self._animation_controller:
            return
        self._animation_controller.reset_animation()
        # Also reset rotations to world 0 when resetting animation
        self._reset_character_rotations_to_world_zero()

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
        if (
            not hasattr(self, "_animation_frame_coordinator")
            or not self._animation_frame_coordinator
        ):
            return
        view_hints = self._animation_frame_coordinator.apply_performance_preset(preset)

        # Apply view-specific hints
        if hasattr(self, "mechanism_view") and self.mechanism_view:
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
            self._render_mechanism_layer(mechanism_id)
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)

    def _update_other_handles(self, mechanism_id: str, moved_handle: str):
        handles = (
            self.parametric_handles.get(mechanism_id, [])
            if hasattr(self, "parametric_handles")
            else []
        )
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
        has_enabled_mechanisms = (
            any(self.mechanism_enabled_state.values()) if self.mechanism_enabled_state else False
        )
        if self.mechanism_layers and has_enabled_mechanisms:
            self.play_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)

    def _on_export_blueprint(self):
        self.blueprint_exporter.export_all()

    @property
    def _grid_step_mm(self) -> float:
        return grid_step_mm(getattr(self, "_grid_cell_cm", DEFAULT_GRID_CELL_CM))

    @staticmethod
    def _normalize_foundry_mechanism_type(mechanism_type: str) -> str:
        if not isinstance(mechanism_type, str):
            return ""
        mechanism_type = mechanism_type.strip().lower()
        return {
            "fourbar": "four_bar",
            "four_bar": "four_bar",
            "four_bar_linkage": "four_bar",
            "4_bar_linkage": "four_bar",
            "slider_crank": "slider_crank",
            "slider-crank": "slider_crank",
            "slidercrank": "slider_crank",
            "cam": "cam_follower",
            "cam_follower": "cam_follower",
            "gear": "gear_train",
            "gear_train": "gear_train",
            "gear_linkage": "gear_linkage",
            "gear+linkage": "gear_linkage",
            "gear_linkage_train": "gear_linkage",
        }.get(mechanism_type, mechanism_type)

    @staticmethod
    def _length_param_keys_for_foundry_type(mechanism_type: str) -> tuple[str, ...]:
        normalized = MechanismDesignTab._normalize_foundry_mechanism_type(mechanism_type)
        if normalized in ("four_bar", "slider_crank"):
            return (
                "l1",
                "l2",
                "l3",
                "l4",
                "L1",
                "L2",
                "L3",
                "L4",
                "ground_link",
                "input_link",
                "coupler_link",
                "output_link",
                "crank_length",
                "rod_length",
            )
        if normalized == "cam_follower":
            return (
                "cam_radius",
                "cam_offset",
                "follower_length",
                "base_radius",
                "eccentricity",
                "follower_rod_length",
            )
        return ()

    def _snap_lengths_to_grid(
        self,
        mechanism_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return dict(
            snap_physical_params(
                mechanism_type,
                params,
                getattr(self, "_grid_cell_cm", DEFAULT_GRID_CELL_CM),
                enabled=bool(getattr(self, "_grid_system_enabled", False)),
                profile=getattr(self, "_physical_profile", DEFAULT_PHYSICAL_KIT_PROFILE),
            )
        )

    def _extract_grid_settings_from_foundry_parameters(
        self,
        parameters: dict[str, Any],
    ) -> tuple[bool, float] | None:
        has_setting = (
            "grid_system_enabled" in parameters
            or "grid_cell_cm" in parameters
            or "grid_pitch_choice" in parameters
            or "physical_profile_key" in parameters
        )
        if not has_setting:
            return None

        params = dict(parameters)
        params.setdefault("grid_system_enabled", getattr(self, "_grid_system_enabled", True))
        params.setdefault("grid_cell_cm", getattr(self, "_grid_cell_cm", DEFAULT_GRID_CELL_CM))
        params.setdefault(
            "grid_pitch_choice",
            getattr(
                self,
                "_grid_pitch_choice",
                physical_context_from_settings(
                    True,
                    DEFAULT_GRID_CELL_CM,
                    profile=DEFAULT_PHYSICAL_KIT_PROFILE,
                ).grid_pitch_choice,
            ),
        )
        params.setdefault(
            "physical_profile_key",
            getattr(self, "_physical_profile", DEFAULT_PHYSICAL_KIT_PROFILE).key,
        )
        context = physical_context_from_params(params)
        return context.enabled, context.grid_cell_cm

    def configure_grid_system(
        self,
        enabled: bool,
        cell_cm: float,
        *,
        profile: PhysicalKitProfile = DEFAULT_PHYSICAL_KIT_PROFILE,
        pitch_choice_key: str | None = None,
    ) -> None:
        context = physical_context_from_settings(
            enabled,
            cell_cm,
            pitch_choice_key,
            profile=profile,
        )
        self._grid_system_enabled = context.enabled
        self._grid_cell_cm = context.grid_cell_cm
        self._grid_pitch_choice = context.grid_pitch_choice
        self._physical_profile = context.profile
        if hasattr(self, "_mechanism_instantiation") and self._mechanism_instantiation:
            self._mechanism_instantiation.set_physical_context(context)
        if hasattr(self, "parametric_manager") and self.parametric_manager:
            self.parametric_manager.set_physical_profile(self._physical_profile)

        if (
            hasattr(self, "mechanism_view")
            and self.mechanism_view
            and hasattr(self.mechanism_view, "set_grid_configuration")
        ):
            self.mechanism_view.set_grid_configuration(
                self._grid_system_enabled,
                self._grid_cell_cm,
            )

        if not self.mechanism_layers:
            return

        changed_ids: list[str] = []
        for mechanism_id, layer_data in self.mechanism_layers.items():
            params = layer_data.get("params")
            if not isinstance(params, dict):
                continue
            before = dict(params)
            params.update(context.as_params())
            snapped = (
                self._snap_lengths_to_grid(
                    str(layer_data.get("type", "")),
                    params,
                )
                if self._grid_system_enabled
                else dict(params)
            )
            if snapped == params:
                if before != params:
                    changed_ids.append(mechanism_id)
                continue
            layer_data["params"] = snapped
            changed_ids.append(mechanism_id)

        for mechanism_id in changed_ids:
            layer_data = self.mechanism_layers.get(mechanism_id)
            if not layer_data:
                continue
            self._regenerate_foundry_layer_simulation(mechanism_id, layer_data)
            if hasattr(self, "_visual_animator") and self._visual_animator:
                self._visual_animator.build_cache(mechanism_id, layer_data)
            self._render_mechanism_layer(mechanism_id)

        if changed_ids and self.mechanism_scene:
            self.mechanism_scene.update()

    def set_physical_context(self, context: PhysicalKitContext) -> None:
        """Apply the app-owned physical context to Design caches and services."""
        self.configure_grid_system(
            context.enabled,
            context.grid_cell_cm,
            profile=context.profile,
            pitch_choice_key=context.grid_pitch_choice,
        )

    # --- Foundry Integration ---

    def import_mechanism_from_foundry(
        self,
        mechanism_type: str,
        parameters: dict,
        pivot_point: tuple,
        mechanism_id: str | None = None,
    ) -> bool:
        """
        Import a mechanism from Mechanism Foundry tab.

        Creates a new mechanism layer with the given configuration.
        If no part is selected, shows a part selection dialog.

        Args:
            mechanism_type: Foundry mechanism type (e.g., "four_bar", "cam_follower")
            parameters: Mechanism parameters from Foundry
            pivot_point: Pivot point coordinates
            mechanism_id: Optional ID for bidirectional sync with Foundry

        Returns:
            True if import successful, False otherwise
        """
        import logging

        logging.info(f"Importing mechanism from Foundry: {mechanism_type} (id={mechanism_id})")

        import_params = dict(parameters)
        foundry_snapshot = import_params.pop("__foundry_snapshot__", None)
        grid_settings = MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            self,
            import_params,
        )
        if grid_settings:
            context = physical_context_from_params(import_params)
            self.configure_grid_system(
                grid_settings[0],
                grid_settings[1],
                profile=context.profile,
                pitch_choice_key=context.grid_pitch_choice,
            )
        import_params = MechanismDesignTab._snap_lengths_to_grid(
            self,
            mechanism_type,
            import_params,
        )

        # Ensure character exists (auto-load default/dummy if needed)
        has_character = self._ensure_character_for_foundry_import()

        # Determine which part to associate with
        part_name = self._resolve_target_part_for_foundry_import()
        if not part_name:
            if has_character:
                logging.warning(
                    "Character data exists but no target part could be resolved for Foundry import."
                )
            else:
                logging.warning(
                    "Unable to import Foundry mechanism: no character parts available for assignment."
                )
            return False

        # Place mechanism near the selected part (fallback: current view center).
        scene_position = self._resolve_foundry_import_scene_position(part_name)

        # Create layer data from Foundry export
        try:
            layer_data = self._mechanism_instantiation.create_layer_data_from_foundry(
                mechanism_type=mechanism_type,
                parameters=import_params,
                pivot_point=pivot_point,
                part_name=part_name,
                scene_position=scene_position,
                foundry_snapshot=foundry_snapshot if isinstance(foundry_snapshot, dict) else None,
            )
        except ValueError as exc:
            logging.warning("Failed to create layer data from Foundry export: %s", exc)
            return False

        if not layer_data:
            logging.warning("Failed to create layer data from Foundry export")
            return False

        # Use provided mechanism_id for bidirectional sync, or generate one
        if mechanism_id:
            layer_data["id"] = mechanism_id
            layer_data["foundry_synced"] = True  # Mark as synced with Foundry
        else:
            mechanism_id = layer_data.get("id", "unknown")
        mechanism_id = str(mechanism_id)
        layer_data["id"] = mechanism_id

        # Add to mechanism layers
        self.mechanism_enabled_state[mechanism_id] = True
        self._add_mechanism_layer(mechanism_id, layer_data)

        # Ensure simulation data is initialized for animation-ready Foundry imports.
        self._regenerate_foundry_layer_simulation(mechanism_id, layer_data)

        # Create visuals
        self._render_mechanism_layer(mechanism_id)

        # Update UI
        self._update_mechanism_layers_list()
        self._update_all_ui_states()
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)

        # Switch to Design tab
        if hasattr(self, "parent") and self.parent():
            parent = self.parent()
            while parent:
                if hasattr(parent, "tab_widget"):
                    # Find the Design tab index
                    for i in range(parent.tab_widget.count()):
                        if parent.tab_widget.widget(i) is self:
                            parent.tab_widget.setCurrentIndex(i)
                            break
                    break
                parent = parent.parent() if hasattr(parent, "parent") else None

        logging.info(f"Successfully imported mechanism: {mechanism_id}")
        return True

    def update_from_foundry(self, mechanism_id: str, mechanism_type: str, parameters: dict) -> None:
        """Update mechanism from Foundry tab changes (bidirectional sync).

        Called when mechanism parameters are modified in Foundry.
        Updates the mechanism layer without emitting change signals back.

        Args:
            mechanism_id: The shared mechanism ID
            mechanism_type: The mechanism type
            parameters: Updated parameters from Foundry
        """
        import logging

        if mechanism_id not in self.mechanism_layers:
            logging.debug(f"Mechanism {mechanism_id} not found in Design Tab")
            return

        update_params = dict(parameters)
        update_params.pop("__foundry_snapshot__", None)
        grid_settings = MechanismDesignTab._extract_grid_settings_from_foundry_parameters(
            self,
            update_params,
        )
        if grid_settings:
            context = physical_context_from_params(update_params)
            self.configure_grid_system(
                grid_settings[0],
                grid_settings[1],
                profile=context.profile,
                pitch_choice_key=context.grid_pitch_choice,
            )
        layer_data = self.mechanism_layers[mechanism_id]

        # Suppress signal emission to prevent infinite loop
        self._suppress_foundry_sync = True
        try:
            # Normalize Foundry schema to Design schema before updating layer params.
            mapped_params = dict(update_params)
            try:
                if hasattr(self, "_mechanism_instantiation") and self._mechanism_instantiation:
                    mapped_params = self._mechanism_instantiation.map_foundry_params_to_internal(
                        mechanism_type, update_params
                    )
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

            mapped_params = MechanismDesignTab._snap_lengths_to_grid(
                self,
                mechanism_type,
                mapped_params,
            )

            # Preserve mechanism-space/editor coordinates from existing params.
            merged_params = dict(layer_data.get("params", {}))
            merged_params.update(mapped_params)

            # Preserve input angle and map it to crank_angle for linkage previews.
            if "input_angle" in update_params:
                try:
                    input_angle = float(update_params["input_angle"])
                    merged_params["input_angle"] = input_angle
                    if mechanism_type in ("four_bar", "fourbar"):
                        merged_params["crank_angle"] = input_angle
                except (TypeError, ValueError):
                    pass

            normalized_type = MechanismDesignTab._normalize_foundry_mechanism_type(mechanism_type)
            if normalized_type == "slider_crank":
                normalized_type = "four_bar"

            # Keep 4-bar aliases synchronized so all editors/mappers see consistent values.
            if normalized_type == "four_bar":
                for lower_key, upper_key in (
                    ("l1", "L1"),
                    ("l2", "L2"),
                    ("l3", "L3"),
                    ("l4", "L4"),
                ):
                    if lower_key in merged_params:
                        try:
                            merged_params[upper_key] = float(merged_params[lower_key])
                        except (TypeError, ValueError):
                            pass
                    elif upper_key in merged_params:
                        try:
                            merged_params[lower_key] = float(merged_params[upper_key])
                        except (TypeError, ValueError):
                            pass

                if "input_angle" in merged_params:
                    try:
                        merged_params["crank_angle"] = float(merged_params["input_angle"])
                    except (TypeError, ValueError):
                        pass

                rebuild_fourbar_scene_geometry_from_params(layer_data, merged_params)

            layer_data["params"] = merged_params

            self._regenerate_foundry_layer_simulation(mechanism_id, layer_data)

            # Rebuild animation cache
            self._visual_animator.build_cache(mechanism_id, layer_data)

            # Update visuals
            self._render_mechanism_layer(mechanism_id)

            # Update scene
            if self.mechanism_scene:
                self.mechanism_scene.update()

            logging.debug(f"Updated mechanism {mechanism_id} from Foundry")

        finally:
            self._suppress_foundry_sync = False

    def _regenerate_foundry_layer_simulation(
        self, mechanism_id: str, layer_data: dict[str, Any]
    ) -> None:
        """Recompute derived payload for Foundry-synced layers before cache rebuild."""
        mech_type = str(layer_data.get("type", ""))
        if mech_type == "gear":
            MechanismDesignTab._refresh_foundry_gear_geometry(layer_data)
            return
        if mech_type not in ("4_bar_linkage", "cam"):
            return

        try:
            if hasattr(self, "parametric_manager") and self.parametric_manager:
                self.parametric_manager._regenerate_mechanism_simulation(mechanism_id, layer_data)
        except Exception:
            logging.debug("Suppressed exception while regenerating Foundry layer", exc_info=True)

    @staticmethod
    def _finite_point(value: object) -> tuple[float, float] | None:
        try:
            x_raw = value[0]  # type: ignore[index]
            y_raw = value[1]  # type: ignore[index]
        except (TypeError, IndexError, KeyError):
            return None
        x_coord = finite_float(x_raw, math.nan)
        y_coord = finite_float(y_raw, math.nan)
        if not math.isfinite(x_coord) or not math.isfinite(y_coord):
            return None
        return x_coord, y_coord

    @staticmethod
    def _gear_center_from_layer(
        layer_data: dict[str, Any],
        key_point_name: str,
        x_param: str,
        y_param: str,
    ) -> tuple[float, float] | None:
        key_points = layer_data.get("key_points")
        if isinstance(key_points, dict):
            point = MechanismDesignTab._finite_point(key_points.get(key_point_name))
            if point is not None:
                return point

        params = layer_data.get("params")
        if isinstance(params, dict) and x_param in params and y_param in params:
            point = MechanismDesignTab._finite_point((params.get(x_param), params.get(y_param)))
            if point is not None:
                return point

        return None

    @staticmethod
    def _refresh_foundry_gear_geometry(layer_data: dict[str, Any]) -> None:
        """Keep Foundry-synced gear metadata aligned with the latest radii."""
        params = layer_data.get("params")
        if not isinstance(params, dict):
            return

        profile = physical_profile_from_params(params)
        if grid_enabled_from_params(params):
            params.update(snap_gear_params(params, profile=profile))
        r1 = positive_finite_param(params, "gear1_radius", "r1", default=48.0)
        r2 = positive_finite_param(params, "gear2_radius", "r2", default=72.0)
        params["r1"] = r1
        params["r2"] = r2
        params["gear1_radius"] = r1
        params["gear2_radius"] = r2

        center_distance = max(
            10.0,
            gear_center_distance(
                r1,
                r2,
                params.get("gear_clearance", params.get("mesh_clearance")),
                profile=profile,
            ),
        )
        gear1_center = MechanismDesignTab._gear_center_from_layer(
            layer_data, "gear1_center", "gear1_x", "gear1_y"
        )
        gear2_center = MechanismDesignTab._gear_center_from_layer(
            layer_data, "gear2_center", "gear2_x", "gear2_y"
        )

        if gear1_center is not None and gear2_center is not None:
            dx = gear2_center[0] - gear1_center[0]
            dy = gear2_center[1] - gear1_center[1]
            old_distance = math.hypot(dx, dy)
            if old_distance > 1e-9:
                unit_x = dx / old_distance
                unit_y = dy / old_distance
            else:
                unit_x, unit_y = 1.0, 0.0
            midpoint = (
                (gear1_center[0] + gear2_center[0]) / 2.0,
                (gear1_center[1] + gear2_center[1]) / 2.0,
            )
            half_distance = center_distance / 2.0
            gear1_center = (
                midpoint[0] - unit_x * half_distance,
                midpoint[1] - unit_y * half_distance,
            )
            gear2_center = (
                midpoint[0] + unit_x * half_distance,
                midpoint[1] + unit_y * half_distance,
            )
        elif gear1_center is not None:
            gear2_center = (gear1_center[0] + center_distance, gear1_center[1])
        elif gear2_center is not None:
            gear1_center = (gear2_center[0] - center_distance, gear2_center[1])
        else:
            transform_params = layer_data.get("transform_params")
            center = (
                MechanismDesignTab._finite_point(transform_params.get("center"))
                if isinstance(transform_params, dict)
                else None
            )
            if center is None:
                center = (0.0, 0.0)
            half_distance = center_distance / 2.0
            gear1_center = (center[0] - half_distance, center[1])
            gear2_center = (center[0] + half_distance, center[1])

        key_points = layer_data.get("key_points")
        if not isinstance(key_points, dict):
            key_points = {}
            layer_data["key_points"] = key_points
        key_points["gear1_center"] = [float(gear1_center[0]), float(gear1_center[1])]
        key_points["gear2_center"] = [float(gear2_center[0]), float(gear2_center[1])]

        params["gear1_x"] = float(gear1_center[0])
        params["gear1_y"] = float(gear1_center[1])
        params["gear2_x"] = float(gear2_center[0])
        params["gear2_y"] = float(gear2_center[1])

        full_simulation_data = layer_data.get("full_simulation_data")
        if not isinstance(full_simulation_data, dict):
            full_simulation_data = {}
            layer_data["full_simulation_data"] = full_simulation_data
        gear_data = full_simulation_data.get("gear_data")
        if not isinstance(gear_data, dict):
            gear_data = {}
            full_simulation_data["gear_data"] = gear_data
        gear_data["gear1_centers"] = [[float(gear1_center[0]), float(gear1_center[1])]]
        gear_data["gear2_centers"] = [[float(gear2_center[0]), float(gear2_center[1])]]

    def _render_mechanism_layer(self, mechanism_id: str) -> None:
        """Render mechanism layer using Presenter payload schema."""
        layer_data = self.mechanism_layers.get(mechanism_id)
        if not layer_data:
            return

        self.handle_mechanism_visuals(
            {
                "mechanism_id": mechanism_id,
                "mechanism_type": layer_data.get("type"),
                **layer_data,
            }
        )

    def _emit_mechanism_params_changed(self, mechanism_id: str) -> None:
        """Emit parameter changes for SSOT history and optional Foundry listeners."""
        if getattr(self, "_suppress_foundry_sync", False):
            return

        if mechanism_id not in self.mechanism_layers:
            return

        layer_data = self.mechanism_layers[mechanism_id]

        params = layer_data.get("params", {})
        self.mechanism_parameters_changed.emit(mechanism_id, params)

    def get_ms4n_snapshot_source(self, mechanism_id: str | None = None) -> dict[str, Any]:
        """
        Return a read-only presentation snapshot source for the Lab/MS4N adapter.

        This is intentionally a narrow public seam: Lab consumes this mapping through
        `ms4n_snapshot_adapter.py`, which converts Qt trace points before they cross
        into application/domain code.
        """
        selected_id = mechanism_id or self.selected_mechanism_id
        if not selected_id and self.mechanism_layers:
            selected_id = next(iter(self.mechanism_layers))

        layer_data: dict[str, Any] = {}
        if selected_id:
            raw_layer_data = self.mechanism_layers.get(selected_id, {})
            if isinstance(raw_layer_data, dict):
                layer_data = dict(raw_layer_data)

        params = layer_data.get("params")
        if not isinstance(params, dict):
            params = dict(self.mechanism_params)

        def plain_point(point: object) -> tuple[float, float]:
            if isinstance(point, QPointF):
                x = point.x()
                y = point.y()
            elif isinstance(point, list | tuple) and len(point) >= 2:
                x = float(point[0])
                y = float(point[1])
            else:
                x_attr = getattr(point, "x", None)
                y_attr = getattr(point, "y", None)
                if callable(x_attr) and callable(y_attr):
                    x = float(x_attr())
                    y = float(y_attr())
                else:
                    raise ValueError(f"Unsupported MS4N snapshot point: {type(point).__name__}")
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("MS4N snapshot points must be finite")
            return (x, y)

        raw_key_points = layer_data.get("key_points", {})
        key_points: dict[str, tuple[float, float]] = {}
        if isinstance(raw_key_points, dict):
            key_points = {str(name): plain_point(point) for name, point in raw_key_points.items()}

        raw_trace_points: list[QPointF] = []
        trace_points: list[tuple[float, float]] = []
        if not isinstance(key_points, dict):
            key_points = {}
        if selected_id and hasattr(self, "_path_trace_manager") and self._path_trace_manager:
            raw_trace_points = self._path_trace_manager.get_trace_points(selected_id)
            trace_points = [plain_point(point) for point in raw_trace_points]

        return {
            "mechanism_id": selected_id or "",
            "mechanism_type": layer_data.get("type") or self.current_mechanism_type or "",
            "part_name": layer_data.get("part_name") or self.selected_part_name or "",
            "parameters": params,
            "key_points": key_points,
            "trace_points": trace_points,
            "coordinate_space": "scene",
        }

    def center_on_character(self):
        if not self.mechanism_view:
            return
        self._view_utilities_service.center_view_on_character(
            self.mechanism_view,
            current_editor_items=self.current_editor_items,
            skeleton_joint_items=getattr(self, "skeleton_joint_items", None),
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
            if hasattr(self, "_animation_controller") and self._animation_controller:
                self._animation_controller.stop_animation()
        except (TypeError, RuntimeError, AttributeError) as e:
            logging.debug(f"MechanismDesignTab: Animation controller cleanup: {e}")

        # Stop legacy animation timer (vestigial, but cleanup for safety)
        try:
            if hasattr(self, "animation_timer") and self.animation_timer:
                self.animation_timer.stop()
                self.animation_timer.timeout.disconnect()
        except (TypeError, RuntimeError) as e:
            logging.debug(f"MechanismDesignTab: Timer cleanup: {e}")

        # Disconnect presenter listeners
        try:
            if hasattr(self, "_presenter") and self._presenter:
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
