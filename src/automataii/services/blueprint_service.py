"""
Enhanced Blueprint Service - Multi-Layer Manufacturing Documentation

This service provides sophisticated blueprint generation from the centralized
Mechanism model, with intelligent layer separation, letter-size optimization,
and manufacturing-grade documentation.

Features:
- Multi-layer blueprint generation with automatic pagination
- Letter-size paper optimization with intelligent scaling
- Manufacturing specifications and dimensional standards
- Integration with physics validation results
- Educational annotations and assembly instructions
"""

import math
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QRectF, QSizeF
from PyQt6.QtGui import QPageSize

from ..models.mechanism import Mechanism, BlueprintLayer, MechanismLink, MechanismJoint
from ..models.mechanism import Point2D, ManufacturingStandard, ForceAnalysis
from ..services.simulation_service import SimulationResult
from ..core.event_bus import EventBus
from ..core.event_types import EventType

logger = logging.getLogger(__name__)


class PaperSize(str, Enum):
    """Standard paper sizes with dimensions in mm"""
    LETTER = "letter"  # 8.5" x 11" = 215.9 x 279.4 mm
    A4 = "a4"         # 210 x 297 mm
    A3 = "a3"         # 297 x 420 mm
    LEGAL = "legal"   # 8.5" x 14" = 215.9 x 355.6 mm


class BlueprintQuality(str, Enum):
    """Blueprint generation quality levels"""
    DRAFT = "draft"           # Fast generation, basic quality
    STANDARD = "standard"     # Good balance of quality and speed
    MANUFACTURING = "manufacturing"  # Highest quality for production use


@dataclass
class PaperDimensions:
    """Paper size dimensions and constraints"""
    width_mm: float
    height_mm: float
    margin_mm: float = 25.4  # 1 inch margin
    
    @property
    def printable_width(self) -> float:
        return self.width_mm - (2 * self.margin_mm)
    
    @property
    def printable_height(self) -> float:
        return self.height_mm - (2 * self.margin_mm)
    
    @property
    def printable_area(self) -> float:
        return self.printable_width * self.printable_height
    
    @classmethod
    def from_paper_size(cls, paper_size: PaperSize) -> 'PaperDimensions':
        """Create dimensions from standard paper size"""
        dimensions_map = {
            PaperSize.LETTER: (215.9, 279.4),
            PaperSize.A4: (210.0, 297.0),
            PaperSize.A3: (297.0, 420.0),
            PaperSize.LEGAL: (215.9, 355.6)
        }
        
        width, height = dimensions_map[paper_size]
        return cls(width_mm=width, height_mm=height)


@dataclass
class LayerLayout:
    """Layout information for a blueprint layer"""
    layer_id: str
    position: Point2D
    scale: float
    bounds: QRectF
    page_number: int
    
    # Manufacturing information
    material_specification: str = ""
    dimensional_tolerance: str = "±0.1mm"
    surface_finish: str = "Ra 3.2"
    assembly_notes: List[str] = None
    
    def __post_init__(self):
        if self.assembly_notes is None:
            self.assembly_notes = []


@dataclass
class BlueprintPage:
    """Single page of multi-page blueprint"""
    page_number: int
    page_title: str
    layers: List[LayerLayout]
    paper_dimensions: PaperDimensions
    
    # Page-specific metadata
    scale_note: str = ""
    revision: str = "A"
    drawing_number: str = ""
    
    @property
    def layer_count(self) -> int:
        return len(self.layers)
    
    @property
    def total_bounds(self) -> QRectF:
        """Calculate total bounds of all layers on this page"""
        if not self.layers:
            return QRectF()
        
        bounds = self.layers[0].bounds
        for layer in self.layers[1:]:
            bounds = bounds.united(layer.bounds)
        
        return bounds


class BlueprintService(QObject):
    """
    Enhanced blueprint generation service with multi-layer support.
    
    Provides intelligent blueprint generation from the centralized Mechanism
    model with automatic layer separation, letter-size optimization, and
    manufacturing-grade documentation.
    
    Features:
    - Automatic layer separation based on mechanism complexity
    - Intelligent scaling to fit letter-size paper
    - Manufacturing specifications and dimensional standards
    - Integration with physics simulation results
    - Multi-page pagination with cross-references
    """
    
    # Signals for event-driven communication
    blueprintGenerationStarted = pyqtSignal(str)  # mechanism_id
    blueprintGenerationCompleted = pyqtSignal(str, list)  # mechanism_id, pages
    blueprintGenerationError = pyqtSignal(str, str)  # mechanism_id, error_message
    layerProcessed = pyqtSignal(str, str, float)  # mechanism_id, layer_id, progress
    
    def __init__(self, event_bus: Optional[EventBus] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self.event_bus = event_bus
        
        # Default configuration
        self.default_paper_size = PaperSize.LETTER
        self.default_quality = BlueprintQuality.STANDARD
        self.manufacturing_standard = ManufacturingStandard.ISO
        
        # Layer generation settings
        self.max_layers_per_page = 4
        self.min_scale_factor = 0.25
        self.max_scale_factor = 4.0
        self.preferred_scale_factors = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0]
        
        # Connect to event bus
        if self.event_bus:
            self.event_bus.subscribe(EventType.SIMULATION_COMPLETED, self._on_simulation_completed)
    
    def generate_blueprint(
        self,
        mechanism: Mechanism,
        paper_size: PaperSize = None,
        quality: BlueprintQuality = None,
        simulation_result: Optional[SimulationResult] = None
    ) -> List[BlueprintPage]:
        """
        Generate multi-layer blueprint from mechanism specification.
        
        Args:
            mechanism: Centralized mechanism data model
            paper_size: Target paper size (defaults to letter)
            quality: Blueprint quality level
            simulation_result: Optional physics simulation results
            
        Returns:
            List of blueprint pages ready for export
        """
        paper_size = paper_size or self.default_paper_size
        quality = quality or self.default_quality
        
        try:
            self.blueprintGenerationStarted.emit(mechanism.id)
            logger.info(f"Generating blueprint for mechanism '{mechanism.name}' on {paper_size.value} paper")
            
            # Get paper dimensions
            paper_dims = PaperDimensions.from_paper_size(paper_size)
            
            # Analyze mechanism complexity and create layer strategy
            layer_strategy = self._create_layer_strategy(mechanism, paper_dims)
            
            # Generate layouts for each layer
            layer_layouts = []
            for i, (layer_id, layer) in enumerate(mechanism.blueprint_layers.items()):
                self.layerProcessed.emit(mechanism.id, layer_id, i / len(mechanism.blueprint_layers))
                
                layout = self._generate_layer_layout(
                    mechanism, layer, paper_dims, quality, simulation_result
                )
                if layout:
                    layer_layouts.append(layout)
            
            # Organize layers into pages
            pages = self._organize_layers_into_pages(
                mechanism, layer_layouts, paper_dims, layer_strategy
            )
            
            # Add manufacturing metadata
            self._add_manufacturing_metadata(mechanism, pages, simulation_result)
            
            # Add cross-references and page numbers
            self._add_cross_references(pages)
            
            logger.info(f"Blueprint generation completed: {len(pages)} pages, {len(layer_layouts)} layers")
            self.blueprintGenerationCompleted.emit(mechanism.id, pages)
            
            return pages
            
        except Exception as e:
            error_msg = f"Blueprint generation failed: {str(e)}"
            logger.error(error_msg)
            self.blueprintGenerationError.emit(mechanism.id, error_msg)
            return []
    
    def _create_layer_strategy(self, mechanism: Mechanism, paper_dims: PaperDimensions) -> Dict[str, Any]:
        """Analyze mechanism and create optimal layer separation strategy"""
        
        # Calculate mechanism complexity
        complexity_score = (
            len(mechanism.links) * 2 +
            len(mechanism.joints) * 1.5 +
            (len(mechanism.motion_paths) * 0.5)
        )
        
        # Estimate drawing bounds
        drawing_bounds = self._estimate_mechanism_bounds(mechanism)
        drawing_area = drawing_bounds.width() * drawing_bounds.height()
        
        # Determine if multi-page layout is needed
        needs_multiple_pages = (
            complexity_score > 20 or
            drawing_area > paper_dims.printable_area * 0.8 or
            len(mechanism.blueprint_layers) > self.max_layers_per_page
        )
        
        strategy = {
            'complexity_score': complexity_score,
            'drawing_bounds': drawing_bounds,
            'needs_multiple_pages': needs_multiple_pages,
            'recommended_scale': self._calculate_optimal_scale(drawing_bounds, paper_dims),
            'layer_grouping': self._determine_layer_grouping(mechanism, needs_multiple_pages)
        }
        
        logger.debug(f"Layer strategy: complexity={complexity_score:.1f}, "
                    f"multi_page={needs_multiple_pages}, scale={strategy['recommended_scale']:.2f}")
        
        return strategy
    
    def _estimate_mechanism_bounds(self, mechanism: Mechanism) -> QRectF:
        """Estimate overall bounds of mechanism drawing"""
        if not mechanism.joints:
            return QRectF(0, 0, 200, 200)  # Default bounds
        
        # Find bounds from joint positions
        positions = [joint.position for joint in mechanism.joints.values()]
        
        if not positions:
            return QRectF(0, 0, 200, 200)
        
        min_x = min(pos.x for pos in positions)
        max_x = max(pos.x for pos in positions)
        min_y = min(pos.y for pos in positions)
        max_y = max(pos.y for pos in positions)
        
        # Add padding for link lengths
        max_link_length = max((link.length for link in mechanism.links.values()), default=50)
        padding = max_link_length * 0.5
        
        bounds = QRectF(
            min_x - padding,
            min_y - padding,
            (max_x - min_x) + 2 * padding,
            (max_y - min_y) + 2 * padding
        )
        
        return bounds
    
    def _calculate_optimal_scale(self, drawing_bounds: QRectF, paper_dims: PaperDimensions) -> float:
        """Calculate optimal scale factor to fit drawing on paper"""
        
        # Calculate scale needed to fit drawing
        scale_x = paper_dims.printable_width / drawing_bounds.width()
        scale_y = paper_dims.printable_height / drawing_bounds.height()
        
        # Use the smaller scale to ensure fit
        calculated_scale = min(scale_x, scale_y)
        
        # Clamp to reasonable bounds
        calculated_scale = max(self.min_scale_factor, 
                              min(self.max_scale_factor, calculated_scale))
        
        # Snap to preferred scale factors
        best_scale = calculated_scale
        min_diff = float('inf')
        
        for preferred_scale in self.preferred_scale_factors:
            diff = abs(calculated_scale - preferred_scale)
            if diff < min_diff and preferred_scale <= calculated_scale * 1.2:
                min_diff = diff
                best_scale = preferred_scale
        
        return best_scale
    
    def _determine_layer_grouping(self, mechanism: Mechanism, needs_multiple_pages: bool) -> Dict[str, List[str]]:
        """Determine how to group layers across pages"""
        
        layers = list(mechanism.blueprint_layers.keys())
        
        if not needs_multiple_pages or len(layers) <= self.max_layers_per_page:
            # Single page layout
            return {'page_1': layers}
        
        # Multi-page layout strategy
        grouping = {}
        
        # Separate assembly views from detail views
        assembly_layers = []
        detail_layers = []
        
        for layer_id, layer in mechanism.blueprint_layers.items():
            if 'assembly' in layer.name.lower() or len(layer.included_links) == len(mechanism.links):
                assembly_layers.append(layer_id)
            else:
                detail_layers.append(layer_id)
        
        # Page 1: Assembly overview
        if assembly_layers:
            grouping['page_1'] = assembly_layers[:2]  # Max 2 assembly views per page
            remaining_assembly = assembly_layers[2:]
        else:
            grouping['page_1'] = []
            remaining_assembly = []
        
        # Distribute remaining layers
        all_remaining = remaining_assembly + detail_layers
        page_num = 2
        
        while all_remaining:
            page_key = f'page_{page_num}'
            page_layers = all_remaining[:self.max_layers_per_page]
            grouping[page_key] = page_layers
            all_remaining = all_remaining[self.max_layers_per_page:]
            page_num += 1
        
        return grouping
    
    def _generate_layer_layout(
        self,
        mechanism: Mechanism,
        layer: BlueprintLayer,
        paper_dims: PaperDimensions,
        quality: BlueprintQuality,
        simulation_result: Optional[SimulationResult]
    ) -> Optional[LayerLayout]:
        """Generate layout for a single blueprint layer"""
        
        try:
            # Calculate layer bounds based on included components
            layer_bounds = self._calculate_layer_bounds(mechanism, layer)
            
            # Determine optimal scale for this layer
            layer_scale = layer.scale if layer.scale > 0 else 1.0
            optimal_scale = self._calculate_optimal_scale(layer_bounds, paper_dims)
            final_scale = min(layer_scale, optimal_scale)
            
            # Calculate final positioned bounds
            scaled_bounds = QRectF(
                layer_bounds.x() * final_scale,
                layer_bounds.y() * final_scale,
                layer_bounds.width() * final_scale,
                layer_bounds.height() * final_scale
            )
            
            # Generate material specifications
            material_spec = self._generate_material_specification(mechanism, layer)
            
            # Generate assembly notes
            assembly_notes = self._generate_assembly_notes(mechanism, layer, simulation_result)
            
            layout = LayerLayout(
                layer_id=layer.id,
                position=layer.position,
                scale=final_scale,
                bounds=scaled_bounds,
                page_number=1,  # Will be updated during page organization
                material_specification=material_spec,
                dimensional_tolerance=self._get_dimensional_tolerance(layer),
                surface_finish=self._get_surface_finish(layer),
                assembly_notes=assembly_notes
            )
            
            return layout
            
        except Exception as e:
            logger.error(f"Error generating layout for layer {layer.id}: {e}")
            return None
    
    def _calculate_layer_bounds(self, mechanism: Mechanism, layer: BlueprintLayer) -> QRectF:
        """Calculate bounds for components included in layer"""
        
        # Start with joint positions for included links
        relevant_joints = []
        for joint in mechanism.joints.values():
            if (joint.link_a in layer.included_links or 
                joint.link_b in layer.included_links or
                joint.id in layer.included_joints):
                relevant_joints.append(joint)
        
        if not relevant_joints:
            return QRectF(0, 0, 100, 100)  # Default size
        
        # Calculate bounds from joint positions
        positions = [joint.position for joint in relevant_joints]
        min_x = min(pos.x for pos in positions)
        max_x = max(pos.x for pos in positions)
        min_y = min(pos.y for pos in positions)
        max_y = max(pos.y for pos in positions)
        
        # Add padding based on included links
        max_link_length = 0
        for link_id in layer.included_links:
            if link_id in mechanism.links:
                max_link_length = max(max_link_length, mechanism.links[link_id].length)
        
        padding = max(max_link_length * 0.3, 20.0)  # Minimum 20mm padding
        
        bounds = QRectF(
            min_x - padding,
            min_y - padding,
            (max_x - min_x) + 2 * padding,
            (max_y - min_y) + 2 * padding
        )
        
        return bounds
    
    def _generate_material_specification(self, mechanism: Mechanism, layer: BlueprintLayer) -> str:
        """Generate material specification string for layer"""
        
        materials = set()
        
        # Collect materials from included links
        for link_id in layer.included_links:
            if link_id in mechanism.links:
                materials.add(mechanism.links[link_id].material)
        
        if not materials:
            return "Material: As specified"
        
        # Convert material codes to readable specifications
        material_specs = []
        for material in materials:
            if material == "steel_a36":
                material_specs.append("Steel ASTM A36 (Fy=250MPa)")
            elif material == "aluminum_6061":
                material_specs.append("Aluminum 6061-T6 (Fy=276MPa)")
            elif material == "stainless_304":
                material_specs.append("Stainless Steel 304 (Fy=207MPa)")
            else:
                material_specs.append(f"Material: {material}")
        
        return "; ".join(material_specs)
    
    def _get_dimensional_tolerance(self, layer: BlueprintLayer) -> str:
        """Get dimensional tolerance specification for layer"""
        
        # Check if layer has specific tolerances
        if layer.dimensional_tolerances:
            # Use the most restrictive tolerance
            min_tolerance = min(layer.dimensional_tolerances.values())
            return f"±{min_tolerance:.2f}mm"
        
        # Default based on manufacturing standard
        if self.manufacturing_standard == ManufacturingStandard.ISO:
            return "±0.1mm (ISO 2768-m)"
        elif self.manufacturing_standard == ManufacturingStandard.ANSI:
            return "±0.005\" (ANSI Y14.5)"
        else:
            return "±0.1mm"
    
    def _get_surface_finish(self, layer: BlueprintLayer) -> str:
        """Get surface finish specification for layer"""
        
        # Check for layer-specific surface finishes
        if layer.surface_finishes:
            finishes = list(set(layer.surface_finishes.values()))
            return ", ".join(finishes)
        
        # Default surface finish
        return "Ra 3.2 (125 μin)"
    
    def _generate_assembly_notes(
        self,
        mechanism: Mechanism,
        layer: BlueprintLayer,
        simulation_result: Optional[SimulationResult]
    ) -> List[str]:
        """Generate assembly notes for layer"""
        
        notes = []
        
        # Add layer-specific assembly notes
        notes.extend(layer.assembly_notes)
        
        # Add physics-based recommendations if available
        if simulation_result and simulation_result.force_analysis:
            force_analysis = simulation_result.force_analysis
            
            # Check for high-stress areas
            if force_analysis.min_safety_factor < 3.0:
                notes.append(f"CAUTION: Minimum safety factor is {force_analysis.min_safety_factor:.1f}")
            
            # Lubrication recommendations based on joint forces
            high_force_joints = []
            for joint_id, force in force_analysis.joint_forces.items():
                force_magnitude = math.sqrt(force[0]**2 + force[1]**2)
                if force_magnitude > 100.0:  # N
                    high_force_joints.append(joint_id)
            
            if high_force_joints:
                notes.append(f"Apply high-pressure lubricant to joints: {', '.join(high_force_joints)}")
        
        # Add standard assembly notes
        standard_notes = [
            "Deburr all edges before assembly",
            "Apply threadlocker to fasteners as specified",
            "Check all dimensions before final assembly",
            "Lubricate moving joints with specified grease"
        ]
        
        # Only add standard notes that aren't already present
        for note in standard_notes:
            if not any(note.lower() in existing.lower() for existing in notes):
                notes.append(note)
        
        return notes
    
    def _organize_layers_into_pages(
        self,
        mechanism: Mechanism,
        layer_layouts: List[LayerLayout],
        paper_dims: PaperDimensions,
        layer_strategy: Dict[str, Any]
    ) -> List[BlueprintPage]:
        """Organize layer layouts into printable pages"""
        
        pages = []
        layer_grouping = layer_strategy['layer_grouping']
        
        for page_key, layer_ids in layer_grouping.items():
            page_number = int(page_key.split('_')[1])
            
            # Find layouts for this page
            page_layouts = []
            for layout in layer_layouts:
                if layout.layer_id in layer_ids:
                    layout.page_number = page_number
                    page_layouts.append(layout)
            
            if not page_layouts:
                continue
            
            # Arrange layouts on page
            arranged_layouts = self._arrange_layouts_on_page(page_layouts, paper_dims)
            
            # Generate page title
            if page_number == 1:
                page_title = f"{mechanism.name} - Assembly & Overview"
            else:
                page_title = f"{mechanism.name} - Details (Page {page_number})"
            
            # Create page
            page = BlueprintPage(
                page_number=page_number,
                page_title=page_title,
                layers=arranged_layouts,
                paper_dimensions=paper_dims,
                scale_note=self._generate_scale_note(arranged_layouts),
                drawing_number=f"{mechanism.id.upper()}-{page_number:02d}"
            )
            
            pages.append(page)
        
        # Sort pages by page number
        pages.sort(key=lambda p: p.page_number)
        
        return pages
    
    def _arrange_layouts_on_page(
        self,
        layouts: List[LayerLayout],
        paper_dims: PaperDimensions
    ) -> List[LayerLayout]:
        """Arrange multiple layouts optimally on a single page"""
        
        if len(layouts) == 1:
            # Single layout - center on page
            layout = layouts[0]
            center_x = paper_dims.printable_width / 2 - layout.bounds.width() / 2
            center_y = paper_dims.printable_height / 2 - layout.bounds.height() / 2
            layout.position = Point2D(center_x + paper_dims.margin_mm, 
                                    center_y + paper_dims.margin_mm)
            return [layout]
        
        elif len(layouts) == 2:
            # Two layouts - side by side or top/bottom
            total_width = sum(layout.bounds.width() for layout in layouts)
            total_height = sum(layout.bounds.height() for layout in layouts)
            
            if total_width <= paper_dims.printable_width:
                # Side by side arrangement
                current_x = paper_dims.margin_mm
                y_center = paper_dims.printable_height / 2
                
                for layout in layouts:
                    layout.position = Point2D(
                        current_x,
                        y_center - layout.bounds.height() / 2 + paper_dims.margin_mm
                    )
                    current_x += layout.bounds.width() + 20  # 20mm spacing
            else:
                # Top/bottom arrangement
                current_y = paper_dims.margin_mm
                x_center = paper_dims.printable_width / 2
                
                for layout in layouts:
                    layout.position = Point2D(
                        x_center - layout.bounds.width() / 2 + paper_dims.margin_mm,
                        current_y
                    )
                    current_y += layout.bounds.height() + 20  # 20mm spacing
        
        else:
            # Multiple layouts - grid arrangement
            cols = math.ceil(math.sqrt(len(layouts)))
            rows = math.ceil(len(layouts) / cols)
            
            col_width = paper_dims.printable_width / cols
            row_height = paper_dims.printable_height / rows
            
            for i, layout in enumerate(layouts):
                col = i % cols
                row = i // cols
                
                layout.position = Point2D(
                    col * col_width + paper_dims.margin_mm,
                    row * row_height + paper_dims.margin_mm
                )
        
        return layouts
    
    def _generate_scale_note(self, layouts: List[LayerLayout]) -> str:
        """Generate scale notation for page"""
        
        scales = [layout.scale for layout in layouts]
        unique_scales = sorted(list(set(scales)))
        
        if len(unique_scales) == 1:
            scale = unique_scales[0]
            if scale == 1.0:
                return "SCALE: FULL SIZE (1:1)"
            elif scale < 1.0:
                ratio = int(1 / scale)
                return f"SCALE: 1:{ratio}"
            else:
                ratio = int(scale)
                return f"SCALE: {ratio}:1"
        else:
            # Multiple scales on page
            scale_notes = []
            for scale in unique_scales:
                if scale == 1.0:
                    scale_notes.append("1:1")
                elif scale < 1.0:
                    ratio = int(1 / scale)
                    scale_notes.append(f"1:{ratio}")
                else:
                    ratio = int(scale)
                    scale_notes.append(f"{ratio}:1")
            
            return f"SCALES: {', '.join(scale_notes)}"
    
    def _add_manufacturing_metadata(
        self,
        mechanism: Mechanism,
        pages: List[BlueprintPage],
        simulation_result: Optional[SimulationResult]
    ):
        """Add manufacturing metadata to all pages"""
        
        # Generate common metadata
        creation_date = datetime.now().strftime("%Y-%m-%d")
        cost_estimate = mechanism.estimate_manufacturing_cost()
        
        for page in pages:
            # Add manufacturing notes based on simulation results
            if simulation_result:
                if simulation_result.constraint_violations:
                    page.revision = "B"  # Increment revision for constraint issues
                
                # Add safety notes
                if (simulation_result.force_analysis and 
                    simulation_result.force_analysis.min_safety_factor < 2.5):
                    # Could add manufacturing warnings here
                    pass
            
            # Add cost information to first page
            if page.page_number == 1:
                # Could add cost summary to first page metadata
                pass
    
    def _add_cross_references(self, pages: List[BlueprintPage]):
        """Add cross-references and navigation aids between pages"""
        
        if len(pages) <= 1:
            return
        
        # Add page references
        for i, page in enumerate(pages):
            # Add total page count to drawing number
            total_pages = len(pages)
            page.drawing_number = f"{page.drawing_number} ({page.page_number} of {total_pages})"
            
            # Add continuation notes
            if i < len(pages) - 1:
                # Could add "Continued on page X" notes
                pass
    
    def _on_simulation_completed(self, event_data: Dict[str, Any]):
        """Handle simulation completion events"""
        simulation_result = event_data.get('simulation_result')
        if simulation_result:
            logger.info(f"Received simulation results for mechanism {simulation_result.mechanism_id}")
            # Could trigger automatic blueprint regeneration here
    
    # Public interface methods
    
    def estimate_blueprint_complexity(self, mechanism: Mechanism) -> Dict[str, Any]:
        """Estimate blueprint generation complexity and requirements"""
        
        paper_dims = PaperDimensions.from_paper_size(self.default_paper_size)
        layer_strategy = self._create_layer_strategy(mechanism, paper_dims)
        
        return {
            'complexity_score': layer_strategy['complexity_score'],
            'estimated_pages': len(layer_strategy['layer_grouping']),
            'recommended_scale': layer_strategy['recommended_scale'],
            'needs_multiple_pages': layer_strategy['needs_multiple_pages'],
            'estimated_generation_time': len(mechanism.blueprint_layers) * 2.0,  # seconds
            'paper_utilization': min(1.0, layer_strategy['drawing_bounds'].width() * 
                                  layer_strategy['drawing_bounds'].height() / paper_dims.printable_area)
        }
    
    def validate_blueprint_feasibility(self, mechanism: Mechanism) -> Tuple[bool, List[str]]:
        """Validate if blueprint can be generated successfully"""
        
        issues = []
        
        # Check if mechanism has any blueprint layers
        if not mechanism.blueprint_layers:
            issues.append("Mechanism has no blueprint layers defined")
        
        # Check if links and joints exist
        if not mechanism.links:
            issues.append("Mechanism has no links to draw")
        
        if not mechanism.joints:
            issues.append("Mechanism has no joints to draw")
        
        # Check layer definitions
        for layer_id, layer in mechanism.blueprint_layers.items():
            # Check if included links exist
            for link_id in layer.included_links:
                if link_id not in mechanism.links:
                    issues.append(f"Layer {layer_id} references non-existent link {link_id}")
            
            # Check if included joints exist
            for joint_id in layer.included_joints:
                if joint_id not in mechanism.joints:
                    issues.append(f"Layer {layer_id} references non-existent joint {joint_id}")
        
        # Check if mechanism bounds are reasonable
        bounds = self._estimate_mechanism_bounds(mechanism)
        if bounds.width() > 10000 or bounds.height() > 10000:  # > 10 meters
            issues.append("Mechanism bounds are unreasonably large")
        
        if bounds.width() < 1 or bounds.height() < 1:  # < 1mm
            issues.append("Mechanism bounds are unreasonably small")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def get_supported_paper_sizes(self) -> List[PaperSize]:
        """Get list of supported paper sizes"""
        return list(PaperSize)
    
    def get_supported_quality_levels(self) -> List[BlueprintQuality]:
        """Get list of supported quality levels"""
        return list(BlueprintQuality)
    
    def set_manufacturing_standard(self, standard: ManufacturingStandard):
        """Set manufacturing standard for dimensional specifications"""
        self.manufacturing_standard = standard
        logger.info(f"Manufacturing standard set to {standard.value}")
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Blueprint service cleaned up")