"""
Adapter pattern for bridging old mechanism system with new modular architecture.
Provides backward compatibility while transitioning to new system.
"""

import logging
from typing import Any

from PyQt6.QtWidgets import QGraphicsScene

from ..interfaces.editor import EditorInterface
from ..interfaces.mechanism import MechanismInterface, MechanismParameters
from ..interfaces.serializer import BlueprintData, BlueprintSerializer
from ..registry import mechanism_registry


class MechanismAdapter:
    """
    Adapter for mechanism system.

    Bridges the old mechanism_design_tab implementation
    with the new modular mechanism system.
    """

    def __init__(self):
        """Initialize adapter."""
        self.mechanisms: dict[str, MechanismInterface] = {}
        self.editors: dict[str, EditorInterface] = {}
        self.serializers: dict[str, BlueprintSerializer] = {}

    def create_mechanism_from_legacy(self, mechanism_data: dict[str, Any]) -> MechanismInterface | None:
        """
        Create mechanism from legacy data format.

        Args:
            mechanism_data: Legacy mechanism configuration

        Returns:
            Mechanism instance or None
        """
        try:
            # Convert legacy format to new format
            parameters = self._convert_legacy_to_parameters(mechanism_data)

            # Create mechanism through registry
            mechanism = mechanism_registry.create_mechanism(parameters)

            if mechanism:
                self.mechanisms[parameters.mechanism_id] = mechanism

            return mechanism

        except Exception as e:
            logging.error(f"[ADAPTER] Failed to create mechanism from legacy data: {e}")
            return None

    def create_editor_for_mechanism(self,
                                   mechanism_id: str,
                                   scene: QGraphicsScene) -> EditorInterface | None:
        """
        Create editor for existing mechanism.

        Args:
            mechanism_id: Mechanism identifier
            scene: Graphics scene

        Returns:
            Editor instance or None
        """
        if mechanism_id not in self.mechanisms:
            logging.error(f"[ADAPTER] Mechanism not found: {mechanism_id}")
            return None

        mechanism = self.mechanisms[mechanism_id]
        mechanism_type = mechanism.mechanism_type

        editor = mechanism_registry.create_editor(mechanism_type, mechanism_id, scene)

        if editor:
            self.editors[mechanism_id] = editor

        return editor

    def export_mechanism_blueprint(self, mechanism_id: str) -> BlueprintData | None:
        """
        Export mechanism as blueprint.

        Args:
            mechanism_id: Mechanism identifier

        Returns:
            Blueprint data or None
        """
        if mechanism_id not in self.mechanisms:
            logging.error(f"[ADAPTER] Mechanism not found: {mechanism_id}")
            return None

        mechanism = self.mechanisms[mechanism_id]
        mechanism_type = mechanism.mechanism_type

        # Get or create serializer
        if mechanism_type not in self.serializers:
            serializer = mechanism_registry.create_serializer(mechanism_type)
            if serializer:
                self.serializers[mechanism_type] = serializer
            else:
                logging.error(f"[ADAPTER] No serializer for type: {mechanism_type}")
                return None

        serializer = self.serializers[mechanism_type]

        # Prepare mechanism data for serialization
        mechanism_data = {
            'parameters': mechanism.get_key_points(),
            'constraints': mechanism.get_constraints(),
            'simulation': mechanism.simulate(num_frames=1)
        }

        return serializer.serialize(mechanism_data)

    def _convert_legacy_to_parameters(self, legacy_data: dict[str, Any]) -> MechanismParameters:
        """
        Convert legacy format to new parameter format.

        Args:
            legacy_data: Legacy mechanism data

        Returns:
            MechanismParameters instance
        """
        # Map legacy type names to new system
        type_mapping = {
            "4_bar_linkage": "four_bar",
            "cam": "cam",
            "gear": "gear",
            "simple_gear": "gear",
            "planetary_gear": "planetary_gear"
        }

        legacy_type = legacy_data.get("type", "unknown")
        mechanism_type = type_mapping.get(legacy_type, legacy_type)

        return MechanismParameters(
            mechanism_type=mechanism_type,
            mechanism_id=legacy_data.get("id", ""),
            part_name=legacy_data.get("part_name", ""),
            params=legacy_data.get("params", {}),
            metadata={
                'legacy_type': legacy_type,
                'key_points': legacy_data.get("key_points"),
                'transform_params': legacy_data.get("transform_params")
            }
        )

    def cleanup(self) -> None:
        """Clean up all resources."""
        for editor in self.editors.values():
            editor.remove_handles()

        self.mechanisms.clear()
        self.editors.clear()
        self.serializers.clear()
