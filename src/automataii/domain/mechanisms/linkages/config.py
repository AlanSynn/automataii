"""Linkage configuration dataclass with role-based identification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LinkageType(Enum):
    """Type of linkage mechanism."""

    THREE_BAR = 3
    FOUR_BAR = 4
    FIVE_BAR = 5
    SIX_BAR = 6


class LinkRole(Enum):
    """Role of a link in the mechanism."""

    GROUND = "ground"
    DRIVER = "driver"
    COUPLER = "coupler"
    FOLLOWER = "follower"


@dataclass(frozen=True)
class LinkageConfig:
    """Linkage mechanism configuration with role-based identification.

    Attributes:
        type: Type of linkage (e.g., FOUR_BAR)
        link_lengths: Tuple of link lengths in mm ordered around the loop
        driver_index: Index of the driven link (0-based, ground link is index 0)
        roles: Tuple describing the semantic role of each link
    """

    type: LinkageType
    link_lengths: tuple[float, ...]
    driver_index: int = 1
    roles: tuple[LinkRole, ...] | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        expected_links = self.type.value
        if len(self.link_lengths) != expected_links:
            raise ValueError(
                f"{self.type.name.replace('_', '-').title()} requires "
                f"{expected_links} lengths, got {len(self.link_lengths)}"
            )

        if any(length <= 0 for length in self.link_lengths):
            raise ValueError("All link lengths must be positive")

        driver_index = self.driver_index
        if expected_links > 1 and driver_index == 0:
            driver_index = 1

        if not 0 <= driver_index < expected_links:
            raise ValueError(
                f"Driver index must be between 0 and {expected_links - 1}, got {self.driver_index}"
            )

        object.__setattr__(self, "driver_index", driver_index)

        roles = self._build_roles(expected_links, driver_index)
        object.__setattr__(self, "roles", roles)

    def validate_grashof(self) -> bool:
        """Check if configuration satisfies Grashof condition.

        Grashof condition: s + l <= p + q
        where s = shortest link, l = longest link, p and q = intermediate links

        Returns:
            True if mechanism can achieve full rotation
        """
        if self.type != LinkageType.FOUR_BAR:
            return False

        sorted_lengths = sorted(self.link_lengths)
        shortest, mid1, mid2, longest = sorted_lengths
        return (shortest + longest) <= (mid1 + mid2)

    @property
    def grashof_ratio(self) -> float:
        """Compute (s+l)/(p+q) ratio for Grashof analysis.

        Returns:
            Ratio <= 1.0 indicates Grashof condition satisfied
        """
        if self.type != LinkageType.FOUR_BAR:
            return float("nan")

        sorted_lengths = sorted(self.link_lengths)
        shortest, mid1, mid2, longest = sorted_lengths
        return (shortest + longest) / (mid1 + mid2) if (mid1 + mid2) > 0 else float("inf")

    def get_link_role(self, index: int) -> LinkRole:
        """Determine role of link at given index.

        Args:
            index: Link index (0=ground, 1=input, 2=coupler, 3=output)

        Returns:
            Role of the link

        Raises:
            ValueError: If index is out of range or roles not initialized
        """
        if not 0 <= index < len(self.link_lengths):
            raise ValueError(
                f"Link index must be between 0 and {len(self.link_lengths) - 1}, got {index}"
            )
        if self.roles is None:
            raise ValueError("Roles not initialized")
        return self.roles[index]

    @staticmethod
    def _build_roles(link_count: int, driver_index: int) -> tuple[LinkRole, ...]:
        if link_count <= 0:
            return ()

        roles: list[LinkRole] = [LinkRole.COUPLER] * link_count
        roles[0] = LinkRole.GROUND

        if link_count > 1:
            roles[driver_index] = LinkRole.DRIVER

        if link_count >= 4:
            follower_idx = None
            for candidate in (link_count - 1, 1, link_count - 2):
                if 0 < candidate < link_count and candidate != driver_index:
                    follower_idx = candidate
                    break
            if follower_idx is not None and follower_idx != driver_index:
                roles[follower_idx] = LinkRole.FOLLOWER

        return tuple(roles)
