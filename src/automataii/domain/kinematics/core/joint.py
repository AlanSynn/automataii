# src/automataii/domain/kinematics/core/joint.py

import math

from PyQt6.QtCore import QPointF


class Joint:
    """
    Represents a single joint in a kinematic chain.

    A joint has a position, angle, and is connected to other joints via links.
    """

    def __init__(
        self,
        name: str,
        position: QPointF = QPointF(0, 0),
        angle: float = 0.0,
        link_length: float = 1.0,
        parent: str | None = None,
        angle_limits: tuple[float, float] | None = None,
    ):
        """
        Initialize a joint.

        Args:
            name: Name of the joint
            position: Initial position
            angle: Initial angle in radians
            link_length: Length of the link from this joint
            parent: Name of the parent joint (None for root)
            angle_limits: Tuple of (min_angle, max_angle) in radians
        """
        self.name = name
        self.position = position
        self.angle = angle
        self.link_length = link_length
        self.parent = parent
        self.angle_limits = angle_limits or (-math.pi, math.pi)

        # Validation
        if self.angle_limits[0] > self.angle_limits[1]:
            raise ValueError("Minimum angle limit must be less than maximum")

    def set_angle(self, angle: float) -> None:
        """
        Set the joint angle with constraint checking.

        Args:
            angle: New angle in radians
        """
        # Normalize angle to [-pi, pi]
        angle = self._normalize_angle(angle)

        # Apply constraints
        angle = max(self.angle_limits[0], min(self.angle_limits[1], angle))

        self.angle = angle

    def get_angle(self) -> float:
        """Get the current joint angle."""
        return self.angle

    def set_position(self, position: QPointF) -> None:
        """Set the joint position."""
        self.position = position

    def get_position(self) -> QPointF:
        """Get the current joint position."""
        return self.position

    def is_angle_valid(self, angle: float) -> bool:
        """Check if an angle is within the joint's limits."""
        normalized = self._normalize_angle(angle)
        return self.angle_limits[0] <= normalized <= self.angle_limits[1]

    def get_link_end_position(self) -> QPointF:
        """Get the position of the end of this joint's link."""
        dx = self.link_length * math.cos(self.angle)
        dy = self.link_length * math.sin(self.angle)
        return QPointF(self.position.x() + dx, self.position.y() + dy)

    def distance_to(self, other_joint: "Joint") -> float:
        """Calculate distance to another joint."""
        dx = self.position.x() - other_joint.position.x()
        dy = self.position.y() - other_joint.position.y()
        return math.sqrt(dx * dx + dy * dy)

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-pi, pi] range."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    def __str__(self) -> str:
        return f"Joint({self.name}, pos={self.position.x():.1f},{self.position.y():.1f}, angle={self.angle:.2f})"

    def __repr__(self) -> str:
        return self.__str__()
