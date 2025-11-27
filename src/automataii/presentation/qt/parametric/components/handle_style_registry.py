"""
Handle Style Registry - Centralized handle style management.

Extracted from parametric_editor.py. Provides consistent styling
for all parametric handle types across mechanism editors.

Design Pattern: Registry (style lookup and management)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from PyQt6.QtGui import QColor


class HandleType(Enum):
    """Enumeration of handle types."""
    ANCHOR = auto()
    JOINT = auto()
    LINK_LENGTH = auto()
    COUPLER = auto()
    CAM_CENTER = auto()
    CAM_PROFILE = auto()
    FOLLOWER = auto()
    GEAR_CENTER = auto()
    GEAR_RADIUS = auto()
    MESH_POINT = auto()
    ROTATION = auto()
    GENERIC = auto()


@dataclass
class HandleStyle:
    """Visual style configuration for parametric handles."""
    size: float = 12.0
    color: QColor = field(default_factory=lambda: QColor(255, 100, 0))
    hover_color: QColor = field(default_factory=lambda: QColor(255, 150, 50))
    active_color: QColor = field(default_factory=lambda: QColor(255, 200, 100))
    border_width: float = 2.0
    border_color: QColor = field(default_factory=lambda: QColor(50, 50, 50))
    opacity: float = 0.9


class HandleStyleRegistry:
    """
    Registry for handle styles.

    Provides consistent styling across mechanism editors and
    allows runtime style customization.

    Responsibilities:
    - Store and retrieve handle styles by type
    - Provide default styles for all handle types
    - Support style inheritance and overrides

    Time Complexity: O(1) for lookups
    """

    def __init__(self) -> None:
        """Initialize registry with default styles."""
        self._styles: dict[HandleType, HandleStyle] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default styles for all handle types."""
        # Anchor handles - larger, green
        self._styles[HandleType.ANCHOR] = HandleStyle(
            size=14.0,
            color=QColor(100, 200, 100),
            hover_color=QColor(150, 230, 150),
            active_color=QColor(200, 255, 200),
        )

        # Joint handles - medium, blue
        self._styles[HandleType.JOINT] = HandleStyle(
            size=12.0,
            color=QColor(100, 150, 255),
            hover_color=QColor(130, 180, 255),
            active_color=QColor(160, 210, 255),
        )

        # Link length handles - small, orange
        self._styles[HandleType.LINK_LENGTH] = HandleStyle(
            size=10.0,
            color=QColor(255, 150, 50),
            hover_color=QColor(255, 180, 100),
            active_color=QColor(255, 210, 150),
        )

        # Coupler handles - medium, purple
        self._styles[HandleType.COUPLER] = HandleStyle(
            size=12.0,
            color=QColor(180, 100, 255),
            hover_color=QColor(200, 130, 255),
            active_color=QColor(220, 160, 255),
        )

        # Cam center handles - large, green
        self._styles[HandleType.CAM_CENTER] = HandleStyle(
            size=16.0,
            color=QColor(100, 200, 100),
            hover_color=QColor(130, 220, 130),
            active_color=QColor(160, 240, 160),
        )

        # Cam profile handles - small, yellow-orange
        self._styles[HandleType.CAM_PROFILE] = HandleStyle(
            size=10.0,
            color=QColor(255, 200, 100),
            hover_color=QColor(255, 220, 140),
            active_color=QColor(255, 240, 180),
        )

        # Follower handles - medium, blue
        self._styles[HandleType.FOLLOWER] = HandleStyle(
            size=12.0,
            color=QColor(100, 100, 255),
            hover_color=QColor(130, 130, 255),
            active_color=QColor(160, 160, 255),
        )

        # Gear center handles - medium, steel blue
        self._styles[HandleType.GEAR_CENTER] = HandleStyle(
            size=14.0,
            color=QColor(100, 149, 237),
            hover_color=QColor(130, 170, 240),
            active_color=QColor(160, 190, 245),
        )

        # Gear radius handles - small, orange
        self._styles[HandleType.GEAR_RADIUS] = HandleStyle(
            size=10.0,
            color=QColor(255, 165, 0),
            hover_color=QColor(255, 190, 60),
            active_color=QColor(255, 215, 120),
        )

        # Mesh point handles - small, red
        self._styles[HandleType.MESH_POINT] = HandleStyle(
            size=10.0,
            color=QColor(255, 100, 100),
            hover_color=QColor(255, 140, 140),
            active_color=QColor(255, 180, 180),
        )

        # Rotation handles - large, cyan
        self._styles[HandleType.ROTATION] = HandleStyle(
            size=18.0,
            color=QColor(0, 200, 200),
            hover_color=QColor(50, 220, 220),
            active_color=QColor(100, 240, 240),
            border_width=3.0,
        )

        # Generic handles - default
        self._styles[HandleType.GENERIC] = HandleStyle()

    def get_style(self, handle_type: HandleType) -> HandleStyle:
        """
        Get style for a handle type.

        Args:
            handle_type: Type of handle

        Returns:
            HandleStyle for the type

        Time Complexity: O(1)
        """
        return self._styles.get(handle_type, self._styles[HandleType.GENERIC])

    def register_style(
        self,
        handle_type: HandleType,
        style: HandleStyle,
    ) -> None:
        """
        Register a custom style for a handle type.

        Args:
            handle_type: Type of handle
            style: Style to register

        Time Complexity: O(1)
        """
        self._styles[handle_type] = style

    def create_style(
        self,
        base_type: HandleType | None = None,
        **overrides: Any,
    ) -> HandleStyle:
        """
        Create a new style, optionally based on existing type.

        Args:
            base_type: Optional base type to inherit from
            **overrides: Style attribute overrides

        Returns:
            New HandleStyle instance

        Time Complexity: O(1)
        """
        if base_type:
            base = self.get_style(base_type)
            return HandleStyle(
                size=overrides.get('size', base.size),
                color=overrides.get('color', base.color),
                hover_color=overrides.get('hover_color', base.hover_color),
                active_color=overrides.get('active_color', base.active_color),
                border_width=overrides.get('border_width', base.border_width),
                border_color=overrides.get('border_color', base.border_color),
                opacity=overrides.get('opacity', base.opacity),
            )
        else:
            return HandleStyle(**overrides)

    def get_style_for_mechanism(
        self,
        mechanism_type: str,
        handle_name: str,
    ) -> HandleStyle:
        """
        Get style for a specific mechanism handle.

        Args:
            mechanism_type: Type of mechanism (4bar, cam, gear, etc.)
            handle_name: Name of handle (anchor1, center, etc.)

        Returns:
            Appropriate HandleStyle

        Time Complexity: O(1)
        """
        # Map handle names to types
        handle_type_map = {
            # 4-bar linkage
            'anchor1': HandleType.ANCHOR,
            'anchor2': HandleType.ANCHOR,
            'crank': HandleType.JOINT,
            'rocker': HandleType.JOINT,
            'coupler': HandleType.COUPLER,
            'crank_length': HandleType.LINK_LENGTH,
            'rocker_length': HandleType.LINK_LENGTH,
            # Cam
            'center': HandleType.CAM_CENTER,
            'follower': HandleType.FOLLOWER,
            'profile': HandleType.CAM_PROFILE,
            # Gear
            'gear_center': HandleType.GEAR_CENTER,
            'gear1_center': HandleType.GEAR_CENTER,
            'gear2_center': HandleType.GEAR_CENTER,
            'sun_center': HandleType.GEAR_CENTER,
            'gear_radius': HandleType.GEAR_RADIUS,
            'gear1_radius': HandleType.GEAR_RADIUS,
            'gear2_radius': HandleType.GEAR_RADIUS,
            'planet_radius': HandleType.GEAR_RADIUS,
            'mesh': HandleType.MESH_POINT,
            # General
            'rotation': HandleType.ROTATION,
        }

        # Find matching handle type
        for key, handle_type in handle_type_map.items():
            if key in handle_name.lower():
                return self.get_style(handle_type)

        return self.get_style(HandleType.GENERIC)


# Global registry instance
_default_registry: HandleStyleRegistry | None = None


def get_default_registry() -> HandleStyleRegistry:
    """Get the default style registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = HandleStyleRegistry()
    return _default_registry
