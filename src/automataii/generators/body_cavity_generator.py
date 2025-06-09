"""Generator for body-mounted mechanism cavities."""

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
class CavityConfig:
    """Configuration for body cavity generation."""
    body_thickness: float
    cavity_depth: float
    wall_clearance: float = 2.0
    reinforcement: bool = True
    access_panel: bool = True
    mounting_bosses: bool = True
    
    # Body shape parameters
    body_outline: Optional[List[Tuple[float, float]]] = None
    body_center: Tuple[float, float] = (0, 0)
    body_bounds: Optional[Tuple[float, float, float, float]] = None  # x,y,w,h


class BodyCavityGenerator(BaseGenerator):
    """Generator for cavities within character bodies."""
    
    def __init__(self, config: GeneratorConfig):
        """Initialize body cavity generator.
        
        Args:
            config: Generator configuration
        """
        super().__init__(config)
        self.cavity_config: Optional[CavityConfig] = None
        self.mechanisms: List[MechanismData] = []
        self.cavity_regions: List[Dict[str, Any]] = []
    
    def set_cavity_config(self, cavity_config: CavityConfig) -> None:
        """Set cavity configuration.
        
        Args:
            cavity_config: Cavity configuration
        """
        self.cavity_config = cavity_config
    
    def set_body_shape(self, outline: List[Tuple[float, float]]) -> None:
        """Set the body outline shape.
        
        Args:
            outline: List of (x, y) points defining body outline
        """
        if self.cavity_config is None:
            raise ValueError("Cavity configuration must be set first")
        
        self.cavity_config.body_outline = outline
        
        # Calculate bounds
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        self.cavity_config.body_bounds = (
            min(xs), min(ys), 
            max(xs) - min(xs), 
            max(ys) - min(ys)
        )
        
        # Calculate center
        self.cavity_config.body_center = (
            (min(xs) + max(xs)) / 2,
            (min(ys) + max(ys)) / 2
        )
    
    def add_mechanism(self, mechanism: MechanismData, 
                     position: Tuple[float, float]) -> None:
        """Add a mechanism to be housed in the body.
        
        Args:
            mechanism: Mechanism data
            position: Position within body (x, y)
        """
        # Store position with mechanism
        if hasattr(mechanism, 'position'):
            mechanism.position = position
        self.mechanisms.append(mechanism)
    
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters."""
        if self.cavity_config is None:
            raise ValueError("Cavity configuration not set")
        
        config = self.cavity_config
        
        if config.body_thickness <= 0:
            raise ValueError("Body thickness must be positive")
        if config.cavity_depth <= 0:
            raise ValueError("Cavity depth must be positive")
        if config.cavity_depth >= config.body_thickness:
            raise ValueError("Cavity depth must be less than body thickness")
        
        if config.body_outline is None:
            raise ValueError("Body shape not set")
        
        # Validate mechanisms fit within body
        self._validate_mechanism_fit()
    
    def _validate_mechanism_fit(self) -> None:
        """Validate that mechanisms fit within body bounds."""
        if not self.cavity_config.body_bounds:
            return
        
        bx, by, bw, bh = self.cavity_config.body_bounds
        
        for mech in self.mechanisms:
            if hasattr(mech, 'position'):
                x, y = mech.position
                # Check if mechanism center is within bounds
                if not (bx <= x <= bx + bw and by <= y <= by + bh):
                    raise ValueError(
                        f"Mechanism at ({x}, {y}) is outside body bounds"
                    )
    
    def generate(self) -> Dict[str, Any]:
        """Generate body cavity structure."""
        self.validate_input()
        
        # Calculate cavity regions for each mechanism
        self._calculate_cavity_regions()
        
        layers = {}
        
        # Generate cavity cutouts
        layers['cavities'] = self._generate_cavity_cutouts()
        
        # Generate reinforcement structures
        if self.cavity_config.reinforcement:
            layers['reinforcement'] = self._generate_reinforcement()
        
        # Generate access panels
        if self.cavity_config.access_panel:
            layers['access_panels'] = self._generate_access_panels()
        
        # Generate mounting features
        if self.cavity_config.mounting_bosses:
            layers['mounting'] = self._generate_mounting_bosses()
        
        # Calculate mounting points
        self._mounting_points = self.calculate_mounting_points()
        
        # Store generated data
        self._generated_data = self.create_blueprint_data(layers)
        self._generated_data['cavity_type'] = 'body_mounted'
        self._generated_data['cavity_regions'] = self.cavity_regions
        
        return self._generated_data
    
    def calculate_mounting_points(self) -> List[MountingPoint]:
        """Calculate mounting points for mechanisms."""
        mounting_points = []
        
        for i, (mech, region) in enumerate(zip(self.mechanisms, self.cavity_regions)):
            # Create mounting point at cavity center
            point = MountingPoint(
                id=f"cavity_mount_{i}",
                position=(region['center'][0], region['center'][1]),
                height=self.cavity_config.body_thickness - self.cavity_config.cavity_depth,
                mechanism_type=mech.mechanism_type,
                orientation=region.get('orientation', 0)
            )
            mounting_points.append(point)
        
        return mounting_points
    
    def _calculate_cavity_regions(self) -> None:
        """Calculate optimal cavity regions for mechanisms."""
        self.cavity_regions = []
        
        for mech in self.mechanisms:
            # Get mechanism footprint
            footprint = self._get_mechanism_footprint(mech)
            
            # Find optimal cavity position
            if hasattr(mech, 'position'):
                center = mech.position
            else:
                center = self.cavity_config.body_center
            
            # Calculate cavity bounds with clearance
            clearance = self.cavity_config.wall_clearance * self.config.scale
            width = footprint['width'] + 2 * clearance
            height = footprint['height'] + 2 * clearance
            
            region = {
                'center': center,
                'width': width,
                'height': height,
                'depth': self.cavity_config.cavity_depth * self.config.scale,
                'mechanism_type': mech.mechanism_type,
                'orientation': 0
            }
            
            self.cavity_regions.append(region)
    
    def _get_mechanism_footprint(self, mechanism: MechanismData) -> Dict[str, float]:
        """Get mechanism footprint dimensions."""
        # Default footprints by mechanism type
        footprints = {
            MechanismType.FOUR_BAR: {'width': 50, 'height': 40},
            MechanismType.CAM_FOLLOWER: {'width': 30, 'height': 30},
            MechanismType.GEAR_TRAIN: {'width': 40, 'height': 40},
            MechanismType.SLIDER_CRANK: {'width': 60, 'height': 30},
        }
        
        default = {'width': 40, 'height': 40}
        footprint = footprints.get(mechanism.mechanism_type, default)
        
        # Scale footprint
        return {
            'width': footprint['width'] * self.config.scale,
            'height': footprint['height'] * self.config.scale
        }
    
    def _generate_cavity_cutouts(self) -> List[Dict[str, Any]]:
        """Generate cavity cutout shapes."""
        cutouts = []
        
        for region in self.cavity_regions:
            # Basic rectangular cavity
            cutout = {
                'type': 'rectangle',
                'x': region['center'][0] - region['width'] / 2,
                'y': region['center'][1] - region['height'] / 2,
                'width': region['width'],
                'height': region['height'],
                'depth': region['depth'],
                'corners_rounded': True,
                'corner_radius': self.config.material_thickness
            }
            
            # Add mechanism-specific features
            if region['mechanism_type'] == MechanismType.GEAR_TRAIN:
                # Add shaft holes
                cutout['shaft_holes'] = self._add_shaft_holes(region)
            
            cutouts.append(cutout)
        
        return cutouts
    
    def _generate_reinforcement(self) -> List[Dict[str, Any]]:
        """Generate reinforcement ribs around cavities."""
        reinforcements = []
        
        for region in self.cavity_regions:
            # Create reinforcement ribs
            rib_width = self.config.material_thickness
            offset = region['width'] / 2 + rib_width
            
            ribs = [
                # Top rib
                {
                    'type': 'rectangle',
                    'x': region['center'][0] - offset,
                    'y': region['center'][1] + region['height'] / 2,
                    'width': region['width'] + 2 * rib_width,
                    'height': rib_width
                },
                # Bottom rib
                {
                    'type': 'rectangle',
                    'x': region['center'][0] - offset,
                    'y': region['center'][1] - region['height'] / 2 - rib_width,
                    'width': region['width'] + 2 * rib_width,
                    'height': rib_width
                }
            ]
            
            reinforcements.extend(ribs)
        
        return reinforcements
    
    def _generate_access_panels(self) -> List[Dict[str, Any]]:
        """Generate removable access panels."""
        panels = []
        
        for i, region in enumerate(self.cavity_regions):
            panel = {
                'type': 'rectangle',
                'x': region['center'][0] - region['width'] / 2,
                'y': region['center'][1] - region['height'] / 2,
                'width': region['width'],
                'height': region['height'],
                'id': f'access_panel_{i}',
                'removable': True,
                'fasteners': self._add_fastener_holes(region)
            }
            panels.append(panel)
        
        return panels
    
    def _generate_mounting_bosses(self) -> List[Dict[str, Any]]:
        """Generate mounting bosses for mechanism attachment."""
        bosses = []
        
        for region in self.cavity_regions:
            # Create mounting bosses at corners
            boss_radius = self.config.material_thickness * 1.5
            positions = [
                (-1, -1), (1, -1), (-1, 1), (1, 1)  # Corner positions
            ]
            
            for px, py in positions:
                x = region['center'][0] + px * (region['width'] / 2 - boss_radius)
                y = region['center'][1] + py * (region['height'] / 2 - boss_radius)
                
                boss = {
                    'type': 'circle',
                    'cx': x,
                    'cy': y,
                    'radius': boss_radius,
                    'hole_radius': self.config.material_thickness / 2,
                    'reinforced': True
                }
                bosses.append(boss)
        
        return bosses
    
    def _add_shaft_holes(self, region: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add shaft holes for gear mechanisms."""
        holes = []
        # Simplified - would calculate actual shaft positions
        hole = {
            'type': 'circle',
            'cx': region['center'][0],
            'cy': region['center'][1],
            'radius': 3 * self.config.scale
        }
        holes.append(hole)
        return holes
    
    def _add_fastener_holes(self, region: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add fastener holes for access panels."""
        holes = []
        # Simplified - would add actual fastener pattern
        return holes