# src/automataii/domain/kinematics/kinematics_system.py
import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, QPointF, pyqtSignal

from automataii.services.project_data_manager import ProjectDataManager

from .ik_animator import IKAnimator
from .ik_manager import IKManager

logger = logging.getLogger(__name__)


class KinematicsSystem(QObject):
    """
    A facade that orchestrates the entire kinematics pipeline, including
    IK solving, animation timing, and mechanism integration. It pulls target
    information from data sources and feeds them to the IKManager.

    Uses callback pattern to avoid circular dependencies with UI layer.
    """

    pose_updated = pyqtSignal(dict)
    # A consolidated signal for animation state
    animation_state_changed = pyqtSignal(bool, bool)  # is_playing, can_reset

    def __init__(self, project_data_manager: ProjectDataManager, parent=None):
        super().__init__(parent)
        self.project_data_manager = project_data_manager
        self._mechanism_target_provider: Callable[[float], dict[str, QPointF]] | None = None

        self.ik_manager = IKManager(self)
        self.ik_animator = IKAnimator(self)

        self._connect_signals()

    def set_mechanism_tab(self, mechanism_tab):
        """Sets the mechanism tab reference after initialization."""
        self.mechanism_tab = mechanism_tab

    def _connect_signals(self):
        """Connects the internal components of the kinematics system."""
        self.ik_animator.tick.connect(self._calculate_and_solve_ik)
        self.ik_manager.pose_updated.connect(self.pose_updated)

        self.ik_animator.animation_started.connect(
            lambda: self.animation_state_changed.emit(True, True)
        )
        self.ik_animator.animation_stopped.connect(
            lambda: self.animation_state_changed.emit(False, True)
        )
        self.ik_animator.animation_reset.connect(self.ik_manager.reset_pose)
        self.ik_animator.animation_reset.connect(
            lambda: self.animation_state_changed.emit(False, False)
        )

    def on_skeleton_data_updated(self, skeleton_data: dict | None):
        """Public slot to update the skeleton data for the entire system."""
        self.ik_manager.on_skeleton_data_updated(skeleton_data)

    def start_animation(self):
        """Public slot to start the animation."""
        logger.info("KINEMATICS_SYSTEM: Starting animation")
        self.ik_animator.start()

    def stop_animation(self):
        """Public slot to stop the animation."""
        self.ik_animator.stop()

    def reset_animation(self):
        """Public slot to reset the animation and pose."""
        self.ik_animator.reset()

    def set_animation_duration(self, duration_ms: int):
        """Public slot to set the animation duration."""
        self.ik_animator.set_duration(duration_ms)

    def _calculate_and_solve_ik(self, progress: float):
        """
        Calculates all IK targets for the current animation progress from all
        sources (motion paths, mechanisms) and tells the IKManager to solve.
        This logic was moved from MainWindow.
        """
        if not self.project_data_manager:
            logger.debug("CALCULATE_IK: No project data manager available")
            return

        targets = {}

        # 1. Get targets from motion paths stored in ProjectDataManager
        parts_data = self.project_data_manager.get_current_parts_data()
        logger.debug(f"CALCULATE_IK: Got parts data: {list(parts_data.keys()) if parts_data else None}")
        
        if parts_data:
            for part_name, part_info in parts_data.items():
                # Check for a valid, non-empty QPainterPath
                if (
                    hasattr(part_info, "motion_path_data")
                    and part_info.motion_path_data
                    and not part_info.motion_path_data.isEmpty()
                ):
                    logger.info(f"CALCULATE_IK: Found motion path for part: {part_name}")
                    # Map the part name to its corresponding end-effector ID
                    effector_id = self.ik_manager.get_end_effector_for_part(part_name)
                    logger.info(f"CALCULATE_IK: Effector ID for {part_name}: {effector_id}")
                    
                    if effector_id:
                        target_point = part_info.motion_path_data.pointAtPercent(progress)
                        targets[effector_id] = target_point
                        logger.info(f"CALCULATE_IK: Set target for {effector_id}: {target_point} (progress: {progress:.3f})")
                    else:
                        logger.warning(f"CALCULATE_IK: No effector ID found for part: {part_name}")
                else:
                    logger.debug(f"CALCULATE_IK: No motion path data for part: {part_name}")

        # 2. Get targets from the mechanism system, which may override path targets
        if self._mechanism_target_provider:
            try:
                mechanism_targets = self._mechanism_target_provider(progress)
                if mechanism_targets:
                    targets.update(mechanism_targets)
            except Exception as e:
                logger.error(f"Failed to get mechanism targets: {e}", exc_info=True)

        # 3. If there are any targets, solve the IK
        if targets:
            logger.info(f"CALCULATE_IK: Solving IK for targets: {list(targets.keys())}")
            self.ik_manager.solve_for_targets(targets)
        else:
            logger.debug("CALCULATE_IK: No targets to solve for")

    def set_mechanism_target_provider(
        self, provider: Callable[[float], dict[str, QPointF]]
    ) -> None:
        """
        Set a callback function to provide mechanism targets.

        Args:
            provider: A function that takes progress (float) and returns
                     a dictionary of effector_id -> target_position
        """
        self._mechanism_target_provider = provider
        logger.debug("Mechanism target provider registered")

    def clear_mechanism_target_provider(self) -> None:
        """Clear the mechanism target provider."""
        self._mechanism_target_provider = None
        logger.debug("Mechanism target provider cleared")
