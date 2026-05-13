"""
Animation Frame Coordinator for mechanism animation updates.

Extracted from MechanismDesignTab as part of god class decomposition.
Coordinates animation frame updates, mechanism output calculations, and IK targets.

Design Pattern: Coordinator (orchestrates animation frame operations)
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

from PyQt6.QtCore import QElapsedTimer, QPointF
from PyQt6.QtWidgets import QGraphicsScene

if TYPE_CHECKING:
    from automataii.presentation.qt.tabs.mechanism_design.path_trace_manager import PathTraceManager


JointCacheSignature = tuple[tuple[tuple[str, str], ...], tuple[str, ...]]


def _finite_qpoint(point: QPointF) -> bool:
    return math.isfinite(point.x()) and math.isfinite(point.y())


class IKManagerProtocol(Protocol):
    """Protocol for IK manager interface."""

    def set_mechanism_position_target(self, joint_id: str, target_pos: QPointF) -> None:
        """Set position target for a joint."""
        ...


class AnimationFrameCoordinator:
    """
    Coordinates animation frame updates for mechanism visualization.

    Responsibilities:
    - Update animation time and frame tick
    - Calculate mechanism outputs in batches (round-robin)
    - Determine IK targets from mechanism outputs
    - Throttle IK updates for performance
    - Update mechanism visuals and path traces

    Time Complexity: O(batch_size) per frame where batch_size is configurable
    """

    def __init__(
        self,
        *,
        ik_update_rate_hz: int = 30,
        mechanism_update_fraction: float = 0.5,
        pos_epsilon_px: float = 0.5,
    ) -> None:
        """
        Initialize coordinator with performance settings.

        Args:
            ik_update_rate_hz: Target IK updates per second
            mechanism_update_fraction: Fraction of mechanisms to update per frame
            pos_epsilon_px: Minimum movement to trigger IK update
        """
        self._ik_update_rate_hz = ik_update_rate_hz
        self._ik_min_interval_ms = int(1000 / max(1, ik_update_rate_hz))
        self._mechanism_update_fraction = mechanism_update_fraction
        self._pos_epsilon_px = pos_epsilon_px

        # Animation state
        self._animation_time: float = 0.0
        self._animation_speed: float = 1.0
        self._trace_frame_tick: int = 0
        self._mech_rr_cursor: int = 0
        self._mechanism_id_cache: tuple[str, ...] = ()
        self._mechanism_cache_ref_id: int | None = None
        self._mechanism_cache_len: int = -1

        # IK throttling state
        self._ik_throttle_timer: QElapsedTimer = QElapsedTimer()
        self._ik_throttle_timer.invalidate()
        self._last_target_pos_by_joint: dict[str, QPointF] = {}
        self._joint_id_cache: dict[str, str | None] = {}
        self._joint_id_cache_signature: JointCacheSignature | None = None

        # Callbacks (injected)
        self._calculate_output_fn: Callable[[str, dict, float, dict], QPointF | None] | None = None
        self._get_target_joint_fn: Callable[[str, str], str] | None = None
        self._get_standardized_joint_fn: Callable[[str], str | None] | None = None
        self._update_visuals_fn: Callable[[str, float, dict], None] | None = None
        self._stop_timer_fn: Callable[[], None] | None = None

    def configure_callbacks(
        self,
        *,
        calculate_output: Callable[[str, dict, float, dict], QPointF | None],
        get_target_joint: Callable[[str, str], str],
        get_standardized_joint: Callable[[str], str | None],
        update_visuals: Callable[[str, float, dict], None],
        stop_timer: Callable[[], None],
    ) -> None:
        """
        Configure callbacks for Tab method delegation.

        Args:
            calculate_output: Function to calculate mechanism output position
            get_target_joint: Function to get target joint for mechanism control
            get_standardized_joint: Function to get standardized joint ID
            update_visuals: Function to update mechanism visuals
            stop_timer: Function to stop animation timer
        """
        self._calculate_output_fn = calculate_output
        self._get_target_joint_fn = get_target_joint
        self._get_standardized_joint_fn = get_standardized_joint
        self._update_visuals_fn = update_visuals
        self._stop_timer_fn = stop_timer

    @property
    def animation_time(self) -> float:
        """Current animation time in radians."""
        return self._animation_time

    @animation_time.setter
    def animation_time(self, value: float) -> None:
        """Set animation time."""
        self._animation_time = value

    @property
    def animation_speed(self) -> float:
        """Animation speed multiplier."""
        return self._animation_speed

    @animation_speed.setter
    def animation_speed(self, value: float) -> None:
        """Set animation speed."""
        self._animation_speed = value

    @property
    def trace_frame_tick(self) -> int:
        """Current frame tick for trace stride gating."""
        return self._trace_frame_tick

    def reset_state(self) -> None:
        """Reset animation state to initial values."""
        self._animation_time = 0.0
        self._trace_frame_tick = 0
        self._mech_rr_cursor = 0
        self._last_target_pos_by_joint.clear()
        self._joint_id_cache.clear()
        self._joint_id_cache_signature = None
        self._invalidate_mechanism_cache()
        self._ik_throttle_timer.invalidate()

    def update_frame(
        self,
        *,
        tab_active: bool,
        mechanism_layers: dict[str, Any],
        part_enabled_state: dict[str, bool],
        parts_data: dict[str, Any],
        ik_manager: IKManagerProtocol | None,
        path_trace_manager: PathTraceManager,
        scene: QGraphicsScene,
        initial_skeleton_cache: dict | None = None,
    ) -> None:
        """
        Update animation frame.

        Calculates mechanism outputs and sets IK targets.
        This is the main entry point called by the animation timer.

        Args:
            tab_active: Whether tab is currently active
            mechanism_layers: Dict of mechanism layer data
            part_enabled_state: Dict of part enabled states
            parts_data: Dict of part info data
            ik_manager: IK manager instance (or None)
            path_trace_manager: Path trace manager for visual trails
            scene: Graphics scene for updates
            initial_skeleton_cache: Cached skeleton data for joint mapping
        """
        # CRITICAL: Prevent animation updates when tab is not active
        if not tab_active:
            if self._stop_timer_fn:
                self._stop_timer_fn()
            return

        # Advance animation time
        dt = 0.05 * self._animation_speed
        self._animation_time += dt
        if self._animation_time > 2 * math.pi:
            self._animation_time -= 2 * math.pi

        # Advance trace frame tick for stride gating
        self._trace_frame_tick = (self._trace_frame_tick + 1) % 1000000

        # Calculate mechanism outputs and collect IK targets
        active_joint_updates = self._process_mechanism_batch(
            mechanism_layers=mechanism_layers,
            part_enabled_state=part_enabled_state,
            parts_data=parts_data,
            path_trace_manager=path_trace_manager,
            scene=scene,
            initial_skeleton_cache=initial_skeleton_cache,
        )

        # Throttled IK target updates
        self._apply_ik_targets(
            active_joint_updates=active_joint_updates,
            ik_manager=ik_manager,
        )

    def _process_mechanism_batch(
        self,
        *,
        mechanism_layers: dict[str, Any],
        part_enabled_state: dict[str, bool],
        parts_data: dict[str, Any],
        path_trace_manager: PathTraceManager,
        scene: QGraphicsScene,
        initial_skeleton_cache: dict | None,
    ) -> dict[str, QPointF]:
        """
        Process a batch of mechanisms for animation (round-robin).

        Args:
            mechanism_layers: Dict of mechanism layer data
            part_enabled_state: Dict of part enabled states
            parts_data: Dict of part info data
            path_trace_manager: Path trace manager
            scene: Graphics scene
            initial_skeleton_cache: Skeleton data cache

        Returns:
            Dict mapping joint IDs to target positions
        """
        active_joint_updates: dict[str, QPointF] = {}

        mech_ids = self._get_mechanism_id_cache(mechanism_layers)
        total_mechs = len(mech_ids)

        if total_mechs == 0:
            return active_joint_updates

        # Calculate batch size for round-robin processing
        batch_count = max(
            1,
            int(math.ceil(total_mechs * max(0.05, min(1.0, self._mechanism_update_fraction))))
        )

        start = self._mech_rr_cursor % total_mechs

        # Process selected mechanisms
        for offset in range(batch_count):
            mechanism_id = mech_ids[(start + offset) % total_mechs]
            layer_data = mechanism_layers.get(mechanism_id)
            if layer_data is None:
                self._invalidate_mechanism_cache()
                continue
            joint_update = self._process_single_mechanism(
                mechanism_id=mechanism_id,
                layer_data=layer_data,
                part_enabled_state=part_enabled_state,
                parts_data=parts_data,
                path_trace_manager=path_trace_manager,
                scene=scene,
                initial_skeleton_cache=initial_skeleton_cache,
            )
            if joint_update:
                joint_id, target_pos = joint_update
                active_joint_updates[joint_id] = target_pos

        self._mech_rr_cursor = (start + batch_count) % total_mechs

        return active_joint_updates

    def _invalidate_mechanism_cache(self) -> None:
        self._mechanism_id_cache = ()
        self._mechanism_cache_ref_id = None
        self._mechanism_cache_len = -1

    def _get_mechanism_id_cache(self, mechanism_layers: dict[str, Any]) -> tuple[str, ...]:
        current_ids = tuple(mechanism_layers.keys())
        cache_ref_id = id(mechanism_layers)
        cache_len = len(mechanism_layers)
        if (
            cache_ref_id != self._mechanism_cache_ref_id
            or cache_len != self._mechanism_cache_len
            or current_ids != self._mechanism_id_cache
        ):
            self._mechanism_id_cache = current_ids
            self._mechanism_cache_ref_id = cache_ref_id
            self._mechanism_cache_len = cache_len
            if self._mechanism_id_cache:
                self._mech_rr_cursor %= len(self._mechanism_id_cache)
            else:
                self._mech_rr_cursor = 0
        return self._mechanism_id_cache

    def _process_single_mechanism(
        self,
        *,
        mechanism_id: str,
        layer_data: dict,
        part_enabled_state: dict[str, bool],
        parts_data: dict[str, Any],
        path_trace_manager: PathTraceManager,
        scene: QGraphicsScene,
        initial_skeleton_cache: dict | None,
    ) -> tuple[str, QPointF] | None:
        """
        Process a single mechanism for animation.

        Args:
            mechanism_id: Mechanism identifier
            layer_data: Mechanism layer data
            part_enabled_state: Part enabled states
            parts_data: Part info data
            path_trace_manager: Path trace manager
            scene: Graphics scene
            initial_skeleton_cache: Skeleton data cache

        Returns:
            Tuple of (joint_id, target_pos) or None
        """
        if not layer_data or not layer_data.get("part_name"):
            return None

        part_name = layer_data["part_name"]

        # Check if part is enabled
        if not part_enabled_state.get(part_name, True):
            return None

        if not self._calculate_output_fn:
            return None

        try:
            output_pos = self._calculate_output_fn(
                layer_data["type"],
                layer_data["params"],
                self._animation_time,
                layer_data,
            )

            if output_pos is None or not _finite_qpoint(output_pos):
                return None

            # Update mechanism visuals and path trace
            if self._update_visuals_fn:
                self._update_visuals_fn(mechanism_id, self._animation_time, layer_data)

            path_trace_manager.update_trace(
                mechanism_id,
                output_pos,
                self._trace_frame_tick,
                scene,
            )

            # Get target joint for IK
            part_info = parts_data.get(part_name)
            if not part_info or not getattr(part_info, 'anchor_joint_id', None):
                return None

            if not self._get_target_joint_fn or not self._get_standardized_joint_fn:
                return None

            target_joint_id = self._get_target_joint_fn(part_name, part_info.anchor_joint_id)
            std_joint_id = self._get_standardized_joint_id(
                target_joint_id,
                initial_skeleton_cache,
            )

            if std_joint_id:
                return (std_joint_id, output_pos)

            return None

        except Exception:
            return None

    def _get_standardized_joint_id(
        self,
        abstract_joint_id: str,
        skeleton_cache: dict | None,
    ) -> str | None:
        """
        Get standardized joint ID from abstract name.

        Args:
            abstract_joint_id: Abstract joint identifier
            skeleton_cache: Cached skeleton data with joint map

        Returns:
            Standardized joint ID or None
        """
        signature = self._get_joint_cache_signature(skeleton_cache)
        if signature != self._joint_id_cache_signature:
            self._joint_id_cache.clear()
            self._joint_id_cache_signature = signature

        if abstract_joint_id in self._joint_id_cache:
            return self._joint_id_cache[abstract_joint_id]

        resolved: str | None = None

        # Try callback first
        if self._get_standardized_joint_fn:
            resolved = self._get_standardized_joint_fn(abstract_joint_id)
            self._joint_id_cache[abstract_joint_id] = resolved
            return resolved

        # Fallback to direct lookup
        if skeleton_cache:
            joint_map = skeleton_cache.get("joint_map", {})
            for orig_name, std_name in joint_map.items():
                if orig_name == abstract_joint_id:
                    resolved = std_name
                    self._joint_id_cache[abstract_joint_id] = resolved
                    return resolved

            # Check if already a standard ID
            if abstract_joint_id in skeleton_cache.get("joints", {}):
                resolved = abstract_joint_id
                self._joint_id_cache[abstract_joint_id] = resolved
                return resolved

        self._joint_id_cache[abstract_joint_id] = None
        return None

    def _get_joint_cache_signature(
        self,
        skeleton_cache: dict | None,
    ) -> JointCacheSignature | None:
        if not skeleton_cache:
            return None
        joints = skeleton_cache.get("joints", {})
        joint_map = skeleton_cache.get("joint_map", {})
        joint_keys = tuple(sorted(str(key) for key in joints)) if isinstance(joints, dict) else ()
        joint_map_items = (
            tuple(sorted((str(key), str(value)) for key, value in joint_map.items()))
            if isinstance(joint_map, dict)
            else ()
        )
        return (joint_map_items, joint_keys)

    def _apply_ik_targets(
        self,
        *,
        active_joint_updates: dict[str, QPointF],
        ik_manager: IKManagerProtocol | None,
    ) -> None:
        """
        Apply IK targets with throttling and epsilon-based skipping.

        Args:
            active_joint_updates: Dict of joint targets
            ik_manager: IK manager instance
        """
        if not active_joint_updates or not ik_manager:
            return

        # Initialize timer if needed
        if not self._ik_throttle_timer.isValid():
            self._ik_throttle_timer.start()

        # Check if enough time has elapsed
        if self._ik_throttle_timer.elapsed() < self._ik_min_interval_ms:
            return

        eps = self._pos_epsilon_px

        for joint_id, target_pos in active_joint_updates.items():
            last = self._last_target_pos_by_joint.get(joint_id)

            # Skip if position hasn't changed significantly
            if last is not None:
                if abs(target_pos.x() - last.x()) <= eps and abs(target_pos.y() - last.y()) <= eps:
                    continue

            ik_manager.set_mechanism_position_target(joint_id, target_pos)
            self._last_target_pos_by_joint[joint_id] = target_pos

        self._ik_throttle_timer.restart()

    def apply_performance_preset(self, preset: str) -> dict[str, Any]:
        """
        Apply performance preset and return view rendering hints.

        Presets:
        - fast: Fewer updates, simpler trace, lower IK rate
        - balanced: Default settings
        - high: More updates, longer trace, higher IK rate

        Args:
            preset: Preset name ('fast', 'balanced', 'high')

        Returns:
            Dict with view hints (antialiasing, trace settings)
        """
        p = (preset or "").strip().lower()
        view_hints: dict[str, Any] = {}

        if p == "fast":
            self._ik_update_rate_hz = 15
            self._ik_min_interval_ms = int(1000 / self._ik_update_rate_hz)
            self._pos_epsilon_px = 1.0
            self._mechanism_update_fraction = 0.33
            view_hints["antialiasing"] = False
            view_hints["trace_stride"] = 4
            view_hints["trace_max_points"] = 250

        elif p == "high":
            self._ik_update_rate_hz = 60
            self._ik_min_interval_ms = int(1000 / self._ik_update_rate_hz)
            self._pos_epsilon_px = 0.2
            self._mechanism_update_fraction = 1.0
            view_hints["antialiasing"] = True
            view_hints["trace_stride"] = 1
            view_hints["trace_max_points"] = 1000

        else:  # balanced/default
            self._ik_update_rate_hz = 30
            self._ik_min_interval_ms = int(1000 / self._ik_update_rate_hz)
            self._pos_epsilon_px = 0.5
            self._mechanism_update_fraction = 0.5
            view_hints["antialiasing"] = True
            view_hints["trace_stride"] = 2
            view_hints["trace_max_points"] = 500

        return view_hints

    @property
    def ik_update_rate_hz(self) -> int:
        """Current IK update rate in Hz."""
        return self._ik_update_rate_hz

    @property
    def mechanism_update_fraction(self) -> float:
        """Fraction of mechanisms updated per frame."""
        return self._mechanism_update_fraction

    @property
    def pos_epsilon_px(self) -> float:
        """Minimum position change in pixels to trigger update."""
        return self._pos_epsilon_px

    def clear_animation_cache(self, target_object: Any) -> None:
        """
        Clear cached animation state variables from target object.

        Clears mechanism-specific animation caches while preserving skeleton data.

        Args:
            target_object: Object to clear cached attributes from
        """
        # Specific animation cache attributes to clear
        explicit_attrs = [
            '_initial_cam_center_scene',
        ]

        for attr in explicit_attrs:
            if hasattr(target_object, attr):
                try:
                    delattr(target_object, attr)
                except AttributeError:
                    pass

        # Clear prefixed caches (but preserve important _*_cache attributes)
        prefixes = ('_animation_', '_cam_', '_gear_', '_fourbar_')
        try:
            all_attrs = [attr for attr in dir(target_object)
                        if attr.startswith(prefixes)]

            for attr in all_attrs:
                if not attr.endswith('_cache') and hasattr(target_object, attr):
                    try:
                        delattr(target_object, attr)
                    except AttributeError:
                        pass
        except Exception:
            logging.debug("Suppressed exception", exc_info=True)
