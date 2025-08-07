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
            logger.error(f"FABRIK: Invalid chain - joints: {len(chain.joints) if chain.joints else 0}")
            return []

        joint_positions = chain.get_joint_positions()

        if not joint_positions:
            logger.error(f"FABRIK: Chain returned empty joint positions")
            return []

        base_pos = joint_positions[0]
        bone_lengths = chain.bone_lengths
        total_length = sum(bone_lengths)



        # Store original bone lengths for validation
        original_bone_lengths = bone_lengths.copy()

        # Check reachability - preserve skeleton length when target is out of reach
        target_distance = QLineF(base_pos, target_pos).length()
        is_reachable = target_distance <= total_length

        if not is_reachable:
            # Target is unreachable - stretch chain towards target while preserving bone lengths
            logger.info(f"Target unreachable: distance={target_distance:.2f}, max_reach={total_length:.2f}")

            direction = target_pos - base_pos
            direction_length = QLineF(QPointF(0, 0), direction).length()

            if direction_length > 1e-9:
                # Normalize the direction vector and extend skeleton
                normalized_direction = direction / direction_length

                joint_positions[0] = base_pos
                for i in range(len(bone_lengths)):
                    joint_positions[i + 1] = joint_positions[i] + normalized_direction * bone_lengths[i]

                # Validate bone lengths remain constant
                self._validate_bone_lengths(joint_positions, original_bone_lengths)
                logger.info(f"Extended skeleton towards unreachable target")
                return joint_positions
            else:
                # If target is too close to base, extend horizontally
                logger.warning("Target too close to base, extending horizontally")
                joint_positions[0] = base_pos
                for i in range(len(bone_lengths)):
                    joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)

                self._validate_bone_lengths(joint_positions, original_bone_lengths)
                return joint_positions

        # --- FABRIK iterations ---
        for _ in range(self.iterations):
            # Forward pass (end effector to base)
            joint_positions[-1] = target_pos
            for i in range(len(joint_positions) - 2, -1, -1):
                direction = joint_positions[i] - joint_positions[i + 1]
                dist = QLineF(QPointF(0, 0), direction).length()

                # Enhanced numerical stability check with better epsilon handling
                if dist > 1e-6:  # Use larger epsilon for better stability
                    joint_positions[i] = (
                        joint_positions[i + 1] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Handle degenerate cases with more robust fallback
                    logger.debug(f"Degenerate case in forward pass at joint {i}, dist={dist}")
                    # Use previous direction if available
                    if i > 0 and i < len(joint_positions) - 1:
                        prev_direction = joint_positions[i - 1] - joint_positions[i + 1]
                        prev_dist = QLineF(QPointF(0, 0), prev_direction).length()
                        if prev_dist > 1e-6:
                            # Place joint along the line from prev to next
                            direction_normalized = prev_direction / prev_dist
                            joint_positions[i] = (
                                joint_positions[i + 1] + direction_normalized * bone_lengths[i]
                            )
                        else:
                            # Use horizontal fallback
                            joint_positions[i] = joint_positions[i + 1] + QPointF(bone_lengths[i], 0)
                    else:
                        # Use horizontal fallback for edge cases
                        joint_positions[i] = joint_positions[i + 1] + QPointF(bone_lengths[i], 0)

            # Backward pass (base to end effector)
            joint_positions[0] = base_pos
            for i in range(len(joint_positions) - 1):
                direction = joint_positions[i + 1] - joint_positions[i]
                dist = QLineF(QPointF(0, 0), direction).length()

                # Enhanced numerical stability check with better epsilon handling
                if dist > 1e-6:  # Use larger epsilon for better stability
                    joint_positions[i + 1] = (
                        joint_positions[i] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Handle degenerate cases with more robust fallback
                    logger.debug(f"Degenerate case in backward pass at joint {i}, dist={dist}")
                    # Use next direction if available
                    if i < len(joint_positions) - 2:
                        next_direction = joint_positions[i + 2] - joint_positions[i]
                        next_dist = QLineF(QPointF(0, 0), next_direction).length()
                        if next_dist > 1e-6:
                            # Place joint along the line from current to next+1
                            direction_normalized = next_direction / next_dist
                            # Scale to bone length
                            joint_positions[i + 1] = (
                                joint_positions[i] + direction_normalized * bone_lengths[i]
                            )
                        else:
                            # Use horizontal fallback
                            joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)
                    else:
                        # Use horizontal fallback for end cases
                        joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)

            # Check for convergence
            if QLineF(joint_positions[-1], target_pos).length() < self.tolerance:
                break

        # Apply bend direction constraints post-solving with enhanced stability
        if chain.bend_direction != 0 and len(joint_positions) > 2:
            logger.debug(f"Applying bend direction constraints: {chain.bend_direction}")
            for i in range(1, len(joint_positions) - 1):
                p0, p1, p2 = joint_positions[i - 1], joint_positions[i], joint_positions[i + 1]

                vec = p2 - p0
                vec_length = QLineF(QPointF(0, 0), vec).length()

                # Skip if the vector is too small (degenerate case)
                if vec_length < 1e-6:
                    logger.debug(f"Skipping bend constraint for joint {i}: degenerate vector")
                    continue

                mid_point = p0 + vec * 0.5

                # Perpendicular vector for bend direction with better numerical stability
                perp_vec = QPointF(-vec.y(), vec.x())
                perp_vec_length = QLineF(QPointF(0, 0), perp_vec).length()

                # Enhanced numerical stability check
                if perp_vec_length > 1e-6:
                    perp_vec = perp_vec / perp_vec_length
                else:
                    # Use default perpendicular direction based on context
                    if abs(vec.x()) > abs(vec.y()):
                        perp_vec = QPointF(0, 1 if vec.x() > 0 else -1)
                    else:
                        perp_vec = QPointF(1 if vec.y() > 0 else -1, 0)

                # Calculate bend offset with better numerical stability
                mid_dist = vec_length * 0.5
                bone_length = bone_lengths[i - 1]

                # Enhanced triangle height calculation
                if bone_length > mid_dist + 1e-6:  # Ensure we can form a triangle
                    bone_length_sq = bone_length ** 2
                    mid_dist_sq = mid_dist ** 2
                    h_sq = bone_length_sq - mid_dist_sq

                    if h_sq > 0:
                        h = math.sqrt(h_sq)
                        # Scale the bend by a reasonable factor to prevent extreme bends
                        h = min(h, bone_length * 0.5)  # Limit bend to reasonable amount

                        # Apply the offset in the determined bend direction
                        joint_positions[i] = mid_point + perp_vec * h * chain.bend_direction
                        logger.debug(f"Applied bend constraint to joint {i}, offset: {h:.3f}")
                    else:
                        logger.debug(f"Joint {i} at maximum extension, no bend applied")
                else:
                    logger.debug(f"Joint {i} cannot form triangle, bone too short")

        # Final validation to ensure bone lengths are preserved
        self._validate_bone_lengths(joint_positions, original_bone_lengths)

        # Return solved positions
        if not joint_positions:
            logger.error(f"FABRIK: Empty result - solving failed")

        return joint_positions

    def _validate_bone_lengths(self, joint_positions: list[QPointF], original_lengths: list[float]) -> None:
        """
        Validates and enforces that bone lengths remain constant after IK solving.
        This is critical for preserving skeleton integrity during animation.
        """
        corrections_made = False

        for i in range(len(original_lengths)):
            actual_length = QLineF(joint_positions[i], joint_positions[i + 1]).length()
            expected_length = original_lengths[i]

            # Use stricter tolerance for bone length preservation
            tolerance = max(1e-6, expected_length * 1e-6)  # Adaptive tolerance

            if abs(actual_length - expected_length) > tolerance:
                logger.debug(
                    f"Correcting bone {i}: expected={expected_length:.4f}, "
                    f"actual={actual_length:.4f}, diff={abs(actual_length - expected_length):.6f}"
                )

                corrections_made = True

                # Force correction to preserve skeleton length
                if actual_length > 1e-9:
                    direction = joint_positions[i + 1] - joint_positions[i]
                    direction_normalized = direction / actual_length
                    joint_positions[i + 1] = joint_positions[i] + direction_normalized * expected_length
                else:
                    # If bone is collapsed, extend it in the previous direction or default
                    if i > 0:
                        prev_direction = joint_positions[i] - joint_positions[i - 1]
                        prev_length = QLineF(QPointF(0, 0), prev_direction).length()
                        if prev_length > 1e-9:
                            direction_normalized = prev_direction / prev_length
                        else:
                            direction_normalized = QPointF(1, 0)  # Default direction
                    else:
                        direction_normalized = QPointF(1, 0)  # Default direction

                    joint_positions[i + 1] = joint_positions[i] + direction_normalized * expected_length

        if corrections_made:
            logger.info("Skeleton bone lengths corrected to preserve original lengths")


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
            min_length = 1e-3  # Increased minimum length for better stability
            if length < min_length:
                logger.warning(
                    f"Very small bone length {length:.6f} detected between joints "
                    f"{self.joints[i].id} and {self.joints[i+1].id}, using minimum length {min_length}"
                )
                length = min_length

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
