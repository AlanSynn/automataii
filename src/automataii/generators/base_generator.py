"""Abstract base generator for automata components."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


# Define enums that might be missing
class BaseType(Enum):
    """Types of base structures."""
    BOX = "box"
    PEDESTAL = "pedestal"
    BODY_CAVITY = "body_cavity"
    CUSTOM = "custom"


# Try to import from core models, provide fallbacks if needed
try:
    from ..core.models import (
        MechanismType, MountingPoint, 
        MechanismData, Blueprint
    )
except ImportError:
    # Define minimal versions if imports fail
    from dataclasses import dataclass as dc
    from enum import Enum as E
    
    class MechanismType(E):
        FOUR_BAR = "four_bar"
        CAM_FOLLOWER = "cam_follower"
        GEAR_TRAIN = "gear_train"
        SLIDER_CRANK = "slider_crank"
    
    @dc
    class MountingPoint:
        id: str
        position: Tuple[float, float]
        height: float
        mechanism_type: Optional[Any]
        orientation: float
    
    @dc
    class MechanismData:
        mechanism_type: MechanismType
        position: Optional[Tuple[float, float]] = None
    
    @dc
    class Blueprint:
        layers: Dict[str, Any]
        metadata: Dict[str, Any]


@dataclass
class GeneratorConfig:
    """Base configuration for generators."""
    scale: float = 1.0
    material_thickness: float = 3.0  # mm
    tolerance: float = 0.1  # mm
    units: str = "mm"
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.scale <= 0:
            raise ValueError("Scale must be positive")
        if self.material_thickness <= 0:
            raise ValueError("Material thickness must be positive")
        if self.tolerance < 0:
            raise ValueError("Tolerance cannot be negative")
        if self.units not in ["mm", "cm", "in"]:
            raise ValueError(f"Unsupported units: {self.units}")


class BaseGenerator(ABC):
    """Abstract base class for all generators."""
    
    def __init__(self, config: GeneratorConfig):
        """Initialize generator with configuration.
        
        Args:
            config: Generator configuration
        """
        self.config = config
        self.config.validate()
        self._mounting_points: List[MountingPoint] = []
        self._generated_data: Dict[str, Any] = {}
    
    @abstractmethod
    def generate(self) -> Dict[str, Any]:
        """Generate the component.
        
        Returns:
            Dictionary containing generated component data
        """
        pass
    
    @abstractmethod
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters for generation.
        
        Raises:
            ValueError: If input is invalid
        """
        pass
    
    @abstractmethod
    def calculate_mounting_points(self) -> List[MountingPoint]:
        """Calculate mounting points for the component.
        
        Returns:
            List of mounting points
        """
        pass
    
    def get_mounting_points(self) -> List[MountingPoint]:
        """Get calculated mounting points.
        
        Returns:
            List of mounting points
        """
        return self._mounting_points
    
    def get_generated_data(self) -> Dict[str, Any]:
        """Get generated component data.
        
        Returns:
            Dictionary of generated data
        """
        return self._generated_data
    
    def transform_point(self, point: Tuple[float, float], 
                       offset: Tuple[float, float] = (0, 0),
                       rotation: float = 0) -> Tuple[float, float]:
        """Transform a point with offset and rotation.
        
        Args:
            point: Original point (x, y)
            offset: Translation offset (dx, dy)
            rotation: Rotation angle in radians
            
        Returns:
            Transformed point (x, y)
        """
        x, y = point
        if rotation != 0:
            cos_r = np.cos(rotation)
            sin_r = np.sin(rotation)
            x_new = x * cos_r - y * sin_r
            y_new = x * sin_r + y * cos_r
            x, y = x_new, y_new
        
        return (x + offset[0], y + offset[1])
    
    def scale_dimensions(self, dimensions: Dict[str, float]) -> Dict[str, float]:
        """Scale dimensions by the configured scale factor.
        
        Args:
            dimensions: Dictionary of dimension names to values
            
        Returns:
            Scaled dimensions
        """
        return {k: v * self.config.scale for k, v in dimensions.items()}
    
    def add_tolerance(self, dimension: float, is_hole: bool = False) -> float:
        """Add tolerance to a dimension.
        
        Args:
            dimension: Base dimension
            is_hole: If True, makes hole larger; if False, makes part smaller
            
        Returns:
            Dimension with tolerance applied
        """
        if is_hole:
            return dimension + self.config.tolerance
        else:
            return dimension - self.config.tolerance
    
    def create_blueprint_data(self, layers: Dict[str, List[Any]]) -> Dict[str, Any]:
        """Create blueprint data structure.
        
        Args:
            layers: Dictionary of layer names to shape lists
            
        Returns:
            Blueprint data dictionary
        """
        return {
            "layers": layers,
            "material_thickness": self.config.material_thickness,
            "units": self.config.units,
            "mounting_points": [mp.__dict__ for mp in self._mounting_points],
            "metadata": {
                "generator": self.__class__.__name__,
                "scale": self.config.scale,
                "tolerance": self.config.tolerance
            }
        }
    
    def validate_mechanisms(self, mechanisms: List[MechanismData]) -> None:
        """Validate that mechanisms can be accommodated.
        
        Args:
            mechanisms: List of mechanisms to validate
            
        Raises:
            ValueError: If mechanisms cannot be accommodated
        """
        if not mechanisms:
            raise ValueError("At least one mechanism is required")
        
        # Check for mechanism conflicts
        positions = []
        for mech in mechanisms:
            if hasattr(mech, 'position') and mech.position is not None:
                positions.append(mech.position)
        
        # Check for overlapping positions
        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions[i+1:], i+1):
                if pos1 is not None and pos2 is not None:
                    dist = np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
                    if dist < self.config.material_thickness * 2:
                        raise ValueError(
                            f"Mechanisms {i} and {j} are too close together"
                        )