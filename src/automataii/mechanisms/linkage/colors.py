"""Color constants and utilities for linkage rendering.

Lines: ~60
Public API: LINK_COLORS, PATH_COLOR, get_link_color, get_link_pen
Deps In: 0 [fourbar renderer]
Deps Out: 2 [PyQt6, config]
Coupling: Low (minimal external deps)
Cohesion: Feature (color utilities)
Owner: Alan Synn
Last Updated: 2025-10-27
"""

from PyQt6.QtGui import QColor, QPen

from automataii.mechanisms.linkage.config import LinkRole

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
