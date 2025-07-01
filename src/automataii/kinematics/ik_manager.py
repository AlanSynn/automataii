# src/automataii/kinematics/ik_manager.py
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from .ik_solver_improved import IKSolver, FABRIKSolver, IKChain
from automataii.core.models_skeleton import StandardizedSkeletonModel, StandardizedJointModel

if TYPE_CHECKING:
    from ..core.skeleton_manager import SkeletonManager

logger = logging.getLogger(__name__)

class IKManager(QObject):
    """
    Manages the Inverse Kinematics (IK) state and solving for a skeleton.
    This class acts as an orchestrator, holding the skeleton's kinematic chains
    and using a solver to calculate new poses based on targets.
    It is now decoupled from animation timing.
    """
    pose_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.skeleton_model: Optional[StandardizedSkeletonModel] = None
        self.ik_chains: Dict[str, IKChain] = {}  # Maps end-effector ID to its chain
        self.solver: IKSolver = FABRIKSolver()
        self.joint_positions: Dict[str, QPointF] = {}
        self._initial_joint_positions: Dict[str, QPointF] = {}

    def on_skeleton_data_updated(self, skeleton_data: Optional[Dict]):
        """
        Receives new skeleton data, clears old state, and builds new IK chains.
        """
        if not skeleton_data:
            self.clear_all_data()
            return

        try:
            # The skeleton_data is already a dict, so we validate it into the pydantic model
            self.skeleton_model = StandardizedSkeletonModel.model_validate(skeleton_data)
            self._build_ik_chains()
            self.reset_pose()
            logger.info(f"IKManager: Successfully built {len(self.ik_chains)} IK chains.")
        except Exception as e:
            self.clear_all_data()
            logger.error(f"Failed to build IK chains from skeleton data: {e}", exc_info=True)
            self.error_occurred.emit(f"Failed to initialize IK skeleton: {e}")

    def _build_ik_chains(self):
        """
        Parses the skeleton model and creates IKChain objects for each limb.
        """
        self.clear_all_data()
        if not self.skeleton_model:
            return

        # Store initial positions from the validated model
        for joint_id, joint in self.skeleton_model.joints.items():
            self._initial_joint_positions[joint_id] = joint.position

        # Define limb chains based on end-effectors
        # This could be loaded from a rig definition file in the future
        # These are abstract names that will be mapped to standardized IDs
        end_effector_abstract_names = ["left_hand", "right_hand", "left_foot", "right_foot", "head"]

        for abstract_name in end_effector_abstract_names:
            effector_id = self.skeleton_model.joint_map.get(abstract_name)
            if not effector_id:
                logger.debug(f"Could not find standardized ID for end-effector '{abstract_name}'.")
                continue

            chain_joints = self._trace_chain_to_root(effector_id)
            if chain_joints:
                # The key for the chain is the end-effector's standardized ID
                self.ik_chains[effector_id] = IKChain(chain_joints)

    def _trace_chain_to_root(self, end_effector_id: str) -> List[StandardizedJointModel]:
        """Traces a joint's hierarchy back to a root or a maximum depth."""
        chain: List[StandardizedJointModel] = []
        current_id: Optional[str] = end_effector_id

        # Max depth to prevent infinite loops in case of malformed hierarchy
        for _ in range(10):
            if not current_id:
                break
            joint = self.skeleton_model.get_joint(current_id)
            if not joint:
                break
            chain.append(joint)
            current_id = joint.parent_id

        return list(reversed(chain)) # Return in order from root to effector

    def solve_for_targets(self, targets: Dict[str, QPointF]):
        """
        Solves the IK for the entire skeleton given a set of targets.

        Args:
            targets: A dictionary mapping end-effector IDs to their target QPointF positions.
        """
        if not self.ik_chains:
            return

        # Reset to initial pose before solving to ensure a consistent starting point
        self.reset_pose()

        # Solve for each chain that has a target
        for effector_id, target_pos in targets.items():
            if effector_id in self.ik_chains:
                chain = self.ik_chains[effector_id]

                # The solver returns a list of new QPointF positions for the joints in the chain
                solved_positions = self.solver.solve(chain, target_pos)

                # Update the main joint positions dictionary with the solved chain
                for i, joint_model in enumerate(chain.joints):
                    self.joint_positions[joint_model.id] = solved_positions[i]

        # Emit the complete updated pose
        self.pose_updated.emit(self.joint_positions)

    def reset_pose(self):
        """Resets all joint positions to their initial state and emits the pose."""
        self.joint_positions = self._initial_joint_positions.copy()
        self.pose_updated.emit(self.joint_positions)

    def clear_all_data(self):
        """Clears all internal data."""
        self.skeleton_model = None
        self.ik_chains.clear()
        self.joint_positions.clear()
        self._initial_joint_positions.clear()
        logger.info("IKManager: All data has been cleared.")

    def get_end_effector_for_part(self, part_name: str) -> Optional[str]:
        """
        Maps a visual part name (e.g., 'left_forearm') to its controlling
        end-effector ID (e.g., 'std_lhand_9').
        """
        if not self.skeleton_model:
            logger.warning("Cannot get end effector: skeleton model not loaded.")
            return None

        # This map defines which end-effector's IK chain is driven by a part's motion path.
        # The key is the part name (from parts_info.json), the value is the ABSTRACT joint name.
        part_to_effector_abstract_name = {
            "left_forearm": "left_hand",
            "right_forearm": "right_hand",
            "left_shin": "left_foot",
            "right_shin": "right_foot",
            "head": "head",
            "left_upper_arm": "left_elbow",
            "right_upper_arm": "right_elbow",
            "torso": "hip", # Example: torso movement could drive the hip
        }

        abstract_name = part_to_effector_abstract_name.get(part_name)
        if not abstract_name:
            # Fallback for parts that might be named the same as abstract joints
            if part_name in self.skeleton_model.joint_map:
                abstract_name = part_name
            else:
                logger.debug(f"No IK end-effector mapping found for part '{part_name}'.")
                return None

        # Map the abstract name (e.g., "left_hand") to its standardized ID (e.g., "left_hand_9")
        effector_id = self.skeleton_model.joint_map.get(abstract_name)
        if not effector_id:
            logger.warning(f"Could not find standardized ID for abstract joint '{abstract_name}'.")
            return None

        # The returned ID is the end-effector that should be targeted.
        return effector_id