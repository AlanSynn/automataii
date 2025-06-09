"""
STEP Export functionality for CAD integration.

This module provides tools to export automata bases as STEP files
for professional CAD software integration. STEP (ISO 10303) is the
standard format for exchanging 3D product data between CAD systems.
"""

from typing import List, Union, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import logging

from automataii.modules.automata_base.enums.base_types import BaseType
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Unit
)

logger = logging.getLogger(__name__)


class STEPExporter:
    """Exports automata bases as STEP files for CAD integration."""
    
    def __init__(self, base_config: BaseConfiguration):
        """
        Initialize STEP exporter with base configuration.
        
        Args:
            base_config: The base configuration to export
        """
        self.config = base_config
        self.entities: List[str] = []
        self.entity_counter = 0
        
        # Convert dimensions to mm for standard output
        if self.config.dimensions.unit != Unit.MM:
            self.dimensions_mm = self.config.dimensions.to_unit(Unit.MM)
        else:
            self.dimensions_mm = self.config.dimensions
    
    def _get_next_id(self) -> str:
        """Get next entity ID."""
        self.entity_counter += 1
        return f"#{self.entity_counter}"
    
    def _add_header(self) -> List[str]:
        """Generate STEP file header."""
        timestamp = datetime.now().isoformat()
        return [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('Automata Base STEP File'),'2;1');",
            f"FILE_NAME('{self.config.name}.step','{timestamp}',"
            "('Automataii'),('Automata Base Designer'),'','','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
            "ENDSEC;",
            ""
        ]
    
    def _add_data_section_start(self) -> List[str]:
        """Start DATA section."""
        return ["DATA;"]
    
    def _add_data_section_end(self) -> List[str]:
        """End DATA section."""
        return ["ENDSEC;", "END-ISO-10303-21;"]
    
    def _create_application_context(self) -> str:
        """Create application context entity."""
        id = self._get_next_id()
        self.entities.append(
            f"{id} = APPLICATION_CONTEXT('mechanical design');"
        )
        return id
    
    def _create_units(self) -> Dict[str, str]:
        """Create unit definitions."""
        units = {}
        
        # Length unit (millimeters)
        length_id = self._get_next_id()
        self.entities.append(
            f"{length_id} = (LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));"
        )
        units['length'] = length_id
        
        # Plane angle unit (radians)
        angle_id = self._get_next_id()
        self.entities.append(
            f"{angle_id} = (NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));"
        )
        units['angle'] = angle_id
        
        # Solid angle unit
        solid_angle_id = self._get_next_id()
        self.entities.append(
            f"{solid_angle_id} = (NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());"
        )
        units['solid_angle'] = solid_angle_id
        
        return units
    
    def _create_cartesian_point(self, x: float, y: float, z: float) -> str:
        """Create a 3D Cartesian point."""
        id = self._get_next_id()
        self.entities.append(
            f"{id} = CARTESIAN_POINT('',({x:.6f},{y:.6f},{z:.6f}));"
        )
        return id
    
    def _create_direction(self, x: float, y: float, z: float) -> str:
        """Create a direction vector."""
        id = self._get_next_id()
        self.entities.append(
            f"{id} = DIRECTION('',({x:.6f},{y:.6f},{z:.6f}));"
        )
        return id
    
    def _create_axis2_placement_3d(self, location_id: str, z_dir_id: str, 
                                   x_dir_id: str, name: str = '') -> str:
        """Create an axis2 placement for 3D positioning."""
        id = self._get_next_id()
        self.entities.append(
            f"{id} = AXIS2_PLACEMENT_3D('{name}',{location_id},{z_dir_id},{x_dir_id});"
        )
        return id
    
    def _create_plane(self, axis_id: str) -> str:
        """Create a plane entity."""
        id = self._get_next_id()
        self.entities.append(
            f"{id} = PLANE('',{axis_id});"
        )
        return id
    
    def _create_rectangular_profile(self, width: float, height: float, 
                                   placement_id: str) -> str:
        """Create a rectangular profile for extrusion."""
        # Create corner points
        p1 = self._create_cartesian_point(-width/2, -height/2, 0)
        p2 = self._create_cartesian_point(width/2, -height/2, 0)
        p3 = self._create_cartesian_point(width/2, height/2, 0)
        p4 = self._create_cartesian_point(-width/2, height/2, 0)
        
        # Create line segments
        line_ids = []
        points = [(p1, p2), (p2, p3), (p3, p4), (p4, p1)]
        
        for start, end in points:
            # Vertex points
            v1_id = self._get_next_id()
            self.entities.append(f"{v1_id} = VERTEX_POINT('',{start});")
            
            v2_id = self._get_next_id()
            self.entities.append(f"{v2_id} = VERTEX_POINT('',{end});")
            
            # Edge curve
            line_id = self._get_next_id()
            self.entities.append(f"{line_id} = LINE('',{start},{self._create_direction(1,0,0)});")
            
            # Edge
            edge_id = self._get_next_id()
            self.entities.append(
                f"{edge_id} = EDGE_CURVE('',{v1_id},{v2_id},{line_id},.T.);"
            )
            line_ids.append(edge_id)
        
        # Create edge loop
        loop_id = self._get_next_id()
        edges = ','.join(line_ids)
        self.entities.append(f"{loop_id} = EDGE_LOOP('',({edges}));")
        
        # Create face bound
        bound_id = self._get_next_id()
        self.entities.append(f"{bound_id} = FACE_OUTER_BOUND('',{loop_id},.T.);")
        
        # Create advanced face
        face_id = self._get_next_id()
        self.entities.append(
            f"{face_id} = ADVANCED_FACE('',({bound_id}),{placement_id},.T.);"
        )
        
        return face_id
    
    def _create_circular_profile(self, radius: float, center_id: str, 
                                normal_id: str) -> str:
        """Create a circular profile."""
        # Create circle
        circle_id = self._get_next_id()
        self.entities.append(
            f"{circle_id} = CIRCLE('',{self._create_axis2_placement_3d(center_id, normal_id, self._create_direction(1,0,0))},{radius:.6f});"
        )
        
        # Create edge loop
        edge_id = self._get_next_id()
        v_id = self._get_next_id()
        self.entities.append(f"{v_id} = VERTEX_POINT('',{center_id});")
        self.entities.append(f"{edge_id} = EDGE_CURVE('',{v_id},{v_id},{circle_id},.T.);")
        
        loop_id = self._get_next_id()
        self.entities.append(f"{loop_id} = EDGE_LOOP('',({edge_id}));")
        
        return loop_id
    
    def _create_extruded_solid(self, profile_id: str, direction_id: str, 
                              depth: float) -> str:
        """Create an extruded solid from a profile."""
        # Create swept area solid
        solid_id = self._get_next_id()
        self.entities.append(
            f"{solid_id} = EXTRUDED_AREA_SOLID('',{profile_id},{self._get_next_id()},{direction_id},{depth:.6f});"
        )
        
        return solid_id
    
    def _create_box_solid(self, width: float, height: float, depth: float,
                         position: Optional[Dict[str, float]] = None) -> str:
        """Create a box-shaped solid."""
        # Default position at origin
        if position is None:
            position = {'x': 0, 'y': 0, 'z': 0}
        
        # Create placement
        origin = self._create_cartesian_point(position['x'], position['y'], position['z'])
        z_dir = self._create_direction(0, 0, 1)
        x_dir = self._create_direction(1, 0, 0)
        placement = self._create_axis2_placement_3d(origin, z_dir, x_dir)
        
        # Create block
        block_id = self._get_next_id()
        self.entities.append(
            f"{block_id} = BLOCK('',{placement},{width:.6f},{height:.6f},{depth:.6f});"
        )
        
        return block_id
    
    def _create_cylinder_solid(self, radius: float, height: float,
                              position: Optional[Dict[str, float]] = None) -> str:
        """Create a cylindrical solid."""
        if position is None:
            position = {'x': 0, 'y': 0, 'z': 0}
        
        # Create placement
        origin = self._create_cartesian_point(position['x'], position['y'], position['z'])
        z_dir = self._create_direction(0, 0, 1)
        x_dir = self._create_direction(1, 0, 0)
        placement = self._create_axis2_placement_3d(origin, z_dir, x_dir)
        
        # Create cylinder
        cylinder_id = self._get_next_id()
        self.entities.append(
            f"{cylinder_id} = RIGHT_CIRCULAR_CYLINDER('',{placement},{height:.6f},{radius:.6f});"
        )
        
        return cylinder_id
    
    def _create_hole(self, mounting_point: MountingPoint, depth: float) -> str:
        """Create a hole for a mounting point."""
        x = mounting_point.position.x
        y = mounting_point.position.y
        z = 0
        
        radius = mounting_point.hole_diameter / 2.0
        
        # Create cylinder for hole
        hole_id = self._create_cylinder_solid(
            radius, depth,
            {'x': x, 'y': y, 'z': z}
        )
        
        return hole_id
    
    def _generate_flat_rectangular(self) -> List[str]:
        """Generate STEP entities for flat rectangular base."""
        if isinstance(self.dimensions_mm, Dimensions2D):
            width = self.dimensions_mm.width
            height = self.dimensions_mm.height
            thickness = self.config.material_thickness or 10.0
        else:
            width = self.dimensions_mm.width
            height = self.dimensions_mm.depth
            thickness = self.dimensions_mm.height
        
        # Create main body
        body_id = self._create_box_solid(width, height, thickness)
        
        # Create holes
        hole_ids = []
        for mp in self.config.mounting_points:
            hole_id = self._create_hole(mp, thickness)
            hole_ids.append(hole_id)
        
        # Create boolean result (subtract holes from body)
        result_id = body_id
        for hole_id in hole_ids:
            new_result_id = self._get_next_id()
            self.entities.append(
                f"{new_result_id} = BOOLEAN_RESULT('',{result_id},{hole_id},.DIFFERENCE.);"
            )
            result_id = new_result_id
        
        return [result_id]
    
    def _generate_flat_circular(self) -> List[str]:
        """Generate STEP entities for flat circular base."""
        if isinstance(self.dimensions_mm, Dimensions2D):
            diameter = min(self.dimensions_mm.width, self.dimensions_mm.height)
            thickness = self.config.material_thickness or 10.0
        else:
            diameter = min(self.dimensions_mm.width, self.dimensions_mm.depth)
            thickness = self.dimensions_mm.height
        
        radius = diameter / 2.0
        
        # Create main cylinder
        body_id = self._create_cylinder_solid(radius, thickness, 
                                            {'x': radius, 'y': radius, 'z': 0})
        
        # Create holes
        hole_ids = []
        for mp in self.config.mounting_points:
            hole_id = self._create_hole(mp, thickness)
            hole_ids.append(hole_id)
        
        # Boolean operations
        result_id = body_id
        for hole_id in hole_ids:
            new_result_id = self._get_next_id()
            self.entities.append(
                f"{new_result_id} = BOOLEAN_RESULT('',{result_id},{hole_id},.DIFFERENCE.);"
            )
            result_id = new_result_id
        
        return [result_id]
    
    def generate_entities(self) -> List[str]:
        """
        Generate STEP entities based on base type.
        
        Returns:
            List of solid entity IDs
        """
        self.entities = []
        self.entity_counter = 0
        
        # Create basic entities
        app_context = self._create_application_context()
        units = self._create_units()
        
        # Generate geometry based on type
        if self.config.base_type == BaseType.FLAT_RECTANGULAR:
            solid_ids = self._generate_flat_rectangular()
        elif self.config.base_type == BaseType.FLAT_CIRCULAR:
            solid_ids = self._generate_flat_circular()
        elif self.config.base_type in [BaseType.BOX_ENCLOSED, BaseType.BOX_OPEN]:
            # Simplified box representation
            solid_ids = self._generate_flat_rectangular()  # Placeholder
        elif self.config.base_type == BaseType.PEDESTAL:
            solid_ids = self._generate_flat_rectangular()  # Placeholder
        elif self.config.base_type == BaseType.WALL_MOUNTED:
            solid_ids = self._generate_flat_rectangular()  # Placeholder
        else:
            raise ValueError(f"Unsupported base type: {self.config.base_type}")
        
        # Create shape representation
        for solid_id in solid_ids:
            shape_rep_id = self._get_next_id()
            self.entities.append(
                f"{shape_rep_id} = ADVANCED_BREP_SHAPE_REPRESENTATION('',"
                f"({solid_id}),{self._get_next_id()});"
            )
        
        return solid_ids
    
    def export(self, filepath: Union[str, Path]) -> None:
        """
        Export geometry as STEP file.
        
        Args:
            filepath: Path to save the STEP file
        """
        filepath = Path(filepath)
        
        # Generate entities
        self.generate_entities()
        
        # Write file
        with open(filepath, 'w') as f:
            # Write header
            for line in self._add_header():
                f.write(line + '\n')
            
            # Write data section
            for line in self._add_data_section_start():
                f.write(line + '\n')
            
            # Write entities
            for entity in self.entities:
                f.write(entity + '\n')
            
            # Write footer
            for line in self._add_data_section_end():
                f.write(line + '\n')
        
        logger.info(f"Exported STEP file to {filepath}")


def create_step_from_config(config: BaseConfiguration, 
                           output_path: Union[str, Path]) -> Path:
    """
    Convenience function to create STEP file from base configuration.
    
    Args:
        config: Base configuration
        output_path: Output file path
    
    Returns:
        Path to the created STEP file
    """
    exporter = STEPExporter(config)
    exporter.export(output_path)
    return Path(output_path)