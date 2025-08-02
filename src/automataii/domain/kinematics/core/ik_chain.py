# src/automataii/domain/kinematics/core/ik_chain.py


from PyQt6.QtCore import QPointF

from .joint import Joint


class IKChain:
    """
    Represents a kinematic chain for inverse kinematics solving.

    A chain consists of a series of joints connected by links.
    """

    def __init__(self, name: str, joints: list[Joint]):
        """
        Initialize an IK chain.

        Args:
            name: Name of the chain
            joints: List of joints in the chain
        """
        self.name = name
        self.joints = joints
        self._validate_chain()

    def _validate_chain(self) -> None:
        """Validate the chain structure."""
        if not self.joints:
            raise ValueError("Chain must have at least one joint")

        # Check for consistent parent-child relationships
        for i in range(len(self.joints) - 1):
            current = self.joints[i]
            next_joint = self.joints[i + 1]
            if next_joint.parent != current.name:
                raise ValueError(f"Chain structure error: joint {next_joint.name} parent mismatch")

    def get_root_joint(self) -> Joint:
        """Get the root joint of the chain."""
        return self.joints[0]

    def get_end_effector(self) -> Joint:
        """Get the end effector joint of the chain."""
        return self.joints[-1]

    def get_joint_by_name(self, name: str) -> Joint | None:
        """Get a joint by name."""
        for joint in self.joints:
            if joint.name == name:
                return joint
        return None

    def get_chain_length(self) -> float:
        """Get the total length of the chain."""
        total_length = 0.0
        for joint in self.joints:
            total_length += joint.link_length
        return total_length

    def get_joint_positions(self) -> list[QPointF]:
        """Get the current positions of all joints in the chain."""
        positions = []
        for joint in self.joints:
            positions.append(joint.position)
        return positions

    def set_joint_positions(self, positions: list[QPointF]) -> None:
        """Set the positions of all joints in the chain."""
        if len(positions) != len(self.joints):
            raise ValueError("Number of positions must match number of joints")

        for joint, position in zip(self.joints, positions, strict=False):
            joint.position = position

    def forward_kinematics(self, start_position: QPointF, angles: list[float]) -> QPointF:
        """
        Compute forward kinematics for the chain.

        Args:
            start_position: Starting position
            angles: Joint angles in radians

        Returns:
            End effector position
        """
        if len(angles) != len(self.joints):
            raise ValueError("Number of angles must match number of joints")

        current_pos = start_position
        current_angle = 0.0

        for joint, angle in zip(self.joints, angles, strict=False):
            current_angle += angle
            # Move along the link
            import math

            dx = joint.link_length * math.cos(current_angle)
            dy = joint.link_length * math.sin(current_angle)
            current_pos = QPointF(current_pos.x() + dx, current_pos.y() + dy)
            joint.position = current_pos

        return current_pos

    def __str__(self) -> str:
        return f"IKChain({self.name}, {len(self.joints)} joints)"

    def __repr__(self) -> str:
        return self.__str__()
