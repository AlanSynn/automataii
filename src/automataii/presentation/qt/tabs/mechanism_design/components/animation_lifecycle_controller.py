"""
Animation Lifecycle Controller - Animation start/stop/reset and frame updates.

Extracted from MechanismDesignTab god class. Handles animation timer management,
frame updates, and IK integration during animation.

Design Pattern: Controller (coordinates animation lifecycle)

Integration:
    This controller can optionally use a CentralAnimationScheduler for unified
    animation timing across all tabs. If no scheduler is set, it falls back to
    using its own QTimer for backward compatibility.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QElapsedTimer, QObject, QPointF, QTimer, pyqtSignal

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene

    from automataii.presentation.qt.animation import CentralAnimationScheduler
    from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import PathTraceManager


class AnimationLifecycleController(QObject):
    """
    Controls animation lifecycle for mechanism design.

    Responsibilities:
    - Manage animation timer start/stop/reset
    - Update animation frames and calculate mechanism outputs
    - Integrate with IK system for skeleton animation
    - Throttle IK updates for performance
    - Coordinate path tracing during animation

    Signals:
        animation_started: Emitted when animation starts
        animation_stopped: Emitted when animation stops
        animation_reset: Emitted when animation resets
        frame_updated: Emitted after each animation frame
    """

    animation_started = pyqtSignal()
    animation_stopped = pyqtSignal()
    animation_reset = pyqtSignal()
    frame_updated = pyqtSignal(float)  # current_time

    def __init__(
        self,
        mechanism_scene: QGraphicsScene,
        path_trace_manager: PathTraceManager,
        parent: QObject | None = None,
    ) -> None:
        """
        Initialize animation lifecycle controller.

        Args:
            mechanism_scene: The graphics scene for mechanism visualization
            path_trace_manager: Manager for path tracing
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._mechanism_scene = mechanism_scene
        self._path_trace_manager = path_trace_manager

        # Central scheduler (optional, for unified animation timing)
        self._scheduler: CentralAnimationScheduler | None = None
        self._subscription_id = "mechanism_design_animation"

        # Fallback animation timer (used when no scheduler is set)
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._update_animation_legacy)
        self._animation_time = 0.0
        self._animation_speed = 1.0  # radians per second
        self._tab_active = False
        self._use_scheduler = False  # Whether scheduler is actively being used

        # IK throttling for performance
        self._ik_update_rate_hz: int = 30
        self._ik_min_interval_ms: int = int(1000 / max(1, self._ik_update_rate_hz))
        self._ik_throttle_timer: QElapsedTimer = QElapsedTimer()
        self._ik_throttle_timer.invalidate()
        self._last_target_pos_by_joint: dict[str, QPointF] = {}
        self._pos_epsilon_px: float = 0.5

        # Mechanism update batching
        self._mechanism_update_fraction: float = 0.5
        self._mech_rr_cursor: int = 0
        self._trace_frame_tick: int = 0

        # Callbacks for external state/operations
        self._get_main_window: Callable[[], Any] = lambda: None
        self._get_mechanism_layers: Callable[[], dict[str, Any]] = lambda: {}
        self._get_part_enabled_state: Callable[[], dict[str, bool]] = lambda: {}
        self._get_parts_data: Callable[[], dict[str, Any]] = lambda: {}
        self._get_presenter: Callable[[], Any] = lambda: None
        self._get_ui_state_manager: Callable[[], Any] = lambda: None
        self._calculate_mechanism_output: Callable[[str, dict, float, dict], QPointF | None] = lambda a, b, c, d: None
        self._update_mechanism_visuals_for_animation: Callable[[str, float, dict], None] = lambda a, b, c: None
        self._get_target_joint_for_mechanism_control: Callable[[str, str], str] = lambda a, b: b
        self._get_standardized_joint_id: Callable[[str], str | None] = lambda x: None
        self._ensure_skeleton_visualization: Callable[[dict], None] = lambda x: None
        self._setup_mechanism_ik_integration: Callable[[], bool] = lambda: False
        self._reset_skeleton_to_initial_state: Callable[[], None] = lambda: None
        self._position_parts_at_anchor_joints: Callable[[], None] = lambda: None
        self._clear_animation_cache: Callable[[], None] = lambda: None

    def configure_callbacks(
        self,
        get_main_window: Callable[[], Any],
        get_mechanism_layers: Callable[[], dict[str, Any]],
        get_part_enabled_state: Callable[[], dict[str, bool]],
        get_parts_data: Callable[[], dict[str, Any]],
        get_presenter: Callable[[], Any],
        get_ui_state_manager: Callable[[], Any],
        calculate_mechanism_output: Callable[[str, dict, float, dict], QPointF | None],
        update_mechanism_visuals_for_animation: Callable[[str, float, dict], None],
        get_target_joint_for_mechanism_control: Callable[[str, str], str],
        get_standardized_joint_id: Callable[[str], str | None],
        ensure_skeleton_visualization: Callable[[dict], None],
        setup_mechanism_ik_integration: Callable[[], bool],
        reset_skeleton_to_initial_state: Callable[[], None],
        position_parts_at_anchor_joints: Callable[[], None],
        clear_animation_cache: Callable[[], None],
    ) -> None:
        """Configure callback functions for external state access."""
        self._get_main_window = get_main_window
        self._get_mechanism_layers = get_mechanism_layers
        self._get_part_enabled_state = get_part_enabled_state
        self._get_parts_data = get_parts_data
        self._get_presenter = get_presenter
        self._get_ui_state_manager = get_ui_state_manager
        self._calculate_mechanism_output = calculate_mechanism_output
        self._update_mechanism_visuals_for_animation = update_mechanism_visuals_for_animation
        self._get_target_joint_for_mechanism_control = get_target_joint_for_mechanism_control
        self._get_standardized_joint_id = get_standardized_joint_id
        self._ensure_skeleton_visualization = ensure_skeleton_visualization
        self._setup_mechanism_ik_integration = setup_mechanism_ik_integration
        self._reset_skeleton_to_initial_state = reset_skeleton_to_initial_state
        self._position_parts_at_anchor_joints = position_parts_at_anchor_joints
        self._clear_animation_cache = clear_animation_cache
        self._callbacks_configured = True

    def is_configured(self) -> bool:
        """Check if essential callbacks have been configured.

        Returns:
            True if callbacks are configured, False otherwise
        """
        return getattr(self, '_callbacks_configured', False)

    # --- Properties ---

    @property
    def animation_time(self) -> float:
        """Get current animation time."""
        return self._animation_time

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set current animation time."""
        self._animation_time = value

    @property
    def animation_speed(self) -> float:
        """Get animation speed multiplier."""
        return self._animation_speed

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed multiplier."""
        self._animation_speed = value

    @property
    def tab_active(self) -> bool:
        """Get whether tab is active."""
        return self._tab_active

    @tab_active.setter
    def tab_active(self, value: bool) -> None:
        """Set whether tab is active."""
        self._tab_active = value

    @property
    def animation_timer(self) -> QTimer:
        """Get the animation timer."""
        return self._animation_timer

    def is_animation_running(self) -> bool:
        """Check if animation is currently running."""
        if self._scheduler and self._use_scheduler:
            return self._use_scheduler
        return self._animation_timer.isActive()

    # --- Scheduler Integration ---

    def set_scheduler(self, scheduler: CentralAnimationScheduler | None) -> None:
        """
        Set the central animation scheduler for unified timing.

        Args:
            scheduler: The CentralAnimationScheduler instance, or None to use local timer
        """
        # Unsubscribe from previous scheduler if any
        if self._scheduler and self._use_scheduler:
            self._scheduler.unsubscribe(self._subscription_id)
            self._use_scheduler = False

        self._scheduler = scheduler

        if scheduler:
            logging.info("AnimationLifecycleController: Using CentralAnimationScheduler")
        else:
            logging.info("AnimationLifecycleController: Using local QTimer fallback")

    def _subscribe_to_scheduler(self) -> None:
        """Subscribe to the central scheduler for animation updates."""
        logging.debug(f"[ANIM-SUB] _subscribe_to_scheduler: scheduler={self._scheduler is not None}, use_scheduler={self._use_scheduler}")
        if self._scheduler and not self._use_scheduler:
            from automataii.presentation.qt.animation import AnimationPriority

            self._scheduler.subscribe(
                callback=self._update_animation,
                priority=AnimationPriority.HIGH,
                owner_id=self._subscription_id,
            )
            self._use_scheduler = True
            logging.info(f"[ANIM-SUB] Subscribed to scheduler: id={self._subscription_id}, scheduler_running={self._scheduler.is_running}")

    def _unsubscribe_from_scheduler(self) -> None:
        """Unsubscribe from the central scheduler."""
        if self._scheduler and self._use_scheduler:
            self._scheduler.unsubscribe(self._subscription_id)
            self._use_scheduler = False

    # --- Performance Settings ---

    def set_ik_update_rate(self, rate_hz: int) -> None:
        """Set IK update rate in Hz."""
        self._ik_update_rate_hz = max(1, rate_hz)
        self._ik_min_interval_ms = int(1000 / self._ik_update_rate_hz)

    def set_mechanism_update_fraction(self, fraction: float) -> None:
        """Set fraction of mechanisms to update per frame (0.0-1.0)."""
        self._mechanism_update_fraction = max(0.05, min(1.0, fraction))

    def set_position_epsilon(self, epsilon_px: float) -> None:
        """Set minimum position change to trigger IK update."""
        self._pos_epsilon_px = max(0.0, epsilon_px)

    # --- Animation Control ---

    def start_animation(self, mechanism_enabled_state: dict[str, bool], initial_skeleton_data: dict | None = None) -> None:
        """
        Start the animation timer and IK animation.

        Args:
            mechanism_enabled_state: Dict of mechanism_id -> enabled state
            initial_skeleton_data: Initial skeleton data for visualization
        """
        # CRITICAL: Ensure tab_active is True when starting animation
        self._tab_active = True
        logging.debug("[ANIM] start_animation: Set tab_active=True")

        # Reset animation state to start fresh
        self._animation_time = 0
        self._trace_frame_tick = 0

        # Clear all existing path traces to prevent "jump" from stale positions
        for mechanism_id in self._path_trace_manager.get_all_mechanism_ids():
            self._path_trace_manager.clear_trace_points_only(mechanism_id)

        # Check if callbacks are configured
        if not self.is_configured():
            logging.warning("AnimationLifecycleController: Callbacks not configured! Animation may not work correctly.")

        if not mechanism_enabled_state:
            logging.warning("AnimationLifecycleController: No mechanisms enabled for animation")
            return

        # Ensure skeleton is properly initialized before starting animation
        if initial_skeleton_data:
            self._ensure_skeleton_visualization(initial_skeleton_data)

        # Setup comprehensive mechanism-IK integration
        integration_success = self._setup_mechanism_ik_integration()

        if integration_success:
            try:
                main_window = self._get_main_window()
                if main_window and hasattr(main_window, 'ik_manager') and main_window.ik_manager:
                    if hasattr(main_window.ik_manager, 'start_animation'):
                        main_window.ik_manager.start_animation()
            except Exception as e:
                logging.debug(f"AnimationLifecycleController: IK start failed: {e}")

        # Start mechanism animation - use scheduler if available, otherwise local timer
        logging.info(f"[ANIM-START] Starting animation: scheduler={self._scheduler is not None}")
        if self._scheduler:
            self._subscribe_to_scheduler()
            # Ensure scheduler is running
            if not self._scheduler.is_running:
                logging.info("[ANIM-START] Starting scheduler (was not running)")
                self._scheduler.start()
            else:
                logging.info(f"[ANIM-START] Scheduler already running, subscriptions={len(self._scheduler._subscriptions)}")
        else:
            logging.info("[ANIM-START] Using fallback QTimer (no scheduler)")
            self._animation_timer.start(33)  # ~30 FPS fallback

        presenter = self._get_presenter()
        if presenter:
            presenter.set_animation_running(True)

        # Update UI state
        self._update_animation_ui_state(can_play=False, can_stop=True, can_reset=True, is_running=True)

        self.animation_started.emit()

    def stop_animation(self) -> None:
        """Stop the animation timer and IK animation with proper cleanup."""
        # Stop animation - unsubscribe from scheduler or stop local timer
        if self._scheduler and self._use_scheduler:
            self._unsubscribe_from_scheduler()
        else:
            self._animation_timer.stop()

        presenter = self._get_presenter()
        if presenter:
            presenter.set_animation_running(False)

        # Stop IK animation
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, 'ik_manager') and main_window.ik_manager:
            try:
                if hasattr(main_window.ik_manager, 'stop_animation'):
                    main_window.ik_manager.stop_animation()

                # Clear all mechanism position targets
                main_window.ik_manager.clear_mechanism_position_targets()
            except Exception as e:
                logging.debug(f"AnimationLifecycleController: IK stop failed: {e}")

        # Update UI state
        self._update_animation_ui_state(can_play=True, can_stop=False, can_reset=True, is_running=False)

        self.animation_stopped.emit()

    def reset_animation(self) -> None:
        """Reset animation to start position with comprehensive IK reset."""
        # Stop animation - unsubscribe from scheduler or stop local timer
        if self._scheduler and self._use_scheduler:
            self._unsubscribe_from_scheduler()
        else:
            self._animation_timer.stop()
        self._animation_time = 0
        self._trace_frame_tick = 0  # Reset frame counter for path tracing

        presenter = self._get_presenter()
        if presenter:
            presenter.set_animation_running(False)

        # Note: Trace initialization with t=0 coupler positions is done later
        # in the mechanism_layers loop after calculating initial positions

        # Reset skeleton to initial state
        self._reset_skeleton_to_initial_state()

        # Reset IK system
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, 'ik_manager') and main_window.ik_manager:
            try:
                if hasattr(main_window.ik_manager, 'stop_animation'):
                    main_window.ik_manager.stop_animation()

                main_window.ik_manager.clear_mechanism_position_targets()

                if hasattr(main_window.ik_manager, 'reset_animation_state'):
                    main_window.ik_manager.reset_animation_state()
            except Exception as e:
                logging.debug(f"AnimationLifecycleController: IK reset failed: {e}")

        # Reset parts to initial positions
        self._position_parts_at_anchor_joints()

        # Reset mechanism visuals to initial state (time=0)
        mechanism_layers = self._get_mechanism_layers()
        for mechanism_id, layer_data in mechanism_layers.items():
            try:
                self._update_mechanism_visuals_for_animation(mechanism_id, 0, layer_data)
            except Exception:
                logging.debug("Suppressed exception", exc_info=True)

            # Calculate the t=0 coupler position for this mechanism
            initial_coupler_pos = None
            try:
                initial_coupler_pos = self._calculate_mechanism_output(
                    layer_data.get("type", ""),
                    layer_data.get("params", {}),
                    0.0,  # time=0
                    layer_data
                )
            except Exception:
                logging.debug("Suppressed exception calculating t=0 coupler position", exc_info=True)

            # Initialize trace with t=0 coupler position (instead of just clearing)
            self._path_trace_manager.init_trace(
                mechanism_id, self._mechanism_scene, initial_coupler_pos
            )

        # Update UI state
        self._update_animation_ui_state(can_play=True, can_stop=False, can_reset=True, is_running=False)

        self.animation_reset.emit()

    def _update_animation_ui_state(
        self,
        can_play: bool,
        can_stop: bool,
        can_reset: bool,
        is_running: bool,
    ) -> None:
        """Update UI state for animation controls."""
        ui_state_manager = self._get_ui_state_manager()
        if ui_state_manager:
            try:
                from automataii.presentation.qt.tabs.mechanism_design.mechanism_design_tab_ui_state import (
                    AnimationState,
                )
                animation_state = AnimationState(
                    can_play=can_play,
                    can_stop=can_stop,
                    can_reset=can_reset,
                    is_running=is_running
                )
                ui_state_manager.set_animation_state(animation_state)
            except ImportError:
                pass

    # --- Animation Frame Update ---

    def _update_animation_legacy(self) -> None:
        """
        Legacy animation update method for local QTimer.
        Delegates to _update_animation with a fixed delta time.
        """
        self._update_animation(0.033)  # ~30 FPS = 33ms per frame

    def _update_animation(self, delta_time: float) -> None:
        """
        Update animation frame by calculating mechanism outputs.

        The IK system is the single source of truth for skeleton and part animation.
        This method calculates mechanism outputs and sets them as IK targets.

        Args:
            delta_time: Time elapsed since last frame (seconds)

        Time Complexity: O(m) where m = number of active mechanisms
        """
        # Always log when called (for debugging)
        logging.debug(f"[ANIM-ENTRY] _update_animation called, tab_active={self._tab_active}, dt={delta_time:.4f}")

        # Prevent animation updates when tab is not active
        if not self._tab_active:
            logging.debug(f"[ANIM] Tab not active, stopping animation (tab_active={self._tab_active})")
            if self._scheduler and self._use_scheduler:
                self._unsubscribe_from_scheduler()
            elif self._animation_timer.isActive():
                self._animation_timer.stop()
            return

        # Advance time - use delta_time from scheduler when available
        dt = delta_time * self._animation_speed * 1.5  # Scale factor to match original ~30 FPS rate
        self._animation_time += dt
        if self._animation_time > 2 * math.pi:
            self._animation_time -= 2 * math.pi

        # Advance trace frame tick for stride gating
        self._trace_frame_tick = (self._trace_frame_tick + 1) % 1000000

        active_joint_updates: dict[str, QPointF] = {}

        # Get mechanism data
        mechanism_layers = self._get_mechanism_layers()
        part_enabled_state = self._get_part_enabled_state()
        parts_data = self._get_parts_data()

        if not mechanism_layers:
            logging.debug(f"[ANIM] No mechanism_layers available (got: {type(mechanism_layers).__name__}, len={len(mechanism_layers) if mechanism_layers else 0})")
            return

        logging.debug(f"[ANIM] Got {len(mechanism_layers)} mechanism(s): {list(mechanism_layers.keys())}")

        # Log first few frames for debugging
        if self._animation_time < 0.1:
            logging.debug(f"[ANIM] Processing {len(mechanism_layers)} mechanisms at time={self._animation_time:.3f}")

        # Round-robin subset selection for batch processing
        mech_items = list(mechanism_layers.items())
        total_mechs = len(mech_items)

        if total_mechs > 0:
            batch_count = max(1, int(math.ceil(total_mechs * self._mechanism_update_fraction)))
            start = self._mech_rr_cursor % total_mechs
            end = start + batch_count

            if end <= total_mechs:
                selected = mech_items[start:end]
            else:
                selected = mech_items[start:] + mech_items[: (end % total_mechs)]

            self._mech_rr_cursor = (self._mech_rr_cursor + batch_count) % total_mechs
        else:
            selected = []

        # Process selected mechanisms
        for mechanism_id, layer_data in selected:
            part_name_val = layer_data.get("part_name") if layer_data else None
            logging.debug(f"[ANIM-MECH] Processing {mechanism_id}: part_name='{part_name_val}' (type={type(part_name_val).__name__})")

            if not layer_data or not layer_data.get("part_name"):
                logging.debug(f"[ANIM-MECH] Skipping {mechanism_id}: layer_data={layer_data is not None}, part_name='{part_name_val}'")
                continue

            part_name = layer_data["part_name"]
            logging.debug(f"[ANIM-MECH] {mechanism_id}: part_name={part_name}, enabled={part_enabled_state.get(part_name, True)}")

            # Check if this part is enabled
            if not part_enabled_state.get(part_name, True):
                logging.debug(f"[ANIM-MECH] Skipping {mechanism_id}: part {part_name} disabled")
                continue

            try:
                output_pos = self._calculate_mechanism_output(
                    layer_data["type"],
                    layer_data["params"],
                    self._animation_time,
                    layer_data
                )

                # Debug: Log output_pos calculation
                if self._animation_time < 0.1:
                    logging.debug(f"[ANIM] Mechanism {mechanism_id}: type={layer_data.get('type')}, output_pos={output_pos}")

                # ALWAYS update mechanism visuals - this is independent of IK output
                logging.debug(f"[ANIM-CALLBACK] About to call _update_mechanism_visuals_for_animation, callback={self._update_mechanism_visuals_for_animation}")
                self._update_mechanism_visuals_for_animation(
                    mechanism_id, self._animation_time, layer_data
                )
                logging.debug("[ANIM-CALLBACK] Finished calling _update_mechanism_visuals_for_animation")

                if output_pos:
                    # Get the correct end effector joint for this part
                    part_info = parts_data.get(part_name)
                    logging.debug(f"[ANIM-IK] part_name={part_name}, part_info exists={part_info is not None}, "
                                  f"has anchor_joint_id={hasattr(part_info, 'anchor_joint_id') if part_info else False}, "
                                  f"anchor_joint_id={getattr(part_info, 'anchor_joint_id', None) if part_info else None}")
                    if part_info and hasattr(part_info, 'anchor_joint_id') and part_info.anchor_joint_id:
                        target_joint_id = self._get_target_joint_for_mechanism_control(
                            part_name, part_info.anchor_joint_id
                        )
                        logging.debug(f"[ANIM-IK] target_joint_id returned: '{target_joint_id}'")

                        std_joint_id = self._get_standardized_joint_id(target_joint_id)
                        logging.debug(f"[ANIM-IK] std_joint_id returned: '{std_joint_id}'")

                        if std_joint_id:
                            active_joint_updates[std_joint_id] = output_pos
                            logging.debug(f"[ANIM-IK] Added to active_joint_updates: {std_joint_id} -> {output_pos}")
                        else:
                            logging.debug("[ANIM-IK] std_joint_id is None/empty, NOT adding to active_joint_updates")

                    # Update path trace (only when we have a valid output position)
                    # Skip first 3 frames to let the mechanism settle and avoid "jump" artifacts
                    # Note: _trace_frame_tick is already incremented once per frame at line 472
                    if self._trace_frame_tick > 3:
                        self._path_trace_manager.update_trace(
                            mechanism_id, output_pos, self._trace_frame_tick, self._mechanism_scene
                        )

            except Exception as e:
                logging.debug(f"AnimationLifecycleController: Mechanism update error: {e}")

        # Throttled IK target updates
        logging.debug(f"[ANIM-IK] Calling _send_throttled_ik_updates with {len(active_joint_updates)} updates: {list(active_joint_updates.keys())}")
        self._send_throttled_ik_updates(active_joint_updates)

        self.frame_updated.emit(self._animation_time)

    def _send_throttled_ik_updates(self, active_joint_updates: dict[str, QPointF]) -> None:
        """
        Send IK updates with throttling and epsilon-based skipping.

        Args:
            active_joint_updates: Dict of joint_id -> target position
        """
        if not active_joint_updates:
            logging.debug("[ANIM-IK-SEND] No active_joint_updates, returning early")
            return

        main_window = self._get_main_window()
        if not main_window or not hasattr(main_window, 'ik_manager') or not main_window.ik_manager:
            logging.debug(f"[ANIM-IK-SEND] No ik_manager: main_window={main_window is not None}, has_attr={hasattr(main_window, 'ik_manager') if main_window else False}")
            return

        # Initialize throttle timer if needed
        if not self._ik_throttle_timer.isValid():
            self._ik_throttle_timer.start()

        # Check if enough time has passed
        elapsed = self._ik_throttle_timer.elapsed()
        if elapsed < self._ik_min_interval_ms:
            logging.debug(f"[ANIM-IK-SEND] Throttled: elapsed={elapsed}ms < min_interval={self._ik_min_interval_ms}ms")
            return

        ik_manager = main_window.ik_manager
        logging.debug(f"[ANIM-IK-SEND] Processing {len(active_joint_updates)} updates, ik_manager={ik_manager}")

        for joint_id, target_pos in active_joint_updates.items():
            last = self._last_target_pos_by_joint.get(joint_id)

            # Check if position changed significantly
            if last is None or (
                abs(target_pos.x() - last.x()) > self._pos_epsilon_px or
                abs(target_pos.y() - last.y()) > self._pos_epsilon_px
            ):
                logging.debug(f"[ANIM-IK-SEND] Calling set_mechanism_position_target({joint_id}, {target_pos})")
                ik_manager.set_mechanism_position_target(joint_id, target_pos)
                self._last_target_pos_by_joint[joint_id] = target_pos
            else:
                logging.debug(f"[ANIM-IK-SEND] Skipped {joint_id}: position change < epsilon")

        self._ik_throttle_timer.restart()

    # --- Animation Cache Management ---

    def clear_throttle_cache(self) -> None:
        """Clear the IK throttle cache."""
        self._last_target_pos_by_joint.clear()
        self._ik_throttle_timer.invalidate()
