"""
STL Export functionality for 3D printing automata bases.

This module provides tools to generate 3D geometry for different base types
and export them as STL files (both ASCII and binary formats) for 3D printing
or CNC machining.
"""

import struct
import numpy as np
from typing import List, Tuple, Optional, Union, BinaryIO
from dataclasses import dataclass
from pathlib import Path
import logging

from automataii.modules.automata_base.enums.base_types import BaseType
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, Point3D, MountingPoint, Unit
)

logger = logging.getLogger(__name__)


@dataclass
class Triangle:
    """Represents a 3D triangle with vertices and normal."""
    v1: np.ndarray  # 3D vertex 1
    v2: np.ndarray  # 3D vertex 2
    v3: np.ndarray  # 3D vertex 3
    normal: Optional[np.ndarray] = None
    
    def __post_init__(self):
        """Calculate normal if not provided."""
        if self.normal is None:
            # Calculate normal using cross product
            edge1 = self.v2 - self.v1
            edge2 = self.v3 - self.v1
            normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(normal)
            if norm > 0:
                self.normal = normal / norm
            else:
                self.normal = np.array([0, 0, 1])


class STLExporter:
    """Exports automata bases as STL files for 3D printing."""
    
    def __init__(self, base_config: BaseConfiguration):
        """
        Initialize STL exporter with base configuration.
        
        Args:
            base_config: The base configuration to export
        """
        self.config = base_config
        self.triangles: List[Triangle] = []
        
        # Convert dimensions to mm for standard STL output
        if self.config.dimensions.unit != Unit.MM:
            self.dimensions_mm = self.config.dimensions.to_unit(Unit.MM)
        else:
            self.dimensions_mm = self.config.dimensions
    
    def generate_geometry(self) -> List[Triangle]:
        """
        Generate 3D geometry based on base type.
        
        Returns:
            List of triangles representing the 3D geometry
        """
        self.triangles = []
        
        # Generate base geometry
        if self.config.base_type == BaseType.FLAT_RECTANGULAR:
            self._generate_flat_rectangular()
        elif self.config.base_type == BaseType.FLAT_CIRCULAR:
            self._generate_flat_circular()
        elif self.config.base_type == BaseType.BOX_ENCLOSED:
            self._generate_box_enclosed()
        elif self.config.base_type == BaseType.BOX_OPEN:
            self._generate_box_open()
        elif self.config.base_type == BaseType.PEDESTAL:
            self._generate_pedestal()
        elif self.config.base_type == BaseType.WALL_MOUNTED:
            self._generate_wall_mounted()
        else:
            raise ValueError(f"Unsupported base type: {self.config.base_type}")
        
        # Add mounting holes
        if self.config.mounting_points:
            self._subtract_mounting_holes()
        
        return self.triangles
    
    def _generate_flat_rectangular(self):
        """Generate a flat rectangular base with thickness."""
        if isinstance(self.dimensions_mm, Dimensions2D):
            width = self.dimensions_mm.width
            height = self.dimensions_mm.height
            thickness = self.config.material_thickness or 10.0  # Default 10mm
        else:
            width = self.dimensions_mm.width
            height = self.dimensions_mm.depth
            thickness = self.dimensions_mm.height
        
        # Create vertices for a rectangular box
        vertices = np.array([
            [0, 0, 0],           # 0: bottom-left-back
            [width, 0, 0],       # 1: bottom-right-back
            [width, height, 0],  # 2: top-right-back
            [0, height, 0],      # 3: top-left-back
            [0, 0, thickness],   # 4: bottom-left-front
            [width, 0, thickness],       # 5: bottom-right-front
            [width, height, thickness],  # 6: top-right-front
            [0, height, thickness],      # 7: top-left-front
        ])
        
        # Define faces using vertex indices
        faces = [
            # Bottom face
            [0, 2, 1], [0, 3, 2],
            # Top face
            [4, 5, 6], [4, 6, 7],
            # Front face
            [0, 1, 5], [0, 5, 4],
            # Back face
            [2, 3, 7], [2, 7, 6],
            # Left face
            [0, 4, 7], [0, 7, 3],
            # Right face
            [1, 2, 6], [1, 6, 5],
        ]
        
        # Create triangles
        for face in faces:
            v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            self.triangles.append(Triangle(v1, v2, v3))
    
    def _generate_flat_circular(self):
        """Generate a flat circular base with thickness."""
        if isinstance(self.dimensions_mm, Dimensions2D):
            diameter = min(self.dimensions_mm.width, self.dimensions_mm.height)
            thickness = self.config.material_thickness or 10.0
        else:
            diameter = min(self.dimensions_mm.width, self.dimensions_mm.depth)
            thickness = self.dimensions_mm.height
        
        radius = diameter / 2.0
        center_x = diameter / 2.0
        center_y = diameter / 2.0
        
        # Number of segments for circle approximation
        segments = 64
        
        # Generate vertices for top and bottom circles
        top_vertices = []
        bottom_vertices = []
        
        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = center_x + radius * np.cos(angle)
            y = center_y + radius * np.sin(angle)
            
            bottom_vertices.append(np.array([x, y, 0]))
            top_vertices.append(np.array([x, y, thickness]))
        
        # Center vertices
        bottom_center = np.array([center_x, center_y, 0])
        top_center = np.array([center_x, center_y, thickness])
        
        # Create triangles for top and bottom faces
        for i in range(segments):
            next_i = (i + 1) % segments
            
            # Bottom face (clockwise)
            self.triangles.append(Triangle(
                bottom_center,
                bottom_vertices[i],
                bottom_vertices[next_i]
            ))
            
            # Top face (counter-clockwise)
            self.triangles.append(Triangle(
                top_center,
                top_vertices[next_i],
                top_vertices[i]
            ))
            
            # Side faces
            self.triangles.append(Triangle(
                bottom_vertices[i],
                top_vertices[i],
                top_vertices[next_i]
            ))
            self.triangles.append(Triangle(
                bottom_vertices[i],
                top_vertices[next_i],
                bottom_vertices[next_i]
            ))
    
    def _generate_box_enclosed(self):
        """Generate an enclosed box base."""
        if isinstance(self.dimensions_mm, Dimensions3D):
            width = self.dimensions_mm.width
            depth = self.dimensions_mm.depth
            height = self.dimensions_mm.height
        else:
            width = self.dimensions_mm.width
            depth = self.dimensions_mm.height
            height = 50.0  # Default height for 2D specs
        
        wall_thickness = self.config.material_thickness or 5.0
        
        # Outer box vertices
        outer_vertices = np.array([
            [0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0],
            [0, 0, height], [width, 0, height], [width, depth, height], [0, depth, height]
        ])
        
        # Inner box vertices (hollow interior)
        inner_vertices = np.array([
            [wall_thickness, wall_thickness, wall_thickness],
            [width - wall_thickness, wall_thickness, wall_thickness],
            [width - wall_thickness, depth - wall_thickness, wall_thickness],
            [wall_thickness, depth - wall_thickness, wall_thickness],
            [wall_thickness, wall_thickness, height],
            [width - wall_thickness, wall_thickness, height],
            [width - wall_thickness, depth - wall_thickness, height],
            [wall_thickness, depth - wall_thickness, height]
        ])
        
        # Generate outer faces
        outer_faces = [
            [0, 2, 1], [0, 3, 2],  # Bottom
            [4, 5, 6], [4, 6, 7],  # Top
            [0, 1, 5], [0, 5, 4],  # Front
            [2, 3, 7], [2, 7, 6],  # Back
            [0, 4, 7], [0, 7, 3],  # Left
            [1, 2, 6], [1, 6, 5],  # Right
        ]
        
        # Generate inner faces (inverted normals)
        inner_faces = [
            [8, 9, 10], [8, 10, 11],    # Bottom (inner)
            [8, 11, 15], [8, 15, 12],   # Left (inner)
            [9, 13, 14], [9, 14, 10],   # Right (inner)
            [10, 14, 15], [10, 15, 11], # Back (inner)
            [8, 12, 13], [8, 13, 9],    # Front (inner)
        ]
        
        # Create triangles for outer box
        for face in outer_faces:
            v1, v2, v3 = outer_vertices[face[0]], outer_vertices[face[1]], outer_vertices[face[2]]
            self.triangles.append(Triangle(v1, v2, v3))
        
        # Create triangles for inner box (adjust indices)
        for face in inner_faces:
            v1 = inner_vertices[face[0] - 8]
            v2 = inner_vertices[face[1] - 8]
            v3 = inner_vertices[face[2] - 8]
            self.triangles.append(Triangle(v1, v2, v3))
    
    def _generate_box_open(self):
        """Generate an open box base (no top)."""
        if isinstance(self.dimensions_mm, Dimensions3D):
            width = self.dimensions_mm.width
            depth = self.dimensions_mm.depth
            height = self.dimensions_mm.height
        else:
            width = self.dimensions_mm.width
            depth = self.dimensions_mm.height
            height = 40.0  # Default height
        
        wall_thickness = self.config.material_thickness or 5.0
        
        # Generate outer walls
        vertices = []
        
        # Bottom face
        self._add_box_face(
            [0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]
        )
        
        # Front wall
        self._add_box_wall(
            [0, 0, 0], [width, 0, 0], height, wall_thickness, "front"
        )
        
        # Back wall
        self._add_box_wall(
            [0, depth, 0], [width, depth, 0], height, wall_thickness, "back"
        )
        
        # Left wall
        self._add_box_wall(
            [0, 0, 0], [0, depth, 0], height, wall_thickness, "left"
        )
        
        # Right wall
        self._add_box_wall(
            [width, 0, 0], [width, depth, 0], height, wall_thickness, "right"
        )
    
    def _generate_pedestal(self):
        """Generate a pedestal base with tapered design."""
        if isinstance(self.dimensions_mm, Dimensions3D):
            base_width = self.dimensions_mm.width
            base_depth = self.dimensions_mm.depth
            height = self.dimensions_mm.height
        else:
            base_width = self.dimensions_mm.width
            base_depth = self.dimensions_mm.height
            height = 100.0  # Default pedestal height
        
        # Taper factor (top is 70% of base size)
        taper = 0.7
        top_width = base_width * taper
        top_depth = base_depth * taper
        
        # Calculate offsets to center top on base
        x_offset = (base_width - top_width) / 2
        z_offset = (base_depth - top_depth) / 2
        
        # Define vertices for tapered box
        vertices = np.array([
            # Bottom vertices
            [0, 0, 0], [base_width, 0, 0], 
            [base_width, 0, base_depth], [0, 0, base_depth],
            # Top vertices
            [x_offset, height, z_offset], 
            [x_offset + top_width, height, z_offset],
            [x_offset + top_width, height, z_offset + top_depth], 
            [x_offset, height, z_offset + top_depth]
        ])
        
        # Define faces
        faces = [
            # Bottom
            [0, 2, 1], [0, 3, 2],
            # Top
            [4, 5, 6], [4, 6, 7],
            # Front
            [0, 1, 5], [0, 5, 4],
            # Back
            [3, 7, 6], [3, 6, 2],
            # Left
            [0, 4, 7], [0, 7, 3],
            # Right
            [1, 2, 6], [1, 6, 5]
        ]
        
        for face in faces:
            v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            self.triangles.append(Triangle(v1, v2, v3))
    
    def _generate_wall_mounted(self):
        """Generate a wall-mounted base with mounting brackets."""
        if isinstance(self.dimensions_mm, Dimensions2D):
            width = self.dimensions_mm.width
            height = self.dimensions_mm.height
            depth = 30.0  # Default depth for wall mount
        else:
            width = self.dimensions_mm.width
            height = self.dimensions_mm.height
            depth = self.dimensions_mm.depth
        
        thickness = self.config.material_thickness or 5.0
        
        # Main backing plate
        self._add_box(
            [0, 0, 0], [width, height, thickness]
        )
        
        # Add mounting brackets at corners
        bracket_size = min(width, height) * 0.15
        bracket_depth = depth
        
        # Top-left bracket
        self._add_bracket(
            [0, height - bracket_size, thickness],
            bracket_size, bracket_depth, thickness
        )
        
        # Top-right bracket
        self._add_bracket(
            [width - bracket_size, height - bracket_size, thickness],
            bracket_size, bracket_depth, thickness
        )
        
        # Bottom-left bracket
        self._add_bracket(
            [0, 0, thickness],
            bracket_size, bracket_depth, thickness
        )
        
        # Bottom-right bracket
        self._add_bracket(
            [width - bracket_size, 0, thickness],
            bracket_size, bracket_depth, thickness
        )
    
    def _add_box(self, min_point: List[float], max_point: List[float]):
        """Add a box to the geometry."""
        x_min, y_min, z_min = min_point
        x_max, y_max, z_max = max_point
        
        vertices = np.array([
            [x_min, y_min, z_min], [x_max, y_min, z_min],
            [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max],
            [x_max, y_max, z_max], [x_min, y_max, z_max]
        ])
        
        faces = [
            [0, 2, 1], [0, 3, 2],  # Bottom
            [4, 5, 6], [4, 6, 7],  # Top
            [0, 1, 5], [0, 5, 4],  # Front
            [2, 3, 7], [2, 7, 6],  # Back
            [0, 4, 7], [0, 7, 3],  # Left
            [1, 2, 6], [1, 6, 5],  # Right
        ]
        
        for face in faces:
            v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            self.triangles.append(Triangle(v1, v2, v3))
    
    def _add_bracket(self, position: List[float], size: float, depth: float, thickness: float):
        """Add an L-shaped bracket."""
        x, y, z = position
        
        # Horizontal part
        self._add_box(
            [x, y, z],
            [x + size, y + thickness, z + depth]
        )
        
        # Vertical part
        self._add_box(
            [x, y, z],
            [x + size, y + size, z + thickness]
        )
    
    def _add_box_face(self, v1: List[float], v2: List[float], v3: List[float], v4: List[float]):
        """Add a rectangular face as two triangles."""
        p1, p2, p3, p4 = np.array(v1), np.array(v2), np.array(v3), np.array(v4)
        self.triangles.append(Triangle(p1, p3, p2))
        self.triangles.append(Triangle(p1, p4, p3))
    
    def _add_box_wall(self, start: List[float], end: List[float], height: float, 
                      thickness: float, side: str):
        """Add a wall with thickness."""
        x1, y1, z1 = start
        x2, y2, z2 = end
        
        if side == "front":
            vertices = np.array([
                [x1, y1, z1], [x2, y2, z2],
                [x2, y2 + thickness, z2], [x1, y1 + thickness, z1],
                [x1, y1, z1 + height], [x2, y2, z2 + height],
                [x2, y2 + thickness, z2 + height], [x1, y1 + thickness, z1 + height]
            ])
        elif side == "back":
            vertices = np.array([
                [x1, y1 - thickness, z1], [x2, y2 - thickness, z2],
                [x2, y2, z2], [x1, y1, z1],
                [x1, y1 - thickness, z1 + height], [x2, y2 - thickness, z2 + height],
                [x2, y2, z2 + height], [x1, y1, z1 + height]
            ])
        elif side == "left":
            vertices = np.array([
                [x1, y1, z1], [x1 + thickness, y1, z1],
                [x1 + thickness, y2, z2], [x1, y2, z2],
                [x1, y1, z1 + height], [x1 + thickness, y1, z1 + height],
                [x1 + thickness, y2, z2 + height], [x1, y2, z2 + height]
            ])
        elif side == "right":
            vertices = np.array([
                [x1 - thickness, y1, z1], [x1, y1, z1],
                [x1, y2, z2], [x1 - thickness, y2, z2],
                [x1 - thickness, y1, z1 + height], [x1, y1, z1 + height],
                [x1, y2, z2 + height], [x1 - thickness, y2, z2 + height]
            ])
        
        # Create wall faces
        faces = [
            [0, 2, 1], [0, 3, 2],  # Bottom
            [4, 5, 6], [4, 6, 7],  # Top
            [0, 1, 5], [0, 5, 4],  # Outer
            [3, 7, 6], [3, 6, 2],  # Inner
            [0, 4, 7], [0, 7, 3],  # Left end
            [1, 2, 6], [1, 6, 5],  # Right end
        ]
        
        for face in faces:
            v1, v2, v3 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            self.triangles.append(Triangle(v1, v2, v3))
    
    def _subtract_mounting_holes(self):
        """Subtract mounting holes from the geometry."""
        # This is a simplified version - for production use, you'd want
        # proper CSG (Constructive Solid Geometry) operations
        logger.info(f"Adding {len(self.config.mounting_points)} mounting holes")
        
        # For now, we'll add visible hole markers as raised rings
        for mp in self.config.mounting_points:
            if isinstance(mp.position, Point3D):
                x, y, z = mp.position.x, mp.position.y, mp.position.z
            else:
                x, y = mp.position.x, mp.position.y
                z = 0
            
            # Add a raised ring to indicate hole position
            self._add_hole_marker(x, y, z, mp.hole_diameter / 2)
    
    def _add_hole_marker(self, x: float, y: float, z: float, radius: float):
        """Add a raised ring to mark hole position."""
        outer_radius = radius * 1.5
        height = 2.0
        segments = 32
        
        for i in range(segments):
            angle1 = 2 * np.pi * i / segments
            angle2 = 2 * np.pi * (i + 1) / segments
            
            # Inner circle points
            x1_inner = x + radius * np.cos(angle1)
            y1_inner = y + radius * np.sin(angle1)
            x2_inner = x + radius * np.cos(angle2)
            y2_inner = y + radius * np.sin(angle2)
            
            # Outer circle points
            x1_outer = x + outer_radius * np.cos(angle1)
            y1_outer = y + outer_radius * np.sin(angle1)
            x2_outer = x + outer_radius * np.cos(angle2)
            y2_outer = y + outer_radius * np.sin(angle2)
            
            # Create ring segment
            # Bottom face
            self.triangles.append(Triangle(
                np.array([x1_inner, y1_inner, z]),
                np.array([x2_inner, y2_inner, z]),
                np.array([x2_outer, y2_outer, z])
            ))
            self.triangles.append(Triangle(
                np.array([x1_inner, y1_inner, z]),
                np.array([x2_outer, y2_outer, z]),
                np.array([x1_outer, y1_outer, z])
            ))
            
            # Top face
            self.triangles.append(Triangle(
                np.array([x1_inner, y1_inner, z + height]),
                np.array([x2_outer, y2_outer, z + height]),
                np.array([x2_inner, y2_inner, z + height])
            ))
            self.triangles.append(Triangle(
                np.array([x1_inner, y1_inner, z + height]),
                np.array([x1_outer, y1_outer, z + height]),
                np.array([x2_outer, y2_outer, z + height])
            ))
    
    def export_ascii(self, filepath: Union[str, Path]) -> None:
        """
        Export geometry as ASCII STL file.
        
        Args:
            filepath: Path to save the STL file
        """
        filepath = Path(filepath)
        
        # Generate geometry if not already done
        if not self.triangles:
            self.generate_geometry()
        
        with open(filepath, 'w') as f:
            f.write(f"solid {self.config.name}\n")
            
            for triangle in self.triangles:
                f.write(f"  facet normal {triangle.normal[0]:.6f} {triangle.normal[1]:.6f} {triangle.normal[2]:.6f}\n")
                f.write("    outer loop\n")
                f.write(f"      vertex {triangle.v1[0]:.6f} {triangle.v1[1]:.6f} {triangle.v1[2]:.6f}\n")
                f.write(f"      vertex {triangle.v2[0]:.6f} {triangle.v2[1]:.6f} {triangle.v2[2]:.6f}\n")
                f.write(f"      vertex {triangle.v3[0]:.6f} {triangle.v3[1]:.6f} {triangle.v3[2]:.6f}\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")
            
            f.write(f"endsolid {self.config.name}\n")
        
        logger.info(f"Exported ASCII STL to {filepath} ({len(self.triangles)} triangles)")
    
    def export_binary(self, filepath: Union[str, Path]) -> None:
        """
        Export geometry as binary STL file.
        
        Args:
            filepath: Path to save the STL file
        """
        filepath = Path(filepath)
        
        # Generate geometry if not already done
        if not self.triangles:
            self.generate_geometry()
        
        with open(filepath, 'wb') as f:
            # Write 80-byte header
            header = f"Binary STL - {self.config.name}"[:80].ljust(80, ' ')
            f.write(header.encode('ascii'))
            
            # Write number of triangles
            f.write(struct.pack('<I', len(self.triangles)))
            
            # Write each triangle
            for triangle in self.triangles:
                # Normal vector (3 floats)
                f.write(struct.pack('<fff', *triangle.normal))
                
                # Vertices (3 x 3 floats)
                f.write(struct.pack('<fff', *triangle.v1))
                f.write(struct.pack('<fff', *triangle.v2))
                f.write(struct.pack('<fff', *triangle.v3))
                
                # Attribute byte count (unused)
                f.write(struct.pack('<H', 0))
        
        logger.info(f"Exported binary STL to {filepath} ({len(self.triangles)} triangles)")
    
    def export(self, filepath: Union[str, Path], binary: bool = True) -> None:
        """
        Export geometry as STL file.
        
        Args:
            filepath: Path to save the STL file
            binary: If True, export as binary STL; otherwise ASCII
        """
        if binary:
            self.export_binary(filepath)
        else:
            self.export_ascii(filepath)
    
    def get_statistics(self) -> dict:
        """
        Get statistics about the generated geometry.
        
        Returns:
            Dictionary with geometry statistics
        """
        if not self.triangles:
            self.generate_geometry()
        
        # Calculate bounding box
        all_vertices = []
        for tri in self.triangles:
            all_vertices.extend([tri.v1, tri.v2, tri.v3])
        
        vertices_array = np.array(all_vertices)
        min_coords = vertices_array.min(axis=0)
        max_coords = vertices_array.max(axis=0)
        
        # Calculate surface area and volume (approximate)
        surface_area = 0
        for tri in self.triangles:
            # Calculate triangle area using cross product
            edge1 = tri.v2 - tri.v1
            edge2 = tri.v3 - tri.v1
            area = 0.5 * np.linalg.norm(np.cross(edge1, edge2))
            surface_area += area
        
        return {
            "triangle_count": len(self.triangles),
            "vertex_count": len(self.triangles) * 3,
            "bounding_box": {
                "min": min_coords.tolist(),
                "max": max_coords.tolist(),
                "dimensions": (max_coords - min_coords).tolist()
            },
            "surface_area": surface_area,
            "file_size_estimate": {
                "ascii": len(self.triangles) * 250,  # Rough estimate
                "binary": 84 + len(self.triangles) * 50  # Header + triangles
            }
        }


def create_stl_from_config(config: BaseConfiguration, output_path: Union[str, Path], 
                          binary: bool = True) -> Path:
    """
    Convenience function to create STL file from base configuration.
    
    Args:
        config: Base configuration
        output_path: Output file path
        binary: Export as binary (True) or ASCII (False)
    
    Returns:
        Path to the created STL file
    """
    exporter = STLExporter(config)
    exporter.export(output_path, binary=binary)
    return Path(output_path)