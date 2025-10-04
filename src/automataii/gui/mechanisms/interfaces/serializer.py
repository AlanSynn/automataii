# Blueprint Serializer Interface
# Lines: ~100
# Public API: BlueprintSerializer, BlueprintData
# Deps In: All serializer implementations
# Deps Out: abc, dataclasses
# Coupling: Low (pure interface)
# Cohesion: Feature (serialization abstraction)
# Owner: Alan Synn
# Last Updated: 2025-01-20

"""
Interface for mechanism blueprint serialization.
Enables consistent export/import of mechanism designs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BlueprintData:
    """Container for blueprint data."""
    mechanism_type: str
    version: str
    dimensions: Dict[str, float]
    parameters: Dict[str, Any]
    visual_properties: Dict[str, Any]
    assembly_instructions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            'type': self.mechanism_type,
            'version': self.version,
            'dimensions': self.dimensions,
            'parameters': self.parameters,
            'visual_properties': self.visual_properties,
            'assembly_instructions': self.assembly_instructions or [],
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BlueprintData':
        """Create from imported dictionary."""
        return cls(
            mechanism_type=data['type'],
            version=data['version'],
            dimensions=data['dimensions'],
            parameters=data['parameters'],
            visual_properties=data['visual_properties'],
            assembly_instructions=data.get('assembly_instructions'),
            metadata=data.get('metadata')
        )


class BlueprintSerializer(ABC):
    """
    Abstract base class for blueprint serialization.
    
    Handles conversion between mechanism data and
    blueprint format for export/import.
    """
    
    @abstractmethod
    def serialize(self, mechanism_data: Dict[str, Any]) -> BlueprintData:
        """
        Serialize mechanism to blueprint format.
        
        Args:
            mechanism_data: Mechanism configuration and state
            
        Returns:
            Blueprint data ready for export
        """
        pass
    
    @abstractmethod
    def deserialize(self, blueprint_data: BlueprintData) -> Dict[str, Any]:
        """
        Deserialize blueprint to mechanism data.
        
        Args:
            blueprint_data: Imported blueprint data
            
        Returns:
            Mechanism configuration
        """
        pass
    
    @abstractmethod
    def export_to_svg(self, blueprint_data: BlueprintData) -> str:
        """
        Export blueprint as SVG.
        
        Args:
            blueprint_data: Blueprint to export
            
        Returns:
            SVG string
        """
        pass
    
    @abstractmethod
    def export_to_pdf(self, blueprint_data: BlueprintData, filepath: str) -> bool:
        """
        Export blueprint as PDF.
        
        Args:
            blueprint_data: Blueprint to export
            filepath: Output file path
            
        Returns:
            Success status
        """
        pass
    
    @abstractmethod
    def validate_blueprint(self, blueprint_data: BlueprintData) -> Tuple[bool, Optional[str]]:
        """
        Validate blueprint data.
        
        Args:
            blueprint_data: Blueprint to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass