"""
Signal Connector - Centralized signal connection management.

Extracted from AutomataDesigner (main_window.py) to handle all signal
connections between managers, tabs, and the main window.

Design Pattern: Coordinator (manages signal wiring)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from PyQt6.QtCore import QObject

if TYPE_CHECKING:
    from automataii.application.managers import ProjectDataManager, SkeletonManager
    from automataii.presentation.qt.kinematics.ik_manager import IKManager
    from automataii.presentation.qt.tabs.editor.tab import EditorTab
    from automataii.presentation.qt.tabs.image_processing_tab import ImageProcessingTab
    from automataii.presentation.qt.tabs.mechanism_design.tab import MechanismDesignTab
    from automataii.presentation.qt.tabs.options_tab import OptionsTab


class SignalHandler(Protocol):
    """Protocol for main window signal handlers."""

    def _handle_project_data_loaded(
        self, success: bool, path: str, parts: dict[str, Any]
    ) -> None: ...

    def _handle_project_data_cleared(self) -> None: ...
    def _handle_project_manager_error(self, error_message: str) -> None: ...
    def _on_skeleton_manager_updated(self, skeleton_data: dict | None) -> None: ...
    def _handle_ik_visuals_update(self, transforms: dict[str, Any]) -> None: ...
    def _handle_skeleton_pose_updated_from_ik(self, pose: dict) -> None: ...
    def _apply_theme(self, theme_name: str) -> None: ...
    def _handle_unit_changed(self, unit: str) -> None: ...
    def _reset_all_animations_button_clicked(self) -> None: ...
    def _handle_part_motion_path_update_from_editor_tab(
        self, part_name: str, path: Any
    ) -> None: ...
    def save_character_alignment_impl(self) -> None: ...
    def generate_blueprint_impl(self) -> None: ...


class SignalConnector(QObject):
    """
    Manages signal connections between components.

    Responsibilities:
    - Connect manager signals to main window handlers
    - Connect tab signals to appropriate handlers
    - Safely disconnect and reconnect signals
    - Prevent duplicate connections

    Time Complexity: O(n) where n = number of connections
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize signal connector."""
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self._connected_pairs: set[tuple[int, int]] = set()

    def connect_project_data_manager(
        self,
        manager: ProjectDataManager,
        handler: SignalHandler,
    ) -> None:
        """
        Connect ProjectDataManager signals to handlers.

        Args:
            manager: The ProjectDataManager instance
            handler: Object implementing SignalHandler protocol
        """
        self._safe_connect(
            manager.project_data_loaded,
            handler._handle_project_data_loaded,
            "ProjectDataManager.project_data_loaded",
        )
        self._safe_connect(
            manager.project_data_cleared,
            handler._handle_project_data_cleared,
            "ProjectDataManager.project_data_cleared",
        )
        self._safe_connect(
            manager.error_occurred,
            handler._handle_project_manager_error,
            "ProjectDataManager.error_occurred",
        )
        self._logger.debug("ProjectDataManager signals connected")

    def connect_skeleton_manager(
        self,
        skeleton_manager: SkeletonManager,
        handler: SignalHandler,
        ik_manager: IKManager | None = None,
    ) -> None:
        """
        Connect SkeletonManager signals to handlers.

        Args:
            skeleton_manager: The SkeletonManager instance
            handler: Object implementing SignalHandler protocol
            ik_manager: Optional IKManager to receive skeleton updates
        """
        self._safe_connect(
            skeleton_manager.skeleton_updated,
            handler._on_skeleton_manager_updated,
            "SkeletonManager.skeleton_updated -> handler",
        )

        if ik_manager and hasattr(ik_manager, "on_skeleton_data_updated_from_manager"):
            self._safe_connect(
                skeleton_manager.skeleton_updated,
                ik_manager.on_skeleton_data_updated_from_manager,
                "SkeletonManager.skeleton_updated -> IKManager",
            )
        self._logger.debug("SkeletonManager signals connected")

    def connect_ik_manager(
        self,
        ik_manager: IKManager,
        handler: SignalHandler,
        editor_tab: EditorTab | None = None,
    ) -> None:
        """
        Connect IKManager signals to handlers.

        Args:
            ik_manager: The IKManager instance
            handler: Object implementing SignalHandler protocol
            editor_tab: Optional EditorTab for animation state changes
        """
        self._safe_connect(
            ik_manager.character_visuals_updated,
            handler._handle_ik_visuals_update,
            "IKManager.character_visuals_updated",
        )

        if hasattr(ik_manager, "skeleton_pose_updated"):
            self._safe_connect(
                ik_manager.skeleton_pose_updated,
                handler._handle_skeleton_pose_updated_from_ik,
                "IKManager.skeleton_pose_updated",
            )

        if editor_tab and hasattr(ik_manager, "animation_state_changed"):
            self._safe_connect(
                ik_manager.animation_state_changed,
                editor_tab.on_simulation_state_changed,
                "IKManager.animation_state_changed -> EditorTab",
            )
        self._logger.debug("IKManager signals connected")

    def connect_editor_tab(
        self,
        editor_tab: EditorTab,
        ik_manager: IKManager | None = None,
        handler: SignalHandler | None = None,
    ) -> None:
        """
        Connect EditorTab signals to handlers.

        Args:
            editor_tab: The EditorTab instance
            ik_manager: Optional IKManager for simulation controls
            handler: Optional handler for alignment/blueprint requests
        """
        if ik_manager:
            if hasattr(ik_manager, "start_animation"):
                self._safe_connect(
                    editor_tab.request_play_simulation,
                    ik_manager.start_animation,
                    "EditorTab.request_play_simulation",
                )
            if hasattr(ik_manager, "stop_animation"):
                self._safe_connect(
                    editor_tab.request_stop_simulation,
                    ik_manager.stop_animation,
                    "EditorTab.request_stop_simulation",
                )
            if hasattr(ik_manager, "reset_animation_state"):
                self._safe_connect(
                    editor_tab.request_reset_simulation,
                    ik_manager.reset_animation_state,
                    "EditorTab.request_reset_simulation",
                )

        if handler:
            if hasattr(handler, "save_character_alignment_impl"):
                self._safe_connect(
                    editor_tab.request_save_alignment,
                    handler.save_character_alignment_impl,
                    "EditorTab.request_save_alignment",
                )
            if hasattr(handler, "generate_blueprint_impl"):
                self._safe_connect(
                    editor_tab.request_generate_blueprint,
                    handler.generate_blueprint_impl,
                    "EditorTab.request_generate_blueprint",
                )
            if hasattr(editor_tab, "request_reset_all_animations") and hasattr(
                handler, "_reset_all_animations_button_clicked"
            ):
                self._safe_connect(
                    editor_tab.request_reset_all_animations,
                    handler._reset_all_animations_button_clicked,
                    "EditorTab.request_reset_all_animations",
                )
            if hasattr(editor_tab, "motion_path_updated") and hasattr(
                handler, "_handle_part_motion_path_update_from_editor_tab"
            ):
                self._safe_connect(
                    editor_tab.motion_path_updated,
                    handler._handle_part_motion_path_update_from_editor_tab,
                    "EditorTab.motion_path_updated",
                )
        self._logger.debug("EditorTab signals connected")

    def connect_options_tab(
        self,
        options_tab: OptionsTab,
        ik_manager: IKManager | None = None,
        image_proc_tab: ImageProcessingTab | None = None,
        mechanism_design_tab: MechanismDesignTab | None = None,
        handler: SignalHandler | None = None,
    ) -> None:
        """
        Connect OptionsTab signals to handlers.

        Args:
            options_tab: The OptionsTab instance
            ik_manager: Optional IKManager for animation settings
            image_proc_tab: Optional ImageProcessingTab for processing visibility
            mechanism_design_tab: Optional MechanismDesignTab for physics snap mode
            handler: Optional handler for theme/unit changes
        """
        if handler:
            self._safe_connect(
                options_tab.themeChanged,
                handler._apply_theme,
                "OptionsTab.themeChanged",
            )

            if hasattr(options_tab, "unitChanged"):
                self._safe_connect(
                    options_tab.unitChanged,
                    handler._handle_unit_changed,
                    "OptionsTab.unitChanged",
                )

        if ik_manager:
            self._safe_connect(
                options_tab.animationDurationChanged,
                ik_manager.set_animation_duration,
                "OptionsTab.animationDurationChanged",
            )

            # Initialize UI with current value
            if hasattr(options_tab, "set_animation_duration_input"):
                options_tab.set_animation_duration_input(
                    ik_manager.animation_duration / 1000.0
                )

        if image_proc_tab and hasattr(options_tab, "advancedProcessingVisibilityChanged"):
            if hasattr(image_proc_tab, "_toggle_detailed_processing_visibility"):
                self._safe_connect(
                    options_tab.advancedProcessingVisibilityChanged,
                    image_proc_tab._toggle_detailed_processing_visibility,
                    "OptionsTab.advancedProcessingVisibilityChanged",
                )

        if mechanism_design_tab and hasattr(options_tab, "physicsSnapModeChanged"):
            try:
                parametric_manager = getattr(
                    mechanism_design_tab, "parametric_manager", None
                )
                if parametric_manager:
                    setter = getattr(parametric_manager, "set_physics_snap_mode", None)
                    if callable(setter):
                        self._safe_connect(
                            options_tab.physicsSnapModeChanged,
                            setter,
                            "OptionsTab.physicsSnapModeChanged",
                        )
                        # Initialize UI
                        if hasattr(options_tab, "set_physics_snap_mode_input"):
                            options_tab.set_physics_snap_mode_input(
                                parametric_manager.physics_snap_mode
                            )
            except Exception as e:
                self._logger.warning(f"Failed to connect physics snap mode: {e}")

        self._logger.debug("OptionsTab signals connected")

    def _safe_connect(
        self,
        signal: Any,
        slot: Any,
        connection_name: str,
    ) -> bool:
        """
        Safely connect a signal to a slot, preventing duplicates.

        Args:
            signal: The PyQt signal
            slot: The slot function
            connection_name: Name for logging

        Returns:
            True if connected successfully
        """
        # Create unique identifier for this connection
        connection_id = (id(signal), id(slot))

        if connection_id in self._connected_pairs:
            self._logger.debug(f"Skipping duplicate connection: {connection_name}")
            return False

        try:
            # Try to disconnect first to prevent duplicates
            try:
                signal.disconnect(slot)
            except TypeError:
                pass  # Not connected, which is fine

            signal.connect(slot)
            self._connected_pairs.add(connection_id)
            self._logger.debug(f"Connected: {connection_name}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to connect {connection_name}: {e}")
            return False

    def disconnect_all(self) -> None:
        """Clear all tracked connections."""
        self._connected_pairs.clear()
        self._logger.info("Signal connector reset")
