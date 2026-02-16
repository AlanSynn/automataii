"""
Joint Mapping Service - Domain Layer

Pure business logic for mapping body parts to skeleton joints.
No dependencies on presentation layer (Qt) or infrastructure.

Design Pattern: Domain Service (DDD)
Architecture: Hexagonal - Domain Core
"""

from __future__ import annotations

from typing import Any


class JointMappingService:
    """
    Maps body parts to their corresponding skeleton joints for mechanism control.

    This is pure domain logic - no Qt dependencies.

    Responsibilities:
    - Determine target joint (end effector) for a body part
    - Standardize joint IDs across different naming conventions
    - Find character position from skeleton data
    """

    # Fallback mapping for parts without joint definitions
    PART_TO_TARGET_JOINT = {
        # Arms - target should be hands (end effectors)
        "left_arm_upper": "left_elbow",
        "left_arm_lower": "left_hand",
        "right_arm_upper": "right_elbow",
        "right_arm_lower": "right_hand",
        # Legs - target should be feet (end effectors)
        "left_leg_upper": "left_knee",
        "left_leg_lower": "left_foot",
        "right_leg_upper": "right_knee",
        "right_leg_lower": "right_foot",
        # Special cases
        "head": "neck",
        "torso": "torso",
    }

    # Standard joint ID mappings
    JOINT_STANDARDIZATION = {
        "left_wrist": "left_hand",
        "right_wrist": "right_hand",
        "left_ankle": "left_foot",
        "right_ankle": "right_foot",
        "spine": "torso",
        "pelvis": "torso",
        "hips": "torso",
    }

    def __init__(self, body_parts_registry: dict[str, Any] | None = None) -> None:
        """
        Initialize with optional body parts registry.

        Args:
            body_parts_registry: Registry of body part definitions with joints
        """
        self._body_parts = body_parts_registry or {}
        # Caching for performance
        self._cached_foot_joints: list[str] | None = None
        self._last_skeleton_keys: frozenset[str] | None = None

    def set_body_parts_registry(self, registry: dict[str, Any]) -> None:
        """Update body parts registry."""
        self._body_parts = registry

    def get_target_joint(self, part_name: str, anchor_joint_id: str) -> str:
        """
        Get the correct target joint (end effector) for mechanism control.

        ALL PARTS ARE END EFFECTORS - every part should control its furthest joint.

        Args:
            part_name: Name of the body part
            anchor_joint_id: Fallback anchor joint ID

        Returns:
            The target joint ID for mechanism control
        """
        # CRITICAL: Always use neck for head mechanism control
        if part_name == "head":
            return "neck"

        # Check if this part has joint definitions
        part_definition = self._body_parts.get(part_name, {})
        part_joints = part_definition.get("joints", [])

        # All parts are end effectors
        # Every part should control its FURTHEST joint (last in the joint chain)
        if part_joints and len(part_joints) > 0:
            return part_joints[-1]

        # Fallback mapping
        return self.PART_TO_TARGET_JOINT.get(part_name, anchor_joint_id)

    def standardize_joint_id(self, abstract_joint_id: str) -> str | None:
        """
        Convert abstract joint IDs to standardized skeleton joint names.

        Args:
            abstract_joint_id: Abstract or alias joint ID

        Returns:
            Standardized joint ID, or None if no mapping exists
        """
        # Check direct standardization
        if abstract_joint_id in self.JOINT_STANDARDIZATION:
            return self.JOINT_STANDARDIZATION[abstract_joint_id]

        # Already a standard ID
        return abstract_joint_id

    def get_character_ground_position(
        self,
        skeleton_data: dict[str, Any] | None,
        offset_y: float = 50.0,
    ) -> tuple[float, float]:
        """
        Get the character's ground position for mechanism placement.

        Finds the lowest point (feet) and returns position below it.

        Args:
            skeleton_data: Skeleton joint data with positions
            offset_y: Vertical offset below feet (positive = down in Qt coords)

        Returns:
            Tuple of (x, y) position for mechanism placement
        """
        default_position = (300.0, 400.0)

        if not skeleton_data:
            return default_position

        joints = skeleton_data.get("joints", {})
        if not joints:
            return default_position

        # Optimization: Cache foot joint identification
        current_keys = frozenset(joints.keys())
        if self._last_skeleton_keys != current_keys:
            self._cached_foot_joints = []
            self._last_skeleton_keys = current_keys

            # Identify foot joints once
            for joint_id in joints.keys():
                if "foot" in joint_id.lower() or "ankle" in joint_id.lower():
                    self._cached_foot_joints.append(joint_id)

        # Use cached identification
        foot_joints: list[tuple[float, float]] = []
        lowest_y = float("-inf")

        # Fast pass for identified foot joints
        if self._cached_foot_joints:
            for joint_id in self._cached_foot_joints:
                if joint_id in joints:
                    pos = joints[joint_id].get("position", [0, 0])
                    foot_joints.append((pos[0], pos[1]))

        # Track lowest Y (still need to scan all for ground truth if no specific foot joints found)
        # But if we have identified feet, we can skip full scan or just use feet
        if not foot_joints:
            for joint_id, joint_data in joints.items():
                pos = joint_data.get("position", [0, 0])
                if pos[1] > lowest_y:
                    lowest_y = pos[1]

        # If we found foot joints using cache, calculate average
        if foot_joints:
            avg_x = sum(pos[0] for pos in foot_joints) / len(foot_joints)
            avg_y = sum(pos[1] for pos in foot_joints) / len(foot_joints)
            return (avg_x, avg_y + offset_y)

        # Otherwise, find the lowest joints (legacy fallback)
        lowest_joints: list[tuple[float, float]] = []
        for _joint_id, joint_data in joints.items():
            pos = joint_data.get("position", [0, 0])
            # Consider joints near the lowest position as feet
            if abs(pos[1] - lowest_y) < 20:
                lowest_joints.append((pos[0], pos[1]))

        if lowest_joints:
            avg_x = sum(pos[0] for pos in lowest_joints) / len(lowest_joints)
            return (avg_x, lowest_y + offset_y)

        return default_position


# Singleton instance for convenience
_default_service: JointMappingService | None = None


def get_joint_mapping_service() -> JointMappingService:
    """Get or create the default joint mapping service."""
    global _default_service
    if _default_service is None:
        _default_service = JointMappingService()
    return _default_service
