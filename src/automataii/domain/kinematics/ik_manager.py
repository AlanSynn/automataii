# src/automataii/kinematics/ik_manager.py
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QLineF, QObject, QPointF, pyqtSignal

from automataii.models.skeleton import StandardizedJointModel, StandardizedSkeletonModel

from .ik_solver_improved import FABRIKSolver, IKChain, IKSolver

if TYPE_CHECKING:
    pass

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
        self.skeleton_model: StandardizedSkeletonModel | None = None
        self.ik_chains: dict[str, IKChain] = {}  # Maps end-effector ID to its chain
        self.solver: IKSolver = FABRIKSolver()
        self.joint_positions: dict[str, QPointF] = {}
        self._initial_joint_positions: dict[str, QPointF] = {}

    def on_skeleton_data_updated(self, skeleton_data: dict | None):
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

        except Exception as e:
            self.clear_all_data()
            logger.error(f"Failed to build IK chains from skeleton data: {e}", exc_info=True)
            self.error_occurred.emit(f"Failed to initialize IK skeleton: {e}")

    def _build_ik_chains(self):
        """
        Parses the skeleton model and creates IKChain objects for each limb.
        """
        # Clear only the IK chains and positions, not the skeleton model
        self.ik_chains.clear()
        self.joint_positions.clear()
        self._initial_joint_positions.clear()

        if not self.skeleton_model:
            logger.warning("No skeleton model available for IK chain building")
            return

        # Building IK chains from skeleton

        # Store initial positions from the validated model - ensure QPointF format
        for joint_id, joint in self.skeleton_model.joints.items():
            if isinstance(joint.position, tuple):
                self._initial_joint_positions[joint_id] = QPointF(joint.position[0], joint.position[1])
            elif hasattr(joint.position, 'x') and hasattr(joint.position, 'y'):
                self._initial_joint_positions[joint_id] = joint.position
            else:
                logger.warning(f"Unknown position type for {joint_id}: {type(joint.position)}")
                self._initial_joint_positions[joint_id] = QPointF(0, 0)  # Fallback

        # Define limb chains based on end-effectors
        # This could be loaded from a rig definition file in the future
        # These are abstract names that will be mapped to standardized IDs
        # Using joint names that actually exist in the skeleton
        end_effector_abstract_names = [
            "left_hand",
            "right_hand",
            "left_foot",
            "right_foot",
            "neck",
        ]

        successful_chains = 0
        for abstract_name in end_effector_abstract_names:
            effector_id = self.skeleton_model.joint_map.get(abstract_name)
            if not effector_id:
                logger.warning(f"Could not find standardized ID for end-effector '{abstract_name}'.")
                continue

            chain_joints = self._trace_chain_to_root(effector_id)
            if chain_joints and len(chain_joints) >= 2:
                # The key for the chain is the end-effector's standardized ID
                chain = IKChain(chain_joints)
                self.ik_chains[effector_id] = chain
                successful_chains += 1
            else:
                logger.warning(f"Could not create valid chain for {abstract_name}")

        logger.info(f"Created {successful_chains}/{len(end_effector_abstract_names)} IK chains")

    def _trace_chain_to_root(self, end_effector_id: str) -> list[StandardizedJointModel]:
        """Traces a joint's hierarchy back to a root or a maximum depth."""
        chain: list[StandardizedJointModel] = []
        current_id: str | None = end_effector_id

        # Max depth to prevent infinite loops in case of malformed hierarchy
        for i in range(10):
            if not current_id:
                break
            joint = self.skeleton_model.get_joint(current_id)
            if not joint:
                break

            chain.append(joint)
            current_id = joint.parent_id

            # Stop at torso or hip to create reasonable IK chains
            if current_id in ["torso", "hip", "root"]:
                # Add the parent joint too for a complete chain
                parent_joint = self.skeleton_model.get_joint(current_id)
                if parent_joint:
                    chain.append(parent_joint)
                break
        return list(reversed(chain))  # Return in order from root to effector

    def solve_for_targets(self, targets: dict[str, QPointF]):
        """
        Solves the IK for the entire skeleton given a set of targets.
        Preserves skeleton bone lengths even when targets are out of reach.

        Args:
            targets: A dictionary mapping end-effector IDs to their target QPointF positions.
        """
        if not self.ik_chains:
            return

        # Don't reset pose here - it prevents IK results from being seen

        # Solve for each chain that has a target
        successfully_solved = False
        for effector_id, target_pos in targets.items():
            if effector_id in self.ik_chains:
                try:
                    chain = self.ik_chains[effector_id]

                    # Check if target is reachable and log the information
                    max_reach = sum(chain.bone_lengths)
                    base_pos = chain.get_joint_positions()[0]
                    target_distance = QLineF(base_pos, target_pos).length()

                    if target_distance > max_reach:
                        logger.info(
                            f"Effector {effector_id}: Target out of reach "
                            f"(distance={target_distance:.2f}, max_reach={max_reach:.2f}) - "
                            f"extending limb in target direction while preserving bone lengths"
                        )

                    # Solve IK for this effector
                    solved_positions = self.solver.solve(chain, target_pos)

                    if not solved_positions:
                        logger.error(f"IK solver returned empty positions for {effector_id}")
                        continue

                    if len(chain.joints) < 2:
                        logger.warning(f"Chain {effector_id} has insufficient joints ({len(chain.joints)}) for IK solving")
                        continue

                    # Ensure we have the right number of positions
                    if len(solved_positions) != len(chain.joints):
                        logger.error(f"Position mismatch for {effector_id}: expected {len(chain.joints)}, got {len(solved_positions)}")
                        continue

                    # Update the main joint positions dictionary with the solved chain
                    for i, joint_model in enumerate(chain.joints):
                        if i < len(solved_positions):
                            self.joint_positions[joint_model.id] = solved_positions[i]

                    successfully_solved = True

                except Exception as e:
                    logger.error(f"Exception during IK solve for {effector_id}: {e}")
                    continue
            else:
                logger.warning(f"Effector {effector_id} not found in IK chains")

        # CRITICAL FIX: Only update pose if IK solving was successful
        if successfully_solved:
            # Ensure ALL skeleton joints have positions (not just those in IK chains)
            all_joint_positions = self._get_complete_skeleton_pose()

            # Convert QPointF positions to tuples for consistent data format
            pose_tuples = {}
            for joint_id, qpoint in all_joint_positions.items():
                if hasattr(qpoint, 'x') and hasattr(qpoint, 'y'):
                    pose_tuples[joint_id] = (qpoint.x(), qpoint.y())
                elif isinstance(qpoint, tuple):
                    pose_tuples[joint_id] = qpoint
                else:
                    logger.warning(f"Unknown position format for joint {joint_id}: {type(qpoint)}")
                    continue

            # Emit the complete updated pose in consistent tuple format
            self.pose_updated.emit(pose_tuples)
        else:
            logger.warning(f"No successful IK solutions")

    def reset_pose(self):
        """Resets all joint positions to their initial state and emits the pose."""
        # CRITICAL FIX: Ensure all positions are QPointF objects even in initial state
        self.joint_positions.clear()
        for joint_id, initial_pos in self._initial_joint_positions.items():
            if isinstance(initial_pos, tuple):
                self.joint_positions[joint_id] = QPointF(initial_pos[0], initial_pos[1])
            elif hasattr(initial_pos, 'x') and hasattr(initial_pos, 'y'):
                self.joint_positions[joint_id] = initial_pos
            else:
                logger.warning(f"Unknown initial position type for {joint_id}: {type(initial_pos)}")
                continue

        # Get complete pose and convert to tuples
        all_joint_positions = self._get_complete_skeleton_pose()

        # Convert all positions to tuples for consistent data format
        pose_tuples = {}
        for joint_id, qpoint in all_joint_positions.items():
            if hasattr(qpoint, 'x') and hasattr(qpoint, 'y'):
                pose_tuples[joint_id] = (qpoint.x(), qpoint.y())
            elif isinstance(qpoint, tuple):
                pose_tuples[joint_id] = qpoint
            else:
                logger.warning(f"Unknown position format for joint {joint_id}: {type(qpoint)}")
                continue

        self.pose_updated.emit(pose_tuples)

    def clear_all_data(self):
        """Clears all internal data."""
        self.skeleton_model = None
        self.ik_chains.clear()
        self.joint_positions.clear()
        self._initial_joint_positions.clear()

    def get_end_effector_for_part(self, part_name: str) -> str | None:
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
            # Map actual part names to IK end-effectors (using joint names that exist in skeleton)
            "left_arm_lower": "left_hand",  # left_arm_lower -> left_hand
            "right_arm_lower": "right_hand",  # right_arm_lower -> right_hand
            "left_leg_lower": "left_foot",  # left_leg_lower -> left_foot
            "right_leg_lower": "right_foot",  # right_leg_lower -> right_foot
            "head": "neck",  # head part -> neck joint
            "left_arm_upper": "left_elbow",  # left_arm_upper -> left_elbow
            "right_arm_upper": "right_elbow",  # right_arm_upper -> right_elbow
            "torso": "hip",  # torso movement could drive the hip
            # Legacy names for backward compatibility
            "left_forearm": "left_hand",
            "right_forearm": "right_hand",
            "left_shin": "left_foot",
            "right_shin": "right_foot",
            "left_upper_arm": "left_elbow",
            "right_upper_arm": "right_elbow",
        }

        abstract_name = part_to_effector_abstract_name.get(part_name)
        if not abstract_name:
            # Fallback for parts that might be named the same as abstract joints
            if part_name in self.skeleton_model.joint_map:
                abstract_name = part_name
            else:
                return None

        # Map the abstract name (e.g., "left_hand") to its standardized ID (e.g., "left_hand_9")
        effector_id = self.skeleton_model.joint_map.get(abstract_name)
        if not effector_id:
            logger.warning(f"Could not find standardized ID for abstract joint '{abstract_name}'.")
            return None

        # The returned ID is the end-effector that should be targeted.
        return effector_id

    def get_max_reach_distance(self, effector_id: str) -> float | None:
        """
        Returns the maximum reach distance for a given end-effector.
        This is useful for checking if a target is reachable before solving.

        Args:
            effector_id: The standardized ID of the end-effector

        Returns:
            Maximum reach distance in pixels, or None if chain not found
        """
        if effector_id not in self.ik_chains:
            return None

        chain = self.ik_chains[effector_id]
        return sum(chain.bone_lengths)

    def is_target_reachable(self, effector_id: str, target_pos: QPointF) -> bool:
        """
        Checks if a target position is reachable by the given end-effector.

        Args:
            effector_id: The standardized ID of the end-effector
            target_pos: The target position to check

        Returns:
            True if target is reachable, False otherwise
        """
        if effector_id not in self.ik_chains:
            return False

        chain = self.ik_chains[effector_id]
        base_pos = chain.get_joint_positions()[0]
        target_distance = QLineF(base_pos, target_pos).length()
        max_reach = sum(chain.bone_lengths)

        return target_distance <= max_reach

    def _get_complete_skeleton_pose(self) -> dict[str, QPointF]:
        """
        Returns a complete skeleton pose including both IK-controlled joints
        and non-IK joints (like spine, torso, etc.).

        Returns:
            Dictionary mapping joint_id to QPointF position
        """
        complete_pose = {}

        if not self.skeleton_model:
            return complete_pose

        # Building complete pose with both initial and IK-updated positions

        # Start with all initial positions
        complete_pose.update(self._initial_joint_positions)

        # Override with IK-updated positions for joints that are in chains
        for joint_id, new_pos in self.joint_positions.items():
            # CRITICAL FIX: Ensure all positions are QPointF objects
            if isinstance(new_pos, tuple):
                new_pos_qpoint = QPointF(new_pos[0], new_pos[1])
            elif hasattr(new_pos, 'x') and hasattr(new_pos, 'y'):
                new_pos_qpoint = new_pos
            else:
                logger.warning(f"Unknown position type {type(new_pos)} for {joint_id}")
                continue

            complete_pose[joint_id] = new_pos_qpoint

        # For joints not in any IK chain, we might want to compute their positions
        # based on their parent joints. This ensures the skeleton stays connected.
        ik_joint_ids = set()
        actually_updated_joint_ids = set(self.joint_positions.keys())

        for chain_id, chain in self.ik_chains.items():
            for joint in chain.joints:
                ik_joint_ids.add(joint.id)

        # IK chains control joints, some are updated by solving

        # Update positions for joints that depend on IK-controlled joints
        for joint_id, joint in self.skeleton_model.joints.items():
            if joint_id not in ik_joint_ids and joint.parent_id:
                parent_id = joint.parent_id
                if parent_id in complete_pose:
                    # If parent was moved by IK, we might need to adjust this joint's position
                    # For now, keep original relative position but this could be enhanced
                    parent_pos = complete_pose[parent_id]
                    original_parent_pos = self._initial_joint_positions.get(parent_id)
                    original_joint_pos = self._initial_joint_positions.get(joint_id)

                    if original_parent_pos and original_joint_pos:
                        # Calculate relative offset from parent
                        if hasattr(original_parent_pos, 'x'):
                            parent_orig_x, parent_orig_y = original_parent_pos.x(), original_parent_pos.y()
                        else:
                            parent_orig_x, parent_orig_y = original_parent_pos[0], original_parent_pos[1]

                        if hasattr(original_joint_pos, 'x'):
                            joint_orig_x, joint_orig_y = original_joint_pos.x(), original_joint_pos.y()
                        else:
                            joint_orig_x, joint_orig_y = original_joint_pos[0], original_joint_pos[1]

                        if hasattr(parent_pos, 'x'):
                            parent_new_x, parent_new_y = parent_pos.x(), parent_pos.y()
                        else:
                            parent_new_x, parent_new_y = parent_pos[0], parent_pos[1]

                        # Calculate relative offset and apply to new parent position
                        offset_x = joint_orig_x - parent_orig_x
                        offset_y = joint_orig_y - parent_orig_y

                        new_joint_pos = QPointF(parent_new_x + offset_x, parent_new_y + offset_y)
                        complete_pose[joint_id] = new_joint_pos

        return complete_pose
