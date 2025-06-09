"""Adapter for connecting mechanisms to automata bases."""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from dataclasses import dataclass

from ..core.models import Mechanism
from ..generation.base_mechanism import BaseMechanism


@dataclass
class ConnectionPoint:
    """Represents a connection point between mechanism and base."""
    position: Tuple[float, float, float]
    normal: Tuple[float, float, float]
    type: str  # 'motor', 'support', 'output'
    diameter: float = 6.0  # mm


@dataclass
class MechanismPlacement:
    """Defines how a mechanism is placed on a base."""
    mechanism_id: str
    base_position: Tuple[float, float, float]
    rotation: Tuple[float, float, float]  # Euler angles
    scale: float = 1.0
    connection_points: List[ConnectionPoint]


class MechanismAdapter:
    """Adapts mechanisms for integration with automata bases."""
    
    def __init__(self):
        self.placements: Dict[str, MechanismPlacement] = {}
        self.clearance_margin = 5.0  # mm
        
    def add_mechanism(self, mechanism: BaseMechanism, base_type: str) -> MechanismPlacement:
        """Add a mechanism and calculate optimal placement on base."""
        # Extract mechanism dimensions
        bounds = self._calculate_mechanism_bounds(mechanism)
        
        # Determine connection points based on mechanism type
        connection_points = self._identify_connection_points(mechanism)
        
        # Calculate optimal position on base
        position = self._calculate_optimal_position(bounds, base_type)
        
        # Create placement
        placement = MechanismPlacement(
            mechanism_id=mechanism.id,
            base_position=position,
            rotation=(0, 0, 0),
            connection_points=connection_points
        )
        
        self.placements[mechanism.id] = placement
        return placement
        
    def _calculate_mechanism_bounds(self, mechanism: BaseMechanism) -> Dict[str, float]:
        """Calculate bounding box of mechanism."""
        # Get all points from mechanism
        points = []
        
        # Extract points based on mechanism type
        if hasattr(mechanism, 'links'):
            for link in mechanism.links:
                if hasattr(link, 'start') and hasattr(link, 'end'):
                    points.extend([link.start, link.end])
                    
        if hasattr(mechanism, 'joints'):
            for joint in mechanism.joints:
                if hasattr(joint, 'position'):
                    points.append(joint.position)
                    
        if not points:
            # Default bounds if no points found
            return {
                'min_x': -50, 'max_x': 50,
                'min_y': -50, 'max_y': 50,
                'min_z': 0, 'max_z': 100
            }
            
        # Convert to numpy array
        np_points = np.array([(p[0], p[1], getattr(p, 'z', 0)) for p in points])
        
        return {
            'min_x': np_points[:, 0].min(),
            'max_x': np_points[:, 0].max(),
            'min_y': np_points[:, 1].min(),
            'max_y': np_points[:, 1].max(),
            'min_z': np_points[:, 2].min() if np_points.shape[1] > 2 else 0,
            'max_z': np_points[:, 2].max() if np_points.shape[1] > 2 else 100
        }
        
    def _identify_connection_points(self, mechanism: BaseMechanism) -> List[ConnectionPoint]:
        """Identify where mechanism connects to base."""
        points = []
        
        # Motor connection (typically at crank pivot)
        if hasattr(mechanism, 'crank_pivot'):
            points.append(ConnectionPoint(
                position=(mechanism.crank_pivot[0], mechanism.crank_pivot[1], 0),
                normal=(0, 0, 1),
                type='motor',
                diameter=8.0
            ))
            
        # Support connections (fixed pivots)
        if hasattr(mechanism, 'fixed_pivots'):
            for i, pivot in enumerate(mechanism.fixed_pivots):
                points.append(ConnectionPoint(
                    position=(pivot[0], pivot[1], 0),
                    normal=(0, 0, 1),
                    type='support',
                    diameter=6.0
                ))
                
        # If no specific points found, use center bottom
        if not points:
            points.append(ConnectionPoint(
                position=(0, 0, 0),
                normal=(0, 0, 1),
                type='support'
            ))
            
        return points
        
    def _calculate_optimal_position(self, bounds: Dict[str, float], base_type: str) -> Tuple[float, float, float]:
        """Calculate optimal position for mechanism on base."""
        # Center mechanism on base
        center_x = -(bounds['min_x'] + bounds['max_x']) / 2
        center_y = -(bounds['min_y'] + bounds['max_y']) / 2
        
        # Height depends on base type
        base_heights = {
            'rectangular': 50,
            'cylindrical': 60,
            'custom': 40
        }
        z_offset = base_heights.get(base_type, 50)
        
        return (center_x, center_y, z_offset)
        
    def check_clearance(self, mechanism_id: str, other_mechanisms: List[str]) -> bool:
        """Check if mechanism has clearance from others."""
        if mechanism_id not in self.placements:
            return False
            
        placement = self.placements[mechanism_id]
        
        for other_id in other_mechanisms:
            if other_id == mechanism_id or other_id not in self.placements:
                continue
                
            other = self.placements[other_id]
            
            # Simple distance check (can be made more sophisticated)
            dist = np.linalg.norm(
                np.array(placement.base_position) - np.array(other.base_position)
            )
            
            if dist < self.clearance_margin:
                return False
                
        return True
        
    def get_connection_mappings(self, mechanism_id: str) -> Dict[str, Any]:
        """Get connection point mappings for manufacturing."""
        if mechanism_id not in self.placements:
            return {}
            
        placement = self.placements[mechanism_id]
        
        mappings = {
            'motor_connections': [],
            'support_connections': [],
            'output_connections': []
        }
        
        for point in placement.connection_points:
            connection_info = {
                'position': point.position,
                'normal': point.normal,
                'diameter': point.diameter,
                'world_position': self._transform_to_world(
                    point.position, placement.base_position, placement.rotation
                )
            }
            
            if point.type == 'motor':
                mappings['motor_connections'].append(connection_info)
            elif point.type == 'support':
                mappings['support_connections'].append(connection_info)
            else:
                mappings['output_connections'].append(connection_info)
                
        return mappings
        
    def _transform_to_world(self, local_pos: Tuple[float, float, float],
                           base_pos: Tuple[float, float, float],
                           rotation: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Transform local position to world coordinates."""
        # Simplified transformation (no rotation for now)
        return (
            local_pos[0] + base_pos[0],
            local_pos[1] + base_pos[1],
            local_pos[2] + base_pos[2]
        )
        
    def update_placement(self, mechanism_id: str, 
                        position: Optional[Tuple[float, float, float]] = None,
                        rotation: Optional[Tuple[float, float, float]] = None,
                        scale: Optional[float] = None):
        """Update mechanism placement parameters."""
        if mechanism_id not in self.placements:
            return
            
        placement = self.placements[mechanism_id]
        
        if position is not None:
            placement.base_position = position
        if rotation is not None:
            placement.rotation = rotation
        if scale is not None:
            placement.scale = scale