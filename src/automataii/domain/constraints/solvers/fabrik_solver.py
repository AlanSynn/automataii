"""
FABRIK Solver Implementation

Wraps the existing FABRIK IK solver to work with the unified constraint framework.
"""

from typing import List
import numpy as np
from PyQt6.QtCore import QPointF, QLineF

from ..base import BaseSolver, BaseConstraint, ConstraintViolationError, ConstraintType


class FABRIKSolver(BaseSolver):
    """
    FABRIK (Forward And Backward Reaching Inverse Kinematics) solver.
    
    This is a specialized solver for IK constraints that uses the FABRIK algorithm.
    It's particularly efficient for kinematic chains without loops.
    """
    
    def __init__(self, max_iterations: int = 15, tolerance: float = 1.0):
        """
        Initialize FABRIK solver.
        
        Args:
            max_iterations: Maximum FABRIK iterations
            tolerance: Position tolerance in pixels/mm
        """
        super().__init__("FABRIK", max_iterations, tolerance)
    
    def solve(self, constraints: List[BaseConstraint], initial_state: np.ndarray, **kwargs) -> np.ndarray:
        """
        Solve IK constraints using FABRIK algorithm.
        
        Args:
            constraints: List of constraints (only IKConstraints are handled)
            initial_state: Initial joint positions
            **kwargs: Additional parameters:
                - target_pos: Target end-effector position (QPointF)
                - bone_lengths: Array of bone lengths
                - base_pos: Base position (QPointF)
                
        Returns:
            Updated joint positions
        """
        self.total_solves += 1
        
        # Extract IK constraints
        ik_constraints = [c for c in constraints if c.constraint_type == ConstraintType.IK and c.enabled]
        
        if not ik_constraints:
            self.logger.warning("No IK constraints provided to FABRIK solver")
            self.last_iterations = 0
            return initial_state
        
        # For now, handle single IK constraint (can be extended for multiple chains)
        if len(ik_constraints) > 1:
            self.logger.warning("FABRIK solver currently handles only one IK constraint, using first one")
        
        ik_constraint = ik_constraints[0]
        
        # Extract parameters from kwargs or constraint
        target_pos = kwargs.get('target_pos')
        bone_lengths = kwargs.get('bone_lengths')
        base_pos = kwargs.get('base_pos')
        
        if target_pos is None or bone_lengths is None:
            self.logger.error("FABRIK solver requires target_pos and bone_lengths")
            raise ConstraintViolationError("FABRIK_params", 1.0, "Missing required parameters")
        
        # Convert initial state to joint positions
        if len(initial_state) % 2 != 0:
            self.logger.error("Initial state must contain even number of elements (x,y pairs)")
            raise ConstraintViolationError("FABRIK_state", 1.0, "Invalid state format")
        
        num_joints = len(initial_state) // 2
        joint_positions = []
        for i in range(num_joints):
            x = initial_state[2*i]
            y = initial_state[2*i + 1]
            joint_positions.append(QPointF(x, y))
        
        if base_pos is None:
            base_pos = joint_positions[0] if joint_positions else QPointF(0, 0)
        
        # Validate bone lengths
        if len(bone_lengths) != num_joints - 1:
            self.logger.error(f"Bone lengths ({len(bone_lengths)}) must match joints-1 ({num_joints-1})")
            raise ConstraintViolationError("FABRIK_bones", 1.0, "Mismatched bone lengths")
        
        total_length = sum(bone_lengths)
        
        # Check reachability and clamp target if necessary
        target_distance = QLineF(base_pos, target_pos).length()
        if target_distance > total_length:
            direction = target_pos - base_pos
            direction_length = QLineF(QPointF(0, 0), direction).length()
            
            if direction_length > 1e-9:
                normalized_direction = direction / direction_length
                target_pos = base_pos + normalized_direction * total_length
            else:
                target_pos = base_pos + QPointF(total_length, 0)
        
        # FABRIK iterations
        for iteration in range(self.max_iterations):
            # Forward pass (end effector to base)
            joint_positions[-1] = target_pos
            for i in range(len(joint_positions) - 2, -1, -1):
                direction = joint_positions[i] - joint_positions[i + 1]
                dist = QLineF(QPointF(0, 0), direction).length()
                
                if dist > 1e-9:
                    joint_positions[i] = (
                        joint_positions[i + 1] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Handle degenerate case
                    if i > 0:
                        prev_direction = joint_positions[i - 1] - joint_positions[i]
                        prev_dist = QLineF(QPointF(0, 0), prev_direction).length()
                        if prev_dist > 1e-9:
                            joint_positions[i] = (
                                joint_positions[i + 1] + (prev_direction / prev_dist) * bone_lengths[i]
                            )
                        else:
                            joint_positions[i] = joint_positions[i + 1] + QPointF(bone_lengths[i], 0)
                    else:
                        joint_positions[i] = joint_positions[i + 1] + QPointF(bone_lengths[i], 0)
            
            # Backward pass (base to end effector)
            joint_positions[0] = base_pos
            for i in range(len(joint_positions) - 1):
                direction = joint_positions[i + 1] - joint_positions[i]
                dist = QLineF(QPointF(0, 0), direction).length()
                
                if dist > 1e-9:
                    joint_positions[i + 1] = (
                        joint_positions[i] + (direction / dist) * bone_lengths[i]
                    )
                else:
                    # Handle degenerate case
                    if i < len(joint_positions) - 2:
                        next_direction = joint_positions[i + 2] - joint_positions[i + 1]
                        next_dist = QLineF(QPointF(0, 0), next_direction).length()
                        if next_dist > 1e-9:
                            joint_positions[i + 1] = (
                                joint_positions[i] + (next_direction / next_dist) * bone_lengths[i]
                            )
                        else:
                            joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)
                    else:
                        joint_positions[i + 1] = joint_positions[i] + QPointF(bone_lengths[i], 0)
            
            # Check convergence
            end_effector_pos = joint_positions[-1]
            distance_to_target = QLineF(end_effector_pos, target_pos).length()
            
            if distance_to_target < self.tolerance:
                self.last_iterations = iteration + 1
                break
        else:
            self.last_iterations = self.max_iterations
        
        # Convert back to state vector
        final_state = np.zeros(len(initial_state))
        for i, pos in enumerate(joint_positions):
            final_state[2*i] = pos.x()
            final_state[2*i + 1] = pos.y()
        
        # Check if constraints are satisfied
        if self.check_convergence(constraints, final_state):
            self.successful_solves += 1
        else:
            # Still return best attempt
            final_distance = QLineF(joint_positions[-1], target_pos).length()
            self.logger.warning(f"FABRIK did not converge, final distance: {final_distance:.3f}")
        
        return final_state
    
    def solve_simple_ik(self, target_pos: QPointF, joint_positions: List[QPointF], 
                       bone_lengths: List[float], base_pos: QPointF = None) -> List[QPointF]:
        """
        Simplified interface for direct FABRIK solving.
        
        Args:
            target_pos: Target end-effector position
            joint_positions: Current joint positions
            bone_lengths: Length of each bone
            base_pos: Base position (defaults to first joint)
            
        Returns:
            Updated joint positions
        """
        if not joint_positions:
            return []
        
        if base_pos is None:
            base_pos = joint_positions[0]
        
        # Convert to state vector
        state = np.zeros(len(joint_positions) * 2)
        for i, pos in enumerate(joint_positions):
            state[2*i] = pos.x()
            state[2*i + 1] = pos.y()
        
        # Create dummy constraint for compatibility
        from ..constraints import IKConstraint
        dummy_constraint = IKConstraint("dummy_ik", target_pos, base_pos)
        
        # Solve
        final_state = self.solve(
            [dummy_constraint],
            state,
            target_pos=target_pos,
            bone_lengths=bone_lengths,
            base_pos=base_pos
        )
        
        # Convert back to joint positions
        final_positions = []
        for i in range(len(joint_positions)):
            x = final_state[2*i]
            y = final_state[2*i + 1]
            final_positions.append(QPointF(x, y))
        
        return final_positions