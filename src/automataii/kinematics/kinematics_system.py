# src/automataii/kinematics/kinematics_system.py
import logging
from typing import Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from .ik_manager import IKManager
from .ik_animator import IKAnimator
from ..core.project_data_manager import ProjectDataManager
# Avoid direct import of the tab to reduce coupling, will be passed in __init__
# from ..gui.tabs.mechanism_design.tab import MechanismDesignTab 

logger = logging.getLogger(__name__)

class KinematicsSystem(QObject):
    """
    A facade that orchestrates the entire kinematics pipeline, including
    IK solving, animation timing, and mechanism integration. It pulls target
    information from data sources and feeds them to the IKManager.
    """
    pose_updated = pyqtSignal(dict)
    # A consolidated signal for animation state
    animation_state_changed = pyqtSignal(bool, bool) # is_playing, can_reset

    def __init__(self, project_data_manager: ProjectDataManager, parent=None):
        super().__init__(parent)
        self.project_data_manager = project_data_manager
        self.mechanism_tab = None

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
        
        self.ik_animator.animation_started.connect(lambda: self.animation_state_changed.emit(True, True))
        self.ik_animator.animation_stopped.connect(lambda: self.animation_state_changed.emit(False, True))
        self.ik_animator.animation_reset.connect(self.ik_manager.reset_pose)
        self.ik_animator.animation_reset.connect(lambda: self.animation_state_changed.emit(False, False))

    def on_skeleton_data_updated(self, skeleton_data: Optional[Dict]):
        """Public slot to update the skeleton data for the entire system."""
        self.ik_manager.on_skeleton_data_updated(skeleton_data)

    def start_animation(self):
        """Public slot to start the animation."""
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
            return

        targets = {}
        
        # 1. Get targets from motion paths stored in ProjectDataManager
        parts_data = self.project_data_manager.get_current_parts_data()
        if parts_data:
            for part_name, part_info in parts_data.items():
                # Check for a valid, non-empty QPainterPath
                if hasattr(part_info, 'motion_path_data') and part_info.motion_path_data and not part_info.motion_path_data.isEmpty():
                    # Map the part name to its corresponding end-effector ID
                    effector_id = self.ik_manager.get_end_effector_for_part(part_name)
                    if effector_id:
                        target_point = part_info.motion_path_data.pointAtPercent(progress)
                        targets[effector_id] = target_point

        # 2. Get targets from the mechanism system, which may override path targets
        if self.mechanism_tab and hasattr(self.mechanism_tab, "get_mechanism_targets"):
            try:
                # The mechanism tab needs the ik_manager to map parts to effectors
                # We can pass it temporarily or refactor mechanism_tab later
                # For now, let's assume it can get the manager reference from main_window
                mechanism_targets = self.mechanism_tab.get_mechanism_targets(progress)
                targets.update(mechanism_targets)
            except Exception as e:
                logger.error(f"Failed to get mechanism targets: {e}", exc_info=True)


        # 3. If there are any targets, solve the IK
        if targets:
            self.ik_manager.solve_for_targets(targets)