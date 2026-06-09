"""
Editor Factory - Factory for creating mechanism-specific editors.

Extracted from ParametricEditor. Provides centralized creation
of mechanism editors based on mechanism type.

Design Pattern: Factory (type-based instantiation)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QGraphicsScene


class EditorFactory:
    """
    Factory for creating mechanism editors.

    Responsibilities:
    - Register editor types for mechanism types
    - Create editor instances based on mechanism data
    - Validate mechanism data before creation

    Time Complexity: O(1) for creation
    """

    def __init__(self) -> None:
        """Initialize factory with default registrations."""
        self._registry: dict[str, type] = {}
        self._validators: dict[str, Callable[[dict], tuple[bool, str]]] = {}

    def register(
        self,
        mechanism_type: str,
        editor_class: type,
        validator: Callable[[dict], tuple[bool, str]] | None = None,
    ) -> None:
        """
        Register an editor class for a mechanism type.

        Args:
            mechanism_type: Type identifier (e.g., "4_bar_linkage")
            editor_class: Editor class to instantiate
            validator: Optional validation function

        Time Complexity: O(1)
        """
        self._registry[mechanism_type] = editor_class
        if validator:
            self._validators[mechanism_type] = validator

    def create(
        self,
        mechanism_id: str,
        mechanism_data: dict[str, Any],
        scene: QGraphicsScene,
    ) -> Any | None:
        """
        Create an editor for the given mechanism.

        Args:
            mechanism_id: Unique mechanism identifier
            mechanism_data: Mechanism configuration data
            scene: Graphics scene for handles

        Returns:
            Editor instance or None if type not registered

        Time Complexity: O(1)
        """
        mechanism_type = mechanism_data.get("type")
        if not mechanism_type:
            return None

        # Normalize type name
        normalized_type = self._normalize_type(mechanism_type)

        if normalized_type not in self._registry:
            return None

        # Validate if validator registered
        if normalized_type in self._validators:
            is_valid, error = self._validators[normalized_type](mechanism_data)
            if not is_valid:
                return None

        # Create editor instance
        editor_class = self._registry[normalized_type]
        editor = editor_class(mechanism_id, scene)

        return editor

    def _normalize_type(self, mechanism_type: str) -> str:
        """
        Normalize mechanism type string.

        Args:
            mechanism_type: Raw type string

        Returns:
            Normalized type string

        Time Complexity: O(1)
        """
        # Handle common variations
        type_map = {
            "4bar": "4_bar_linkage",
            "4-bar": "4_bar_linkage",
            "4_bar": "4_bar_linkage",
            "fourbar": "4_bar_linkage",
            "four_bar": "4_bar_linkage",
            "5bar": "5_bar_linkage",
            "5-bar": "5_bar_linkage",
            "5_bar": "5_bar_linkage",
            "fivebar": "5_bar_linkage",
            "6bar": "6_bar_linkage",
            "6-bar": "6_bar_linkage",
            "6_bar": "6_bar_linkage",
            "sixbar": "6_bar_linkage",
            "cam_follower": "cam",
            "cam-follower": "cam",
            "simple_gear": "gear",
            "gear_pair": "gear",
            "planetary": "planetary_gear",
        }

        normalized = mechanism_type.lower().strip()
        return type_map.get(normalized, normalized)

    def get_supported_types(self) -> list[str]:
        """
        Get list of supported mechanism types.

        Returns:
            List of registered mechanism types

        Time Complexity: O(n)
        """
        return list(self._registry.keys())

    def is_supported(self, mechanism_type: str) -> bool:
        """
        Check if a mechanism type is supported.

        Args:
            mechanism_type: Type to check

        Returns:
            True if type is registered

        Time Complexity: O(1)
        """
        normalized = self._normalize_type(mechanism_type)
        return normalized in self._registry


def create_default_factory() -> EditorFactory:
    """
    Create factory with default editor registrations.

    This function creates a factory pre-configured with
    standard mechanism editors.

    Returns:
        Configured EditorFactory

    Note:
        Import actual editor classes lazily to avoid
        circular dependencies.
    """
    factory = EditorFactory()

    # Register validators
    def validate_4bar(data: dict) -> tuple[bool, str]:
        params = data.get("params", {})
        if "anchor1_x" not in params:
            return False, "Missing anchor1_x"
        if "anchor2_x" not in params:
            return False, "Missing anchor2_x"
        return True, ""

    def validate_cam(data: dict) -> tuple[bool, str]:
        params = data.get("params", {})
        # Cam requires at least center position
        if "center_x" not in params and "cam_position" not in data:
            return False, "Missing cam center position"
        return True, ""

    def validate_gear(data: dict) -> tuple[bool, str]:
        params = data.get("params", {})
        if "r1" not in params and "radius1" not in params:
            return False, "Missing gear radius"
        return True, ""

    # Store validators (editors registered at runtime)
    factory._validators["4_bar_linkage"] = validate_4bar
    factory._validators["cam"] = validate_cam
    factory._validators["gear"] = validate_gear
    factory._validators["planetary_gear"] = validate_gear

    return factory


# Singleton instance
_default_factory: EditorFactory | None = None


def get_default_factory() -> EditorFactory:
    """Get the default editor factory singleton."""
    global _default_factory
    if _default_factory is None:
        _default_factory = create_default_factory()
    return _default_factory
