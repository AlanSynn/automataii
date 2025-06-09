"""Generator for axis systems (shafts, bearings, couplings)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from .base_generator import BaseGenerator, GeneratorConfig


# Define enums for axis systems
class AxisType(Enum):
    """Types of axis configurations."""
    STRAIGHT = "straight"
    STEPPED = "stepped"
    TAPERED = "tapered"
    SPLINED = "splined"


class BearingType(Enum):
    """Types of bearings."""
    BUSHING = "bushing"
    BALL_BEARING = "ball_bearing"
    ROLLER_BEARING = "roller_bearing"
    THRUST_BEARING = "thrust_bearing"
    PLAIN_BEARING = "plain_bearing"


# Import other required types
try:
    from ..core.models import MountingPoint, MechanismData, MechanismType
except ImportError:
    # Define minimal versions if imports fail
    from dataclasses import dataclass as dc
    from enum import Enum as E
    
    @dc
    class MountingPoint:
        id: str
        position: Tuple[float, float]
        height: float
        mechanism_type: Optional[Any]
        orientation: float
    
    @dc
    class MechanismData:
        mechanism_type: Any
        position: Optional[Tuple[float, float]] = None
    
    class MechanismType(E):
        FOUR_BAR = "four_bar"
        CAM_FOLLOWER = "cam_follower"
        GEAR_TRAIN = "gear_train"
        SLIDER_CRANK = "slider_crank"


@dataclass
class AxisConfig:
    """Configuration for axis system generation."""
    shaft_diameter: float = 6.0  # mm
    bearing_type: BearingType = BearingType.BUSHING
    coupling_type: str = "rigid"  # rigid, flexible, universal
    support_spacing: float = 50.0  # mm
    material: str = "steel"
    
    # Bearing parameters
    bearing_od: Optional[float] = None
    bearing_length: Optional[float] = None
    bearing_clearance: float = 0.1
    
    # Support parameters
    support_thickness: float = 5.0
    support_height: float = 20.0
    adjustable_height: bool = False


@dataclass
class AxisSegment:
    """Represents a segment of an axis."""
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    diameter: float
    bearing_positions: List[float] = field(default_factory=list)
    features: List[str] = field(default_factory=list)


class AxisGenerator(BaseGenerator):
    """Generator for complete axis systems."""
    
    def __init__(self, config: GeneratorConfig):
        """Initialize axis generator.
        
        Args:
            config: Generator configuration
        """
        super().__init__(config)
        self.axis_config: Optional[AxisConfig] = None
        self.axis_segments: List[AxisSegment] = []
        self.mechanisms: List[MechanismData] = []
        self.connection_points: List[Tuple[float, float, float]] = []
    
    def set_axis_config(self, axis_config: AxisConfig) -> None:
        """Set axis configuration.
        
        Args:
            axis_config: Axis system configuration
        """
        self.axis_config = axis_config
        
        # Set default bearing dimensions if not provided
        if axis_config.bearing_od is None:
            axis_config.bearing_od = axis_config.shaft_diameter + 4.0
        if axis_config.bearing_length is None:
            axis_config.bearing_length = axis_config.shaft_diameter * 1.5
    
    def add_mechanism_connection(self, mechanism: MechanismData,
                               connection_point: Tuple[float, float, float]) -> None:
        """Add a mechanism that connects to the axis.
        
        Args:
            mechanism: Mechanism requiring axis connection
            connection_point: 3D point where mechanism connects (x, y, z)
        """
        self.mechanisms.append(mechanism)
        self.connection_points.append(connection_point)
    
    def add_axis_segment(self, start: Tuple[float, float, float],
                        end: Tuple[float, float, float],
                        diameter: Optional[float] = None) -> None:
        """Add an axis segment.
        
        Args:
            start: Start point (x, y, z)
            end: End point (x, y, z)
            diameter: Shaft diameter (uses config default if None)
        """
        if diameter is None:
            diameter = self.axis_config.shaft_diameter
        
        segment = AxisSegment(
            start_point=start,
            end_point=end,
            diameter=diameter * self.config.scale
        )
        
        # Calculate bearing positions
        segment.bearing_positions = self._calculate_bearing_positions(segment)
        
        self.axis_segments.append(segment)
    
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters."""
        if self.axis_config is None:
            raise ValueError("Axis configuration not set")
        
        config = self.axis_config
        
        if config.shaft_diameter <= 0:
            raise ValueError("Shaft diameter must be positive")
        if config.support_spacing <= 0:
            raise ValueError("Support spacing must be positive")
        if config.bearing_clearance < 0:
            raise ValueError("Bearing clearance cannot be negative")
        
        if not self.axis_segments:
            raise ValueError("At least one axis segment required")
        
        # Validate bearing dimensions
        if config.bearing_od <= config.shaft_diameter:
            raise ValueError("Bearing OD must be larger than shaft diameter")
    
    def generate(self) -> Dict[str, Any]:
        """Generate complete axis system."""
        self.validate_input()
        
        layers = {}
        
        # Generate shaft components
        layers['shafts'] = self._generate_shafts()
        
        # Generate bearings
        layers['bearings'] = self._generate_bearings()
        
        # Generate supports
        layers['supports'] = self._generate_supports()
        
        # Generate couplings
        if len(self.axis_segments) > 1:
            layers['couplings'] = self._generate_couplings()
        
        # Generate mechanism interfaces
        layers['interfaces'] = self._generate_mechanism_interfaces()
        
        # Calculate mounting points
        self._mounting_points = self.calculate_mounting_points()
        
        # Store generated data
        self._generated_data = self.create_blueprint_data(layers)
        self._generated_data['axis_type'] = 'multi_segment'
        self._generated_data['total_length'] = self._calculate_total_length()
        
        return self._generated_data
    
    def calculate_mounting_points(self) -> List[MountingPoint]:
        """Calculate mounting points for axis system."""
        mounting_points = []
        
        # Add mounting points for each bearing position
        for seg_idx, segment in enumerate(self.axis_segments):
            for bear_idx, position in enumerate(segment.bearing_positions):
                # Calculate 3D position along segment
                t = position  # Normalized position along segment
                point_3d = self._interpolate_3d_point(
                    segment.start_point, segment.end_point, t
                )
                
                mount = MountingPoint(
                    id=f"bearing_{seg_idx}_{bear_idx}",
                    position=(point_3d[0], point_3d[1]),
                    height=point_3d[2],
                    mechanism_type=None,  # Bearing mount
                    orientation=self._calculate_segment_angle(segment)
                )
                mounting_points.append(mount)
        
        # Add mounting points for mechanism connections
        for i, (mech, conn_point) in enumerate(zip(self.mechanisms, self.connection_points)):
            mount = MountingPoint(
                id=f"mechanism_{i}",
                position=(conn_point[0], conn_point[1]),
                height=conn_point[2],
                mechanism_type=mech.mechanism_type,
                orientation=0
            )
            mounting_points.append(mount)
        
        return mounting_points
    
    def _calculate_bearing_positions(self, segment: AxisSegment) -> List[float]:
        """Calculate optimal bearing positions along segment."""
        length = self._segment_length(segment)
        spacing = self.axis_config.support_spacing * self.config.scale
        
        # Calculate number of bearings needed
        num_bearings = max(2, int(length / spacing) + 1)
        
        # Distribute bearings evenly
        positions = []
        for i in range(num_bearings):
            t = i / (num_bearings - 1) if num_bearings > 1 else 0.5
            positions.append(t)
        
        return positions
    
    def _generate_shafts(self) -> List[Dict[str, Any]]:
        """Generate shaft geometry."""
        shafts = []
        
        for i, segment in enumerate(self.axis_segments):
            # Calculate shaft profile
            length = self._segment_length(segment)
            
            shaft = {
                'type': 'cylinder',
                'id': f'shaft_{i}',
                'start': segment.start_point,
                'end': segment.end_point,
                'diameter': segment.diameter,
                'length': length,
                'features': self._generate_shaft_features(segment)
            }
            
            shafts.append(shaft)
        
        return shafts
    
    def _generate_bearings(self) -> List[Dict[str, Any]]:
        """Generate bearing components."""
        bearings = []
        config = self.axis_config
        
        for seg_idx, segment in enumerate(self.axis_segments):
            for bear_idx, position in enumerate(segment.bearing_positions):
                # Calculate bearing position
                point_3d = self._interpolate_3d_point(
                    segment.start_point, segment.end_point, position
                )
                
                bearing = {
                    'type': 'bearing',
                    'id': f'bearing_{seg_idx}_{bear_idx}',
                    'position': point_3d,
                    'inner_diameter': segment.diameter + config.bearing_clearance,
                    'outer_diameter': config.bearing_od * self.config.scale,
                    'length': config.bearing_length * self.config.scale,
                    'bearing_type': config.bearing_type.value
                }
                
                bearings.append(bearing)
        
        return bearings
    
    def _generate_supports(self) -> List[Dict[str, Any]]:
        """Generate bearing support structures."""
        supports = []
        config = self.axis_config
        
        for seg_idx, segment in enumerate(self.axis_segments):
            for bear_idx, position in enumerate(segment.bearing_positions):
                # Calculate support position
                point_3d = self._interpolate_3d_point(
                    segment.start_point, segment.end_point, position
                )
                
                # Create support structure
                support = {
                    'type': 'support',
                    'id': f'support_{seg_idx}_{bear_idx}',
                    'base_position': (point_3d[0], point_3d[1], 0),
                    'height': point_3d[2] if not config.adjustable_height else None,
                    'thickness': config.support_thickness * self.config.scale,
                    'width': config.bearing_od * self.config.scale * 1.5,
                    'adjustable': config.adjustable_height,
                    'mounting_holes': self._generate_mounting_holes()
                }
                
                supports.append(support)
        
        return supports
    
    def _generate_couplings(self) -> List[Dict[str, Any]]:
        """Generate coupling components between segments."""
        couplings = []
        
        for i in range(len(self.axis_segments) - 1):
            seg1 = self.axis_segments[i]
            seg2 = self.axis_segments[i + 1]
            
            # Check if segments connect
            if np.allclose(seg1.end_point, seg2.start_point):
                coupling = {
                    'type': 'coupling',
                    'id': f'coupling_{i}',
                    'position': seg1.end_point,
                    'coupling_type': self.axis_config.coupling_type,
                    'diameter1': seg1.diameter,
                    'diameter2': seg2.diameter,
                    'length': max(seg1.diameter, seg2.diameter) * 2
                }
                couplings.append(coupling)
        
        return couplings
    
    def _generate_mechanism_interfaces(self) -> List[Dict[str, Any]]:
        """Generate interfaces for mechanism connections."""
        interfaces = []
        
        for i, (mech, point) in enumerate(zip(self.mechanisms, self.connection_points)):
            # Find closest shaft segment
            segment, t = self._find_closest_segment(point)
            
            interface = {
                'type': 'interface',
                'id': f'interface_{i}',
                'position': point,
                'mechanism_type': mech.mechanism_type.value,
                'shaft_diameter': segment.diameter,
                'interface_type': self._get_interface_type(mech)
            }
            
            # Add mechanism-specific features
            if mech.mechanism_type == MechanismType.GEAR_TRAIN:
                interface['keyway'] = True
                interface['set_screw'] = True
            elif mech.mechanism_type == MechanismType.CAM_FOLLOWER:
                interface['cam_mount'] = True
            
            interfaces.append(interface)
        
        return interfaces
    
    def _generate_shaft_features(self, segment: AxisSegment) -> List[Dict[str, Any]]:
        """Generate features on shaft (keyways, threads, etc.)."""
        features = []
        
        # Add keyways at mechanism connection points
        for mech, point in zip(self.mechanisms, self.connection_points):
            if self._point_on_segment(point, segment):
                feature = {
                    'type': 'keyway',
                    'position': self._project_point_to_segment(point, segment),
                    'width': segment.diameter * 0.25,
                    'depth': segment.diameter * 0.125,
                    'length': segment.diameter * 2
                }
                features.append(feature)
        
        return features
    
    def _generate_mounting_holes(self) -> List[Dict[str, Any]]:
        """Generate mounting hole pattern."""
        holes = []
        # Simplified - would generate actual mounting pattern
        for i in range(4):
            angle = i * np.pi / 2
            radius = self.axis_config.bearing_od * self.config.scale * 0.7
            hole = {
                'type': 'circle',
                'cx': radius * np.cos(angle),
                'cy': radius * np.sin(angle),
                'radius': 2.5 * self.config.scale
            }
            holes.append(hole)
        return holes
    
    def _segment_length(self, segment: AxisSegment) -> float:
        """Calculate length of axis segment."""
        return np.linalg.norm(
            np.array(segment.end_point) - np.array(segment.start_point)
        )
    
    def _calculate_segment_angle(self, segment: AxisSegment) -> float:
        """Calculate angle of segment in XY plane."""
        dx = segment.end_point[0] - segment.start_point[0]
        dy = segment.end_point[1] - segment.start_point[1]
        return np.arctan2(dy, dx)
    
    def _interpolate_3d_point(self, start: Tuple[float, float, float],
                             end: Tuple[float, float, float], 
                             t: float) -> Tuple[float, float, float]:
        """Interpolate point along 3D line."""
        return tuple(
            start[i] + t * (end[i] - start[i]) for i in range(3)
        )
    
    def _find_closest_segment(self, point: Tuple[float, float, float]) -> Tuple[AxisSegment, float]:
        """Find closest segment to a point."""
        min_dist = float('inf')
        closest_segment = self.axis_segments[0]
        closest_t = 0
        
        for segment in self.axis_segments:
            t = self._closest_point_on_segment(point, segment)
            closest_point = self._interpolate_3d_point(
                segment.start_point, segment.end_point, t
            )
            dist = np.linalg.norm(
                np.array(point) - np.array(closest_point)
            )
            
            if dist < min_dist:
                min_dist = dist
                closest_segment = segment
                closest_t = t
        
        return closest_segment, closest_t
    
    def _closest_point_on_segment(self, point: Tuple[float, float, float],
                                 segment: AxisSegment) -> float:
        """Find parametric position of closest point on segment."""
        # Vector from start to end
        v = np.array(segment.end_point) - np.array(segment.start_point)
        # Vector from start to point
        w = np.array(point) - np.array(segment.start_point)
        
        # Project w onto v
        t = np.dot(w, v) / np.dot(v, v)
        
        # Clamp to [0, 1]
        return max(0, min(1, t))
    
    def _point_on_segment(self, point: Tuple[float, float, float],
                         segment: AxisSegment, tolerance: float = 1e-3) -> bool:
        """Check if point lies on segment."""
        t = self._closest_point_on_segment(point, segment)
        closest = self._interpolate_3d_point(
            segment.start_point, segment.end_point, t
        )
        return np.linalg.norm(np.array(point) - np.array(closest)) < tolerance
    
    def _project_point_to_segment(self, point: Tuple[float, float, float],
                                 segment: AxisSegment) -> float:
        """Project point to segment and return parametric position."""
        return self._closest_point_on_segment(point, segment)
    
    def _get_interface_type(self, mechanism: MechanismData) -> str:
        """Determine interface type based on mechanism."""
        interface_map = {
            MechanismType.GEAR_TRAIN: "keyed",
            MechanismType.CAM_FOLLOWER: "clamped",
            MechanismType.FOUR_BAR: "pinned",
            MechanismType.SLIDER_CRANK: "pinned"
        }
        return interface_map.get(mechanism.mechanism_type, "fixed")
    
    def _calculate_total_length(self) -> float:
        """Calculate total length of all axis segments."""
        return sum(self._segment_length(seg) for seg in self.axis_segments)