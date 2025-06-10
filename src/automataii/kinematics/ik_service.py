"""High-level service API for IK system."""

import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QPointF
from PyQt6.QtGui import QPainterPath

from .ik_coordinator import IKCoordinator

if TYPE_CHECKING:
    from ..core.skeleton_manager import SkeletonManager
    from ..gui.graphics_items.part_item import CharacterPartItem


class IKService(QObject):
    """High-level service interface for the IK system.

    This class provides a simplified API for interacting with the
    IK system, hiding implementation details from the rest of the
    application.
    """

    # Signals
    character_updated = pyqtSignal(dict)  # part transforms
    skeleton_updated = pyqtSignal(dict)  # joint positions
    animation_state_changed = pyqtSignal(str)  # playing/stopped
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._coordinator = IKCoordinator(self)
        self._skeleton_manager: Optional['SkeletonManager'] = None
        self._part_items: Dict[str, 'CharacterPartItem'] = {}
        self._limb_to_end_effector_part_map: Dict[str, str] = {}

        # Part name mappings
        self._ik_to_part_mapping = {
            "left_arm": "left_arm_upper",
            "right_arm": "right_arm_upper",
            "left_leg": "left_leg_upper",
            "right_leg": "right_leg_upper",
        }

        self._setup_connections()

        logging.info("IKService initialized")

    def _setup_connections(self):
        """Set up signal connections."""
        self._coordinator.solver_initialized.connect(self._on_solver_initialized)
        self._coordinator.ik_solved.connect(self._on_ik_solved)
        self._coordinator.animation_updated.connect(self._on_animation_updated)
        self._coordinator.error_occurred.connect(self.error_occurred)

    def set_skeleton_manager(self, skeleton_manager: 'SkeletonManager'):
        """Set reference to skeleton manager."""
        self._skeleton_manager = skeleton_manager

        # Connect to skeleton updates
        if hasattr(skeleton_manager, 'skeleton_updated'):
            skeleton_manager.skeleton_updated.connect(self._on_skeleton_updated)

    def set_part_items(self, part_items: Dict[str, 'CharacterPartItem']):
        """Set character part items for visual updates."""
        self._part_items = part_items

    def initialize_from_skeleton(self, skeleton_data: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize IK system from skeleton data.

        Args:
            skeleton_data: Optional skeleton data. If None, uses skeleton manager.

        Returns:
            True if successful
        """
        if skeleton_data is None and self._skeleton_manager:
            skeleton_data = self._skeleton_manager.get_current_skeleton_data()

        if not skeleton_data:
            logging.error("No skeleton data available for IK initialization")
            return False

        return self._coordinator.initialize_from_skeleton(skeleton_data)

    def set_motion_paths(self, motion_paths: Dict[str, QPainterPath]):
        """Set motion paths for parts.

        Args:
            motion_paths: Dict mapping part names to motion paths
        """
        # Convert part names to limb names and store the end-effector mapping
        limb_paths = {}
        self._limb_to_end_effector_part_map.clear()
        for part_name, path in motion_paths.items():
            limb_name = self._part_to_limb_name(part_name)
            if limb_name:
                limb_paths[limb_name] = path
                self._limb_to_end_effector_part_map[limb_name] = part_name

        self._coordinator.set_motion_paths(limb_paths)

    def start_animation(self):
        """Start IK animation."""
        self._coordinator.start_animation()
        self.animation_state_changed.emit("playing")

    def stop_animation(self):
        """Stop IK animation."""
        self._coordinator.stop_animation()
        self.animation_state_changed.emit("stopped")

    def reset_animation(self):
        """Reset animation to beginning."""
        self._coordinator.reset_animation()
        self.animation_state_changed.emit("reset")

    def set_animation_duration(self, duration_ms: int):
        """Set animation duration in milliseconds."""
        self._coordinator.animation.set_duration(duration_ms)

    def set_animation_loop(self, loop: bool):
        """Set whether animation should loop."""
        self._coordinator.animation.set_loop(loop)

    def solve_limb_ik(self, limb_name: str, target: QPointF) -> bool:
        """Manually solve IK for a limb.

        Args:
            limb_name: Name of limb
            target: Target position

        Returns:
            True if successful
        """
        solution = self._coordinator.solve_limb(limb_name, target)
        return solution is not None and solution.success

    def get_joint_positions(self) -> Dict[str, QPointF]:
        """Get current joint positions."""
        joints = self._coordinator.state.get_all_joints()
        return {name: data['position'] for name, data in joints.items()}

    def get_joint_angles(self) -> Dict[str, float]:
        """Get current joint angles."""
        joints = self._coordinator.state.get_all_joints()
        return {name: data['angle'] for name, data in joints.items()}

    def is_initialized(self) -> bool:
        """Check if IK system is initialized."""
        return self._coordinator.state.solver_initialized

    def is_animating(self) -> bool:
        """Check if animation is playing."""
        return self._coordinator.state.is_animating

    def clear(self):
        """Clear all IK data."""
        self._coordinator.clear()
        self._limb_to_end_effector_part_map.clear()

    @property
    def coordinator(self):
        """Get the IK coordinator (for internal use)."""
        return self._coordinator

    def _part_to_limb_name(self, part_name: str) -> Optional[str]:
        """Convert part name to limb name."""
        # Check direct mapping
        for limb_name, mapped_part in self._ik_to_part_mapping.items():
            if part_name == mapped_part:
                return limb_name

        # Check if part name contains limb indicators
        if 'arm' in part_name.lower():
            if 'left' in part_name.lower():
                return 'left_arm'
            elif 'right' in part_name.lower():
                return 'right_arm'
        elif 'leg' in part_name.lower():
            if 'left' in part_name.lower():
                return 'left_leg'
            elif 'right' in part_name.lower():
                return 'right_leg'

        return None

    def _on_solver_initialized(self, success: bool, joint_config: Dict[str, Any]):
        """Handle solver initialization."""
        if success:
            logging.info("IK solver initialized successfully")
            self.skeleton_updated.emit(joint_config)
        else:
            logging.error("IK solver initialization failed")

    def _on_ik_solved(self, solution_data: Dict[str, Any]):
        """Handle IK solution."""
        # Update character visuals if part items are available
        if self._part_items:
            self._update_character_visuals(solution_data)

    def _on_animation_updated(self, progress: float):
        """Handle animation update."""
        # Could emit progress or handle frame updates
        pass

    def _on_skeleton_updated(self, skeleton_data: Dict[str, Any]):
        """Handle skeleton data update from skeleton manager."""
        # Re-initialize if needed
        if self.is_initialized():
            self.initialize_from_skeleton(skeleton_data)

    def _update_character_visuals(self, solution_data: Dict[str, Any]):
        """Update character part visuals based on IK solution."""
        limb_name = solution_data.get('limb')
        solution = solution_data.get('solution')

        if not limb_name or not solution:
            return

        joint_positions = getattr(solution, 'joint_positions', {})
        joint_angles = getattr(solution, 'joint_angles', {})

        if not joint_positions or not joint_angles:
            logging.warning("IK solution is missing position or angle data.")
            return

        transforms = {}
        limb_config = self._coordinator.get_limb_config(limb_name)
        if not limb_config:
            logging.warning(f"Could not find config for limb '{limb_name}'")
            return

        # This mapping is crucial. It connects skeleton joints to body part names.
        # We need a robust way to get this. For now, let's assume a convention.
        # Example: 'left_shoulder' joint controls 'left_arm_upper' part.
        #          'left_elbow' joint controls 'left_arm_lower' part.
        joint_to_part_map = self._get_joint_to_part_map(limb_name, limb_config)

        # Get world angle of the parent of the first joint
        root_joint_id = limb_config.joints[0]
        root_parent_id = self._coordinator.get_joint_parent(root_joint_id)
        parent_world_angle = 0.0
        if root_parent_id:
            # Note: We should probably fetch the entire joint data once and cache it
            parent_world_angle = self._coordinator.state.get_joint_data(root_parent_id).get('angle', 0.0)

        for i, joint_id in enumerate(limb_config.joints):
            part_name = joint_to_part_map.get(joint_id)
            if not part_name:
                continue

            position = joint_positions.get(joint_id)
            world_angle = joint_angles.get(joint_id, 0.0)

            # Rotation of the part is its world angle minus its parent's world angle.
            # For the first part in the limb, the parent is the joint the limb is attached to (e.g., torso).
            # For subsequent parts, the parent is the previous joint in the limb.
            parent_angle = parent_world_angle if i == 0 else joint_angles.get(limb_config.joints[i-1], 0.0)
            rotation = world_angle - parent_angle

            if position is not None:
                transforms[part_name] = {
                    'position': position,
                    'rotation': rotation
                }

        if transforms:
            self.character_updated.emit(transforms)
            # logging.debug(f"IKService: Updated visuals for limb '{limb_name}' with transforms: {transforms}")

    def _get_joint_to_part_map(self, limb_name: str, limb_config: Dict[str, Any]) -> Dict[str, str]:
        """Dynamically create a map from joint IDs to part names for a limb."""
        # This is a temporary, convention-based solution.
        # A more robust implementation would use metadata from the skeleton definition.
        mapping = {}
        joints = limb_config.joints

        if limb_name == 'left_arm' and len(joints) >= 2:
            mapping[joints[0]] = 'left_arm_upper'
            mapping[joints[1]] = 'left_arm_lower'
        elif limb_name == 'right_arm' and len(joints) >= 2:
            mapping[joints[0]] = 'right_arm_upper'
            mapping[joints[1]] = 'right_arm_lower'
        elif limb_name == 'left_leg' and len(joints) >= 2:
            mapping[joints[0]] = 'left_leg_upper'
            mapping[joints[1]] = 'left_leg_lower'
        elif limb_name == 'right_leg' and len(joints) >= 2:
            mapping[joints[0]] = 'right_leg_upper'
            mapping[joints[1]] = 'right_leg_lower'

        return mapping