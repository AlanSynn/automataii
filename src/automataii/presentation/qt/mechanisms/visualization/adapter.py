"""
Adapter to integrate new visualization system with existing mechanism_design_tab.

This provides a smooth transition from the old monolithic visualization methods
to the new modular system.
"""

import logging
from typing import Any, Callable, Optional

from PyQt6.QtWidgets import QGraphicsItem, QGraphicsScene

from .base import VisualizationConfig
from .factory import VisualizerFactory


class VisualizationAdapter:
    """
    Adapter class to bridge the new visualization system with existing code.
    
    This allows gradual migration from the old system to the new one without
    breaking existing functionality.
    """
    
    def __init__(self, scene: QGraphicsScene, 
                 transform_function: Optional[Callable] = None):
        """
        Initialize the adapter.
        
        Args:
            scene: Graphics scene to add visual items to
            transform_function: Function to transform mechanism coords to scene coords
        """
        self.scene = scene
        self.config = VisualizationConfig(transform_function=transform_function)
        self._visualizers: dict[str, Any] = {}
        self._visual_items: dict[str, list[QGraphicsItem]] = {}
    
    def create_mechanism_visuals(self, mechanism_id: str, 
                                mechanism_data: dict[str, Any]) -> list[QGraphicsItem]:
        """
        Create visuals for a mechanism using the new system.
        
        Args:
            mechanism_id: Unique identifier for the mechanism
            mechanism_data: Mechanism configuration and state
            
        Returns:
            List of created visual items
        """
        mechanism_type = mechanism_data.get("type")
        if not mechanism_type:
            logging.warning(f"No type specified for mechanism {mechanism_id}")
            return []
        
        # Update transform function if provided
        if "transform_function" in mechanism_data:
            self.config.transform_function = mechanism_data["transform_function"]
        
        # Get or create visualizer
        if mechanism_id not in self._visualizers:
            visualizer = VisualizerFactory.create(mechanism_type, self.config)
            if not visualizer:
                logging.warning(f"No visualizer available for type {mechanism_type}")
                return []
            self._visualizers[mechanism_id] = visualizer
        else:
            visualizer = self._visualizers[mechanism_id]
        
        # Clean up old visuals if they exist
        if mechanism_id in self._visual_items:
            self.cleanup_mechanism_visuals(mechanism_id)
        
        # Create new visuals
        visual_items = visualizer.create_visuals(mechanism_data)
        
        # Add to scene
        for item in visual_items:
            if item and not item.scene():
                self.scene.addItem(item)
        
        # Store for later reference
        self._visual_items[mechanism_id] = visual_items
        
        return visual_items
    
    def update_mechanism_visuals(self, mechanism_id: str, 
                                mechanism_data: dict[str, Any]) -> None:
        """
        Update existing visuals for a mechanism.
        
        Args:
            mechanism_id: Unique identifier for the mechanism
            mechanism_data: Updated mechanism configuration and state
        """
        if mechanism_id not in self._visualizers:
            # Try to create visualizer if it doesn't exist
            visual_items = self.create_mechanism_visuals(mechanism_id, mechanism_data)
            if visual_items:
                logging.debug(f"Created new visuals for {mechanism_id} during update")
            return
        
        # Update transform function if provided
        if "transform_function" in mechanism_data:
            self.config.transform_function = mechanism_data["transform_function"]
        
        visualizer = self._visualizers[mechanism_id]
        visual_items = self._visual_items.get(mechanism_id, [])
        
        if visual_items:
            visualizer.update_visuals(visual_items, mechanism_data)
            logging.debug(f"Updated visuals for mechanism {mechanism_id}")
    
    def cleanup_mechanism_visuals(self, mechanism_id: str) -> None:
        """
        Clean up visuals for a mechanism.
        
        Args:
            mechanism_id: Unique identifier for the mechanism
        """
        if mechanism_id in self._visual_items:
            visual_items = self._visual_items[mechanism_id]
            
            # Remove from scene
            for item in visual_items:
                if item and item.scene() == self.scene:
                    self.scene.removeItem(item)
            
            # Clear from storage
            del self._visual_items[mechanism_id]
        
        # Clean up visualizer if needed
        if mechanism_id in self._visualizers:
            del self._visualizers[mechanism_id]
    
    def cleanup_all_visuals(self) -> None:
        """Clean up all visual items and visualizers."""
        mechanism_ids = list(self._visual_items.keys())
        for mechanism_id in mechanism_ids:
            self.cleanup_mechanism_visuals(mechanism_id)
        
        self._visualizers.clear()
        self._visual_items.clear()
    
    @staticmethod
    def migrate_mechanism_data(old_data: dict[str, Any]) -> dict[str, Any]:
        """
        Migrate old mechanism data format to new format if needed.
        
        Args:
            old_data: Original mechanism data
            
        Returns:
            Migrated mechanism data compatible with new system
        """
        # For now, just pass through - add migration logic as needed
        return old_data