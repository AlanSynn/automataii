"""Main coordinator for the IK system."""

import logging
from typing import Dict, Any, Optional, List

from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from .core import (
    IKState,
    JointConfigurationManager,
    LimbConfigurationManager,
    SolverType
)
from .solvers import SolverFactory, IKSolution
from .animation import AnimationManager


class IKCoordinator(QObject):
    """Coordinates all IK system components.

    This class acts as the main entry point for IK operations,
    managing state, configuration, solving, and animation.
    """

    # Signals
    solver_initialized = pyqtSignal(bool, dict)  # success, joint_config
    ik_solved = pyqtSignal(dict)  # solution data
    animation_updated = pyqtSignal(float)  # progress
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Core components
        self._state = IKState(self)
        self._joint_config = JointConfigurationManager()
        self._limb_config = LimbConfigurationManager()
        self._animation = AnimationManager(self._state, self)
        self._skeleton_hierarchy: Dict[str, List[str]] = {}

        # Solvers
        self._solvers: Dict[SolverType, Any] = {}

        # Connect signals
        self._setup_connections()

        logging.info("IKCoordinator initialized")

    def _setup_connections(self):
        """Set up internal signal connections."""
        # Animation signals
        self._animation.frame_updated.connect(self.animation_updated)
        self._animation.target_positions_updated.connect(self._solve_frame)

        # State signals
        self._state.state_changed.connect(self._on_state_changed)

    def initialize_from_skeleton(self, skeleton_data: Dict[str, Any]) -> bool:
        """Initialize IK system from skeleton data.

        Args:
            skeleton_data: Skeleton joint and hierarchy data

        Returns:
            True if successful
        """
        try:
            # Clear existing configuration
            self.clear()

            # Extract joints from the standardized data model
            joints = skeleton_data.get('joints', {})

            if not joints:
                logging.warning("IKCoordinator: No joints found in skeleton_data.")
                return False

            # Add joints to the state. The joint_id from the standardized data
            # is now the canonical name for the IK system.
            for joint_id, joint_info in joints.items():
                pos_tuple = joint_info.get('position', (0.0, 0.0))
                # Ensure position is a QPointF for IK calculations
                position = QPointF(pos_tuple[0], pos_tuple[1])
                angle = joint_info.get('angle', 0.0)

                # Use the joint_id directly as it's the standardized name
                self._state.add_joint(joint_id, position, angle)

            # Store hierarchy for later use
            self._skeleton_hierarchy = skeleton_data.get('hierarchy', {})

            # Set up standard humanoid limbs if applicable
            if self._detect_humanoid_skeleton(joints):
                self._limb_config.create_standard_humanoid_limbs(joint_prefix="")

                # Add limbs to state
                for limb_name, limb_config in self._limb_config.get_all_limbs().items():
                    self._state.add_limb(
                        limb_name,
                        limb_config.joints,
                        limb_config.bend_direction
                    )

            # Create solvers
            self._create_solvers()

            # Mark as initialized
            self._state.set_solver_initialized(True)

            # Emit success signal
            self.solver_initialized.emit(True, self._state.get_all_joints())

            logging.info("IK system initialized from skeleton")
            return True

        except Exception as e:
            error_msg = f"Failed to initialize IK system: {str(e)}"
            logging.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)
            return False

    def _detect_humanoid_skeleton(self, joints: Dict[str, Any]) -> bool:
        """Detect if skeleton is humanoid based on joint IDs."""
        humanoid_joints = [
            'shoulder', 'elbow', 'wrist',
            'hip', 'knee', 'ankle',
        ]

        # Check joint IDs (which are the keys of the dict)
        joint_ids_lower = [jid.lower() for jid in joints.keys()]

        matches = sum(1 for joint_pattern in humanoid_joints
                     if any(joint_pattern in jid for jid in joint_ids_lower))

        # A humanoid should have at least arms and legs
        return matches >= 4

    def _create_solvers(self):
        """Create solvers for configured limbs."""
        self._solvers.clear()

        for limb_config in self._limb_config.get_all_limbs().values():
            if limb_config.solver_type not in self._solvers:
                solver = SolverFactory.create_solver(limb_config.solver_type)
                self._solvers[limb_config.solver_type] = solver

    def solve_limb(self, limb_name: str, target: QPointF) -> Optional[IKSolution]:
        """Solve IK for a specific limb.

        Args:
            limb_name: Name of limb to solve
            target: Target position for end effector

        Returns:
            IK solution or None if failed
        """
        # Get limb configuration
        limb_config = self._limb_config.get_limb(limb_name)
        if not limb_config:
            logging.error(f"Limb '{limb_name}' not found")
            return None

        # Get solver
        solver = self._solvers.get(limb_config.solver_type)
        if not solver:
            logging.error(f"No solver for type {limb_config.solver_type}")
            return None

        # Prepare joint positions
        joint_positions = {}
        for i, joint_name in enumerate(limb_config.joints):
            joint_state = self._state.get_joint(joint_name)
            if not joint_state:
                # Try with j_ prefix for backward compatibility
                if not joint_name.startswith('j_'):
                    joint_state = self._state.get_joint(f'j_{joint_name}')
                if not joint_state:
                    logging.error(f"Joint '{joint_name}' not found in state")
                    return None

            # Map to solver's expected names
            if i == 0:
                joint_positions['root'] = joint_state.position
            elif i == 1 and len(limb_config.joints) == 3:
                joint_positions['middle'] = joint_state.position
            elif i == len(limb_config.joints) - 1:
                joint_positions['end'] = joint_state.position

        # Prepare constraints
        constraints = {
            'bend_direction': limb_config.bend_direction
        }

        # Solve
        solution = solver.solve(target, joint_positions, constraints)

        if solution.success:
            # Update state with solution
            self._apply_solution(limb_config, solution)

            # Emit solved signal
            self.ik_solved.emit({
                'limb': limb_name,
                'solution': solution
            })

        return solution

    def _apply_solution(self, limb_config, solution: IKSolution):
        """Apply IK solution to state."""
        # Map solution back to actual joint names
        joint_mapping = {
            'root': limb_config.joints[0],
            'middle': limb_config.joints[1] if len(limb_config.joints) == 3 else None,
            'end': limb_config.joints[-1]
        }

        for solver_joint, position in solution.joint_positions.items():
            actual_joint = joint_mapping.get(solver_joint)
            if actual_joint:
                self._state.update_joint_position(actual_joint, position)

        for solver_joint, angle in solution.joint_angles.items():
            actual_joint = joint_mapping.get(solver_joint)
            if actual_joint:
                self._state.update_joint_angle(actual_joint, angle)

    def _solve_frame(self, targets: Dict[str, QPointF]):
        """Solve IK for animation frame."""
        for limb_name, target in targets.items():
            self.solve_limb(limb_name, target)

    def _on_state_changed(self, state_key: str):
        """Handle state changes."""
        logging.debug(f"IK state changed: {state_key}")

    def set_motion_paths(self, motion_paths: Dict[str, Any]):
        """Set motion paths for animation.

        Args:
            motion_paths: Dict mapping limb names to motion paths
        """
        self._animation.load_motion_paths(motion_paths)

    def start_animation(self):
        """Start IK animation."""
        self._animation.start()

    def stop_animation(self):
        """Stop IK animation."""
        self._animation.stop()

    def reset_animation(self):
        """Reset animation to beginning."""
        self._animation.reset()

    def get_limb_config(self, limb_name: str) -> Optional[Any]:
        """Get configuration for a specific limb."""
        return self._limb_config.get_limb(limb_name)

    def get_joint_parent(self, child_id: str) -> Optional[str]:
        """Get the parent of a specific joint from the stored hierarchy."""
        for parent_id, children in self._skeleton_hierarchy.items():
            if child_id in children:
                return parent_id
        return None

    @property
    def state(self) -> IKState:
        """Get IK state."""
        return self._state

    @property
    def animation(self) -> AnimationManager:
        """Get animation manager."""
        return self._animation

    def clear(self):
        """Clear all IK system components."""
        self._state.clear()
        self._joint_config.clear()
        self._limb_config.clear()
        self._animation.clear()
        self._solvers.clear()
        self._skeleton_hierarchy.clear()
        logging.info("IK coordinator cleared")