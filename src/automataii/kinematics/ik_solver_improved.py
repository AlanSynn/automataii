import logging
import math
from typing import List, Dict
from PyQt6.QtCore import QPointF, QLineF

from automataii.core.models_skeleton import StandardizedJointModel

logger = logging.getLogger(__name__)

class IKSolver:
    """
    An abstract base class for different IK solving algorithms.
    """
    def solve(self, chain: 'IKChain', target_pos: QPointF) -> List[QPointF]:
        raise NotImplementedError

class FABRIKSolver(IKSolver):
    """
    Implements the FABRIK (Forward And Backward Reaching Inverse Kinematics) algorithm
    with constraints for natural limb bending.
    """
    def __init__(self, iterations: int = 15, tolerance: float = 1.0):
        self.iterations = iterations
        self.tolerance = tolerance

    def solve(self, chain: 'IKChain', target_pos: QPointF) -> List[QPointF]:
        """Solves the IK for the given chain and target position."""
        if not chain.joints or len(chain.joints) < 2:
            return []

        joint_positions = chain.get_joint_positions()
        base_pos = joint_positions[0]
        bone_lengths = chain.bone_lengths
        total_length = sum(bone_lengths)

        # Check reachability and clamp target if necessary
        target_distance = QLineF(base_pos, target_pos).length()
        if target_distance > total_length:
            direction = (target_pos - base_pos)
            if direction.manhattanLength() > 0:
                # Normalize the direction vector
                normalized_direction = direction / QLineF(QPointF(0, 0), direction).length()
                target_pos = base_pos + normalized_direction * total_length

        # --- FABRIK iterations ---
        for _ in range(self.iterations):
            # Forward pass (end effector to base)
            joint_positions[-1] = target_pos
            for i in range(len(joint_positions) - 2, -1, -1):
                direction = (joint_positions[i] - joint_positions[i+1])
                dist = QLineF(QPointF(0,0), direction).length()
                if dist > 1e-6:
                    joint_positions[i] = joint_positions[i+1] + (direction / dist) * bone_lengths[i]

            # Backward pass (base to end effector)
            joint_positions[0] = base_pos
            for i in range(len(joint_positions) - 1):
                direction = (joint_positions[i+1] - joint_positions[i])
                dist = QLineF(QPointF(0,0), direction).length()
                if dist > 1e-6:
                    joint_positions[i+1] = joint_positions[i] + (direction / dist) * bone_lengths[i]

            # Check for convergence
            if QLineF(joint_positions[-1], target_pos).length() < self.tolerance:
                break
        
        # Apply bend direction constraints post-solving
        if chain.bend_direction != 0 and len(joint_positions) > 2:
            for i in range(1, len(joint_positions) - 1):
                p0, p1, p2 = joint_positions[i-1], joint_positions[i], joint_positions[i+1]
                
                vec = p2 - p0
                if vec.manhattanLength() == 0: continue

                mid_point = p0 + vec * 0.5
                
                # Perpendicular vector for bend direction
                perp_vec = QPointF(-vec.y(), vec.x())
                if perp_vec.manhattanLength() > 0:
                    perp_vec = perp_vec / QLineF(QPointF(0,0), perp_vec).length()

                # Height of the triangle (distance from midpoint to the middle joint)
                h = math.sqrt(max(0, bone_lengths[i-1]**2 - (QLineF(p0, mid_point).length())**2))

                # Apply the offset in the determined bend direction
                joint_positions[i] = mid_point + perp_vec * h * chain.bend_direction

        return joint_positions

class IKChain:
    """
    Represents a single kinematic chain (e.g., an arm or a leg),
    holding the joints in order and their properties.
    """
    def __init__(self, joints: List[StandardizedJointModel]):
        # Joints are assumed to be passed in order from root to effector
        self.joints: List[StandardizedJointModel] = joints
        self.bone_lengths: List[float] = self._calculate_bone_lengths()
        self.bend_direction: int = self._infer_bend_direction()

    def _calculate_bone_lengths(self) -> List[float]:
        """Calculates the length of each bone in the chain."""
        lengths = []
        for i in range(len(self.joints) - 1):
            p1 = self.joints[i].position
            p2 = self.joints[i+1].position
            lengths.append(QLineF(p1, p2).length())
        return lengths

    def _infer_bend_direction(self) -> int:
        """
        Infers the natural bend direction (e.g., for an elbow or knee)
        from the initial pose of the chain.
        Returns +1 for one side, -1 for the other, or 0 if straight/not applicable.
        """
        if len(self.joints) < 3:
            return 0 # Not applicable for 2-joint chains

        p0 = self.joints[0].position
        p1 = self.joints[1].position
        p2 = self.joints[2].position

        # Using the 2D cross-product of (p1-p0) and (p2-p1) to determine the side
        cross_product = (p1.x() - p0.x()) * (p2.y() - p1.y()) - (p1.y() - p0.y()) * (p2.x() - p1.x())
        
        # Invert the sign for Qt's Y-down coordinate system to get intuitive bend directions
        if cross_product > 1e-6: # Threshold to avoid floating point issues
            return -1 # e.g., Left bend
        elif cross_product < -1e-6:
            return 1  # e.g., Right bend
        return 0 # Straight
        
    def get_joint_positions(self) -> List[QPointF]:
        """Returns a list of the current positions of the joints in the chain."""
        return [j.position for j in self.joints]