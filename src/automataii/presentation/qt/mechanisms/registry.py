"""
Registry pattern for mechanism types.
Provides centralized registration and factory for all mechanisms.
"""

import logging
from typing import Any, Optional

from .interfaces.editor import EditorInterface
from .interfaces.mechanism import MechanismInterface, MechanismParameters
from .interfaces.serializer import BlueprintSerializer


class MechanismRegistry:
    """
    Singleton registry for mechanism types.

    Provides:
    - Dynamic registration of mechanism types
    - Factory methods for creating mechanisms
    - Type discovery and validation
    """

    _instance: Optional['MechanismRegistry'] = None

    def __new__(cls) -> 'MechanismRegistry':
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry."""
        if self._initialized:
            return

        self._mechanisms: dict[str, type[MechanismInterface]] = {}
        self._editors: dict[str, type[EditorInterface]] = {}
        self._serializers: dict[str, type[BlueprintSerializer]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._initialized = True

        logging.info("[REGISTRY] Mechanism registry initialized")

    def register_mechanism(self,
                          mechanism_type: str,
                          mechanism_class: type[MechanismInterface],
                          editor_class: type[EditorInterface] | None = None,
                          serializer_class: type[BlueprintSerializer] | None = None,
                          metadata: dict[str, Any] | None = None) -> None:
        """
        Register a mechanism type.

        Args:
            mechanism_type: Unique type identifier
            mechanism_class: Mechanism implementation class
            editor_class: Optional editor implementation
            serializer_class: Optional serializer implementation
            metadata: Optional metadata (display name, icon, etc.)
        """
        if mechanism_type in self._mechanisms:
            logging.warning(f"[REGISTRY] Overwriting existing mechanism type: {mechanism_type}")

        self._mechanisms[mechanism_type] = mechanism_class

        if editor_class:
            self._editors[mechanism_type] = editor_class

        if serializer_class:
            self._serializers[mechanism_type] = serializer_class

        if metadata:
            self._metadata[mechanism_type] = metadata

        logging.info(f"[REGISTRY] Registered mechanism type: {mechanism_type}")

    def create_mechanism(self, parameters: MechanismParameters) -> MechanismInterface | None:
        """
        Create a mechanism instance.

        Args:
            parameters: Mechanism configuration

        Returns:
            Mechanism instance or None if type not found
        """
        mechanism_type = parameters.mechanism_type

        if mechanism_type not in self._mechanisms:
            logging.error(f"[REGISTRY] Unknown mechanism type: {mechanism_type}")
            return None

        try:
            mechanism_class = self._mechanisms[mechanism_type]
            mechanism = mechanism_class(parameters)
            logging.info(f"[REGISTRY] Created mechanism: {parameters.mechanism_id} (type: {mechanism_type})")
            return mechanism
        except Exception as e:
            logging.error(f"[REGISTRY] Failed to create mechanism: {e}")
            return None

    def create_editor(self, mechanism_type: str, mechanism_id: str, scene: Any) -> EditorInterface | None:
        """
        Create an editor instance for a mechanism.

        Args:
            mechanism_type: Type of mechanism
            mechanism_id: Unique mechanism identifier
            scene: Graphics scene for handles

        Returns:
            Editor instance or None if not available
        """
        if mechanism_type not in self._editors:
            logging.warning(f"[REGISTRY] No editor registered for type: {mechanism_type}")
            return None

        try:
            editor_class = self._editors[mechanism_type]
            editor = editor_class(mechanism_id, scene)
            logging.info(f"[REGISTRY] Created editor for: {mechanism_id} (type: {mechanism_type})")
            return editor
        except Exception as e:
            logging.error(f"[REGISTRY] Failed to create editor: {e}")
            return None

    def create_serializer(self, mechanism_type: str) -> BlueprintSerializer | None:
        """
        Create a serializer instance for a mechanism.

        Args:
            mechanism_type: Type of mechanism

        Returns:
            Serializer instance or None if not available
        """
        if mechanism_type not in self._serializers:
            logging.warning(f"[REGISTRY] No serializer registered for type: {mechanism_type}")
            return None

        try:
            serializer_class = self._serializers[mechanism_type]
            serializer = serializer_class()
            logging.info(f"[REGISTRY] Created serializer for type: {mechanism_type}")
            return serializer
        except Exception as e:
            logging.error(f"[REGISTRY] Failed to create serializer: {e}")
            return None

    def get_mechanism_types(self) -> list[str]:
        """Get list of registered mechanism types."""
        return list(self._mechanisms.keys())

    def get_mechanism_metadata(self, mechanism_type: str) -> dict[str, Any]:
        """Get metadata for a mechanism type."""
        return self._metadata.get(mechanism_type, {})

    def has_editor(self, mechanism_type: str) -> bool:
        """Check if mechanism type has an editor."""
        return mechanism_type in self._editors

    def has_serializer(self, mechanism_type: str) -> bool:
        """Check if mechanism type has a serializer."""
        return mechanism_type in self._serializers

    def clear(self) -> None:
        """Clear all registrations (mainly for testing)."""
        self._mechanisms.clear()
        self._editors.clear()
        self._serializers.clear()
        self._metadata.clear()
        logging.info("[REGISTRY] Cleared all registrations")


# Global registry instance
mechanism_registry = MechanismRegistry()
