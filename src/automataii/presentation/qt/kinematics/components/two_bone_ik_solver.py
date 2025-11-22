"""
Two-Bone IK Solver - Analytical 2-bone IK for arms and legs.

Extracted from IKManager. Handles geometric calculations for 2-bone
IK chains (shoulder-elbow-hand, hip-knee-foot).

Design Pattern: Solver (pure geometric calculation)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF


@dataclass(frozen=True)
class TwoBoneIKConfig:
    """Configuration for two-bone IK solving."""

    max_elbow_flexion_deg: float = 160.0
    epsilon_dist: float = 1.0
    near_max_reach_threshold: float = 5.0
    near_min_reach_threshold: float = 5.0


@dataclass
class TwoBoneIKResult:
    """Result of two-bone IK solving."""

    middle_pos: QPointF
    end_pos: QPointF


class TwoBoneIKSolver:
    """
    Solves two-bone IK for arm and leg chains.

    Responsibilities:
    - Calculate middle joint (elbow/knee) position
    - Calculate end effector (hand/foot) position
    - Respect bend direction constraints
    - Handle reach limits (min/max extension)

    Time Complexity: O(1) - geometric calculation
    """

    def __init__(self, config: TwoBoneIKConfig | None = None) -> None:
        """Initialize solver with configuration."""
        self._config = config or TwoBoneIKConfig()
        self._rest_angles: dict[str, float] = {
            "left_shoulder": 180.0,
            "right_shoulder": 0.0,
            "left_hip": -90.0,
            "right_hip": -90.0,
        }

    def set_rest_angles(self, rest_angles: dict[str, float]) -> None:
        """Set rest angles for root joints."""
        self._rest_angles = rest_angles

    def solve(
        self,
        root_pos: QPointF,
        target_pos: QPointF,
        length1: float,
        length2: float,
        bend_direction: float = 1.0,
        root_joint_id: str = "",
    ) -> TwoBoneIKResult | None:
        """
        Solve 2-bone IK for given root, target, and bone lengths.

        Args:
            root_pos: Position of root joint (shoulder/hip)
            target_pos: Target position for end effector (hand/foot)
            length1: Length of first bone (upper arm/leg)
            length2: Length of second bone (lower arm/leg)
            bend_direction: Direction of bend (-1 or 1)
            root_joint_id: ID of root joint for rest angle lookup

        Returns:
            TwoBoneIKResult with middle and end positions, or None if unsolvable

        Time Complexity: O(1)
        """
        p0 = root_pos
        target = target_pos
        l1 = length1
        l2 = length2

        # Validate bone lengths
        if l1 <= 0 or l2 <= 0:
            safe_l1 = l1 if l1 > 0 else 1.0
            safe_l2 = l2 if l2 > 0 else 1.0
            p1_bail = QPointF(p0.x(), p0.y() + safe_l1)
            p2_bail = QPointF(p1_bail.x(), p1_bail.y() + safe_l2)
            return TwoBoneIKResult(middle_pos=p1_bail, end_pos=p2_bail)

        # Calculate distance to target
        dx = target.x() - p0.x()
        dy = target.y() - p0.y()
        dist_sq = dx * dx + dy * dy
        dist = math.sqrt(dist_sq) if dist_sq > 1e-12 else 0.0

        # Calculate elbow constraints
        min_elbow_internal_angle_rad = math.pi - math.radians(
            self._config.max_elbow_flexion_deg
        )
        min_elbow_internal_angle_rad = max(
            0.0, min(math.pi, min_elbow_internal_angle_rad)
        )

        cos_min_elbow_angle = math.cos(min_elbow_internal_angle_rad)
        d_min_sq_with_limit = l1 * l1 + l2 * l2 - 2 * l1 * l2 * cos_min_elbow_angle
        if d_min_sq_with_limit < 0:
            d_min_sq_with_limit = 0
        d_min_with_limit = math.sqrt(d_min_sq_with_limit)

        # Case 1: Target too close (collapsed)
        if dist < self._config.epsilon_dist:
            return self._solve_collapsed_case(
                p0,
                l1,
                l2,
                bend_direction,
                min_elbow_internal_angle_rad,
                root_joint_id,
            )

        # Case 2: Target at or beyond max reach
        if dist >= (l1 + l2 - self._config.near_max_reach_threshold):
            return self._solve_stretched_case(p0, l1, l2, dx, dy)

        # Case 3: Target near minimum reach (highly bent)
        if dist < (d_min_with_limit + self._config.near_min_reach_threshold):
            return self._solve_near_min_case(
                p0,
                l1,
                l2,
                dx,
                dy,
                d_min_with_limit,
                bend_direction,
                min_elbow_internal_angle_rad,
                root_joint_id,
            )

        # Case 4: Normal case - within reachable range
        return self._solve_normal_case(
            p0, l1, l2, dx, dy, dist, dist_sq, bend_direction, min_elbow_internal_angle_rad
        )

    def _solve_collapsed_case(
        self,
        p0: QPointF,
        l1: float,
        l2: float,
        bend_direction: float,
        min_elbow_angle_rad: float,
        root_joint_id: str,
    ) -> TwoBoneIKResult:
        """Solve for collapsed position (target too close)."""
        base_angle_rad = math.radians(self._rest_angles.get(root_joint_id, 90.0))

        p1_x = p0.x() + l1 * math.cos(base_angle_rad)
        p1_y = p0.y() + l1 * math.sin(base_angle_rad)
        p1_new = QPointF(p1_x, p1_y)

        angle_of_bone2 = base_angle_rad + bend_direction * (math.pi - min_elbow_angle_rad)
        p2_x = p1_new.x() + l2 * math.cos(angle_of_bone2)
        p2_y = p1_new.y() + l2 * math.sin(angle_of_bone2)
        p2_new = QPointF(p2_x, p2_y)

        return TwoBoneIKResult(middle_pos=p1_new, end_pos=p2_new)

    def _solve_stretched_case(
        self, p0: QPointF, l1: float, l2: float, dx: float, dy: float
    ) -> TwoBoneIKResult:
        """Solve for stretched position (at max reach)."""
        angle_root_to_target = math.atan2(dy, dx)

        p1_x = p0.x() + l1 * math.cos(angle_root_to_target)
        p1_y = p0.y() + l1 * math.sin(angle_root_to_target)
        p1_new = QPointF(p1_x, p1_y)

        p2_x = p1_new.x() + l2 * math.cos(angle_root_to_target)
        p2_y = p1_new.y() + l2 * math.sin(angle_root_to_target)
        p2_new = QPointF(p2_x, p2_y)

        return TwoBoneIKResult(middle_pos=p1_new, end_pos=p2_new)

    def _solve_near_min_case(
        self,
        p0: QPointF,
        l1: float,
        l2: float,
        dx: float,
        dy: float,
        d_min_with_limit: float,
        bend_direction: float,
        min_elbow_angle_rad: float,
        root_joint_id: str,
    ) -> TwoBoneIKResult:
        """Solve for near-minimum reach (highly bent)."""
        angle_root_to_target = math.atan2(dy, dx)
        dist_eff = d_min_with_limit

        if dist_eff < self._config.epsilon_dist:
            return self._solve_collapsed_case(
                p0, l1, l2, bend_direction, min_elbow_angle_rad, root_joint_id
            )

        cos_alpha_eff_numerator = dist_eff * dist_eff + l1 * l1 - l2 * l2
        cos_alpha_eff_denominator = 2 * dist_eff * l1

        if abs(cos_alpha_eff_denominator) < 1e-9:
            p1_x_f = p0.x() + l1 * math.cos(angle_root_to_target)
            p1_y_f = p0.y() + l1 * math.sin(angle_root_to_target)
            p1_new_f = QPointF(p1_x_f, p1_y_f)

            angle_bone2_world_f = angle_root_to_target + bend_direction * (
                math.pi - min_elbow_angle_rad
            )
            p2_x_f = p1_new_f.x() + l2 * math.cos(angle_bone2_world_f)
            p2_y_f = p1_new_f.y() + l2 * math.sin(angle_bone2_world_f)
            p2_new_f = QPointF(p2_x_f, p2_y_f)

            return TwoBoneIKResult(middle_pos=p1_new_f, end_pos=p2_new_f)

        cos_alpha_eff = cos_alpha_eff_numerator / cos_alpha_eff_denominator
        cos_alpha_eff = max(-1.0, min(1.0, cos_alpha_eff))
        alpha_eff_rad = math.acos(cos_alpha_eff)

        angle1_final_rad = angle_root_to_target - (bend_direction * alpha_eff_rad)

        p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
        p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
        p1_new = QPointF(p1_x, p1_y)

        angle_elbow_bend = bend_direction * (math.pi - min_elbow_angle_rad)
        p2_x = p1_new.x() + l2 * math.cos(angle1_final_rad + angle_elbow_bend)
        p2_y = p1_new.y() + l2 * math.sin(angle1_final_rad + angle_elbow_bend)
        p2_new = QPointF(p2_x, p2_y)

        return TwoBoneIKResult(middle_pos=p1_new, end_pos=p2_new)

    def _solve_normal_case(
        self,
        p0: QPointF,
        l1: float,
        l2: float,
        dx: float,
        dy: float,
        dist: float,
        dist_sq: float,
        bend_direction: float,
        min_elbow_angle_rad: float,
    ) -> TwoBoneIKResult:
        """Solve for normal reachable case."""
        l1_sq = l1 * l1
        l2_sq = l2 * l2

        # Calculate elbow angle using law of cosines
        cos_angle2_numerator = l1_sq + l2_sq - dist_sq
        cos_angle2_denominator = 2 * l1 * l2

        if abs(cos_angle2_denominator) < 1e-9:
            angle_root_to_target_s = math.atan2(dy, dx)
            p1_x_s = p0.x() + l1 * math.cos(angle_root_to_target_s)
            p1_y_s = p0.y() + l1 * math.sin(angle_root_to_target_s)
            p1_new_s = QPointF(p1_x_s, p1_y_s)

            p2_x_s = p1_new_s.x() + l2 * math.cos(angle_root_to_target_s)
            p2_y_s = p1_new_s.y() + l2 * math.sin(angle_root_to_target_s)
            p2_new_s = QPointF(p2_x_s, p2_y_s)

            return TwoBoneIKResult(middle_pos=p1_new_s, end_pos=p2_new_s)

        cos_angle2 = cos_angle2_numerator / cos_angle2_denominator
        cos_angle2 = max(-1.0, min(1.0, cos_angle2))
        angle2_triangle_rad = math.acos(cos_angle2)

        # Apply minimum elbow angle constraint
        angle2_triangle_rad = max(angle2_triangle_rad, min_elbow_angle_rad)

        # Calculate shoulder angle
        cos_alpha_numerator = dist_sq + l1_sq - l2_sq
        cos_alpha_denominator = 2 * dist * l1

        if abs(cos_alpha_denominator) < 1e-9:
            angle_root_to_target_s2 = math.atan2(dy, dx)
            p1_x_s2 = p0.x() + l1 * math.cos(angle_root_to_target_s2)
            p1_y_s2 = p0.y() + l1 * math.sin(angle_root_to_target_s2)
            p1_new_s2 = QPointF(p1_x_s2, p1_y_s2)

            angle_bone2_world_s2 = angle_root_to_target_s2 + bend_direction * (
                math.pi - angle2_triangle_rad
            )
            p2_x_s2 = p1_new_s2.x() + l2 * math.cos(angle_bone2_world_s2)
            p2_y_s2 = p1_new_s2.y() + l2 * math.sin(angle_bone2_world_s2)
            p2_new_s2 = QPointF(p2_x_s2, p2_y_s2)

            return TwoBoneIKResult(middle_pos=p1_new_s2, end_pos=p2_new_s2)

        cos_alpha = cos_alpha_numerator / cos_alpha_denominator
        cos_alpha = max(-1.0, min(1.0, cos_alpha))
        alpha_rad = math.acos(cos_alpha)

        angle_root_to_target_rad = math.atan2(dy, dx)
        angle1_final_rad = angle_root_to_target_rad - (bend_direction * alpha_rad)

        p1_x = p0.x() + l1 * math.cos(angle1_final_rad)
        p1_y = p0.y() + l1 * math.sin(angle1_final_rad)
        p1_new = QPointF(p1_x, p1_y)

        angle_elbow_bend = bend_direction * (math.pi - angle2_triangle_rad)
        p2_x = p1_new.x() + l2 * math.cos(angle1_final_rad + angle_elbow_bend)
        p2_y = p1_new.y() + l2 * math.sin(angle1_final_rad + angle_elbow_bend)
        p2_new = QPointF(p2_x, p2_y)

        return TwoBoneIKResult(middle_pos=p1_new, end_pos=p2_new)
