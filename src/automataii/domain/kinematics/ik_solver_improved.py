import logging
import math

from PyQt6.QtCore import QLineF, QPointF

from automataii.models.skeleton import StandardizedJointModel

logger = logging.getLogger(__name__)


class IKSolver:
    """
    An abstract base class for different IK solving algorithms.
    """

    def solve(self, chain: "IKChain", target_pos: QPointF) -> list[QPointF]:
        raise NotImplementedError


class FABRIKSolver(IKSolver):
    """
    Implements the FABRIK (Forward And Backward Reaching Inverse Kinematics) algorithm
    with constraints for natural limb bending.
    """

    def __init__(self, iterations: int = 15, tolerance: float = 1.0):
        self.iterations = iterations
        self.tolerance = tolerance

    def solve(self, chain: "IKChain", target_pos: QPointF) -> list[QPointF]:
        """Solves the IK for the given chain and target position."""
        if not chain.joints or len(chain.joints) < 2:
            return []

        joint_positions = chain.get_joint_positions()
        base_pos = joint_positions[0]
        bone_lengths = chain.bone_lengths
        total_length = sum(bone_lengths)
        
        # Store original bone lengths for validation
        original_bone_lengths = bone_lengths.copy()

        # Check reachability
        target_distance = QLineF(base_pos, target_pos).length()
        is_reachable = target_distance <= total_length
        
        if not is_reachable:
            # Target is unreachable - stretch chain towards target
            direction = target_pos - base_pos
            direction_length = QLineF(QPointF(0, 0), direction).length()

            if direction_length > 1e-9:
                # Normalize the direction vector
                normalized_direction = direction / direction_length
                
                # Stretch the chain in the target direction
                joint_positions[0] = base_pos
                for i in range(len(bone_lengths)):
                    joint_positions[i + 1] = joint_positions[i] + normalized_direction * bone_lengths[i]
                
                # Validate bone lengths remain constant
                self._validate_bone_lengths(joint_positions, original_bone_lengths)
                return joint_positions
            else:
                # If target is too close to base, use default direction
                target_pos = base_pos + QPointF(total_length, 0)

        # --- FABRIK iterations ---
        for _ in range(self.iterations):
            # Forward pass (end effector to base)
            joint_positions[-1] = target_pos
            for i in range(len(joint_positions) - 2, -1, -1):
                direction = joint_positions[i] - joint_positions[i + 1]
                dist = QLineF(QPointF(0, 0), direction).length()

                # More robust numerical stability check
                if dist > 1e-9:
                    joint_positions[i] = (
                        joint_positions[i + 1] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Use previous direction if available, otherwise use default
                    if i > 0:
                        prev_direction = joint_positions[i - 1] - joint_positions[i]
                        prev_dist = QLineF(QPointF(0, 0), prev_direction).length()
                        if prev_dist > 1e-9:
                            joint_positions[i] = (
                                joint_positions[i + 1]
                                + (prev_direction / prev_dist) * bone_lengths[i]
                            )
                        else:
                            joint_positions[i] = joint_positions[i + 1] + QPointF(
                                bone_lengths[i], 0
                            )
                    else:
                        joint_positions[i] = joint_positions[i + 1] + QPointF(bone_lengths[i], 0)

            # Backward pass (base to end effector)
            joint_positions[0] = base_pos
            for i in range(len(joint_positions) - 1):
                direction = joint_positions[i + 1] - joint_positions[i]
                dist = QLineF(QPointF(0, 0), direction).length()

                # More robust numerical stability check
                if dist > 1e-9:
                    joint_positions[i + 1] = (
                        joint_positions[i] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Use next direction if available, otherwise use default
                    if i < len(joint_positions) - 2:
                        next_direction = joint_positions[i + 2] - joint_positions[i + 1]
                        next_dist = QLineF(QPointF(0, 0), next_direction).length()
                        if next_dist > 1e-9:
                            joint_positions[i + 1] = (
                                joint_positions[i] + (next_direction / next_dist) * bone_lengths[i]
                            )
                        else:
                            joint_positions[i + 1] = joint_positions[i] + QPointF(
                                bone_lengths[i], 0
                            )
                    else:
                        joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)

            # Check for convergence
            if QLineF(joint_positions[-1], target_pos).length() < self.tolerance:
                break

        # Apply bend direction constraints post-solving
        if chain.bend_direction != 0 and len(joint_positions) > 2:
            for i in range(1, len(joint_positions) - 1):
                p0, p1, p2 = joint_positions[i - 1], joint_positions[i], joint_positions[i + 1]

                vec = p2 - p0
                if vec.manhattanLength() == 0:
                    continue

                mid_point = p0 + vec * 0.5

                # Perpendicular vector for bend direction
                perp_vec = QPointF(-vec.y(), vec.x())
                perp_vec_length = QLineF(QPointF(0, 0), perp_vec).length()

                # Avoid division by zero
                if perp_vec_length > 1e-9:
                    perp_vec = perp_vec / perp_vec_length
                else:
                    # Use default perpendicular direction
                    perp_vec = QPointF(0, 1)

                # Height of the triangle (distance from midpoint to the middle joint)
                # Ensure we don't get negative values under square root
                mid_dist = QLineF(p0, mid_point).length()
                bone_length_sq = bone_lengths[i - 1] ** 2
                mid_dist_sq = mid_dist**2

                # Use numerical stability check
                if bone_length_sq > mid_dist_sq:
                    h = math.sqrt(bone_length_sq - mid_dist_sq)
                else:
                    h = 0.0  # Joint is at maximum extension

                # Apply the offset in the determined bend direction
                joint_positions[i] = mid_point + perp_vec * h * chain.bend_direction

        # Final validation to ensure bone lengths are preserved
        self._validate_bone_lengths(joint_positions, original_bone_lengths)
        
        return joint_positions
    
    def _validate_bone_lengths(self, joint_positions: list[QPointF], original_lengths: list[float]) -> None:
        """Validates that bone lengths remain constant after IK solving."""
        for i in range(len(original_lengths)):
            actual_length = QLineF(joint_positions[i], joint_positions[i + 1]).length()
            expected_length = original_lengths[i]
            
            # Check if lengths match within tolerance
            if abs(actual_length - expected_length) > 1e-6:
                logger.warning(
                    f"Bone length mismatch at index {i}: "
                    f"expected={expected_length:.4f}, actual={actual_length:.4f}"
                )
                
                # Force correction if needed
                if actual_length > 1e-9:
                    direction = joint_positions[i + 1] - joint_positions[i]
                    direction_normalized = direction / actual_length
                    joint_positions[i + 1] = joint_positions[i] + direction_normalized * expected_length


class IKChain:
    """
    Represents a single kinematic chain (e.g., an arm or a leg),
    holding the joints in order and their properties.
    """

    def __init__(self, joints: list[StandardizedJointModel]):
        # Joints are assumed to be passed in order from root to effector
        self.joints: list[StandardizedJointModel] = joints
        self.bone_lengths: list[float] = self._calculate_bone_lengths()
        self.bend_direction: int = self._infer_bend_direction()

    def _calculate_bone_lengths(self) -> list[float]:
        """Calculates the length of each bone in the chain."""
        lengths = []
        for i in range(len(self.joints) - 1):
            p1 = self.joints[i].position
            p2 = self.joints[i + 1].position

            # Convert tuples to QPointF if necessary
            if isinstance(p1, tuple):
                p1 = QPointF(p1[0], p1[1])
            if isinstance(p2, tuple):
                p2 = QPointF(p2[0], p2[1])

            length = QLineF(p1, p2).length()

            # Ensure minimum bone length for numerical stability
            if length < 1e-6:
                logging.warning(
                    f"Very small bone length {length} detected in chain, using minimum length 1e-6"
                )
                length = 1e-6

            lengths.append(length)
        return lengths

    def _infer_bend_direction(self) -> int:
        """
        Infers the natural bend direction (e.g., for an elbow or knee)
        from the initial pose of the chain.
        Returns +1 for one side, -1 for the other, or 0 if straight/not applicable.
        """
        if len(self.joints) < 3:
            return 0  # Not applicable for 2-joint chains

        p0 = self.joints[0].position
        p1 = self.joints[1].position
        p2 = self.joints[2].position

        # Convert tuples to QPointF if necessary
        if isinstance(p0, tuple):
            p0 = QPointF(p0[0], p0[1])
        if isinstance(p1, tuple):
            p1 = QPointF(p1[0], p1[1])
        if isinstance(p2, tuple):
            p2 = QPointF(p2[0], p2[1])

        # Using the 2D cross-product of (p1-p0) and (p2-p1) to determine the side
        v1 = QPointF(p1.x() - p0.x(), p1.y() - p0.y())
        v2 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())

        # Check if vectors are degenerate
        if QLineF(QPointF(0, 0), v1).length() < 1e-9 or QLineF(QPointF(0, 0), v2).length() < 1e-9:
            return 0  # Cannot determine bend direction with degenerate vectors

        cross_product = v1.x() * v2.y() - v1.y() * v2.x()

        # Invert the sign for Qt's Y-down coordinate system to get intuitive bend directions
        # Use more robust threshold
        if cross_product > 1e-9:
            return -1  # e.g., Left bend
        elif cross_product < -1e-9:
            return 1  # e.g., Right bend
        return 0  # Straight

    def get_joint_positions(self) -> list[QPointF]:
        """Returns a list of the current positions of the joints in the chain."""
        positions = []
        for joint in self.joints:
            pos = joint.position
            if isinstance(pos, tuple):
                pos = QPointF(pos[0], pos[1])
            positions.append(pos)
        return positions
