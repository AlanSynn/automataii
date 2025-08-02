"""
Blueprint Exporters - Multi-format export implementations

This module provides concrete implementations for different blueprint export formats.
Each exporter follows the same interface but generates output optimized for its
specific use case and target applications.

Exporters:
- DxfExporter: CAD-level precision for AutoCAD, SolidWorks, etc.
- SvgExporter: Vector graphics for web and documentation
- PdfExporter: Professional documentation with annotations
- PngExporter: Raster format for presentations and reports
"""

import os
import math
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

# Core libraries
import json
from pathlib import Path

# PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, letter, legal
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import black, blue, red, green
from reportlab.graphics.shapes import Drawing, Line, Circle, Rect, Polygon
from reportlab.graphics import renderPDF

# SVG generation
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


@dataclass
class GeometryElement:
    """Base class for geometric elements in blueprints"""
    element_type: str
    properties: Dict[str, Any]
    style: Dict[str, Any]
    layer: str = "default"


@dataclass
class LineElement(GeometryElement):
    """Line element for blueprints"""
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    
    def __post_init__(self):
        self.element_type = "line"


@dataclass 
class CircleElement(GeometryElement):
    """Circle element for blueprints"""
    center: Tuple[float, float]
    radius: float
    
    def __post_init__(self):
        self.element_type = "circle"


@dataclass
class ArcElement(GeometryElement):
    """Arc element for blueprints"""
    center: Tuple[float, float]
    radius: float
    start_angle: float  # in degrees
    end_angle: float    # in degrees
    
    def __post_init__(self):
        self.element_type = "arc"


@dataclass
class DimensionElement(GeometryElement):
    """Dimension element for blueprints"""
    start_point: Tuple[float, float]
    end_point: Tuple[float, float]
    dimension_value: float
    dimension_text: str
    offset: float = 10.0  # offset from measured line
    
    def __post_init__(self):
        self.element_type = "dimension"


@dataclass
class TextElement(GeometryElement):
    """Text element for blueprints"""
    position: Tuple[float, float]
    text: str
    font_size: float = 12.0
    rotation: float = 0.0  # in degrees
    
    def __post_init__(self):
        self.element_type = "text"


class BlueprintExporter(ABC):
    """
    Abstract base class for blueprint exporters.
    
    Defines the common interface that all exporters must implement.
    Provides shared functionality for geometry processing and validation.
    """
    
    def __init__(self):
        self.mechanism_data: Optional[Dict[str, Any]] = None
        self.export_settings = None
        self.geometry_elements: List[GeometryElement] = []
        self.drawing_bounds: Tuple[float, float, float, float] = (0, 0, 0, 0)  # min_x, min_y, max_x, max_y
        
    def initialize(self, mechanism_data: Dict[str, Any], settings):
        """Initialize exporter with mechanism data and settings"""
        self.mechanism_data = mechanism_data
        self.export_settings = settings
        self.geometry_elements = []
        
        logger.info(f"Initialized {self.__class__.__name__} with mechanism: {mechanism_data.get('name', 'Unknown')}")
        
    def generate_geometry(self):
        """Generate geometry elements from mechanism data"""
        if not self.mechanism_data:
            raise ValueError("Exporter not initialized with mechanism data")
            
        # Extract components and generate geometry
        components = self.mechanism_data.get('components', [])
        constraints = self.mechanism_data.get('constraints', [])
        
        # Generate geometry for each component
        for component in components:
            self._generate_component_geometry(component)
            
        # Generate constraint visualization
        for constraint in constraints:
            self._generate_constraint_geometry(constraint)
            
        # Calculate drawing bounds
        self._calculate_drawing_bounds()
        
        logger.info(f"Generated {len(self.geometry_elements)} geometry elements")
        
    def add_dimensions(self):
        """Add automatic dimensions to the blueprint"""
        if not self.export_settings.include_dimensions:
            return
            
        # Auto-dimension key features
        dimension_elements = self._generate_auto_dimensions()
        self.geometry_elements.extend(dimension_elements)
        
        logger.info(f"Added {len(dimension_elements)} dimension elements")
        
    def add_annotations(self):
        """Add annotations, notes, and specifications"""
        if not self.export_settings.include_annotations:
            return
            
        # Add title block
        title_elements = self._generate_title_block()
        self.geometry_elements.extend(title_elements)
        
        # Add material specifications
        if self.export_settings.include_material_specs:
            material_elements = self._generate_material_specs()
            self.geometry_elements.extend(material_elements)
            
        # Add assembly notes
        if self.export_settings.include_assembly_notes:
            assembly_elements = self._generate_assembly_notes()
            self.geometry_elements.extend(assembly_elements)
            
        logger.info("Added annotations and specifications")
        
    @abstractmethod
    def export(self, output_path: str) -> Tuple[List[str], List[str]]:
        """
        Export blueprint to file.
        
        Returns:
            (warnings, errors) - Lists of warning and error messages
        """
        pass
        
    def _generate_component_geometry(self, component: Dict[str, Any]):
        """Generate geometry for a single component"""
        component_type = component.get('type', 'unknown')
        geometry = component.get('geometry', {})
        
        if component_type == 'link':
            self._generate_link_geometry(component, geometry)
        elif component_type == 'joint':
            self._generate_joint_geometry(component, geometry)
        elif component_type == 'gear':
            self._generate_gear_geometry(component, geometry)
        elif component_type == 'cam':
            self._generate_cam_geometry(component, geometry)
        else:
            logger.warning(f"Unknown component type: {component_type}")
            
    def _generate_link_geometry(self, component: Dict[str, Any], geometry: Dict[str, Any]):
        """Generate geometry for a link component"""
        start_pos = geometry.get('start_position', (0, 0))
        end_pos = geometry.get('end_position', (100, 0))
        width = geometry.get('width', 6.0)
        
        # Main link line
        line = LineElement(
            start_point=start_pos,
            end_point=end_pos,
            properties={'component_id': component.get('id', ''), 'width': width},
            style={'stroke_width': 2.0, 'stroke_color': 'black'},
            layer='mechanism'
        )
        self.geometry_elements.append(line)
        
        # Link outline (simplified rectangular representation)
        length = math.sqrt((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2)
        angle = math.atan2(end_pos[1] - start_pos[1], end_pos[0] - start_pos[0])
        
        # Calculate rectangle corners
        half_width = width / 2
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        perp_x, perp_y = -sin_a * half_width, cos_a * half_width
        
        corners = [
            (start_pos[0] + perp_x, start_pos[1] + perp_y),
            (start_pos[0] - perp_x, start_pos[1] - perp_y),
            (end_pos[0] - perp_x, end_pos[1] - perp_y),
            (end_pos[0] + perp_x, end_pos[1] + perp_y)
        ]
        
        # Add outline lines
        for i in range(4):
            next_i = (i + 1) % 4
            outline = LineElement(
                start_point=corners[i],
                end_point=corners[next_i],
                properties={'component_id': component.get('id', ''), 'outline': True},
                style={'stroke_width': 1.0, 'stroke_color': 'black'},
                layer='mechanism'
            )
            self.geometry_elements.append(outline)
            
    def _generate_joint_geometry(self, component: Dict[str, Any], geometry: Dict[str, Any]):
        """Generate geometry for a joint component"""
        position = geometry.get('position', (0, 0))
        radius = geometry.get('radius', 8.0)
        is_fixed = geometry.get('fixed', False)
        
        # Main joint circle
        circle = CircleElement(
            center=position,
            radius=radius,
            properties={'component_id': component.get('id', ''), 'fixed': is_fixed},
            style={'stroke_width': 2.0, 'stroke_color': 'black', 'fill_color': 'white'},
            layer='mechanism'
        )
        self.geometry_elements.append(circle)
        
        # Fixed joint indication
        if is_fixed:
            # Ground symbol (triangle pattern)
            ground_size = radius * 1.5
            ground_lines = [
                ((position[0] - ground_size, position[1] + radius + 5),
                 (position[0] + ground_size, position[1] + radius + 5)),
                ((position[0] - ground_size * 0.8, position[1] + radius + 10),
                 (position[0] + ground_size * 0.8, position[1] + radius + 10)),
                ((position[0] - ground_size * 0.6, position[1] + radius + 15),
                 (position[0] + ground_size * 0.6, position[1] + radius + 15))
            ]
            
            for start, end in ground_lines:
                ground_line = LineElement(
                    start_point=start,
                    end_point=end,
                    properties={'component_id': component.get('id', ''), 'ground_symbol': True},
                    style={'stroke_width': 1.0, 'stroke_color': 'black'},
                    layer='symbols'
                )
                self.geometry_elements.append(ground_line)
                
    def _generate_gear_geometry(self, component: Dict[str, Any], geometry: Dict[str, Any]):
        """Generate geometry for a gear component"""
        center = geometry.get('center', (0, 0))
        radius = geometry.get('radius', 20.0)
        teeth_count = geometry.get('teeth_count', 24)
        
        # Main gear circle (pitch circle)
        pitch_circle = CircleElement(
            center=center,
            radius=radius,
            properties={'component_id': component.get('id', ''), 'gear_pitch': True},
            style={'stroke_width': 1.5, 'stroke_color': 'blue', 'stroke_style': 'dashed'},
            layer='mechanism'
        )
        self.geometry_elements.append(pitch_circle)
        
        # Addendum circle (outer)
        addendum = radius * 0.1  # Simplified addendum
        outer_circle = CircleElement(
            center=center,
            radius=radius + addendum,
            properties={'component_id': component.get('id', ''), 'gear_outer': True},
            style={'stroke_width': 2.0, 'stroke_color': 'black'},
            layer='mechanism'
        )
        self.geometry_elements.append(outer_circle)
        
        # Dedendum circle (inner)
        dedendum = radius * 0.12  # Simplified dedendum
        inner_circle = CircleElement(
            center=center,
            radius=radius - dedendum,
            properties={'component_id': component.get('id', ''), 'gear_inner': True},
            style={'stroke_width': 1.0, 'stroke_color': 'black'},
            layer='mechanism'
        )
        self.geometry_elements.append(inner_circle)
        
        # Simplified tooth representation (radial lines)
        for i in range(min(teeth_count, 24)):  # Limit for clarity
            angle = i * 2 * math.pi / teeth_count
            inner_x = center[0] + (radius - dedendum) * math.cos(angle)
            inner_y = center[1] + (radius - dedendum) * math.sin(angle)
            outer_x = center[0] + (radius + addendum) * math.cos(angle)
            outer_y = center[1] + (radius + addendum) * math.sin(angle)
            
            tooth_line = LineElement(
                start_point=(inner_x, inner_y),
                end_point=(outer_x, outer_y),
                properties={'component_id': component.get('id', ''), 'tooth': i},
                style={'stroke_width': 0.5, 'stroke_color': 'gray'},
                layer='details'
            )
            self.geometry_elements.append(tooth_line)
            
    def _generate_cam_geometry(self, component: Dict[str, Any], geometry: Dict[str, Any]):
        """Generate geometry for a cam component"""
        center = geometry.get('center', (0, 0))
        base_radius = geometry.get('base_radius', 30.0)
        profile_points = geometry.get('profile_points', [])
        
        # Base circle
        base_circle = CircleElement(
            center=center,
            radius=base_radius,
            properties={'component_id': component.get('id', ''), 'cam_base': True},
            style={'stroke_width': 1.0, 'stroke_color': 'blue', 'stroke_style': 'dashed'},
            layer='mechanism'
        )
        self.geometry_elements.append(base_circle)
        
        # Cam profile (if profile points available)
        if profile_points and len(profile_points) > 2:
            for i in range(len(profile_points)):
                start_point = profile_points[i]
                end_point = profile_points[(i + 1) % len(profile_points)]
                
                profile_line = LineElement(
                    start_point=start_point,
                    end_point=end_point,
                    properties={'component_id': component.get('id', ''), 'cam_profile': True},
                    style={'stroke_width': 2.0, 'stroke_color': 'black'},
                    layer='mechanism'
                )
                self.geometry_elements.append(profile_line)
        else:
            # Simple elliptical cam profile
            for i in range(32):
                angle = i * 2 * math.pi / 32
                next_angle = (i + 1) * 2 * math.pi / 32
                
                # Simple cam profile with sinusoidal variation
                r1 = base_radius + 10 * (1 + math.sin(2 * angle)) / 2
                r2 = base_radius + 10 * (1 + math.sin(2 * next_angle)) / 2
                
                x1 = center[0] + r1 * math.cos(angle)
                y1 = center[1] + r1 * math.sin(angle)
                x2 = center[0] + r2 * math.cos(next_angle)
                y2 = center[1] + r2 * math.sin(next_angle)
                
                profile_line = LineElement(
                    start_point=(x1, y1),
                    end_point=(x2, y2),
                    properties={'component_id': component.get('id', ''), 'cam_profile': True},
                    style={'stroke_width': 2.0, 'stroke_color': 'black'},
                    layer='mechanism'
                )
                self.geometry_elements.append(profile_line)
                
    def _generate_constraint_geometry(self, constraint: Dict[str, Any]):
        """Generate geometry for constraint visualization"""
        constraint_type = constraint.get('type', 'unknown')
        
        if constraint_type == 'distance':
            self._generate_distance_constraint(constraint)
        elif constraint_type == 'angle':
            self._generate_angle_constraint(constraint)
        # Add more constraint types as needed
        
    def _generate_distance_constraint(self, constraint: Dict[str, Any]):
        """Generate geometry for distance constraint"""
        point1 = constraint.get('point1', (0, 0))
        point2 = constraint.get('point2', (100, 0))
        distance = constraint.get('distance', 100.0)
        
        # Constraint line (dashed)
        constraint_line = LineElement(
            start_point=point1,
            end_point=point2,
            properties={'constraint_id': constraint.get('id', ''), 'distance': distance},
            style={'stroke_width': 1.0, 'stroke_color': 'red', 'stroke_style': 'dashed'},
            layer='constraints'
        )
        self.geometry_elements.append(constraint_line)
        
    def _generate_angle_constraint(self, constraint: Dict[str, Any]):
        \"\"\"Generate geometry for angle constraint\"\"\"\n        center = constraint.get('center', (0, 0))\n        start_angle = constraint.get('start_angle', 0.0)\n        end_angle = constraint.get('end_angle', 90.0)\n        radius = constraint.get('radius', 20.0)\n        \n        # Angle arc\n        angle_arc = ArcElement(\n            center=center,\n            radius=radius,\n            start_angle=start_angle,\n            end_angle=end_angle,\n            properties={'constraint_id': constraint.get('id', ''), 'angle': end_angle - start_angle},\n            style={'stroke_width': 1.0, 'stroke_color': 'green'},\n            layer='constraints'\n        )\n        self.geometry_elements.append(angle_arc)\n        \n    def _calculate_drawing_bounds(self):\n        \"\"\"Calculate bounding box for all geometry elements\"\"\"\n        if not self.geometry_elements:\n            self.drawing_bounds = (0, 0, 100, 100)\n            return\n            \n        min_x = min_y = float('inf')\n        max_x = max_y = float('-inf')\n        \n        for element in self.geometry_elements:\n            bounds = self._get_element_bounds(element)\n            if bounds:\n                min_x = min(min_x, bounds[0])\n                min_y = min(min_y, bounds[1])\n                max_x = max(max_x, bounds[2])\n                max_y = max(max_y, bounds[3])\n                \n        # Add margin\n        margin = 20.0\n        self.drawing_bounds = (min_x - margin, min_y - margin, \n                             max_x + margin, max_y + margin)\n                             \n    def _get_element_bounds(self, element: GeometryElement) -> Optional[Tuple[float, float, float, float]]:\n        \"\"\"Get bounding box for a single element\"\"\"\n        if isinstance(element, LineElement):\n            return (min(element.start_point[0], element.end_point[0]),\n                   min(element.start_point[1], element.end_point[1]),\n                   max(element.start_point[0], element.end_point[0]),\n                   max(element.start_point[1], element.end_point[1]))\n        elif isinstance(element, CircleElement):\n            return (element.center[0] - element.radius,\n                   element.center[1] - element.radius,\n                   element.center[0] + element.radius,\n                   element.center[1] + element.radius)\n        elif isinstance(element, ArcElement):\n            # Simplified bounds for arc (could be more precise)\n            return (element.center[0] - element.radius,\n                   element.center[1] - element.radius,\n                   element.center[0] + element.radius,\n                   element.center[1] + element.radius)\n        elif isinstance(element, TextElement):\n            # Approximate text bounds\n            return (element.position[0], element.position[1],\n                   element.position[0] + len(element.text) * element.font_size * 0.6,\n                   element.position[1] + element.font_size)\n        return None\n        \n    def _generate_auto_dimensions(self) -> List[DimensionElement]:\n        \"\"\"Generate automatic dimensions for key features\"\"\"\n        dimensions = []\n        \n        # Find key dimensional features\n        links = [e for e in self.geometry_elements if isinstance(e, LineElement) and \n                e.properties.get('outline') != True]\n        \n        for link in links[:5]:  # Limit to first 5 links to avoid clutter\n            length = math.sqrt((link.end_point[0] - link.start_point[0])**2 + \n                             (link.end_point[1] - link.start_point[1])**2)\n            \n            dimension = DimensionElement(\n                start_point=link.start_point,\n                end_point=link.end_point,\n                dimension_value=length,\n                dimension_text=f\"{length:.1f}\",\n                properties={'auto_generated': True},\n                style={'stroke_width': 1.0, 'stroke_color': 'blue'},\n                layer='dimensions'\n            )\n            dimensions.append(dimension)\n            \n        return dimensions\n        \n    def _generate_title_block(self) -> List[GeometryElement]:\n        \"\"\"Generate title block elements\"\"\"\n        elements = []\n        \n        # Title block position (bottom right)\n        bounds = self.drawing_bounds\n        title_x = bounds[2] - 200\n        title_y = bounds[3] - 100\n        \n        # Title block rectangle\n        title_rect_lines = [\n            LineElement((title_x, title_y), (title_x + 180, title_y),\n                       properties={'title_block': True}, style={'stroke_width': 2.0}, layer='annotations'),\n            LineElement((title_x + 180, title_y), (title_x + 180, title_y + 80),\n                       properties={'title_block': True}, style={'stroke_width': 2.0}, layer='annotations'),\n            LineElement((title_x + 180, title_y + 80), (title_x, title_y + 80),\n                       properties={'title_block': True}, style={'stroke_width': 2.0}, layer='annotations'),\n            LineElement((title_x, title_y + 80), (title_x, title_y),\n                       properties={'title_block': True}, style={'stroke_width': 2.0}, layer='annotations')\n        ]\n        elements.extend(title_rect_lines)\n        \n        # Title text\n        mechanism_name = self.mechanism_data.get('name', 'Mechanism')\n        title_text = TextElement(\n            position=(title_x + 10, title_y + 60),\n            text=mechanism_name,\n            font_size=16.0,\n            properties={'title_block': True},\n            style={'text_color': 'black'},\n            layer='annotations'\n        )\n        elements.append(title_text)\n        \n        # Scale text\n        scale_text = TextElement(\n            position=(title_x + 10, title_y + 40),\n            text=f\"Scale: {self.export_settings.scale}:1\",\n            font_size=12.0,\n            properties={'title_block': True},\n            style={'text_color': 'black'},\n            layer='annotations'\n        )\n        elements.append(scale_text)\n        \n        # Date text\n        import datetime\n        date_text = TextElement(\n            position=(title_x + 10, title_y + 20),\n            text=f\"Date: {datetime.date.today().strftime('%Y-%m-%d')}\",\n            font_size=10.0,\n            properties={'title_block': True},\n            style={'text_color': 'black'},\n            layer='annotations'\n        )\n        elements.append(date_text)\n        \n        return elements\n        \n    def _generate_material_specs(self) -> List[GeometryElement]:\n        \"\"\"Generate material specification elements\"\"\"\n        elements = []\n        \n        # Material specifications table (simplified)\n        bounds = self.drawing_bounds\n        spec_x = bounds[0] + 20\n        spec_y = bounds[3] - 120\n        \n        # Material spec text\n        material_text = TextElement(\n            position=(spec_x, spec_y),\n            text=\"MATERIALS:\",\n            font_size=12.0,\n            properties={'material_spec': True},\n            style={'text_color': 'black'},\n            layer='annotations'\n        )\n        elements.append(material_text)\n        \n        # Default material specifications\n        materials = [\n            \"Links: Steel, Grade A36\",\n            \"Joints: Bronze bushings\",\n            \"Fasteners: Grade 8 bolts\"\n        ]\n        \n        for i, material in enumerate(materials):\n            mat_text = TextElement(\n                position=(spec_x, spec_y - 20 - i * 15),\n                text=material,\n                font_size=10.0,\n                properties={'material_spec': True},\n                style={'text_color': 'black'},\n                layer='annotations'\n            )\n            elements.append(mat_text)\n            \n        return elements\n        \n    def _generate_assembly_notes(self) -> List[GeometryElement]:\n        \"\"\"Generate assembly note elements\"\"\"\n        elements = []\n        \n        # Assembly notes (simplified)\n        bounds = self.drawing_bounds\n        notes_x = bounds[0] + 20\n        notes_y = bounds[1] + 100\n        \n        notes_text = TextElement(\n            position=(notes_x, notes_y),\n            text=\"ASSEMBLY NOTES:\",\n            font_size=12.0,\n            properties={'assembly_notes': True},\n            style={'text_color': 'black'},\n            layer='annotations'\n        )\n        elements.append(notes_text)\n        \n        # Default assembly notes\n        notes = [\n            \"1. Lubricate all joints before assembly\",\n            \"2. Check clearances per drawing\",\n            \"3. Apply thread locker to fasteners\"\n        ]\n        \n        for i, note in enumerate(notes):\n            note_text = TextElement(\n                position=(notes_x, notes_y - 20 - i * 15),\n                text=note,\n                font_size=10.0,\n                properties={'assembly_notes': True},\n                style={'text_color': 'black'},\n                layer='annotations'\n            )\n            elements.append(note_text)\n            \n        return elements


class PdfExporter(BlueprintExporter):\n    \"\"\"Professional PDF blueprint exporter with full annotation support\"\"\"\n    \n    def export(self, output_path: str) -> Tuple[List[str], List[str]]:\n        \"\"\"Export blueprint as PDF\"\"\"\n        warnings = []\n        errors = []\n        \n        try:\n            # Get page size\n            page_size = self._get_page_size()\n            \n            # Create PDF canvas\n            c = canvas.Canvas(output_path, pagesize=page_size)\n            \n            # Set up coordinate system and scaling\n            self._setup_pdf_coordinates(c, page_size)\n            \n            # Draw all geometry elements\n            self._draw_geometry_elements(c)\n            \n            # Save PDF\n            c.save()\n            \n            logger.info(f\"PDF blueprint exported to: {output_path}\")\n            \n        except Exception as e:\n            error_msg = f\"PDF export failed: {str(e)}\"\n            logger.error(error_msg)\n            errors.append(error_msg)\n            \n        return warnings, errors\n        \n    def _get_page_size(self):\n        \"\"\"Get page size based on settings\"\"\"\n        size_map = {\n            'A4': A4,\n            'A3': A3,\n            'Letter': letter,\n            'Legal': legal\n        }\n        return size_map.get(self.export_settings.paper_size, A4)\n        \n    def _setup_pdf_coordinates(self, canvas, page_size):\n        \"\"\"Setup coordinate system and scaling for PDF\"\"\"\n        page_width, page_height = page_size\n        \n        # Calculate scaling to fit drawing bounds on page\n        bounds_width = self.drawing_bounds[2] - self.drawing_bounds[0]\n        bounds_height = self.drawing_bounds[3] - self.drawing_bounds[1]\n        \n        # Leave margins\n        margin = 50\n        available_width = page_width - 2 * margin\n        available_height = page_height - 2 * margin\n        \n        # Calculate scale to fit\n        scale_x = available_width / bounds_width if bounds_width > 0 else 1.0\n        scale_y = available_height / bounds_height if bounds_height > 0 else 1.0\n        scale = min(scale_x, scale_y) * self.export_settings.scale\n        \n        # Set transformation\n        canvas.translate(margin, margin)\n        canvas.scale(scale, scale)\n        canvas.translate(-self.drawing_bounds[0], -self.drawing_bounds[1])\n        \n    def _draw_geometry_elements(self, canvas):\n        \"\"\"Draw all geometry elements on PDF canvas\"\"\"\n        # Group elements by layer for proper drawing order\n        layers = ['constraints', 'mechanism', 'details', 'dimensions', 'annotations', 'symbols']\n        \n        for layer in layers:\n            layer_elements = [e for e in self.geometry_elements if e.layer == layer]\n            \n            for element in layer_elements:\n                self._draw_element(canvas, element)\n                \n    def _draw_element(self, canvas, element: GeometryElement):\n        \"\"\"Draw a single geometry element\"\"\"\n        if isinstance(element, LineElement):\n            self._draw_line(canvas, element)\n        elif isinstance(element, CircleElement):\n            self._draw_circle(canvas, element)\n        elif isinstance(element, ArcElement):\n            self._draw_arc(canvas, element)\n        elif isinstance(element, DimensionElement):\n            self._draw_dimension(canvas, element)\n        elif isinstance(element, TextElement):\n            self._draw_text(canvas, element)\n            \n    def _draw_line(self, canvas, element: LineElement):\n        \"\"\"Draw line element\"\"\"\n        style = element.style\n        \n        # Set line style\n        canvas.setStrokeColor(self._get_color(style.get('stroke_color', 'black')))\n        canvas.setLineWidth(style.get('stroke_width', 1.0))\n        \n        # Set line style (solid, dashed, etc.)\n        if style.get('stroke_style') == 'dashed':\n            canvas.setDash([3, 3])\n        else:\n            canvas.setDash([])\n            \n        # Draw line\n        canvas.line(element.start_point[0], element.start_point[1],\n                   element.end_point[0], element.end_point[1])\n                   \n    def _draw_circle(self, canvas, element: CircleElement):\n        \"\"\"Draw circle element\"\"\"\n        style = element.style\n        \n        # Set style\n        canvas.setStrokeColor(self._get_color(style.get('stroke_color', 'black')))\n        canvas.setLineWidth(style.get('stroke_width', 1.0))\n        \n        if style.get('fill_color'):\n            canvas.setFillColor(self._get_color(style.get('fill_color')))\n            canvas.circle(element.center[0], element.center[1], element.radius, fill=1)\n        else:\n            canvas.circle(element.center[0], element.center[1], element.radius, fill=0)\n            \n    def _draw_arc(self, canvas, element: ArcElement):\n        \"\"\"Draw arc element\"\"\"\n        # Note: ReportLab doesn't have a direct arc method, so we approximate with path\n        import math\n        \n        style = element.style\n        canvas.setStrokeColor(self._get_color(style.get('stroke_color', 'black')))\n        canvas.setLineWidth(style.get('stroke_width', 1.0))\n        \n        # Create path for arc\n        path = canvas.beginPath()\n        \n        # Convert angles to radians\n        start_rad = math.radians(element.start_angle)\n        end_rad = math.radians(element.end_angle)\n        \n        # Generate arc points\n        num_segments = max(8, int(abs(element.end_angle - element.start_angle) / 15))\n        for i in range(num_segments + 1):\n            angle = start_rad + (end_rad - start_rad) * i / num_segments\n            x = element.center[0] + element.radius * math.cos(angle)\n            y = element.center[1] + element.radius * math.sin(angle)\n            \n            if i == 0:\n                path.moveTo(x, y)\n            else:\n                path.lineTo(x, y)\n                \n        canvas.drawPath(path, stroke=1, fill=0)\n        \n    def _draw_dimension(self, canvas, element: DimensionElement):\n        \"\"\"Draw dimension element with arrows and text\"\"\"\n        style = element.style\n        canvas.setStrokeColor(self._get_color(style.get('stroke_color', 'blue')))\n        canvas.setLineWidth(style.get('stroke_width', 1.0))\n        \n        # Calculate dimension line position\n        dx = element.end_point[0] - element.start_point[0]\n        dy = element.end_point[1] - element.start_point[1]\n        length = math.sqrt(dx*dx + dy*dy)\n        \n        if length == 0:\n            return\n            \n        # Unit vector perpendicular to dimension line\n        perp_x = -dy / length\n        perp_y = dx / length\n        \n        # Dimension line points\n        offset = element.offset\n        dim_start = (element.start_point[0] + perp_x * offset,\n                    element.start_point[1] + perp_y * offset)\n        dim_end = (element.end_point[0] + perp_x * offset,\n                  element.end_point[1] + perp_y * offset)\n        \n        # Draw dimension line\n        canvas.line(dim_start[0], dim_start[1], dim_end[0], dim_end[1])\n        \n        # Draw extension lines\n        canvas.line(element.start_point[0], element.start_point[1],\n                   dim_start[0], dim_start[1])\n        canvas.line(element.end_point[0], element.end_point[1],\n                   dim_end[0], dim_end[1])\n        \n        # Draw arrows (simplified)\n        arrow_size = 5\n        # Start arrow\n        canvas.line(dim_start[0], dim_start[1],\n                   dim_start[0] - arrow_size * (dx/length), dim_start[1] - arrow_size * (dy/length))\n        # End arrow  \n        canvas.line(dim_end[0], dim_end[1],\n                   dim_end[0] + arrow_size * (dx/length), dim_end[1] + arrow_size * (dy/length))\n        \n        # Draw dimension text\n        text_x = (dim_start[0] + dim_end[0]) / 2\n        text_y = (dim_start[1] + dim_end[1]) / 2\n        \n        canvas.setFillColor(self._get_color('black'))\n        canvas.drawCentredText(text_x, text_y, element.dimension_text)\n        \n    def _draw_text(self, canvas, element: TextElement):\n        \"\"\"Draw text element\"\"\"\n        style = element.style\n        \n        canvas.setFillColor(self._get_color(style.get('text_color', 'black')))\n        canvas.setFont(\"Helvetica\", element.font_size)\n        \n        if element.rotation != 0:\n            canvas.saveState()\n            canvas.translate(element.position[0], element.position[1])\n            canvas.rotate(element.rotation)\n            canvas.drawString(0, 0, element.text)\n            canvas.restoreState()\n        else:\n            canvas.drawString(element.position[0], element.position[1], element.text)\n            \n    def _get_color(self, color_name: str):\n        \"\"\"Convert color name to ReportLab color\"\"\"\n        color_map = {\n            'black': black,\n            'blue': blue,\n            'red': red,\n            'green': green,\n            'white': (1, 1, 1),\n            'gray': (0.5, 0.5, 0.5)\n        }\n        return color_map.get(color_name, black)\n\n\nclass SvgExporter(BlueprintExporter):\n    \"\"\"SVG blueprint exporter for web and documentation\"\"\"\n    \n    def export(self, output_path: str) -> Tuple[List[str], List[str]]:\n        \"\"\"Export blueprint as SVG\"\"\"\n        warnings = []\n        errors = []\n        \n        try:\n            # Create SVG root element\n            svg_root = self._create_svg_root()\n            \n            # Add geometry elements\n            self._add_geometry_to_svg(svg_root)\n            \n            # Write SVG file\n            tree = ET.ElementTree(svg_root)\n            tree.write(output_path, xml_declaration=True, encoding='utf-8')\n            \n            logger.info(f\"SVG blueprint exported to: {output_path}\")\n            \n        except Exception as e:\n            error_msg = f\"SVG export failed: {str(e)}\"\n            logger.error(error_msg)\n            errors.append(error_msg)\n            \n        return warnings, errors\n        \n    def _create_svg_root(self):\n        \"\"\"Create SVG root element with proper dimensions\"\"\"\n        bounds = self.drawing_bounds\n        width = bounds[2] - bounds[0]\n        height = bounds[3] - bounds[1]\n        \n        svg = ET.Element('svg')\n        svg.set('xmlns', 'http://www.w3.org/2000/svg')\n        svg.set('width', f\"{width}\")\n        svg.set('height', f\"{height}\")\n        svg.set('viewBox', f\"{bounds[0]} {bounds[1]} {width} {height}\")\n        \n        return svg\n        \n    def _add_geometry_to_svg(self, svg_root):\n        \"\"\"Add all geometry elements to SVG\"\"\"\n        # Group elements by layer\n        layers = ['constraints', 'mechanism', 'details', 'dimensions', 'annotations', 'symbols']\n        \n        for layer in layers:\n            layer_elements = [e for e in self.geometry_elements if e.layer == layer]\n            \n            if layer_elements:\n                # Create layer group\n                layer_group = ET.SubElement(svg_root, 'g')\n                layer_group.set('class', f'layer-{layer}')\n                \n                for element in layer_elements:\n                    self._add_element_to_svg(layer_group, element)\n                    \n    def _add_element_to_svg(self, parent, element: GeometryElement):\n        \"\"\"Add single element to SVG\"\"\"\n        if isinstance(element, LineElement):\n            self._add_line_to_svg(parent, element)\n        elif isinstance(element, CircleElement):\n            self._add_circle_to_svg(parent, element)\n        elif isinstance(element, TextElement):\n            self._add_text_to_svg(parent, element)\n        # Add more element types as needed\n        \n    def _add_line_to_svg(self, parent, element: LineElement):\n        \"\"\"Add line element to SVG\"\"\"\n        line = ET.SubElement(parent, 'line')\n        line.set('x1', str(element.start_point[0]))\n        line.set('y1', str(element.start_point[1]))\n        line.set('x2', str(element.end_point[0]))\n        line.set('y2', str(element.end_point[1]))\n        \n        # Apply style\n        style = element.style\n        line.set('stroke', style.get('stroke_color', 'black'))\n        line.set('stroke-width', str(style.get('stroke_width', 1.0)))\n        \n        if style.get('stroke_style') == 'dashed':\n            line.set('stroke-dasharray', '3,3')\n            \n    def _add_circle_to_svg(self, parent, element: CircleElement):\n        \"\"\"Add circle element to SVG\"\"\"\n        circle = ET.SubElement(parent, 'circle')\n        circle.set('cx', str(element.center[0]))\n        circle.set('cy', str(element.center[1]))\n        circle.set('r', str(element.radius))\n        \n        # Apply style\n        style = element.style\n        circle.set('stroke', style.get('stroke_color', 'black'))\n        circle.set('stroke-width', str(style.get('stroke_width', 1.0)))\n        circle.set('fill', style.get('fill_color', 'none'))\n        \n    def _add_text_to_svg(self, parent, element: TextElement):\n        \"\"\"Add text element to SVG\"\"\"\n        text = ET.SubElement(parent, 'text')\n        text.set('x', str(element.position[0]))\n        text.set('y', str(element.position[1]))\n        text.set('font-size', str(element.font_size))\n        text.set('font-family', 'Arial, sans-serif')\n        \n        if element.rotation != 0:\n            text.set('transform', f'rotate({element.rotation} {element.position[0]} {element.position[1]})')\n            \n        text.text = element.text\n\n\nclass DxfExporter(BlueprintExporter):\n    \"\"\"DXF blueprint exporter for CAD applications\"\"\"\n    \n    def export(self, output_path: str) -> Tuple[List[str], List[str]]:\n        \"\"\"Export blueprint as DXF\"\"\"\n        warnings = []\n        errors = []\n        \n        try:\n            # For now, create a simple DXF-like text format\n            # In production, would use ezdxf library\n            with open(output_path, 'w') as f:\n                f.write(\"999\\nDXF Blueprint Export\\n\")\n                f.write(\"0\\nSECTION\\n\")\n                f.write(\"2\\nENTITIES\\n\")\n                \n                # Write geometry elements\n                for element in self.geometry_elements:\n                    self._write_dxf_element(f, element)\n                    \n                f.write(\"0\\nENDSEC\\n\")\n                f.write(\"0\\nEOF\\n\")\n                \n            logger.info(f\"DXF blueprint exported to: {output_path}\")\n            \n        except Exception as e:\n            error_msg = f\"DXF export failed: {str(e)}\"\n            logger.error(error_msg)\n            errors.append(error_msg)\n            \n        return warnings, errors\n        \n    def _write_dxf_element(self, file, element: GeometryElement):\n        \"\"\"Write single element to DXF file\"\"\"\n        if isinstance(element, LineElement):\n            file.write(\"0\\nLINE\\n\")\n            file.write(f\"10\\n{element.start_point[0]}\\n\")\n            file.write(f\"20\\n{element.start_point[1]}\\n\")\n            file.write(f\"11\\n{element.end_point[0]}\\n\")\n            file.write(f\"21\\n{element.end_point[1]}\\n\")\n        elif isinstance(element, CircleElement):\n            file.write(\"0\\nCIRCLE\\n\")\n            file.write(f\"10\\n{element.center[0]}\\n\")\n            file.write(f\"20\\n{element.center[1]}\\n\")\n            file.write(f\"40\\n{element.radius}\\n\")\n        # Add more element types as needed