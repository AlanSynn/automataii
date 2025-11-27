"""
IK Solver Core - Core inverse kinematics solving algorithms.

Extracted from IKManager. Handles the mathematical IK calculations
without Qt dependencies where possible.

Design Pattern: Solver (pure algorithmic computation)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Point2D:
    """Immutable 2D point for IK calculations."""

    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        """Calculate distance to another point."""
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx * dx + dy * dy)

    def direction_to(self, other: Point2D) -> tuple[float, float]:
        """Get normalized direction vector to another point."""
        dist = self.distance_to(other)
        if dist < 1e-10:
            return (0.0, 1.0)
        return ((other.x - self.x) / dist, (other.y - self.y) / dist)


@dataclass
class IKSolution:
    """Result of an IK solve operation."""

    success: bool
    joint_positions: dict[str, Point2D]
    joint_angles: dict[str, float]
    error_message: str | None = None


class IKSolverCore:
    """
    Core IK solving algorithms.

    Responsibilities:
    - Solve single-bone IK (rotation only)
    - Solve two-bone IK (elbow/knee bending)
    - Calculate bone angles from positions

    Time Complexity:
    - Single bone: O(1)
    - Two bone: O(1)
    """

    # Bone length constraints (90%-110% of original)
    MIN_LENGTH_FACTOR = 0.9
    MAX_LENGTH_FACTOR = 1.1

    def __init__(self) -> None:
        """Initialize IK solver."""
        self._bend_directions: dict[str, float] = {}

    def set_bend_direction(self, joint_id: str, direction: float) -> None:
        """
        Set bend direction for a joint.

        Args:
            joint_id: Joint identifier
            direction: 1.0 for positive bend, -1.0 for negative
        """
        self._bend_directions[joint_id] = direction

    def get_bend_direction(self, joint_id: str) -> float:
        """Get bend direction for a joint (default: 1.0)."""
        return self._bend_directions.get(joint_id, 1.0)

    def solve_single_bone(
        self,
        anchor_pos: Point2D,
        target_pos: Point2D,
        original_length: float | None = None,
    ) -> IKSolution:
        """
        Solve single-bone IK (position constraint with length preservation).

        Args:
            anchor_pos: Fixed anchor point
            target_pos: Desired end position
            original_length: Original bone length (for constraint)

        Returns:
            IKSolution with final position

        Time Complexity: O(1)
        """
        dx = target_pos.x - anchor_pos.x
        dy = target_pos.y - anchor_pos.y
        current_distance = math.sqrt(dx * dx + dy * dy)

        if original_length and original_length > 0:
            min_length = original_length * self.MIN_LENGTH_FACTOR
            max_length = original_length * self.MAX_LENGTH_FACTOR

            if current_distance < min_length or current_distance > max_length:
                if current_distance > 1e-6:
                    clamped_length = max(min_length, min(max_length, current_distance))
                    direction_x = dx / current_distance
                    direction_y = dy / current_distance
                    final_x = anchor_pos.x + direction_x * clamped_length
                    final_y = anchor_pos.y + direction_y * clamped_length
                else:
                    final_x = anchor_pos.x
                    final_y = anchor_pos.y + original_length
            else:
                final_x = target_pos.x
                final_y = target_pos.y
        else:
            final_x = target_pos.x
            final_y = target_pos.y

        final_pos = Point2D(final_x, final_y)
        angle = math.atan2(dy, dx) if current_distance > 1e-6 else 0.0

        return IKSolution(
            success=True,
            joint_positions={"end": final_pos},
            joint_angles={"end": angle},
        )

    def solve_two_bone(
        self,
        root_pos: Point2D,
        target_pos: Point2D,
        length1: float,
        length2: float,
        bend_preference: float = 1.0,
    ) -> IKSolution:
        """
        Solve two-bone IK (elbow/knee style).

        Uses law of cosines to find middle joint position.

        Args:
            root_pos: Root/anchor position
            target_pos: Desired end effector position
            length1: First bone length
            length2: Second bone length
            bend_preference: 1.0 for one direction, -1.0 for opposite

        Returns:
            IKSolution with middle and end positions

        Time Complexity: O(1)
        """
        if length1 <= 0 or length2 <= 0:
            # Invalid lengths - return straight line fallback
            safe_l1 = length1 if length1 > 0 else 1.0
            safe_l2 = length2 if length2 > 0 else 1.0
            middle = Point2D(root_pos.x, root_pos.y + safe_l1)
            end = Point2D(middle.x, middle.y + safe_l2)
            return IKSolution(
                success=False,
                joint_positions={"middle": middle, "end": end},
                joint_angles={"middle": math.pi / 2, "end": math.pi / 2},
                error_message="Invalid bone lengths",
            )

        dx = target_pos.x - root_pos.x
        dy = target_pos.y - root_pos.y
        dist_sq = dx * dx + dy * dy
        dist = math.sqrt(dist_sq) if dist_sq > 1e-12 else 0.0

        # Total chain length constraints
        max_reach = length1 + length2
        min_reach = abs(length1 - length2)

        # Clamp target distance to reachable range
        clamped_dist = max(min_reach + 0.01, min(max_reach - 0.01, dist))

        if dist > 1e-6:
            # Calculate angle at root using law of cosines
            cos_angle1 = (length1 * length1 + clamped_dist * clamped_dist - length2 * length2) / (
                2 * length1 * clamped_dist
            )
            cos_angle1 = max(-1.0, min(1.0, cos_angle1))  # Clamp to valid range
            angle1 = math.acos(cos_angle1)

            # Base angle from root to target
            base_angle = math.atan2(dy, dx)

            # Apply bend direction preference
            if bend_preference < 0:
                angle1 = -angle1

            # Middle joint position
            middle_angle = base_angle + angle1
            middle_x = root_pos.x + length1 * math.cos(middle_angle)
            middle_y = root_pos.y + length1 * math.sin(middle_angle)
            middle = Point2D(middle_x, middle_y)

            # Recalculate end position (may differ from target if clamped)
            if clamped_dist < dist:
                # Target was out of reach, scale towards target
                scale = clamped_dist / dist
                end_x = root_pos.x + dx * scale
                end_y = root_pos.y + dy * scale
            else:
                end_x = target_pos.x
                end_y = target_pos.y
            end = Point2D(end_x, end_y)

            # Calculate angles
            angle_to_middle = math.atan2(middle_y - root_pos.y, middle_x - root_pos.x)
            angle_to_end = math.atan2(end_y - middle_y, end_x - middle_x)

        else:
            # Target at root - extend straight down
            middle = Point2D(root_pos.x, root_pos.y + length1)
            end = Point2D(middle.x, middle.y + length2)
            angle_to_middle = math.pi / 2
            angle_to_end = math.pi / 2

        return IKSolution(
            success=True,
            joint_positions={"middle": middle, "end": end},
            joint_angles={"middle": angle_to_middle, "end": angle_to_end},
        )

    def calculate_bone_angle(self, start: Point2D, end: Point2D) -> float:
        """
        Calculate angle of bone from start to end.

        Args:
            start: Start point
            end: End point

        Returns:
            Angle in radians

        Time Complexity: O(1)
        """
        dx = end.x - start.x
        dy = end.y - start.y
        return math.atan2(dy, dx)

    def calculate_chain_lengths(
        self, positions: list[Point2D]
    ) -> list[float]:
        """
        Calculate bone lengths for a chain of positions.

        Args:
            positions: List of joint positions in order

        Returns:
            List of bone lengths

        Time Complexity: O(n) where n = number of positions
        """
        lengths = []
        for i in range(len(positions) - 1):
            length = positions[i].distance_to(positions[i + 1])
            lengths.append(length)
        return lengths
