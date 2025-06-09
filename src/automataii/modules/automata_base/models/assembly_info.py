"""
Assembly information models for automata base system.

This module provides classes for representing assembly instructions,
connection details, and component relationships.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from automataii.modules.automata_base.enums.base_types import ConnectionType, AssemblyMethod
from automataii.modules.automata_base.models.dimensions import Point3D, Unit


class ComponentType(Enum):
    """Types of components in assembly."""
    BASE_PLATE = "base_plate"
    SIDE_WALL = "side_wall"
    TOP_COVER = "top_cover"
    MOUNTING_BRACKET = "mounting_bracket"
    SUPPORT_BEAM = "support_beam"
    CONNECTOR = "connector"
    FASTENER = "fastener"
    ACCESSORY = "accessory"


@dataclass
class Component:
    """Individual component in assembly."""
    
    id: str
    name: str
    type: ComponentType
    quantity: int = 1
    material: Optional[str] = None
    dimensions: Optional[Dict[str, float]] = None
    part_number: Optional[str] = None
    notes: Optional[str] = None
    
    @property
    def is_structural(self) -> bool:
        """Check if component is structural."""
        return self.type in [
            ComponentType.BASE_PLATE,
            ComponentType.SIDE_WALL,
            ComponentType.SUPPORT_BEAM,
        ]


@dataclass
class ConnectionInfo:
    """Information about a connection between components."""
    
    connection_type: ConnectionType
    component_a_id: str
    component_b_id: str
    position: Optional[Point3D] = None
    orientation: Optional[Tuple[float, float, float]] = None  # rotation angles
    strength_rating: Optional[int] = None
    removable: bool = True
    tools_required: List[str] = field(default_factory=list)
    hardware: List[str] = field(default_factory=list)  # screws, bolts, etc.
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Set default strength rating if not provided."""
        if self.strength_rating is None:
            self.strength_rating = ConnectionType.get_strength_rating(
                self.connection_type
            )
    
    @property
    def is_permanent(self) -> bool:
        """Check if connection is permanent."""
        return not self.removable


@dataclass
class AssemblyStep:
    """Single step in assembly instructions."""
    
    step_number: int
    description: str
    components: List[str]  # component IDs involved
    connections: List[ConnectionInfo] = field(default_factory=list)
    tools_required: List[str] = field(default_factory=list)
    estimated_time: Optional[int] = None  # in minutes
    difficulty: int = 1  # 1-5 scale
    image_ref: Optional[str] = None
    video_ref: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)
    
    def validate(self) -> List[str]:
        """Validate assembly step and return any issues."""
        issues = []
        
        if self.step_number < 1:
            issues.append("Step number must be positive")
        
        if not self.description:
            issues.append("Step description is required")
        
        if not self.components:
            issues.append("At least one component must be specified")
        
        if self.difficulty < 1 or self.difficulty > 5:
            issues.append("Difficulty must be between 1 and 5")
        
        return issues


@dataclass
class AssemblyInfo:
    """Complete assembly information for a base."""
    
    # Components
    components: List[Component] = field(default_factory=list)
    
    # Assembly details
    primary_method: AssemblyMethod = AssemblyMethod.SCREWS
    secondary_methods: List[AssemblyMethod] = field(default_factory=list)
    assembly_steps: List[AssemblyStep] = field(default_factory=list)
    
    # Overall properties
    total_assembly_time: Optional[int] = None  # in minutes
    difficulty_rating: int = 1  # 1-5 scale
    tools_required: List[str] = field(default_factory=list)
    
    # Documentation
    assembly_manual_ref: Optional[str] = None
    video_tutorial_ref: Optional[str] = None
    support_contact: Optional[str] = None
    
    # Metadata
    version: str = "1.0"
    last_updated: Optional[str] = None
    notes: Optional[str] = None
    
    def add_component(self, component: Component):
        """Add a component to the assembly."""
        self.components.append(component)
    
    def add_step(self, step: AssemblyStep):
        """Add an assembly step."""
        # Validate step
        issues = step.validate()
        if issues:
            raise ValueError(f"Invalid assembly step: {', '.join(issues)}")
        
        # Ensure step numbers are sequential
        if self.assembly_steps:
            expected_number = len(self.assembly_steps) + 1
            if step.step_number != expected_number:
                step.step_number = expected_number
        
        self.assembly_steps.append(step)
        self._update_totals()
    
    def _update_totals(self):
        """Update total time and tools from steps."""
        if self.assembly_steps:
            # Calculate total time
            total_time = sum(
                step.estimated_time for step in self.assembly_steps 
                if step.estimated_time
            )
            if total_time > 0:
                self.total_assembly_time = total_time
            
            # Collect all tools
            all_tools = set()
            for step in self.assembly_steps:
                all_tools.update(step.tools_required)
            self.tools_required = sorted(list(all_tools))
            
            # Calculate average difficulty
            avg_difficulty = sum(
                step.difficulty for step in self.assembly_steps
            ) / len(self.assembly_steps)
            self.difficulty_rating = round(avg_difficulty)
    
    def get_component_by_id(self, component_id: str) -> Optional[Component]:
        """Find component by ID."""
        for component in self.components:
            if component.id == component_id:
                return component
        return None
    
    def get_components_by_type(self, component_type: ComponentType) -> List[Component]:
        """Get all components of a specific type."""
        return [c for c in self.components if c.type == component_type]
    
    def get_bill_of_materials(self) -> Dict[str, int]:
        """Generate bill of materials."""
        bom = {}
        for component in self.components:
            key = f"{component.name} ({component.part_number or 'N/A'})"
            bom[key] = bom.get(key, 0) + component.quantity
        return bom
    
    def validate_assembly(self) -> List[str]:
        """Validate entire assembly and return issues."""
        issues = []
        
        # Check components referenced in steps exist
        component_ids = {c.id for c in self.components}
        for step in self.assembly_steps:
            for comp_id in step.components:
                if comp_id not in component_ids:
                    issues.append(
                        f"Step {step.step_number} references unknown component: {comp_id}"
                    )
        
        # Check for duplicate component IDs
        seen_ids = set()
        for component in self.components:
            if component.id in seen_ids:
                issues.append(f"Duplicate component ID: {component.id}")
            seen_ids.add(component.id)
        
        # Check step numbers are sequential
        step_numbers = [step.step_number for step in self.assembly_steps]
        if step_numbers != list(range(1, len(step_numbers) + 1)):
            issues.append("Assembly step numbers are not sequential")
        
        return issues