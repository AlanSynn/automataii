"""
Base configuration models for automata base system.

This module provides the core configuration class that defines all properties
of an automata base, including type, dimensions, materials, and assembly info.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from uuid import uuid4

from automataii.modules.automata_base.enums.base_types import (
    BaseType,
    MountingType,
    MaterialType,
    AssemblyMethod,
)
from automataii.modules.automata_base.models.dimensions import (
    Dimensions2D,
    Dimensions3D,
    BoundingBox,
    MountingPoint,
    Unit,
    Point2D,
    Point3D,
)
from automataii.modules.automata_base.models.assembly_info import AssemblyInfo


@dataclass
class BaseConfiguration:
    """Complete configuration for an automata base."""
    
    # Basic properties
    name: str
    base_type: BaseType
    dimensions: Union[Dimensions2D, Dimensions3D]
    
    # Material and construction
    primary_material: MaterialType
    secondary_materials: List[MaterialType] = field(default_factory=list)
    material_thickness: Optional[float] = None
    
    # Mounting and assembly
    mounting_type: MountingType = MountingType.SURFACE
    mounting_points: List[MountingPoint] = field(default_factory=list)
    assembly_method: AssemblyMethod = AssemblyMethod.SCREWS
    assembly_info: Optional[AssemblyInfo] = None
    
    # Weight and load capacity
    weight: Optional[float] = None  # in kg
    max_load: Optional[float] = None  # in kg
    
    # Visual properties
    color: Optional[str] = None
    finish: Optional[str] = None
    texture: Optional[str] = None
    
    # Metadata
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    custom_properties: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate configuration consistency."""
        # Check material compatibility
        if self.base_type == BaseType.WALL_MOUNTED:
            if self.mounting_type not in [MountingType.WALL, MountingType.SURFACE]:
                raise ValueError("Wall-mounted base requires wall or surface mounting")
        
        # Check if mounting type is compatible with base type
        compatible_bases = MountingType.get_compatible_bases(self.mounting_type)
        if self.base_type not in compatible_bases:
            raise ValueError(f"{self.base_type} is not compatible with {self.mounting_type}")
        
        # Validate material thickness for certain materials
        if self.primary_material in [MaterialType.WOOD, MaterialType.MDF, 
                                     MaterialType.PLYWOOD, MaterialType.ACRYLIC]:
            if self.material_thickness is None:
                raise ValueError(f"Material thickness required for {self.primary_material}")
    
    @property
    def is_3d(self) -> bool:
        """Check if base has 3D dimensions."""
        return isinstance(self.dimensions, Dimensions3D)
    
    @property
    def footprint(self) -> Dimensions2D:
        """Get 2D footprint of base."""
        if isinstance(self.dimensions, Dimensions2D):
            return self.dimensions
        else:
            return self.dimensions.to_2d(exclude_axis="height")
    
    @property
    def bounding_box(self) -> BoundingBox:
        """Get bounding box of base."""
        if isinstance(self.dimensions, Dimensions2D):
            # Create 3D bounding box with minimal height
            return BoundingBox(
                min_point=Point3D(0, 0, 0),
                max_point=Point3D(
                    self.dimensions.width,
                    self.dimensions.height,
                    self.material_thickness or 10
                ),
                unit=self.dimensions.unit
            )
        else:
            return BoundingBox(
                min_point=Point3D(0, 0, 0),
                max_point=Point3D(
                    self.dimensions.width,
                    self.dimensions.height,
                    self.dimensions.depth
                ),
                unit=self.dimensions.unit
            )
    
    @property
    def total_materials(self) -> List[MaterialType]:
        """Get list of all materials used."""
        materials = [self.primary_material]
        materials.extend(self.secondary_materials)
        return list(set(materials))  # Remove duplicates
    
    def add_mounting_point(self, mounting_point: MountingPoint):
        """Add a mounting point to the base."""
        self.mounting_points.append(mounting_point)
        self.modified_at = datetime.now()
    
    def remove_mounting_point(self, index: int):
        """Remove a mounting point by index."""
        if 0 <= index < len(self.mounting_points):
            self.mounting_points.pop(index)
            self.modified_at = datetime.now()
    
    def update_dimensions(self, new_dimensions: Union[Dimensions2D, Dimensions3D]):
        """Update base dimensions."""
        # Validate type consistency
        if self.is_3d and isinstance(new_dimensions, Dimensions2D):
            raise ValueError("Cannot change from 3D to 2D dimensions")
        if not self.is_3d and isinstance(new_dimensions, Dimensions3D):
            raise ValueError("Cannot change from 2D to 3D dimensions")
        
        self.dimensions = new_dimensions
        self.modified_at = datetime.now()
    
    def scale(self, factor: float) -> "BaseConfiguration":
        """Create scaled copy of configuration."""
        import copy
        
        scaled = copy.deepcopy(self)
        scaled.dimensions = scaled.dimensions.scale(factor)
        
        # Scale mounting points
        for i, mp in enumerate(scaled.mounting_points):
            # Create new scaled position based on type
            if isinstance(mp.position, Point3D):
                scaled.mounting_points[i].position = Point3D(
                    x=mp.position.x * factor,
                    y=mp.position.y * factor,
                    z=mp.position.z * factor
                )
            else:  # Point2D
                scaled.mounting_points[i].position = Point2D(
                    x=mp.position.x * factor,
                    y=mp.position.y * factor
                )
            
            # Scale hole properties
            scaled.mounting_points[i].hole_diameter = mp.hole_diameter * factor
            if mp.hole_depth is not None:
                scaled.mounting_points[i].hole_depth = mp.hole_depth * factor
            if mp.countersink_diameter is not None:
                scaled.mounting_points[i].countersink_diameter = mp.countersink_diameter * factor
        
        # Scale material thickness
        if scaled.material_thickness:
            scaled.material_thickness *= factor
        
        # Update weight and load capacity
        if scaled.weight:
            scaled.weight *= factor ** 3  # Volume scales cubically
        if scaled.max_load:
            scaled.max_load *= factor ** 2  # Load capacity scales with area
        
        scaled.modified_at = datetime.now()
        scaled.id = str(uuid4())  # New ID for scaled version
        
        return scaled
    
    def validate(self) -> bool:
        """Validate the configuration and return True if valid."""
        try:
            self._validate()
            return True
        except ValueError:
            return False
    
    def _validate(self):
        """Internal validation method."""
        # Check base type and mounting compatibility
        compatible_bases = MountingType.get_compatible_bases(self.mounting_type)
        if self.base_type not in compatible_bases:
            raise ValueError(f"{self.base_type} is not compatible with {self.mounting_type}")
        
        # Validate material thickness for certain materials
        if self.primary_material in [MaterialType.WOOD, MaterialType.MDF, 
                                     MaterialType.PLYWOOD, MaterialType.ACRYLIC]:
            if self.material_thickness is None:
                raise ValueError(f"Material thickness required for {self.primary_material}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "base_type": self.base_type.value,
            "dimensions": {
                "type": "3D" if self.is_3d else "2D",
                "width": self.dimensions.width,
                "height": self.dimensions.height,
                "depth": getattr(self.dimensions, "depth", None),
                "unit": self.dimensions.unit.value,
            },
            "primary_material": self.primary_material.value,
            "secondary_materials": [m.value for m in self.secondary_materials],
            "material_thickness": self.material_thickness,
            "mounting_type": self.mounting_type.value,
            "assembly_method": self.assembly_method.value,
            "weight": self.weight,
            "max_load": self.max_load,
            "color": self.color,
            "finish": self.finish,
            "texture": self.texture,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "version": self.version,
            "custom_properties": self.custom_properties,
        }