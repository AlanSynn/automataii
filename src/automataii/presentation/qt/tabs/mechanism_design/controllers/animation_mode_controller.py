"""
Animation Mode Controller for MechanismDesignTab.

Extracted from god class decomposition to handle animation lifecycle,
frame updates, and animation state management.

Design Pattern: Controller (handles animation mode operations)
Architecture: Hexagonal - Presentation Layer
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene
    from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import PathTraceManager
    from automataii.presentation.qt.tabs.mechanism_design.services import AnimationFrameCoordinator


class AnimationModeController(QObject):
    """
    Controls animation mode operations for MechanismDesignTab.

    Responsibilities:
    - Start/stop/reset animation
    - Manage animation timer
    - Coordinate with IK system
    - Update mechanism visuals during animation
    - Manage path traces

    This controller owns the animation timer and delegates frame updates
    to AnimationFrameCoordinator.
    """

    def __init__(
        self,
        *,
        animation_timer: QTimer,
        animation_frame_coordinator: "AnimationFrameCoordinator",
        path_trace_manager: "PathTraceManager",
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize controller.

        Args:
            animation_timer: QTimer for animation frame updates
            animation_frame_coordinator: Coordinator for frame calculations
            path_trace_manager: Manager for path trace visualization
            parent: Parent QObject
        """
        super().__init__(parent)
        self._timer = animation_timer
        self._frame_coordinator = animation_frame_coordinator
        self._path_trace_manager = path_trace_manager

        # Callbacks (injected from Tab)
        self._get_mechanism_layers_fn: Callable[[], dict] | None = None
        self._get_mechanism_enabled_state_fn: Callable[[], dict] | None = None
        self._get_part_enabled_state_fn: Callable[[], dict] | None = None
        self._get_parts_data_fn: Callable[[], dict] | None = None
        self._get_ik_manager_fn: Callable[[], Any] | None = None
        self._get_scene_fn: Callable[[], "QGraphicsScene"] | None = None
        self._get_skeleton_cache_fn: Callable[[], dict | None] | None = None
        self._get_tab_active_fn: Callable[[], bool] | None = None
        self._setup_ik_integration_fn: Callable[[], bool] | None = None
        self._reset_skeleton_fn: Callable[[], None] | None = None
        self._ensure_skeleton_viz_fn: Callable[[dict], None] | None = None
        self._update_ui_state_fn: Callable[[], None] | None = None
        self._position_parts_fn: Callable[[], None] | None = None

    def configure_callbacks(
        self,
        *,
        get_mechanism_layers: Callable[[], dict],
        get_mechanism_enabled_state: Callable[[], dict],
        get_part_enabled_state: Callable[[], dict],
        get_parts_data: Callable[[], dict],
        get_ik_manager: Callable[[], Any],
        get_scene: Callable[[], "QGraphicsScene"],
        get_skeleton_cache: Callable[[], dict | None],
        get_tab_active: Callable[[], bool],
        setup_ik_integration: Callable[[], bool],
        reset_skeleton: Callable[[], None],
        ensure_skeleton_viz: Callable[[dict], None],
        update_ui_state: Callable[[], None],
        position_parts: Callable[[], None],
    ) -> None:
        """Configure callbacks for Tab method delegation."""
        self._get_mechanism_layers_fn = get_mechanism_layers
        self._get_mechanism_enabled_state_fn = get_mechanism_enabled_state
        self._get_part_enabled_state_fn = get_part_enabled_state
        self._get_parts_data_fn = get_parts_data
        self._get_ik_manager_fn = get_ik_manager
        self._get_scene_fn = get_scene
        self._get_skeleton_cache_fn = get_skeleton_cache
        self._get_tab_active_fn = get_tab_active
        self._setup_ik_integration_fn = setup_ik_integration
        self._reset_skeleton_fn = reset_skeleton
        self._ensure_skeleton_viz_fn = ensure_skeleton_viz
        self._update_ui_state_fn = update_ui_state
        self._position_parts_fn = position_parts

    @property
    def is_running(self) -> bool:
        """Check if animation is currently running."""
        return self._timer.isActive()

    @property
    def animation_time(self) -> float:
        """Current animation time."""
        return self._frame_coordinator.animation_time

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set animation time."""
        self._frame_coordinator.animation_time = value

    @property
    def animation_speed(self) -> float:
        """Animation speed multiplier."""
        return self._frame_coordinator.animation_speed

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed."""
        self._frame_coordinator.animation_speed = value

    def start_animation(self, parent_widget: QObject | None = None) -> bool:
        """
        Start the animation.

        Args:
            parent_widget: Parent widget for message boxes

        Returns:
            True if animation started successfully
        """
        mechanism_enabled_state = self._get_mechanism_enabled_state_fn() if self._get_mechanism_enabled_state_fn else {}

        if not mechanism_enabled_state or not any(mechanism_enabled_state.values()):
            if parent_widget:
                QMessageBox.warning(
                    parent_widget,
                    "Warning",
                    "No mechanisms are enabled for animation."
                )
            return False

        # Ensure skeleton visualization before animation
        skeleton_cache = self._get_skeleton_cache_fn() if self._get_skeleton_cache_fn else None
        if skeleton_cache and self._ensure_skeleton_viz_fn:
            self._ensure_skeleton_viz_fn(skeleton_cache)

        # Setup IK integration
        if self._setup_ik_integration_fn:
            self._setup_ik_integration_fn()

        # Start IK animation if manager available
        ik_manager = self._get_ik_manager_fn() if self._get_ik_manager_fn else None
        if ik_manager and hasattr(ik_manager, 'start_animation'):
            ik_manager.start_animation()

        # Start animation timer (60 FPS)
        self._timer.start(16)

        # Update UI
        if self._update_ui_state_fn:
            self._update_ui_state_fn()

        return True

    def stop_animation(self) -> None:
        """Stop the animation."""
        # Stop timer
        if self._timer.isActive():
            self._timer.stop()

        # Stop IK animation
        ik_manager = self._get_ik_manager_fn() if self._get_ik_manager_fn else None
        if ik_manager:
            if hasattr(ik_manager, 'stop_animation'):
                ik_manager.stop_animation()
            if hasattr(ik_manager, 'clear_mechanism_position_targets'):
                ik_manager.clear_mechanism_position_targets()

        # Update UI
        if self._update_ui_state_fn:
            self._update_ui_state_fn()

    def reset_animation(self) -> None:
        """Reset animation to initial state."""
        # Stop if running
        self.stop_animation()

        # Reset animation time
        self._frame_coordinator.animation_time = 0.0
        self._frame_coordinator.reset_state()

        # Clear all traces
        scene = self._get_scene_fn() if self._get_scene_fn else None
        if scene:
            for mech_id in self._path_trace_manager.get_all_mechanism_ids():
                self._path_trace_manager.clear_trace(mech_id, scene)

        # Reset skeleton
        if self._reset_skeleton_fn:
            self._reset_skeleton_fn()

        # Position parts
        if self._position_parts_fn:
            self._position_parts_fn()

        # Update UI
        if self._update_ui_state_fn:
            self._update_ui_state_fn()

    def update_frame(self) -> None:
        """
        Update single animation frame.

        Called by animation timer. Delegates to AnimationFrameCoordinator.
        """
        tab_active = self._get_tab_active_fn() if self._get_tab_active_fn else False
        mechanism_layers = self._get_mechanism_layers_fn() if self._get_mechanism_layers_fn else {}
        part_enabled_state = self._get_part_enabled_state_fn() if self._get_part_enabled_state_fn else {}
        parts_data = self._get_parts_data_fn() if self._get_parts_data_fn else {}
        ik_manager = self._get_ik_manager_fn() if self._get_ik_manager_fn else None
        scene = self._get_scene_fn() if self._get_scene_fn else None
        skeleton_cache = self._get_skeleton_cache_fn() if self._get_skeleton_cache_fn else None

        if not scene:
            return

        self._frame_coordinator.update_frame(
            tab_active=tab_active,
            mechanism_layers=mechanism_layers,
            part_enabled_state=part_enabled_state,
            parts_data=parts_data,
            ik_manager=ik_manager,
            path_trace_manager=self._path_trace_manager,
            scene=scene,
            initial_skeleton_cache=skeleton_cache,
        )

    def clear_traces_for_selection_change(self) -> None:
        """Clear all traces when selection changes."""
        scene = self._get_scene_fn() if self._get_scene_fn else None
        if scene:
            for mech_id in self._path_trace_manager.get_all_mechanism_ids():
                self._path_trace_manager.clear_trace(mech_id, scene)

    def clear_animation_cache(self, target_object: Any) -> None:
        """Clear animation cache on target object."""
        self._frame_coordinator.clear_animation_cache(target_object)
