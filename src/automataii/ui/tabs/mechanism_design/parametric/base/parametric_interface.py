"""
Abstract interface for mechanism-specific parametric editing.

Defines the standard interface that all mechanism parametric editors must implement.
This ensures consistency and enables the factory pattern.
"""

from abc import ABC, abstractmethod
from typing import Any

from PyQt6.QtCore import QPointF

from ..handles.base_handle import BaseHandle


class ParametricMechanismInterface(ABC):
    """
    Abstract base class for mechanism-specific parametric editing.

    Each mechanism type (linkage, gear, cam, etc.) must implement this interface
    to provide consistent parametric editing capabilities.
    """

    def __init__(self, mechanism_id: str, layer_data: dict[str, Any], scene_manager):
        self.mechanism_id = mechanism_id
        self.layer_data = layer_data
        self.scene_manager = scene_manager
        self.handles: list[BaseHandle] = []
        self.is_active = False

    @abstractmethod
    def create_handles(self) -> list[BaseHandle]:
        """
        Create all parametric editing handles for this mechanism.

        Returns:
            List of handle objects that can be manipulated by the user
        """
        pass

    @abstractmethod
    def update_mechanism_from_handles(self, changed_handles: dict[str, Any]) -> dict[str, Any]:
        """
        Update mechanism parameters based on handle changes.

        Args:
            changed_handles: Dictionary of handle_name -> new_value

        Returns:
            Updated mechanism parameters dictionary
        """
        pass

    @abstractmethod
    def validate_parameters(self, params: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate mechanism parameters for feasibility.

        Args:
            params: Mechanism parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_editable_parameters(self) -> list[str]:
        """
        Get list of parameter names that can be edited.

        Returns:
            List of parameter names (e.g., ['l1', 'l2', 'anchor_x', 'anchor_y'])
        """
        pass

    def activate(self) -> None:
        """Activate parametric editing mode."""
        if not self.is_active:
            self.handles = self.create_handles()
            for handle in self.handles:
                self.scene_manager.scene.addItem(handle)
            self.is_active = True

    def deactivate(self) -> None:
        """Deactivate parametric editing mode."""
        if self.is_active:
            for handle in self.handles:
                self.scene_manager.scene.removeItem(handle)
            self.handles.clear()
            self.is_active = False

    def get_handle_count(self) -> int:
        """Get number of active handles."""
        return len(self.handles)

    def get_mechanism_type(self) -> str:
        """Get mechanism type identifier."""
        return self.layer_data.get("type", "unknown")


class ParametricHandleFactory:
    """
    Factory for creating common handle types.
    Reduces code duplication across mechanism implementations.
    """

    @staticmethod
    def create_anchor_handle(
        mechanism_id: str, anchor_name: str, position: QPointF, mechanism_data: dict, callback
    ) -> BaseHandle:
        """Create an anchor point handle."""
        from ..handles.anchor_handle import AnchorHandle

        return AnchorHandle(mechanism_id, anchor_name, position, mechanism_data, callback)

    @staticmethod
    def create_radius_handle(
        mechanism_id: str,
        param_name: str,
        center: QPointF,
        radius: float,
        mechanism_data: dict,
        callback,
    ) -> BaseHandle:
        """Create a radius adjustment handle."""
        # TODO: Implement RadiusHandle
        pass

    @staticmethod
    def create_angle_handle(
        mechanism_id: str,
        param_name: str,
        center: QPointF,
        angle: float,
        mechanism_data: dict,
        callback,
    ) -> BaseHandle:
        """Create an angle adjustment handle."""
        # TODO: Implement AngleHandle
        pass

    @staticmethod
    def create_distance_handle(
        mechanism_id: str,
        param_name: str,
        start: QPointF,
        end: QPointF,
        mechanism_data: dict,
        callback,
    ) -> BaseHandle:
        """Create a distance/length adjustment handle."""
        # TODO: Implement DistanceHandle
        pass
