"""Color constants and utilities for linkage rendering.

Qt-specific rendering utilities for linkage visualization.
This module belongs in the presentation layer as it uses Qt types.
"""

from PyQt6.QtGui import QColor, QPen

from automataii.domain.mechanisms.linkage.config import LinkRole

LINK_COLORS: dict[LinkRole, str] = {
    LinkRole.GROUND: "#4A4A4A",
    LinkRole.DRIVER: "#1E88E5",
    LinkRole.COUPLER: "#FF9800",
    LinkRole.FOLLOWER: "#4CAF50",
}

PATH_COLOR = "#E53935"


def get_link_color(role: LinkRole) -> QColor:
    """Convert link role to QColor for rendering.

    Args:
        role: Link role

    Returns:
        QColor object for the role
    """
    return QColor(LINK_COLORS[role])


def get_link_pen(role: LinkRole, width: int = 4) -> QPen:
    """Create QPen for link rendering.

    Args:
        role: Link role
        width: Pen width in pixels (default: 4)

    Returns:
        Configured QPen with role-based color
    """
    return QPen(get_link_color(role), width)
