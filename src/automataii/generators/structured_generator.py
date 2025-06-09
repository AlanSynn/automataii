"""Generator for structured bases (box and pedestal types)."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from .base_generator import BaseGenerator, GeneratorConfig, BaseType

# Import other required types with fallback
try:
    from ..core.models import MountingPoint, MechanismData, MechanismType
except ImportError:
    from .base_generator import MountingPoint, MechanismData, MechanismType


@dataclass
class BoxBase:
    """Configuration for box-type base."""
    width: float
    depth: float
    height: float
    wall_thickness: float = 5.0
    bottom_thickness: float = 5.0
    open_top: bool = True
    ventilation_holes: bool = True
    cable_management: bool = True


@dataclass
class PedestalBase:
    """Configuration for pedestal-type base."""
    base_diameter: float
    top_diameter: float
    height: float
    wall_thickness: float = 5.0
    num_supports: int = 4
    hollow: bool = True


class StructuredGenerator(BaseGenerator):
    """Generator for structured base components."""
    
    def __init__(self, config: GeneratorConfig, base_type: BaseType):
        """Initialize structured generator.
        
        Args:
            config: Generator configuration
            base_type: Type of base to generate
        """
        super().__init__(config)
        self.base_type = base_type
        self.base_config: Optional[Any] = None
        self.mechanisms: List[MechanismData] = []
    
    def set_box_config(self, box_config: BoxBase) -> None:
        """Set configuration for box base.
        
        Args:
            box_config: Box base configuration
        """
        if self.base_type != BaseType.BOX:
            raise ValueError("Base type must be BOX for box configuration")
        self.base_config = box_config
    
    def set_pedestal_config(self, pedestal_config: PedestalBase) -> None:
        """Set configuration for pedestal base.
        
        Args:
            pedestal_config: Pedestal base configuration
        """
        if self.base_type != BaseType.PEDESTAL:
            raise ValueError("Base type must be PEDESTAL for pedestal configuration")
        self.base_config = pedestal_config
    
    def add_mechanism(self, mechanism: MechanismData) -> None:
        """Add a mechanism to be accommodated.
        
        Args:
            mechanism: Mechanism data
        """
        self.mechanisms.append(mechanism)
    
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters."""
        if self.base_config is None:
            raise ValueError("Base configuration not set")
        
        if self.base_type == BaseType.BOX:
            self._validate_box_config()
        elif self.base_type == BaseType.PEDESTAL:
            self._validate_pedestal_config()
        
        self.validate_mechanisms(self.mechanisms)
    
    def _validate_box_config(self) -> None:
        """Validate box configuration."""
        config = self.base_config
        if config.width <= 0 or config.depth <= 0 or config.height <= 0:
            raise ValueError("Box dimensions must be positive")
        if config.wall_thickness <= 0 or config.bottom_thickness <= 0:
            raise ValueError("Thickness values must be positive")
    
    def _validate_pedestal_config(self) -> None:
        """Validate pedestal configuration."""
        config = self.base_config
        if config.base_diameter <= 0 or config.top_diameter <= 0:
            raise ValueError("Diameters must be positive")
        if config.height <= 0:
            raise ValueError("Height must be positive")
        if config.num_supports < 3:
            raise ValueError("Minimum 3 supports required")
    
    def generate(self) -> Dict[str, Any]:
        """Generate the structured base."""
        self.validate_input()
        
        if self.base_type == BaseType.BOX:
            return self._generate_box()
        elif self.base_type == BaseType.PEDESTAL:
            return self._generate_pedestal()
        else:
            raise ValueError(f"Unsupported base type: {self.base_type}")
    
    def _generate_box(self) -> Dict[str, Any]:
        """Generate box base structure."""
        config = self.base_config
        scaled = self.scale_dimensions({
            'width': config.width,
            'depth': config.depth,
            'height': config.height,
            'wall': config.wall_thickness,
            'bottom': config.bottom_thickness
        })
        
        layers = {}
        
        # Bottom panel
        layers['bottom'] = [{
            'type': 'rectangle',
            'x': 0,
            'y': 0,
            'width': scaled['width'],
            'height': scaled['depth'],
            'cuts': self._generate_box_cuts(scaled)
        }]
        
        # Side panels
        layers['front'] = [{
            'type': 'rectangle',
            'x': 0,
            'y': 0,
            'width': scaled['width'],
            'height': scaled['height'],
            'tabs': self._generate_tabs(scaled['width'], scaled['height'])
        }]
        
        layers['back'] = layers['front'].copy()
        
        layers['left'] = [{
            'type': 'rectangle',
            'x': 0,
            'y': 0,
            'width': scaled['depth'],
            'height': scaled['height'],
            'tabs': self._generate_tabs(scaled['depth'], scaled['height'])
        }]
        
        layers['right'] = layers['left'].copy()
        
        # Add ventilation if configured
        if config.ventilation_holes:
            self._add_ventilation(layers, scaled)
        
        # Calculate mounting points
        self._mounting_points = self.calculate_mounting_points()
        
        # Store generated data
        self._generated_data = self.create_blueprint_data(layers)
        self._generated_data['base_type'] = 'box'
        self._generated_data['dimensions'] = scaled
        
        return self._generated_data
    
    def _generate_pedestal(self) -> Dict[str, Any]:
        """Generate pedestal base structure."""
        config = self.base_config
        scaled = self.scale_dimensions({
            'base_dia': config.base_diameter,
            'top_dia': config.top_diameter,
            'height': config.height,
            'wall': config.wall_thickness
        })
        
        layers = {}
        
        # Base plate
        layers['base'] = [{
            'type': 'circle',
            'cx': 0,
            'cy': 0,
            'radius': scaled['base_dia'] / 2,
            'holes': self._generate_support_holes(scaled)
        }]
        
        # Top plate
        layers['top'] = [{
            'type': 'circle',
            'cx': 0,
            'cy': 0,
            'radius': scaled['top_dia'] / 2,
            'holes': self._generate_support_holes(scaled)
        }]
        
        # Support structures
        layers['supports'] = self._generate_supports(scaled)
        
        # Calculate mounting points
        self._mounting_points = self.calculate_mounting_points()
        
        # Store generated data
        self._generated_data = self.create_blueprint_data(layers)
        self._generated_data['base_type'] = 'pedestal'
        self._generated_data['dimensions'] = scaled
        
        return self._generated_data
    
    def calculate_mounting_points(self) -> List[MountingPoint]:
        """Calculate mounting points based on mechanisms."""
        mounting_points = []
        
        for i, mech in enumerate(self.mechanisms):
            # Calculate position based on mechanism type and base type
            if self.base_type == BaseType.BOX:
                point = self._calculate_box_mounting(mech, i)
            else:
                point = self._calculate_pedestal_mounting(mech, i)
            
            mounting_points.append(point)
        
        return mounting_points
    
    def _calculate_box_mounting(self, mech: MechanismData, index: int) -> MountingPoint:
        """Calculate mounting point for box base."""
        config = self.base_config
        
        # Default to center of top surface
        x = config.width / 2
        y = config.depth / 2
        z = config.height
        
        # Adjust based on mechanism requirements
        if hasattr(mech, 'position'):
            x, y = mech.position
        
        return MountingPoint(
            id=f"mount_{index}",
            position=(x * self.config.scale, y * self.config.scale),
            height=z * self.config.scale,
            mechanism_type=mech.mechanism_type,
            orientation=0
        )
    
    def _calculate_pedestal_mounting(self, mech: MechanismData, 
                                   index: int) -> MountingPoint:
        """Calculate mounting point for pedestal base."""
        config = self.base_config
        
        # Default to center of top surface
        x = 0
        y = 0
        z = config.height
        
        # For multiple mechanisms, arrange in circle
        if len(self.mechanisms) > 1:
            angle = 2 * np.pi * index / len(self.mechanisms)
            radius = config.top_diameter * 0.3  # 30% of top diameter
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
        
        return MountingPoint(
            id=f"mount_{index}",
            position=(x * self.config.scale, y * self.config.scale),
            height=z * self.config.scale,
            mechanism_type=mech.mechanism_type,
            orientation=angle if len(self.mechanisms) > 1 else 0
        )
    
    def _generate_tabs(self, width: float, height: float) -> List[Dict]:
        """Generate tab/slot pattern for joints."""
        tabs = []
        num_tabs = int(width / (self.config.material_thickness * 4))
        tab_width = width / (num_tabs * 2)
        
        for i in range(num_tabs):
            x = i * tab_width * 2
            tabs.append({
                'type': 'rectangle',
                'x': x,
                'y': 0,
                'width': tab_width,
                'height': self.config.material_thickness
            })
        
        return tabs
    
    def _generate_box_cuts(self, dimensions: Dict[str, float]) -> List[Dict]:
        """Generate cuts for box assembly."""
        # Simplified - would include slots for tabs
        return []
    
    def _generate_support_holes(self, dimensions: Dict[str, float]) -> List[Dict]:
        """Generate holes for pedestal supports."""
        holes = []
        config = self.base_config
        
        for i in range(config.num_supports):
            angle = 2 * np.pi * i / config.num_supports
            radius = dimensions['base_dia'] * 0.4
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            
            holes.append({
                'type': 'circle',
                'cx': x,
                'cy': y,
                'radius': self.config.material_thickness / 2
            })
        
        return holes
    
    def _generate_supports(self, dimensions: Dict[str, float]) -> List[Dict]:
        """Generate support structures for pedestal."""
        # Simplified - would generate actual support geometry
        return []
    
    def _add_ventilation(self, layers: Dict, dimensions: Dict[str, float]) -> None:
        """Add ventilation holes to panels."""
        # Simplified - would add actual ventilation pattern
        pass