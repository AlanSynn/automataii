"""
Tab Adapters for Project State Management.

Adapters bridge existing tabs to the centralized ProjectStateManager,
enabling reactive state updates without modifying tab internals.

Architecture: Application Layer (Hexagonal)
Pattern: Adapter
"""

from .base import TabAdapter
from .editor import EditorTabAdapter
from .image_processing import ImageProcessingTabAdapter
from .mechanism_design import MechanismDesignTabAdapter

__all__ = [
    "TabAdapter",
    "ImageProcessingTabAdapter",
    "EditorTabAdapter",
    "MechanismDesignTabAdapter",
]
