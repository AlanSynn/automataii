"""Linkage mechanism configuration and color-coding system.

Public API:
- LinkageConfig: Configuration dataclass with role-based identification
- LinkageType: Enum for linkage types (FOUR_BAR, etc.)
- LinkRole: Enum for link roles (GROUND, DRIVER, COUPLER, FOLLOWER)
- LINK_COLORS: Color mapping for link roles
- get_link_color: Convert role to QColor
- get_link_pen: Create QPen for role
"""

from automataii.mechanisms.linkage.config import (
    LinkageConfig,
    LinkageType,
    LinkRole,
)
from automataii.mechanisms.linkage.colors import (
    LINK_COLORS,
    PATH_COLOR,
    get_link_color,
    get_link_pen,
)

__all__ = [
    "LinkageConfig",
    "LinkageType",
    "LinkRole",
    "LINK_COLORS",
    "PATH_COLOR",
    "get_link_color",
    "get_link_pen",
]
