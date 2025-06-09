"""
Base specifications and presets for common automata bases.

This module provides predefined specifications for standard base types
and functions to create custom specifications.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from automataii.modules.automata_base.enums.base_types import (
    BaseType,
    MountingType,
    MaterialType,
    AssemblyMethod,
)
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D,
    Dimensions3D,
    Unit,
    MountingPoint,
    Point2D,
    Point3D,
)
from automataii.modules.automata_base.models.base_config import BaseConfiguration


@dataclass
class BaseSpecification:
    """Predefined specification for a base type."""
    
    name: str
    description: str
    base_type: BaseType
    standard_sizes: Dict[str, Dict[str, float]]  # size_name -> dimensions
    recommended_materials: List[MaterialType]
    default_material: MaterialType
    typical_mounting: MountingType
    typical_assembly: AssemblyMethod
    weight_range: Tuple[float, float]  # min, max in kg
    load_capacity_range: Tuple[float, float]  # min, max in kg
    cost_category: str  # "low", "medium", "high"
    difficulty_level: int  # 1-5
    
    def create_base(
        self,
        size_name: str,
        material: Optional[MaterialType] = None,
        **kwargs
    ) -> BaseConfiguration:
        """Create a base configuration from this specification."""
        if size_name not in self.standard_sizes:
            raise ValueError(f"Unknown size: {size_name}")
        
        size_data = self.standard_sizes[size_name]
        
        # Create dimensions based on available data
        if "depth" in size_data:
            dimensions = Dimensions3D(
                width=size_data["width"],
                height=size_data["height"],
                depth=size_data["depth"],
                unit=Unit.MM
            )
        else:
            dimensions = Dimensions2D(
                width=size_data["width"],
                height=size_data["height"],
                unit=Unit.MM
            )
        
        # Create base configuration
        config = BaseConfiguration(
            name=f"{self.name} - {size_name}",
            base_type=self.base_type,
            dimensions=dimensions,
            primary_material=material or self.default_material,
            mounting_type=self.typical_mounting,
            assembly_method=self.typical_assembly,
            material_thickness=size_data.get("thickness"),
            **kwargs
        )
        
        # Add standard mounting points if applicable
        if self.base_type in [BaseType.FLAT_RECTANGULAR, BaseType.BOX_ENCLOSED]:
            self._add_standard_mounting_points(config, size_data)
        
        return config
    
    def _add_standard_mounting_points(
        self,
        config: BaseConfiguration,
        size_data: Dict[str, float]
    ):
        """Add standard mounting points based on base type."""
        width = size_data["width"]
        height = size_data["height"]
        
        if self.base_type == BaseType.FLAT_RECTANGULAR:
            # Four corner mounting points
            offset = 10  # 10mm from edges
            points = [
                Point2D(offset, offset),
                Point2D(width - offset, offset),
                Point2D(offset, height - offset),
                Point2D(width - offset, height - offset),
            ]
            
            for point in points:
                config.add_mounting_point(
                    MountingPoint(
                        position=point,
                        hole_diameter=4.0,  # M4 screw
                        thread_type="M4",
                        countersink=True,
                        countersink_diameter=8.0,
                    )
                )
    
    def create_configuration(self, size_name: str, **kwargs):
        """Alias for create_base for backward compatibility."""
        return self.create_base(size_name, **kwargs)


# Predefined specifications
SPECIFICATIONS: Dict[str, BaseSpecification] = {
    "simple_flat": BaseSpecification(
        name="Simple Flat Base",
        description="Basic flat rectangular base for small automata",
        base_type=BaseType.FLAT_RECTANGULAR,
        standard_sizes={
            "small": {"width": 150, "height": 100, "thickness": 12},
            "medium": {"width": 200, "height": 150, "thickness": 15},
            "large": {"width": 300, "height": 200, "thickness": 18},
        },
        recommended_materials=[
            MaterialType.WOOD,
            MaterialType.MDF,
            MaterialType.PLYWOOD,
        ],
        default_material=MaterialType.MDF,
        typical_mounting=MountingType.SURFACE,
        typical_assembly=AssemblyMethod.SCREWS,
        weight_range=(0.2, 2.0),
        load_capacity_range=(1.0, 10.0),
        cost_category="low",
        difficulty_level=1,
    ),
    
    "display_box": BaseSpecification(
        name="Display Box Base",
        description="Enclosed box base with transparent front for display",
        base_type=BaseType.BOX_ENCLOSED,
        standard_sizes={
            "small": {"width": 200, "height": 150, "depth": 150, "thickness": 6},
            "medium": {"width": 300, "height": 200, "depth": 200, "thickness": 8},
            "large": {"width": 400, "height": 300, "depth": 250, "thickness": 10},
        },
        recommended_materials=[
            MaterialType.WOOD,
            MaterialType.ACRYLIC,
            MaterialType.MDF,
        ],
        default_material=MaterialType.WOOD,
        typical_mounting=MountingType.SURFACE,
        typical_assembly=AssemblyMethod.SCREWS,
        weight_range=(1.0, 5.0),
        load_capacity_range=(5.0, 20.0),
        cost_category="medium",
        difficulty_level=3,
    ),
    
    "wall_mount": BaseSpecification(
        name="Wall Mount Base",
        description="Wall-mounted base for space-saving installations",
        base_type=BaseType.WALL_MOUNTED,
        standard_sizes={
            "small": {"width": 150, "height": 200, "depth": 80},
            "medium": {"width": 200, "height": 300, "depth": 100},
            "large": {"width": 300, "height": 400, "depth": 120},
        },
        recommended_materials=[
            MaterialType.WOOD,
            MaterialType.ALUMINUM,
            MaterialType.STEEL,
        ],
        default_material=MaterialType.WOOD,
        typical_mounting=MountingType.WALL,
        typical_assembly=AssemblyMethod.SCREWS,
        weight_range=(0.5, 3.0),
        load_capacity_range=(2.0, 15.0),
        cost_category="medium",
        difficulty_level=2,
    ),
    
    "pedestal": BaseSpecification(
        name="Pedestal Base",
        description="Elegant pedestal base for premium displays",
        base_type=BaseType.PEDESTAL,
        standard_sizes={
            "small": {"width": 120, "height": 300, "depth": 120},
            "medium": {"width": 150, "height": 400, "depth": 150},
            "large": {"width": 200, "height": 500, "depth": 200},
        },
        recommended_materials=[
            MaterialType.WOOD,
            MaterialType.ALUMINUM,
            MaterialType.COMPOSITE,
        ],
        default_material=MaterialType.WOOD,
        typical_mounting=MountingType.FREESTANDING,
        typical_assembly=AssemblyMethod.SCREWS,
        weight_range=(2.0, 10.0),
        load_capacity_range=(5.0, 30.0),
        cost_category="high",
        difficulty_level=4,
    ),
    
    "maker_friendly": BaseSpecification(
        name="Maker-Friendly Base",
        description="3D-printable or laser-cuttable base for makers",
        base_type=BaseType.MODULAR,
        standard_sizes={
            "mini": {"width": 100, "height": 80, "thickness": 6},
            "standard": {"width": 150, "height": 120, "thickness": 8},
            "extended": {"width": 200, "height": 150, "thickness": 10},
        },
        recommended_materials=[
            MaterialType.PLASTIC_3D_PRINTED,
            MaterialType.ACRYLIC,
            MaterialType.PLYWOOD,
        ],
        default_material=MaterialType.PLASTIC_3D_PRINTED,
        typical_mounting=MountingType.SURFACE,
        typical_assembly=AssemblyMethod.SNAP_FIT,
        weight_range=(0.1, 1.0),
        load_capacity_range=(0.5, 5.0),
        cost_category="low",
        difficulty_level=2,
    ),
}


def get_base_specification(spec_name: str) -> BaseSpecification:
    """Get a predefined base specification by name."""
    if spec_name not in SPECIFICATIONS:
        raise ValueError(f"Unknown specification: {spec_name}")
    return SPECIFICATIONS[spec_name]


def list_specifications() -> List[str]:
    """List all available specification names."""
    return list(SPECIFICATIONS.keys())


def create_custom_specification(**kwargs) -> BaseSpecification:
    """Create a custom base specification."""
    required_fields = [
        "name", "description", "base_type", "standard_sizes",
        "recommended_materials", "default_material", "typical_mounting",
        "typical_assembly", "weight_range", "load_capacity_range",
        "cost_category", "difficulty_level"
    ]
    
    for field in required_fields:
        if field not in kwargs:
            raise ValueError(f"Missing required field: {field}")
    
    return BaseSpecification(**kwargs)