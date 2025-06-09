"""
Export mechanism bases for 3D printing.

This module provides integration between the mechanism system and STL export,
allowing users to export bases that are properly sized for their mechanisms.
"""

from typing import Optional, List, Tuple
from pathlib import Path
import numpy as np

from automataii.modules.automata_base.enums.base_types import (
    BaseType, MaterialType, MountingType
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D, Dimensions3D, MountingPoint, Point2D, Unit
)
from automataii.utils.stl_exporter import STLExporter


class MechanismBaseExporter:
    """Export bases sized for specific mechanisms."""
    
    def __init__(self, mechanism_bounds: Tuple[float, float, float, float],
                 margin: float = 20.0):
        """
        Initialize with mechanism bounding box.
        
        Args:
            mechanism_bounds: (min_x, min_y, max_x, max_y) of mechanism
            margin: Extra margin around mechanism in mm
        """
        self.min_x, self.min_y, self.max_x, self.max_y = mechanism_bounds
        self.margin = margin
        
        # Calculate base dimensions
        self.width = (self.max_x - self.min_x) + 2 * margin
        self.height = (self.max_y - self.min_y) + 2 * margin
        
        # Offset to center mechanism on base
        self.offset_x = margin - self.min_x
        self.offset_y = margin - self.min_y
    
    def create_flat_base(self, thickness: float = 10.0,
                        material: MaterialType = MaterialType.ALUMINUM) -> BaseConfiguration:
        """Create a flat rectangular base for the mechanism."""
        config = BaseConfiguration(
            name="MechanismFlatBase",
            base_type=BaseType.FLAT_RECTANGULAR,
            dimensions=Dimensions2D(width=self.width, height=self.height, unit=Unit.MM),
            primary_material=material,
            material_thickness=thickness,
            mounting_type=MountingType.SURFACE
        )
        
        # Add corner mounting holes
        self._add_corner_holes(config, inset=15.0, diameter=5.0)
        
        return config
    
    def create_box_base(self, wall_height: float = 50.0,
                       wall_thickness: float = 5.0,
                       open_top: bool = True) -> BaseConfiguration:
        """Create a box base for the mechanism."""
        base_type = BaseType.BOX_OPEN if open_top else BaseType.BOX_ENCLOSED
        
        config = BaseConfiguration(
            name="MechanismBoxBase",
            base_type=base_type,
            dimensions=Dimensions3D(
                width=self.width,
                height=wall_height,
                depth=self.height,
                unit=Unit.MM
            ),
            primary_material=MaterialType.PLYWOOD,
            material_thickness=wall_thickness,
            mounting_type=MountingType.FREESTANDING
        )
        
        return config
    
    def create_display_base(self, pedestal_height: float = 100.0) -> BaseConfiguration:
        """Create a display pedestal base."""
        config = BaseConfiguration(
            name="MechanismDisplayBase",
            base_type=BaseType.PEDESTAL,
            dimensions=Dimensions3D(
                width=self.width,
                height=pedestal_height,
                depth=self.height,
                unit=Unit.MM
            ),
            primary_material=MaterialType.WOOD,
            material_thickness=15.0,
            mounting_type=MountingType.FREESTANDING
        )
        
        # Add top mounting points for mechanism
        self._add_mechanism_mounting_points(config)
        
        return config
    
    def create_wall_mount(self, bracket_depth: float = 40.0) -> BaseConfiguration:
        """Create a wall-mounted base."""
        config = BaseConfiguration(
            name="MechanismWallMount",
            base_type=BaseType.WALL_MOUNTED,
            dimensions=Dimensions2D(width=self.width, height=self.height, unit=Unit.MM),
            primary_material=MaterialType.STEEL,
            material_thickness=5.0,
            mounting_type=MountingType.WALL
        )
        
        # Add wall mounting holes
        self._add_wall_mounting_holes(config)
        
        # Add mechanism mounting points
        self._add_mechanism_mounting_points(config)
        
        return config
    
    def _add_corner_holes(self, config: BaseConfiguration, inset: float, diameter: float):
        """Add mounting holes at corners."""
        positions = [
            (inset, inset),
            (self.width - inset, inset),
            (self.width - inset, self.height - inset),
            (inset, self.height - inset)
        ]
        
        for x, y in positions:
            config.add_mounting_point(MountingPoint(
                position=Point2D(x, y),
                hole_diameter=diameter,
                thread_type="M5"
            ))
    
    def _add_mechanism_mounting_points(self, config: BaseConfiguration):
        """Add mounting points for mechanism attachment."""
        # Add mounting points based on mechanism size
        # Center point
        config.add_mounting_point(MountingPoint(
            position=Point2D(self.width / 2, self.height / 2),
            hole_diameter=8,
            thread_type="M8"
        ))
        
        # Additional support points
        if self.width > 150 or self.height > 150:
            # Add quadrant mounting points for larger mechanisms
            positions = [
                (self.width * 0.25, self.height * 0.25),
                (self.width * 0.75, self.height * 0.25),
                (self.width * 0.75, self.height * 0.75),
                (self.width * 0.25, self.height * 0.75)
            ]
            
            for x, y in positions:
                config.add_mounting_point(MountingPoint(
                    position=Point2D(x, y),
                    hole_diameter=5,
                    thread_type="M5"
                ))
    
    def _add_wall_mounting_holes(self, config: BaseConfiguration):
        """Add holes for wall mounting."""
        # Keyhole slots for easy mounting
        vertical_spacing = self.height * 0.7
        horizontal_spacing = self.width * 0.7
        
        positions = [
            (self.width * 0.15, self.height * 0.85),
            (self.width * 0.85, self.height * 0.85),
            (self.width * 0.15, self.height * 0.15),
            (self.width * 0.85, self.height * 0.15)
        ]
        
        for x, y in positions:
            config.add_mounting_point(MountingPoint(
                position=Point2D(x, y),
                hole_diameter=8,
                countersink=True,
                countersink_diameter=16,
                countersink_angle=90
            ))
    
    def export_all_variants(self, output_dir: Path, prefix: str = "mechanism_base"):
        """Export all base variants for the mechanism."""
        output_dir.mkdir(exist_ok=True)
        
        variants = [
            ("flat", self.create_flat_base()),
            ("box_open", self.create_box_base(open_top=True)),
            ("box_closed", self.create_box_base(open_top=False)),
            ("pedestal", self.create_display_base()),
            ("wall_mount", self.create_wall_mount())
        ]
        
        exported_files = []
        
        for variant_name, config in variants:
            filename = f"{prefix}_{variant_name}.stl"
            filepath = output_dir / filename
            
            exporter = STLExporter(config)
            exporter.export_binary(filepath)
            
            stats = exporter.get_statistics()
            exported_files.append({
                "file": filepath,
                "variant": variant_name,
                "triangles": stats["triangle_count"],
                "dimensions": stats["bounding_box"]["dimensions"]
            })
        
        return exported_files


def export_mechanism_base(mechanism_bounds: Tuple[float, float, float, float],
                         output_path: Path,
                         base_type: str = "flat",
                         **kwargs) -> Path:
    """
    Convenience function to export a single base type.
    
    Args:
        mechanism_bounds: (min_x, min_y, max_x, max_y) of mechanism
        output_path: Path for STL file
        base_type: Type of base ("flat", "box", "pedestal", "wall")
        **kwargs: Additional arguments for base creation
    
    Returns:
        Path to exported STL file
    """
    exporter = MechanismBaseExporter(mechanism_bounds)
    
    if base_type == "flat":
        config = exporter.create_flat_base(**kwargs)
    elif base_type == "box":
        config = exporter.create_box_base(**kwargs)
    elif base_type == "pedestal":
        config = exporter.create_display_base(**kwargs)
    elif base_type == "wall":
        config = exporter.create_wall_mount(**kwargs)
    else:
        raise ValueError(f"Unknown base type: {base_type}")
    
    stl_exporter = STLExporter(config)
    stl_exporter.export_binary(output_path)
    
    return output_path