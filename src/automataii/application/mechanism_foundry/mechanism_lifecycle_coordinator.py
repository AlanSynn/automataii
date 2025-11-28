"""
Mechanism Lifecycle Coordinator - Application Layer

Orchestrates the lifecycle of mechanism instances including creation,
IK integration, and cleanup. This is application-level coordination
that doesn't belong in the presentation layer.

Design Pattern: Application Service / Coordinator (DDD)
Architecture: Hexagonal - Application Layer
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QPainterPath


class IKManagerProtocol(Protocol):
    """Protocol for IK Manager dependency."""

    def stop_animation(self) -> None: ...
    def clear_mechanism_position_targets(self) -> None: ...
    def reset_animation_state(self) -> None: ...
    def set_project_parts_data(self, parts_data: dict) -> None: ...
    def on_skeleton_data_updated_from_manager(self, data: dict) -> None: ...
    def set_joint_motion_path(self, joint_id: str, path: Any) -> None: ...
    def register_mechanism_position_target(
        self, joint_id: str, target_joint: str, callback: Callable
    ) -> None: ...


@dataclass
class MechanismLifecycleContext:
    """Context data for mechanism lifecycle operations."""

    mechanism_layers: dict[str, Any] = field(default_factory=dict)
    mechanism_enabled_state: dict[str, bool] = field(default_factory=dict)
    parts_data: dict[str, Any] = field(default_factory=dict)
    skeleton_cache: dict[str, Any] | None = None


class MechanismLifecycleCoordinator:
    """
    Coordinates mechanism lifecycle operations.

    This is an APPLICATION layer service that orchestrates:
    - Mechanism-IK integration setup
    - Mechanism controller registration
    - Skeleton state management
    - Mechanism cleanup

    Does NOT contain:
    - Qt/UI code (presentation layer)
    - Direct mechanism computation (domain layer)
    """

    def __init__(self) -> None:
        """Initialize coordinator."""
        # Callbacks for domain operations (injected)
        self._calculate_output_fn: Callable[..., Any] | None = None
        self._generate_motion_path_fn: Callable[..., Any] | None = None
        self._get_target_joint_fn: Callable[[str, str], str] | None = None

    def configure_callbacks(
        self,
        *,
        calculate_output: Callable[..., Any],
        generate_motion_path: Callable[..., Any],
        get_target_joint: Callable[[str, str], str],
    ) -> None:
        """
        Configure callbacks for domain operations.

        Args:
            calculate_output: Function to calculate mechanism output
            generate_motion_path: Function to generate joint motion path
            get_target_joint: Function to get target joint for part
        """
        self._calculate_output_fn = calculate_output
        self._generate_motion_path_fn = generate_motion_path
        self._get_target_joint_fn = get_target_joint

    def setup_ik_integration(
        self,
        *,
        ik_manager: Any | None,
        context: MechanismLifecycleContext,
        register_controller_fn: Callable[[str, dict, str], None],
    ) -> bool:
        """
        Setup integration between mechanism animation and IK system.

        Args:
            ik_manager: IK manager instance
            context: Lifecycle context with mechanism data
            register_controller_fn: Function to register mechanism controllers

        Returns:
            True if setup succeeded, False otherwise
        """
        if not ik_manager:
            return False

        try:
            # Set up parts data in IK manager
            if context.parts_data:
                if hasattr(ik_manager, 'set_project_parts_data'):
                    ik_manager.set_project_parts_data(context.parts_data)

            # Set skeleton data if available
            if context.skeleton_cache:
                if hasattr(ik_manager, 'on_skeleton_data_updated_from_manager'):
                    ik_manager.on_skeleton_data_updated_from_manager(context.skeleton_cache)

            # Register mechanism controllers for each active mechanism
            for mech_id, layer_data in context.mechanism_layers.items():
                if context.mechanism_enabled_state.get(mech_id, False):
                    part_name = layer_data.get("part_name")
                    if part_name and part_name in context.parts_data:
                        part_info = context.parts_data[part_name]
                        anchor_joint = getattr(part_info, 'anchor_joint_id', None)
                        if anchor_joint:
                            register_controller_fn(mech_id, layer_data, anchor_joint)

            return True

        except Exception:
            return False

    def register_mechanism_controller(
        self,
        *,
        mech_id: str,
        layer_data: dict[str, Any],
        joint_id: str,
        ik_manager: Any | None,
    ) -> bool:
        """
        Register a mechanism as a controller for a specific joint.

        Args:
            mech_id: Mechanism ID
            layer_data: Mechanism layer data
            joint_id: Joint ID to control
            ik_manager: IK manager instance

        Returns:
            True if registration succeeded
        """
        if not ik_manager or not self._calculate_output_fn or not self._get_target_joint_fn:
            return False

        try:
            # Create callback for mechanism output calculation
            def mechanism_joint_callback(time: float) -> Any:
                return self._calculate_output_fn(
                    layer_data.get("type"),
                    layer_data.get("params", {}),
                    time,
                    layer_data
                )

            # Generate complete motion path for IK system
            if self._generate_motion_path_fn:
                joint_motion_path = self._generate_motion_path_fn(layer_data, joint_id)
                if joint_motion_path and hasattr(ik_manager, 'set_joint_motion_path'):
                    ik_manager.set_joint_motion_path(joint_id, joint_motion_path)

            # Get target joint for this part
            part_name = layer_data.get("part_name", "")
            target_joint = self._get_target_joint_fn(part_name, joint_id)

            # Register position target
            if hasattr(ik_manager, 'register_mechanism_position_target'):
                ik_manager.register_mechanism_position_target(
                    joint_id, target_joint, mechanism_joint_callback
                )

            return True

        except Exception:
            return False

    def reset_skeleton_state(
        self,
        *,
        ik_manager: Any | None,
        skeleton_cache: dict[str, Any] | None,
        animation_timer: Any | None,
        on_skeleton_reset: Callable[[dict], None] | None = None,
    ) -> None:
        """
        Reset skeleton to initial state.

        Args:
            ik_manager: IK manager instance
            skeleton_cache: Cached initial skeleton data
            animation_timer: Animation timer to stop
            on_skeleton_reset: Callback when skeleton is reset
        """
        # Stop animation timer
        if animation_timer and hasattr(animation_timer, 'isActive'):
            if animation_timer.isActive():
                animation_timer.stop()

        # Reset IK system
        if ik_manager:
            try:
                if hasattr(ik_manager, 'stop_animation'):
                    ik_manager.stop_animation()
                if hasattr(ik_manager, 'clear_mechanism_position_targets'):
                    ik_manager.clear_mechanism_position_targets()
                if hasattr(ik_manager, 'reset_animation_state'):
                    ik_manager.reset_animation_state()
            except Exception:
                pass

        # Notify about skeleton reset
        if skeleton_cache and on_skeleton_reset:
            on_skeleton_reset(skeleton_cache.copy())

    def clear_mechanism_for_part(
        self,
        part_name: str,
        *,
        mechanism_layers: dict[str, Any],
        mechanism_enabled_state: dict[str, bool],
        on_visual_cleanup: Callable[[str, dict], None] | None = None,
    ) -> list[str]:
        """
        Clear all mechanisms associated with a specific part.

        Args:
            part_name: Name of the part to clear mechanisms for
            mechanism_layers: Dict of mechanism layers
            mechanism_enabled_state: Dict of mechanism enabled states
            on_visual_cleanup: Callback to clean up visuals for each mechanism

        Returns:
            List of cleared mechanism IDs
        """
        cleared_ids: list[str] = []

        # Find and remove mechanisms for this part
        mechanisms_to_remove = [
            mech_id for mech_id, layer_data in mechanism_layers.items()
            if layer_data.get("part_name") == part_name
        ]

        for mech_id in mechanisms_to_remove:
            layer_data = mechanism_layers.get(mech_id)

            # Notify about visual cleanup
            if on_visual_cleanup and layer_data:
                on_visual_cleanup(mech_id, layer_data)

            # Remove from data structures
            mechanism_layers.pop(mech_id, None)
            mechanism_enabled_state.pop(mech_id, None)
            cleared_ids.append(mech_id)

        return cleared_ids
