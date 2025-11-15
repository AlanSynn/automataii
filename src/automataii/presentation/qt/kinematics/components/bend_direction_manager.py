"""
BendDirectionManager - Extracted from IKManager god class.

Handles bend direction calculation, storage, and retrieval for IK limbs.
Bend directions determine which way joints (elbows, knees) bend during IK solving.

This is a presentation-layer component due to Qt type dependencies (QPointF).
"""

import logging
from typing import Any, Protocol

from PyQt6.QtCore import QPointF

logger = logging.getLogger(__name__)


class SkeletonDataProvider(Protocol):
    """Protocol for accessing skeleton data (avoids circular imports)."""

    def get_joint_data(self, joint_id: str) -> dict[str, Any] | None:
        """Get data for a joint by ID."""
        ...

    def get_hierarchy(self) -> dict[str, list[str]]:
        """Get the skeleton hierarchy as parent -> children mapping."""
        ...

    def get_standardized_joint_id(self, abstract_name: str) -> str | None:
        """Convert abstract joint name to standardized ID."""
        ...


class BendDirectionManager:
    """
    Manages bend directions for IK joints (elbows, knees).

    Bend direction (+1 or -1) determines which way a joint bends
    when solving inverse kinematics. This is critical for natural
    arm/leg poses.

    Responsibilities:
    - Store bend directions for each middle joint
    - Calculate default bend directions from geometry
    - Sync with skeleton data (SkeletonManager)
    - Provide bend direction lookups for IK solvers
    """

    # Middle joints that have bend directions
    MIDDLE_JOINTS = ("left_elbow", "right_elbow", "left_knee", "right_knee")

    # Hardcoded mapping for when hierarchy lookup fails
    ROOT_TO_MIDDLE_MAPPING = {
        "left_shoulder": "left_elbow",
        "right_shoulder": "right_elbow",
        "left_hip": "left_knee",
        "right_hip": "right_knee",
        # Common standardized ID formats
        "left_shoulder_7": "left_elbow_8",
        "right_shoulder_4": "right_elbow_5",
        "left_hip_13": "left_knee_14",
        "right_hip_10": "right_knee_11",
    }

    def __init__(self) -> None:
        # Map from joint ID (standardized or abstract) -> bend direction (+1 or -1)
        self._bend_directions: dict[str, int] = {}

    @property
    def directions(self) -> dict[str, int]:
        """Get all bend directions as a copy."""
        return self._bend_directions.copy()

    def get(self, joint_id: str) -> int:
        """
        Get bend direction for a joint.

        Args:
            joint_id: Joint ID (standardized like 'left_elbow_8' or abstract like 'left_elbow')

        Returns:
            +1 or -1 for bend direction, defaults to +1 if not found
        """
        if joint_id in self._bend_directions:
            return self._bend_directions[joint_id]

        # Try abstract name extraction for standardized IDs
        if '_' in joint_id and joint_id.split('_')[-1].isdigit():
            abstract_name = '_'.join(joint_id.split('_')[:-1])
            if abstract_name in self._bend_directions:
                return self._bend_directions[abstract_name]

        return 1  # Default

    def set(self, joint_id: str, direction: int) -> None:
        """
        Set bend direction for a joint.

        Args:
            joint_id: Joint ID (standardized or abstract)
            direction: +1 or -1
        """
        normalized = 1 if direction >= 0 else -1
        self._bend_directions[joint_id] = normalized

        # Also store with alternative form for compatibility
        if '_' in joint_id and joint_id.split('_')[-1].isdigit():
            abstract_name = '_'.join(joint_id.split('_')[:-1])
            self._bend_directions[abstract_name] = normalized

    def clear(self) -> None:
        """Clear all bend directions."""
        self._bend_directions.clear()

    def get_for_root_joint(
        self,
        root_joint_std_id: str,
        hierarchy: dict[str, list[str]] | None = None
    ) -> float:
        """
        Get bend direction for a limb based on its root joint.

        Used by two-bone IK to determine which way the middle joint
        (elbow/knee) should bend.

        Args:
            root_joint_std_id: Standardized ID of the root joint (shoulder/hip)
            hierarchy: Optional skeleton hierarchy for child lookup

        Returns:
            Bend direction as float (+1.0 or -1.0)
        """
        middle_joint_std_id = None

        # Try hierarchy lookup first
        if hierarchy:
            children = hierarchy.get(root_joint_std_id, [])
            for child_id in children:
                if "shoulder" in root_joint_std_id and "elbow" in child_id:
                    middle_joint_std_id = child_id
                    break
                elif "hip" in root_joint_std_id and "knee" in child_id:
                    middle_joint_std_id = child_id
                    break

        # Fallback to hardcoded mapping
        if not middle_joint_std_id:
            middle_joint_std_id = self.ROOT_TO_MIDDLE_MAPPING.get(root_joint_std_id)

        # Also try just the abstract name portion
        if not middle_joint_std_id:
            if '_' in root_joint_std_id:
                parts = root_joint_std_id.split('_')
                if len(parts) >= 2:
                    # Try 'left_shoulder' from 'left_shoulder_7'
                    abstract_root = '_'.join(parts[:-1]) if parts[-1].isdigit() else root_joint_std_id
                    middle_joint_std_id = self.ROOT_TO_MIDDLE_MAPPING.get(abstract_root)

        if middle_joint_std_id:
            direction = self.get(middle_joint_std_id)
            logger.debug(
                "BendDirectionManager: bend_direction %s for '%s' (from '%s')",
                direction, middle_joint_std_id, root_joint_std_id
            )
            return float(direction)

        logger.debug(
            "BendDirectionManager: No middle joint found for root '%s', using default 1.0",
            root_joint_std_id
        )
        return 1.0

    def calculate_from_geometry(
        self,
        middle_joint_abstract_name: str,
        p0_pos: QPointF,  # Parent/root position
        p1_pos: QPointF,  # Middle joint position
        p2_pos: QPointF,  # End effector position
        standardized_id: str | None = None
    ) -> int:
        """
        Calculate bend direction from joint geometry using cross product.

        Args:
            middle_joint_abstract_name: Abstract name like 'left_elbow'
            p0_pos: Position of parent joint (shoulder/hip)
            p1_pos: Position of middle joint (elbow/knee)
            p2_pos: Position of end effector (hand/foot)
            standardized_id: Optional standardized ID to also store under

        Returns:
            Calculated bend direction (+1 or -1)
        """
        vec_to_root = QPointF(p0_pos.x() - p1_pos.x(), p0_pos.y() - p1_pos.y())
        vec_to_end = QPointF(p2_pos.x() - p1_pos.x(), p2_pos.y() - p1_pos.y())

        # Cross product to determine handedness
        cross_product = (vec_to_root.x() * vec_to_end.y()) - (vec_to_root.y() * vec_to_end.x())

        if abs(cross_product) < 1e-4:
            # Nearly collinear - use side heuristic
            direction = 1 if "left" in middle_joint_abstract_name else -1
        else:
            direction = -1 if cross_product > 0 else 1

        # Store the result
        self._bend_directions[middle_joint_abstract_name] = direction
        if standardized_id:
            self._bend_directions[standardized_id] = direction

        logger.debug(
            "BendDirectionManager: Calculated bend_direction = %s for '%s'",
            direction, middle_joint_abstract_name
        )

        return direction

    def update_from_skeleton_data(
        self,
        joints_data: dict[str, dict[str, Any]]
    ) -> int:
        """
        Update bend directions from skeleton joint data.

        Looks for 'bend_direction' field in each joint's data
        and stores it in this manager.

        Args:
            joints_data: Dict of joint_id -> joint data dict

        Returns:
            Number of bend directions updated
        """
        count = 0

        for joint_id, joint_data in joints_data.items():
            bend_dir = joint_data.get("bend_direction")
            if bend_dir is not None:
                # Only process actual middle joints
                if not any(j in joint_id for j in ("elbow", "knee")):
                    continue

                self._bend_directions[joint_id] = bend_dir

                # Also store with abstract name for compatibility
                if '_' in joint_id and joint_id.split('_')[-1].isdigit():
                    abstract_name = '_'.join(joint_id.split('_')[:-1])
                    self._bend_directions[abstract_name] = bend_dir

                count += 1
                logger.debug(
                    "BendDirectionManager: Updated '%s' to %s from skeleton",
                    joint_id, bend_dir
                )

        return count

    def get_for_fabrik(self) -> dict[str, int]:
        """
        Get bend directions formatted for FABRIK solver.

        FABRIK expects abstract names (e.g., 'left_elbow') not
        standardized IDs (e.g., 'left_elbow_8').

        Returns:
            Dict of abstract_name -> bend_direction
        """
        result: dict[str, int] = {}

        for std_id, bend_dir in self._bend_directions.items():
            # Only process middle joints
            if not any(j in std_id for j in ("elbow", "knee")):
                continue

            # Extract abstract name
            if '_' in std_id:
                parts = std_id.split('_')
                if len(parts) >= 3 and parts[-1].isdigit():
                    abstract_name = '_'.join(parts[:-1])
                else:
                    abstract_name = std_id
            else:
                abstract_name = std_id

            result[abstract_name] = bend_dir

        return result

    def __repr__(self) -> str:
        return f"BendDirectionManager({self._bend_directions})"
