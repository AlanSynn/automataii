"""
Base classes for mechanism visualization.

This module defines the abstract base class and configuration for
mechanism visualizers, ensuring consistent interface and behavior.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem


@dataclass
class VisualizationConfig:
    """Configuration for mechanism visualization."""

    # Visual appearance
    default_pen_width: float = 2.0
    pivot_radius: float = 4.0
    joint_radius: float = 3.0

    # Colors (using field with default_factory for mutable defaults)
    link_color: QColor = field(default_factory=lambda: QColor(100, 100, 100))
    pivot_color: QColor = field(default_factory=lambda: QColor(255, 0, 0))
    joint_color: QColor = field(default_factory=lambda: QColor(0, 100, 255))
    gear_color: QColor = field(default_factory=lambda: QColor(150, 150, 150))
    cam_color: QColor = field(default_factory=lambda: QColor(100, 150, 100))

    # Z-indices for layering
    z_index_base: int = 100
    z_index_pivot: int = 102
    z_index_joint: int = 101

    # Coordinate transformation
    transform_function: Callable | None = None

    def get_link_pen(self) -> QPen:
        """Get pen for drawing links."""
        pen = QPen(self.link_color)
        pen.setWidthF(self.default_pen_width)
        return pen

    def get_pivot_pen(self) -> QPen:
        """Get pen for drawing pivots."""
        pen = QPen(self.pivot_color)
        pen.setWidthF(self.default_pen_width)
        return pen

    def get_joint_pen(self) -> QPen:
        """Get pen for drawing joints."""
        pen = QPen(self.joint_color)
        pen.setWidthF(self.default_pen_width)
        return pen


class MechanismVisualizer(ABC):
    """
    Abstract base class for mechanism visualizers.

    Each mechanism type should implement this interface to provide
    consistent visualization behavior.
    """

    def __init__(self, config: VisualizationConfig | None = None):
        """
        Initialize visualizer with configuration.

        Args:
            config: Visualization configuration, uses defaults if None
        """
        self.config = config or VisualizationConfig()
        self._visual_items: list[QGraphicsItem] = []

    @abstractmethod
    def create_visuals(self, mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visual representation of the mechanism.

        Args:
            mechanism_data: Dictionary containing mechanism parameters and state

        Returns:
            List of QGraphicsItem objects representing the mechanism
        """
        pass

    @abstractmethod
    def update_visuals(self, visual_items: list[QGraphicsItem],
                      mechanism_data: dict[str, Any]) -> None:
        """
        Update existing visual items with new mechanism state.

        Args:
            visual_items: Existing visual items to update
            mechanism_data: Updated mechanism parameters and state
        """
        pass

    def cleanup_visuals(self, visual_items: list[QGraphicsItem]) -> None:
        """
        Clean up visual items when no longer needed.

        Args:
            visual_items: Visual items to clean up
        """
        for item in visual_items:
            if item and item.scene():
                item.scene().removeItem(item)

    def transform_point(self, point: np.ndarray) -> QPointF:
        """
        Transform a point from mechanism space to scene coordinates.

        Args:
            point: Point in mechanism space (numpy array)

        Returns:
            Point in scene coordinates (QPointF)
        """
        if self.config.transform_function:
            return self.config.transform_function(point)
        return QPointF(float(point[0]), float(point[1]))

    def get_mechanism_type(self) -> str:
        """
        Get the type of mechanism this visualizer handles.

        Returns:
            String identifier for the mechanism type
        """
        # Default implementation based on class name
        class_name = self.__class__.__name__
        return class_name.replace('Visualizer', '').lower()

    @staticmethod
    def extract_params(mechanism_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract parameters from mechanism data.

        Args:
            mechanism_data: Full mechanism data dictionary

        Returns:
            Parameters dictionary
        """
        return mechanism_data.get("params", {})
